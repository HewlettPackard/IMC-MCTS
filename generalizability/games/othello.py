# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""8x8 Othello / Reversi."""

from typing import List, Tuple
import numpy as np

from core.algorithm.game_interface import GameInterface


class Othello(GameInterface):
    name = "Othello"
    board_size = 8
    description = "8x8 Othello/Reversi"
    num_players = 2

    _DIRS = [(-1, -1), (-1, 0), (-1, 1),
             (0, -1),          (0, 1),
             (1, -1),  (1, 0), (1, 1)]

    def initial_state(self) -> np.ndarray:
        board = np.zeros((self.board_size, self.board_size), dtype=np.int8)
        center = self.board_size // 2
        board[center - 1, center - 1] = 2  # white
        board[center - 1, center] = 1      # black
        board[center, center - 1] = 1      # black
        board[center, center] = 2          # white
        return board

    def _get_flips(self, board: np.ndarray, r: int, c: int, player: int) -> List[Tuple[int, int]]:
        """Return list of cells that would be flipped by player placing at (r, c)."""
        if board[r, c] != 0:
            return []
        opponent = 3 - player
        all_flips: List[Tuple[int, int]] = []
        board_size = self.board_size
        for row_step, col_step in self._DIRS:
            direction_flips = []
            next_row = r + row_step
            next_col = c + col_step
            while (0 <= next_row < board_size and
                   0 <= next_col < board_size and
                   board[next_row, next_col] == opponent):
                direction_flips.append((next_row, next_col))
                next_row += row_step
                next_col += col_step
            if (direction_flips and
                    0 <= next_row < board_size and
                    0 <= next_col < board_size and
                    board[next_row, next_col] == player):
                all_flips.extend(direction_flips)
        return all_flips

    def _has_valid_move(self, board: np.ndarray, player: int) -> bool:
        board_size = self.board_size
        for row in range(board_size):
            for col in range(board_size):
                if (board[row, col] == 0 and
                        self._get_flips(board, row, col, player)):
                    return True
        return False

    def get_legal_moves(self, board: np.ndarray, player: int) -> List[Tuple[int, int]]:
        """Return valid Othello moves (cells that flip at least one opponent stone).

        If no flipping moves exist, return empty list (player must pass).
        """
        moves = []
        board_size = self.board_size
        for row in range(board_size):
            for col in range(board_size):
                if (board[row, col] == 0 and
                        self._get_flips(board, row, col, player)):
                    moves.append((row, col))
        return moves

    def apply_move(self, board: np.ndarray, move: Tuple[int, int], player: int) -> np.ndarray:
        new_board = board.copy()
        row, col = move
        flipped_cells = self._get_flips(board, row, col, player)
        new_board[row, col] = player
        for flip_row, flip_col in flipped_cells:
            new_board[flip_row, flip_col] = player
        return new_board

    def is_terminal(self, board: np.ndarray) -> bool:
        if int(np.count_nonzero(board)) == self.board_size * self.board_size:
            return True
        return not self._has_valid_move(board, 1) and not self._has_valid_move(board, 2)

    def get_metrics(self, board: np.ndarray) -> dict:
        p1_count = int(np.sum(board == 1))
        p2_count = int(np.sum(board == 2))
        return {"piece_differential": p1_count - p2_count}

    def get_result(self, board: np.ndarray, player: int) -> float:
        player_count = int(np.sum(board == player))
        opponent_count = int(np.sum(board == (3 - player)))
        if player_count > opponent_count:
            return 1.0
        elif player_count < opponent_count:
            return 0.0
        return 0.5
