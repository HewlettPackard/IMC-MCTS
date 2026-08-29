#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Normalized Search Guidance Gain (SGG) metric for cross-domain NN evaluation.

                  P_nn - P_rand
SGG(game) = ─────────────────────────────
              log2(N) * sqrt(B) / K

Where:
    P_nn   : NN-MCTS performance   (H2H win rate for 2P; avg_score for 1P)
    P_rand : Random-MCTS baseline  (0.50 for 2P H2H; measured avg_score for 1P)
    N      : MCTS iteration count
    B      : effective playing-area cells
    K      : reference constant = log2(50) * sqrt(64) ~ 45.15,
             chosen so SGG == raw_lift for a 50-iteration, 64-cell game.

Verdict bands:
    SGG > +0.05            GREEN   NN helps meaningfully
    -0.05 <= SGG <= +0.05  YELLOW  marginal / noise
    SGG < -0.05            RED     NN hurts

The 1P-vs-2P difference lives entirely in how P_nn and P_rand are measured
(win rate vs average score); the normalization below is player-count agnostic.
Run this file directly to see worked examples and the reference-point check.
"""

import math

# Effective playing-area cells per game (accounts for hex masks, active regions).
EFFECTIVE_CELLS = {
    "go": 81,               # 9x9 full board
    "hex": 121,             # 11x11 full board
    "gomoku": 225,          # 15x15 full board
    "havannah": 169,        # 15x15 grid, 169 valid hex cells (base 8)
    "othello": 64,          # 8x8 full board
    "connect_four": 42,     # 7x6 active (6 rows x 7 cols)
    "pente": 361,           # 19x19 full board
    "breakthrough": 64,     # 8x8 full board
    "protein_folding": 169, # 13x13 full board
    "nonograms": 81,        # 9x9 full board
    "frozen_lake": 64,      # 8x8 full board
    "minigrid": 64,         # 8x8 full board
    "minesweeper": 81,      # 9x9 full board
}
DEFAULT_CELLS = 64          # fallback for a game not listed above

# Reference constant K = log2(50) * sqrt(64) ~ 45.15
K_REF = math.log2(50) * math.sqrt(64)

# Verdict thresholds on SGG.
SGG_GREEN_THRESHOLD = 0.05
SGG_RED_THRESHOLD = -0.05


def compute_sgg(game_key, nn_perf, rand_perf, iterations, num_players):
    """Compute the Search Guidance Gain for one game.

    game_key    : game name; looked up in EFFECTIVE_CELLS (falls back to 64).
    nn_perf     : NN-MCTS performance   (2P: H2H win rate; 1P: avg_score).
    rand_perf   : Random-MCTS baseline  (2P: 0.50; 1P: measured avg_score).
    iterations  : MCTS iteration count N.
    num_players : 1 or 2. Validated here only -- the 1P/2P measurement choice
                  is already baked into nn_perf / rand_perf by the caller.

    Returns a dict: raw_lift, log2_N, sqrt_B, K, denominator, sgg, verdict,
    effective_cells.
    """
    if num_players not in (1, 2):
        raise ValueError("num_players must be 1 or 2")

    # Effective board size B. Unknown games fall back to the 64-cell reference.
    if game_key in EFFECTIVE_CELLS:
        B = EFFECTIVE_CELLS[game_key]
    else:
        B = DEFAULT_CELLS

    N = max(iterations, 2)  # keep log2(N) defined for tiny iteration counts

    # SGG = (P_nn - P_rand) / (log2(N) * sqrt(B) / K).
    raw_lift = nn_perf - rand_perf
    log2_N = math.log2(N)
    sqrt_B = math.sqrt(B)
    denominator = log2_N * sqrt_B / K_REF

    if denominator == 0:
        sgg = 0.0
    else:
        sgg = raw_lift / denominator

    if sgg > SGG_GREEN_THRESHOLD:
        verdict = "GREEN"
    elif sgg < SGG_RED_THRESHOLD:
        verdict = "RED"
    else:
        verdict = "YELLOW"

    return {
        "raw_lift": round(raw_lift, 4),
        "log2_N": round(log2_N, 4),
        "sqrt_B": round(sqrt_B, 4),
        "K": round(K_REF, 4),
        "denominator": round(denominator, 4),
        "sgg": round(sgg, 4),
        "verdict": verdict,
        "effective_cells": B,
    }


if __name__ == "__main__":
    # Reference-point check: a 50-iteration, 64-cell game has denominator == 1,
    # so SGG must equal the raw lift exactly. This is what K_REF is chosen for.
    ref = compute_sgg("othello", nn_perf=0.80, rand_perf=0.50,
                      iterations=50, num_players=2)
    assert abs(ref["denominator"] - 1.0) < 1e-9, ref["denominator"]
    assert abs(ref["sgg"] - ref["raw_lift"]) < 1e-9, ref
    print(f"reference point OK: denominator={ref['denominator']}, "
          f"sgg == raw_lift == {ref['sgg']}")
    print()

    # Worked examples (illustrative inputs; they reproduce the reported SGG values).
    # game_key, nn_perf, rand_perf, iterations, num_players
    examples = [
        ("minigrid",        0.967, 0.405, 50, 1),  # navigation, 8x8
        ("protein_folding", 1.000, 0.685, 50, 1),  # HP folding, 13x13
        ("go",              0.600, 0.500, 50, 2),  # 9x9 H2H
        ("minesweeper",     0.933, 0.789, 80, 1),  # 9x9 puzzles
    ]

    header = f"{'game':<16}{'raw_lift':>10}{'denom':>8}{'SGG':>9}  verdict"
    print(header)
    print("-" * len(header))
    for game_key, nn_perf, rand_perf, iters, players in examples:
        r = compute_sgg(game_key, nn_perf, rand_perf, iters, players)
        print(f"{game_key:<16}{r['raw_lift']:>+10.4f}{r['denominator']:>8.3f}"
              f"{r['sgg']:>+9.4f}  {r['verdict']}")
