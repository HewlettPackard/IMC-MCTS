#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Generate cleaned CSV files for the MCTS paper figures.

Reads raw benchmark + SST-simulator outputs and writes one tidy CSV per figure
into paper/results/ -- the single source of truth the plot_*.py scripts read.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Paths (this file lives at paper/figure/).
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_OUT = Path(__file__).resolve().parent.parent / "results"   # paper/results/
ACCELERATOR_DIR = BASE_DIR / "core/simulator/results/experiment_data"
BENCHMARK_DIR = BASE_DIR / "cpu-gpu-benchmarking"


def latest_match(pattern: str) -> Path:
    matches = sorted(BENCHMARK_DIR.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No benchmark file matched {pattern}")
    return matches[-1]


def get_dominant_bottleneck_data(df, platform_name):
    """Per board size: average each phase's percentage across trials and pick
    the dominant (largest-percentage) phase."""
    results = []
    for board_size in df['board_size'].unique():
        df_board = df[df['board_size'] == board_size]

        # Average percentages across trials
        sel_pct = df_board['selection_percent'].mean()
        exp_pct = df_board['expansion_percent'].mean()
        sim_pct = df_board['simulation_percent'].mean()
        back_pct = df_board['backpropagation_percent'].mean()

        # Find dominant phase
        phases = {
            'Selection': sel_pct,
            'Expansion': exp_pct,
            'Rollout': sim_pct,
            'Backpropagation': back_pct
        }
        dominant_phase = max(phases, key=phases.get)
        dominant_pct = phases[dominant_phase]

        results.append({
            'board_size': board_size,
            'platform': platform_name,
            'dominant_phase': dominant_phase,
            'percentage': dominant_pct,
            'selection_pct': sel_pct,
            'expansion_pct': exp_pct,
            'rollout_pct': sim_pct,
            'backpropagation_pct': back_pct
        })

    return results


def gen_fig01_bottleneck():
    """Figure 1: dominant MCTS bottleneck phase per platform x board size."""
    print("\n[1/5] Generating fig01_bottleneck_scaling.csv...")

    cpu_file = latest_match("results/traditional/mcts_benchmark_cpu_*.csv")
    df_cpu = pd.read_csv(cpu_file)

    gpu_fair_file = latest_match("results/traditional/mcts_benchmark_gpu_fair_*.csv")
    df_gpu_fair = pd.read_csv(gpu_fair_file)

    gpu_max_file = latest_match("results/traditional/mcts_benchmark_gpu_capability_*.csv")
    df_gpu_max = pd.read_csv(gpu_max_file)

    bottleneck_data = []
    bottleneck_data.extend(get_dominant_bottleneck_data(df_cpu, 'CPU (Xeon 8462Y+)'))
    bottleneck_data.extend(get_dominant_bottleneck_data(df_gpu_fair, 'GPU Fair (H100)'))
    bottleneck_data.extend(get_dominant_bottleneck_data(df_gpu_max, 'GPU Max (H100)'))

    df_bottleneck = pd.DataFrame(bottleneck_data)
    df_bottleneck.to_csv(DATA_OUT / "fig01_bottleneck_scaling.csv", index=False)
    print(f"   Saved {len(df_bottleneck)} rows to fig01_bottleneck_scaling.csv")


def gen_fig04_area():
    """Figure 4: per-component area, pivoted wide for the stacked bar."""
    print("\n[2/5] Generating fig04_area_breakdown.csv...")

    df_breakdown = pd.read_csv(ACCELERATOR_DIR / "power_area_breakdown.csv")
    df_area = df_breakdown.copy()

    # Pivot to wide format; exclude 'Total' and break out 'FSM' separately
    # (FSM is controller overhead).
    components = ['TCAM', 'Selection', 'Expansion', 'Rollout', 'Backprop']
    df_area_pivot = df_area[df_area['component'].isin(components)].pivot_table(
        index=['board_size', 'play_strength'],
        columns='component',
        values='area_mm2',
        aggfunc='first'
    ).reset_index()

    # Add FSM as controller overhead
    df_fsm = df_area[df_area['component'] == 'FSM'][['board_size', 'play_strength', 'area_mm2']].rename(columns={'area_mm2': 'FSM'})
    df_area_pivot = df_area_pivot.merge(df_fsm, on=['board_size', 'play_strength'])

    # Reorder columns
    df_area_pivot = df_area_pivot[['board_size', 'play_strength', 'TCAM', 'Selection', 'Expansion', 'Rollout', 'Backprop', 'FSM']]

    df_area_pivot.to_csv(DATA_OUT / "fig04_area_breakdown.csv", index=False)
    print(f"   Saved {len(df_area_pivot)} rows to fig04_area_breakdown.csv")


def gen_fig04_power():
    """Figure 4: per-component power, same pivot as the area breakdown."""
    print("\n[3/5] Generating fig04_power_breakdown.csv...")

    df_breakdown = pd.read_csv(ACCELERATOR_DIR / "power_area_breakdown.csv")
    df_power = df_breakdown.copy()

    components = ['TCAM', 'Selection', 'Expansion', 'Rollout', 'Backprop']
    df_power_pivot = df_power[df_power['component'].isin(components)].pivot_table(
        index=['board_size', 'play_strength'],
        columns='component',
        values='power_mw',
        aggfunc='first'
    ).reset_index()

    df_fsm_power = df_power[df_power['component'] == 'FSM'][['board_size', 'play_strength', 'power_mw']].rename(columns={'power_mw': 'FSM'})
    df_power_pivot = df_power_pivot.merge(df_fsm_power, on=['board_size', 'play_strength'])

    df_power_pivot = df_power_pivot[['board_size', 'play_strength', 'TCAM', 'Selection', 'Expansion', 'Rollout', 'Backprop', 'FSM']]

    df_power_pivot.to_csv(DATA_OUT / "fig04_power_breakdown.csv", index=False)
    print(f"   Saved {len(df_power_pivot)} rows to fig04_power_breakdown.csv")


def gen_fig05_energy():
    """Figure 5: energy per iteration, Accelerator vs CPU/GPU baselines."""
    print("\n[4/5] Generating fig05_energy_scaling.csv...")

    df_accelerator = pd.read_csv(ACCELERATOR_DIR / "scalability_energy.csv")

    # CPU/GPU data from benchmark tables
    df_bench_table = pd.read_csv(BENCHMARK_DIR / "analysis/tables/scalability_analysis.csv")

    # Merge on board_size
    df_energy = df_accelerator[['board_size', 'energy_per_iteration_uj']].rename(
        columns={'energy_per_iteration_uj': 'accelerator_energy_uj'}
    )

    df_energy = df_energy.merge(
        df_bench_table[['board_size', 'cpu_eng_mean', 'gpu_fair_eng_mean', 'gpu_cap_eng_mean']],
        on='board_size',
        how='outer'
    )

    # Rename for clarity
    df_energy.columns = ['board_size', 'Accelerator', 'CPU (Xeon 8462Y+)', 'GPU Fair (H100)', 'GPU Max (H100)']

    df_energy.to_csv(DATA_OUT / "fig05_energy_scaling.csv", index=False)
    print(f"   Saved {len(df_energy)} rows to fig05_energy_scaling.csv")


def gen_fig06_cam():
    """Figure 6: system-level area/power impact of each CAM technology."""
    print("\n[5/5] Generating fig06_cam_system_impact.csv...")

    df_cam = pd.read_csv(ACCELERATOR_DIR / "accelerator_cam_comparison.csv")

    # All rows are relevant - total Accelerator area/power with different CAMs.
    df_cam_out = df_cam[[
        'cam_design', 'cell_type',
        'total_area_mm2', 'total_power_mw',
        'tcam_area_mm2', 'tcam_power_mw',
        'non_tcam_area_mm2', 'non_tcam_power_mw'
    ]].copy()

    df_cam_out.to_csv(DATA_OUT / "fig06_cam_system_impact.csv", index=False)
    print(f"   Saved {len(df_cam_out)} rows to fig06_cam_system_impact.csv")


def main():
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    print("Starting data file generation...")
    gen_fig01_bottleneck()
    gen_fig04_area()
    gen_fig04_power()
    gen_fig05_energy()
    gen_fig06_cam()
    print("\n" + "=" * 60)
    print("All data files generated successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
