#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
GTP Tournament: IMC-MCTS vs external Go engines.

Supports any GTP-compatible engine (GnuGo, Pachi) and
our C-based IMC-MCTS engine via ctypes.
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
from paths import GNUGO_BIN, PACHI_BIN

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


class GTPEngine:
    """Wrapper for an external GTP engine process."""

    def __init__(self, name, cmd, cwd=None):
        self.name = name
        self.cmd = cmd
        self.cwd = cwd
        self.process = None

    def start(self):
        self.process = subprocess.Popen(
            self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True, bufsize=1,
            cwd=self.cwd,
        )
        self._send("boardsize 9")
        self._send("clear_board")
        self._send("komi 6.5")

    def _send(self, command):
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
        response_lines = []
        first_line = True
        while True:
            line = self.process.stdout.readline()
            if not line:
                break
            line = line.rstrip('\n\r')
            if line.strip() == '' and not first_line:
                break
            if first_line:
                first_line = False
                if line.startswith("?"):
                    return "error"
                if line.startswith("="):
                    content = line[1:].strip()
                    if content:
                        response_lines.append(content)
                    continue
            response_lines.append(line.strip())
        return "\n".join(response_lines)

    def new_game(self):
        self._send("clear_board")

    def play(self, color, gtp_move):
        self._send(f"play {color} {gtp_move}")

    def genmove(self, color):
        response = self._send(f"genmove {color}")
        return response.strip().split()[0] if response.strip() else "pass"

    def stop(self):
        if self.process:
            try:
                self._send("quit")
                self.process.terminate()
            except Exception:
                pass


class IMCEngine:
    """Our IMC-MCTS C engine wrapper (GTP-like interface)."""

    def __init__(self, name, weights_path, iterations, exploration_c=0.7):
        self.name = name
        self.weights_path = weights_path
        self.iterations = iterations
        self.exploration_c = exploration_c
        self.new_board_buf = (ct.c_int8 * NUM_CELLS)()

    def start(self):
        load_status = lib.load_weights(self.weights_path)
        if load_status != 0:
            raise RuntimeError(f"Failed to load weights: {self.weights_path}")
        self.new_game()

    def new_game(self):
        self.board = np.zeros(NUM_CELLS, dtype=np.int8)
        self.consecutive_passes = 0
        self.move_count = 0
        self.ko_hash = 0

    def _apply(self, move_int, player_int):
        if move_int == PASS_MOVE:
            self.consecutive_passes += 1
        else:
            self.consecutive_passes = 0
            self.ko_hash = board_hash_fnv(self.board)
            board_ptr = self.board.ctypes.data_as(ct.POINTER(ct.c_int8))
            lib.apply_move_c(board_ptr, ct.c_int(move_int), ct.c_int8(player_int), self.new_board_buf)
            self.board = np.frombuffer(self.new_board_buf, dtype=np.int8).copy()
        self.move_count += 1

    def play(self, color, gtp_move):
        current_player = 1 if color.lower() in ("b", "black") else -1
        self._apply(gtp_to_move(gtp_move), current_player)

    def genmove(self, color):
        current_player = 1 if color.lower() in ("b", "black") else -1
        lib.load_weights(self.weights_path)
        board_ptr = self.board.ctypes.data_as(ct.POINTER(ct.c_int8))
        move = lib.mcts_search(
            board_ptr, ct.c_int8(current_player),
            ct.c_int(self.consecutive_passes), ct.c_int(self.move_count),
            ct.c_uint64(self.ko_hash), ct.c_int(self.iterations), ct.c_double(self.exploration_c)
        )
        gtp_move = move_to_gtp(move)
        self._apply(move, current_player)
        return gtp_move

    def stop(self):
        pass


def play_one_game(black_engine, white_engine, game_id=0, verbose=False):
    """Play one game. Returns (winner_char, b_score, w_score, num_moves, resigned)."""
    black_engine.new_game()
    white_engine.new_game()

    board = np.zeros(NUM_CELLS, dtype=np.int8)
    new_board_buf = (ct.c_int8 * NUM_CELLS)()
    consecutive_passes = 0
    move_count = 0
    resigned = False

    while move_count < MAX_MOVES and consecutive_passes < 2:
        # Current player
        if move_count % 2 == 0:
            color_str = "black"
            player_int = 1
            current_engine = black_engine
            opponent_engine = white_engine
        else:
            color_str = "white"
            player_int = -1
            current_engine = white_engine
            opponent_engine = black_engine

        gtp_move = current_engine.genmove(color_str)
        gtp_upper = gtp_move.upper()

        if gtp_upper == "RESIGN":
            resigned = True
            break

        # Keep the opponent synchronized with the selected move.
        opponent_engine.play(color_str, gtp_move)

        # Update our tracking board
        move_int = gtp_to_move(gtp_move)
        if move_int == PASS_MOVE:
            consecutive_passes += 1
        else:
            consecutive_passes = 0
            board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
            lib.apply_move_c(board_ptr, ct.c_int(move_int), ct.c_int8(player_int), new_board_buf)
            board = np.frombuffer(new_board_buf, dtype=np.int8).copy()

        move_count += 1

    board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
    black_score, white_score = score_position(board_2d)

    if resigned:
        # The engine whose turn it was resigned
        winner = "W" if move_count % 2 == 0 else "B"
    elif black_score > white_score:
        winner = "B"
    elif white_score > black_score:
        winner = "W"
    else:
        winner = "D"

    return winner, black_score, white_score, move_count, resigned


def run_matchup(engine_a_factory, engine_b_factory, num_games=10):
    """Run a matchup with color alternation. Returns (a_wins, b_wins, draws)."""
    engine_a = engine_a_factory()
    engine_b = engine_b_factory()
    engine_a.start()
    engine_b.start()

    a_wins, b_wins, draws = 0, 0, 0

    for game_index in range(num_games):
        # Alternate: even games A=Black, odd games A=White
        if game_index % 2 == 0:
            black_engine, white_engine = engine_a, engine_b
            a_color = "B"
        else:
            black_engine, white_engine = engine_b, engine_a
            a_color = "W"

        game_start_time = time.time()
        winner, black_score, white_score, moves, resigned = play_one_game(
            black_engine,
            white_engine,
            game_index
        )
        elapsed = time.time() - game_start_time

        if winner == "D":
            draws += 1
            result = "Draw"
        elif winner == a_color:
            a_wins += 1
            result = f"{engine_a.name} wins"
        else:
            b_wins += 1
            result = f"{engine_b.name} wins"

        resignation_suffix = "R" if resigned else ""
        print(f"  Game {game_index+1:2d}: {engine_a.name}={a_color} | Winner={winner}{resignation_suffix} | "
              f"B={black_score:.1f} W={white_score:.1f} | {moves} moves | {elapsed:.1f}s | {result}")

    engine_a.stop()
    engine_b.stop()
    return a_wins, b_wins, draws


def main():
    GNUGO = GNUGO_BIN
    PACHI = PACHI_BIN

    W_STRONG = b"weights/final/strong.bin"
    W_MID = b"weights/final/mid.bin"
    W_WEAK = b"weights/final/weak.bin"

    num_games = 20

    engines = {
        "GnuGo-L1":     lambda: GTPEngine("GnuGo-L1",  [GNUGO, "--mode", "gtp", "--level", "1"]),
        "GnuGo-L10":    lambda: GTPEngine("GnuGo-L10", [GNUGO, "--mode", "gtp", "--level", "10"]),
        "Pachi-1k":     lambda: GTPEngine("Pachi-1k",   [PACHI, "-e", "montecarlo", "-t", "=1000"], cwd=PACHI_DIR),
        "IMC-Strong":   lambda: IMCEngine("IMC-Strong", W_STRONG, 500),
        "IMC-Mid":      lambda: IMCEngine("IMC-Mid",    W_MID,    500),
        "IMC-Weak":     lambda: IMCEngine("IMC-Weak",   W_WEAK,   500),
    }

    matchups = [
        # Internal tier ordering
        ("IMC-Strong", "IMC-Mid"),
        ("IMC-Strong", "IMC-Weak"),
        ("IMC-Mid",    "IMC-Weak"),
        # All tiers vs GnuGo L1
        ("IMC-Strong", "GnuGo-L1"),
        ("IMC-Mid",    "GnuGo-L1"),
        ("IMC-Weak",   "GnuGo-L1"),
        # Strong vs GnuGo L10
        ("IMC-Strong", "GnuGo-L10"),
    ]

    print(f"{'='*70}")
    print(f"  IMC-MCTS Tournament (9x9 Go, Chinese rules, komi 6.5)")
    print(f"  Strong=v6-iter5, Mid=v1-iter1, Weak=supervised (iterative self-play)")
    print(f"  Games per matchup: {num_games} (alternating colors)")
    print(f"{'='*70}")

    all_results = {}

    for name_a, name_b in matchups:
        print(f"\n--- {name_a} vs {name_b} ---")
        matchup_start_time = time.time()
        wins_a, wins_b, draws = run_matchup(engines[name_a], engines[name_b], num_games)
        elapsed = time.time() - matchup_start_time
        print(f"  >> {name_a} {wins_a}-{draws}-{wins_b} {name_b}  ({elapsed:.1f}s total)")
        all_results[(name_a, name_b)] = (wins_a, wins_b, draws)

    print(f"\n{'='*70}")
    print("  RESULTS SUMMARY")
    print(f"{'='*70}")
    for (name_a, name_b), (wins_a, wins_b, draws) in all_results.items():
        total_games = wins_a + wins_b + draws
        win_percentage_a = wins_a / total_games * 100 if total_games > 0 else 0
        print(f"  {name_a:12s} vs {name_b:12s} : {wins_a:2d}-{draws}-{wins_b:2d}  ({win_percentage_a:.0f}%)")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
