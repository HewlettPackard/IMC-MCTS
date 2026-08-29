# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Greedy Heuristic Player for Tournament Baseline.

This player selects moves that maximize immediate heuristic value without lookahead.
Uses the same heuristic as NN training: material + 0.5×territory + 0.1×liberties.

Provides a baseline showing value of MCTS tree search vs. pure heuristic evaluation.
"""

import numpy as np
from typing import Tuple

from tournament.engines.heuristic_eval import HeuristicEvaluator


class GreedyPlayer:
    """
    Greedy baseline player that selects moves maximizing immediate heuristic value.

    This player:
    - Evaluates each legal move by playing it and checking the heuristic score
    - Selects the move with the best immediate value
    - Has no lookahead or tree search (greedy one-step)

    Serves as a baseline showing the value of MCTS over pure heuristic play.
    """

    def __init__(
        self,
        board_size: int,
        player_id: int = 1,  # 1 for Black, -1 for White
        **kwargs  # Accept and ignore other parameters for compatibility
    ):
        """
        Initialize Greedy player.

        Args:
            board_size: Size of board (e.g., 9 for 9x9)
            player_id: Player color (1 = Black, -1 = White)
            **kwargs: Ignored parameters for compatibility with other players
        """
        self.board_size = board_size
        self.player_id = player_id

        # Use the exact heuristic that generated the training labels.
        self.evaluator = HeuristicEvaluator(board_size)

    def select_move(self, board_state: np.ndarray) -> Tuple[int, int]:
        """
        Select move with best immediate heuristic value.

        Args:
            board_state: numpy array (board_size, board_size) with:
                         1 = Black, -1 = White, 0 = Empty

        Returns:
            Tuple of (row, col) for best greedy move
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

        # Infer the side to move from the current stone counts.
        black_stones = np.sum(board_state == 1)
        white_stones = np.sum(board_state == -1)

        if black_stones == white_stones:
            current_player = 1  # Black moves (if equal, black goes first)
        else:
            current_player = -1  # White moves

        # Evaluate every one-step candidate from the current player's view.
        best_move = None
        best_value = -float('inf')

        for move in legal_moves:
            row, col = move

            # Apply the candidate move on a private board copy.
            test_board = board_state.copy()
            test_board[row, col] = current_player

            # Score the resulting position with the training heuristic.
            outcome, details = self.evaluator.evaluate_position(test_board)

            # Convert the black-perspective outcome to the mover's perspective.
            if current_player == 1:  # Black player
                value = outcome
            else:  # White player
                value = 1.0 - outcome

            # Preserve row-major tie breaking by replacing only on strict gain.
            if value > best_value:
                best_value = value
                best_move = move

        return best_move if best_move is not None else legal_moves[0]

    def get_tree_stats(self) -> dict:
        """
        Get player statistics (for compatibility with MCTS players).

        Returns:
            Dictionary with player type
        """
        return {'nodes': 0, 'type': 'greedy_heuristic'}


def test_greedy_player():
    """Test greedy player on simple position."""
    print("Testing Greedy Heuristic Player")
    print("=" * 80)

    # Create test board (5x5)
    board = np.zeros((5, 5), dtype=int)
    board[2, 2] = 1  # Black in center
    board[1, 1] = -1  # White

    # Create player (White to move)
    player = GreedyPlayer(board_size=5, player_id=-1)

    print("Test board (White to move):")
    for row in board:
        print(" ".join([
            'B' if x == 1 else 'W' if x == -1 else '.'
            for x in row
        ]))
    print()

    # Test greedy move selection
    print("Selecting greedy move...")
    move = player.select_move(board)

    print(f"Selected move: {move} (row={move[0]}, col={move[1]})")

    # Verify move is valid
    assert board[move[0], move[1]] == 0, f"Move {move} should be on empty position"

    print()

    # Apply move and show result
    board[move[0], move[1]] = -1
    print("Board after greedy move:")
    for row in board:
        print(" ".join([
            'B' if x == 1 else 'W' if x == -1 else '.'
            for x in row
        ]))

    print()
    print("✓ Greedy player test passed!")


if __name__ == "__main__":
    test_greedy_player()
