#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Generate Accelerator CAM Comparison Data
=========================================

This script generates data showing how different CAM technology choices
affect the total Accelerator architecture (Selection + Expansion + Rollout +
Backprop + FSM + TCAM).

Baseline: 9×9 board, Medium play strength
CAM technologies from cam_choices.csv
"""

import pandas as pd


# TCAM configuration for MCTS FSM
TCAM_NUM_ROWS = 11
TCAM_ROW_WIDTH_BITS = 16
TCAM_TOTAL_CELLS = TCAM_NUM_ROWS * TCAM_ROW_WIDTH_BITS  # 176 cells

# Baseline TCAM at 22nm (from tcam_power.py)
BASELINE_TCAM_CELL_AREA_UM2 = 0.4  # µm² per cell at 22nm
BASELINE_TCAM_CELL_POWER_UW = 1.415  # µW per cell (estimated from leakage + dynamic)


def generate_accelerator_cam_comparison():
    """Swap CAM technologies into the 9×9 Accelerator baseline."""
    print("\n" + "="*70)
    print("GENERATING ACCELERATOR CAM COMPARISON")
    print("="*70)

    # Read baseline 9x9 Medium configuration
    breakdown_df = pd.read_csv('experiment_results/power_area_breakdown.csv')
    baseline = breakdown_df[
        (breakdown_df['board_size'] == '9x9') &
        (breakdown_df['play_strength'] == 'Medium') &
        (breakdown_df['component'] != 'Total')
    ].copy()

    print("\nBaseline 9×9 Medium Configuration:")
    print(baseline[['component', 'area_mm2', 'power_mw']].to_string(index=False))

    # Get non-TCAM components (these stay constant)
    non_tcam_area = baseline[baseline['component'] != 'TCAM']['area_mm2'].sum()
    non_tcam_power = baseline[baseline['component'] != 'TCAM']['power_mw'].sum()

    print(f"\nNon-TCAM Components:")
    print(f"  Total Area:  {non_tcam_area:.6f} mm²")
    print(f"  Total Power: {non_tcam_power:.2f} mW")

    # Read CAM technology options
    cam_options_df = pd.read_csv('cam_choices.csv')

    print(f"\n\nProcessing {len(cam_options_df)} CAM technologies...")
    print()

    # Generate Accelerator configurations
    accelerator_rows = []

    for _, cam_row in cam_options_df.iterrows():
        cam_name = cam_row['cam_design']
        cam_area_um2 = cam_row['area_um2']
        cam_power_mw = cam_row['power_mw']
        cell_type = cam_row['cell_type']

        # Calculate TCAM area with this CAM technology
        # TCAM = 176 cells × (area per cell)
        tcam_area_um2 = TCAM_TOTAL_CELLS * cam_area_um2
        tcam_area_mm2 = tcam_area_um2 / 1e6

        # Estimate TCAM power scaling
        # Assume power scales with area ratio (simplified model)
        cam_area_ratio = cam_area_um2 / BASELINE_TCAM_CELL_AREA_UM2
        baseline_tcam_power_mw = 0.249  # from power_area_breakdown.csv
        scaled_tcam_power_mw = baseline_tcam_power_mw * cam_area_ratio

        # For power-optimized designs (low power CAMs), use their power spec
        # Scale to account for 176 cells
        cam_power_per_cell_uw = (cam_power_mw * 1000) / 1  # Assume 1 cell baseline
        specified_tcam_power_mw = (TCAM_TOTAL_CELLS * cam_power_per_cell_uw) / 1000

        # Use minimum of scaled baseline and spec-based estimate
        tcam_power_mw = min(scaled_tcam_power_mw, specified_tcam_power_mw)

        # Calculate total Accelerator metrics
        total_area_mm2 = non_tcam_area + tcam_area_mm2
        total_power_mw = non_tcam_power + tcam_power_mw

        accelerator_rows.append({
            'accelerator_config': f'Accelerator {cam_name}',
            'cam_design': cam_name,
            'cell_type': cell_type,
            'total_area_mm2': total_area_mm2,
            'total_power_mw': total_power_mw,
            'tcam_area_mm2': tcam_area_mm2,
            'tcam_power_mw': tcam_power_mw,
            'non_tcam_area_mm2': non_tcam_area,
            'non_tcam_power_mw': non_tcam_power
        })

        print(f"  {cam_name:25s}: TCAM={tcam_area_um2:6.1f}µm² {tcam_power_mw:5.2f}mW → "
              f"Total={total_area_mm2:.6f}mm² {total_power_mw:6.2f}mW")

    # Create DataFrame
    accelerator_df = pd.DataFrame(accelerator_rows)

    # Save to CSV
    output_file = 'experiment_results/accelerator_cam_comparison.csv'
    accelerator_df.to_csv(output_file, index=False)

    print(f"\n✅ Saved: {output_file}")
    print(f"   Generated {len(accelerator_df)} Accelerator configurations")

    # Print summary statistics
    print("\n" + "="*70)
    print("ACCELERATOR DESIGN SPACE SUMMARY")
    print("="*70)
    print(f"Area range:  {accelerator_df['total_area_mm2'].min():.6f} - "
          f"{accelerator_df['total_area_mm2'].max():.6f} mm²")
    print(f"Power range: {accelerator_df['total_power_mw'].min():.2f} - "
          f"{accelerator_df['total_power_mw'].max():.2f} mW")

    # Find optimal (minimum area + power product)
    accelerator_df['area_power_product'] = (
        accelerator_df['total_area_mm2'] * accelerator_df['total_power_mw']
    )
    optimal_idx = accelerator_df['area_power_product'].idxmin()
    optimal_config = accelerator_df.loc[optimal_idx]

    print(f"\nOptimal Configuration (min area×power):")
    print(f"  {optimal_config['accelerator_config']}")
    print(f"  Area:  {optimal_config['total_area_mm2']:.6f} mm²")
    print(f"  Power: {optimal_config['total_power_mw']:.2f} mW")
    print()

    return output_file


if __name__ == '__main__':
    generate_accelerator_cam_comparison()
