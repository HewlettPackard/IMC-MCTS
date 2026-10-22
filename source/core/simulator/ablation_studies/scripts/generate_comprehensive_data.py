#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Generate Comprehensive Experimental Data
=========================================

Collects data for:
1. Power and Area breakdown by board size and play strength
2. Scalability: Energy per iteration from 2x2 to 19x19
3. CAM architecture search: different CAM cell designs
"""

import sys
import os
import csv
import time
import numpy as np
import pandas as pd

# Add paths
sys.path.insert(0, 'py_sst_cpp/components')

# Create results directory
os.makedirs('experiment_results', exist_ok=True)


def collect_power_area_breakdown():
    """Collect power and area for every board size and play strength."""
    print("\n" + "="*70)
    print("COLLECTING POWER AND AREA BREAKDOWN DATA")
    print("="*70)

    from board_config_performance import get_board_config_with_performance

    rows = []

    board_sizes = [2, 3, 5, 9, 13, 19]
    play_strengths = ['Low', 'Medium', 'High']

    for board_size in board_sizes:
        print(f"\nProcessing {board_size}×{board_size} board...")

        # For each play strength, get performance-aware configuration
        for strength in play_strengths:
            # Get hardware configuration adjusted for this performance level
            try:
                board_config = get_board_config_with_performance(board_size, strength)
            except (ValueError, KeyError) as e:
                print(f"  ⚠️  No config for {board_size}×{board_size} {strength}, skipping: {e}")
                continue
            # Component breakdown
            components = {
                'TCAM': (board_config.tcam_area_mm2, board_config.tcam_power_mw),
                'Selection': (board_config.selection_area_mm2, board_config.selection_power_mw),
                'Expansion': (board_config.expansion_area_mm2, board_config.expansion_power_mw),
                'Rollout': (board_config.rollout_total_area_mm2, board_config.rollout_power_mw_computed),
                'Backprop': (board_config.backprop_area_mm2, board_config.backprop_power_mw),
                'FSM': (board_config.fsm_area_mm2, board_config.fsm_power_mw),
            }

            for component_name, (area, power) in components.items():
                rows.append({
                    'board_size': f'{board_size}x{board_size}',
                    'play_strength': strength,
                    'component': component_name,
                    'area_mm2': area,
                    'power_mw': power
                })

            # Add total
            rows.append({
                'board_size': f'{board_size}x{board_size}',
                'play_strength': strength,
                'component': 'Total',
                'area_mm2': board_config.total_area_mm2,
                'power_mw': board_config.total_power_mw
            })

        print(f"  ✅ Collected data for {board_size}×{board_size}")

    # Write CSV
    csv_file = 'experiment_results/power_area_breakdown.csv'
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ Saved: {csv_file}")
    return csv_file


def collect_scalability_energy():
    """Collect energy per iteration from 2×2 through 19×19 boards."""
    print("\n" + "="*70)
    print("COLLECTING SCALABILITY DATA (2×2 TO 19×19)")
    print("="*70)

    from crossbar_rollout import CrossbarRolloutUnit
    from board_config import get_board_config, BoardSize

    rows = []

    board_sizes = [2, 3, 5, 9, 13, 19]

    for board_size in board_sizes:
        print(f"\nTesting {board_size}×{board_size} board...")

        try:
            # Get config
            board_enum = BoardSize(board_size)
            board_config = get_board_config(board_enum)

            # Run quick performance test
            rollout = CrossbarRolloutUnit(board_size=board_size)
            board = [[0]*board_size for _ in range(board_size)]
            num_rollouts = 50

            start_time = time.time()
            for _ in range(num_rollouts):
                rollout.perform_rollout(board, current_player=1)
            elapsed = time.time() - start_time

            iterations_per_sec = num_rollouts / elapsed
            total_power_mw = board_config.total_power_mw
            energy_per_iter_j = total_power_mw * 1e-3 / iterations_per_sec

            rows.append({
                'board_size': f'{board_size}x{board_size}',
                'num_positions': board_size ** 2,
                'iterations_per_sec': iterations_per_sec,
                'power_mw': total_power_mw,
                'energy_per_iteration_j': energy_per_iter_j,
                'energy_per_iteration_uj': energy_per_iter_j * 1e6,
                'area_mm2': board_config.total_area_mm2
            })

            print(f"  Iterations/sec: {iterations_per_sec:.1f}")
            print(f"  Energy/iter: {energy_per_iter_j*1e6:.2f} µJ")

        except (ValueError, KeyError, Exception) as e:
            print(f"  ⚠️  Error for {board_size}×{board_size}: {e}")
            continue

    # Write CSV
    csv_file = 'experiment_results/scalability_energy.csv'
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ Saved: {csv_file}")
    return csv_file


def process_cam_architecture_search():
    """Prepare the CAM design choices used by the search plot."""
    print("\n" + "="*70)
    print("PROCESSING CAM ARCHITECTURE SEARCH DATA")
    print("="*70)

    # Read CAM choices
    cam_options_df = pd.read_csv('cam_choices.csv')

    print(f"\nLoaded {len(cam_options_df)} CAM designs:")
    for _, row in cam_options_df.iterrows():
        print(f"  {row['cam_design']:25s}: {row['area_um2']:6.2f} µm², {row['power_mw']:5.2f} mW")

    # Copy to experiment_results for consistency
    cam_options_df.to_csv('experiment_results/cam_architecture_search.csv', index=False)

    print(f"\n✅ Saved: experiment_results/cam_architecture_search.csv")
    return 'experiment_results/cam_architecture_search.csv'


def main():
    """Generate all comprehensive data"""
    print("="*70)
    print("COMPREHENSIVE DATA GENERATION")
    print("="*70)

    csv_files = []

    # Collect all data
    csv_files.append(collect_power_area_breakdown())
    csv_files.append(collect_scalability_energy())
    csv_files.append(process_cam_architecture_search())

    # Generate Accelerator CAM comparison
    from generate_accelerator_cam_comparison import generate_accelerator_cam_comparison
    csv_files.append(generate_accelerator_cam_comparison())

    print("\n" + "="*70)
    print("DATA COLLECTION COMPLETE")
    print("="*70)
    print("\nGenerated CSV files:")
    for f in csv_files:
        print(f"  ✅ {f}")

    print("\nNext: Run plotting script to generate figures")


if __name__ == '__main__':
    main()
