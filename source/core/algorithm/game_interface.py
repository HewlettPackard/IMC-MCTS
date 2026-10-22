# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Abstract game interface for Accelerator applications.

All 13 applications implement this interface so the MCTS engine can play them
without game-specific knowledge.
"""

from abc import ABC, abstractmethod


class GameInterface(ABC):
    """Abstract base class for all Accelerator applications."""

    name = ""
    board_size = 0
    description = ""
    num_players = 2

    @abstractmethod
    def initial_state(self):
        """Return the initial board state as an NxN array. 0=empty."""

    @abstractmethod
    def get_legal_moves(self, board, player):
        """Return the list of legal (row, col) moves for the given player."""

    @abstractmethod
    def apply_move(self, board, move, player):
        """Apply move and return the new board state."""

    @abstractmethod
    def is_terminal(self, board):
        """Return True if the game is over."""

    @abstractmethod
    def get_result(self, board, player):
        """Return result from player's perspective: 1.0=win, 0.5=draw, 0.0=loss."""

    def get_metrics(self, board):
        """Return game-specific metrics from the final board state.

        Override in subclasses to provide rich per-game metrics.
        """
        return {}
