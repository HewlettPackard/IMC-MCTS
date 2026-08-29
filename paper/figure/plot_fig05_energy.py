#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Figure 5: energy-scaling comparison.

Line plot of energy per iteration/move across platforms and board sizes
(log y-axis). Reads paper/results/fig05_energy_scaling.csv and writes
fig_05_energy_scaling.{png,pdf} into paper/figure/.
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# plotstyle is a sibling module in paper/figure/.
sys.path.insert(0, str(Path(__file__).parent))
import plotstyle

DATA_DIR = Path(__file__).resolve().parent.parent / "results"
OUTPUT_DIR = Path(__file__).resolve().parent          # paper/figure/


def extract_board_num(board_str):
    return int(board_str.split('x')[0])


def load_energy():
    """Load the energy CSV and sort rows by board size numerically."""
    df = pd.read_csv(DATA_DIR / "fig05_energy_scaling.csv")
    df['_sort_key'] = df['board_size'].apply(extract_board_num)
    df = df.sort_values('_sort_key').drop('_sort_key', axis=1)
    return df


def plot_energy(df):
    """Energy-vs-board-size line plot: one styled line per platform."""
    board_sizes = df['board_size'].values
    accelerator = df['Accelerator'].values
    cpu = df['CPU (AMD Threadripper 5945WX)'].values
    gpu_fair = df['GPU Fair (H100)'].values
    gpu_max = df['GPU Max (H100)'].values

    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.set_facecolor(plotstyle.BACKGROUNDS['white'])
    ax.grid(True, alpha=0.3, linewidth=0.5)

    # Styles per whatwewant.txt:
    #   Accelerator = blue diamond solid;  CPU = orange circle dashed;
    #   GPU Fair = green triangle dotted;  GPU Max = red triangle dash-dot.
    ax.plot(board_sizes, accelerator,
            color=plotstyle.DEFAULT_COLORS[0], marker='D', linestyle='-',
            linewidth=2.5, markersize=8, label='This Work')
    ax.plot(board_sizes, cpu,
            color=plotstyle.DEFAULT_COLORS[1], marker='o', linestyle='--',
            linewidth=2.5, markersize=8, label='CPU (AMD Threadripper 5945WX)')
    ax.plot(board_sizes, gpu_fair,
            color=plotstyle.DEFAULT_COLORS[2], marker='^', linestyle=':',
            linewidth=2.5, markersize=8, label='GPU Fair (H100)')
    ax.plot(board_sizes, gpu_max,
            color=plotstyle.DEFAULT_COLORS[3], marker='v', linestyle='-.',
            linewidth=2.5, markersize=8, label='GPU Max (H100)')

    ax.set_xlabel('Board Size (N×N)', fontsize=plotstyle.FONT_SIZES['large'])
    ax.set_ylabel('Energy per Inference/Move (μJ)', fontsize=plotstyle.FONT_SIZES['large'])
    ax.set_yscale('log')                                   # log y-axis per specs
    ax.set_xticks(range(len(board_sizes)))
    ax.set_xticklabels(board_sizes, fontsize=plotstyle.FONT_SIZES['medium'])
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.30),
              fontsize=plotstyle.FONT_SIZES['medium'], framealpha=0.9, ncol=2)
    ax.tick_params(axis='both', which='major', labelsize=plotstyle.FONT_SIZES['medium'])
    ax.tick_params(axis='both', which='minor', labelsize=plotstyle.FONT_SIZES['small'])
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    return fig


def main():
    print("Generating Figure 5: Energy Scaling...")
    df = load_energy()
    fig = plot_energy(df)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plotstyle.save_fig(fig, OUTPUT_DIR / "fig_05_energy_scaling.png", format='png')
    plotstyle.save_fig(fig, OUTPUT_DIR / "fig_05_energy_scaling.pdf", format='pdf')
    print(f"Saved fig_05_energy_scaling.png and .pdf to {OUTPUT_DIR}")

    # Energy-efficiency improvement vs CPU, per board size.
    board_sizes = df['board_size'].values
    accelerator = df['Accelerator'].values
    cpu = df['CPU (AMD Threadripper 5945WX)'].values
    for i, size in enumerate(board_sizes):
        if not np.isnan(cpu[i]) and not np.isnan(accelerator[i]):
            improvement = cpu[i] / accelerator[i]
            print(f"  {size}: {improvement:.0f}x more energy efficient than CPU")

    plt.close()


if __name__ == "__main__":
    main()
