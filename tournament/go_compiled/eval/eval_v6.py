#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Quick eval of v6 iterations vs GnuGo L10 (20 games each)."""
import subprocess
import ctypes as ct
import numpy as np
import os
import time
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


def move_to_gtp(move_int):
    if move_int == PASS_MOVE:
        return "pass"
    row, col = move_int // BOARD_SIZE, move_int % BOARD_SIZE
    return f"{COL_LETTERS[col]}{BOARD_SIZE - row}"


def gtp_to_move(gtp_str):
    gtp_str = gtp_str.strip().upper()
    if gtp_str in ("PASS", "RESIGN"):
        return PASS_MOVE
    col = COL_LETTERS.index(gtp_str[0])
    row = BOARD_SIZE - int(gtp_str[1:])
    return row * BOARD_SIZE + col


def score_position(board, komi=6.5):
    black_score = float(np.sum(board == 1))
    white_score = float(np.sum(board == -1))
    visited = np.zeros_like(board, dtype=bool)
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r, c] != 0 or visited[r, c]:
                continue
            region = []
            owners = set()
            stack = [(r, c)]
            while stack:
                cr, cc = stack.pop()
                if cr < 0 or cr >= BOARD_SIZE or cc < 0 or cc >= BOARD_SIZE:
                    continue
                if visited[cr, cc]:
                    continue
                if board[cr, cc] != 0:
                    owners.add(int(board[cr, cc]))
                    continue
                visited[cr, cc] = True
                region.append((cr, cc))
                for dr, dc in ((-1,0),(1,0),(0,-1),(0,1)):
                    stack.append((cr+dr, cc+dc))
            if len(owners) == 1:
                owner = owners.pop()
                if owner == 1:
                    black_score += len(region)
                else:
                    white_score += len(region)
    return black_score, white_score + komi


class GnuGoProcess:
    def __init__(self, level=10):
        self.proc = subprocess.Popen(
            [GNUGO, "--mode", "gtp", "--level", str(level)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True, bufsize=1
        )
        self._send("boardsize 9")
        self._send("clear_board")
        self._send("komi 6.5")

    def _send(self, cmd):
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()
        lines = []
        first = True
        while True:
            line = self.proc.stdout.readline()
            if not line:
                break
            line = line.rstrip('\n\r')
            if line.strip() == '' and not first:
                break
            if first:
                first = False
                if line.startswith("?"):
                    return "error"
                if line.startswith("="):
                    content = line[1:].strip()
                    if content:
                        lines.append(content)
                    continue
            lines.append(line.strip())
        return "\n".join(lines)

    def new_game(self):
        self._send("clear_board")

    def play(self, color, gtp_move):
        self._send(f"play {color} {gtp_move}")

    def genmove(self, color):
        response = self._send(f"genmove {color}")
        return response.strip().split()[0] if response.strip() else "pass"

    def stop(self):
        try:
            self._send("quit")
            self.proc.terminate()
        except:
            pass


def eval_weights_vs_gnugo(weights_path, num_games=20, mcts_iters=500):
    """Play num_games vs GnuGo L10 with alternating colors. Return win count."""
    gnugo_player = GnuGoProcess(level=10)
    imc_wins = 0

    for game_index in range(num_games):
        gnugo_player.new_game()
        board = np.zeros(NUM_CELLS, dtype=np.int8)
        new_board_buf = (ct.c_int8 * NUM_CELLS)()
        consecutive_passes = 0
        move_count = 0
        ko_hash = 0
        resigned = False

        # Alternate: even=IMC is Black, odd=IMC is White
        imc_is_black = (game_index % 2 == 0)

        while move_count < MAX_MOVES and consecutive_passes < 2:
            is_black_turn = (move_count % 2 == 0)
            imc_turn = (is_black_turn == imc_is_black)
            color_str = "black" if is_black_turn else "white"
            player_int = 1 if is_black_turn else -1

            if imc_turn:
                lib.load_weights(weights_path)
                board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
                move = lib.mcts_search(
                    board_ptr, ct.c_int8(player_int),
                    ct.c_int(consecutive_passes), ct.c_int(move_count),
                    ct.c_uint64(ko_hash), ct.c_int(mcts_iters), ct.c_double(0.7)
                )
                gtp_move = move_to_gtp(move)
                gnugo_player.play(color_str, gtp_move)
            else:
                gtp_move = gnugo_player.genmove(color_str)
                if gtp_move.upper() == "RESIGN":
                    resigned = True
                    break
                move = gtp_to_move(gtp_move)

            if move == PASS_MOVE:
                consecutive_passes += 1
            else:
                consecutive_passes = 0
                ko_hash = board_hash_fnv(board)
                board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
                lib.apply_move_c(board_ptr, ct.c_int(move), ct.c_int8(player_int), new_board_buf)
                board = np.frombuffer(new_board_buf, dtype=np.int8).copy()

            move_count += 1

        # Determine winner
        if resigned:
            # GnuGo resigned, IMC wins
            imc_wins += 1
        else:
            board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
            black_score, white_score = score_position(board_2d)
            if imc_is_black and black_score > white_score:
                imc_wins += 1
            elif not imc_is_black and white_score > black_score:
                imc_wins += 1

    gnugo_player.stop()
    return imc_wins


def main():
    # Test these weight files
    candidates = [
        ("current-strong", b"weights/final/strong.bin"),
        ("v6-iter5", b"weights/iterative_v6/iter5.bin"),
        ("v6-iter10", b"weights/iterative_v6/iter10.bin"),
        ("v6-iter15", b"weights/iterative_v6/iter15.bin"),
        ("v6-best", b"weights/iterative_v6/best_model.bin"),
    ]

    num_games = 20
    print(f"Evaluating {len(candidates)} models vs GnuGo L10 ({num_games} games each)")
    print(f"{'='*60}")

    results = []
    for name, weights_path in candidates:
        if not os.path.exists(weights_path):
            print(f"  {name}: MISSING ({weights_path})")
            continue
        evaluation_start_time = time.time()
        wins = eval_weights_vs_gnugo(weights_path, num_games=num_games, mcts_iters=500)
        elapsed = time.time() - evaluation_start_time
        win_percentage = wins / num_games * 100
        results.append((name, wins, num_games, win_percentage))
        print(f"  {name:20s}: {wins}/{num_games} = {win_percentage:.0f}%  ({elapsed:.0f}s)")

    print(f"\n{'='*60}")
    print("Summary:")
    for name, wins, total, win_percentage in results:
        bar = "#" * int(win_percentage / 5)
        print(f"  {name:20s}: {win_percentage:5.0f}% {bar}")


if __name__ == "__main__":
    main()
