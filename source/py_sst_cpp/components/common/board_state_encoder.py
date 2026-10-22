#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Board State Encoder for CAM-Based MCTS Tree Storage

This module implements board state encoding and hashing for content-addressable
memory (CAM) lookups in the MCTS accelerator. The CAM searches by board state
CONTENT rather than node ID, enabling transposition detection.

Key Features:
- 2-bit per cell encoding (00=empty, 01=black, 10=white)
- Zobrist hashing for efficient state comparison
- State canonicalization for symmetry handling
- Support for board sizes 2x2 through 19x19
"""

import random
from typing import List, Tuple, Optional
import numpy as np


class BoardStateEncoder:
    """
    Encodes board states for CAM-based tree storage.

    The CAM stores parent board states and searches by content (not by ID).
    This enables O(1) parallel lookup and automatic transposition detection.
    """

    def __init__(self, board_size: int, seed: int = 42):
        """
        Initialize board state encoder.

        Args:
            board_size: Board dimension (e.g., 5 for 5x5, 9 for 9x9)
            seed: Random seed for Zobrist hash table generation
        """
        self.board_size = board_size
        self.num_positions = board_size * board_size
        self.bits_per_cell = 2  # 00=empty, 01=black, 10=white
        self.total_bits = self.num_positions * self.bits_per_cell

        # Initialize Zobrist hash table for efficient state hashing
        self._init_zobrist_table(seed)

    def _init_zobrist_table(self, seed: int):
        """
        Initialize Zobrist hash table for position hashing.

        Zobrist hashing: Each (position, piece) combination has a random number.
        Board hash = XOR of all occupied position's random numbers.

        This gives O(1) incremental hash updates when making moves.
        """
        random.seed(seed)
        np.random.seed(seed)

        # Zobrist table: [position][piece_type] -> random 64-bit number
        # piece_type: 0=empty (unused), 1=black, 2=white
        self.zobrist_table = np.zeros((self.num_positions, 3), dtype=np.uint64)

        for position_index in range(self.num_positions):
            for piece in range(1, 3):  # Only black and white (empty doesn't contribute)
                # Generate random 64-bit number
                self.zobrist_table[position_index][piece] = random.getrandbits(64)

    def encode_to_bits(self, board: List[List[int]]) -> int:
        """
        Encode board state to bit pattern for CAM storage.

        Each cell is encoded as 2 bits:
        - 00 (0): Empty
        - 01 (1): Black stone
        - 10 (2): White stone
        - 11 (3): Reserved

        Args:
            board: 2D list representing board state
                   board[row][col] = 0 (empty), 1 (black), 2 (white)

        Returns:
            Bit pattern (integer) representing the board state
            For 5x5: 50-bit pattern, 9x9: 162-bit pattern, etc.

        Example for 2x2 board:
            [[1, 0],   # Black at (0,0), empty at (0,1)
             [2, 1]]   # White at (1,0), black at (1,1)

            Encoding (row-major order):
            01 00 10 01 = 0b01001001 = 0x49
        """
        if len(board) != self.board_size or len(board[0]) != self.board_size:
            raise ValueError(f"Board size must be {self.board_size}x{self.board_size}")

        bit_pattern = 0
        for row in range(self.board_size):
            for col in range(self.board_size):
                cell_value = board[row][col]
                if cell_value < 0 or cell_value > 2:
                    raise ValueError(f"Invalid cell value {cell_value} at ({row},{col})")

                # Shift pattern left by 2 bits and add current cell
                bit_pattern = (bit_pattern << self.bits_per_cell) | (cell_value & 0x3)

        return bit_pattern

    def decode_from_bits(self, pattern: int) -> List[List[int]]:
        """
        Decode bit pattern back to board state.

        Args:
            pattern: Bit pattern representing board state

        Returns:
            2D list representing the board
        """
        board = [[0] * self.board_size for _ in range(self.board_size)]

        # Extract cells in reverse order (LSB first)
        for row in range(self.board_size - 1, -1, -1):
            for col in range(self.board_size - 1, -1, -1):
                cell_value = pattern & 0x3  # Extract lowest 2 bits
                board[row][col] = cell_value
                pattern >>= self.bits_per_cell  # Shift right by 2 bits

        return board

    def zobrist_hash(self, board: List[List[int]]) -> int:
        """
        Compute Zobrist hash of board state.

        This is the PRIMARY hash used for CAM lookups because:
        - O(1) incremental updates when making moves
        - Uniform distribution (good for hash tables)
        - 64-bit hash reduces collisions

        Args:
            board: 2D list representing board state

        Returns:
            64-bit Zobrist hash of the board state
        """
        hash_value = 0

        for row in range(self.board_size):
            for col in range(self.board_size):
                piece = board[row][col]
                if piece != 0:  # Only hash non-empty cells
                    position_index = row * self.board_size + col
                    hash_value ^= int(self.zobrist_table[position_index][piece])

        return hash_value

    def incremental_hash_update(self, current_hash: int, row: int, col: int,
                                old_piece: int, new_piece: int) -> int:
        """
        Update Zobrist hash incrementally after a move.

        This is MUCH faster than recomputing the entire hash.
        Used during MCTS rollout when simulating moves.

        Args:
            current_hash: Current board hash
            row, col: Position of the move
            old_piece: Previous piece at position (usually 0=empty)
            new_piece: New piece at position (1=black or 2=white)

        Returns:
            Updated hash after the move
        """
        position_index = row * self.board_size + col

        # XOR out old piece contribution (if any)
        if old_piece != 0:
            current_hash ^= int(self.zobrist_table[position_index][old_piece])

        # XOR in new piece contribution
        if new_piece != 0:
            current_hash ^= int(self.zobrist_table[position_index][new_piece])

        return current_hash

    def canonicalize_state(self, board: List[List[int]]) -> Tuple[List[List[int]], str]:
        """
        Canonicalize board state to detect symmetric positions.

        Many board games have symmetries (rotations, reflections).
        Different symmetries of the same position should map to the same CAM entry.

        Args:
            board: 2D list representing board state

        Returns:
            Tuple of (canonical_board, transformation_applied)
            canonical_board: Lexicographically smallest symmetric variant
            transformation: String describing which symmetry was canonical

        Symmetries considered:
        - Original
        - 90° rotation
        - 180° rotation
        - 270° rotation
        - Horizontal flip
        - Vertical flip
        - Diagonal flip
        - Anti-diagonal flip
        """
        symmetric_boards = []
        transformation_names = []

        # Original
        symmetric_boards.append(board)
        transformation_names.append("original")

        # Rotations
        rotation_90 = self._rotate_90(board)
        symmetric_boards.append(rotation_90)
        transformation_names.append("rot90")

        rotation_180 = self._rotate_90(rotation_90)
        symmetric_boards.append(rotation_180)
        transformation_names.append("rot180")

        rotation_270 = self._rotate_90(rotation_180)
        symmetric_boards.append(rotation_270)
        transformation_names.append("rot270")

        # Reflections
        horizontal_flip = self._flip_horizontal(board)
        symmetric_boards.append(horizontal_flip)
        transformation_names.append("h_flip")

        vertical_flip = self._flip_vertical(board)
        symmetric_boards.append(vertical_flip)
        transformation_names.append("v_flip")

        # Diagonal flips
        diagonal_flip = self._flip_diagonal(board)
        symmetric_boards.append(diagonal_flip)
        transformation_names.append("d_flip")

        antidiagonal_flip = self._flip_antidiagonal(board)
        symmetric_boards.append(antidiagonal_flip)
        transformation_names.append("ad_flip")

        # Find lexicographically smallest variant (canonical form)
        canonical_index = 0
        canonical_board = symmetric_boards[0]

        for variant_index, variant in enumerate(symmetric_boards[1:], 1):
            if self._compare_boards(variant, canonical_board) < 0:
                canonical_index = variant_index
                canonical_board = variant

        return canonical_board, transformation_names[canonical_index]

    def _rotate_90(self, board: List[List[int]]) -> List[List[int]]:
        """Rotate board 90° clockwise"""
        board_size = self.board_size
        rotated = [[0] * board_size for _ in range(board_size)]
        for row in range(board_size):
            for col in range(board_size):
                rotated[col][board_size-1-row] = board[row][col]
        return rotated

    def _flip_horizontal(self, board: List[List[int]]) -> List[List[int]]:
        """Flip board horizontally"""
        return [row[::-1] for row in board]

    def _flip_vertical(self, board: List[List[int]]) -> List[List[int]]:
        """Flip board vertically"""
        return board[::-1]

    def _flip_diagonal(self, board: List[List[int]]) -> List[List[int]]:
        """Flip board along main diagonal"""
        board_size = self.board_size
        flipped = [[0] * board_size for _ in range(board_size)]
        for row in range(board_size):
            for col in range(board_size):
                flipped[col][row] = board[row][col]
        return flipped

    def _flip_antidiagonal(self, board: List[List[int]]) -> List[List[int]]:
        """Flip board along anti-diagonal"""
        board_size = self.board_size
        flipped = [[0] * board_size for _ in range(board_size)]
        for row in range(board_size):
            for col in range(board_size):
                flipped[board_size-1-col][board_size-1-row] = board[row][col]
        return flipped

    def _compare_boards(self, board1: List[List[int]], board2: List[List[int]]) -> int:
        """
        Compare two boards lexicographically.

        Returns:
            -1 if board1 < board2
             0 if board1 == board2
            +1 if board1 > board2
        """
        for row1, row2 in zip(board1, board2):
            for cell1, cell2 in zip(row1, row2):
                if cell1 < cell2:
                    return -1
                elif cell1 > cell2:
                    return 1
        return 0

    def get_bit_width(self) -> int:
        """Get total bit width needed for board state encoding"""
        return self.total_bits

    def get_hash_width(self) -> int:
        """Get bit width of Zobrist hash (always 64 bits)"""
        return 64


# Convenience functions for common board sizes
def create_encoder_2x2() -> BoardStateEncoder:
    """Create encoder for 2x2 boards (8 bits)"""
    return BoardStateEncoder(board_size=2)


def create_encoder_5x5() -> BoardStateEncoder:
    """Create encoder for 5x5 boards (50 bits)"""
    return BoardStateEncoder(board_size=5)


def create_encoder_9x9() -> BoardStateEncoder:
    """Create encoder for 9x9 boards (162 bits)"""
    return BoardStateEncoder(board_size=9)


def create_encoder_19x19() -> BoardStateEncoder:
    """Create encoder for 19x19 boards (722 bits)"""
    return BoardStateEncoder(board_size=19)


if __name__ == "__main__":
    # Test the encoder
    print("Testing BoardStateEncoder...")

    # Test 5x5 board
    encoder = create_encoder_5x5()
    print(f"\n5x5 Board Encoder:")
    print(f"  Bit width: {encoder.get_bit_width()} bits")
    print(f"  Hash width: {encoder.get_hash_width()} bits")

    # Create test board
    test_board = [
        [1, 0, 2, 0, 0],
        [0, 1, 0, 2, 0],
        [0, 0, 0, 0, 1],
        [0, 2, 0, 1, 0],
        [0, 0, 0, 0, 0]
    ]

    # Test encoding
    bit_pattern = encoder.encode_to_bits(test_board)
    print(f"\nBit pattern: 0x{bit_pattern:013X} ({encoder.get_bit_width()} bits)")

    # Test decoding
    decoded = encoder.decode_from_bits(bit_pattern)
    assert decoded == test_board, "Decode failed!"
    print("✓ Encode/decode test passed")

    # Test Zobrist hashing
    hash1 = encoder.zobrist_hash(test_board)
    print(f"\nZobrist hash: 0x{hash1:016X}")

    # Test incremental hash update
    hash2 = encoder.incremental_hash_update(hash1, 4, 4, 0, 2)  # Add white at (4,4)
    test_board[4][4] = 2
    hash3 = encoder.zobrist_hash(test_board)
    assert hash2 == hash3, "Incremental hash failed!"
    print("✓ Incremental hash update test passed")

    # Test canonicalization
    canonical, transform = encoder.canonicalize_state(test_board)
    print(f"\nCanonical form: {transform}")

    print("\n✓ All tests passed!")
