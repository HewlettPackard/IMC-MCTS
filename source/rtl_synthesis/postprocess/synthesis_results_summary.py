#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Synthesis Results Summary

Generates a comprehensive summary report of the DC synthesis results
for the IMC-MCTS accelerator components.
"""

import pandas as pd
import numpy as np
from pathlib import Path

def load_synthesis_data():
    """Load the synthesis area and power data"""
    synthesis_results_dir = Path(__file__).resolve().parent.parent / "synthesis_results"

    # Load area data
    area_df = pd.read_csv(synthesis_results_dir / "DC_synthesis_area.txt")

    # Load power data
    power_df = pd.read_csv(synthesis_results_dir / "DC_synthesis_power.txt")

    return area_df, power_df

def generate_summary_report(area_df, power_df):
    """Generate comprehensive summary report"""

    print("=" * 80)
    print("IMC-MCTS ACCELERATOR - SYNTHESIS RESULTS SUMMARY")
    print("=" * 80)
    print()

    # Board sizes and labels
    board_sizes = [4, 9, 25, 81, 169, 361]
    board_labels = ['2×2', '3×3', '5×5', '9×9', '13×13', '19×19']
    board_columns = ['2x2 (4 squares)', '3x3 (9 squares)', '5x5 (25 squares)',
                     '9x9 (81 squares)', '13x13 (169 squares)', '19x19 (361 squares)']

    # Calculate totals
    total_area = area_df[board_columns].sum()
    total_power = power_df[board_columns].sum()

    print("📊 OVERALL SCALING METRICS")
    print("-" * 40)
    print(f"{'Board Size':<12} {'Area (μm²)':<15} {'Power (mW)':<15} {'Area/Pos':<12} {'Power/Pos':<12}")
    print("-" * 80)

    for board_index, (position_count, board_label) in enumerate(zip(board_sizes, board_labels)):
        area_value = total_area.iloc[board_index]
        power_value = total_power.iloc[board_index]
        area_per_position = area_value / position_count
        power_per_position = power_value / position_count
        print(f"{board_label:<12} {area_value:<15.0f} {power_value:<15.3f} {area_per_position:<12.2f} {power_per_position:<12.4f}")

    print()

    # Scaling analysis
    print("📈 SCALING ANALYSIS")
    print("-" * 40)

    # Area scaling
    area_scaling = np.polyfit(np.log(board_sizes), np.log(total_area.values), 1)
    print(f"Area scaling: O(n^{area_scaling[0]:.2f})")

    # Power scaling
    power_scaling = np.polyfit(np.log(board_sizes), np.log(total_power.values), 1)
    print(f"Power scaling: O(n^{power_scaling[0]:.2f})")

    # Efficiency trends
    area_per_position = total_area.values / np.array(board_sizes)
    power_per_position = total_power.values / np.array(board_sizes)

    area_efficiency_trend = np.polyfit(np.log(board_sizes), np.log(area_per_position), 1)
    power_efficiency_trend = np.polyfit(np.log(board_sizes), np.log(power_per_position), 1)

    print(f"Area efficiency trend: O(n^{area_efficiency_trend[0]:.2f})")
    print(f"Power efficiency trend: O(n^{power_efficiency_trend[0]:.2f})")
    print()

    # Component analysis
    print("🔧 COMPONENT ANALYSIS (19×19 Board)")
    print("-" * 40)

    # Get 19x19 data
    area_19x19 = area_df[['Component Name', 'Category', '19x19 (361 squares)']].copy()
    power_19x19 = power_df[['Component Name', 'Category', '19x19 (361 squares)']].copy()

    # Sort by area
    area_19x19 = area_19x19.sort_values('19x19 (361 squares)', ascending=False)

    print("Top 5 Components by Area:")
    print(f"{'Component':<25} {'Category':<12} {'Area (μm²)':<12} {'% of Total':<10}")
    print("-" * 65)
    total_area_19x19 = area_19x19['19x19 (361 squares)'].sum()
    for _, component_row in area_19x19.head(5).iterrows():
        percentage = (component_row['19x19 (361 squares)'] / total_area_19x19) * 100
        print(f"{component_row['Component Name']:<25} {component_row['Category']:<12} {component_row['19x19 (361 squares)']:<12.0f} {percentage:<10.1f}%")

    print()

    # Sort by power
    power_19x19 = power_19x19.sort_values('19x19 (361 squares)', ascending=False)

    print("Top 5 Components by Power:")
    print(f"{'Component':<25} {'Category':<12} {'Power (mW)':<12} {'% of Total':<10}")
    print("-" * 65)
    total_power_19x19 = power_19x19['19x19 (361 squares)'].sum()
    for _, component_row in power_19x19.head(5).iterrows():
        percentage = (component_row['19x19 (361 squares)'] / total_power_19x19) * 100
        print(f"{component_row['Component Name']:<25} {component_row['Category']:<12} {component_row['19x19 (361 squares)']:<12.3f} {percentage:<10.1f}%")

    print()

    # Category analysis
    print("📋 CATEGORY BREAKDOWN (19×19 Board)")
    print("-" * 40)

    area_by_category = area_19x19.groupby('Category')['19x19 (361 squares)'].sum().sort_values(ascending=False)
    power_by_category = power_19x19.groupby('Category')['19x19 (361 squares)'].sum().sort_values(ascending=False)

    print("Area by Category:")
    print(f"{'Category':<15} {'Area (μm²)':<15} {'% of Total':<10}")
    print("-" * 45)
    for category, area_value in area_by_category.items():
        percentage = (area_value / total_area_19x19) * 100
        print(f"{category:<15} {area_value:<15.0f} {percentage:<10.1f}%")

    print()
    print("Power by Category:")
    print(f"{'Category':<15} {'Power (mW)':<15} {'% of Total':<10}")
    print("-" * 45)
    for category, power_value in power_by_category.items():
        percentage = (power_value / total_power_19x19) * 100
        print(f"{category:<15} {power_value:<15.3f} {percentage:<10.1f}%")

    print()

    # Key insights
    print("💡 KEY INSIGHTS")
    print("-" * 40)

    # Largest component
    largest_area_component = area_19x19.iloc[0]
    largest_power_component = power_19x19.iloc[0]

    print(f"• Largest area component: {largest_area_component['Component Name']} ({largest_area_component['Category']}) - {largest_area_component['19x19 (361 squares)']:.0f} μm²")
    print(f"• Largest power component: {largest_power_component['Component Name']} ({largest_power_component['Category']}) - {largest_power_component['19x19 (361 squares)']:.3f} mW")

    # Most efficient board size
    area_efficiency = total_area.values / np.array(board_sizes)
    power_efficiency = total_power.values / np.array(board_sizes)

    most_efficient_area_idx = np.argmin(area_efficiency)
    most_efficient_power_idx = np.argmin(power_efficiency)

    print(f"• Most area-efficient board size: {board_labels[most_efficient_area_idx]} ({area_efficiency[most_efficient_area_idx]:.2f} μm²/pos)")
    print(f"• Most power-efficient board size: {board_labels[most_efficient_power_idx]} ({power_efficiency[most_efficient_power_idx]:.4f} mW/pos)")

    # Scaling efficiency
    if area_scaling[0] < 1.0:
        print(f"• Area scaling is sub-linear (O(n^{area_scaling[0]:.2f})) - good scalability")
    else:
        print(f"• Area scaling is super-linear (O(n^{area_scaling[0]:.2f})) - scalability concern")

    if power_scaling[0] < 1.0:
        print(f"• Power scaling is sub-linear (O(n^{power_scaling[0]:.2f})) - good scalability")
    else:
        print(f"• Power scaling is super-linear (O(n^{power_scaling[0]:.2f})) - scalability concern")

    print()

    # Technology implications
    print("🔬 TECHNOLOGY IMPLICATIONS")
    print("-" * 40)

    # Calculate energy per iteration
    energy_per_iteration = total_power.values * 1000  # Convert mW to μW for nJ calculation
    print("Energy per MCTS iteration (assuming 1ms iteration time):")
    for board_index, (board_label, board_energy) in enumerate(zip(board_labels, energy_per_iteration)):
        print(f"  {board_label}: {board_energy:.2f} nJ")

    print()

    # Memory requirements
    print("Memory requirements (estimated):")
    for board_index, (board_label, position_count) in enumerate(zip(board_labels, board_sizes)):
        # Estimate memory based on board size (rough calculation)
        estimated_memory = position_count * 4  # 4 bytes per position (rough estimate)
        print(f"  {board_label}: ~{estimated_memory} bytes ({estimated_memory/1024:.1f} KB)")

    print()
    print("=" * 80)
    print("SUMMARY COMPLETE")
    print("=" * 80)

def main():
    """Main function"""
    print("Loading synthesis data...")
    area_df, power_df = load_synthesis_data()

    print("Generating summary report...")
    generate_summary_report(area_df, power_df)

if __name__ == "__main__":
    main()
