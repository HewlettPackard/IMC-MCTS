#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Figure 4a: area breakdown by component.

Grouped stacked bars of Accelerator area (mm^2) per component, across board sizes
and play strengths (log y). Reads paper/results/fig04_area_breakdown.csv, writes
fig_04_area_breakdown.{png,pdf} into paper/figure/.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# plotstyle is a sibling module in paper/figure/.
sys.path.insert(0, str(Path(__file__).parent))
import plotstyle

DATA_DIR = Path(__file__).resolve().parent.parent / "results"
OUTPUT_DIR = Path(__file__).resolve().parent          # paper/figure/

PLAY_STRENGTHS = ['Low', 'Medium', 'High']
COMPONENTS = ['Selection', 'Expansion', 'Rollout', 'Backprop', 'FSM']
# Component colors (consistent across all plots): Selection, Expansion, Rollout, Backprop, FSM.
COLORS = ['#6BB6FF', '#2ca02c', '#ff7f0e', '#9467bd', '#808080']
PATTERNS = ['', '///', 'xxx']   # hatch per play strength (Low, Medium, High)


def extract_board_num(board_str):
    return int(board_str.split('x')[0])


def load():
    df = pd.read_csv(DATA_DIR / "fig04_area_breakdown.csv")
    df['_sort_key'] = df['board_size'].apply(extract_board_num)
    df = df.sort_values(['_sort_key', 'play_strength']).drop('_sort_key', axis=1)
    return df


def plot(df):
    """Grouped stacked bars: one group per board size, one bar per play strength,
    stacked over the five components."""
    board_sizes_unique = sorted(df['board_size'].unique(), key=extract_board_num)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.set_facecolor(plotstyle.BACKGROUNDS['white'])
    ax.grid(True, alpha=0.3, linewidth=0.5, axis='y')

    n_strengths = len(PLAY_STRENGTHS)
    bar_width = 0.25
    x_pos = np.arange(len(board_sizes_unique))

    for i, strength in enumerate(PLAY_STRENGTHS):
        df_strength = df[df['play_strength'] == strength].copy()
        x = x_pos + i * bar_width
        bottom = np.zeros(len(board_sizes_unique))
        for j, component in enumerate(COMPONENTS):
            values = df_strength[component].values
            ax.bar(x, values, bar_width, bottom=bottom,
                   label=component if i == 0 else '',   # label once
                   color=COLORS[j],
                   hatch=PATTERNS[i],
                   edgecolor='black', linewidth=0.5)
            bottom += values

    ax.set_xlabel('Board Size', fontsize=plotstyle.FONT_SIZES['large'])
    ax.set_ylabel('Area (mm²)', fontsize=plotstyle.FONT_SIZES['large'])
    ax.set_xticks(x_pos + bar_width * (n_strengths - 1) / 2)
    ax.set_xticklabels(board_sizes_unique, fontsize=plotstyle.FONT_SIZES['medium'])
    ax.set_xlim([-0.3, len(board_sizes_unique) - 0.3])
    ax.set_yscale('log')                                   # log y: small boards visible
    ax.set_ylim([0.001, 1.0])
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.2),
              fontsize=plotstyle.FONT_SIZES['medium'], framealpha=0.9, ncol=3)
    ax.tick_params(axis='both', which='major', labelsize=plotstyle.FONT_SIZES['medium'])
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    return fig


def main():
    print("Generating Figure 4a: Area Breakdown...")
    df = load()
    fig = plot(df)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plotstyle.save_fig(fig, OUTPUT_DIR / "fig_04_area_breakdown.png", format='png')
    plotstyle.save_fig(fig, OUTPUT_DIR / "fig_04_area_breakdown.pdf", format='pdf')
    print(f"Saved fig_04_area_breakdown.png and .pdf to {OUTPUT_DIR}")

    # Total area range across all play strengths.
    all_totals = []
    for strength in PLAY_STRENGTHS:
        df_strength = df[df['play_strength'] == strength]
        total = df_strength[COMPONENTS].sum(axis=1).values
        all_totals.extend(total)
    print(f"  Total area range: {min(all_totals):.4f} - {max(all_totals):.4f} mm²")

    plt.close()


if __name__ == "__main__":
    main()
