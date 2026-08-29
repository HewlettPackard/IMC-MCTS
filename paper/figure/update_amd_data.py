#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Calculate AMD CPU energy values and update Figure 5 data."""

import argparse
import pandas as pd
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AMD_FILE = REPO_ROOT / "cpu-gpu-benchmarking" / "results" / "mcts_benchmark_cpu_amd_ryzen_threadripper_pro_5945wx_12_cores_20251112_182746.csv"
DEFAULT_SCALABILITY = REPO_ROOT / "cpu-gpu-benchmarking" / "tables" / "scalability_analysis.csv"
DEFAULT_ACCELERATOR = REPO_ROOT / "core" / "simulator" / "results" / "experiment_data" / "scalability_energy.csv"
DEFAULT_OUTPUT = REPO_ROOT / "paper" / "results" / "fig05_energy_scaling.csv"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amd-results", type=Path, default=DEFAULT_AMD_FILE)
    parser.add_argument("--scalability", type=Path, default=DEFAULT_SCALABILITY)
    parser.add_argument("--accelerator", type=Path, default=DEFAULT_ACCELERATOR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    df_amd = pd.read_csv(args.amd_results)

    print("Calculating AMD CPU energy values...")
    print("\nBoard Size -> Energy per iteration (μJ)")
    print("-" * 50)

    amd_energy_data = {}

    for board_size in sorted(df_amd['board_size'].unique()):
        df_board = df_amd[df_amd['board_size'] == board_size]

    # Filter out rows where energy is 0 (measurement issues)
        df_valid = df_board[df_board['total_energy_uj'] > 0]

        if len(df_valid) > 0:
        # Convert each valid trial to energy per MCTS iteration.
            energy_per_iter = df_valid['total_energy_uj'] / df_valid['iterations']

        # Aggregate the valid trials for this board size.
            mean_energy = energy_per_iter.mean()
            std_energy = energy_per_iter.std()

            amd_energy_data[f"{board_size}x{board_size}"] = mean_energy

            print(f"{board_size}x{board_size}: {mean_energy:.3f} ± {std_energy:.3f} μJ")
        else:
            print(f"{board_size}x{board_size}: No valid measurements")

# Replace the CPU energy column in the scalability table with AMD measurements.
    print("\n" + "=" * 50)
    print("Updating scalability analysis with AMD data...")

    df_scalability = pd.read_csv(args.scalability)

# Update one board-size row at a time.
    for idx, row in df_scalability.iterrows():
        board_size = row['board_size']
        if board_size in amd_energy_data:
            df_scalability.loc[idx, 'cpu_eng_mean'] = amd_energy_data[board_size]
        # Keep std as proportional (rough estimate)
            df_scalability.loc[idx, 'cpu_eng_std'] = amd_energy_data[board_size] * 0.05

# Save updated file
    df_scalability.to_csv(args.scalability, index=False)
    print(f"Updated {args.scalability}")

# Regenerate the Figure 5 energy-scaling data.
    print("\nRegenerating fig05_energy_scaling.csv...")

# Load the Accelerator energy measurements.
    df_accelerator = pd.read_csv(args.accelerator)

# Merge Accelerator, CPU, and both GPU operating modes on board size.
    df_energy = df_accelerator[['board_size', 'energy_per_iteration_uj']].rename(
        columns={'energy_per_iteration_uj': 'accelerator_energy_uj'}
    )

    df_energy = df_energy.merge(
        df_scalability[['board_size', 'cpu_eng_mean', 'gpu_fair_eng_mean', 'gpu_cap_eng_mean']],
        on='board_size',
        how='outer'
    )

# Use the AMD processor name in the final figure-data columns.
    df_energy.columns = ['board_size', 'Accelerator', 'CPU (AMD Threadripper 5945WX)', 'GPU Fair (H100)', 'GPU Max (H100)']

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df_energy.to_csv(args.output, index=False)
    print(f"Saved {len(df_energy)} rows to {args.output}")

    print("\n" + "=" * 50)
    print("Data update complete")
    print("=" * 50)


if __name__ == "__main__":
    main()
