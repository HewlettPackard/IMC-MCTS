# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Go Rules Implementation - Proper capture and suicide detection.

Implements standard Go rules for stone captures and suicide prevention.
This module ensures the tournament game controller applies the same rules
that external Go engines (KataGo, Pachi) expect.
"""

import numpy as np
from typing import List, Tuple


class GoRules:
    """
    Implements proper Go rules for stone captures and move validation.

    Rules implemented:
    - Group connectivity via flood-fill
    - Liberty counting for groups
    - Capture of groups with zero liberties
    - Suicide move prevention (unless capturing)
    """

    def __init__(self, board_size: int):
        """
        Initialize Go rules engine.

        Args:
            board_size: Size of the Go board (e.g., 9 for 9x9)
        """
        self.board_size = board_size

    def _find_group(self, board: np.ndarray, i: int, j: int, visited: np.ndarray) -> List[Tuple[int, int]]:
        """
        Find all stones connected to position (i, j) using flood-fill.

        Args:
            board: Board state array
            i: Row coordinate
            j: Column coordinate
            visited: Array tracking visited positions

        Returns:
            List of (row, col) tuples forming the connected group
        """
        if visited[i, j]:
            return []

        group_color = board[i, j]
        if group_color == 0:
            return []

        group = []
        stack = [(i, j)]

        while stack:
            row, col = stack.pop()
            if visited[row, col]:
                continue

            visited[row, col] = True
            group.append((row, col))

            # Continue the flood-fill through same-color orthogonal neighbors.
            for row_offset, col_offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                neighbor_row = row + row_offset
                neighbor_col = col + col_offset
                if (0 <= neighbor_row < self.board_size and 0 <= neighbor_col < self.board_size
                    and not visited[neighbor_row, neighbor_col]
                    and board[neighbor_row, neighbor_col] == group_color):
                    stack.append((neighbor_row, neighbor_col))

        return group

    def _get_group_liberties(self, board: np.ndarray, group: List[Tuple[int, int]]) -> int:
        """
        Count liberties (empty adjacent points) for a group of stones.

        Args:
            board: Board state array
            group: List of (row, col) positions forming the group

        Returns:
            Number of liberties for the group
        """
        liberties = set()

        for row, col in group:
            for row_offset, col_offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                neighbor_row = row + row_offset
                neighbor_col = col + col_offset
                if (0 <= neighbor_row < self.board_size and 0 <= neighbor_col < self.board_size
                    and board[neighbor_row, neighbor_col] == 0):
                    liberties.add((neighbor_row, neighbor_col))

        return len(liberties)

    def _capture_groups(self, board: np.ndarray, opponent_color: int) -> int:
        """
        Remove all opponent groups with zero liberties (captured groups).

        Args:
            board: Board state array (modified in-place)
            opponent_color: Color of opponent stones to check (1 or -1)

        Returns:
            Number of stones captured
        """
        captured_count = 0
        visited = np.zeros((self.board_size, self.board_size), dtype=bool)

        for row in range(self.board_size):
            for col in range(self.board_size):
                if board[row, col] == opponent_color and not visited[row, col]:
                    group = self._find_group(board, row, col, visited)

                    if group:
                        liberties = self._get_group_liberties(board, group)

                        if liberties == 0:
                            # Remove this captured group from the board.
                            for group_row, group_col in group:
                                board[group_row, group_col] = 0
                            captured_count += len(group)

        return captured_count

    def _is_suicide_move(self, board: np.ndarray, i: int, j: int, color: int) -> bool:
        """
        Check if placing a stone at (i, j) would be suicide.

        A move is suicide if it results in the placed stone's group having
        zero liberties AND doesn't capture any opponent groups.

        Args:
            board: Board state array
            i: Row coordinate
            j: Column coordinate
            color: Color of stone to place (1 or -1)

        Returns:
            True if the move would be suicide, False otherwise
        """
        if board[i, j] != 0:
            return True  # Position already occupied

        # Place the candidate stone while checking captures and liberties.
        board[i, j] = color

        # A neighboring capture makes an otherwise zero-liberty move legal.
        opponent_color = -color
        opponent_captured = False

        for row_offset, col_offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            neighbor_row = i + row_offset
            neighbor_col = j + col_offset
            if (0 <= neighbor_row < self.board_size and 0 <= neighbor_col < self.board_size
                and board[neighbor_row, neighbor_col] == opponent_color):
                visited = np.zeros((self.board_size, self.board_size), dtype=bool)
                opponent_group = self._find_group(board, neighbor_row, neighbor_col, visited)
                if opponent_group and self._get_group_liberties(board, opponent_group) == 0:
                    opponent_captured = True
                    break

        # Count liberties of the candidate stone's connected group.
        visited = np.zeros((self.board_size, self.board_size), dtype=bool)
        our_group = self._find_group(board, i, j, visited)
        our_liberties = self._get_group_liberties(board, our_group)

        # Restore the caller's board before returning the legality result.
        board[i, j] = 0

        # A move is suicide only when both escape conditions fail.
        return (our_liberties == 0 and not opponent_captured)

    def apply_move(self, board: np.ndarray, row: int, col: int, color: int) -> Tuple[bool, int]:
        """
        Apply a move to the board with proper Go rules (captures, suicide).

        Args:
            board: Board state array (modified in-place if move is legal)
            row: Row coordinate of move
            col: Column coordinate of move
            color: Color of stone to place (1 or -1)

        Returns:
            Tuple of (move_was_legal, captured_stones_count)
        """
        # Reject occupied points and suicide moves before mutating the board.
        if board[row, col] != 0:
            return (False, 0)

        if self._is_suicide_move(board, row, col, color):
            return (False, 0)

        # Apply the legal stone, then remove captured opponent groups.
        board[row, col] = color

        opponent_color = -color
        captured_count = self._capture_groups(board, opponent_color)

        return (True, captured_count)

    def is_legal_move(self, board: np.ndarray, row: int, col: int, color: int) -> bool:
        """
        Check if a move is legal without modifying the board.

        Args:
            board: Board state array (not modified)
            row: Row coordinate of move
            col: Column coordinate of move
            color: Color of stone to place (1 or -1)

        Returns:
            True if the move is legal, False otherwise
        """
        # Test legality on a copy so the input board remains unchanged.
        if board[row, col] != 0:
            return False

        board_copy = board.copy()
        if self._is_suicide_move(board_copy, row, col, color):
            return False

        return True


def test_go_rules():
    """Test Go rules implementation."""
    print("Testing Go Rules Implementation")
    print("=" * 80)

    rules = GoRules(board_size=9)

    # Test 1: Simple capture
    print("\nTest 1: Simple Capture")
    print("-" * 40)
    board = np.zeros((9, 9), dtype=int)
    # Create a white stone surrounded by black
    board[4, 4] = -1  # White stone
    board[3, 4] = 1   # Black above
    board[5, 4] = 1   # Black below
    board[4, 3] = 1   # Black left
    # Black plays at (4,5) to capture

    print("Before capture:")
    for row in board[2:7, 2:7]:
        print(" ".join(['B' if x == 1 else 'W' if x == -1 else '.' for x in row]))

    legal, captured = rules.apply_move(board, 4, 5, 1)  # Black plays right

    print(f"\nMove legal: {legal}, Captured: {captured} stones")
    print("\nAfter capture:")
    for row in board[2:7, 2:7]:
        print(" ".join(['B' if x == 1 else 'W' if x == -1 else '.' for x in row]))

    assert legal == True, "Capture move should be legal"
    assert captured == 1, "Should capture 1 white stone"
    assert board[4, 4] == 0, "White stone should be removed"
    print("✓ Capture test passed")

    # Test 2: Suicide prevention
    print("\n\nTest 2: Suicide Prevention")
    print("-" * 40)
    board = np.zeros((9, 9), dtype=int)
    # Create a position where white would be suicide
    board[3, 4] = 1   # Black above
    board[5, 4] = 1   # Black below
    board[4, 3] = 1   # Black left
    board[4, 5] = 1   # Black right
    # White tries to play at (4,4) - suicide!

    print("Board state:")
    for row in board[2:7, 2:7]:
        print(" ".join(['B' if x == 1 else 'W' if x == -1 else '.' for x in row]))

    legal, captured = rules.apply_move(board, 4, 4, -1)  # White tries suicide

    print(f"\nMove legal: {legal} (should be False - suicide)")
    assert legal == False, "Suicide move should be illegal"
    assert board[4, 4] == 0, "Board should be unchanged"
    print("✓ Suicide prevention test passed")

    # Test 3: Suicide allowed when capturing
    print("\n\nTest 3: Suicide Allowed When Capturing")
    print("-" * 40)
    board = np.zeros((9, 9), dtype=int)
    # White group with one liberty at (4,5)
    board[4, 4] = -1  # White
    board[3, 4] = 1   # Black above white
    board[5, 4] = 1   # Black below white
    board[4, 3] = 1   # Black left of white
    # Black group surrounding (4,5)
    board[3, 5] = 1   # Black above (4,5)
    board[5, 5] = 1   # Black below (4,5)
    board[4, 6] = 1   # Black right of (4,5)
    # Black plays at (4,5) - looks like suicide but captures white!

    print("Board state:")
    for row in board[2:7, 2:8]:
        print(" ".join(['B' if x == 1 else 'W' if x == -1 else '.' for x in row]))

    legal, captured = rules.apply_move(board, 4, 5, 1)  # Black captures

    print(f"\nMove legal: {legal} (should be True - capturing saves it)")
    print(f"Captured: {captured} stones")
    print("\nAfter move:")
    for row in board[2:7, 2:8]:
        print(" ".join(['B' if x == 1 else 'W' if x == -1 else '.' for x in row]))

    assert legal == True, "Capture move should be legal even if it looks like suicide"
    assert captured == 1, "Should capture white stone"
    print("✓ Suicide-with-capture test passed")

    print("\n" + "=" * 80)
    print("All Go rules tests passed!")


if __name__ == "__main__":
    test_go_rules()
