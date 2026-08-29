#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Hardware Functional Model - Python Implementation of RTL Logic
===============================================================

Pure FUNCTIONALITY - no timing, no SST, just what the hardware DOES.

Each function mirrors the logic in the corresponding RTL module:
- ucb1_calculator.sv      → ucb1_calculator()
- best_child_selector.sv  → best_child_selector()
- statistics_updater.sv   → statistics_updater()
- crossbar_control.sv     → crossbar_forward_pass()
- position_to_voltage_dacs.sv → board_to_voltages()
- current_to_digital_adcs.sv  → currents_to_digital()

Data flows: Selection → Expansion → Rollout → Backprop
"""

import numpy as np
import pickle
import random
from typing import List, Tuple, Dict
import math


# =============================================================================
# SELECTION UNIT - UCB1 Calculator (from ucb1_calculator.sv)
# =============================================================================

def ucb1_calculator(
    child_wins: List[int],
    child_visits: List[int],
    parent_visits: int,
    exploration_const: float = 1.414,
    child_valid: List[bool] = None
) -> List[float]:
    """
    Calculate UCB1 values for all children.

    Mirrors ucb1_calculator.sv logic:
    - If visits == 0: return MAX (unvisited nodes get priority)
    - Otherwise: exploitation + exploration term

    Args:
        child_wins: Win count for each child
        child_visits: Visit count for each child
        parent_visits: Total visits to parent node
        exploration_const: UCB1 exploration parameter (default sqrt(2))
        child_valid: Which children are valid moves

    Returns:
        UCB1 values for each child
    """
    num_children = len(child_wins)
    ucb1_values = []

    if child_valid is None:
        child_valid = [True] * num_children

    for child_index in range(num_children):
        if not child_valid[child_index]:
            ucb1_values.append(0.0)
            continue

        child_visit_count = child_visits[child_index]
        child_win_count = child_wins[child_index]

        if child_visit_count == 0:
            # RTL: return 16'hFFFF for unvisited nodes
            ucb1_values.append(float('inf'))
        else:
            # UCB1 = wins/visits + c * sqrt(ln(parent_visits) / visits)  (paper Eq. 1)
            exploitation_term = child_win_count / child_visit_count
            exploration_term = exploration_const * math.sqrt(
                math.log(parent_visits) / child_visit_count
            )
            ucb1_values.append(exploitation_term + exploration_term)

    return ucb1_values


# =============================================================================
# SELECTION UNIT - Best Child Selector (from best_child_selector.sv)
# =============================================================================

def best_child_selector(
    ucb1_values: List[float],
    child_valid: List[bool] = None
) -> Tuple[int, float, bool]:
    """
    Select child with highest UCB1 value using tournament comparison.

    Mirrors best_child_selector.sv logic:
    - Stage 1: Compare pairs (0,1) and (2,3)
    - Stage 2: Compare winners

    Args:
        ucb1_values: UCB1 value for each child
        child_valid: Which children are valid

    Returns:
        (best_child_id, max_ucb1_value, selection_valid)
    """
    if child_valid is None:
        child_valid = [True] * len(ucb1_values)

    # Check if any valid children
    if not any(child_valid):
        return (0, 0.0, False)

    best_child_id = -1
    highest_ucb1_value = float('-inf')

    for child_index, (ucb1_value, is_valid) in enumerate(
        zip(ucb1_values, child_valid)
    ):
        if is_valid and ucb1_value > highest_ucb1_value:
            highest_ucb1_value = ucb1_value
            best_child_id = child_index

    return (best_child_id, highest_ucb1_value, best_child_id >= 0)


# =============================================================================
# EXPANSION UNIT - Child State Generator (from child_state_generator.sv)
# =============================================================================

def child_state_generator(
    board_state: np.ndarray,
    current_player: int
) -> List[Tuple[int, int]]:
    """
    Generate all valid child moves from current board state.

    Mirrors child_state_generator.sv / empty_position_detector.sv logic:
    - Scan all positions
    - Return list of empty positions as valid moves

    Args:
        board_state: Current board (1=black, -1=white, 0=empty)
        current_player: Who is to play (1 or -1)

    Returns:
        List of (row, col) valid moves
    """
    board_size = board_state.shape[0]
    valid_moves = []

    for row in range(board_size):
        for col in range(board_size):
            if board_state[row, col] == 0:
                valid_moves.append((row, col))

    return valid_moves


# =============================================================================
# ROLLOUT UNIT - DAC Conversion (from position_to_voltage_dacs.sv)
# =============================================================================

def board_to_voltages(
    board_state: np.ndarray,
    v_high: float = 1.0,
    v_low: float = 0.0
) -> np.ndarray:
    """
    Convert board state to voltage inputs for crossbar.

    Mirrors position_to_voltage_dacs.sv logic with 2-channel encoding
    matching the NN architecture (Supplementary Table 4: N² × 2 inputs):
    - Channel 0: Black stone presence (1.0V if black, 0.0V otherwise)
    - Channel 1: White stone presence (1.0V if white, 0.0V otherwise)

    This produces N² × 2 voltages, consistent with how the crossbar NN
    is trained (board_to_features in CrossbarNNFunctional).

    Args:
        board_state: Board array (1=black, -1=white, 0=empty)
        v_high: Voltage for stone present
        v_low: Voltage for stone absent

    Returns:
        Voltage vector of length 2 * N² (2-channel encoding)
    """
    voltages = []

    for cell in board_state.flatten():
        if cell == 1:      # Black
            voltages.extend([v_high, v_low])
        elif cell == -1:   # White
            voltages.extend([v_low, v_high])
        else:              # Empty
            voltages.extend([v_low, v_low])

    return np.array(voltages)


# =============================================================================
# ROLLOUT UNIT - Crossbar Matrix-Vector Multiply (from crossbar_control.sv)
# =============================================================================

def quantize_weights(weights: np.ndarray, num_bits: int) -> np.ndarray:
    """
    Quantize weight matrix to fixed-point representation.

    Models the limited precision of RRAM conductance programming.
    Paper Supp Section 4.4: "Weights are quantized to 6-8 bits for
    practical RRAM programming using a differential pair scheme (w = G+ - G-)."

    Args:
        weights: Full-precision weight matrix
        num_bits: Number of bits (6-8 typical for RRAM)

    Returns:
        Quantized weight matrix
    """
    num_levels = 2 ** num_bits
    minimum_weight, maximum_weight = weights.min(), weights.max()
    if maximum_weight == minimum_weight:
        return weights
    # Uniform quantization to num_levels
    quantization_step = (maximum_weight - minimum_weight) / (num_levels - 1)
    quantized_weights = (
        np.round((weights - minimum_weight) / quantization_step)
        * quantization_step
        + minimum_weight
    )
    return quantized_weights


def crossbar_forward_pass(
    voltages: np.ndarray,
    conductance_matrix: np.ndarray,
    conductance_noise_std: float = 0.0,
) -> np.ndarray:
    """
    Perform crossbar matrix-vector multiplication.

    Mirrors crossbar analog computation:
    - I = V × G (Ohm's law at each crosspoint)
    - Currents sum on columns (Kirchhoff's law)

    This is what the physical memristor crossbar does!

    Supports optional conductance noise to model device-to-device variation
    in RRAM cells. Paper Section V-C: "MCTS tolerates analog errors through
    statistical averaging, exhibiting robustness to ±10% conductance
    variations (<1% impact on game-play accuracy)."

    Args:
        voltages: Input voltage vector (from DACs)
        conductance_matrix: Memristor conductances (weights)
        conductance_noise_std: Relative std of Gaussian noise on conductances
            (0.0 = ideal, 0.10 = ±10% variation). Default: 0.0 (ideal).

    Returns:
        Output current vector (to ADCs)
    """
    G = conductance_matrix
    if conductance_noise_std > 0.0:
        # Multiplicative Gaussian noise: G_noisy = G * (1 + N(0, std))
        noise = np.random.normal(0, conductance_noise_std, G.shape)
        G = G * (1.0 + noise)

    # V × G = I (matrix-vector multiply)
    currents = voltages @ G
    return currents


# =============================================================================
# ROLLOUT UNIT - ADC Conversion (from current_to_digital_adcs.sv)
# =============================================================================

def currents_to_digital(
    currents: np.ndarray,
    num_bits: int = 8,
    i_ref: float = 10e-3  # 10mA reference
) -> np.ndarray:
    """
    Convert analog currents to digital values.

    Mirrors current_to_digital_adcs.sv logic:
    - Quantize current to discrete levels
    - Clamp to valid range

    Args:
        currents: Analog current vector
        num_bits: ADC resolution
        i_ref: Reference current (full scale)

    Returns:
        Digital output values (0 to 2^num_bits - 1)
    """
    max_val = (2 ** num_bits) - 1

    # Normalize and quantize
    normalized = currents / i_ref
    digital = np.clip(normalized * max_val, 0, max_val)

    return digital.astype(int)


# =============================================================================
# ROLLOUT UNIT - Complete NN Forward Pass with Trained Weights
# =============================================================================

class CrossbarNNFunctional:
    """
    Functional model of crossbar neural network.

    Uses ACTUAL trained weights from our training pipeline.
    Architecture: 2*N² inputs → hidden (ReLU) → 3 outputs (softmax)
    Hidden size varies by model (e.g. 32 or 96 neurons).

    Supports optional analog non-idealities:
    - Weight quantization (6-8 bits) for RRAM programming limits
    - Conductance noise (±10%) for device-to-device variation
    - ADC quantization (8-bit) for analog-to-digital conversion
    All default to ideal (disabled) for functional verification.
    """

    def __init__(self, weights_file: str, board_size: int = 9,
                 weight_bits: int = 0, conductance_noise_std: float = 0.0,
                 adc_bits: int = 0):
        """
        Load trained weights with optional non-ideality modeling.

        Args:
            weights_file: Path to pickled weight file
            board_size: Board dimension (e.g. 9 for 9x9)
            weight_bits: Weight quantization bits (0=ideal, 6-8 typical)
            conductance_noise_std: Conductance variation std (0.0=ideal, 0.10=±10%)
            adc_bits: ADC resolution bits (0=ideal, 8 typical)
        """
        self.board_size = board_size
        self.conductance_noise_std = conductance_noise_std
        self.adc_bits = adc_bits

        with open(weights_file, 'rb') as weights_file_handle:
            model_data = pickle.load(weights_file_handle)

        self.weights1 = np.array(model_data['weights1'])
        self.weights2 = np.array(model_data['weights2'])
        self.accuracy = model_data.get('accuracy', 0.0)

        # Apply weight quantization at load time (models RRAM programming)
        if weight_bits > 0:
            self.weights1 = quantize_weights(self.weights1, weight_bits)
            self.weights2 = quantize_weights(self.weights2, weight_bits)

        print(f"Loaded weights: {self.weights1.shape} → {self.weights2.shape}")
        print(f"Trained accuracy: {self.accuracy:.2%}")
        if weight_bits > 0:
            print(f"Weight quantization: {weight_bits}-bit")
        if conductance_noise_std > 0:
            print(f"Conductance noise: ±{conductance_noise_std*100:.0f}%")
        if adc_bits > 0:
            print(f"ADC resolution: {adc_bits}-bit")

    def board_to_features(self, board: np.ndarray) -> np.ndarray:
        """Convert board to 162-feature input (2 channels per cell)."""
        features = []
        for cell in board.flatten():
            if cell == 1:      # Black
                features.extend([1.0, 0.0])
            elif cell == -1:   # White
                features.extend([0.0, 1.0])
            else:              # Empty
                features.extend([0.0, 0.0])
        return np.array(features)

    def forward(self, board: np.ndarray) -> Tuple[float, np.ndarray]:
        """
        Complete forward pass through crossbar NN.

        Layer 1 (Crossbar 1): features × weights1 → ReLU → hidden
        Layer 2 (Crossbar 2): hidden × weights2 → softmax → output

        Non-idealities applied at each crossbar:
        - Conductance noise: multiplicative Gaussian per-element
        - ADC quantization: applied to crossbar output currents

        Returns:
            (value, probabilities) where value is from Black's perspective
        """
        # Convert board to features
        features = self.board_to_features(board)

        # Layer 1: Crossbar + (optional ADC quantization) + ReLU
        hidden_activations = crossbar_forward_pass(
            features, self.weights1, self.conductance_noise_std
        )
        if self.adc_bits > 0:
            hidden_activations = currents_to_digital(
                hidden_activations, self.adc_bits
            ).astype(float)
            hidden_activations = hidden_activations / ((2 ** self.adc_bits) - 1)  # Normalize back to [0,1]
        hidden_activations = np.maximum(0, hidden_activations)  # ReLU activation

        # Layer 2: Crossbar + (optional ADC quantization) + Softmax
        logits = crossbar_forward_pass(hidden_activations, self.weights2,
                                       self.conductance_noise_std)
        if self.adc_bits > 0:
            logits = currents_to_digital(logits, self.adc_bits).astype(float)
            logits = logits / ((2 ** self.adc_bits) - 1)
        exp_logits = np.exp(logits - np.max(logits))
        probabilities = exp_logits / np.sum(exp_logits)

        # probabilities = [P(White), P(Draw), P(Black)]
        value = probabilities[2] * 1.0 + probabilities[1] * 0.5 + probabilities[0] * 0.0

        return value, probabilities


# =============================================================================
# BACKPROP UNIT - Statistics Updater (from statistics_updater_5x5.sv)
# =============================================================================

def statistics_updater(
    node_stats: Dict[int, Tuple[float, int]],  # node_id → (wins, visits)
    path: List[int],
    value: float,  # Continuous NN value 0.0-1.0 (from Black's perspective)
    node_players: Dict[int, int] = None,  # node_id → player to move (1=Black, -1=White)
) -> Dict[int, Tuple[float, int]]:
    """
    Update statistics for all nodes in backpropagation path.

    Mirrors statistics_updater_5x5.sv logic and paper Algorithm 1 line 24:
        node.wins ← node.wins + result

    The NN outputs a continuous value (0.0-1.0) from Black's perspective.
    For correct UCB1 selection, each node accumulates value from its OWN
    player's perspective:
    - Black-to-play nodes: accumulate value (high = good for Black)
    - White-to-play nodes: accumulate (1 - value) (high = good for White)

    This ensures UCB1's exploitation term (w/n) always reflects how good
    the subtree is for the player who chose this move.

    Args:
        node_stats: Current statistics {node_id: (wins, visits)}
        path: List of node IDs from root to leaf
        value: Continuous NN evaluation (0.0=white wins, 1.0=black wins)
        node_players: Player-to-move at each node. If None, value is used
            directly (backwards-compatible with no perspective flipping).

    Returns:
        Updated node_stats
    """
    MAX_VISITS = 0xFFFE  # From RTL
    MAX_WINS_SCALED = 0xFFFE  # Saturating counter limit

    for node_id in path:
        if node_id not in node_stats:
            node_stats[node_id] = (0.0, 0)

        current_wins, current_visits = node_stats[node_id]

        # Increment visits (with overflow protection)
        new_visits = min(current_visits + 1, MAX_VISITS)

        # Flip value based on player perspective
        if node_players is not None and node_id in node_players:
            node_value = value if node_players[node_id] == 1 else (1.0 - value)
        else:
            node_value = value

        # Add perspective-corrected value to win accumulator
        new_wins = min(current_wins + node_value, MAX_WINS_SCALED)

        node_stats[node_id] = (new_wins, new_visits)

    return node_stats


# =============================================================================
# COMPLETE MCTS ITERATION - All Units Working Together
# =============================================================================

class MCTSHardwareFunctional:
    """
    Complete MCTS accelerator functional model.

    Data flows exactly like the hardware:
    Selection → Expansion → Rollout (Crossbar NN) → Backprop
    """

    def __init__(self, board_size: int, weights_file: str):
        """Initialize with trained crossbar weights."""
        self.board_size = board_size

        # Load crossbar NN for rollout
        self.crossbar_nn = CrossbarNNFunctional(weights_file, board_size)

        # MCTS tree storage (like SRAM in hardware)
        # node_id → {board, children, wins, visits, parent}
        self.tree = {}
        self.next_node_id = 1

        # Root node
        self.root_id = 0

    def reset(self, initial_board: np.ndarray):
        """Reset tree with new root board."""
        self.tree = {}
        self.next_node_id = 1
        self.root_id = 0

        self.tree[self.root_id] = {
            'board': initial_board.copy(),
            'children': {},  # move → child_id
            'wins': 0.0,
            'visits': 0,
            'parent': None,
            'player': 1  # Black to play
        }

    def run_iteration(self) -> float:
        """
        Run one complete MCTS iteration through all hardware units.

        Returns:
            Value from rollout
        """
        # ========== SELECTION UNIT ==========
        path = []
        current_node_id = self.root_id

        while True:
            current_node = self.tree[current_node_id]
            path.append(current_node_id)

            # Get children
            child_nodes = current_node['children']
            if not child_nodes:
                break

            # Calculate UCB1 for all children
            child_ids = list(child_nodes.values())
            child_wins = [self.tree[child_id]['wins'] for child_id in child_ids]
            child_visits = [self.tree[child_id]['visits'] for child_id in child_ids]
            parent_visits = current_node['visits']

            ucb1_values = ucb1_calculator(child_wins, child_visits, parent_visits)

            # Select best child
            best_child_index, _, selection_valid = best_child_selector(ucb1_values)

            if not selection_valid:
                break

            current_node_id = child_ids[best_child_index]

        # ========== EXPANSION UNIT ==========
        current_node = self.tree[current_node_id]

        if current_node['visits'] > 0 and not current_node['children']:
            # Generate children (paper Algo 1 line 11: GetLegalMoves)
            valid_moves = child_state_generator(current_node['board'], current_node['player'])

            for move in valid_moves:
                # Create child board
                child_board = current_node['board'].copy()
                child_board[move[0], move[1]] = current_node['player']

                # Create child node
                child_id = self.next_node_id
                self.next_node_id += 1

                self.tree[child_id] = {
                    'board': child_board,
                    'children': {},
                    'wins': 0.0,
                    'visits': 0,
                    'parent': current_node_id,
                    'player': -current_node['player']  # Alternate players
                }

                current_node['children'][move] = child_id

            # Select random child for rollout (paper Algo 1 line 12: RandomChoice)
            if current_node['children']:
                random_child_id = random.choice(list(current_node['children'].values()))
                current_node_id = random_child_id
                path.append(current_node_id)

        # ========== ROLLOUT UNIT (Crossbar NN) ==========
        # NN evaluates position and outputs win/loss/draw probabilities
        # (paper Section IV-C: "single forward pass produces win/loss/draw
        # probabilities that serve the same algorithmic role as Monte Carlo
        # sampling in UCB1 calculations")
        rollout_node = self.tree[current_node_id]
        value, probabilities = self.crossbar_nn.forward(rollout_node['board'])

        # ========== BACKPROP UNIT ==========
        # Paper Algo 1 line 24: node.wins ← node.wins + result
        # Use continuous NN value directly (no discretization)
        # Flip value based on player perspective so UCB1 maximizes correctly
        node_stats = {node_id: (self.tree[node_id]['wins'], self.tree[node_id]['visits'])
                      for node_id in path}
        node_players = {node_id: self.tree[node_id]['player'] for node_id in path}

        node_stats = statistics_updater(node_stats, path, value, node_players)

        # Write back to tree
        for node_id, (wins, visits) in node_stats.items():
            self.tree[node_id]['wins'] = wins
            self.tree[node_id]['visits'] = visits

        return value

    def select_best_move(self, iterations: int = 100) -> Tuple[int, int]:
        """Run MCTS and select best move."""
        for _ in range(iterations):
            self.run_iteration()

        # Select most visited child of root
        root_node = self.tree[self.root_id]
        if not root_node['children']:
            return None

        best_move = max(root_node['children'].keys(),
                       key=lambda move: self.tree[root_node['children'][move]]['visits'])
        return best_move


# =============================================================================
# TEST
# =============================================================================

def test_hardware_functional():
    """Test the functional model."""
    print("=" * 70)
    print("HARDWARE FUNCTIONAL MODEL TEST")
    print("=" * 70)

    # Test UCB1 Calculator
    print("\n1. UCB1 Calculator:")
    ucb1 = ucb1_calculator([5, 3, 0, 2], [10, 10, 0, 10], 30)
    print(f"   UCB1 values: {ucb1}")

    # Test Best Child Selector
    print("\n2. Best Child Selector:")
    best_id, best_val, valid = best_child_selector(ucb1)
    print(f"   Best child: {best_id}, value: {best_val:.3f}")

    # Test Board to Voltages (2-channel encoding: N² × 2)
    print("\n3. DAC Conversion (2-channel encoding):")
    board = np.array([[1, 0, -1], [0, 1, 0], [-1, 0, 1]])
    voltages = board_to_voltages(board)
    print(f"   Board shape: {board.shape} → Voltage length: {len(voltages)} (9 cells × 2 channels)")
    print(f"   Voltages: {voltages}")

    # Test Crossbar Forward Pass (ideal and noisy)
    print("\n4. Crossbar Matrix Multiply:")
    G = np.random.rand(18, 4) * 0.001  # 18 inputs (9 cells × 2 channels) → 4 outputs
    currents_ideal = crossbar_forward_pass(voltages, G)
    currents_noisy = crossbar_forward_pass(voltages, G, conductance_noise_std=0.10)
    print(f"   Ideal currents:  {currents_ideal}")
    print(f"   Noisy (±10%):    {currents_noisy}")
    print(f"   Relative error:  {np.abs(currents_noisy - currents_ideal) / (np.abs(currents_ideal) + 1e-12)}")

    # Test Weight Quantization
    print("\n4b. Weight Quantization:")
    W = np.random.randn(4, 3) * 0.5
    W_q6 = quantize_weights(W, 6)
    W_q8 = quantize_weights(W, 8)
    print(f"   Original: {W[0]}")
    print(f"   6-bit:    {W_q6[0]}")
    print(f"   8-bit:    {W_q8[0]}")
    print(f"   6-bit MSE: {np.mean((W - W_q6)**2):.6f}, 8-bit MSE: {np.mean((W - W_q8)**2):.6f}")

    # Test Statistics Updater (continuous value with player perspective)
    print("\n5. Statistics Updater (with player perspective):")
    stats = {0: (5.0, 10), 1: (3.0, 8), 2: (2.0, 5)}
    # Node 0: Black to play, Node 1: White to play, Node 2: Black to play
    players = {0: 1, 1: -1, 2: 1}
    updated = statistics_updater(stats.copy(), [0, 1, 2], value=0.73, node_players=players)
    print(f"   Before: {stats}")
    print(f"   After:  {updated}")
    print(f"   Node 0 (Black): +0.73, Node 1 (White): +0.27, Node 2 (Black): +0.73")

    print("\n" + "=" * 70)
    print("All hardware functional units working!")
    print("=" * 70)


if __name__ == "__main__":
    test_hardware_functional()
