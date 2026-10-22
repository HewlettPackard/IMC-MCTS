# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Havannah on a 15x15 rectangular grid with hex-shaped valid region (base 8)."""

from typing import List, Tuple, Set
import numpy as np

from core.algorithm.game_interface import GameInterface


class Havannah(GameInterface):
    name = "Havannah"
    board_size = 15
    description = "Havannah on 15x15 rectangular grid"
    num_players = 2

    _BASE = 8  # hexagonal side length
    # 6-connectivity on offset hex grid
    _DIRS = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0)]

    def __init__(self):
        board_size = self.board_size
        base = self._BASE
        # Build validity mask for a hexagon with side `base` centred in 15x15
        self._valid = np.zeros((board_size, board_size), dtype=bool)
        center = board_size // 2
        for row in range(board_size):
            for col in range(board_size):
                # Axial distance from centre in offset coordinates
                row_offset = row - center
                col_offset = col - center
                # Convert to cube coordinates for hex distance
                x = col_offset - (row_offset - (row_offset & 1)) // 2
                z = row_offset
                y = -x - z
                if max(abs(x), abs(y), abs(z)) < base:
                    self._valid[row, col] = True

        # Precompute corners and edges
        valid_cells = list(zip(*np.where(self._valid)))
        # Corners: valid cells with exactly 2 valid hex-neighbours
        # Edges: valid cells on the boundary with exactly 3 valid hex-neighbours (non-corner)
        self._corners: Set[Tuple[int, int]] = set()
        self._edge_id: dict = {}  # cell -> edge_index (0-5)
        boundary = []
        for row, col in valid_cells:
            neighbor_count = 0
            for row_step, col_step in self._DIRS:
                next_row = row + row_step
                next_col = col + col_step
                if (0 <= next_row < board_size and
                        0 <= next_col < board_size and
                        self._valid[next_row, next_col]):
                    neighbor_count += 1
            if neighbor_count <= 3:
                boundary.append((row, col, neighbor_count))

        # Corners have exactly 2 valid neighbours
        for row, col, neighbor_count in boundary:
            if neighbor_count == 2:
                self._corners.add((row, col))

        # Label edges via BFS from corners along boundary (non-corner boundary cells)
        non_corner_boundary = {
            (row, col) for row, col, neighbor_count in boundary
            if neighbor_count == 3
        }
        edge_index = 0
        assigned: Set[Tuple[int, int]] = set()
        for corner_row, corner_col in sorted(self._corners):
            # Walk boundary from this corner in each direction
            for row_step, col_step in self._DIRS:
                next_row = corner_row + row_step
                next_col = corner_col + col_step
                next_cell = (next_row, next_col)
                if next_cell in non_corner_boundary and next_cell not in assigned:
                    # BFS along edge
                    stack = [next_cell]
                    while stack:
                        edge_row, edge_col = stack.pop()
                        edge_cell = (edge_row, edge_col)
                        if edge_cell in assigned:
                            continue
                        assigned.add(edge_cell)
                        self._edge_id[edge_cell] = edge_index
                        for next_row_step, next_col_step in self._DIRS:
                            neighbor_row = edge_row + next_row_step
                            neighbor_col = edge_col + next_col_step
                            neighbor_cell = (neighbor_row, neighbor_col)
                            if (neighbor_cell in non_corner_boundary and
                                    neighbor_cell not in assigned):
                                stack.append(neighbor_cell)
                    edge_index += 1

    def initial_state(self) -> np.ndarray:
        return np.zeros((self.board_size, self.board_size), dtype=np.int8)

    def get_legal_moves(self, board: np.ndarray, player: int) -> List[Tuple[int, int]]:
        return [(row, col) for row in range(self.board_size)
                for col in range(self.board_size)
                if self._valid[row, col] and board[row, col] == 0]

    def apply_move(self, board: np.ndarray, move: Tuple[int, int], player: int) -> np.ndarray:
        new_board = board.copy()
        new_board[move[0], move[1]] = player
        return new_board

    def _connected_component(self, board: np.ndarray, start: Tuple[int, int], player: int) -> Set[Tuple[int, int]]:
        visited: Set[Tuple[int, int]] = set()
        stack = [start]
        board_size = self.board_size
        while stack:
            row, col = stack.pop()
            cell = (row, col)
            if cell in visited:
                continue
            visited.add(cell)
            for row_step, col_step in self._DIRS:
                next_row = row + row_step
                next_col = col + col_step
                next_cell = (next_row, next_col)
                if (0 <= next_row < board_size and
                        0 <= next_col < board_size and
                        board[next_row, next_col] == player and
                        next_cell not in visited):
                    stack.append(next_cell)
        return visited

    def _has_bridge(self, board: np.ndarray, player: int) -> bool:
        """Bridge: a connected group touching at least 2 distinct corners."""
        visited_global: Set[Tuple[int, int]] = set()
        board_size = self.board_size
        for row in range(board_size):
            for col in range(board_size):
                cell = (row, col)
                if board[row, col] == player and cell not in visited_global:
                    component = self._connected_component(board, cell, player)
                    visited_global |= component
                    corners_touched = component & self._corners
                    if len(corners_touched) >= 2:
                        return True
        return False

    def _has_fork(self, board: np.ndarray, player: int) -> bool:
        """Fork: a connected group touching at least 3 distinct edges."""
        visited_global: Set[Tuple[int, int]] = set()
        board_size = self.board_size
        for row in range(board_size):
            for col in range(board_size):
                cell = (row, col)
                if board[row, col] == player and cell not in visited_global:
                    component = self._connected_component(board, cell, player)
                    visited_global |= component
                    edges_touched = set()
                    for component_cell in component:
                        if component_cell in self._edge_id:
                            edges_touched.add(self._edge_id[component_cell])
                    if len(edges_touched) >= 3:
                        return True
        return False

    def _has_ring(self, board: np.ndarray, player: int) -> bool:
        """Ring: a cycle enclosing at least one cell (simplified detection).

        We detect a ring if a connected group of player stones contains a
        cycle, i.e., has more edges than vertices - 1 (not a tree).
        """
        visited_global: Set[Tuple[int, int]] = set()
        board_size = self.board_size
        for row in range(board_size):
            for col in range(board_size):
                cell = (row, col)
                if board[row, col] == player and cell not in visited_global:
                    component = self._connected_component(board, cell, player)
                    visited_global |= component
                    # Count edges in the component
                    edge_count = 0
                    for component_row, component_col in component:
                        for row_step, col_step in self._DIRS:
                            next_cell = (component_row + row_step,
                                         component_col + col_step)
                            if next_cell in component:
                                edge_count += 1
                    edge_count //= 2  # each edge counted twice
                    if edge_count >= len(component):
                        # More edges than a spanning tree -> cycle exists
                        return True
        return False

    def _player_wins(self, board: np.ndarray, player: int) -> bool:
        return (self._has_bridge(board, player) or
                self._has_fork(board, player) or
                self._has_ring(board, player))

    def is_terminal(self, board: np.ndarray) -> bool:
        if self._player_wins(board, 1) or self._player_wins(board, 2):
            return True
        # All valid cells filled
        return all(board[r, c] != 0
                   for r in range(self.board_size)
                   for c in range(self.board_size)
                   if self._valid[r, c])

    def _get_win_type(self, board: np.ndarray, player: int) -> str:
        """Return the winning condition type for player, or 'none'."""
        if self._has_bridge(board, player):
            return "bridge"
        if self._has_fork(board, player):
            return "fork"
        if self._has_ring(board, player):
            return "ring"
        return "none"

    def get_metrics(self, board: np.ndarray) -> dict:
        p1_win_type = self._get_win_type(board, 1)
        p2_win_type = self._get_win_type(board, 2)
        win_type = p1_win_type if p1_win_type != "none" else p2_win_type
        return {"win_type": win_type}

    def get_result(self, board: np.ndarray, player: int) -> float:
        if self._player_wins(board, player):
            return 1.0
        if self._player_wins(board, 3 - player):
            return 0.0
        return 0.5
