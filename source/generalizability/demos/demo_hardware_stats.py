#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Hardware Stats Demo - Report accelerator metrics for all 13 applications.

Uses the accelerator_api.estimate() analytical model to compute area, power,
energy, and latency for each application at LOW/MED/HIGH play strengths.

Usage:
    python applications/demo_hardware_stats.py
"""

import sys
import os
import csv

# Add SST simulator to path for accelerator_api
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "simulator", "sst"))
from core.architecture.accelerator_api import estimate

# Application -> board size mapping (must match games/__init__.py)
APP_BOARD_SIZES = {
    "go": 9,
    "hex": 11,
    "gomoku": 15,
    "havannah": 15,
    "pente": 19,
    "othello": 8,
    "connect_four": 8,
    "breakthrough": 8,
    "protein_folding": 13,
    "nonograms": 9,
    "frozen_lake": 8,
    "minigrid": 8,
    "minesweeper": 9,
}

STRENGTHS = ["low", "medium", "high"]


def run_hardware_estimates():
    """Sweep every application and play strength through the analytical model."""
    hardware_results = []

    # One hardware estimate per application and strength level.
    for app_name, board_size in sorted(APP_BOARD_SIZES.items()):
        for strength in STRENGTHS:
            estimate_result = estimate(
                board_size=board_size,
                play_strength=strength,
                mode="analytical",
            )
            hardware_results.append({
                "application": app_name,
                "board_size": board_size,
                "strength": strength.upper(),
                "iterations": estimate_result.iterations,
                "area_mm2": estimate_result.area_mm2,
                "power_mw": estimate_result.power_mw,
                "energy_uj": estimate_result.energy_uj,
                "latency_us": estimate_result.latency_us,
                "throughput_miter_s": estimate_result.throughput_iter_per_s / 1e6,
                "efficiency_miter_j": estimate_result.energy_efficiency_miter_per_j,
            })

    return hardware_results


def print_results_table(results):
    """Print per-application estimates and the board-size summary."""
    header = (
        f"{'Application':<18} {'Board':>5} {'Strength':>8} {'Iter':>8} "
        f"{'Area(mm2)':>10} {'Power(mW)':>10} {'Energy(uJ)':>11} {'Latency(us)':>12}"
    )
    sep = "-" * len(header)

    print("\n" + "=" * len(header))
    print("Accelerator Hardware Estimation - All 13 Applications")
    print("Technology: 22nm @ 500 MHz  |  Mode: Analytical")
    print("=" * len(header))
    print(header)
    print(sep)

    current_app = None
    for result in results:
        if result["application"] != current_app:
            if current_app is not None:
                print(sep)
            current_app = result["application"]
        print(
            f"{result['application']:<18} "
            f"{result['board_size']:>5} "
            f"{result['strength']:>8} "
            f"{result['iterations']:>8,} "
            f"{result['area_mm2']:>10.4f} "
            f"{result['power_mw']:>10.2f} "
            f"{result['energy_uj']:>11.3f} "
            f"{result['latency_us']:>12.2f}"
        )
    print(sep)

    # Group the medium-strength rows by physical board size.
    print("\n" + "=" * 60)
    print("Summary by Board Size (MEDIUM strength)")
    print("=" * 60)
    print(f"{'Board':>5} {'Apps':>5} {'Area(mm2)':>10} {'Power(mW)':>10} {'Energy(uJ)':>11}")
    print("-" * 50)

    board_groups = {}
    for result in results:
        if result["strength"] == "MEDIUM":
            board_size = result["board_size"]
            if board_size not in board_groups:
                board_groups[board_size] = {
                    "apps": [],
                    "area": result["area_mm2"],
                    "power": result["power_mw"],
                    "energy": result["energy_uj"],
                }
            board_groups[board_size]["apps"].append(result["application"])

    for board_size in sorted(board_groups.keys()):
        board_group = board_groups[board_size]
        print(
            f"{board_size:>5} {len(board_group['apps']):>5} "
            f"{board_group['area']:>10.4f} {board_group['power']:>10.2f} "
            f"{board_group['energy']:>11.3f}"
        )
    print("-" * 50)
    print(f"Note: Applications sharing a board size use identical hardware.")


def save_results_csv(results, filepath):
    """Save hardware estimation results to CSV."""
    if not results:
        return
    keys = ["application", "board_size", "strength", "iterations",
            "area_mm2", "power_mw", "energy_uj", "latency_us",
            "throughput_miter_s", "efficiency_miter_j"]
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults saved to: {filepath}")


def main():
    print("Running Accelerator hardware estimation for 13 applications ...")
    hardware_results = run_hardware_estimates()
    print_results_table(hardware_results)

    # Save the full sweep beside this script.
    csv_path = os.path.join(os.path.dirname(__file__), "hardware_stats.csv")
    save_results_csv(hardware_results, csv_path)


if __name__ == "__main__":
    main()
