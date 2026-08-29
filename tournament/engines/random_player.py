# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Random Player for Tournament Baseline.

This player selects moves uniformly at random from all legal positions.
Provides a trivial baseline to establish the floor of playing strength.
"""

import numpy as np
import random
from typing import Tuple


class RandomPlayer:
    """
    Random baseline player that selects moves uniformly at random.

    This serves as the weakest possible baseline - any intelligent player
    should significantly outperform random play.
    """

    def __init__(
        self,
        board_size: int,
        player_id: int = 1,  # 1 for Black, -1 for White
        **kwargs  # Accept and ignore other parameters for compatibility
    ):
        """
        Initialize Random player.

        Args:
            board_size: Size of board (e.g., 9 for 9x9)
            player_id: Player color (1 = Black, -1 = White)
            **kwargs: Ignored parameters for compatibility with other players
        """
        self.board_size = board_size
        self.player_id = player_id

    def select_move(self, board_state: np.ndarray) -> Tuple[int, int]:
        """
        Select a random legal move.

        Args:
            board_state: numpy array (board_size, board_size) with:
                         1 = Black, -1 = White, 0 = Empty

        Returns:
            Tuple of (row, col) for selected move
        """
        # Enumerate every empty board point in row-major order.
        legal_moves = []
        for row in range(self.board_size):
            for col in range(self.board_size):
                if board_state[row, col] == 0:
                    legal_moves.append((row, col))

        # Use the shared invalid-move sentinel when the board is full.
        if len(legal_moves) == 0:
            return (-1, -1)

        # Sample uniformly from the empty points.
        return random.choice(legal_moves)

    def get_tree_stats(self) -> dict:
        """
        Get player statistics (for compatibility with MCTS players).

        Returns:
            Empty dictionary (random player has no tree)
        """
        return {'nodes': 0, 'type': 'random'}


def test_random_player():
    """Test random player on simple position."""
    print("Testing Random Player")
    print("=" * 80)

    # Create test board (5x5)
    board = np.zeros((5, 5), dtype=int)
    board[2, 2] = 1  # Black in center
    board[1, 1] = -1  # White

    # Create player
    player = RandomPlayer(board_size=5)

    print("Test board:")
    for row in board:
        print(" ".join([
            'B' if x == 1 else 'W' if x == -1 else '.'
            for x in row
        ]))
    print()

    # Test 10 random moves
    print("Testing 10 random moves:")
    for i in range(10):
        move = player.select_move(board)
        print(f"  Move {i+1}: {move} (row={move[0]}, col={move[1]})")

        # Verify move is valid
        assert board[move[0], move[1]] == 0, f"Move {move} should be on empty position"

    print()
    print("✓ Random player test passed!")


if __name__ == "__main__":
    test_random_player()
