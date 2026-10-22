# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Nonograms - 9x9 single-player logic puzzle.

Fill cells to match a hidden target pattern using row/column clues.
States: 0=unknown, 1=filled, 2=marked empty.
"""

from typing import List, Tuple
import numpy as np
from core.algorithm.game_interface import GameInterface


class Nonograms(GameInterface):
    name = "Nonograms"
    board_size = 9
    description = "9x9 Nonogram puzzle"
    num_players = 1

    def __init__(self, seed: int = 42):
        self._rng = np.random.RandomState(seed)
        self._target = self._generate_target()
        self._row_clues = [
            self._compute_clues(self._target[row, :])
            for row in range(self.board_size)
        ]
        self._col_clues = [
            self._compute_clues(self._target[:, col])
            for col in range(self.board_size)
        ]

    def _generate_target(self) -> np.ndarray:
        """Generate a random binary target solution."""
        # Roughly 50% filled
        return (self._rng.rand(self.board_size, self.board_size) > 0.5).astype(int)

    @staticmethod
    def _compute_clues(line: np.ndarray) -> List[int]:
        """Compute nonogram clues (run lengths of filled cells) for a row/column."""
        clues = []
        run_length = 0
        for cell_value in line:
            if cell_value == 1:
                run_length += 1
            else:
                if run_length > 0:
                    clues.append(run_length)
                run_length = 0
        if run_length > 0:
            clues.append(run_length)
        return clues if clues else [0]

    @property
    def row_clues(self) -> List[List[int]]:
        return self._row_clues

    @property
    def col_clues(self) -> List[List[int]]:
        return self._col_clues

    def initial_state(self) -> np.ndarray:
        return np.zeros((self.board_size, self.board_size), dtype=int)

    def get_legal_moves(self, board: np.ndarray, player: int) -> List[Tuple[int, int]]:
        """Return (r, c) for fill and (r + board_size, c) for mark-empty, for each unknown cell."""
        moves = []
        positions = list(zip(*np.where(board == 0)))
        for row, col in positions:
            moves.append((row, col))                         # fill action
            moves.append((row + self.board_size, col))       # mark-empty action
        return moves

    def apply_move(self, board: np.ndarray, move: Tuple[int, int], player: int) -> np.ndarray:
        new_board = board.copy()
        row, col = move
        if row >= self.board_size:
            # Mark-empty action
            new_board[row - self.board_size, col] = 2
        else:
            # Fill action
            new_board[row, col] = 1
        return new_board

    def is_terminal(self, board: np.ndarray) -> bool:
        # Terminal when no unknown cells remain
        return not np.any(board == 0)

    def get_metrics(self, board: np.ndarray) -> dict:
        total_cells = self.board_size * self.board_size
        correct_cells = 0
        for row in range(self.board_size):
            for col in range(self.board_size):
                cell_value = board[row, col]
                target_value = self._target[row, col]
                if ((cell_value == 1 and target_value == 1) or
                        (cell_value == 2 and target_value == 0)):
                    correct_cells += 1
        return {"accuracy": correct_cells / total_cells}

    def _line_score(self, line: np.ndarray, clues: List[int]) -> float:
        """Score a completed line against its clues. 1.0 if clues match, 0.0 otherwise."""
        # Only score completed lines (no unknown cells)
        if np.any(line == 0):
            return -1.0  # not yet scoreable
        # Compute clues for the current line state (treat 2=empty as 0)
        binary_line = (line == 1).astype(int)
        actual_clues = self._compute_clues(binary_line)
        return 1.0 if actual_clues == clues else 0.0

    def get_result(self, board: np.ndarray, player: int) -> float:
        """Combined score: cell accuracy + line-by-line clue matching.

        Line scoring gives incremental feedback before the board is fully filled.
        """
        total_cells = self.board_size * self.board_size
        correct_cells = 0
        for row in range(self.board_size):
            for col in range(self.board_size):
                cell_value = board[row, col]
                target_value = self._target[row, col]
                if cell_value == 1 and target_value == 1:
                    correct_cells += 1
                elif cell_value == 2 and target_value == 0:
                    correct_cells += 1
        cell_score = correct_cells / total_cells

        # Line scoring: fraction of completed lines that match their clues
        lines_scored = 0
        lines_correct = 0
        for row in range(self.board_size):
            score = self._line_score(board[row, :], self._row_clues[row])
            if score >= 0:
                lines_scored += 1
                lines_correct += score
        for col in range(self.board_size):
            score = self._line_score(board[:, col], self._col_clues[col])
            if score >= 0:
                lines_scored += 1
                lines_correct += score

        if lines_scored > 0:
            line_score = lines_correct / lines_scored
            return 0.5 * cell_score + 0.5 * line_score
        return cell_score
