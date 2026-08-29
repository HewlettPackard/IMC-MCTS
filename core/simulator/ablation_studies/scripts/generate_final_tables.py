#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Generate Final LaTeX Tables with ACTUAL COMPUTED VALUES
========================================================

Uses the v2 ablation study results with complete energy accounting
to generate publication-ready tables with REAL numbers, not estimates.
"""

import pandas as pd
import numpy as np
import os


def generate_table1_progressive_buildup():
    """Table 1: Progressive Build-up with REAL computed values"""

    print("\n" + "="*80)
    print("TABLE 1: PROGRESSIVE OPTIMIZATION BUILD-UP (REAL COMPUTED VALUES)")
    print("="*80)
    print()

    # Load v2 data
    progressive_df = pd.read_csv('../../experiment_results/ablation_progressive_buildup_v2.csv')
    progressive_9x9 = progressive_df[progressive_df['board_size'] == 9].copy()

    print("\\begin{table*}[t]")
    print("\\centering")
    print("\\caption{Progressive Optimization Analysis (9$\\times$9 Board, 22nm Technology). ")
    print("\\textbf{Baseline}: ARM Cortex-M7 @ 400 MHz (edge deployment target). ")
    print("All designs include complete system costs: compute energy, ADC/DAC conversions (8-bit), ")
    print("SRAM accesses (200 pJ/access from CACTI 7.0), and peripheral logic. ")
    print("Energy accounting is \\textbf{conservative} - includes all overheads.}")
    print("\\label{tab:progressive_buildup}")
    print("\\begin{tabular}{|l|r|r|r|r|}")
    print("\\hline")
    print("\\textbf{Configuration} & \\textbf{Speedup} & \\textbf{Energy} & \\textbf{Energy} & \\textbf{Area} \\\\")
    print("& \\textbf{vs M7}  & \\textbf{Savings}& \\textbf{Total (pJ)} & \\textbf{(mm²)} \\\\")
    print("\\hline")

    # Configuration name mapping
    name_map = {
        'Baseline (ARM CPU)': 'Baseline (Cortex-M7)',
        '+ Digital Selection': '+ Digital Selection',
        '+ TCAM Selection': '+ TCAM Selection (ours)',
        '+ Digital Rollout': '+ Digital Rollout',
        '+ IMC Rollout': '+ IMC Rollout (ours)',
        '+ Hardware Expansion': '+ Hardware Expansion (ours)',
        'Full Accelerator': 'Full Accelerator (ours)'
    }

    for _, row in progressive_9x9.iterrows():
        config_name = name_map.get(row['configuration_name'], row['configuration_name'])
        speedup = row['speedup_vs_baseline']
        energy_savings = row['energy_savings_vs_baseline']
        total_energy = row['total_energy_pj']
        area = row['area_mm2']

        # Format area
        if area < 0.0001:
            area_str = "--"
        else:
            area_str = f"{area:.4f}"

        print(f"{config_name:35s} & {speedup:7.1f}$\\times$ & {energy_savings:6.1f}$\\times$ & "
              f"{total_energy:10.1f} & {area_str:8s} \\\\")

    print("\\hline")
    print("\\end{tabular}")
    print("\\vspace{2mm}")
    print("\\begin{flushleft}")
    print("\\footnotesize")
    print("\\textbf{Energy Breakdown (9×9 Full Accelerator)}:")

    # Get full system breakdown
    full = progressive_9x9[progressive_9x9['configuration_name'] == 'Full Accelerator'].iloc[0]
    print(f"\\\\• Analog compute: {full['compute_energy_pj']:.1f} pJ")
    print(f"\\\\• ADC/DAC (8-bit): {full['adc_dac_energy_pj']:.1f} pJ")
    print(f"\\\\• SRAM accesses ({full['num_memory_accesses']} reads × 200 pJ): {full['memory_energy_pj']:.1f} pJ")
    print(f"\\\\• Peripherals (TCAM, control): {full['peripheral_energy_pj']:.1f} pJ")
    print(f"\\\\• \\textbf{{Total: {full['total_energy_pj']:.1f} pJ}} vs Baseline: {progressive_9x9.iloc[0]['total_energy_pj']:.1f} pJ")
    print("\\\\")
    mem_pct = 100 * (full['adc_dac_energy_pj'] + full['memory_energy_pj']) / full['total_energy_pj']
    print("\\\\\\textbf{{Technology}}: All normalized to a 22nm reference node. Digital baselines scaled from Eyeriss/DianNao @ 65nm.")
    print("\\\\\\textbf{{Memory dominates}}: {:.1f}\\% of total energy is memory/ADC/DAC, not analog compute.".format(mem_pct))
    print("\\\\\\textbf{{Realistic speedup}}: {:.0f}$\\times$ speedup (latency), {:.0f}$\\times$ energy savings (complete accounting).".format(
        full['speedup_vs_baseline'], full['energy_savings_vs_baseline']))
    print("\\end{flushleft}")
    print("\\end{table*}")
    print()


def generate_table2_design_alternatives():
    """Table 2: Design Alternatives with REAL computed values"""

    print("\n" + "="*80)
    print("TABLE 2: DESIGN ALTERNATIVES (REAL COMPUTED VALUES)")
    print("="*80)
    print()

    # Load v2 data
    alternatives_df = pd.read_csv('../../experiment_results/ablation_design_alternatives_v2.csv')
    alternatives_9x9 = alternatives_df[alternatives_df['board_size'] == 9].copy()

    print("\\begin{table*}[t]")
    print("\\centering")
    print("\\caption{Module Implementation Alternatives (9$\\times$9 Board) with Complete Energy Accounting. ")
    print("All at 22nm technology. Energy includes: compute, ADC/DAC (for IMC), memory (200 pJ/access), and peripherals.}")
    print("\\label{tab:design_alternatives}")
    print("\\begin{tabular}{|l|l|r|r|r|r|r|c|}")
    print("\\hline")
    print("\\textbf{Module} & \\textbf{Implementation} & \\textbf{Latency} & \\textbf{Compute} & \\textbf{ADC/DAC} & \\textbf{Memory} & \\textbf{Total} & \\textbf{Choice} \\\\")
    print("& & \\textbf{(ns)} & \\textbf{Energy (pJ)} & \\textbf{Energy (pJ)} & \\textbf{Energy (pJ)} & \\textbf{Energy (pJ)} & \\\\")
    print("\\hline")

    modules = alternatives_9x9['module_name'].unique()

    for module_idx, module in enumerate(modules):
        module_df = alternatives_9x9[alternatives_9x9['module_name'] == module]

        for row_number, (_, row) in enumerate(module_df.iterrows()):
            implementation = row['implementation']
            latency = row['latency_per_op_ns']
            compute = row['compute_energy_pj']
            adc_dac = row['adc_dac_energy_pj']
            memory = row['memory_energy_pj']
            total = row['total_energy_pj']
            chosen = row['chosen']

            # Choice marker
            choice_mark = "\\checkmark" if chosen else ""

            # Module name only on first row
            if row_number == 0:
                module_name = module.replace(" Unit", "")
            else:
                module_name = ""

            print(f"{module_name:10s} & {implementation:25s} & {latency:8.1f} & {compute:8.1f} & "
                  f"{adc_dac:8.1f} & {memory:9.1f} & {total:10.1f} & {choice_mark:10s} \\\\")

        # Add line between modules
        if module_idx < len(modules) - 1:
            print("\\hline")

    print("\\hline")
    print("\\end{tabular}")
    print("\\vspace{2mm}")
    print("\\begin{flushleft}")
    print("\\footnotesize")
    print("\\textbf{Key Insights}:")

    # Get chosen implementations
    imc = alternatives_9x9[(alternatives_9x9['module_name'] == 'Rollout Unit') &
                           (alternatives_9x9['implementation'] == 'IMC Crossbar (chosen)')].iloc[0]
    sw = alternatives_9x9[(alternatives_9x9['module_name'] == 'Rollout Unit') &
                          (alternatives_9x9['implementation'] == 'Software (ARM CPU)')].iloc[0]

    print(f"\\\\• \\textbf{{IMC Rollout}}: {imc['speedup_vs_baseline']:.0f}$\\times$ faster, "
          f"{imc['energy_savings_vs_baseline']:.1f}$\\times$ energy savings vs software")
    print(f"\\\\• \\textbf{{ADC/DAC overhead}}: {imc['adc_dac_energy_pj']:.0f} pJ "
          f"({100*imc['adc_dac_energy_pj']/imc['total_energy_pj']:.1f}\\% of IMC total)")
    print(f"\\\\• \\textbf{{Memory dominates}}: {imc['memory_energy_pj']:.0f} pJ "
          f"({100*imc['memory_energy_pj']/imc['total_energy_pj']:.1f}\\% of IMC total)")
    print(f"\\\\• \\textbf{{Analog compute}}: Only {imc['compute_energy_pj']:.1f} pJ "
          f"({100*imc['compute_energy_pj']/imc['total_energy_pj']:.1f}\\% of total)")
    print("\\\\")
    compute_only_speedup = sw['compute_energy_pj'] / imc['compute_energy_pj']
    print("\\\\\\textbf{{Real speedup}}: Not {:.0f}$\\times$ (compute-only), but {:.0f}$\\times$ (complete system).".format(
        compute_only_speedup, imc['energy_savings_vs_baseline']))
    print("\\\\\\textbf{{Why?}} Memory and ADC/DAC energy cannot be ignored in realistic IMC designs.")
    print("\\end{flushleft}")
    print("\\end{table*}")
    print()


def generate_table3_board_sizes():
    """Table 3: Scaling across board sizes"""

    print("\n" + "="*80)
    print("TABLE 3: SCALING ACROSS BOARD SIZES (REAL COMPUTED VALUES)")
    print("="*80)
    print()

    # Load v2 data
    progressive_df = pd.read_csv('../../experiment_results/ablation_progressive_buildup_v2.csv')
    full_system_df = progressive_df[progressive_df['configuration_name'] == 'Full Accelerator'].copy()

    print("\\begin{table}[t]")
    print("\\centering")
    print("\\caption{Full Accelerator Performance Across Board Sizes (vs ARM Cortex-M7 @ 22nm). ")
    print("All designs include complete system costs (compute, ADC/DAC, memory, peripherals).}")
    print("\\label{tab:board_sizes}")
    print("\\begin{tabular}{|c|r|r|r|r|}")
    print("\\hline")
    print("\\textbf{Board} & \\textbf{Speedup} & \\textbf{Energy} & \\textbf{Total Energy} & \\textbf{Area} \\\\")
    print("\\textbf{Size} & \\textbf{vs M7} & \\textbf{Savings} & \\textbf{(pJ)} & \\textbf{(mm²)} \\\\")
    print("\\hline")

    for _, row in full_system_df.iterrows():
        board = row['board_size']
        speedup = row['speedup_vs_baseline']
        energy_savings = row['energy_savings_vs_baseline']
        total_energy = row['total_energy_pj']
        area = row['area_mm2']

        print(f"{board:d}$\\times${board:d} & {speedup:7.1f}$\\times$ & {energy_savings:6.1f}$\\times$ & "
              f"{total_energy:10.1f} & {area:.4f} \\\\")

    print("\\hline")
    print("\\end{tabular}")
    print("\\vspace{2mm}")
    print("\\begin{flushleft}")
    print("\\footnotesize")
    print("\\textbf{Scaling trends}:")
    print("\\\\• Energy savings improve with board size (more computation to amortize ADC/DAC overhead)")
    print("\\\\• Speedup increases due to software becoming relatively slower for larger boards")
    print("\\\\• All numbers include \\textbf{complete} energy accounting (not just compute)")
    print("\\end{flushleft}")
    print("\\end{table}")
    print()


def generate_summary():
    """Print summary of key results"""

    print("\n" + "="*80)
    print("SUMMARY: KEY RESULTS WITH COMPLETE ENERGY ACCOUNTING")
    print("="*80)
    print()

    # Load both datasets
    progressive_df = pd.read_csv('../../experiment_results/ablation_progressive_buildup_v2.csv')
    alternatives_df = pd.read_csv('../../experiment_results/ablation_design_alternatives_v2.csv')

    # 9×9 Full Accelerator
    full_9x9 = progressive_df[(progressive_df['board_size'] == 9) &
                              (progressive_df['configuration_name'] == 'Full Accelerator')].iloc[0]

    # 9×9 IMC vs Software
    imc_9x9 = alternatives_df[(alternatives_df['board_size'] == 9) &
                              (alternatives_df['module_name'] == 'Rollout Unit') &
                              (alternatives_df['implementation'] == 'IMC Crossbar (chosen)')].iloc[0]
    sw_9x9 = alternatives_df[(alternatives_df['board_size'] == 9) &
                             (alternatives_df['module_name'] == 'Rollout Unit') &
                             (alternatives_df['implementation'] == 'Software (ARM CPU)')].iloc[0]

    print("9×9 Board Results:")
    print(f"  Full Accelerator speedup:       {full_9x9['speedup_vs_baseline']:7.1f}×")
    print(f"  Full Accelerator energy savings: {full_9x9['energy_savings_vs_baseline']:7.1f}×")
    print()
    print("Energy Breakdown (Full Accelerator):")
    print(f"  Compute:      {full_9x9['compute_energy_pj']:8.1f} pJ ({100*full_9x9['compute_energy_pj']/full_9x9['total_energy_pj']:5.2f}%)")
    print(f"  ADC/DAC:      {full_9x9['adc_dac_energy_pj']:8.1f} pJ ({100*full_9x9['adc_dac_energy_pj']/full_9x9['total_energy_pj']:5.2f}%)")
    print(f"  Memory:       {full_9x9['memory_energy_pj']:8.1f} pJ ({100*full_9x9['memory_energy_pj']/full_9x9['total_energy_pj']:5.2f}%)")
    print(f"  Peripherals:  {full_9x9['peripheral_energy_pj']:8.1f} pJ ({100*full_9x9['peripheral_energy_pj']/full_9x9['total_energy_pj']:5.2f}%)")
    print(f"  TOTAL:        {full_9x9['total_energy_pj']:8.1f} pJ")
    print()
    print("IMC vs Software (Rollout only):")
    print(f"  IMC speedup:          {imc_9x9['speedup_vs_baseline']:10.1f}×")
    print(f"  IMC energy savings:    {imc_9x9['energy_savings_vs_baseline']:10.1f}×")
    print(f"  IMC total energy:      {imc_9x9['total_energy_pj']:10.1f} pJ")
    print(f"  Software total energy: {sw_9x9['total_energy_pj']:10.1f} pJ")
    print()
    print("Critical Insight:")
    print(f"  If we ONLY counted analog compute energy ({imc_9x9['compute_energy_pj']:.1f} pJ),")
    print(f"  we would claim {sw_9x9['compute_energy_pj']/imc_9x9['compute_energy_pj']:.0f}× energy savings.")
    print(f"  But with COMPLETE accounting (ADC/DAC + memory), it's {imc_9x9['energy_savings_vs_baseline']:.1f}×.")
    print(f"  Complete accounting keeps the energy comparison honest.")
    print()


def main():
    """Generate all final tables"""

    print("\n" + "="*80)
    print("FINAL LATEX TABLES WITH REAL COMPUTED VALUES")
    print("="*80)
    print()
    print("Using data from:")
    print("  - ablation_progressive_buildup_v2.csv")
    print("  - ablation_design_alternatives_v2.csv")
    print()
    print("All values are COMPUTED, not estimated!")
    print("="*80)

    # Check if data files exist
    prog_file = '../../experiment_results/ablation_progressive_buildup_v2.csv'
    alt_file = '../../experiment_results/ablation_design_alternatives_v2.csv'

    if not os.path.exists(prog_file):
        print(f"\n❌ Error: {prog_file} not found!")
        print("   Run ablation_progressive_buildup_v2.py first")
        return

    if not os.path.exists(alt_file):
        print(f"\n❌ Error: {alt_file} not found!")
        print("   Run ablation_design_alternatives_v2.py first")
        return

    # Generate tables
    generate_table1_progressive_buildup()
    generate_table2_design_alternatives()
    generate_table3_board_sizes()
    generate_summary()

    print("\n" + "="*80)
    print("✅ Final LaTeX tables generated successfully!")
    print("="*80)
    print()
    print("Next steps:")
    print("1. Copy the tables above into your LaTeX document")
    print("2. Add citations from generate_ablation_tables_with_citations.py")
    print("3. These are REAL computed values with complete energy accounting")
    print("4. Review values before external reporting.")
    print()


if __name__ == "__main__":
    main()
