# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
IMC-MCTS[high acc NN] vs IMC-MCTS[low acc NN] match.
Uses the C engine for speed.
"""

import ctypes as ct
import os
import numpy as np
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_PATH = os.path.join(_PROJECT_ROOT, 'engine', 'imc_mcts.so')
BOARD_SIZE = 9
NUM_CELLS = 81
PASS_MOVE = 81
MAX_MOVES = 200

# Load two separate copies of the library — can't have two weight sets in one instance.
# Instead, use mcts_search directly with board state, loading weights between searches.
# Actually easier: just load the lib once and swap weights per move.

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
lib.get_legal_moves.argtypes = [ct.POINTER(ct.c_int8), ct.c_int8, ct.c_uint64, ct.POINTER(ct.c_int)]
lib.get_legal_moves.restype = ct.c_int


def board_hash_fnv(board):
    board_hash = 14695981039346656037
    for value in board.ravel():
        board_hash ^= int(value) & 0xFF
        board_hash = (board_hash * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return board_hash


def score_position(board, komi=6.5):
    """Chinese area scoring. Returns (black_score, white_score)."""
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


def play_game(weights_black, weights_white, iters_black, iters_white, game_id):
    """Play one game. Returns ('B','W', or 'D'), black_score, white_score."""
    board = np.zeros(NUM_CELLS, dtype=np.int8)
    new_board = (ct.c_int8 * NUM_CELLS)()
    current_player = 1  # Black first
    consecutive_passes = 0
    move_count = 0
    ko_hash = 0

    while move_count < MAX_MOVES:
        if consecutive_passes >= 2:
            break

        # Select the active model and search budget for this color.
        if current_player == 1:
            active_weights, active_iterations = weights_black, iters_black
        else:
            active_weights, active_iterations = weights_white, iters_white
        lib.load_weights(active_weights)

        board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
        move = lib.mcts_search(
            board_ptr, ct.c_int8(current_player),
            ct.c_int(consecutive_passes), ct.c_int(move_count),
            ct.c_uint64(ko_hash), ct.c_int(active_iterations), ct.c_double(0.7)
        )

        if move == PASS_MOVE:
            consecutive_passes += 1
        else:
            consecutive_passes = 0
            ko_hash = board_hash_fnv(board)
            lib.apply_move_c(board_ptr, ct.c_int(move), ct.c_int8(current_player), new_board)
            board = np.frombuffer(new_board, dtype=np.int8).copy()

        current_player = -current_player
        move_count += 1

    board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
    black_score, white_score = score_position(board_2d)
    if black_score > white_score:
        winner = 'B'
    elif white_score > black_score:
        winner = 'W'
    else:
        winner = 'D'

    return winner, black_score, white_score, move_count


def main():
    weights_high = b'weights/regression_163/weights.bin'
    weights_low = b'weights/regression_163/weights.bin'

    iters_high = 200
    iters_low = 50
    num_games = 20

    print(f"IMC-MCTS Match: 163-feature regression (200 iter) vs (50 iter)")
    print(f"Games: {num_games} (alternating colors)")
    print(f"{'='*65}")

    high_wins = 0
    low_wins = 0
    draws = 0
    results = []

    tournament_start_time = time.time()

    for game_index in range(num_games):
        # Alternate colors: even games High=Black, odd games High=White
        if game_index % 2 == 0:
            black_weights, white_weights = weights_high, weights_low
            black_iterations, white_iterations = iters_high, iters_low
            high_color = 'B'
        else:
            black_weights, white_weights = weights_low, weights_high
            black_iterations, white_iterations = iters_low, iters_high
            high_color = 'W'

        game_start_time = time.time()
        winner, black_score, white_score, moves = play_game(
            black_weights,
            white_weights,
            black_iterations,
            white_iterations,
            game_index + 1
        )
        game_end_time = time.time()

        # Determine if high or low won
        if winner == 'D':
            draws += 1
            result_str = "Draw"
        elif winner == high_color:
            high_wins += 1
            result_str = "High wins"
        else:
            low_wins += 1
            result_str = "Low wins"

        results.append((winner, high_color, black_score, white_score))
        print(f"Game {game_index+1:2d}: High={high_color} | Winner={winner} | "
              f"B={black_score:.1f} W={white_score:.1f} | {moves} moves | "
              f"{game_end_time-game_start_time:.1f}s | {result_str}")

    elapsed = time.time() - tournament_start_time

    print(f"{'='*65}")
    print(f"Results: High {high_wins} - {draws} - {low_wins} Low")
    print(f"High win rate: {high_wins}/{num_games} ({high_wins/num_games*100:.0f}%)")
    print(f"Total time: {elapsed:.1f}s ({elapsed/num_games:.1f}s per game)")

    # Breakdown by color
    high_as_black = sum(
        1 for winner, high_color, _, _ in results
        if high_color == 'B' and winner == 'B'
    )
    high_as_white = sum(
        1 for winner, high_color, _, _ in results
        if high_color == 'W' and winner == 'W'
    )
    games_as_black = sum(1 for _, high_color, _, _ in results if high_color == 'B')
    games_as_white = sum(1 for _, high_color, _, _ in results if high_color == 'W')
    print(f"High as Black: {high_as_black}/{games_as_black} | "
          f"High as White: {high_as_white}/{games_as_white}")


if __name__ == '__main__':
    main()
