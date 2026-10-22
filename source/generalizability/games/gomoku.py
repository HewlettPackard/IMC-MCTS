# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""15x15 Gomoku (five-in-a-row)."""

from typing import List, Tuple
import numpy as np

from core.algorithm.game_interface import GameInterface


class Gomoku(GameInterface):
    name = "Gomoku"
    board_size = 15
    description = "15x15 Gomoku (five-in-a-row)"
    num_players = 2

    _DIRS = [(0, 1), (1, 0), (1, 1), (1, -1)]  # horizontal, vertical, 2 diagonals

    def initial_state(self) -> np.ndarray:
        return np.zeros((self.board_size, self.board_size), dtype=np.int8)

    def get_legal_moves(self, board: np.ndarray, player: int) -> List[Tuple[int, int]]:
        return [(row, col) for row in range(self.board_size)
                for col in range(self.board_size) if board[row, col] == 0]

    def apply_move(self, board: np.ndarray, move: Tuple[int, int], player: int) -> np.ndarray:
        new_board = board.copy()
        new_board[move[0], move[1]] = player
        return new_board

    def _check_five(self, board: np.ndarray, player: int) -> bool:
        """Check if player has 5 in a row in any direction."""
        board_size = self.board_size
        for row in range(board_size):
            for col in range(board_size):
                if board[row, col] != player:
                    continue
                for row_step, col_step in self._DIRS:
                    count = 1
                    for step in range(1, 5):
                        next_row = row + row_step * step
                        next_col = col + col_step * step
                        if (0 <= next_row < board_size and
                                0 <= next_col < board_size and
                                board[next_row, next_col] == player):
                            count += 1
                        else:
                            break
                    if count >= 5:
                        return True
        return False

    def is_terminal(self, board: np.ndarray) -> bool:
        if self._check_five(board, 1) or self._check_five(board, 2):
            return True
        return int(np.count_nonzero(board)) == self.board_size * self.board_size

    def get_metrics(self, board: np.ndarray) -> dict:
        stone_count = int(np.count_nonzero(board))
        cell_count = self.board_size * self.board_size
        return {"move_efficiency": stone_count / cell_count if cell_count else 0.0}

    def get_result(self, board: np.ndarray, player: int) -> float:
        if self._check_five(board, player):
            return 1.0
        if self._check_five(board, 3 - player):
            return 0.0
        return 0.5  # draw (board full, no five)
