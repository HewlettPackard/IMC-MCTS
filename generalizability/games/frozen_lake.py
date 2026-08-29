# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Frozen Lake - 8x8 single-player grid navigation.

Navigate from (0,0) to goal at (7,7) on a frozen lake, avoiding holes.
States: 0=frozen(safe), 1=hole, 2=goal, 3=agent position (internal).
"""

from typing import List, Tuple
import numpy as np
from core.algorithm.game_interface import GameInterface


class FrozenLake(GameInterface):
    name = "FrozenLake"
    board_size = 8
    description = "8x8 Frozen Lake navigation"
    num_players = 1

    SAFE = 0
    HOLE = 1
    GOAL = 2
    AGENT = 3

    # Directional offsets: up, down, left, right
    DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def __init__(self, seed: int = 42, num_holes: int = 10):
        self._rng = np.random.RandomState(seed)
        self._base_board = self._generate_lake(num_holes)

    def _generate_lake(self, num_holes: int) -> np.ndarray:
        """Generate the lake layout with holes, ensuring a valid path exists."""
        board = np.zeros((self.board_size, self.board_size), dtype=int)
        board[self.board_size - 1, self.board_size - 1] = self.GOAL

        # Place holes randomly, avoiding start and goal
        reserved = {(0, 0), (self.board_size - 1, self.board_size - 1)}
        all_cells = [
            (row, col)
            for row in range(self.board_size)
            for col in range(self.board_size)
            if (row, col) not in reserved
        ]
        self._rng.shuffle(all_cells)

        holes_placed = 0
        for row, col in all_cells:
            if holes_placed >= num_holes:
                break
            board[row, col] = self.HOLE
            # Verify path still exists
            if self._has_path(board):
                holes_placed += 1
            else:
                board[row, col] = self.SAFE  # Revert

        return board

    def _has_path(self, board: np.ndarray) -> bool:
        """BFS to check if a path exists from (0,0) to goal."""
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
                            board[next_row, next_col] != self.HOLE):
                        visited.add(next_cell)
                        queue.append(next_cell)
        return False

    def _find_agent(self, board: np.ndarray) -> Tuple[int, int]:
        """Find agent position on the board."""
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
                moves.append((next_row, next_col))
        return moves

    def apply_move(self, board: np.ndarray, move: Tuple[int, int], player: int) -> np.ndarray:
        new_board = board.copy()
        agent_row, agent_col = self._find_agent(board)

        # Restore the underlying cell where the agent was
        new_board[agent_row, agent_col] = self._base_board[agent_row, agent_col]

        next_row, next_col = move
        # Check what the agent lands on
        underlying = self._base_board[next_row, next_col]
        if underlying == self.HOLE:
            # Agent falls in hole - mark it
            new_board[next_row, next_col] = self.AGENT
        elif underlying == self.GOAL:
            # Agent reaches goal
            new_board[next_row, next_col] = self.AGENT
        else:
            new_board[next_row, next_col] = self.AGENT

        return new_board

    def is_terminal(self, board: np.ndarray) -> bool:
        agent_row, agent_col = self._find_agent(board)
        underlying = self._base_board[agent_row, agent_col]
        return underlying == self.HOLE or underlying == self.GOAL

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
                            self._base_board[next_row, next_col] != self.HOLE):
                        visited.add(next_cell)
                        queue.append((next_cell, distance + 1))
        return -1  # no path

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
        underlying = self._base_board[agent_row, agent_col]
        if underlying == self.GOAL:
            return 1.0
        # Partial credit based on Manhattan distance to goal, scaled to [0, 0.5)
        goal_row, goal_col = self.board_size - 1, self.board_size - 1
        max_distance = goal_row + goal_col  # maximum possible Manhattan distance
        distance = abs(agent_row - goal_row) + abs(agent_col - goal_col)
        return 0.5 * (1.0 - distance / max_distance)
