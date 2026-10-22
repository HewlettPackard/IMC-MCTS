#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Generate LaTeX Tables from Ablation Study Results
==================================================

Reads the JSON output from both ablation studies and generates
publication-ready LaTeX tables.
"""

import json
import pandas as pd
from pathlib import Path


def generate_progressive_buildup_table():
    """Build the progressive build-up table for the 9×9 board."""

    json_file = Path('../../experiment_results/ablation_progressive_buildup_v2.json')

    with open(json_file, 'r') as f:
        data = json.load(f)

    progressive_df = pd.DataFrame(data)

    # Filter for 9x9 board only
    progressive_9x9 = progressive_df[progressive_df['board_size'] == 9].copy()

    print("="*80)
    print("TABLE 1: PROGRESSIVE BUILD-UP ABLATION (9×9 BOARD)")
    print("="*80)
    print()

    latex = r"""\begin{table}[t]
\centering
\caption{Progressive Build-Up Ablation Study for 9×9 Go Board}
\label{tab:progressive_buildup}
\begin{tabular}{lrrrr}
\toprule
\textbf{Configuration} & \textbf{Latency} & \textbf{Energy} & \textbf{Speedup} & \textbf{Energy} \\
                       & \textbf{(ns)}    & \textbf{(pJ)}   & \textbf{vs Baseline} & \textbf{Savings} \\
\midrule
"""

    for _, row in progressive_9x9.iterrows():
        config_name = row['configuration_name']
        latency = row['latency_per_iter_ns']
        energy = row['total_energy_pj']
        speedup = row['speedup_vs_baseline']
        savings = row['energy_savings_vs_baseline']

        # Format configuration name for LaTeX
        config_name = config_name.replace('+ ', '')
        config_name = config_name.replace('(ARM CPU)', '(baseline)')

        latex += f"{config_name:<30s} & {latency:>10,.0f} & {energy:>12,.0f} & {speedup:>6.1f}$\\times$ & {savings:>6.1f}$\\times$ \\\\\n"

    latex += r"""\bottomrule
\end{tabular}
\end{table}

% Energy Breakdown for Full Accelerator:
% - ADC/DAC: """ + f"{progressive_9x9.iloc[-1]['adc_dac_energy_pj']:.0f} pJ ({progressive_9x9.iloc[-1]['adc_dac_energy_pj']/progressive_9x9.iloc[-1]['total_energy_pj']*100:.0f}%)\n"
    latex += r"""% - Compute: """ + f"{progressive_9x9.iloc[-1]['compute_energy_pj']:.0f} pJ ({progressive_9x9.iloc[-1]['compute_energy_pj']/progressive_9x9.iloc[-1]['total_energy_pj']*100:.0f}%)\n"
    latex += r"""% - Peripheral: """ + f"{progressive_9x9.iloc[-1]['peripheral_energy_pj']:.0f} pJ ({progressive_9x9.iloc[-1]['peripheral_energy_pj']/progressive_9x9.iloc[-1]['total_energy_pj']*100:.0f}%)\n"

    print(latex)
    print()

    return latex


def generate_design_alternatives_table():
    """Build the 9×9 table of module implementation alternatives."""

    json_file = Path('../../experiment_results/ablation_design_alternatives_v2.json')

    with open(json_file, 'r') as f:
        data = json.load(f)

    alternatives_df = pd.DataFrame(data)

    # Filter for 9x9 board only
    alternatives_9x9 = alternatives_df[alternatives_df['board_size'] == 9].copy()

    print("="*80)
    print("TABLE 2: DESIGN ALTERNATIVES ABLATION (9×9 BOARD)")
    print("="*80)
    print()

    latex = r"""\begin{table}[t]
\centering
\caption{Design Alternatives for Each Module (9×9 Go Board)}
\label{tab:design_alternatives}
\begin{tabular}{llrrrr}
\toprule
\textbf{Module} & \textbf{Implementation} & \textbf{Latency} & \textbf{Energy} & \textbf{Speedup} & \textbf{Energy} \\
                &                         & \textbf{(ns)}    & \textbf{(pJ)}   & \textbf{vs Base} & \textbf{Savings} \\
\midrule
"""

    # Group by module
    for module in alternatives_9x9['module_name'].unique():
        module_df = alternatives_9x9[alternatives_9x9['module_name'] == module]

        for i, (_, row) in enumerate(module_df.iterrows()):
            impl = row['implementation']
            latency = row['latency_per_op_ns']
            energy = row['total_energy_pj']
            speedup = row['speedup_vs_baseline']
            savings = row['energy_savings_vs_baseline']
            chosen = row['chosen']

            # Format implementation name
            impl = impl.replace('(chosen)', '').strip()
            if chosen:
                impl = r'\textbf{' + impl + r'}'

            # First row of module: include module name
            if i == 0:
                module_name = module.replace('Unit', '')
                latex += f"{module_name:<15s} & {impl:<30s} & {latency:>8.1f} & {energy:>10,.0f} & {speedup:>5.1f}$\\times$ & {savings:>5.1f}$\\times$ \\\\\n"
            else:
                latex += f"{'':15s} & {impl:<30s} & {latency:>8.1f} & {energy:>10,.0f} & {speedup:>5.1f}$\\times$ & {savings:>5.1f}$\\times$ \\\\\n"

        # Add separator between modules
        if module != alternatives_9x9['module_name'].unique()[-1]:
            latex += r"\midrule" + "\n"

    latex += r"""\bottomrule
\end{tabular}
\vspace{-2mm}
\begin{tablenotes}[flushleft]
\small
\item Bold entries indicate chosen design for Accelerator.
\end{tablenotes}
\end{table}
"""

    print(latex)
    print()

    return latex


def save_tables_to_file():
    """Write both ablation tables to one LaTeX text file."""

    output_file = Path('ablation_tables_latex.txt')

    with open(output_file, 'w') as f:
        f.write("% ============================================================================\n")
        f.write("% ABLATION STUDY LATEX TABLES\n")
        f.write("% Generated from ablation_progressive_buildup_v2.py and\n")
        f.write("% ablation_design_alternatives_v2.py\n")
        f.write("%\n")
        f.write("% Uses REALISTIC speedup numbers with complete ADC/DAC specs!\n")
        f.write("% 9×9 Board: 640× speedup, 366× energy savings (not 6,099×!)\n")
        f.write("% ============================================================================\n\n")

        f.write("% Required packages:\n")
        f.write("% \\usepackage{booktabs}\n")
        f.write("% \\usepackage{threeparttable}\n\n")

        table1 = generate_progressive_buildup_table()
        f.write(table1)
        f.write("\n\n")

        table2 = generate_design_alternatives_table()
        f.write(table2)

    print("="*80)
    print(f"✅ LaTeX tables saved to: {output_file}")
    print("="*80)
    print()

    return output_file


if __name__ == "__main__":
    print("\n" + "="*80)
    print("GENERATING LATEX TABLES FROM ABLATION STUDIES")
    print("="*80)
    print()

    output_file = save_tables_to_file()

    print("To use in publication materials, copy the tables from:")
    print(f"  {output_file.absolute()}")
    print()
    print("Make sure to include these packages in your LaTeX preamble:")
    print("  \\usepackage{booktabs}")
    print("  \\usepackage{threeparttable}")
    print()
    print("✅ Done!")
    print()
