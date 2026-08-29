#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Probe: IMC-MCTS at 200/500/2000 sims vs GnuGo L10, 50 games each."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from training.selfplay_iterative import load_engine, eval_vs_gnugo
from paths import GNUGO_BIN as GNUGO
import time
import json

WEIGHTS = os.path.abspath("weights/final/strong.bin")
SIM_COUNTS = [200, 500, 2000]
GNUGO_LEVEL = 10
NUM_GAMES = 50

def main():
    lib = load_engine()
    results = []

    for probe_index, num_simulations in enumerate(SIM_COUNTS, 1):
        print(f"\n{'='*60}", flush=True)
        print(f"[{probe_index}/{len(SIM_COUNTS)}] IMC-{num_simulations} vs GnuGo-L{GNUGO_LEVEL}  ({NUM_GAMES} games)", flush=True)
        print(f"{'='*60}", flush=True)

        probe_start_time = time.time()
        wins, total = eval_vs_gnugo(
            lib, GNUGO, GNUGO_LEVEL,
            WEIGHTS.encode(), NUM_GAMES, num_simulations
        )
        elapsed = time.time() - probe_start_time
        win_percentage = wins / total * 100

        result = {
            "imc_sims": num_simulations,
            "opponent": f"GnuGo-L{GNUGO_LEVEL}",
            "wins": wins, "losses": total - wins,
            "total": total, "win_pct": win_percentage,
            "time_s": round(elapsed, 1),
        }
        results.append(result)
        print(f"  => IMC-{num_simulations}: {wins}/{total} ({win_percentage:.0f}%) in {elapsed:.0f}s", flush=True)

    print(f"\n{'='*60}", flush=True)
    print(f"RESULTS: IMC-MCTS (strong weights) vs GnuGo-L{GNUGO_LEVEL} (50 games each)", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"{'Sims':>6} {'W-L':>8} {'Win%':>8}", flush=True)
    print(f"{'-'*26}", flush=True)
    for result in results:
        print(f"{result['imc_sims']:>6} {result['wins']}-{result['losses']:>6} {result['win_pct']:>7.0f}%", flush=True)

    with open("probe_sims_50_results.json", "w") as output_handle:
        json.dump(results, output_handle, indent=2)
    print(f"\nSaved to probe_sims_50_results.json", flush=True)

if __name__ == "__main__":
    main()
