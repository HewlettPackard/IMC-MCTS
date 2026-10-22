# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""19x19 Pente with custodial captures."""

from typing import List, Tuple, Dict
import numpy as np

from core.algorithm.game_interface import GameInterface


class Pente(GameInterface):
    name = "Pente"
    board_size = 19
    description = "19x19 Pente with custodial captures"
    num_players = 2

    _DIRS = [(-1, -1), (-1, 0), (-1, 1),
             (0, -1),          (0, 1),
             (1, -1),  (1, 0), (1, 1)]

    # Track captures per game instance (keyed by board id for isolation)
    # In practice MCTS creates copies, so we store captures in extra board rows.
    # Row board_size+0: captures for player 1 (stored in col 0)
    # Row board_size+1: captures for player 2 (stored in col 0)

    def initial_state(self) -> np.ndarray:
        # Extra 2 rows for capture counts
        board = np.zeros((self.board_size + 2, self.board_size), dtype=np.int8)
        return board

    def get_legal_moves(self, board: np.ndarray, player: int) -> List[Tuple[int, int]]:
        return [(row, col) for row in range(self.board_size)
                for col in range(self.board_size) if board[row, col] == 0]

    def apply_move(self, board: np.ndarray, move: Tuple[int, int], player: int) -> np.ndarray:
        new_board = board.copy()
        row, col = move
        new_board[row, col] = player
        opponent = 3 - player
        board_size = self.board_size

        # Custodial captures: pattern [player, opponent, opponent, player]
        captured_pairs = 0
        for row_step, col_step in self._DIRS:
            row_1, col_1 = row + row_step, col + col_step
            row_2, col_2 = row + 2 * row_step, col + 2 * col_step
            row_3, col_3 = row + 3 * row_step, col + 3 * col_step
            if (0 <= row_3 < board_size and 0 <= col_3 < board_size and
                    new_board[row_1, col_1] == opponent and
                    new_board[row_2, col_2] == opponent and
                    new_board[row_3, col_3] == player):
                new_board[row_1, col_1] = 0
                new_board[row_2, col_2] = 0
                captured_pairs += 1

        # Update capture count (stored in metadata rows)
        capture_row = self.board_size + (player - 1)
        new_board[capture_row, 0] += captured_pairs
        return new_board

    def _check_five(self, board: np.ndarray, player: int) -> bool:
        """Check if player has 5 or more in a row."""
        board_size = self.board_size
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for row in range(board_size):
            for col in range(board_size):
                if board[row, col] != player:
                    continue
                for row_step, col_step in directions:
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

    def _captures(self, board: np.ndarray, player: int) -> int:
        """Get number of pairs captured by player."""
        return int(board[self.board_size + (player - 1), 0])

    def _player_wins(self, board: np.ndarray, player: int) -> bool:
        return self._check_five(board, player) or self._captures(board, player) >= 5

    def is_terminal(self, board: np.ndarray) -> bool:
        if self._player_wins(board, 1) or self._player_wins(board, 2):
            return True
        # Board full
        play_board = board[:self.board_size]
        return (int(np.count_nonzero(play_board)) ==
                self.board_size * self.board_size)

    def get_metrics(self, board: np.ndarray) -> dict:
        return {
            "capture_pairs_p1": self._captures(board, 1),
            "capture_pairs_p2": self._captures(board, 2),
        }

    def get_result(self, board: np.ndarray, player: int) -> float:
        if self._player_wins(board, player):
            return 1.0
        if self._player_wins(board, 3 - player):
            return 0.0
        return 0.5
