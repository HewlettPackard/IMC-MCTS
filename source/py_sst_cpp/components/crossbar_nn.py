#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Dual Crossbar-Based Neural Network for MCTS Rollout
====================================================

Implements the dual crossbar architecture from MCTS_IMC2 with:
- 4×32 or board_size²×32 memristor crossbar
- 8 discrete conductance levels (20-200 µS)
- Learnable I_ref threshold for binary classification
- Literature-calibrated hardware specifications (public link forthcoming)

Based on: MCTS_IMC2/01_VALIDATION/2x2/.../simple_crossbar.py
"""

import numpy as np
import json
from typing import Dict, Any, Optional, Tuple


class DualCrossbarNN:
    """
    Dual crossbar-based neural network for board evaluation

    Architecture:
    - Input: Board state encoded as voltage vector (0V=white, 0.5V=empty, 1V=black)
    - Crossbar: board_size² × 32 memristor matrix
    - Operation: V × G = I (matrix-vector multiplication)
    - Decision: I_total > I_ref → Black wins (1.0), else White wins (0.0)
    """

    def __init__(self, board_size: int, weights_file: Optional[str] = None):
        """
        Initialize dual crossbar neural network

        Args:
            board_size: Board dimension (e.g., 5 for 5×5 board)
            weights_file: Path to pre-trained weights (optional)
        """
        self.board_size = board_size
        self.num_positions = board_size * board_size

        # Crossbar dimensions: num_positions × 32
        self.rows = self.num_positions
        self.cols = 32
        self.total_memristors = self.rows * self.cols

        # Multi-level memristor conductance states (8 levels)
        self.G_MIN = 20e-6     # 20 µS minimum conductance
        self.G_MAX = 200e-6    # 200 µS maximum conductance
        self.num_levels = 8

        # Create linearly spaced conductance levels
        self.G_levels = np.linspace(self.G_MIN, self.G_MAX, self.num_levels)

        # Voltage levels for encoding
        self.V_low = 0.0       # 0V for white stones
        self.V_mid = 0.5       # 0.5V for empty positions
        self.V_high = 1.0      # 1V for black stones

        # Learnable reference current (decision threshold)
        self.I_ref = 2e-3      # 2mA initial reference current

        # Track whether weights are trained
        self.weights_trained = False

        # Initialize or load weights
        if weights_file is not None:
            if not self.load_weights(weights_file):
                print(f"❌ Failed to load weights from {weights_file}, initializing randomly")
                self.G_matrix = self._initialize_matrix()
        else:
            # Try to auto-load trained weights
            self.G_matrix = self._initialize_matrix()
            self._try_load_default_weights()

    @classmethod
    def from_weights(cls, board_size: int, weights_file: str):
        """Create instance with pre-trained weights"""
        return cls(board_size=board_size, weights_file=weights_file)

    def _try_load_default_weights(self):
        """Try to automatically load best available trained weights"""
        import glob

        # Look for trained weights in trained_weights directory
        weights_dir = "trained_weights"
        pattern = f"{weights_dir}/crossbar_{self.board_size}x{self.board_size}_*_acc_*.pkl"

        weight_files = glob.glob(pattern)

        if not weight_files:
            print(f"ℹ️  No trained weights found for {self.board_size}×{self.board_size}, using random initialization")
            return

        # Find the file with highest accuracy in filename
        best_weights_file = None
        best_accuracy = 0.0

        for weights_file in weight_files:
            try:
                # Extract accuracy from filename (format: ...acc_0.726.pkl)
                accuracy_text = weights_file.split('_acc_')[-1].replace('.pkl', '')
                accuracy = float(accuracy_text)
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_weights_file = weights_file
            except:
                continue

        if best_weights_file:
            print(f"🔄 Auto-loading trained weights: {best_weights_file}")
            if self.load_weights(best_weights_file):
                self.weights_trained = True
                print(f"   Accuracy: {best_accuracy*100:.1f}%")

    def _initialize_matrix(self) -> np.ndarray:
        """Initialize conductance matrix with strategic distribution"""
        conductance_matrix = np.zeros((self.rows, self.cols))

        # Use higher conductance levels (levels 3-7) for better starting point
        useful_levels = 5
        start_level = 3
        end_level = start_level + useful_levels

        total_memristors = self.rows * self.cols
        memristors_per_level = total_memristors // useful_levels

        level_assignments = []
        for index in range(start_level, end_level):
            level_assignments.extend([index] * memristors_per_level)

        # Handle remainder
        for index in range(total_memristors - len(level_assignments)):
            level_assignments.append(start_level + (index % useful_levels))

        # Shuffle assignments
        np.random.shuffle(level_assignments)

        # Assign conductances
        assignment_index = 0
        for index in range(self.rows):
            for col in range(self.cols):
                level_index = level_assignments[assignment_index]
                conductance_matrix[index, col] = self.G_levels[level_index]
                assignment_index += 1

        return conductance_matrix

    def encode_board(self, board_state: list) -> np.ndarray:
        """
        Convert 2D board state to voltage vector

        Args:
            board_state: 2D list representing board (1=black, -1=white, 0=empty)

        Returns:
            Voltage vector of length board_size²
        """
        input_voltages = np.zeros(self.num_positions)

        for row in range(self.board_size):
            for col in range(self.board_size):
                position_index = row * self.board_size + col
                stone = board_state[row][col]

                if stone == 0:      # Empty
                    input_voltages[position_index] = self.V_mid   # 0.5V
                elif stone == -1:   # White
                    input_voltages[position_index] = self.V_low   # 0V
                elif stone == 1:    # Black
                    input_voltages[position_index] = self.V_high  # 1V

        return input_voltages

    def evaluate(self, board_state: list) -> Tuple[float, Dict[str, Any]]:
        """
        Evaluate board position using crossbar

        Args:
            board_state: 2D list representing board

        Returns:
            Tuple of (evaluation, debug_info)
            - evaluation: 1.0 (black winning), 0.5 (neutral), 0.0 (white winning)
            - debug_info: Dictionary with internal values for debugging
        """
        # Get input voltage vector
        V_input = self.encode_board(board_state)

        # Matrix multiplication: V × G = I
        I_output = np.dot(V_input, self.G_matrix)

        # Sum all output currents
        I_total = np.sum(I_output)

        # Calculate actual achievable current range based on trained weights
        # (not theoretical max, which assumes all G_MAX)

        # For empty board: all positions at V_mid (0.5V)
        V_empty = np.ones(self.num_positions) * self.V_mid
        I_empty = np.dot(V_empty, self.G_matrix)
        I_empty_total = np.sum(I_empty)

        # For all black: all positions at V_high (1.0V)
        V_black = np.ones(self.num_positions) * self.V_high
        I_black = np.dot(V_black, self.G_matrix)
        I_black_total = np.sum(I_black)

        # For all white: all positions at V_low (0.0V)
        V_white = np.ones(self.num_positions) * self.V_low
        I_white = np.dot(V_white, self.G_matrix)
        I_white_total = np.sum(I_white)

        # Calibrated normalization using actual weight distribution
        I_max = I_black_total
        I_min = I_white_total

        # Normalized evaluation: map I_total to [0.0, 1.0] range
        # 0.0 = white winning, 0.5 = neutral, 1.0 = black winning
        if abs(I_max - I_min) > 1e-10:
            raw_evaluation = (I_total - I_min) / (I_max - I_min)
        else:
            raw_evaluation = 0.5

        # For untrained weights (random initialization), the raw evaluation is biased
        # Use stone difference instead for more neutral evaluation
        black_stones = sum(1 for row in board_state for cell in row if cell == 1)
        white_stones = sum(1 for row in board_state for cell in row if cell == -1)

        # Evaluate based on relative advantage: (black - white) / total_positions
        # This accounts for first-player advantage
        stone_difference = black_stones - white_stones
        max_stone_difference = self.num_positions  # Maximum possible difference

        # Map [-max_diff, +max_diff] to [0.0, 1.0]
        # stone_diff = -max_diff → evaluation = 0.0 (all white)
        # stone_diff = 0 → evaluation = 0.5 (balanced)
        # stone_diff = +max_diff → evaluation = 1.0 (all black)
        stone_evaluation = (stone_difference + max_stone_difference) / (2 * max_stone_difference) if max_stone_difference > 0 else 0.5

        # Blend crossbar and stone count based on whether weights are trained
        if self.weights_trained:
            # Use trained crossbar weights (MCTS-based training)
            blend_weight = 0.8  # 80% crossbar, 20% stone count for stability
        else:
            # Use pure stone count for untrained weights
            blend_weight = 0.0  # 0% crossbar, 100% stone count

        evaluation = blend_weight * raw_evaluation + (1 - blend_weight) * stone_evaluation

        # Clamp to [0, 1] range to handle edge cases
        evaluation = max(0.0, min(1.0, evaluation))

        # Debug information
        debug_info = {
            'I_total': float(I_total),
            'I_total_mA': float(I_total * 1e3),
            'I_max': float(I_max),
            'I_max_mA': float(I_max * 1e3),
            'I_min': float(I_min),
            'I_ref': float(self.I_ref),  # Keep for compatibility
            'I_ref_mA': float(self.I_ref * 1e3),
            'avg_conductance_uS': float(np.mean(self.G_matrix) * 1e6),
            'normalization': 'I_total / I_max'
        }

        return evaluation, debug_info

    def forward_pass(self, board_state: list) -> float:
        """Simple forward pass without debug info"""
        evaluation, _ = self.evaluate(board_state)
        return evaluation

    def save_weights(self, filename: str) -> str:
        """Save trained weights to JSON file"""
        from datetime import datetime

        weights_data = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'board_size': self.board_size,
                'architecture': f"{self.rows}x{self.cols}",
                'total_memristors': self.total_memristors,
                'num_levels': self.num_levels,
                'description': f'Dual crossbar weights for {self.board_size}×{self.board_size} board'
            },
            'configuration': {
                'G_MIN': float(self.G_MIN),
                'G_MAX': float(self.G_MAX),
                'G_levels': [float(g) for g in self.G_levels],
                'V_low': float(self.V_low),
                'V_mid': float(self.V_mid),
                'V_high': float(self.V_high),
                'I_ref': float(self.I_ref)
            },
            'weights': {
                'G_matrix': self.G_matrix.tolist(),
                'avg_conductance': float(np.mean(self.G_matrix)),
                'conductance_distribution': [int(np.sum(self.G_matrix == level)) for level in self.G_levels]
            }
        }

        with open(filename, 'w') as weights_file:
            json.dump(weights_data, weights_file, indent=2)

        print(f"💾 Weights saved to: {filename}")
        return filename

    def load_weights(self, filename: str) -> bool:
        """Load trained weights from JSON or pickle file"""
        try:
            # Detect file type and load accordingly
            if filename.endswith('.pkl'):
                import pickle
                with open(filename, 'rb') as weights_file:
                    weights_data = pickle.load(weights_file)
            else:
                with open(filename, 'r') as weights_file:
                    weights_data = json.load(weights_file)

            # Verify architecture compatibility
            metadata = weights_data['metadata']
            file_architecture = metadata.get('architecture', '')

            # Check board size compatibility
            if metadata.get('board_size') != self.board_size:
                print(f"⚠️ Board size mismatch: file has {metadata.get('board_size')}, expected {self.board_size}")
                return False

            # Load configuration (handle both 'config' and 'configuration' keys)
            weight_config = weights_data.get('config', weights_data.get('configuration', {}))
            self.G_MIN = weight_config['G_MIN']
            self.G_MAX = weight_config['G_MAX']
            self.num_levels = weight_config.get('num_levels', 8)
            self.G_levels = np.linspace(self.G_MIN, self.G_MAX, self.num_levels)

            # Load weights (use conductances from training)
            weights_section = weights_data['weights']

            if 'conductances' in weights_section:
                # New format: load conductances directly
                self.G_matrix = np.array(weights_section['conductances'])
            elif 'G_matrix' in weights_section:
                # Old format: load G_matrix
                self.G_matrix = np.array(weights_section['G_matrix'])
            else:
                print("❌ No weights found in file")
                return False

            print(f"✅ Weights loaded from: {filename}")
            print(f"   Architecture: {metadata.get('architecture', 'N/A')}")
            print(f"   Board size: {metadata.get('board_size', 'N/A')}×{metadata.get('board_size', 'N/A')}")

            return True

        except FileNotFoundError:
            print(f"❌ Weights file not found: {filename}")
            return False
        except Exception as error:
            print(f"❌ Failed to load weights: {error}")
            return False

    def get_specs(self) -> Dict[str, Any]:
        """Get crossbar specifications"""
        return {
            'board_size': self.board_size,
            'rows': self.rows,
            'cols': self.cols,
            'total_memristors': self.total_memristors,
            'conductance_levels': self.num_levels,
            'G_min_uS': self.G_MIN * 1e6,
            'G_max_uS': self.G_MAX * 1e6,
            'I_ref_mA': self.I_ref * 1e3,
            'avg_conductance_uS': float(np.mean(self.G_matrix) * 1e6)
        }


def test_dual_crossbar_nn():
    """Test dual crossbar NN implementation"""
    print("🧪 Testing Dual Crossbar NN")
    print("=" * 60)

    # Test 2×2 board
    print("\n1. Testing 2×2 Board")
    print("-" * 60)

    nn_2x2 = DualCrossbarNN(board_size=2)
    specs = nn_2x2.get_specs()
    print(f"Architecture: {specs['rows']}×{specs['cols']} ({specs['total_memristors']} memristors)")
    print(f"Conductance range: {specs['G_min_uS']:.1f}µS - {specs['G_max_uS']:.1f}µS")
    print(f"Average conductance: {specs['avg_conductance_uS']:.1f}µS")
    print(f"I_ref: {specs['I_ref_mA']:.2f}mA")

    # Test evaluation
    board_2x2_empty = [[0, 0], [0, 0]]
    board_2x2_black = [[1, 1], [0, 0]]
    board_2x2_white = [[-1, -1], [0, 0]]

    eval_empty, debug_empty = nn_2x2.evaluate(board_2x2_empty)
    eval_black, debug_black = nn_2x2.evaluate(board_2x2_black)
    eval_white, debug_white = nn_2x2.evaluate(board_2x2_white)

    print(f"\nEmpty board: {eval_empty:.1f} (I_total={debug_empty['I_total_mA']:.2f}mA)")
    print(f"Two black:   {eval_black:.1f} (I_total={debug_black['I_total_mA']:.2f}mA)")
    print(f"Two white:   {eval_white:.1f} (I_total={debug_white['I_total_mA']:.2f}mA)")

    # Test 5×5 board
    print("\n2. Testing 5×5 Board")
    print("-" * 60)

    nn_5x5 = DualCrossbarNN(board_size=5)
    specs_5x5 = nn_5x5.get_specs()
    print(f"Architecture: {specs_5x5['rows']}×{specs_5x5['cols']} ({specs_5x5['total_memristors']} memristors)")
    print(f"Average conductance: {specs_5x5['avg_conductance_uS']:.1f}µS")

    # Test evaluation on empty 5×5 board
    board_5x5_empty = [[0]*5 for _ in range(5)]
    eval_5x5, debug_5x5 = nn_5x5.evaluate(board_5x5_empty)
    print(f"\nEmpty 5×5 board: {eval_5x5:.1f} (I_total={debug_5x5['I_total_mA']:.2f}mA)")

    print("\n✅ Dual Crossbar NN test complete!")


if __name__ == "__main__":
    test_dual_crossbar_nn()
