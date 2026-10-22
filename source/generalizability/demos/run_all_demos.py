#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Master Demo Runner - Runs behavioral and hardware demos for all 13 applications.

Executes:
  1. Behavioral demo at LOW iterations (quick) for all games
  2. Hardware stats demo for all applications at all strength levels

Saves results to CSV files in this directory.

Usage:
    python generalizability/demos/run_all_demos.py
"""

import subprocess
import sys
import os
import time


APPS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(APPS_DIR)


def run_command(desc, cmd):
    """Run one demo command and report its return code and elapsed time."""
    print(f"\n{'='*70}")
    print(f"  {desc}")
    print(f"{'='*70}\n")
    start_time = time.time()
    completed_process = subprocess.run(
        cmd,
        cwd=PROJECT_DIR,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    elapsed = time.time() - start_time
    status = (
        "OK" if completed_process.returncode == 0
        else f"FAILED (rc={completed_process.returncode})"
    )
    print(f"\n  [{status}] {desc} ({elapsed:.1f}s)")
    return completed_process.returncode


def main():
    print("=" * 70)
    print("  Accelerator Multi-Application Demo Suite")
    print("  13 Applications, Zero Hardware Changes")
    print("=" * 70)

    total_start = time.time()
    failed_demos = []

    # Stage 1: run a short behavioral pass across every game.
    behavioral_csv = os.path.join(APPS_DIR, "behavioral_results.csv")
    return_code = run_command(
        "Behavioral Demo (LOW=50 iterations, all games, 3 games each)",
        [
            sys.executable,
            os.path.join(APPS_DIR, "demo_behavioral.py"),
            "--game", "all",
            "--iterations", "50",
            "--num-games", "3",
            "--output-csv", behavioral_csv,
        ],
    )
    if return_code != 0:
        failed_demos.append("behavioral demo")

    # Stage 2: run the analytical hardware sweep.
    return_code = run_command(
        "Hardware Stats Demo (all applications, analytical)",
        [
            sys.executable,
            os.path.join(APPS_DIR, "demo_hardware_stats.py"),
        ],
    )
    if return_code != 0:
        failed_demos.append("hardware stats demo")

    # Stage 3: report runtime, output files, and failures.
    total_elapsed = time.time() - total_start
    print("\n" + "=" * 70)
    print("  DEMO SUITE SUMMARY")
    print("=" * 70)
    print(f"  Total elapsed time: {total_elapsed:.1f}s")

    output_files = [
        ("Behavioral results", behavioral_csv),
        ("Hardware stats", os.path.join(APPS_DIR, "hardware_stats.csv")),
    ]
    print("\n  Output files:")
    for label, path in output_files:
        exists = os.path.exists(path)
        status = "OK" if exists else "MISSING"
        print(f"    [{status}] {label}: {path}")

    if failed_demos:
        print(f"\n  WARNING: {len(failed_demos)} demo(s) failed: {', '.join(failed_demos)}")
        return 1
    else:
        print("\n  All demos completed successfully.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
