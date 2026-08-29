#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Figure 6: CAM technology system-level impact.

Scatter of total Accelerator area vs power for each CAM technology, with a Pareto
frontier. Reads paper/results/fig06_cam_system_impact.csv, writes
fig_06_cam_comparison.{png,svg} into paper/figure/.
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

# Color per cell type.
cell_type_colors = {
    'SRAM': plotstyle.DEFAULT_COLORS[0],      # Blue
    'eDRAM': plotstyle.DEFAULT_COLORS[1],     # Orange
    'STT-MRAM': plotstyle.DEFAULT_COLORS[2],  # Green
    'ReRAM': plotstyle.DEFAULT_COLORS[3],     # Red
    'FinFET': plotstyle.DEFAULT_COLORS[4],    # Purple
    'TCAM': plotstyle.DEFAULT_COLORS[5],      # Brown
    'Hybrid': plotstyle.DEFAULT_COLORS[6],    # Pink
    'Analog': plotstyle.DEFAULT_COLORS[7],    # Gray
}


def load():
    return pd.read_csv(DATA_DIR / "fig06_cam_system_impact.csv")


def plot(df):
    """Scatter of total area vs power, one labeled point per CAM, plus a Pareto
    frontier swept by increasing area."""
    fig, ax = plt.subplots(figsize=(7, 4.67))
    ax.set_facecolor(plotstyle.BACKGROUNDS['light'])
    ax.grid(True, alpha=0.3, linewidth=0.5)

    for idx, row in df.iterrows():
        color = cell_type_colors.get(row['cell_type'], plotstyle.DEFAULT_COLORS[8])
        # One point per CAM; only label a cell type the first time it appears.
        ax.scatter(row['total_area_mm2'], row['total_power_mw'],
                   s=200, c=color, alpha=0.7, edgecolors='black', linewidth=1.5,
                   label=row['cell_type'] if row['cell_type'] not in ax.get_legend_handles_labels()[1] else '')
        ax.annotate(row['cam_design'],
                    xy=(row['total_area_mm2'], row['total_power_mw']),
                    xytext=(5, 5), textcoords='offset points',
                    fontsize=plotstyle.FONT_SIZES['small'],
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7, edgecolor='none'))

    ax.set_xlabel('Total Accelerator Area (mm²)', fontsize=plotstyle.FONT_SIZES['large'])
    ax.set_ylabel('Total Accelerator Power (mW)', fontsize=plotstyle.FONT_SIZES['large'])
    ax.set_title('CAM Technology System-Level Impact\n(9×9 Board, Medium Play Strength)',
                 fontsize=plotstyle.FONT_SIZES['title'], pad=20)
    ax.legend(loc='lower right', fontsize=plotstyle.FONT_SIZES['medium'],
              title='Cell Type', title_fontsize=plotstyle.FONT_SIZES['medium'],
              framealpha=0.9)
    ax.tick_params(axis='both', which='major', labelsize=plotstyle.FONT_SIZES['medium'])

    # Pareto frontier: sweep by increasing area, keep each point that lowers power.
    pareto_points = []
    sorted_df = df.sort_values('total_area_mm2')
    min_power = float('inf')
    for idx, row in sorted_df.iterrows():
        if row['total_power_mw'] < min_power:
            pareto_points.append((row['total_area_mm2'], row['total_power_mw']))
            min_power = row['total_power_mw']
    if len(pareto_points) > 1:
        pareto_x, pareto_y = zip(*pareto_points)
        ax.plot(pareto_x, pareto_y, 'k--', linewidth=2, alpha=0.5, label='Pareto Frontier')

    plt.tight_layout()
    return fig


def main():
    print("Generating Figure 6: CAM System-Level Impact...")
    df = load()
    fig = plot(df)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plotstyle.save_fig(fig, OUTPUT_DIR / "fig_06_cam_comparison.png", format='png')
    plotstyle.save_fig(fig, OUTPUT_DIR / "fig_06_cam_comparison.svg", format='svg')
    print(f"Saved fig_06_cam_comparison.png and .svg to {OUTPUT_DIR}")
    print(f"  CAM technologies compared: {len(df)}")
    print(f"  Area range: {df['total_area_mm2'].min():.5f} - {df['total_area_mm2'].max():.5f} mm²")
    print(f"  Power range: {df['total_power_mw'].min():.2f} - {df['total_power_mw'].max():.2f} mW")

    # Best area+power tradeoff: min-max normalize both metrics, minimize their sum.
    df['combined_score'] = (df['total_area_mm2'] - df['total_area_mm2'].min()) / (df['total_area_mm2'].max() - df['total_area_mm2'].min()) + \
                           (df['total_power_mw'] - df['total_power_mw'].min()) / (df['total_power_mw'].max() - df['total_power_mw'].min())
    best_cam = df.loc[df['combined_score'].idxmin()]
    print(f"  Recommended CAM (best area+power tradeoff): {best_cam['cam_design']}")

    plt.close()


if __name__ == "__main__":
    main()
