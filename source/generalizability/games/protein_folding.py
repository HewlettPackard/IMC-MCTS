# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""HP Protein Folding - Single-player lattice protein folding optimization.

Place amino acids on a 2D grid to maximize hydrophobic (H-H) contacts.
Uses the HP model: H = hydrophobic (1), P = polar (2).
"""

from typing import List, Tuple
import numpy as np
from core.algorithm.game_interface import GameInterface


class ProteinFolding(GameInterface):
    name = "HP Protein Folding"
    board_size = 13
    description = "HP lattice protein folding on 13x13 grid"
    num_players = 1

    SEQUENCE = "HPHPPHHPHPPHPHHPPHPH"  # 20 residues
    EMPTY = 0
    H = 1  # Hydrophobic
    P = 2  # Polar

    # Known optimal H-H contacts for benchmark sequences (from literature)
    KNOWN_OPTIMAL = {
        "HPHPPHHPHPPHPHHPPHPH": 9,   # Benchmark seq #13, 20 residues
    }

    def __init__(self):
        self._sequence = self.SEQUENCE
        self._max_hh = self.KNOWN_OPTIMAL.get(self._sequence,
                                               self._theoretical_max_hh())

    def _theoretical_max_hh(self) -> int:
        """Estimate an upper bound for H-H contacts (fallback)."""
        hydrophobic_count = self._sequence.count("H")
        # Each H can have at most 4 neighbors, minus sequence-adjacent H pairs
        adjacent_hh_count = sum(
            1 for sequence_idx in range(len(self._sequence) - 1)
            if (self._sequence[sequence_idx] == "H" and
                self._sequence[sequence_idx + 1] == "H")
        )
        return min(2 * hydrophobic_count,
                   4 * hydrophobic_count - adjacent_hh_count) // 2

    def initial_state(self) -> np.ndarray:
        board = np.zeros((self.board_size, self.board_size), dtype=int)
        center = self.board_size // 2
        # Place first amino acid at center
        amino_acid = self.H if self._sequence[0] == "H" else self.P
        board[center, center] = amino_acid
        # Encode placement count in top-left corner using negative value
        # We use a metadata convention: board[-1, -1] stores placed count
        # But since board values must be 0/1/2, track externally.
        # We'll use a simple convention: placed_count is derived by
        # counting non-zero cells.
        return board

    def _placed_count(self, board: np.ndarray) -> int:
        return int(np.count_nonzero(board))

    def _last_placed_position(self, board: np.ndarray) -> Tuple[int, int]:
        """Find the last placed amino acid position.

        We track placement order by scanning for the most recently added piece.
        For simplicity, we store the chain as the sequence of non-zero cells.
        Since we need adjacency, we reconstruct the chain by BFS from center.
        """
        center = self.board_size // 2
        placed = self._placed_count(board)
        if placed == 0:
            return (center, center)

        # BFS/DFS to reconstruct chain order from center
        visited = set()
        chain = []
        stack = [(center, center)]
        while stack:
            position = stack.pop()
            if position in visited:
                continue
            row, col = position
            if (row < 0 or row >= self.board_size or
                    col < 0 or col >= self.board_size):
                continue
            if board[row, col] == 0:
                continue
            visited.add(position)
            chain.append(position)
            for row_step, col_step in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                next_position = (row + row_step, col + col_step)
                if next_position not in visited:
                    stack.append(next_position)

        # The last element in the chain is the endpoint furthest from center
        # For a proper chain, find the endpoint (degree 1 node, not center)
        if len(chain) <= 1:
            return (center, center)

        # Build adjacency for placed cells
        adjacency = {position: [] for position in chain}
        for position in chain:
            row, col = position
            for row_step, col_step in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                neighbor = (row + row_step, col + col_step)
                if neighbor in adjacency:
                    adjacency[position].append(neighbor)

        # Find endpoints (degree 1) that are not the center
        endpoints = [position for position in chain
                     if len(adjacency[position]) == 1]
        for endpoint in endpoints:
            if endpoint != (center, center):
                return endpoint
        # Fallback: return last in chain
        return chain[-1]

    def get_legal_moves(self, board: np.ndarray, player: int) -> List[Tuple[int, int]]:
        placed = self._placed_count(board)
        if placed >= len(self._sequence):
            return []

        last_position = self._last_placed_position(board)
        row, col = last_position
        moves = []
        for row_step, col_step in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            next_row = row + row_step
            next_col = col + col_step
            if (0 <= next_row < self.board_size and
                    0 <= next_col < self.board_size):
                if board[next_row, next_col] == self.EMPTY:
                    moves.append((next_row, next_col))
        return moves

    def apply_move(self, board: np.ndarray, move: Tuple[int, int], player: int) -> np.ndarray:
        new_board = board.copy()
        placed = self._placed_count(board)
        if placed >= len(self._sequence):
            return new_board

        amino_acid_code = self._sequence[placed]
        amino_acid = self.H if amino_acid_code == "H" else self.P
        new_board[move[0], move[1]] = amino_acid
        return new_board

    def is_terminal(self, board: np.ndarray) -> bool:
        placed = self._placed_count(board)
        if placed >= len(self._sequence):
            return True
        if placed > 0 and len(self.get_legal_moves(board, 1)) == 0:
            return True
        return False

    def _count_hh_contacts(self, board: np.ndarray) -> int:
        """Count H-H contacts that are NOT consecutive in the sequence."""
        # Find all H positions
        hydrophobic_positions = list(zip(*np.where(board == self.H)))
        contacts = 0
        hydrophobic_set = set(hydrophobic_positions)

        # Reconstruct chain to know which H's are sequence-adjacent
        center = self.board_size // 2
        chain = self._reconstruct_chain(board, center)
        seq_adjacent = set()
        for chain_idx in range(len(chain) - 1):
            if (board[chain[chain_idx]] == self.H and
                    board[chain[chain_idx + 1]] == self.H):
                seq_adjacent.add((chain[chain_idx], chain[chain_idx + 1]))
                seq_adjacent.add((chain[chain_idx + 1], chain[chain_idx]))

        for row, col in hydrophobic_positions:
            for row_step, col_step in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                neighbor = (row + row_step, col + col_step)
                if (neighbor in hydrophobic_set and
                        ((row, col), neighbor) not in seq_adjacent):
                    contacts += 1
        return contacts // 2  # Each contact counted twice

    def _reconstruct_chain(self, board, center):
        """Reconstruct the placement chain from center outward."""
        start = (center, center)
        if board[start] == 0:
            return []

        visited = set()
        # Build adjacency
        placed_positions = list(zip(*np.where(board > 0)))
        placed_set = set(placed_positions)
        adjacency = {position: [] for position in placed_positions}
        for row, col in placed_positions:
            for row_step, col_step in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                neighbor = (row + row_step, col + col_step)
                if neighbor in placed_set:
                    adjacency[(row, col)].append(neighbor)

        # Walk the chain from start
        chain = [start]
        visited.add(start)
        current = start
        while True:
            found_next = False
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    chain.append(neighbor)
                    visited.add(neighbor)
                    current = neighbor
                    found_next = True
                    break
            if not found_next:
                break
        return chain

    def get_metrics(self, board: np.ndarray) -> dict:
        hh_contacts = self._count_hh_contacts(board)
        return {
            "hh_contacts": hh_contacts,
            "optimality_ratio": hh_contacts / max(1, self._max_hh),
        }

    def get_result(self, board: np.ndarray, player: int) -> float:
        hh_contacts = self._count_hh_contacts(board)
        if self._max_hh == 0:
            return 1.0
        return min(1.0, hh_contacts / max(1, self._max_hh))
