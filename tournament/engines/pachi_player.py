# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Pachi Player for Tournament Baseline.

GTP (Go Text Protocol) wrapper for Pachi MCTS Go engine.
Provides an external, citable baseline for comparison.

Citation:
  Baudiš, P., Gailly, J-l. (2012). PACHI: State of the Art Open Source Go Program.
  In: Advances in Computer Games. ACG 2011. Lecture Notes in Computer Science,
  vol 7168, pp. 24-38. Springer. https://doi.org/10.1007/978-3-642-31866-5_3
"""

import numpy as np
import subprocess
import os
from typing import Tuple, Optional


class PachiPlayer:
    """
    Wrapper for Pachi Go engine using GTP protocol.

    Pachi is a state-of-the-art open-source MCTS Go engine.
    This wrapper provides a common interface for tournament play.
    """

    def __init__(
        self,
        board_size: int,
        iterations: int = 5000,
        pachi_path: Optional[str] = None,
        player_id: int = 1,  # 1 for Black, -1 for White
        **kwargs  # Accept and ignore other parameters for compatibility
    ):
        """
        Initialize Pachi player.

        Args:
            board_size: Size of board (e.g., 9 for 9x9)
            iterations: Number of playouts per move (default: 5000)
            pachi_path: Path to pachi binary (auto-detect if None)
            player_id: Player color (1 = Black, -1 = White)
            **kwargs: Ignored parameters for compatibility
        """
        self.board_size = board_size
        self.iterations = iterations
        self.player_id = player_id  # Store for GameController compatibility

        # Resolve the requested Pachi binary, preferring the local tournament copy.
        if pachi_path is None:
            local_pachi = os.path.join(os.path.dirname(__file__), "pachi", "pachi")
            if os.path.exists(local_pachi):
                self.pachi_path = local_pachi
            else:
                self.pachi_path = "pachi"
        else:
            self.pachi_path = pachi_path

        # Start one persistent GTP process for this player.
        self.process = None
        self.move_history = []
        self._start_engine()

    def _start_engine(self):
        """Start Pachi GTP process."""
        try:
            # Limit tree memory and use one thread for benchmark reproducibility.
            command_args = [
                self.pachi_path,
                f"max_tree_size=1024",  # 1GB tree limit
                f"threads=1"  # Single-threaded for fair comparison
            ]

            self.process = subprocess.Popen(
                command_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,  # Capture stderr to avoid clutter
                universal_newlines=True,
                bufsize=1
            )

            # Configure the board and clear all prior engine state.
            self._send_command(f"boardsize {self.board_size}")
            self._send_command("clear_board")

            # Convert the requested playout budget to Pachi's time control.
            time_per_move = max(1, int(self.iterations / 1000))
            self._send_command(f"time_settings 0 {time_per_move} 1")

        except FileNotFoundError:
            raise RuntimeError(
                f"Pachi not found at {self.pachi_path}. "
                f"Please install Pachi or provide correct path."
            )

    def _send_command(self, command: str, debug: bool = False) -> str:
        """
        Send GTP command to Pachi and get response.

        Args:
            command: GTP command string
            debug: If True, print GTP communication for debugging

        Returns:
            Response from Pachi (without "=" prefix)
        """
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError("Pachi process not running")

        # Write one complete GTP command.
        if debug:
            print(f"    [GTP >>] {command}")
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

        # Read response lines until the blank GTP terminator.
        response_lines = []
        success = False

        while True:
            line = self.process.stdout.readline().strip()

            # A blank line terminates one GTP response.
            if not line:
                break

            # Collect content from successful response lines.
            if line.startswith("="):
                success = True
                # Extract response after "=" (e.g., "= C4" -> "C4")
                content = line[1:].strip()
                if content:
                    response_lines.append(content)
                    if debug:
                        print(f"    [GTP <<] = {content}")
                continue

            # Surface protocol errors immediately.
            if line.startswith("?"):
                if debug:
                    print(f"    [GTP <<] ERROR: {line}")
                raise RuntimeError(f"Pachi error: {line}")

            # Ignore command echoes and other diagnostic output.
            if line.startswith("IN:"):
                continue

            continue

        return " ".join(response_lines)

    def _coord_to_gtp(self, row: int, col: int) -> str:
        """
        Convert (row, col) to GTP coordinate format (e.g., "C4").

        Args:
            row: Board row (0-indexed)
            col: Board column (0-indexed)

        Returns:
            GTP coordinate string
        """
        # GTP columns skip I.
        col_letters = "ABCDEFGHJKLMNOPQRST"
        gtp_col = col_letters[col]

        # Convert top-origin array rows to bottom-origin GTP rows.
        gtp_row = self.board_size - row

        return f"{gtp_col}{gtp_row}"

    def _gtp_to_coord(self, gtp_move: str) -> Tuple[int, int]:
        """
        Convert GTP coordinate to (row, col).

        Args:
            gtp_move: GTP coordinate string (e.g., "C4")

        Returns:
            Tuple of (row, col)
        """
        gtp_move = gtp_move.strip().upper()

        if gtp_move == "PASS" or gtp_move == "RESIGN":
            return (-1, -1)

        # Decode the GTP column and bottom-origin row.
        col_letters = "ABCDEFGHJKLMNOPQRST"
        gtp_col = gtp_move[0]
        col = col_letters.index(gtp_col)

        gtp_row = int(gtp_move[1:])
        row = self.board_size - gtp_row

        return (row, col)

    def update_with_move(self, move: Tuple[int, int], player_id: int):
        """
        Update Pachi's internal state with a move that was played.

        Args:
            move: (row, col) move that was played
            player_id: 1 for Black, -1 for White
        """
        if move == (-1, -1):
            return  # Invalid move, skip

        color = "black" if player_id == 1 else "white"
        gtp_coord = self._coord_to_gtp(move[0], move[1])

        try:
            self._send_command(f"play {color} {gtp_coord}")
            self.move_history.append((move, player_id))
        except RuntimeError as e:
            # Preserve the original error and print the recent GTP history.
            print(f"\\n!!! PACHI ERROR !!!")
            print(f"Failed to update Pachi with move: {move} -> {gtp_coord} for {color}")
            print(f"Move history length: {len(self.move_history)}")
            print(f"Last 10 moves:")
            for history_index, (history_move, history_player_id) in enumerate(self.move_history[-10:], 1):
                color_name = "Black" if history_player_id == 1 else "White"
                history_gtp_move = self._coord_to_gtp(history_move[0], history_move[1])
                print(f"  {len(self.move_history)-10+history_index}. {history_move} -> {history_gtp_move} ({color_name})")

            raise

    def select_move(self, board_state: np.ndarray) -> Tuple[int, int]:
        """
        Ask Pachi to select a move for the current position.

        Args:
            board_state: numpy array (board_size, board_size) with:
                         1 = Black, -1 = White, 0 = Empty

        Returns:
            Tuple of (row, col) for Pachi's chosen move
        """
        # Request a move for this wrapper's fixed tournament color.
        current_color = "black" if self.player_id == 1 else "white"

        # genmove also applies the selected move to Pachi's internal board.
        gtp_response = self._send_command(f"genmove {current_color}", debug=False)

        # Use the first response token, or PASS for an empty response.
        gtp_move = gtp_response.strip().split()[0] if gtp_response.strip() else "PASS"

        # Convert normal coordinates and preserve PASS/RESIGN as the sentinel.
        if gtp_move in ["PASS", "RESIGN"]:
            move = (-1, -1)
        else:
            try:
                move = self._gtp_to_coord(gtp_move)
            except (ValueError, IndexError) as e:
                print(f"WARNING: Failed to parse Pachi move '{gtp_move}' from response '{gtp_response}'")
                print(f"Error: {e}")
                raise RuntimeError(f"Invalid move from Pachi: '{gtp_move}'")

        # Record locally without replaying a move already applied by genmove.
        self.move_history.append((move, self.player_id))

        return move

    def get_tree_stats(self) -> dict:
        """
        Get Pachi engine statistics.

        Returns:
            Dictionary with engine info
        """
        return {
            'nodes': self.iterations,  # Approximate - Pachi doesn't expose this
            'type': 'pachi',
            'iterations': self.iterations
        }

    def __del__(self):
        """Clean up Pachi process on deletion."""
        if self.process is not None and self.process.poll() is None:
            try:
                self._send_command("quit")
            except:
                pass

            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                self.process.kill()


def test_pachi_player():
    """Test Pachi player on simple position."""
    print("Testing Pachi Player")
    print("=" * 80)

    # Create test board (9x9)
    board = np.zeros((9, 9), dtype=int)
    board[4, 4] = 1  # Black in center
    board[3, 3] = -1  # White

    # Create player (White to move)
    print("Initializing Pachi...")
    try:
        player = PachiPlayer(board_size=9, iterations=1000, player_id=-1)
    except RuntimeError as e:
        print(f"✗ Failed to initialize Pachi: {e}")
        return

    print("Test board (White to move):")
    for row in board:
        print(" ".join([
            'B' if x == 1 else 'W' if x == -1 else '.'
            for x in row
        ]))
    print()

    # Test move selection
    print("Asking Pachi to select move (1000 playouts)...")
    move = player.select_move(board)

    print(f"Pachi selected: {move} (row={move[0]}, col={move[1]})")

    # Verify move is valid
    if move != (-1, -1):
        assert board[move[0], move[1]] == 0, f"Move {move} should be on empty position"

    print()

    stats = player.get_tree_stats()
    print(f"Engine statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print()
    print("✓ Pachi player test passed!")


if __name__ == "__main__":
    test_pachi_player()
