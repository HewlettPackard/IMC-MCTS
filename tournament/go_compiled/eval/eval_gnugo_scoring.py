#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Eval IMC vs GnuGo using GnuGo's own final_score for accurate results.
This fixes the dead stone detection issue in our scoring.
"""
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
    def final_score(self):
        """Ask GnuGo for the final score (handles dead stone removal)."""
        return self._send("final_score")
    def stop(self):
        try: self._send("quit"); self.proc.terminate()
        except: pass


def parse_gnugo_score(score_str):
    """Parse GnuGo score like 'W+13.5' or 'B+5.5' or '0'. Returns (winner, margin)."""
    score_str = score_str.strip()
    if score_str == "0":
        return "D", 0.0
    if score_str.startswith("W+"):
        return "W", float(score_str[2:])
    elif score_str.startswith("B+"):
        return "B", float(score_str[2:])
    return "D", 0.0


def eval_weights(weights_path, num_games=20, mcts_iters=500, level=1):
    """Evaluate using GnuGo's scoring for accuracy."""
    gnugo_player = GnuGoProcess(level=level)
    imc_wins_gnugo_scoring = 0
    imc_wins_our_scoring = 0

    for game_index in range(num_games):
        gnugo_player.new_game()
        lib.load_weights(weights_path)
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
                if gtp_move.upper() == "RESIGN":
                    resigned = True; break
                move = gtp_to_move(gtp_move)

            if move == PASS_MOVE: consecutive_passes += 1
            else:
                consecutive_passes = 0; ko_hash = board_hash_fnv(board)
                board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
                lib.apply_move_c(board_ptr, ct.c_int(move), ct.c_int8(current_player), new_board)
                board = np.frombuffer(new_board, dtype=np.int8).copy()
            move_count += 1

        if resigned:
            imc_wins_gnugo_scoring += 1
            imc_wins_our_scoring += 1
            result = "IMC(resign)"
        else:
            # GnuGo scoring (accurate)
            gnugo_score = gnugo_player.final_score()
            winner, margin = parse_gnugo_score(gnugo_score)
            imc_color = "B" if imc_black else "W"
            if winner == imc_color:
                imc_wins_gnugo_scoring += 1

            # Our scoring (for comparison)
            from eval.debug_gnugo import score_position
            board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
            black_score, white_score = score_position(board_2d)
            if (imc_black and black_score > white_score) or (not imc_black and white_score > black_score):
                imc_wins_our_scoring += 1

            result = f"gnugo={gnugo_score} ours={'B' if black_score>white_score else 'W'}+{abs(black_score-white_score):.1f}"

        imc_side = "B" if imc_black else "W"
        print(f"  Game {game_index+1:2d}: IMC={imc_side} | {result}")

    gnugo_player.stop()
    return imc_wins_gnugo_scoring, imc_wins_our_scoring, num_games


def main():
    weights = b"weights/final/strong.bin"

    print("=" * 70)
    print("  Scoring Comparison: GnuGo final_score vs our score_position")
    print("=" * 70)

    for level in [1, 10]:
        print(f"\n--- vs GnuGo L{level} (20 games, 500 MCTS iters) ---")
        evaluation_start_time = time.time()
        gnugo_wins, our_wins, total = eval_weights(weights, 20, 500, level)
        elapsed = time.time() - evaluation_start_time
        print(f"\n  GnuGo scoring: {gnugo_wins}/{total} = {gnugo_wins/total*100:.0f}%")
        print(f"  Our scoring:   {our_wins}/{total} = {our_wins/total*100:.0f}%")
        print(f"  Disagreements: {abs(gnugo_wins - our_wins)} games")
        print(f"  Time: {elapsed:.0f}s")

    # Also test mixed_v1
    print(f"\n--- mixed_v1 vs GnuGo L1 (20 games) ---")
    mixed_weights = b"weights/mixed/mixed_v1.bin"
    if os.path.exists(mixed_weights):
        gnugo_wins, our_wins, total = eval_weights(mixed_weights, 20, 500, 1)
        print(f"\n  GnuGo scoring: {gnugo_wins}/{total} = {gnugo_wins/total*100:.0f}%")
        print(f"  Our scoring:   {our_wins}/{total} = {our_wins/total*100:.0f}%")


if __name__ == "__main__":
    main()
