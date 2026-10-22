#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Figure 3a: replot archived energy per iteration within a move (µJ).
Reads package/data/figure_inputs/fig3a/iteration_energy.csv; writes into
package/figures/generated/. Run through figures/regenerate.py.
No processor benchmark or simulator search is executed."""

import sys
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# plotstyle is a sibling module in paper/figure/.
import plotstyle

DATA_DIR = Path(__file__).resolve().parents[2] / "data/figure_inputs/fig3a"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "generated"


def extract_board_num(board_str):
    return int(board_str.split('x')[0])


def load_energy():
    """Load the energy CSV and sort rows by board size numerically."""
    df = pd.read_csv(DATA_DIR / "iteration_energy.csv")
    df['_sort_key'] = df['board_size'].apply(extract_board_num)
    df = df.sort_values('_sort_key').drop('_sort_key', axis=1)
    return df


def plot_energy(df):
    """Energy-vs-board-size line plot: one styled line per platform."""
    board_sizes = df['board_size'].values
    accelerator = df['This Work'].values
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
    ax.set_ylabel('Energy per iteration\nwithin a move (μJ)', fontsize=plotstyle.FONT_SIZES['large'])
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
    print("Replotting Figure 3a: archived iteration energy...")
    df = load_energy()
    fig = plot_energy(df)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plotstyle.save_fig(fig, OUTPUT_DIR / "fig3a_iteration_energy.png", format='png')
    plotstyle.save_fig(fig, OUTPUT_DIR / "fig3a_iteration_energy.pdf", format='pdf')
    print(f"Saved fig3a_iteration_energy.png and .pdf to {OUTPUT_DIR}")

    plt.close(fig)

if __name__ == '__main__': main()
