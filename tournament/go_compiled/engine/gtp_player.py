# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Generic GTP (Go Text Protocol) Player Wrapper.

Unified interface for external Go engines: KataGo, Pachi, GnuGo.
"""

import subprocess
import numpy as np
from typing import Tuple, Optional


class GTPPlayer:
    """
    Generic wrapper for GTP-compatible Go engines.

    Supports: KataGo, Pachi, GnuGo
    """

    def __init__(self, engine_type: str, board_size: int = 9,
                 player_id: int = 1, **kwargs):
        """
        Args:
            engine_type: "katago", "pachi", or "gnugo"
            board_size: Board dimension
            player_id: 1 for Black, -1 for White
            **kwargs: Engine-specific options:
                katago: katago_path, model_path, config_path, max_visits
                pachi: pachi_path, time_per_move
                gnugo: gnugo_path, level
        """
        self.engine_type = engine_type
        self.board_size = board_size
        self.player_id = player_id
        self.move_history = []
        self.process = None

        self._col_letters = "ABCDEFGHJKLMNOPQRST"  # Skip I

        if engine_type == "katago":
            self._start_katago(**kwargs)
        elif engine_type == "pachi":
            self._start_pachi(**kwargs)
        elif engine_type == "gnugo":
            self._start_gnugo(**kwargs)
        else:
            raise ValueError(f"Unknown engine type: {engine_type}")

    # ------------------------------------------------------------------
    # Engine startup
    # ------------------------------------------------------------------

    def _start_katago(self, katago_path: str = "katago",
                      model_path: Optional[str] = None,
                      config_path: Optional[str] = None,
                      max_visits: int = 100, **kwargs):
        if model_path is None:
            raise ValueError("KataGo requires model_path")
        if config_path is None:
            raise ValueError("KataGo requires config_path")

        command_args = [katago_path, "gtp", "-model", model_path, "-config", config_path]
        self._launch(command_args)
        self._send(f"boardsize {self.board_size}")
        self._send("clear_board")
        self._send(f"komi 6.5")
        self._send(f"kata-set-param maxVisits {max_visits}")

    def _start_pachi(self, pachi_path: str = "pachi",
                     time_per_move: int = 5, **kwargs):
        command_args = [pachi_path, "--nopatterns", "max_tree_size=1024", "threads=1"]
        self._launch(command_args)
        self._send(f"boardsize {self.board_size}")
        self._send("clear_board")
        self._send(f"komi 6.5")
        self._send(f"time_settings 0 {time_per_move} 1")

    def _start_gnugo(self, gnugo_path: str = "gnugo",
                     level: int = 10, **kwargs):
        command_args = [gnugo_path, "--mode", "gtp", "--level", str(level)]
        self._launch(command_args)
        self._send(f"boardsize {self.board_size}")
        self._send("clear_board")
        self._send(f"komi 6.5")

    def _launch(self, cmd):
        """Launch subprocess."""
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
        except FileNotFoundError:
            raise RuntimeError(f"Engine not found: {cmd[0]}")

    # ------------------------------------------------------------------
    # GTP communication
    # ------------------------------------------------------------------

    def _send(self, command: str) -> str:
        """Send GTP command and return response."""
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError(f"{self.engine_type} process not running")

        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

        response_lines = []
        # Read until the blank line that terminates one GTP response.
        while True:
            line = self.process.stdout.readline().strip()

            if not line:
                break

            if line.startswith("="):
                content = line[1:].strip()
                if content:
                    response_lines.append(content)
                continue

            if line.startswith("?"):
                raise RuntimeError(f"{self.engine_type} error: {line}")

            # Ignore diagnostic output from any supported engine.
            continue

        return " ".join(response_lines)

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    def _coord_to_gtp(self, row: int, col: int) -> str:
        """(row, col) -> GTP string like 'C4'."""
        gtp_col = self._col_letters[col]
        gtp_row = self.board_size - row
        return f"{gtp_col}{gtp_row}"

    def _gtp_to_coord(self, gtp_move: str) -> Tuple[int, int]:
        """GTP string -> (row, col)."""
        gtp_move = gtp_move.strip().upper()
        if gtp_move in ("PASS", "RESIGN"):
            return (-1, -1)
        col = self._col_letters.index(gtp_move[0])
        row = self.board_size - int(gtp_move[1:])
        return (row, col)

    # ------------------------------------------------------------------
    # Player interface
    # ------------------------------------------------------------------

    def select_move(self, board: np.ndarray) -> Tuple[int, int]:
        """Ask engine to generate a move. genmove auto-plays internally."""
        # genmove also applies the selected move to the engine's board.
        color = "black" if self.player_id == 1 else "white"
        response = self._send(f"genmove {color}")
        gtp_move = response.strip().split()[0] if response.strip() else "PASS"

        if gtp_move in ("PASS", "RESIGN"):
            move = (-1, -1)
        else:
            move = self._gtp_to_coord(gtp_move)

        self.move_history.append((move, self.player_id))
        return move

    def update_with_move(self, move: Tuple[int, int], player_id: int):
        """Inform engine of a move played."""
        # Synchronize pass moves without adding them to local history.
        if move == (-1, -1):
            color = "black" if player_id == 1 else "white"
            try:
                self._send(f"play {color} pass")
            except RuntimeError:
                pass
            return

        color = "black" if player_id == 1 else "white"
        gtp_coord = self._coord_to_gtp(move[0], move[1])

        try:
            self._send(f"play {color} {gtp_coord}")
            self.move_history.append((move, player_id))
        except RuntimeError as e:
            if "illegal" in str(e).lower():
                # Keep the external board synchronized by substituting a pass.
                try:
                    self._send(f"play {color} pass")
                except RuntimeError:
                    pass
            else:
                raise

    def cleanup(self):
        """Shut down the engine process."""
        if self.process is not None and self.process.poll() is None:
            try:
                self._send("quit")
            except (RuntimeError, BrokenPipeError):
                pass
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()

    def __del__(self):
        self.cleanup()


def create_gtp_player(engine: str, board_size: int = 9,
                      player_id: int = 1, **kwargs) -> GTPPlayer:
    """
    Factory function for creating GTP players.

    Args:
        engine: "katago", "pachi", "gnugo"
        board_size: Board size
        player_id: 1=Black, -1=White
        **kwargs: Engine-specific options

    Returns:
        GTPPlayer instance
    """
    return GTPPlayer(engine, board_size, player_id, **kwargs)
