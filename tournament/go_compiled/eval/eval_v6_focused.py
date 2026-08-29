#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Focused eval: v6-iter3 through iter7 + current strong, 20 games each vs GnuGo L10."""
import subprocess
import ctypes as ct
import numpy as np
import os
import sys
import time

BOARD_SIZE = 9
NUM_CELLS = 81
PASS_MOVE = 81
MAX_MOVES = 200
COL_LETTERS = "ABCDEFGHJKLMNOPQRST"

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
from paths import GNUGO_BIN as GNUGO

LIB_PATH = os.path.join(_PROJECT_ROOT, 'engine', 'imc_mcts.so')
lib = ct.CDLL(LIB_PATH)
lib.load_weights.argtypes = [ct.c_char_p]
lib.load_weights.restype = ct.c_int
lib.mcts_search.argtypes = [
    ct.POINTER(ct.c_int8), ct.c_int8, ct.c_int, ct.c_int,
    ct.c_uint64, ct.c_int, ct.c_double,
]
lib.mcts_search.restype = ct.c_int
lib.apply_move_c.argtypes = [ct.POINTER(ct.c_int8), ct.c_int, ct.c_int8, ct.POINTER(ct.c_int8)]
lib.apply_move_c.restype = ct.c_int

def board_hash_fnv(board):
    board_hash = 14695981039346656037
    for value in board.ravel():
        board_hash ^= int(value) & 0xFF
        board_hash = (board_hash * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return board_hash

def move_to_gtp(m):
    if m == PASS_MOVE: return "pass"
    return f"{COL_LETTERS[m % BOARD_SIZE]}{BOARD_SIZE - m // BOARD_SIZE}"

def gtp_to_move(s):
    s = s.strip().upper()
    if s in ("PASS", "RESIGN"): return PASS_MOVE
    return (BOARD_SIZE - int(s[1:])) * BOARD_SIZE + COL_LETTERS.index(s[0])

def score_position(board, komi=6.5):
    black_score = float(np.sum(board == 1))
    white_score = float(np.sum(board == -1))
    visited = np.zeros_like(board, dtype=bool)
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row, col] != 0 or visited[row, col]: continue
            region, owners, stack = [], set(), [(row, col)]
            while stack:
                current_row, current_col = stack.pop()
                if current_row < 0 or current_row >= BOARD_SIZE or current_col < 0 or current_col >= BOARD_SIZE: continue
                if visited[current_row, current_col]: continue
                if board[current_row, current_col] != 0:
                    owners.add(int(board[current_row, current_col])); continue
                visited[current_row, current_col] = True
                region.append((current_row, current_col))
                for row_offset, col_offset in ((-1,0),(1,0),(0,-1),(0,1)):
                    stack.append((current_row+row_offset, current_col+col_offset))
            if len(owners) == 1:
                owner = owners.pop()
                if owner == 1: black_score += len(region)
                else: white_score += len(region)
    return black_score, white_score + komi


class GnuGoProcess:
    def __init__(self, level=10):
        self.proc = subprocess.Popen(
            [GNUGO, "--mode", "gtp", "--level", str(level)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True, bufsize=1)
        self._send("boardsize 9"); self._send("clear_board"); self._send("komi 6.5")

    def _send(self, cmd):
        self.proc.stdin.write(cmd + "\n"); self.proc.stdin.flush()
        response_lines, first_line = [], True
        while True:
            line = self.proc.stdout.readline()
            if not line: break
            line = line.rstrip('\n\r')
            if line.strip() == '' and not first_line: break
            if first_line:
                first_line = False
                if line.startswith("?"): return "error"
                if line.startswith("="):
                    content = line[1:].strip()
                    if content: response_lines.append(content)
                    continue
            response_lines.append(line.strip())
        return "\n".join(response_lines)

    def new_game(self): self._send("clear_board")
    def play(self, color, move): self._send(f"play {color} {move}")
    def genmove(self, color):
        response = self._send(f"genmove {color}")
        return response.strip().split()[0] if response.strip() else "pass"
    def stop(self):
        try: self._send("quit"); self.proc.terminate()
        except: pass


def eval_weights(weights_path, num_games=20, mcts_iters=500):
    gnugo_player = GnuGoProcess(level=10)
    wins = 0
    for game_index in range(num_games):
        gnugo_player.new_game()
        board = np.zeros(NUM_CELLS, dtype=np.int8)
        new_board = (ct.c_int8 * NUM_CELLS)()
        consecutive_passes, move_count, ko_hash = 0, 0, 0
        imc_black = (game_index % 2 == 0)
        resigned = False

        while move_count < MAX_MOVES and consecutive_passes < 2:
            black_turn = (move_count % 2 == 0)
            imc_turn = (black_turn == imc_black)
            color = "black" if black_turn else "white"
            current_player = 1 if black_turn else -1

            if imc_turn:
                lib.load_weights(weights_path)
                board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
                move = lib.mcts_search(board_ptr, ct.c_int8(current_player), ct.c_int(consecutive_passes),
                    ct.c_int(move_count), ct.c_uint64(ko_hash), ct.c_int(mcts_iters), ct.c_double(0.7))
                gtp_move = move_to_gtp(move)
                gnugo_player.play(color, gtp_move)
            else:
                gtp_move = gnugo_player.genmove(color)
                if gtp_move.upper() == "RESIGN": resigned = True; break
                move = gtp_to_move(gtp_move)

            if move == PASS_MOVE: consecutive_passes += 1
            else:
                consecutive_passes = 0; ko_hash = board_hash_fnv(board)
                board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
                lib.apply_move_c(board_ptr, ct.c_int(move), ct.c_int8(current_player), new_board)
                board = np.frombuffer(new_board, dtype=np.int8).copy()
            move_count += 1

        if resigned:
            wins += 1
        else:
            board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
            black_score, white_score = score_position(board_2d)
            if (imc_black and black_score > white_score) or (not imc_black and white_score > black_score):
                wins += 1
    gnugo_player.stop()
    return wins


candidates = [
    ("v6-iter3", b"weights/iterative_v6/iter3.bin"),
    ("v6-iter4", b"weights/iterative_v6/iter4.bin"),
    ("v6-iter5", b"weights/iterative_v6/iter5.bin"),
    ("v6-iter6", b"weights/iterative_v6/iter6.bin"),
    ("v6-iter7", b"weights/iterative_v6/iter7.bin"),
    ("v6-iter8", b"weights/iterative_v6/iter8.bin"),
]

N = 20
print(f"Focused eval: v6 iter3-8 vs GnuGo L10 ({N} games each)")
print("=" * 55)
for name, weights_path in candidates:
    if not os.path.exists(weights_path):
        print(f"  {name}: MISSING"); continue
    evaluation_start_time = time.time()
    wins = eval_weights(weights_path, N)
    print(f"  {name:15s}: {wins}/{N} = {wins/N*100:.0f}%  ({time.time()-evaluation_start_time:.0f}s)")
print("=" * 55)
