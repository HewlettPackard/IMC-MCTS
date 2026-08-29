# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""11x11 Hex with Union-Find win detection."""

from typing import List, Tuple
import numpy as np

from core.algorithm.game_interface import GameInterface


class UnionFind:
    """Lightweight disjoint-set structure for Hex connectivity."""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        root_a = self.find(a)
        root_b = self.find(b)
        if root_a == root_b:
            return
        if self.rank[root_a] < self.rank[root_b]:
            root_a, root_b = root_b, root_a
        self.parent[root_b] = root_a
        if self.rank[root_a] == self.rank[root_b]:
            self.rank[root_a] += 1

    def connected(self, a: int, b: int) -> bool:
        return self.find(a) == self.find(b)


class Hex(GameInterface):
    name = "Hex"
    board_size = 11
    description = "11x11 Hex with Union-Find win detection"
    num_players = 2

    # Hex neighbours (6-connectivity on a hex grid stored in a square array)
    _DIRS = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0)]

    def initial_state(self) -> np.ndarray:
        return np.zeros((self.board_size, self.board_size), dtype=np.int8)

    def get_legal_moves(self, board: np.ndarray, player: int) -> List[Tuple[int, int]]:
        return [(row, col) for row in range(self.board_size)
                for col in range(self.board_size) if board[row, col] == 0]

    def apply_move(self, board: np.ndarray, move: Tuple[int, int], player: int) -> np.ndarray:
        new_board = board.copy()
        new_board[move[0], move[1]] = player
        return new_board

    def _check_winner(self, board: np.ndarray, player: int) -> bool:
        """Use Union-Find to check if player has a winning connection."""
        board_size = self.board_size
        # Two virtual nodes: source and sink
        total_nodes = board_size * board_size + 2
        source = board_size * board_size
        sink = board_size * board_size + 1
        connectivity = UnionFind(total_nodes)

        for row in range(board_size):
            for col in range(board_size):
                if board[row, col] != player:
                    continue
                cell_index = row * board_size + col
                # Connect to virtual nodes
                if player == 1:  # top-bottom
                    if row == 0:
                        connectivity.union(cell_index, source)
                    if row == board_size - 1:
                        connectivity.union(cell_index, sink)
                else:  # left-right
                    if col == 0:
                        connectivity.union(cell_index, source)
                    if col == board_size - 1:
                        connectivity.union(cell_index, sink)
                # Connect to neighbours
                for row_step, col_step in self._DIRS:
                    next_row = row + row_step
                    next_col = col + col_step
                    if (0 <= next_row < board_size and
                            0 <= next_col < board_size and
                            board[next_row, next_col] == player):
                        neighbor_index = next_row * board_size + next_col
                        connectivity.union(cell_index, neighbor_index)

        return connectivity.connected(source, sink)

    def is_terminal(self, board: np.ndarray) -> bool:
        if self._check_winner(board, 1) or self._check_winner(board, 2):
            return True
        return int(np.count_nonzero(board)) == self.board_size * self.board_size

    def get_metrics(self, board: np.ndarray) -> dict:
        stone_count = int(np.count_nonzero(board))
        cell_count = self.board_size * self.board_size
        return {"move_efficiency": stone_count / cell_count if cell_count else 0.0}

    def get_result(self, board: np.ndarray, player: int) -> float:
        if self._check_winner(board, player):
            return 1.0
        if self._check_winner(board, 3 - player):
            return 0.0
        # No draws in Hex, but if board is full someone must have won
        return 0.5
