# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""MiniGrid - 8x8 single-player navigation with walls.

Navigate from (0,0) to goal avoiding walls.
States: 0=empty, 1=wall, 2=goal, 3=agent (internal tracking).

All game state is derived from the board array (no mutable instance state)
so MCTS rollouts work correctly with board copies.
"""

from typing import List, Tuple
import numpy as np
from core.algorithm.game_interface import GameInterface


class MiniGrid(GameInterface):
    name = "MiniGrid"
    board_size = 8
    description = "8x8 MiniGrid navigation with walls"
    num_players = 1

    EMPTY = 0
    WALL = 1
    GOAL = 2
    AGENT = 3

    DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def __init__(self, seed: int = 42, wall_fraction: float = 0.25):
        self._rng = np.random.RandomState(seed)
        self._base_board = self._generate_grid(wall_fraction)

    def _generate_grid(self, wall_fraction: float) -> np.ndarray:
        """Generate grid with walls, guaranteeing a path from start to goal."""
        board = np.zeros((self.board_size, self.board_size), dtype=int)
        goal_row, goal_col = self.board_size - 1, self.board_size - 1
        board[goal_row, goal_col] = self.GOAL

        reserved = {(0, 0), (goal_row, goal_col)}
        num_walls = int(wall_fraction * self.board_size * self.board_size)

        all_cells = [
            (row, col)
            for row in range(self.board_size)
            for col in range(self.board_size)
            if (row, col) not in reserved
        ]
        self._rng.shuffle(all_cells)

        walls_placed = 0
        for row, col in all_cells:
            if walls_placed >= num_walls:
                break
            board[row, col] = self.WALL
            if self._has_path(board):
                walls_placed += 1
            else:
                board[row, col] = self.EMPTY  # Revert to maintain connectivity

        return board

    def _has_path(self, board: np.ndarray) -> bool:
        """BFS check for path from (0,0) to goal."""
        start = (0, 0)
        goal = (self.board_size - 1, self.board_size - 1)
        visited = {start}
        queue = [start]
        while queue:
            row, col = queue.pop(0)
            if (row, col) == goal:
                return True
            for row_step, col_step in self.DIRECTIONS:
                next_row = row + row_step
                next_col = col + col_step
                next_cell = (next_row, next_col)
                if (0 <= next_row < self.board_size and
                        0 <= next_col < self.board_size):
                    if (next_cell not in visited and
                            board[next_row, next_col] != self.WALL):
                        visited.add(next_cell)
                        queue.append(next_cell)
        return False

    def _find_agent(self, board: np.ndarray) -> Tuple[int, int]:
        positions = list(zip(*np.where(board == self.AGENT)))
        if positions:
            return positions[0]
        return (0, 0)

    def initial_state(self) -> np.ndarray:
        board = self._base_board.copy()
        board[0, 0] = self.AGENT
        return board

    def get_legal_moves(self, board: np.ndarray, player: int) -> List[Tuple[int, int]]:
        agent_row, agent_col = self._find_agent(board)
        moves = []
        for row_step, col_step in self.DIRECTIONS:
            next_row = agent_row + row_step
            next_col = agent_col + col_step
            if (0 <= next_row < self.board_size and
                    0 <= next_col < self.board_size):
                if self._base_board[next_row, next_col] != self.WALL:
                    moves.append((next_row, next_col))
        return moves

    def apply_move(self, board: np.ndarray, move: Tuple[int, int], player: int) -> np.ndarray:
        new_board = board.copy()
        agent_row, agent_col = self._find_agent(board)

        # Restore underlying cell where agent was
        new_board[agent_row, agent_col] = self._base_board[agent_row, agent_col]

        next_row, next_col = move
        new_board[next_row, next_col] = self.AGENT

        return new_board

    def is_terminal(self, board: np.ndarray) -> bool:
        agent_row, agent_col = self._find_agent(board)
        if self._base_board[agent_row, agent_col] == self.GOAL:
            return True
        if not self.get_legal_moves(board, 1):
            return True
        return False

    def _bfs_shortest_path(self) -> int:
        """BFS shortest path length from (0,0) to goal on the base board."""
        start = (0, 0)
        goal = (self.board_size - 1, self.board_size - 1)
        visited = {start}
        queue = [(start, 0)]
        while queue:
            (row, col), distance = queue.pop(0)
            if (row, col) == goal:
                return distance
            for row_step, col_step in self.DIRECTIONS:
                next_row = row + row_step
                next_col = col + col_step
                next_cell = (next_row, next_col)
                if (0 <= next_row < self.board_size and
                        0 <= next_col < self.board_size):
                    if (next_cell not in visited and
                            self._base_board[next_row, next_col] != self.WALL):
                        visited.add(next_cell)
                        queue.append((next_cell, distance + 1))
        return -1

    def get_metrics(self, board: np.ndarray) -> dict:
        agent_row, agent_col = self._find_agent(board)
        reached_goal = self._base_board[agent_row, agent_col] == self.GOAL
        optimal_path_length = self._bfs_shortest_path()
        return {
            "reached_goal": reached_goal,
            "optimal_path_length": optimal_path_length,
        }

    def get_result(self, board: np.ndarray, player: int) -> float:
        agent_row, agent_col = self._find_agent(board)
        if self._base_board[agent_row, agent_col] == self.GOAL:
            return 1.0
        # Partial credit based on Manhattan distance to goal, scaled to [0, 0.5)
        goal_row, goal_col = self.board_size - 1, self.board_size - 1
        max_distance = goal_row + goal_col
        distance = abs(agent_row - goal_row) + abs(agent_col - goal_col)
        return 0.5 * (1.0 - distance / max_distance)
