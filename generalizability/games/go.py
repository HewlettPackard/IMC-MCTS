# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""9x9 Go with proper capture, suicide prevention, and simple ko detection."""

from typing import List, Tuple, Set
import numpy as np

from core.algorithm.game_interface import GameInterface


class Go(GameInterface):
    name = "Go"
    board_size = 9
    description = "9x9 Go with captures and ko"
    num_players = 2

    # Board layout: (board_size + 2) x board_size
    #   Rows 0..8: the 9x9 playing area
    #   Row 9 (metadata row 0): col 0 = consecutive-pass counter,
    #       col 1 = P1 total captures, col 2 = P2 total captures, col 3 = move count
    #   Row 10 (metadata row 1): col 0 = previous board hash for ko detection
    _MAX_MOVES = 162  # 2x board cells — generous limit for a 9x9 game

    def initial_state(self) -> np.ndarray:
        # Use int16 to avoid overflow on capture counters and ko hash
        board = np.zeros((self.board_size + 2, self.board_size), dtype=np.int16)
        return board

    # ----------------------------------------------------------------
    # Group / liberty helpers
    # ----------------------------------------------------------------

    def _find_group(self, play: np.ndarray, r: int, c: int) -> Set[Tuple[int, int]]:
        """Flood-fill to find connected stones of the same colour (4-dir)."""
        color = play[r, c]
        if color == 0:
            return set()
        group: Set[Tuple[int, int]] = set()
        stack = [(r, c)]
        while stack:
            row, col = stack.pop()
            cell = (row, col)
            if cell in group:
                continue
            group.add(cell)
            for row_step, col_step in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                next_row = row + row_step
                next_col = col + col_step
                next_cell = (next_row, next_col)
                if (0 <= next_row < self.board_size and
                        0 <= next_col < self.board_size and
                        play[next_row, next_col] == color and
                        next_cell not in group):
                    stack.append(next_cell)
        return group

    def _group_liberties(self, play: np.ndarray, group: Set[Tuple[int, int]]) -> int:
        """Count empty neighbours (liberties) of a group."""
        liberties: Set[Tuple[int, int]] = set()
        for row, col in group:
            for row_step, col_step in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                next_row = row + row_step
                next_col = col + col_step
                if (0 <= next_row < self.board_size and
                        0 <= next_col < self.board_size and
                        play[next_row, next_col] == 0):
                    liberties.add((next_row, next_col))
        return len(liberties)

    # ----------------------------------------------------------------
    # Capture logic
    # ----------------------------------------------------------------

    def _capture_dead_groups(self, play: np.ndarray, opponent: int) -> int:
        """Remove all opponent groups with 0 liberties. Returns capture count."""
        captured_stones = 0
        visited = np.zeros((self.board_size, self.board_size), dtype=bool)
        for row in range(self.board_size):
            for col in range(self.board_size):
                if play[row, col] == opponent and not visited[row, col]:
                    group = self._find_group(play, row, col)
                    for group_row, group_col in group:
                        visited[group_row, group_col] = True
                    if self._group_liberties(play, group) == 0:
                        for group_row, group_col in group:
                            play[group_row, group_col] = 0
                        captured_stones += len(group)
        return captured_stones

    # ----------------------------------------------------------------
    # Ko / suicide detection helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _board_hash(play: np.ndarray) -> int:
        """Simple hash of the playing area for ko comparison."""
        return hash(play.tobytes())

    def _store_ko_hash(self, board: np.ndarray, h: int) -> None:
        """Store truncated board hash in metadata row 1, col 0 (int16)."""
        board[self.board_size + 1, 0] = h & 0x7FFF  # keep within int16 range

    def _load_ko_hash(self, board: np.ndarray) -> int:
        return int(board[self.board_size + 1, 0])

    # ----------------------------------------------------------------
    # Move legality
    # ----------------------------------------------------------------

    def _has_liberty_fast(self, play: np.ndarray, r: int, c: int) -> bool:
        """Quick check: does position (r,c) have an empty orthogonal neighbour?"""
        board_size = self.board_size
        for row_step, col_step in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            next_row = r + row_step
            next_col = c + col_step
            if (0 <= next_row < board_size and
                    0 <= next_col < board_size and
                    play[next_row, next_col] == 0):
                return True
        return False

    def _neighbor_has_one_liberty(self, play: np.ndarray, r: int, c: int, color: int) -> bool:
        """Check if any neighbouring group of `color` has exactly 1 liberty (at r,c)."""
        board_size = self.board_size
        checked: Set[Tuple[int, int]] = set()
        for row_step, col_step in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            next_row = r + row_step
            next_col = c + col_step
            next_cell = (next_row, next_col)
            if (0 <= next_row < board_size and
                    0 <= next_col < board_size and
                    play[next_row, next_col] == color and
                    next_cell not in checked):
                group = self._find_group(play, next_row, next_col)
                checked |= group
                if self._group_liberties(play, group) == 1:
                    return True
        return False

    def _is_legal(self, board: np.ndarray, r: int, c: int, player: int) -> bool:
        """Check whether placing player at (r,c) is legal (not suicide, not ko)."""
        play_board = board[:self.board_size]
        if play_board[r, c] != 0:
            return False

        opponent = 3 - player

        # Fast path: if the cell has an empty neighbour, placing here gives
        # the new stone at least 1 liberty, so it can't be suicide.
        # Ko only matters when exactly 1 stone is captured, so also skip
        # the expensive check unless an opponent neighbour group has 1 liberty.
        if self._has_liberty_fast(play_board, r, c):
            return True

        # Slow path: need to simulate to check suicide / ko
        test_board = play_board.copy()
        test_board[r, c] = player

        # Capture opponent dead groups
        captured_stones = self._capture_dead_groups(test_board, opponent)

        # Check if our own group has liberties after captures
        own_group = self._find_group(test_board, r, c)
        if self._group_liberties(test_board, own_group) == 0:
            return False  # suicide

        # Simple ko check: would the new board recreate the previous state?
        if captured_stones > 0:
            new_hash = self._board_hash(test_board) & 0x7FFF
            previous_hash = self._load_ko_hash(board)
            if new_hash == previous_hash:
                return False  # ko violation

        return True

    # ----------------------------------------------------------------
    # GameInterface implementation
    # ----------------------------------------------------------------

    def get_legal_moves(self, board: np.ndarray, player: int) -> List[Tuple[int, int]]:
        moves = []
        for row in range(self.board_size):
            for col in range(self.board_size):
                if (board[row, col] == 0 and
                        self._is_legal(board, row, col, player)):
                    moves.append((row, col))
        # Pass is always legal — include multiple times proportional to board
        # fill ratio so random rollouts naturally double-pass as the board fills,
        # ending games with meaningful area scores instead of hitting the move limit.
        total_cells = self.board_size * self.board_size
        stone_count = int(np.count_nonzero(board[:self.board_size]))
        fill_ratio = stone_count / total_cells
        # Number of pass copies: at least 1, scaling up as board fills
        num_passes = max(1, int(fill_ratio * len(moves))) if moves else 1
        for _ in range(num_passes):
            moves.append((-1, -1))
        return moves

    def apply_move(self, board: np.ndarray, move: Tuple[int, int], player: int) -> np.ndarray:
        new_board = board.copy()

        if move == (-1, -1):
            # Pass
            new_board[self.board_size, 0] += 1
            new_board[self.board_size, 3] += 1
            return new_board

        row, col = move
        play_board = new_board[:self.board_size]
        opponent = 3 - player

        # Stage 1: save the pre-move board hash for ko detection.
        previous_hash = self._board_hash(play_board)

        # Stage 2: place the stone and remove captured groups.
        play_board[row, col] = player
        captured_stones = self._capture_dead_groups(play_board, opponent)

        # Stage 3: update capture, ko, pass, and move metadata.
        new_board[self.board_size, player] += captured_stones  # col 1 for P1, col 2 for P2

        # Store previous-board hash for ko detection
        self._store_ko_hash(new_board, previous_hash & 0x7FFF)

        # Reset consecutive-pass counter
        new_board[self.board_size, 0] = 0

        # Increment move counter
        new_board[self.board_size, 3] += 1

        return new_board

    def is_terminal(self, board: np.ndarray) -> bool:
        # Two consecutive passes
        if board[self.board_size, 0] >= 2:
            return True
        # Board full
        if np.count_nonzero(board[:self.board_size]) == self.board_size * self.board_size:
            return True
        # Move limit (prevents infinite cycling in random play)
        if board[self.board_size, 3] >= self._MAX_MOVES:
            return True
        return False

    def get_result(self, board: np.ndarray, player: int) -> float:
        """Area scoring: stones + territory. Komi 6.5 for player 2 (white)."""
        area_score = {1: 0.0, 2: 0.0}
        play_board = board[:self.board_size]

        for color in (1, 2):
            area_score[color] += float(np.sum(play_board == color))

        # Assign empty regions surrounded by a single colour
        visited = np.zeros_like(play_board, dtype=bool)
        for row in range(self.board_size):
            for col in range(self.board_size):
                if play_board[row, col] == 0 and not visited[row, col]:
                    region, owners = [], set()
                    stack = [(row, col)]
                    while stack:
                        region_row, region_col = stack.pop()
                        if (region_row < 0 or region_row >= self.board_size or
                                region_col < 0 or region_col >= self.board_size):
                            continue
                        if visited[region_row, region_col]:
                            continue
                        if play_board[region_row, region_col] != 0:
                            owners.add(int(play_board[region_row, region_col]))
                            continue
                        visited[region_row, region_col] = True
                        region.append((region_row, region_col))
                        for row_step, col_step in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                            stack.append((region_row + row_step,
                                          region_col + col_step))
                    if len(owners) == 1:
                        area_score[owners.pop()] += len(region)

        area_score[2] += 6.5  # komi
        if area_score[player] > area_score[3 - player]:
            return 1.0
        elif area_score[player] < area_score[3 - player]:
            return 0.0
        return 0.5

    # ----------------------------------------------------------------
    # Metrics for behavioral demo
    # ----------------------------------------------------------------

    def get_metrics(self, board: np.ndarray) -> dict:
        play_board = board[:self.board_size]
        # Territory scores (area scoring)
        area_score = {1: 0.0, 2: 0.0}
        for color in (1, 2):
            area_score[color] += float(np.sum(play_board == color))
        visited = np.zeros_like(play_board, dtype=bool)
        for row in range(self.board_size):
            for col in range(self.board_size):
                if play_board[row, col] == 0 and not visited[row, col]:
                    region, owners = [], set()
                    stack = [(row, col)]
                    while stack:
                        region_row, region_col = stack.pop()
                        if (region_row < 0 or region_row >= self.board_size or
                                region_col < 0 or region_col >= self.board_size):
                            continue
                        if visited[region_row, region_col]:
                            continue
                        if play_board[region_row, region_col] != 0:
                            owners.add(int(play_board[region_row, region_col]))
                            continue
                        visited[region_row, region_col] = True
                        region.append((region_row, region_col))
                        for row_step, col_step in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                            stack.append((region_row + row_step,
                                          region_col + col_step))
                    if len(owners) == 1:
                        area_score[owners.pop()] += len(region)
        area_score[2] += 6.5
        territory_diff = area_score[1] - area_score[2]

        # Captures
        p1_captures = int(board[self.board_size, 1])
        p2_captures = int(board[self.board_size, 2])

        return {
            "territory_score": territory_diff,
            "captures_p1": p1_captures,
            "captures_p2": p2_captures,
            "total_captures": p1_captures + p2_captures,
        }
