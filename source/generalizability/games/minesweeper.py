# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Minesweeper - 9x9 single-player mine avoidance game.

Reveal cells to uncover the board without hitting a mine.
States: 0=hidden, 1=revealed safe, 2=mine (hidden until triggered).
"""

from typing import List, Tuple
import numpy as np
from core.algorithm.game_interface import GameInterface


class Minesweeper(GameInterface):
    name = "Minesweeper"
    board_size = 9
    description = "9x9 Minesweeper"
    num_players = 1

    HIDDEN = 0
    REVEALED = 1
    MINE_MARKER = 2  # Used internally on the board when a mine is revealed

    def __init__(self, seed: int = 42, num_mines: int = 10):
        self._rng = np.random.RandomState(seed)
        self._num_mines = num_mines
        self._mine_locations = self._place_mines()
        self._total_safe = self.board_size * self.board_size - num_mines

    def _place_mines(self) -> set:
        """Randomly place mines, excluding corners and their neighbors."""
        # Reserve corners and adjacent cells so the game is playable
        reserved = set()
        for corner_row, corner_col in [
                (0, 0), (0, self.board_size - 1),
                (self.board_size - 1, 0),
                (self.board_size - 1, self.board_size - 1)]:
            for row_step in [-1, 0, 1]:
                for col_step in [-1, 0, 1]:
                    next_row = corner_row + row_step
                    next_col = corner_col + col_step
                    if (0 <= next_row < self.board_size and
                            0 <= next_col < self.board_size):
                        reserved.add((next_row, next_col))
        all_cells = [
            (row, col)
            for row in range(self.board_size)
            for col in range(self.board_size)
            if (row, col) not in reserved
        ]
        self._rng.shuffle(all_cells)
        return set(all_cells[:self._num_mines])

    def _count_adjacent_mines(self, r: int, c: int) -> int:
        """Count mines in the 8 cells surrounding (r, c)."""
        mine_count = 0
        for row_step in [-1, 0, 1]:
            for col_step in [-1, 0, 1]:
                if row_step == 0 and col_step == 0:
                    continue
                next_cell = (r + row_step, c + col_step)
                if next_cell in self._mine_locations:
                    mine_count += 1
        return mine_count

    def initial_state(self) -> np.ndarray:
        """All cells start hidden (0)."""
        return np.zeros((self.board_size, self.board_size), dtype=int)

    def _find_provable_mines(self, board: np.ndarray) -> set:
        """Identify hidden cells that are provably mines via neighbor constraints.

        For each revealed cell, count its adjacent mines and adjacent hidden cells.
        If adjacent_mines == number of adjacent hidden cells, all those hidden cells
        must be mines.
        """
        provable_mines = set()
        for row in range(self.board_size):
            for col in range(self.board_size):
                if board[row, col] != self.REVEALED:
                    continue
                adjacent_mines = self._count_adjacent_mines(row, col)
                if adjacent_mines == 0:
                    continue
                hidden_neighbors = []
                for row_step in [-1, 0, 1]:
                    for col_step in [-1, 0, 1]:
                        if row_step == 0 and col_step == 0:
                            continue
                        next_row = row + row_step
                        next_col = col + col_step
                        if (0 <= next_row < self.board_size and
                                0 <= next_col < self.board_size):
                            if board[next_row, next_col] == self.HIDDEN:
                                hidden_neighbors.append((next_row, next_col))
                if len(hidden_neighbors) == adjacent_mines:
                    provable_mines.update(hidden_neighbors)
        return provable_mines

    def get_legal_moves(self, board: np.ndarray, player: int) -> List[Tuple[int, int]]:
        """Hidden cells minus provably-mined cells."""
        if np.any(board == self.MINE_MARKER):
            return []
        hidden_cells = [
            (row, col) for row, col in zip(*np.where(board == self.HIDDEN))
        ]
        provable_mines = self._find_provable_mines(board)
        safe_candidates = [
            cell for cell in hidden_cells if cell not in provable_mines
        ]
        # If all hidden cells are provable mines, return them anyway (game must end)
        return safe_candidates if safe_candidates else hidden_cells

    def apply_move(self, board: np.ndarray, move: Tuple[int, int], player: int) -> np.ndarray:
        new_board = board.copy()
        row, col = move

        if (row, col) in self._mine_locations:
            new_board[row, col] = self.MINE_MARKER
        else:
            # Reveal the cell
            new_board[row, col] = self.REVEALED
            # Auto-reveal neighbors if no adjacent mines (flood fill)
            if self._count_adjacent_mines(row, col) == 0:
                self._flood_reveal(new_board, row, col)

        return new_board

    def _flood_reveal(self, board: np.ndarray, start_r: int, start_c: int) -> None:
        """Flood-fill reveal cells with 0 adjacent mines."""
        queue = [(start_r, start_c)]
        while queue:
            row, col = queue.pop(0)
            for row_step in [-1, 0, 1]:
                for col_step in [-1, 0, 1]:
                    if row_step == 0 and col_step == 0:
                        continue
                    next_row = row + row_step
                    next_col = col + col_step
                    next_cell = (next_row, next_col)
                    if (0 <= next_row < self.board_size and
                            0 <= next_col < self.board_size):
                        if (board[next_row, next_col] == self.HIDDEN and
                                next_cell not in self._mine_locations):
                            board[next_row, next_col] = self.REVEALED
                            if self._count_adjacent_mines(next_row, next_col) == 0:
                                queue.append(next_cell)

    def _revealed_safe_count(self, board: np.ndarray) -> int:
        """Count how many safe cells have been revealed."""
        return int(np.sum(board == self.REVEALED))

    def is_terminal(self, board: np.ndarray) -> bool:
        # Hit a mine
        if np.any(board == self.MINE_MARKER):
            return True
        # All safe cells revealed
        if self._revealed_safe_count(board) >= self._total_safe:
            return True
        return False

    def get_metrics(self, board: np.ndarray) -> dict:
        revealed_count = self._revealed_safe_count(board)
        return {"cells_revealed_pct": revealed_count / self._total_safe}

    def get_result(self, board: np.ndarray, player: int) -> float:
        if np.any(board == self.MINE_MARKER):
            return 0.0
        if self._revealed_safe_count(board) >= self._total_safe:
            return 1.0
        # Partial progress (for non-terminal evaluation)
        return self._revealed_safe_count(board) / self._total_safe
