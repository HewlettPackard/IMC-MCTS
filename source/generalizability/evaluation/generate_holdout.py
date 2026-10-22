# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Generate held-out 9x9 Go position sets for the noise-sweep experiment.

Produces two .npz files in generalizability/data/ (where run_noise_sweep.py reads them):
  - 9x9_mid_positions.npz       — mid-game boards for panel b (move-agreement)
  - 9x9_terminal_positions.npz  — terminal boards + outcomes for panel c (NN accuracy)

Run once; the result is deterministic given the seed.

Usage:
    python generalizability/evaluation/generate_holdout.py
    python generalizability/evaluation/generate_holdout.py --out-dir /tmp/holdout_check
"""

import argparse
import os
import random

import numpy as np

from generalizability.games import GAME_REGISTRY

GO = GAME_REGISTRY["go"]
# Held-out sets live in generalizability/data/ (two levels up from this file).
DEFAULT_OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

SEED = 20260515
N_GAMES = 60               # number of self-play games to mine
MID_MOVE_RANGE = (20, 50)  # sample mid-game snapshots from this move window
MAX_MOVES = 200            # cap each self-play game length


def _self_play(seed):
    """Random self-play. Yields (board_snapshot, move_idx) per move and the
    final terminal board + result."""
    rng = random.Random(seed)
    b = GO.initial_state()
    p = 1
    snapshots = []
    for move_idx in range(MAX_MOVES):
        if GO.is_terminal(b):
            break
        moves = GO.get_legal_moves(b, p)
        if not moves:
            break
        snapshots.append((b.copy(), move_idx))
        b = GO.apply_move(b, rng.choice(moves), p)
        p = 3 - p
    result_p1 = GO.get_result(b, 1)
    return snapshots, b.copy(), result_p1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=str, default=DEFAULT_OUT_DIR,
                    help="Where to write the .npz files (default: generalizability/data/)")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    rng = random.Random(SEED)
    mid_boards = []
    term_boards = []
    term_results = []  # P1 perspective: 1.0 win / 0.5 draw / 0.0 loss

    for g in range(N_GAMES):
        snaps, term_b, res = _self_play(rng.randint(0, 2**31 - 1))
        # Mid-game: take all snapshots in the [20, 50) move window.
        for board, idx in snaps:
            if MID_MOVE_RANGE[0] <= idx < MID_MOVE_RANGE[1]:
                mid_boards.append(board)
        # Terminal: keep the final board + result if the game actually ended.
        if GO.is_terminal(term_b):
            term_boards.append(term_b)
            term_results.append(res)

    mid_arr = np.stack(mid_boards, axis=0) if mid_boards else np.empty((0, 11, 9), dtype=np.int16)
    term_arr = np.stack(term_boards, axis=0) if term_boards else np.empty((0, 11, 9), dtype=np.int16)
    res_arr = np.array(term_results, dtype=np.float32)

    mid_path = os.path.join(args.out_dir, "9x9_mid_positions.npz")
    term_path = os.path.join(args.out_dir, "9x9_terminal_positions.npz")
    np.savez(mid_path, boards=mid_arr)
    np.savez(term_path, boards=term_arr, results=res_arr)

    p1_wins = int((res_arr == 1.0).sum())
    p2_wins = int((res_arr == 0.0).sum())
    draws = int((res_arr == 0.5).sum())
    print(f"Mid-game positions: {len(mid_arr)} -> {mid_path}")
    print(f"Terminal positions: {len(term_arr)} -> {term_path}")
    print(f"  outcomes: P1={p1_wins}  P2={p2_wins}  draws={draws}")


if __name__ == "__main__":
    main()
