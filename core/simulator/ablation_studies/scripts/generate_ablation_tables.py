#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Generate LaTeX Tables for Ablation Studies
===========================================

Generates publication-ready LaTeX tables for both ablation studies:
1. Table 1: Progressive Build-up (shows cumulative optimization benefits)
2. Table 2: Design Alternatives (justifies design choices)

Tables are copy-paste ready for LaTeX documents.
"""

import pandas as pd
import numpy as np
import os


def generate_progressive_buildup_table():
    """Generate Table 1: Progressive Optimization Build-up"""

    print("\n" + "="*80)
    print("TABLE 1: PROGRESSIVE OPTIMIZATION BUILD-UP")
    print("="*80)
    print()

    # Load data
    progressive_df = pd.read_csv('../../experiment_results/ablation_progressive_buildup.csv')

    # Focus on 9×9 board for main table (most representative)
    progressive_9x9 = progressive_df[progressive_df['board_size'] == 9].copy()

    # Generate LaTeX
    print("% Table 1: Progressive Optimization Build-up")
    print("% Shows cumulative benefit of adding each optimization")
    print()
    print("\\begin{table*}[t]")
    print("\\centering")
    print("\\caption{Progressive Optimization Analysis for 9$\\times$9 Board}")
    print("\\label{tab:progressive_buildup}")
    print("\\begin{tabular}{|l|r|r|r|r|l|}")
    print("\\hline")
    print("\\textbf{Configuration} & \\textbf{Speedup} & \\textbf{Energy} & \\textbf{Area} & \\textbf{TOPS/W} & \\textbf{Key Improvement} \\\\")
    print("                       & \\textbf{vs CPU}  & \\textbf{Savings}& \\textbf{(mm²)}& & \\\\")
    print("\\hline")

    for _, row in progressive_9x9.iterrows():
        configuration_name = row['configuration_name']
        speedup = row['speedup_vs_baseline']
        energy = row['energy_savings_vs_baseline']
        area = row['area_mm2']
        tops_w = row['tops_per_watt']
        bottleneck = row['bottleneck']

        # Format area
        if area < 0.0001:
            area_str = "--"
        else:
            area_str = f"{area:.4f}"

        # Shorten configuration names for table
        config_short = configuration_name.replace("(ARM CPU)", "").replace("(chosen)", "").strip()
        if len(config_short) > 25:
            config_short = config_short[:22] + "..."

        # Shorten bottleneck
        bottleneck_short = bottleneck
        if len(bottleneck_short) > 35:
            bottleneck_short = bottleneck_short[:32] + "..."

        print(f"{config_short:28s} & {speedup:5.1f}$\\times$ & {energy:5.1f}$\\times$ & "
              f"{area_str:8s} & {tops_w:6.1f} & {bottleneck_short} \\\\")

    print("\\hline")
    print("\\end{tabular}")
    print("\\end{table*}")
    print()

    # Summary statistics
    print("% Summary Statistics (for all board sizes):")
    print(f"% Average speedup (3×3 to 13×13): {progressive_df[progressive_df['configuration_name']=='Full Accelerator']['speedup_vs_baseline'].mean():.1f}×")
    print(f"% Average energy savings: {progressive_df[progressive_df['configuration_name']=='Full Accelerator']['energy_savings_vs_baseline'].mean():.1f}×")
    print()


def generate_design_alternatives_table():
    """Generate Table 2: Design Alternative Comparisons"""

    print("\n" + "="*80)
    print("TABLE 2: DESIGN ALTERNATIVE COMPARISONS")
    print("="*80)
    print()

    # Load data
    alternatives_df = pd.read_csv('../../experiment_results/ablation_design_alternatives.csv')

    # Focus on 9×9 board
    alternatives_9x9 = alternatives_df[alternatives_df['board_size'] == 9].copy()

    # Generate LaTeX
    print("% Table 2: Design Alternative Comparisons")
    print("% Justifies implementation choices for each module")
    print()
    print("\\begin{table*}[t]")
    print("\\centering")
    print("\\caption{Module Implementation Alternatives for 9$\\times$9 Board}")
    print("\\label{tab:design_alternatives}")
    print("\\begin{tabular}{|l|l|r|r|r|r|c|}")
    print("\\hline")
    print("\\textbf{Module} & \\textbf{Implementation} & \\textbf{Latency} & \\textbf{Energy} & \\textbf{Area} & \\textbf{Speedup} & \\textbf{Choice} \\\\")
    print("               &                         & \\textbf{(ns)}    & \\textbf{(pJ)}  & \\textbf{(mm²)}& \\textbf{vs Base}& \\\\")
    print("\\hline")

    # Process by module
    modules = alternatives_9x9['module_name'].unique()

    for module_idx, module in enumerate(modules):
        module_df = alternatives_9x9[alternatives_9x9['module_name'] == module]

        for row_index, row in module_df.iterrows():
            implementation = row['implementation']
            latency = row['latency_per_op_ns']
            energy = row['energy_per_op_pj']
            area = row['area_mm2']
            speedup = row['speedup_vs_baseline']
            chosen = row['chosen']

            # Format area
            if area < 0.00001:
                area_str = "--"
            else:
                area_str = f"{area:.5f}"

            # Choice marker
            choice_mark = "\\checkmark" if chosen else ""

            # Module name only on first row
            if row_index == module_df.index[0]:
                module_name = module.replace("Unit", "")
            else:
                module_name = ""

            print(f"{module_name:15s} & {implementation:23s} & {latency:8.1f} & {energy:8.1f} & "
                  f"{area_str:8s} & {speedup:5.1f}$\\times$ & {choice_mark:10s} \\\\")

        # Add line between modules (except after last)
        if module_idx < len(modules) - 1:
            print("\\hline")

    print("\\hline")
    print("\\end{tabular}")
    print("\\end{table*}")
    print()

    # Add notes
    print("% Notes:")
    rollout_chosen = alternatives_9x9[(alternatives_9x9['module_name']=='Rollout Unit') & (alternatives_9x9['chosen']==True)]
    if not rollout_chosen.empty:
        speedup = rollout_chosen.iloc[0]['speedup_vs_baseline']
        energy = rollout_chosen.iloc[0]['energy_efficiency_vs_baseline']
        print(f"% - IMC Rollout: {speedup:.0f}× faster, {energy:.0f}× more energy efficient than software")

    selection_chosen = alternatives_9x9[(alternatives_9x9['module_name']=='Selection Unit') & (alternatives_9x9['chosen']==True)]
    if not selection_chosen.empty:
        speedup = selection_chosen.iloc[0]['speedup_vs_baseline']
        print(f"% - TCAM Selection: {speedup:.0f}× faster than sequential FSM")

    expansion_chosen = alternatives_9x9[(alternatives_9x9['module_name']=='Expansion Unit') & (alternatives_9x9['chosen']==True)]
    if not expansion_chosen.empty:
        speedup = expansion_chosen.iloc[0]['speedup_vs_baseline']
        print(f"% - Optimized Expansion: {speedup:.0f}× faster than software")
    print()


def generate_compact_comparison_table():
    """Generate compact comparison table (alternative format)"""

    print("\n" + "="*80)
    print("ALTERNATIVE: COMPACT COMPARISON TABLE")
    print("="*80)
    print()

    # Load both datasets
    progressive_df = pd.read_csv('../../experiment_results/ablation_progressive_buildup.csv')
    alternatives_df = pd.read_csv('../../experiment_results/ablation_design_alternatives.csv')

    # Get key configurations for 9×9
    baseline = progressive_df[(progressive_df['board_size']==9) & (progressive_df['configuration_name']=='Baseline (ARM CPU)')].iloc[0]
    digital_rollout = progressive_df[(progressive_df['board_size']==9) & (progressive_df['configuration_name']=='+ Digital Rollout')].iloc[0]
    full_system = progressive_df[(progressive_df['board_size']==9) & (progressive_df['configuration_name']=='Full Accelerator')].iloc[0]

    print("% Compact Comparison: Key Configurations (9×9 Board)")
    print()
    print("\\begin{table}[t]")
    print("\\centering")
    print("\\caption{Key Design Points Comparison}")
    print("\\label{tab:key_comparisons}")
    print("\\begin{tabular}{|l|r|r|r|}")
    print("\\hline")
    print("\\textbf{Configuration} & \\textbf{Speedup} & \\textbf{Energy} & \\textbf{Area} \\\\")
    print("                       & \\textbf{vs CPU}  & \\textbf{Savings} & \\textbf{(mm²)} \\\\")
    print("\\hline")
    print(f"Software Baseline      & {baseline['speedup_vs_baseline']:5.1f}$\\times$ & {baseline['energy_savings_vs_baseline']:5.1f}$\\times$ & -- \\\\")
    print(f"+ Digital Acceleration & {digital_rollout['speedup_vs_baseline']:5.1f}$\\times$ & {digital_rollout['energy_savings_vs_baseline']:5.1f}$\\times$ & {digital_rollout['area_mm2']:.4f} \\\\")
    print(f"Full IMC System        & {full_system['speedup_vs_baseline']:5.1f}$\\times$ & {full_system['energy_savings_vs_baseline']:5.1f}$\\times$ & {full_system['area_mm2']:.4f} \\\\")
    print("\\hline")
    print("\\end{tabular}")
    print("\\end{table}")
    print()


def main():
    """Generate all LaTeX tables"""

    print("\n" + "="*80)
    print("LATEX TABLE GENERATOR FOR ABLATION STUDIES")
    print("="*80)
    print()
    print("Generating publication-ready LaTeX tables...")
    print("Copy-paste the output below into publication materials")
    print("="*80)

    # Check if data files exist
    prog_file = '../../experiment_results/ablation_progressive_buildup.csv'
    alt_file = '../../experiment_results/ablation_design_alternatives.csv'

    if not os.path.exists(prog_file):
        print(f"\n❌ Error: {prog_file} not found!")
        print("   Run ablation_progressive_buildup.py first")
        return

    if not os.path.exists(alt_file):
        print(f"\n❌ Error: {alt_file} not found!")
        print("   Run ablation_design_alternatives.py first")
        return

    # Generate tables
    generate_progressive_buildup_table()
    generate_design_alternatives_table()
    generate_compact_comparison_table()

    print("\n" + "="*80)
    print("✅ LaTeX tables generated successfully!")
    print("="*80)
    print()
    print("Usage:")
    print("1. Copy the table code above")
    print("2. Paste into your LaTeX document")
    print("3. Ensure you have these packages: \\usepackage{multirow,array}")
    print()


if __name__ == "__main__":
    main()
