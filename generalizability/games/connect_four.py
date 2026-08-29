# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Connect Four on an 8x8 board with 6x7 active region."""

from typing import List, Tuple
import numpy as np

from core.algorithm.game_interface import GameInterface


class ConnectFour(GameInterface):
    name = "Connect Four"
    board_size = 8
    description = "Connect Four on 8x8 (6x7 active)"
    num_players = 2

    _ROWS = 6
    _COLS = 7
    _DIRS = [(0, 1), (1, 0), (1, 1), (1, -1)]

    def initial_state(self) -> np.ndarray:
        return np.zeros((self.board_size, self.board_size), dtype=np.int8)

    def get_legal_moves(self, board: np.ndarray, player: int) -> List[Tuple[int, int]]:
        """For each column 0-6, find the bottom-most empty row (gravity)."""
        moves = []
        for col in range(self._COLS):
            for row in range(self._ROWS - 1, -1, -1):
                if board[row, col] == 0:
                    moves.append((row, col))
                    break
        return moves

    def apply_move(self, board: np.ndarray, move: Tuple[int, int], player: int) -> np.ndarray:
        new_board = board.copy()
        new_board[move[0], move[1]] = player
        return new_board

    def _check_four(self, board: np.ndarray, player: int) -> bool:
        """Check if player has 4 in a row within the active region."""
        for row in range(self._ROWS):
            for col in range(self._COLS):
                if board[row, col] != player:
                    continue
                for row_step, col_step in self._DIRS:
                    count = 1
                    for step in range(1, 4):
                        next_row = row + row_step * step
                        next_col = col + col_step * step
                        if (0 <= next_row < self._ROWS and
                                0 <= next_col < self._COLS and
                                board[next_row, next_col] == player):
                            count += 1
                        else:
                            break
                    if count >= 4:
                        return True
        return False

    def is_terminal(self, board: np.ndarray) -> bool:
        if self._check_four(board, 1) or self._check_four(board, 2):
            return True
        # All columns full
        return len(self.get_legal_moves(board, 1)) == 0

    def get_metrics(self, board: np.ndarray) -> dict:
        stone_count = int(np.count_nonzero(board[:self._ROWS, :self._COLS]))
        cell_count = self._ROWS * self._COLS
        return {"move_efficiency": stone_count / cell_count if cell_count else 0.0}

    def get_result(self, board: np.ndarray, player: int) -> float:
        if self._check_four(board, player):
            return 1.0
        if self._check_four(board, 3 - player):
            return 0.0
        return 0.5  # draw
