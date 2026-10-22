#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Generate Plots for Ablation Studies
=====================================

Creates publication-quality figures for both ablation studies:
1. Progressive build-up bar chart
2. Design alternatives comparison
3. (Optional) Component breakdown

All plots are 300 DPI, publication-ready
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import os

# Set publication-quality defaults
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 11
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'


def plot_progressive_buildup():
    """Plot speedup and energy gains across optimization stages."""

    # Load data
    progressive_df = pd.read_csv('../../experiment_results/ablation_progressive_buildup.csv')

    # Get 9×9 board data
    progressive_9x9 = progressive_df[progressive_df['board_size'] == 9].copy()

    # Extract data
    configurations = progressive_9x9['configuration_name'].tolist()
    speedups = progressive_9x9['speedup_vs_baseline'].tolist()
    energy_savings = progressive_9x9['energy_savings_vs_baseline'].tolist()

    # Shorten configuration names
    config_labels = []
    for configuration_name in configurations:
        if "Baseline" in configuration_name:
            config_labels.append("Baseline\n(CPU)")
        elif "+ Digital Selection" in configuration_name:
            config_labels.append("+Digital\nSelection")
        elif "+ TCAM Selection" in configuration_name:
            config_labels.append("+TCAM\nSelection")
        elif "+ Digital Rollout" in configuration_name:
            config_labels.append("+Digital\nRollout")
        elif "+ IMC Rollout" in configuration_name:
            config_labels.append("+IMC\nRollout")
        elif "+ Hardware Expansion" in configuration_name:
            config_labels.append("+Hardware\nExpansion")
        elif "Full" in configuration_name:
            config_labels.append("Full\nAccelerator")
        else:
            config_labels.append(configuration_name[:15])

    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Colors for each stage
    colors = ['#e74c3c', '#e67e22', '#f39c12', '#3498db', '#2ecc71', '#27ae60', '#16a085']

    # Plot 1: Speedup
    x = np.arange(len(config_labels))
    bars1 = ax1.bar(x, speedups, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)

    ax1.set_xlabel('Configuration', fontweight='bold')
    ax1.set_ylabel('Speedup vs CPU Baseline (×)', fontweight='bold')
    ax1.set_title('Progressive Speedup Improvement (9×9 Board)', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(config_labels, rotation=0, ha='center', fontsize=9)
    ax1.set_yscale('log')
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    ax1.set_axisbelow(True)

    # Add value labels on bars
    for bar, speedup in zip(bars1, speedups):
        if speedup < 2.0:
            label_text = f'{speedup:.1f}×'
        else:
            label_text = f'{speedup:.0f}×'

        ax1.text(bar.get_x() + bar.get_width()/2, speedup * 1.1,
                label_text, ha='center', va='bottom', fontsize=9, fontweight='bold')

    # Plot 2: Energy Savings
    bars2 = ax2.bar(x, energy_savings, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)

    ax2.set_xlabel('Configuration', fontweight='bold')
    ax2.set_ylabel('Energy Savings vs CPU Baseline (×)', fontweight='bold')
    ax2.set_title('Progressive Energy Efficiency Improvement (9×9 Board)', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(config_labels, rotation=0, ha='center', fontsize=9)
    ax2.set_yscale('log')
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    ax2.set_axisbelow(True)

    # Add value labels
    for bar, val in zip(bars2, energy_savings):
        if val < 2.0:
            label_text = f'{val:.1f}×'
        else:
            label_text = f'{val:.0f}×'

        ax2.text(bar.get_x() + bar.get_width()/2, val * 1.1,
                label_text, ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()

    # Save
    os.makedirs('../../plots', exist_ok=True)
    plt.savefig('../../plots/ablation_progressive_speedup.png', dpi=300)
    print("✅ Saved: plots/ablation_progressive_speedup.png")
    plt.close()


def plot_design_alternatives():
    """Compare implementation alternatives for each hardware module."""

    # Load data
    alternatives_df = pd.read_csv('../../experiment_results/ablation_design_alternatives.csv')

    # Get 9×9 board data
    alternatives_9x9 = alternatives_df[alternatives_df['board_size'] == 9].copy()

    # Create figure with three subplots (one per module)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    modules = [
        ('Rollout Unit', axes[0]),
        ('Selection Unit', axes[1]),
        ('Expansion Unit', axes[2])
    ]

    for module_name, ax in modules:
        module_df = alternatives_9x9[alternatives_9x9['module_name'] == module_name].copy()

        # Extract data
        implementations = module_df['implementation'].tolist()
        speedups = module_df['speedup_vs_baseline'].tolist()
        chosen = module_df['chosen'].tolist()

        # Shorten implementation names
        impl_labels = []
        for implementation in implementations:
            impl_clean = implementation.replace(" (chosen)", "").replace("(chosen)", "").strip()
            if "Software" in impl_clean and module_name == "Rollout Unit":
                impl_labels.append("Software\n(CPU)")
            elif "Software" in impl_clean:
                impl_labels.append("Software")
            elif "Digital ASIC" in impl_clean:
                impl_labels.append("Digital\nASIC")
            elif "FPGA" in impl_clean:
                impl_labels.append("FPGA")
            elif "IMC Crossbar" in impl_clean:
                impl_labels.append("IMC\nCrossbar")
            elif "Sequential" in impl_clean:
                impl_labels.append("Sequential\nFSM")
            elif "Hash Table" in impl_clean:
                impl_labels.append("Hash\nTable")
            elif "TCAM" in impl_clean:
                impl_labels.append("TCAM")
            elif "Digital Hardware" in impl_clean:
                impl_labels.append("Digital\nHW")
            elif "Optimized" in impl_clean:
                impl_labels.append("Optimized\nHW")
            else:
                impl_labels.append(impl_clean[:10])

        # Colors: red for baseline, gray for alternatives, green for chosen
        colors = []
        for i, is_chosen in enumerate(chosen):
            if i == 0:  # Baseline
                colors.append('#e74c3c')
            elif is_chosen:  # Chosen design
                colors.append('#2ecc71')
            else:  # Alternative
                colors.append('#95a5a6')

        # Plot
        x = np.arange(len(impl_labels))
        bars = ax.bar(x, speedups, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)

        # Add labels
        ax.set_xlabel('Implementation', fontweight='bold')
        ax.set_ylabel('Speedup vs Baseline (×)', fontweight='bold')
        ax.set_title(module_name.replace(" Unit", ""), fontweight='bold', fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(impl_labels, rotation=0, ha='center', fontsize=9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)

        # Add value labels and checkmarks
        for i, (bar, val, is_chosen) in enumerate(zip(bars, speedups, chosen)):
            # Value label
            if val < 2.0:
                label_text = f'{val:.1f}×'
            else:
                label_text = f'{val:.0f}×'

            ax.text(bar.get_x() + bar.get_width()/2, val * 1.05,
                   label_text, ha='center', va='bottom', fontsize=9, fontweight='bold')

            # Checkmark for chosen design
            if is_chosen:
                ax.text(bar.get_x() + bar.get_width()/2, val * 0.5,
                       '✓', ha='center', va='center', fontsize=16,
                       color='white', fontweight='bold')

    plt.tight_layout()

    # Save
    plt.savefig('../../plots/ablation_design_alternatives.png', dpi=300)
    print("✅ Saved: plots/ablation_design_alternatives.png")
    plt.close()


def plot_scalability():
    """Plot full-system scaling across board sizes."""

    # Load data
    progressive_df = pd.read_csv('../../experiment_results/ablation_progressive_buildup.csv')

    # Get Full Accelerator data for all board sizes
    full_system_df = progressive_df[progressive_df['configuration_name'] == 'Full Accelerator'].copy()

    # Sort by board size
    full_system_df = full_system_df.sort_values('board_size')

    board_sizes = full_system_df['board_size'].tolist()
    speedups = full_system_df['speedup_vs_baseline'].tolist()
    energy_savings = full_system_df['energy_savings_vs_baseline'].tolist()
    tops_per_watt = full_system_df['tops_per_watt'].tolist()

    # Create figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Plot 1: Speedup and Energy vs Board Size
    board_labels = [f'{n}×{n}' for n in board_sizes]
    x = np.arange(len(board_labels))
    width = 0.35

    bars1 = ax1.bar(x - width/2, speedups, width, label='Speedup',
                    color='#3498db', alpha=0.8, edgecolor='black', linewidth=0.5)
    bars2 = ax1.bar(x + width/2, energy_savings, width, label='Energy Savings',
                    color='#2ecc71', alpha=0.8, edgecolor='black', linewidth=0.5)

    ax1.set_xlabel('Board Size', fontweight='bold')
    ax1.set_ylabel('Improvement vs CPU Baseline (×)', fontweight='bold')
    ax1.set_title('Full Accelerator: Scalability Analysis', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(board_labels)
    ax1.legend(loc='upper left')
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    ax1.set_axisbelow(True)

    # Add value labels
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, height * 1.02,
                f'{height:.0f}×', ha='center', va='bottom', fontsize=9)

    for bar in bars2:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, height * 1.02,
                f'{height:.0f}×', ha='center', va='bottom', fontsize=9)

    # Plot 2: Energy Efficiency (TOPS/W)
    bars3 = ax2.bar(x, tops_per_watt, color='#9b59b6', alpha=0.8,
                    edgecolor='black', linewidth=0.5)

    ax2.set_xlabel('Board Size', fontweight='bold')
    ax2.set_ylabel('Energy Efficiency (TOPS/W)', fontweight='bold')
    ax2.set_title('Compute Efficiency Across Board Sizes', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(board_labels)
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    ax2.set_axisbelow(True)

    # Add value labels
    for bar in bars3:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, height * 1.02,
                f'{height:.0f}', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()

    # Save
    plt.savefig('../../plots/ablation_scalability.png', dpi=300)
    print("✅ Saved: plots/ablation_scalability.png")
    plt.close()


def main():
    """Generate all plots"""

    print("\n" + "="*80)
    print("GENERATING ABLATION STUDY PLOTS")
    print("="*80)
    print()

    # Check if data files exist
    prog_file = '../../experiment_results/ablation_progressive_buildup.csv'
    alt_file = '../../experiment_results/ablation_design_alternatives.csv'

    if not os.path.exists(prog_file):
        print(f"❌ Error: {prog_file} not found!")
        print("   Run ablation_progressive_buildup.py first")
        return

    if not os.path.exists(alt_file):
        print(f"❌ Error: {alt_file} not found!")
        print("   Run ablation_design_alternatives.py first")
        return

    # Generate plots
    print("Generating plots...")
    plot_progressive_buildup()
    plot_design_alternatives()
    plot_scalability()

    print()
    print("="*80)
    print("✅ All plots generated successfully!")
    print("="*80)
    print()
    print("Generated files:")
    print("  📊 plots/ablation_progressive_speedup.png (Progressive build-up)")
    print("  📊 plots/ablation_design_alternatives.png (Design alternatives)")
    print("  📊 plots/ablation_scalability.png (Scalability across board sizes)")
    print()
    print("All plots are 300 DPI, ready for publication")
    print("="*80)
    print()


if __name__ == "__main__":
    main()
