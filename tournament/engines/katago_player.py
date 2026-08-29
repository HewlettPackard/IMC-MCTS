# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
KataGo Player for Tournament Baseline.

GTP (Go Text Protocol) wrapper for KataGo - a state-of-the-art Go engine.
Provides an external, citable baseline for comparison.

Citation:
  Wu, D.J. (2019). Accelerating Self-Play Learning in Go.
  arXiv preprint arXiv:1902.10565.
"""

import numpy as np
import subprocess
import os
from typing import Tuple, Optional


class KataGoPlayer:
    """
    Wrapper for KataGo engine using GTP protocol.

    KataGo is a superhuman-strength Go engine that uses modern
    neural network architectures and training methods.
    """

    def __init__(
        self,
        board_size: int,
        iterations: int = 5000,
        katago_path: Optional[str] = None,
        model_path: Optional[str] = None,
        config_path: Optional[str] = None,
        player_id: int = 1,  # 1 for Black, -1 for White
        **kwargs  # Accept and ignore other parameters for compatibility
    ):
        """
        Initialize KataGo player.

        Args:
            board_size: Size of board (e.g., 9 for 9x9)
            iterations: Number of playouts per move (default: 5000)
            katago_path: Path to katago binary (auto-detect if None)
            model_path: Path to neural network model file
            config_path: Path to GTP config file
            player_id: Player color (1 = Black, -1 = White)
            **kwargs: Ignored parameters for compatibility
        """
        self.board_size = board_size
        self.iterations = iterations
        self.player_id = player_id

        # Resolve the requested KataGo binary, preferring local builds.
        if katago_path is None:
            script_dir = os.path.dirname(__file__)
            local_katago = os.path.join(script_dir, "katago_bin", "katago")
            if os.path.exists(local_katago):
                self.katago_path = local_katago
            else:
                compiled_katago = os.path.join(script_dir, "katago_bin", "KataGo", "cpp", "build", "katago")
                if os.path.exists(compiled_katago):
                    self.katago_path = compiled_katago
                else:
                    self.katago_path = "katago"
        else:
            self.katago_path = katago_path

        # Select the first local KataGo model when no model is specified.
        if model_path is None:
            script_dir = os.path.dirname(__file__)
            model_dir = os.path.join(script_dir, "katago_bin")
            if os.path.exists(model_dir):
                for model_file in os.listdir(model_dir):
                    if model_file.endswith('.bin') or model_file.endswith('.bin.gz'):
                        model_path = os.path.join(model_dir, model_file)
                        break

        if model_path is None or not os.path.exists(model_path):
            raise RuntimeError(
                f"KataGo model not found. Please provide model_path or place a .bin file in katago_bin/"
            )
        self.model_path = model_path

        # Use KataGo's local default GTP configuration when unspecified.
        if config_path is None:
            script_dir = os.path.dirname(__file__)
            config_path = os.path.join(script_dir, "katago_bin", "default_gtp.cfg")

        if not os.path.exists(config_path):
            raise RuntimeError(
                f"KataGo config not found at {config_path}"
            )
        self.config_path = config_path

        # Start one persistent GTP process for this player.
        self.process = None
        self.move_history = []
        self._start_engine()

    def _start_engine(self):
        """Start KataGo GTP process."""
        try:
            command_args = [
                self.katago_path,
                "gtp",
                "-model", self.model_path,
                "-config", self.config_path
            ]

            self.process = subprocess.Popen(
                command_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout for debugging
                universal_newlines=True,
                bufsize=1
            )

            # Configure the board and clear all prior engine state.
            self._send_command(f"boardsize {self.board_size}")
            self._send_command("clear_board")

            # Match KataGo's search budget to the tournament iteration count.
            self._send_command(f"kata-set-param maxVisits {self.iterations}")

        except FileNotFoundError:
            raise RuntimeError(
                f"KataGo not found at {self.katago_path}. "
                f"Please compile KataGo or provide correct path."
            )

    def _send_command(self, command: str, debug: bool = False) -> str:
        """
        Send GTP command to KataGo and get response.

        Args:
            command: GTP command string
            debug: If True, print GTP communication for debugging

        Returns:
            Response from KataGo (without "=" prefix)
        """
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError("KataGo process not running")

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
                raise RuntimeError(f"KataGo error: {line}")

            # Ignore KataGo diagnostic output merged into stdout.
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
        Update KataGo's internal state with a move that was played.

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
            # Map simplified-rule moves rejected by KataGo to an internal PASS.
            if "illegal move" in str(e).lower():
                try:
                    self._send_command(f"play {color} pass")
                    self.move_history.append((move, player_id))  # Record original move
                except:
                    pass  # If even PASS fails, just skip
            else:
                # Preserve non-legality failures for tournament debugging.
                print(f"\n!!! KATAGO ERROR !!!")
                print(f"Failed to update KataGo with move: {move} -> {gtp_coord} for {color}")
                print(f"Move history length: {len(self.move_history)}")
                raise

    def select_move(self, board_state: np.ndarray) -> Tuple[int, int]:
        """
        Ask KataGo to select a move for the current position.

        Args:
            board_state: numpy array (board_size, board_size) with:
                         1 = Black, -1 = White, 0 = Empty

        Returns:
            Tuple of (row, col) for KataGo's chosen move
        """
        # Request a move for this wrapper's fixed tournament color.
        current_color = "black" if self.player_id == 1 else "white"

        # genmove also applies the selected move to KataGo's internal board.
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
                print(f"WARNING: Failed to parse KataGo move '{gtp_move}' from response '{gtp_response}'")
                print(f"Error: {e}")
                raise RuntimeError(f"Invalid move from KataGo: '{gtp_move}'")

        # Record locally without replaying a move already applied by genmove.
        self.move_history.append((move, self.player_id))

        return move

    def get_tree_stats(self) -> dict:
        """
        Get KataGo engine statistics.

        Returns:
            Dictionary with engine info
        """
        return {
            'nodes': self.iterations,
            'type': 'katago',
            'iterations': self.iterations
        }

    def __del__(self):
        """Clean up KataGo process on deletion."""
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


def test_katago_player():
    """Test KataGo player on simple position."""
    print("Testing KataGo Player")
    print("=" * 80)

    # Create test board (9x9)
    board = np.zeros((9, 9), dtype=int)
    board[4, 4] = 1  # Black in center
    board[3, 3] = -1  # White

    # Create player (White to move)
    print("Initializing KataGo...")
    try:
        player = KataGoPlayer(board_size=9, iterations=100, player_id=-1)
    except RuntimeError as e:
        print(f"✗ Failed to initialize KataGo: {e}")
        return

    print("Test board (White to move):")
    for row in board:
        print(" ".join([
            'B' if x == 1 else 'W' if x == -1 else '.'
            for x in row
        ]))
    print()

    # Update KataGo with existing stones
    print("Updating KataGo with board position...")
    player.update_with_move((4, 4), 1)  # Black stone
    player.update_with_move((3, 3), -1)  # White stone (opponent's last move)

    # Test move selection
    print("Asking KataGo to select move (100 playouts for quick test)...")
    move = player.select_move(board)

    print(f"KataGo selected: {move} (row={move[0]}, col={move[1]})")

    # Verify move is valid
    if move != (-1, -1):
        assert board[move[0], move[1]] == 0, f"Move {move} should be on empty position"

    print()

    stats = player.get_tree_stats()
    print(f"Engine statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print()
    print("✓ KataGo player test passed!")


if __name__ == "__main__":
    test_katago_player()
