#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Quick probe: IMC-MCTS (strong/mid/weak) vs GnuGo (L1/L5/L10), 10 games each."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training.selfplay_iterative import load_engine, eval_vs_gnugo
from paths import GNUGO_BIN as GNUGO
import time
import json

WEIGHTS = {
    "IMC-strong": "weights/final/strong.bin",
    "IMC-mid":    "weights/final/mid.bin",
    "IMC-weak":   "weights/final/weak.bin",
}
GNUGO_LEVELS = [1, 5, 10]
NUM_GAMES = 10
MCTS_ITERS = 500

def main():
    lib = load_engine()
    results = []

    total_probes = len(WEIGHTS) * len(GNUGO_LEVELS)
    completed_probes = 0

    for weight_name, weight_path in WEIGHTS.items():
        for level in GNUGO_LEVELS:
            completed_probes += 1
            print(f"\n{'='*60}")
            print(f"[{completed_probes}/{total_probes}] {weight_name} vs GnuGo-L{level}  ({NUM_GAMES} games, {MCTS_ITERS} sims)")
            print(f"{'='*60}")

            probe_start_time = time.time()
            wins, total_games = eval_vs_gnugo(
                lib, GNUGO, level,
                os.path.abspath(weight_path).encode(),
                NUM_GAMES, MCTS_ITERS
            )
            elapsed = time.time() - probe_start_time
            win_percentage = wins / total_games * 100

            result = {
                "imc": weight_name,
                "opponent": f"GnuGo-L{level}",
                "wins": wins,
                "losses": total_games - wins,
                "total": total_games,
                "win_pct": win_percentage,
                "time_s": round(elapsed, 1),
            }
            results.append(result)
            print(f"  => {weight_name} {wins}/{total_games} ({win_percentage:.0f}%) in {elapsed:.0f}s")

    # Print summary
    print(f"\n{'='*60}")
    print(f"PROBE RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"{'Matchup':<35} {'W-L':>8} {'Win%':>8}")
    print(f"{'-'*55}")
    for result in results:
        matchup = f"{result['imc']} vs {result['opponent']}"
        win_loss = f"{result['wins']}-{result['losses']}"
        print(f"{matchup:<35} {win_loss:>8} {result['win_pct']:>7.0f}%")

    with open("probe_results.json", "w") as output_handle:
        json.dump(results, output_handle, indent=2)
    print(f"\nSaved to probe_results.json")

if __name__ == "__main__":
    main()
