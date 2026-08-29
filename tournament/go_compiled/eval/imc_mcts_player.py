# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Python wrapper for the C IMC-MCTS engine.

Provides the same interface as the Python MCTSEngine for tournament integration.
"""

import ctypes
import os
import numpy as np
from typing import Tuple

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_lib_path = os.path.join(_PROJECT_ROOT, 'engine', 'imc_mcts.so')
_lib = ctypes.CDLL(_lib_path)

# Configure function signatures
_lib.load_weights.argtypes = [ctypes.c_char_p]
_lib.load_weights.restype = ctypes.c_int

_lib.mcts_search.argtypes = [
    ctypes.POINTER(ctypes.c_int8),  # board
    ctypes.c_int8,                   # player
    ctypes.c_int,                    # consecutive_passes
    ctypes.c_int,                    # move_count
    ctypes.c_uint64,                 # ko_hash
    ctypes.c_int,                    # iterations
    ctypes.c_double,                 # exploration_c
]
_lib.mcts_search.restype = ctypes.c_int

_lib.gtp_init.argtypes = [ctypes.c_int]
_lib.gtp_init.restype = None

_lib.gtp_play.argtypes = [ctypes.c_int8, ctypes.c_int]
_lib.gtp_play.restype = ctypes.c_int

_lib.gtp_genmove.argtypes = [ctypes.c_int8]
_lib.gtp_genmove.restype = ctypes.c_int

_lib.gtp_get_board.argtypes = [ctypes.POINTER(ctypes.c_int8)]
_lib.gtp_get_board.restype = None

_lib.gtp_is_terminal.argtypes = []
_lib.gtp_is_terminal.restype = ctypes.c_int

_lib.gtp_score.argtypes = []
_lib.gtp_score.restype = ctypes.c_double


class IMCMCTSPlayer:
    """C-accelerated IMC-MCTS player for tournament use."""

    def __init__(self, weights_file: str, iterations: int = 2000,
                 exploration_c: float = 0.7):
        self.iterations = iterations
        self.exploration_c = exploration_c
        self.weights_file = weights_file

        load_status = _lib.load_weights(weights_file.encode())
        if load_status != 0:
            raise RuntimeError(f"Failed to load weights from {weights_file}")

    def select_move(self, state: dict) -> Tuple[int, int]:
        """Select best move given a game state dict (compatible with GoEngine)."""
        board = state['board']
        player = state['current_player']
        consecutive_passes = state.get('consecutive_passes', 0)
        move_count = state.get('move_count', 0)
        ko_hash = 0  # Simplified; C engine uses FNV hash internally

        board_ptr = board.ctypes.data_as(ctypes.POINTER(ctypes.c_int8))

        move_index = _lib.mcts_search(
            board_ptr,
            ctypes.c_int8(player),
            ctypes.c_int(consecutive_passes),
            ctypes.c_int(move_count),
            ctypes.c_uint64(ko_hash),
            ctypes.c_int(self.iterations),
            ctypes.c_double(self.exploration_c),
        )

        if move_index == 81:  # PASS_MOVE
            return (-1, -1)
        return (move_index // 9, move_index % 9)
