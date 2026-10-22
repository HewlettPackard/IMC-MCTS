# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Conductance-noise sweep on 9x9 Go.

Runs 4 sigma values x 3 seeds = 12 conditions. For each:
  - Win-rate: NN-MCTS (noisy) vs random-rollout MCTS, head-to-head.
  - 1-ply move-agreement: fraction of held-out mid-game positions where the
    noisy NN's preferred move (argmax 1-ply NN value) matches the sigma=0 NN's.
  - Terminal accuracy: argmax(NN output) vs known terminal outcome.

Output: generalizability/results/noise_sweep_9x9.csv  (override with --output;
the paper figure reads paper/results/noise_sweep_9x9.csv).

Usage:
    python generalizability/sweeps/run_noise_sweep.py                # full run
    python generalizability/sweeps/run_noise_sweep.py --smoke        # 2 games, 1 seed, 2 sigma
    python generalizability/sweeps/run_noise_sweep.py --games 50     # override
"""

import argparse
import csv
import os
import random
import time

import numpy as np

from generalizability.games import GAME_REGISTRY
from core.algorithm.mcts_engine import MCTSEngine
from generalizability.evaluation.noisy_eval import NoisyCrossbarEval

GO = GAME_REGISTRY["go"]

# Held-out boards live in generalizability/data/; results go one level up from
# sweeps/ into generalizability/results/.
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
OUT_CSV = os.path.join(OUT_DIR, "noise_sweep_9x9.csv")


def play_one(p1_engine, p2_engine, max_moves=200):
    """Play a single game. Returns P1's result (1.0 win / 0.5 draw / 0.0 loss)."""
    b = GO.initial_state()
    p = 1
    for _ in range(max_moves):
        if GO.is_terminal(b):
            break
        engine = p1_engine if p == 1 else p2_engine
        move = engine.search(b, p)
        b = GO.apply_move(b, move, p)
        p = 3 - p
    return GO.get_result(b, 1)


def head_to_head(nn_eval, n_games, iterations, game_seed_base):
    """NN-MCTS vs random-rollout MCTS, alternating colors.

    To control variance, we fix the Python/numpy global RNG per game so each
    (sigma, seed) condition explores the SAME game tree under the SAME random
    rollouts. The only thing that varies across conditions is the NN weights.
    """
    nn_engine = MCTSEngine(GO, iterations=iterations, eval_fn=nn_eval)
    rand_engine = MCTSEngine(GO, iterations=iterations)

    wins = draws = losses = 0
    for g in range(n_games):
        random.seed(game_seed_base + g)
        np.random.seed(game_seed_base + g)
        nn_is_p1 = (g % 2 == 0)
        if nn_is_p1:
            res = play_one(nn_engine, rand_engine)        # res = P1 result = NN result
        else:
            res = 1.0 - play_one(rand_engine, nn_engine)  # flip: NN was P2
        if res >= 0.9:
            wins += 1
        elif res <= 0.1:
            losses += 1
        else:
            draws += 1
    return {
        "wins": wins, "draws": draws, "losses": losses,
        "winrate": (wins + 0.5 * draws) / n_games,
    }


def _value_after_move(eval_fn, board, move, mover):
    """One-ply value: after `mover` plays `move`, return eval from opponent's POV.
    A move is 'good' for `mover` if the opponent's value after the move is LOW
    (= mover's value is HIGH). We return the eval directly; caller picks argmin
    if mover=P1 maximizing, argmax if mover=P2 maximizing-from-P2-POV."""
    new_board = GO.apply_move(board, move, mover)
    if GO.is_terminal(new_board):
        return GO.get_result(new_board, 1)
    return eval_fn(new_board, 3 - mover)


def _best_move(eval_fn, board, mover):
    """1-ply lookahead: mover picks the move that maximizes its own value.
    eval_fn returns P1-perspective value; P1 maximizes, P2 minimizes."""
    moves = GO.get_legal_moves(board, mover)
    if not moves:
        return None
    vals = [_value_after_move(eval_fn, board, m, mover) for m in moves]
    if mover == 1:
        return moves[int(np.argmax(vals))]
    return moves[int(np.argmin(vals))]


def move_agreement(noisy, baseline, positions):
    """Fraction of held-out positions where noisy NN's 1-ply preferred move
    matches the sigma=0 baseline's. Player-to-move alternates by stone count."""
    if len(positions) == 0:
        return 0.0
    agree = 0
    n = 0
    for b in positions:
        # Player to move: P1 if equal counts (or initial), P2 if P1 ahead by one.
        play = b[:9]
        p1_count = int((play == 1).sum())
        p2_count = int((play == 2).sum())
        mover = 1 if p1_count <= p2_count else 2
        m_noisy = _best_move(noisy, b, mover)
        m_base = _best_move(baseline, b, mover)
        if m_noisy is None or m_base is None:
            continue
        n += 1
        if m_noisy == m_base:
            agree += 1
    return agree / n if n else 0.0


def terminal_accuracy(eval_fn, positions, results):
    """For each terminal board with known outcome, argmax(softmax) vs truth.

    Truth label (P1=Black perspective): 1.0 -> class 2 (Black-win), 0.5 -> class 1
    (draw), 0.0 -> class 0 (White-win). Also returns value-MSE which is
    invariant to label-distribution skew.
    """
    if len(positions) == 0:
        return {"acc": 0.0, "balanced_acc": 0.0, "value_mse": 0.0}
    truth_class = []
    pred_class = []
    pred_val = []
    for b, r in zip(positions, results):
        if r >= 0.9:
            tc = 2
        elif r <= 0.1:
            tc = 0
        else:
            tc = 1
        truth_class.append(tc)
        probs = eval_fn.raw_probs(b)
        pred_class.append(int(np.argmax(probs)))
        pred_val.append(eval_fn(b, 1))
    truth_class = np.array(truth_class)
    pred_class = np.array(pred_class)
    pred_val = np.array(pred_val)
    acc = float((truth_class == pred_class).mean())
    # Balanced accuracy across observed classes.
    bal_parts = []
    for c in np.unique(truth_class):
        mask = truth_class == c
        bal_parts.append(float((pred_class[mask] == c).mean()))
    balanced_acc = float(np.mean(bal_parts)) if bal_parts else 0.0
    value_mse = float(((pred_val - results) ** 2).mean())
    return {"acc": acc, "balanced_acc": balanced_acc, "value_mse": value_mse}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sigmas", nargs="*", type=float,
                    default=[0.00, 0.02, 0.05, 0.10])
    ap.add_argument("--seeds", nargs="*", type=int, default=[1, 2, 3])
    ap.add_argument("--games", type=int, default=30)
    ap.add_argument("--iterations", type=int, default=1000)
    ap.add_argument("--mid-subsample", type=int, default=200,
                    help="Random subsample of mid-game positions for panel b")
    ap.add_argument("--smoke", action="store_true",
                    help="Quick smoke test: 2 games x 1 seed x 2 sigma")
    ap.add_argument("--output", type=str, default=OUT_CSV)
    args = ap.parse_args()

    if args.smoke:
        args.sigmas = [0.0, 0.10]
        args.seeds = [1]
        args.games = 2
        args.iterations = 200
        args.mid_subsample = 30

    # Load the held-out sets: mid-game boards (panel b) and terminal boards with
    # known outcomes (panel c). Subsample mid for speed.
    mid_path = os.path.join(DATA_DIR, "9x9_mid_positions.npz")
    term_path = os.path.join(DATA_DIR, "9x9_terminal_positions.npz")
    mid = np.load(mid_path)["boards"]
    term = np.load(term_path)
    term_boards, term_results = term["boards"], term["results"]
    if len(mid) > args.mid_subsample:
        rng = np.random.RandomState(0)
        idx = rng.choice(len(mid), size=args.mid_subsample, replace=False)
        mid = mid[idx]

    print(f"Held-out: {len(mid)} mid + {len(term_boards)} terminal positions")
    print(f"Sweep: sigma={args.sigmas}, seeds={args.seeds}, "
          f"{args.games} games x {args.iterations} iter")

    # Baseline (sigma=0) is the reference the noisy runs are compared against in
    # the move-agreement panel.
    baseline = NoisyCrossbarEval("go", noise_sigma=0.0)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    rows = []
    t_start = time.time()
    for sigma in args.sigmas:
        for seed in args.seeds:
            t0 = time.time()
            noisy = NoisyCrossbarEval("go", noise_sigma=sigma, noise_seed=seed)
            # Win-rate uses a per-(sigma, seed) game-seed offset so games are
            # comparable across conditions (same opponent move randomness).
            hh = head_to_head(noisy, args.games, args.iterations,
                              game_seed_base=10_000 * seed)
            agree = move_agreement(noisy, baseline, mid)
            acc = terminal_accuracy(noisy, term_boards, term_results)
            dt = time.time() - t0
            row = {
                "sigma": sigma, "seed": seed,
                "wins": hh["wins"], "draws": hh["draws"], "losses": hh["losses"],
                "winrate": hh["winrate"],
                "move_agreement": agree,
                "term_acc": acc["acc"],
                "term_balanced_acc": acc["balanced_acc"],
                "term_value_mse": acc["value_mse"],
                "n_games": args.games,
                "n_iter": args.iterations,
                "n_mid": int(len(mid)),
                "n_term": int(len(term_boards)),
                "elapsed_s": round(dt, 2),
            }
            rows.append(row)
            print(f"sigma={sigma:.2f} seed={seed}: "
                  f"winrate={hh['winrate']:.3f} ({hh['wins']}-{hh['draws']}-{hh['losses']})  "
                  f"agree={agree:.3f}  term_bal_acc={acc['balanced_acc']:.3f}  "
                  f"mse={acc['value_mse']:.3f}  ({dt:.0f}s)")

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} rows -> {args.output}")
    print(f"Total wall-clock: {(time.time() - t_start) / 60:.1f} min")


if __name__ == "__main__":
    main()
