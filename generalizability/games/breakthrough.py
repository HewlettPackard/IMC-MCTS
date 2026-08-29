# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Breakthrough - 8x8 two-player board game.

Player 1 starts in rows 0-1 and advances downward.
Player 2 starts in rows 6-7 and advances upward.
Win by reaching the opponent's home row or capturing all their pieces.
"""

from typing import List, Tuple
import numpy as np
from core.algorithm.game_interface import GameInterface


class Breakthrough(GameInterface):
    name = "Breakthrough"
    board_size = 8
    description = "8x8 Breakthrough"
    num_players = 2

    def initial_state(self) -> np.ndarray:
        board = np.zeros((self.board_size, self.board_size), dtype=int)
        board[0:2, :] = 1  # Player 1 in rows 0-1
        board[6:8, :] = 2  # Player 2 in rows 6-7
        return board

    def get_legal_moves(self, board: np.ndarray, player: int) -> List[Tuple[int, int]]:
        """Return moves as (source_index, dest_index) where index = r * board_size + c."""
        moves = []
        direction = 1 if player == 1 else -1
        opponent = 2 if player == 1 else 1
        board_size = self.board_size

        positions = list(zip(*np.where(board == player)))
        for row, col in positions:
            next_row = row + direction
            if next_row < 0 or next_row >= board_size:
                continue
            source_index = row * board_size + col
            # Move straight ahead (only if empty)
            if board[next_row, col] == 0:
                moves.append((source_index, next_row * board_size + col))
            # Diagonal captures and moves
            for col_step in [-1, 1]:
                next_col = col + col_step
                if 0 <= next_col < board_size:
                    if (board[next_row, next_col] == 0 or
                            board[next_row, next_col] == opponent):
                        moves.append((source_index,
                                      next_row * board_size + next_col))
        return moves

    def apply_move(self, board: np.ndarray, move: Tuple[int, int], player: int) -> np.ndarray:
        new_board = board.copy()
        source_index, destination_index = move
        board_size = self.board_size
        source_row, source_col = divmod(source_index, board_size)
        next_row, next_col = divmod(destination_index, board_size)
        new_board[source_row, source_col] = 0
        new_board[next_row, next_col] = player
        return new_board

    def is_terminal(self, board: np.ndarray) -> bool:
        # Player 1 wins by reaching row 7
        if np.any(board[7, :] == 1):
            return True
        # Player 2 wins by reaching row 0
        if np.any(board[0, :] == 2):
            return True
        # A player with no pieces loses
        if not np.any(board == 1) or not np.any(board == 2):
            return True
        return False

    def get_metrics(self, board: np.ndarray) -> dict:
        p1_pieces = int(np.sum(board == 1))
        p2_pieces = int(np.sum(board == 2))
        return {
            "pieces_remaining_p1": p1_pieces,
            "pieces_remaining_p2": p2_pieces,
        }

    def get_result(self, board: np.ndarray, player: int) -> float:
        opponent = 2 if player == 1 else 1
        home_row_opp = 7 if player == 1 else 0
        home_row_self = 0 if player == 1 else 7

        # Check if player reached opponent's home row
        if np.any(board[home_row_opp, :] == player):
            return 1.0
        # Check if opponent reached player's home row
        if np.any(board[home_row_self, :] == opponent):
            return 0.0
        # Check piece elimination
        if not np.any(board == opponent):
            return 1.0
        if not np.any(board == player):
            return 0.0
        return 0.5
