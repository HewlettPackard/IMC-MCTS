# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Heuristic evaluation for simplified Go positions.

This module implements the EXACT same evaluation function used during
neural network training (from datagen.py). Consistency is critical for
ensuring the tournament evaluates positions the same way the NNs were trained.

Evaluation formula:
    score = material_diff + 0.5 * territory_diff + 0.1 * liberty_diff

Where:
    - material_diff = black_stones - white_stones
    - territory_diff = black_territory - white_territory (3x3 heuristic)
    - liberty_diff = black_liberties - white_liberties (individual stone count)

Game outcome:
    - score > 1.5  → Black wins (return 1.0)
    - score < -1.5 → White wins (return 0.0)
    - otherwise    → Draw (return 0.5)
"""

import numpy as np
from typing import Tuple


class HeuristicEvaluator:
    """
    Evaluates board positions using the training heuristic.

    This class provides the same evaluation logic used in crossbar_training/datagen.py
    to ensure tournament games are scored consistently with how the neural networks
    were trained.
    """

    def __init__(self, board_size: int):
        """
        Initialize evaluator for a specific board size.

        Args:
            board_size: Size of the board (e.g., 9 for 9x9)
        """
        self.board_size = board_size

    def evaluate_position(self, board: np.ndarray) -> Tuple[float, dict]:
        """
        Evaluate who is winning in this position.

        Args:
            board: numpy array of shape (board_size, board_size)
                   Values: 1 = Black, -1 = White, 0 = Empty

        Returns:
            Tuple of (outcome, details) where:
                outcome: 1.0 (Black wins), 0.0 (White wins), or 0.5 (Draw)
                details: dict with score breakdown {
                    'total_score': float,
                    'material_diff': int,
                    'territory_diff': int,
                    'liberty_diff': int,
                    'black_stones': int,
                    'white_stones': int,
                    'black_territory': int,
                    'white_territory': int,
                    'black_liberties': int,
                    'white_liberties': int
                }
        """
        # Stage 1: count the stone advantage.
        black_stones = np.sum(board == 1)
        white_stones = np.sum(board == -1)
        material_diff = black_stones - white_stones

        # Stage 2: estimate territory from each empty point's 3x3 neighborhood.
        black_territory, white_territory = self._count_territory(board)
        territory_diff = black_territory - white_territory

        # Stage 3: count per-stone orthogonal liberties.
        black_liberties = self._count_liberties(board, 1)
        white_liberties = self._count_liberties(board, -1)
        liberty_diff = black_liberties - white_liberties

        # Apply the exact training score from datagen.py.
        total_score = material_diff + territory_diff * 0.5 + liberty_diff * 0.1

        # Convert the score with the exact training thresholds.
        if total_score > 1.5:
            outcome = 1.0    # Black wins
        elif total_score < -1.5:
            outcome = 0.0    # White wins
        else:
            outcome = 0.5    # Draw/close game

        # Preserve every score component for tournament analysis.
        details = {
            'total_score': total_score,
            'material_diff': int(material_diff),
            'territory_diff': int(territory_diff),
            'liberty_diff': int(liberty_diff),
            'black_stones': int(black_stones),
            'white_stones': int(white_stones),
            'black_territory': int(black_territory),
            'white_territory': int(white_territory),
            'black_liberties': int(black_liberties),
            'white_liberties': int(white_liberties)
        }

        return outcome, details

    def _count_territory(self, board: np.ndarray) -> Tuple[int, int]:
        """
        Count territory controlled by each color using 3x3 neighborhood heuristic.

        This is a simplified territory estimation (NOT real Go scoring):
        - For each empty point, count surrounding stones in 3x3 neighborhood
        - If more black neighbors: counts as black territory
        - If more white neighbors: counts as white territory
        - Equal neighbors: neutral (doesn't count for either)

        Args:
            board: numpy array of shape (board_size, board_size)

        Returns:
            Tuple of (black_territory, white_territory)
        """
        black_territory = 0
        white_territory = 0

        for row in range(self.board_size):
            for col in range(self.board_size):
                if board[row, col] == 0:
                    # Count black and white stones in the local 3x3 window.
                    nearby_black = 0
                    nearby_white = 0

                    for row_offset in range(-1, 2):
                        for col_offset in range(-1, 2):
                            neighbor_row = row + row_offset
                            neighbor_col = col + col_offset
                            if 0 <= neighbor_row < self.board_size and 0 <= neighbor_col < self.board_size:
                                if board[neighbor_row, neighbor_col] == 1:
                                    nearby_black += 1
                                elif board[neighbor_row, neighbor_col] == -1:
                                    nearby_white += 1

                    # Assign the empty point to the local majority color.
                    if nearby_black > nearby_white:
                        black_territory += 1
                    elif nearby_white > nearby_black:
                        white_territory += 1
                    # Equal neighborhoods remain neutral.

        return black_territory, white_territory

    def _count_liberties(self, board: np.ndarray, color: int) -> int:
        """
        Count total liberties for a color (individual stone liberties, NOT group).

        This counts adjacent empty spaces for each stone independently.
        NOTE: This is NOT group liberty counting from real Go!
        Same stone's liberty can be counted multiple times if it's adjacent
        to multiple stones of the same color.

        Args:
            board: numpy array of shape (board_size, board_size)
            color: 1 for Black, -1 for White

        Returns:
            Total liberty count (sum across all stones)
        """
        total_liberties = 0

        for row in range(self.board_size):
            for col in range(self.board_size):
                if board[row, col] == color:
                    # Count empty orthogonal neighbors for this stone.
                    for row_offset, col_offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        neighbor_row = row + row_offset
                        neighbor_col = col + col_offset
                        if 0 <= neighbor_row < self.board_size and 0 <= neighbor_col < self.board_size:
                            if board[neighbor_row, neighbor_col] == 0:
                                total_liberties += 1

        return total_liberties

    def get_winner_string(self, outcome: float) -> str:
        """
        Convert numerical outcome to readable string.

        Args:
            outcome: 1.0 (Black), 0.0 (White), or 0.5 (Draw)

        Returns:
            "Black", "White", or "Draw"
        """
        if outcome == 1.0:
            return "Black"
        elif outcome == 0.0:
            return "White"
        else:
            return "Draw"

    def format_evaluation(self, outcome: float, details: dict) -> str:
        """
        Format evaluation results as human-readable string.

        Args:
            outcome: Game outcome (1.0/0.5/0.0)
            details: Score breakdown dictionary

        Returns:
            Formatted string with evaluation details
        """
        winner = self.get_winner_string(outcome)

        lines = [
            f"Winner: {winner}",
            f"Total Score: {details['total_score']:.2f}",
            f"",
            f"Score Breakdown:",
            f"  Material: {details['material_diff']:+d} (B:{details['black_stones']} W:{details['white_stones']})",
            f"  Territory: {details['territory_diff']:+d} (B:{details['black_territory']} W:{details['white_territory']}) [×0.5]",
            f"  Liberties: {details['liberty_diff']:+d} (B:{details['black_liberties']} W:{details['white_liberties']}) [×0.1]",
        ]

        return "\n".join(lines)


def test_evaluator():
    """Simple test to verify evaluator works correctly."""

    # Test on 5x5 board
    evaluator = HeuristicEvaluator(board_size=5)

    # Create a test position
    # B = Black (1), W = White (-1), . = Empty (0)
    #  . . . . .
    #  . B B . .
    #  . B W . .
    #  . . W . .
    #  . . . . .

    board = np.zeros((5, 5), dtype=int)
    board[1, 1] = 1  # Black
    board[1, 2] = 1  # Black
    board[2, 1] = 1  # Black
    board[2, 2] = -1  # White
    board[3, 2] = -1  # White

    outcome, details = evaluator.evaluate_position(board)

    print("Test Position Evaluation:")
    print(evaluator.format_evaluation(outcome, details))
    print()

    # Expected: Black has more stones (3 vs 2), more liberties, more territory
    assert outcome == 1.0, "Black should win this position"
    assert details['material_diff'] > 0, "Black has more stones"

    print("✓ Evaluator test passed!")


if __name__ == "__main__":
    test_evaluator()
