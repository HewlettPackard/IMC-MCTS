# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Standalone 9x9 Go Engine with full rules.

Features: captures, ko detection (Zobrist hashing), suicide prevention,
Chinese area scoring with 6.5 komi, pass handling.

Board representation: flat numpy array (board_size, board_size)
  1 = Black, -1 = White, 0 = Empty
"""

import numpy as np
import ctypes
import os
from typing import List, Tuple, Set

# Load the optional C implementation for 9x9 board operations.
_go_fast = None
try:
    _lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'go_fast.so')
    _go_fast = ctypes.CDLL(_lib_path)

    # Declare the C argument and return types once at import time.
    _go_fast.get_legal_moves.argtypes = [
        ctypes.POINTER(ctypes.c_int8),  # board
        ctypes.c_int8,                   # player
        ctypes.c_uint64,                 # ko_hash
        ctypes.POINTER(ctypes.c_int),    # out_moves
    ]
    _go_fast.get_legal_moves.restype = ctypes.c_int

    _go_fast.apply_move_c.argtypes = [
        ctypes.POINTER(ctypes.c_int8),  # board
        ctypes.c_int,                    # pos
        ctypes.c_int8,                   # player
        ctypes.POINTER(ctypes.c_int8),  # new_board
    ]
    _go_fast.apply_move_c.restype = ctypes.c_int
except (OSError, AttributeError):
    _go_fast = None


class GoEngine:
    """Full 9x9 Go rules engine."""

    def __init__(self, board_size: int = 9, komi: float = 6.5):
        self.board_size = board_size
        self.komi = komi
        self._max_moves = 2 * board_size * board_size
        self._use_c = _go_fast is not None and board_size == 9

        # Reuse fixed C buffers for the supported 9x9 path.
        if self._use_c:
            self._c_moves_buf = (ctypes.c_int * 82)()
            self._c_board_buf = (ctypes.c_int8 * 81)()

        # Build deterministic Zobrist tables for ko detection.
        rng = np.random.RandomState(42)
        self._zobrist_black = rng.randint(0, 2**63, size=(board_size, board_size), dtype=np.int64)
        self._zobrist_white = rng.randint(0, 2**63, size=(board_size, board_size), dtype=np.int64)

    def initial_state(self) -> dict:
        """Create a new game state."""
        return {
            'board': np.zeros((self.board_size, self.board_size), dtype=np.int8),
            'ko_hash': None,          # Previous board hash for simple ko
            'consecutive_passes': 0,
            'move_count': 0,
            'captures': {1: 0, -1: 0},  # Captures by each player
            'current_player': 1,       # Black plays first
            'history_hashes': set(),   # For superko (optional)
        }

    def _board_hash(self, board: np.ndarray) -> int:
        """Compute Zobrist hash of board position."""
        board_hash = np.int64(0)
        black_mask = board == 1
        white_mask = board == -1
        if np.any(black_mask):
            board_hash ^= np.bitwise_xor.reduce(self._zobrist_black[black_mask])
        if np.any(white_mask):
            board_hash ^= np.bitwise_xor.reduce(self._zobrist_white[white_mask])
        return int(board_hash)

    def _find_group(self, board: np.ndarray, r: int, c: int) -> Set[Tuple[int, int]]:
        """Flood-fill to find connected group of same color."""
        group_color = board[r, c]
        if group_color == 0:
            return set()
        group = set()
        stack = [(r, c)]
        while stack:
            row, col = stack.pop()
            if (row, col) in group:
                continue
            group.add((row, col))
            for row_offset, col_offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                neighbor_row = row + row_offset
                neighbor_col = col + col_offset
                if (0 <= neighbor_row < self.board_size and 0 <= neighbor_col < self.board_size
                        and board[neighbor_row, neighbor_col] == group_color
                        and (neighbor_row, neighbor_col) not in group):
                    stack.append((neighbor_row, neighbor_col))
        return group

    def _group_liberties(self, board: np.ndarray, group: Set[Tuple[int, int]]) -> int:
        """Count liberties of a group."""
        liberties = set()
        for row, col in group:
            for row_offset, col_offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                neighbor_row = row + row_offset
                neighbor_col = col + col_offset
                if (0 <= neighbor_row < self.board_size and 0 <= neighbor_col < self.board_size
                        and board[neighbor_row, neighbor_col] == 0):
                    liberties.add((neighbor_row, neighbor_col))
        return len(liberties)

    def _capture_dead_groups(self, board: np.ndarray, opponent: int) -> int:
        """Remove all opponent groups with 0 liberties. Returns capture count."""
        captured_count = 0
        visited = set()
        for row in range(self.board_size):
            for col in range(self.board_size):
                if board[row, col] == opponent and (row, col) not in visited:
                    group = self._find_group(board, row, col)
                    visited.update(group)
                    if self._group_liberties(board, group) == 0:
                        for group_row, group_col in group:
                            board[group_row, group_col] = 0
                        captured_count += len(group)
        return captured_count

    def is_legal(self, state: dict, r: int, c: int, player: int) -> bool:
        """Check if placing player's stone at (r,c) is legal."""
        board = state['board']
        if board[r, c] != 0:
            return False

        opponent = -player

        # Any empty orthogonal neighbor guarantees an immediate liberty.
        for row_offset, col_offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            neighbor_row = r + row_offset
            neighbor_col = c + col_offset
            if (0 <= neighbor_row < self.board_size and 0 <= neighbor_col < self.board_size
                    and board[neighbor_row, neighbor_col] == 0):
                return True

        # Otherwise simulate captures, suicide, and simple ko on a copy.
        candidate_board = board.copy()
        candidate_board[r, c] = player

        captured_count = self._capture_dead_groups(candidate_board, opponent)

        own_group = self._find_group(candidate_board, r, c)
        if self._group_liberties(candidate_board, own_group) == 0:
            return False  # Suicide

        if captured_count > 0 and state['ko_hash'] is not None:
            new_hash = self._board_hash(candidate_board)
            if new_hash == state['ko_hash']:
                return False  # Ko violation

        return True

    def get_legal_moves(self, state: dict) -> List[Tuple[int, int]]:
        """Get all legal moves including pass (-1, -1)."""
        if self._use_c:
            return self._get_legal_moves_c(state)

        player = state['current_player']
        moves = []
        for row in range(self.board_size):
            for col in range(self.board_size):
                if state['board'][row, col] == 0 and self.is_legal(state, row, col, player):
                    moves.append((row, col))
        moves.append((-1, -1))  # Pass is always legal
        return moves

    def _get_legal_moves_c(self, state: dict) -> List[Tuple[int, int]]:
        """C-accelerated legal move generation."""
        board = state['board']
        player = state['current_player']
        ko_hash = state['ko_hash'] if state['ko_hash'] is not None else 0

        board_ptr = board.ctypes.data_as(ctypes.POINTER(ctypes.c_int8))
        move_count = _go_fast.get_legal_moves(board_ptr, ctypes.c_int8(player),
                                               ctypes.c_uint64(ko_hash), self._c_moves_buf)

        moves = []
        for move_index in range(move_count):
            position = self._c_moves_buf[move_index]
            if position == 81:  # PASS_MOVE
                moves.append((-1, -1))
            else:
                moves.append((position // 9, position % 9))
        return moves

    def apply_move(self, state: dict, move: Tuple[int, int], lightweight: bool = False) -> dict:
        """Apply a move and return new state. Does NOT modify input state.

        Args:
            lightweight: If True, skip history_hashes copy (faster for MCTS).
        """
        player = state['current_player']

        if move == (-1, -1):
            return {
                'board': state['board'].copy(),
                'ko_hash': state['ko_hash'],
                'consecutive_passes': state['consecutive_passes'] + 1,
                'move_count': state['move_count'] + 1,
                'captures': dict(state['captures']),
                'current_player': -player,
                'history_hashes': state['history_hashes'] if lightweight else set(state['history_hashes']),
            }

        row, col = move

        if self._use_c:
            return self._apply_move_c(state, row, col, player, lightweight)

        new_state = {
            'board': state['board'].copy(),
            'ko_hash': state['ko_hash'],
            'consecutive_passes': 0,
            'move_count': state['move_count'] + 1,
            'captures': dict(state['captures']),
            'current_player': -player,
            'history_hashes': state['history_hashes'] if lightweight else set(state['history_hashes']),
        }

        # Save the pre-move board hash for the next simple-ko check.
        prev_hash = self._board_hash(new_state['board'])

        # Place the stone and remove dead opponent groups.
        new_state['board'][row, col] = player

        captured_count = self._capture_dead_groups(new_state['board'], -player)
        new_state['captures'][player] += captured_count

        # Store the pre-move hash for simple ko detection.
        new_state['ko_hash'] = prev_hash

        # Track the resulting position in the optional superko history.
        new_state['history_hashes'].add(self._board_hash(new_state['board']))

        return new_state

    def _apply_move_c(self, state: dict, r: int, c: int, player: int, lightweight: bool) -> dict:
        """C-accelerated apply_move."""
        board = state['board']
        position = r * 9 + c

        board_ptr = board.ctypes.data_as(ctypes.POINTER(ctypes.c_int8))
        captured_count = _go_fast.apply_move_c(board_ptr, ctypes.c_int(position),
                                                ctypes.c_int8(player), self._c_board_buf)

        new_board = np.frombuffer(self._c_board_buf, dtype=np.int8).copy().reshape(9, 9)

        # Preserve the existing Python hash used by this C integration path.
        prev_hash = hash(board.tobytes())

        captures = dict(state['captures'])
        captures[player] += captured_count

        return {
            'board': new_board,
            'ko_hash': prev_hash,
            'consecutive_passes': 0,
            'move_count': state['move_count'] + 1,
            'captures': captures,
            'current_player': -player,
            'history_hashes': state['history_hashes'] if lightweight else set(state['history_hashes']),
        }

    def is_terminal(self, state: dict) -> bool:
        """Check if game is over."""
        if state['consecutive_passes'] >= 2:
            return True
        if state['move_count'] >= self._max_moves:
            return True
        if np.count_nonzero(state['board']) == self.board_size * self.board_size:
            return True
        return False

    def score_position(self, board: np.ndarray) -> Tuple[float, float]:
        """Chinese area scoring. Returns (black_score, white_score)."""
        score = {1: 0.0, -1: 0.0}

        # Chinese area score starts with stones already on the board.
        for player in (1, -1):
            score[player] = float(np.sum(board == player))

        # Add each empty region only when one color exclusively surrounds it.
        visited = np.zeros_like(board, dtype=bool)
        for row in range(self.board_size):
            for col in range(self.board_size):
                if board[row, col] == 0 and not visited[row, col]:
                    region = []
                    owners = set()
                    stack = [(row, col)]
                    while stack:
                        region_row, region_col = stack.pop()
                        if (region_row < 0 or region_row >= self.board_size or
                                region_col < 0 or region_col >= self.board_size):
                            continue
                        if visited[region_row, region_col]:
                            continue
                        if board[region_row, region_col] != 0:
                            owners.add(int(board[region_row, region_col]))
                            continue
                        visited[region_row, region_col] = True
                        region.append((region_row, region_col))
                        for row_offset, col_offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                            stack.append((region_row + row_offset, region_col + col_offset))
                    if len(owners) == 1:
                        score[owners.pop()] += len(region)

        return score[1], score[-1] + self.komi

    def get_result(self, state: dict, player: int) -> float:
        """Get game result from player's perspective. 1.0=win, 0.0=loss, 0.5=draw."""
        black_score, white_score = self.score_position(state['board'])
        if player == 1:
            if black_score > white_score:
                return 1.0
            elif black_score < white_score:
                return 0.0
            return 0.5
        else:
            if white_score > black_score:
                return 1.0
            elif white_score < black_score:
                return 0.0
            return 0.5

    def get_result_black(self, state: dict) -> float:
        """Get result from Black's perspective."""
        return self.get_result(state, 1)

    def board_to_features(self, board: np.ndarray, current_player: int = 1) -> np.ndarray:
        """Convert board to 163-feature input (2 channels per cell + turn bit).

        Channel encoding:
        - Channels 0-161: Black/White stone presence (2 per cell)
        - Channel 162: Turn bit (1.0 = Black to play, 0.0 = White to play)
        """
        features = np.zeros(self.board_size * self.board_size * 2 + 1, dtype=np.float32)
        flat = board.flatten()
        for cell_index, cell in enumerate(flat):
            if cell == 1:  # Black
                features[2 * cell_index] = 1.0
            elif cell == -1:  # White
                features[2 * cell_index + 1] = 1.0
        # The final feature encodes the side to move.
        features[-1] = 1.0 if current_player == 1 else 0.0
        return features

    def print_board(self, board: np.ndarray):
        """Pretty-print the board."""
        col_letters = "ABCDEFGHJ"[:self.board_size]
        print(f"  {' '.join(col_letters)}")
        for r in range(self.board_size):
            row_num = self.board_size - r
            row_str = ' '.join(
                'X' if board[r, c] == 1 else 'O' if board[r, c] == -1 else '.'
                for c in range(self.board_size)
            )
            print(f"{row_num:2d} {row_str} {row_num}")
        print(f"  {' '.join(col_letters)}")


def test_go_engine():
    """Basic self-test."""
    engine = GoEngine(9)
    state = engine.initial_state()

    # Play a few moves
    moves = [(4, 4), (3, 3), (2, 4), (5, 5)]
    for m in moves:
        assert engine.is_legal(state, m[0], m[1], state['current_player'])
        state = engine.apply_move(state, m)

    assert not engine.is_terminal(state)
    legal = engine.get_legal_moves(state)
    assert len(legal) > 0
    assert (-1, -1) in legal

    # Test double pass terminates
    state = engine.apply_move(state, (-1, -1))
    state = engine.apply_move(state, (-1, -1))
    assert engine.is_terminal(state)

    # Test scoring
    b, w = engine.score_position(state['board'])
    assert b >= 0 and w >= 0

    print("Go engine tests passed!")


if __name__ == "__main__":
    test_go_engine()
