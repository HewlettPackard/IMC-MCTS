#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Probe: different weight versions vs GnuGo L10, 30 games each."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from training.selfplay_iterative import load_engine, eval_vs_gnugo
from paths import GNUGO_BIN as GNUGO
import time
import json

GNUGO_LEVEL = 10
NUM_GAMES = 30
MCTS_ITERS = 500

CANDIDATES = [
    ("final/strong",         "weights/final/strong.bin"),
    ("v6/best",              "weights/iterative_v6/best_model.bin"),
    ("v6/iter10",            "weights/iterative_v6/iter10.bin"),
    ("v1/iter1 (early SP)",  "weights/iterative/iter1.bin"),
    ("supervised-80%",       "weights/80pct/weights.bin"),
    ("supervised-60%",       "weights/60pct/weights.bin"),
]

def main():
    lib = load_engine()
    results = []

    for candidate_index, (name, path) in enumerate(CANDIDATES, 1):
        absolute_path = os.path.abspath(path)
        if not os.path.exists(absolute_path):
            print(f"[{candidate_index}/{len(CANDIDATES)}] SKIP {name}: {path} not found", flush=True)
            continue

        print(f"\n{'='*60}", flush=True)
        print(f"[{candidate_index}/{len(CANDIDATES)}] {name} vs GnuGo-L{GNUGO_LEVEL}  ({NUM_GAMES} games, {MCTS_ITERS} sims)", flush=True)
        print(f"{'='*60}", flush=True)

        probe_start_time = time.time()
        wins, total = eval_vs_gnugo(
            lib, GNUGO, GNUGO_LEVEL,
            absolute_path.encode(), NUM_GAMES, MCTS_ITERS
        )
        elapsed = time.time() - probe_start_time
        win_percentage = wins / total * 100

        result = {
            "name": name, "path": path,
            "wins": wins, "losses": total - wins,
            "total": total, "win_pct": win_percentage,
            "time_s": round(elapsed, 1),
        }
        results.append(result)
        print(f"  => {name}: {wins}/{total} ({win_percentage:.0f}%) in {elapsed:.0f}s", flush=True)

    print(f"\n{'='*60}", flush=True)
    print(f"WEIGHT COMPARISON vs GnuGo-L{GNUGO_LEVEL} ({NUM_GAMES} games, {MCTS_ITERS} sims)", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"{'Model':<25} {'W-L':>8} {'Win%':>8}", flush=True)
    print(f"{'-'*45}", flush=True)
    for result in sorted(results, key=lambda result: -result['win_pct']):
        win_loss = f"{result['wins']}-{result['losses']}"
        print(f"{result['name']:<25} {win_loss:>8} {result['win_pct']:>7.0f}%", flush=True)

    with open("probe_weights_results.json", "w") as output_handle:
        json.dump(results, output_handle, indent=2)
    print(f"\nSaved to probe_weights_results.json", flush=True)

if __name__ == "__main__":
    main()
