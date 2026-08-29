#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Debug: play one verbose game vs GnuGo L1 and L10, print every move."""
import subprocess
import ctypes as ct
import numpy as np
import os
import sys

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

def print_board(board):
    symbols = {0: '.', 1: 'X', -1: 'O'}
    b2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
    print("  " + " ".join(COL_LETTERS[:BOARD_SIZE]))
    for r in range(BOARD_SIZE):
        row = " ".join(symbols[b2d[r, c]] for c in range(BOARD_SIZE))
        print(f"{BOARD_SIZE - r} {row} {BOARD_SIZE - r}")
    print("  " + " ".join(COL_LETTERS[:BOARD_SIZE]))


class GnuGoProcess:
    def __init__(self, level=1):
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
    def final_score(self):
        return self._send("final_score")
    def stop(self):
        try: self._send("quit"); self.proc.terminate()
        except: pass


def play_verbose(level, imc_is_black=True):
    weights = b"weights/final/strong.bin"
    lib.load_weights(weights)
    gnugo_player = GnuGoProcess(level=level)

    board = np.zeros(NUM_CELLS, dtype=np.int8)
    new_board = (ct.c_int8 * NUM_CELLS)()
    consecutive_passes, move_count, ko_hash = 0, 0, 0
    resigned = False

    print(f"\n{'='*40}")
    print(f"IMC ({'Black' if imc_is_black else 'White'}) vs GnuGo L{level}")
    print(f"{'='*40}")

    while move_count < MAX_MOVES and consecutive_passes < 2:
        black_turn = (move_count % 2 == 0)
        imc_turn = (black_turn == imc_is_black)
        color = "black" if black_turn else "white"
        current_player = 1 if black_turn else -1
        symbol = "X(B)" if black_turn else "O(W)"

        if imc_turn:
            lib.load_weights(weights)
            board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
            move = lib.mcts_search(board_ptr, ct.c_int8(current_player), ct.c_int(consecutive_passes),
                ct.c_int(move_count), ct.c_uint64(ko_hash), ct.c_int(500), ct.c_double(0.7))
            gtp_move = move_to_gtp(move)
            gnugo_player.play(color, gtp_move)
            player_name = "IMC"
        else:
            gtp_move = gnugo_player.genmove(color)
            if gtp_move.upper() == "RESIGN":
                print(f"  Move {move_count+1}: GnuGo {symbol} RESIGNS")
                resigned = True; break
            move = gtp_to_move(gtp_move)
            player_name = "GNU"

        if move == PASS_MOVE:
            consecutive_passes += 1
            print(f"  Move {move_count+1}: {player_name} {symbol} passes")
        else:
            consecutive_passes = 0; ko_hash = board_hash_fnv(board)
            board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
            lib.apply_move_c(board_ptr, ct.c_int(move), ct.c_int8(current_player), new_board)
            board = np.frombuffer(new_board, dtype=np.int8).copy()
            print(f"  Move {move_count+1}: {player_name} {symbol} plays {gtp_move}")
        move_count += 1

    print(f"\nFinal board after {move_count} moves:")
    print_board(board)

    board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
    black_score, white_score = score_position(board_2d)
    print(f"\nOur scoring: Black={black_score:.1f} White={white_score:.1f}")

    # Also ask GnuGo for its score
    gnugo_score = gnugo_player.final_score()
    print(f"GnuGo scoring: {gnugo_score}")

    if resigned:
        print("Result: GnuGo resigned -> IMC wins!")
    elif (imc_is_black and black_score > white_score) or (not imc_is_black and white_score > black_score):
        print("Result: IMC wins!")
    else:
        print("Result: GnuGo wins")

    gnugo_player.stop()


# Play 2 games vs L1 and 2 vs L10
play_verbose(1, imc_is_black=True)
play_verbose(1, imc_is_black=False)
play_verbose(10, imc_is_black=True)
play_verbose(10, imc_is_black=False)
