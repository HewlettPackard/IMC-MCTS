#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Figure 1: bottleneck scaling across board sizes.

Grouped stacked bars of MCTS phase time (%) per platform x board size, showing
how the dominant bottleneck persists/shifts. Reads paper/results/
fig01_bottleneck_scaling.csv, writes fig_01_bottleneck_scaling.{png,pdf} into
paper/figure/.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# plotstyle is a sibling module in paper/figure/.
sys.path.insert(0, str(Path(__file__).parent))
import plotstyle

DATA_DIR = Path(__file__).resolve().parent.parent / "results"
OUTPUT_DIR = Path(__file__).resolve().parent          # paper/figure/

# Phase colors (consistent across all plots).
phase_colors = {
    'Selection': '#6BB6FF',      # Baby blue
    'Expansion': '#2ca02c',      # Green
    'Rollout': '#ff7f0e',        # Orange/yellowish
    'Backpropagation': '#9467bd' # Purple
}
# Hatch per platform.
platform_hatches = {
    'CPU': '',        # Solid (no hatch)
    'GPU-F': '///',   # Diagonal lines
    'GPU-M': 'xxx'    # Cross-hatch
}
platform_short = ['CPU', 'GPU-F', 'GPU-M']


def extract_board_num(board_str):
    return int(board_str.split('x')[0])


def load():
    return pd.read_csv(DATA_DIR / "fig01_bottleneck_scaling.csv")


def plot(df):
    """Grouped stacked bars: one bar group per board size, one bar per platform,
    stacked Rollout/Expansion/Backprop/Selection (bottom to top)."""
    platforms = df['platform'].unique()
    board_sizes = sorted(df['board_size'].unique(), key=extract_board_num)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.set_facecolor(plotstyle.BACKGROUNDS['white'])
    ax.grid(True, alpha=0.7, linewidth=0.5)

    n_platforms = len(platforms)
    bar_width = 0.25
    x_pos = np.arange(len(board_sizes))

    for i, platform in enumerate(platforms):
        df_platform = df[df['platform'] == platform].copy()
        # Sort by board size numerically (not alphabetically).
        df_platform['board_num'] = df_platform['board_size'].apply(extract_board_num)
        df_platform = df_platform.sort_values('board_num')

        selection = df_platform['selection_pct'].values
        expansion = df_platform['expansion_pct'].values
        rollout = df_platform['rollout_pct'].values
        backprop = df_platform['backpropagation_pct'].values

        x = x_pos + i * bar_width
        hatch_pattern = platform_hatches[platform_short[i]]

        # Stack largest-to-smallest: Rollout (bottom), Expansion, Backprop, Selection (top).
        ax.bar(x, rollout, bar_width,
               label='Rollout' if i == 0 else '',
               color=phase_colors['Rollout'], edgecolor='black', linewidth=0.5,
               hatch=hatch_pattern)
        ax.bar(x, expansion, bar_width, bottom=rollout,
               label='Expansion' if i == 0 else '',
               color=phase_colors['Expansion'], edgecolor='black', linewidth=0.5,
               hatch=hatch_pattern)
        ax.bar(x, backprop, bar_width, bottom=rollout+expansion,
               label='Backpropagation' if i == 0 else '',
               color=phase_colors['Backpropagation'], edgecolor='black', linewidth=0.5,
               hatch=hatch_pattern)
        ax.bar(x, selection, bar_width, bottom=rollout+expansion+backprop,
               label='Selection' if i == 0 else '',
               color=phase_colors['Selection'], edgecolor='black', linewidth=0.5,
               hatch=hatch_pattern)

    ax.set_xlabel('Board Size', fontsize=plotstyle.FONT_SIZES['large'])
    ax.set_ylabel('Execution Time (%)', fontsize=plotstyle.FONT_SIZES['large'])
    ax.set_xticks(x_pos + bar_width * (n_platforms - 1) / 2)
    ax.set_xticklabels(board_sizes, fontsize=plotstyle.FONT_SIZES['medium'])
    ax.set_xlim([-0.3, len(board_sizes) - 0.3])
    ax.set_ylim([0, 105])

    # Two legends: phases (top-left), platform hatches (top-right). add_artist
    # re-attaches the phase legend that the second ax.legend() would otherwise drop.
    phase_legend = ax.legend(loc='upper left', fontsize=plotstyle.FONT_SIZES['medium'],
                             ncol=2, frameon=True, bbox_to_anchor=(-0.1, 1.3))
    platform_handles = [
        Patch(facecolor='white', edgecolor='black', hatch=platform_hatches['CPU'], label='CPU'),
        Patch(facecolor='white', edgecolor='black', hatch=platform_hatches['GPU-F'], label='GPU-F'),
        Patch(facecolor='white', edgecolor='black', hatch=platform_hatches['GPU-M'], label='GPU-M')
    ]
    ax.legend(handles=platform_handles, loc='upper right',
              fontsize=plotstyle.FONT_SIZES['medium'],
              ncol=2, frameon=True, bbox_to_anchor=(1.0, 1.3))
    ax.add_artist(phase_legend)

    ax.tick_params(axis='both', which='major', labelsize=plotstyle.FONT_SIZES['medium'])
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    return fig


def main():
    print("Generating Figure 1: Bottleneck Scaling...")
    df = load()
    fig = plot(df)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plotstyle.save_fig(fig, OUTPUT_DIR / "fig_01_bottleneck_scaling.png", format='png')
    plotstyle.save_fig(fig, OUTPUT_DIR / "fig_01_bottleneck_scaling.pdf", format='pdf')
    print(f"Saved fig_01_bottleneck_scaling.png and .pdf to {OUTPUT_DIR}")
    print("  Key insight: CPU stays rollout-bound (~94%), GPU shifts from expansion to backprop")

    plt.close()


if __name__ == "__main__":
    main()
