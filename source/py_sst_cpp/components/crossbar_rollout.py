#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Crossbar-Based Rollout Unit for MCTS Acceleration
==================================================

Integrates:
1. Dual Crossbar Neural Network (evaluation logic)
2. Literature-calibrated Hardware Model (area, power, timing)
3. MCTS Rollout Interface (board evaluation and playout)

This replaces the random rollout with NN-guided evaluation.
"""

import sys
import os
from typing import Dict, Any, Tuple, Optional
import random

# Add components to path

from py_sst_cpp.components.crossbar_nn import DualCrossbarNN
from py_sst_cpp.components.crossbar_hardware import CrossbarHardwareModel


class CrossbarRolloutUnit:
    """
    Complete crossbar-based rollout unit

    Combines:
    - Neural network evaluation (DualCrossbarNN)
    - Hardware specifications (CrossbarHardwareModel)
    - Rollout logic (NN-guided playout)
    """

    def __init__(self, board_size: int, weights_file: Optional[str] = None, tech_node: str = '28nm'):
        """
        Initialize crossbar rollout unit

        Args:
            board_size: Board dimension (e.g., 5 for 5×5 board)
            weights_file: Path to pre-trained weights (optional)
            tech_node: Technology node for hardware model (default 28nm)
        """
        self.board_size = board_size

        # Initialize neural network
        self.nn = DualCrossbarNN(board_size=board_size, weights_file=weights_file)

        # Initialize hardware model
        self.hw_model = CrossbarHardwareModel()

        # Get hardware specifications
        # Hidden size varies by board size (Supplementary Table 4)
        hidden_sizes = {2: 32, 3: 32, 5: 96, 9: 96, 13: 96, 19: 96}
        crossbar_rows = board_size * board_size
        crossbar_cols = hidden_sizes.get(board_size, 96)
        self.hw_specs = self.hw_model.estimate_crossbar(rows=crossbar_rows, cols=crossbar_cols, tech_node=tech_node)

        # Statistics
        self.total_rollouts = 0
        self.total_evaluations = 0
        self.total_moves_simulated = 0
        self.total_cycles = 0
        self.total_energy_pj = 0.0

        # Configuration
        self.max_rollout_moves = 50  # Maximum moves per rollout
        self.use_nn_guidance = False  # Use NN for move selection (vs random) - DISABLED: untrained weights are biased

    def perform_rollout(self, board_state: list, current_player: int) -> Tuple[int, float, int]:
        """
        Perform NN-guided rollout from current position

        Args:
            board_state: 2D list representing board (1=black, -1=white, 0=empty)
            current_player: Current player (1=black, -1=white)

        Returns:
            Tuple of (winner, evaluation, moves_made)
            - winner: 1 (black), -1 (white), or 0 (draw)
            - evaluation: Float value 0.0-1.0
            - moves_made: Number of moves simulated
        """
        # Copy board state for simulation
        rollout_board = [row[:] for row in board_state]
        rollout_player = current_player
        num_moves = 0

        self.total_rollouts += 1

        # Simulate game until terminal or max moves
        for _ in range(self.max_rollout_moves):
            # Find valid moves
            valid_moves = self._get_valid_moves(rollout_board)

            if not valid_moves:
                break  # No more moves available

            # Select move (NN-guided or random)
            if self.use_nn_guidance and len(valid_moves) > 1:
                selected_move = self._select_best_move_nn(rollout_board, valid_moves, rollout_player)
            else:
                selected_move = random.choice(valid_moves)

            # Make move
            row, col = selected_move
            rollout_board[row][col] = rollout_player
            num_moves += 1
            self.total_moves_simulated += 1

            # Switch player
            rollout_player = -rollout_player

        # Evaluate final position with neural network
        evaluation, evaluation_details = self.nn.evaluate(rollout_board)
        self.total_evaluations += 1

        # Track hardware metrics
        self.total_cycles += self.hw_specs['read_latency_cycles'] * (num_moves + 1)  # +1 for final eval
        self.total_energy_pj += self.hw_specs['read_energy_pj'] * (num_moves + 1)

        # Determine winner from evaluation
        if evaluation > 0.5:
            winner = 1  # Black wins
        elif evaluation < 0.5:
            winner = -1  # White wins
        else:
            winner = 0  # Draw

        return winner, evaluation, num_moves

    def perform_rollout_fast(self, board_state: list, current_player: int) -> Tuple[int, float, int]:
        """
        Fast rollout: Immediate NN evaluation without playout

        This is faster but may be less accurate than full playout.
        Useful when iteration budget is high.

        Args:
            board_state: 2D list representing board
            current_player: Current player

        Returns:
            Tuple of (winner, evaluation, moves_made=0)
        """
        self.total_rollouts += 1

        # Direct NN evaluation
        evaluation, evaluation_details = self.nn.evaluate(board_state)
        self.total_evaluations += 1

        # Track hardware metrics (single evaluation)
        self.total_cycles += self.hw_specs['read_latency_cycles']
        self.total_energy_pj += self.hw_specs['read_energy_pj']

        # Determine winner
        if evaluation > 0.5:
            winner = 1
        elif evaluation < 0.5:
            winner = -1
        else:
            winner = 0

        return winner, evaluation, 0  # 0 moves made

    def _get_valid_moves(self, board: list) -> list:
        """Get list of valid (empty) positions"""
        valid_moves = []
        for row in range(self.board_size):
            for col in range(self.board_size):
                if board[row][col] == 0:
                    valid_moves.append((row, col))
        return valid_moves

    def _select_best_move_nn(self, board: list, valid_moves: list, player: int) -> Tuple[int, int]:
        """
        Select best move using neural network evaluation

        For each valid move, evaluate resulting position and choose best.

        Args:
            board: Current board state
            valid_moves: List of (row, col) tuples
            player: Current player

        Returns:
            Best move (row, col)
        """
        best_move = valid_moves[0]
        best_evaluation = float('-inf') if player == 1 else float('inf')

        for move in valid_moves:
            row, col = move

            # Make temporary move
            board[row][col] = player

            # Evaluate position
            evaluation, _ = self.nn.evaluate(board)
            self.total_evaluations += 1

            # Track hardware (evaluation cost)
            self.total_cycles += self.hw_specs['read_latency_cycles']
            self.total_energy_pj += self.hw_specs['read_energy_pj']

            # Undo move
            board[row][col] = 0

            # Update best move
            if player == 1:  # Black wants high evaluation
                if evaluation > best_evaluation:
                    best_evaluation = evaluation
                    best_move = move
            else:  # White wants low evaluation
                if evaluation < best_evaluation:
                    best_evaluation = evaluation
                    best_move = move

        return best_move

    def get_hardware_specs(self) -> Dict[str, Any]:
        """Get hardware specifications"""
        return self.hw_specs.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """Get rollout statistics"""
        avg_moves_per_rollout = self.total_moves_simulated / self.total_rollouts if self.total_rollouts > 0 else 0
        avg_cycles_per_rollout = self.total_cycles / self.total_rollouts if self.total_rollouts > 0 else 0
        avg_energy_per_rollout_pj = self.total_energy_pj / self.total_rollouts if self.total_rollouts > 0 else 0

        return {
            'total_rollouts': self.total_rollouts,
            'total_evaluations': self.total_evaluations,
            'total_moves_simulated': self.total_moves_simulated,
            'total_cycles': self.total_cycles,
            'total_energy_pj': self.total_energy_pj,
            'avg_moves_per_rollout': avg_moves_per_rollout,
            'avg_cycles_per_rollout': avg_cycles_per_rollout,
            'avg_energy_per_rollout_pj': avg_energy_per_rollout_pj,
            'avg_energy_per_rollout_nj': avg_energy_per_rollout_pj / 1000.0
        }

    def reset_statistics(self):
        """Reset statistics counters"""
        self.total_rollouts = 0
        self.total_evaluations = 0
        self.total_moves_simulated = 0
        self.total_cycles = 0
        self.total_energy_pj = 0.0

    def get_neural_network_specs(self) -> Dict[str, Any]:
        """Get neural network specifications"""
        return self.nn.get_specs()

    def print_specs(self):
        """Print complete specifications"""
        print()
        print("=" * 70)
        print("CROSSBAR-BASED ROLLOUT UNIT SPECIFICATIONS")
        print("=" * 70)

        # Neural network specs
        nn_specs = self.get_neural_network_specs()
        print("\nNeural Network:")
        print(f"  Architecture: {nn_specs['rows']}×{nn_specs['cols']} crossbar")
        print(f"  Total memristors: {nn_specs['total_memristors']}")
        print(f"  Conductance levels: {nn_specs['conductance_levels']}")
        print(f"  Conductance range: {nn_specs['G_min_uS']:.1f}µS - {nn_specs['G_max_uS']:.1f}µS")
        print(f"  Average conductance: {nn_specs['avg_conductance_uS']:.1f}µS")
        print(f"  Decision threshold (I_ref): {nn_specs['I_ref_mA']:.2f}mA")

        # Hardware specs
        print("\nHardware (literature-calibrated @ 28nm):")
        print(f"  Area: {self.hw_specs['area_mm2']:.6f} mm² ({self.hw_specs['area_um2']:.1f} µm²)")
        print(f"  Power: {self.hw_specs['power_mw']:.3f} mW")
        print(f"    Static: {self.hw_specs['static_power_mw']:.3f} mW")
        print(f"    Dynamic: {self.hw_specs['dynamic_power_mw']:.3f} mW")
        print(f"  Read energy: {self.hw_specs['read_energy_pj']:.2f} pJ")
        print(f"  Read latency: {self.hw_specs['read_latency_cycles']} cycle ({self.hw_specs['read_latency_ns']:.2f} ns)")
        print(f"  Operating frequency: {self.hw_specs['frequency_mhz']:.0f} MHz")

        print()
        print("=" * 70)


def test_crossbar_rollout():
    """Test crossbar rollout unit"""
    print("🧪 Testing Crossbar-Based Rollout Unit")
    print("=" * 70)

    # Test 5×5 board
    print("\n1. Initializing 5×5 Crossbar Rollout Unit")
    print("-" * 70)

    rollout_unit = CrossbarRolloutUnit(board_size=5)
    rollout_unit.print_specs()

    # Test rollout
    print("\n2. Testing Rollout")
    print("-" * 70)

    board_5x5_empty = [[0]*5 for _ in range(5)]
    board_5x5_mixed = [
        [1, -1, 0, 0, 0],
        [0, 1, -1, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0]
    ]

    print("\nEmpty board rollout:")
    winner, eval_val, moves = rollout_unit.perform_rollout(board_5x5_empty, current_player=1)
    print(f"  Winner: {winner}, Evaluation: {eval_val:.3f}, Moves: {moves}")

    print("\nMixed board rollout:")
    winner, eval_val, moves = rollout_unit.perform_rollout(board_5x5_mixed, current_player=1)
    print(f"  Winner: {winner}, Evaluation: {eval_val:.3f}, Moves: {moves}")

    # Test fast rollout
    print("\nFast rollout (immediate NN evaluation):")
    winner, eval_val, moves = rollout_unit.perform_rollout_fast(board_5x5_mixed, current_player=1)
    print(f"  Winner: {winner}, Evaluation: {eval_val:.3f}, Moves: {moves}")

    # Statistics
    print("\n3. Rollout Statistics")
    print("-" * 70)
    stats = rollout_unit.get_statistics()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    print("\n✅ Crossbar rollout unit test complete!")


if __name__ == "__main__":
    test_crossbar_rollout()
