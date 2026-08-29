#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Regenerate Figure 5c: cross-domain per-move energy bar chart.

Reads measured per-move energies from the cross-domain sweep CSV
(`generalizability/logs/cross_domain_sgg_all13.csv`, produced by
`generalizability/sweeps/run_cross_domain.py`) and renders the per-move
energy bar chart across the 8 display applications.

The figure is generated directly from the simulator CSV so the plotted
values, the caption text, and the source CSV always agree. Energy is
reported per move, not per iteration.

Usage
-----
    python paper/figure/regenerate_5c_cross_domain_energy.py

The output PDF is written next to this script as `5c_energy_bars.pdf`.
"""
import csv
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

# Repo root — this file lives at <root>/paper/figure/<this>
REPO = Path(__file__).resolve().parent.parent.parent
CSV_PATH = REPO / "generalizability" / "logs" / "cross_domain_sgg_all13.csv"
OUT_PATH = Path(__file__).resolve().parent / "5c_energy_bars.pdf"

# The 8 applications shown in the paper's Fig 5, in display order.
# (csv_app_name, display_label, board, domain)
APPS = [
    ("Connect Four",       "Connect 4",   "8×8",   "Board Games"),
    ("Othello",            "Othello",     "8×8",   "Board Games"),
    ("Hex",                "Hex",         "11×11", "Board Games"),
    ("Go",                 "Go",          "9×9",   "Board Games"),
    ("FrozenLake",         "FrozenLake",  "8×8",   "Navigation"),
    ("MiniGrid",           "MiniGrid",    "8×8",   "Navigation"),
    ("HP Protein Folding", "HP Protein",  "13×13", "Optimization"),
    ("Minesweeper",        "Minesweeper", "9×9",   "Puzzles"),
]

DOMAIN_COLORS = {
    "Board Games":  "#1f77b4",   # blue
    "Navigation":   "#2ca02c",   # green
    "Optimization": "#ff7f0e",   # orange
    "Puzzles":      "#d62728",   # red
}


def load_energies():
    """Pull Energy_uJ for the 8 paper apps from the sim CSV."""
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Sim CSV not found: {CSV_PATH}")
    energies = {}
    target_names = {csv_name for csv_name, *_ in APPS}
    with open(CSV_PATH) as fp:
        for row in csv.DictReader(fp):
            if row["Application"] in target_names:
                energies[row["Application"]] = float(row["Energy_uJ"])
    missing = target_names - set(energies)
    if missing:
        raise RuntimeError(f"Missing rows in CSV: {sorted(missing)}")
    return energies


def render(energies):
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["font.serif"] = ["Times New Roman"] + plt.rcParams["font.serif"]
    plt.rcParams["axes.linewidth"] = 1.0
    plt.rcParams["savefig.dpi"] = 300
    plt.rcParams["savefig.bbox"] = "tight"
    plt.rcParams["pdf.fonttype"] = 42  # editable text in vector output

    fig, ax = plt.subplots(figsize=(6.4, 3.8))

    labels = [f"{disp}\n{board}" for _, disp, board, _ in APPS]
    values = [energies[csv_name] for csv_name, *_ in APPS]
    colors = [DOMAIN_COLORS[domain] for *_, domain in APPS]

    bars = ax.bar(
        range(len(labels)),
        values,
        color=colors,
        edgecolor="black",
        linewidth=0.6,
        width=0.75,
    )

    # Value labels above each bar
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.4,
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=8.5,
        )

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Energy per move (µJ)", fontsize=10)
    ymax = max(values) * 1.18
    ax.set_ylim(0, ymax)
    ax.tick_params(axis="y", labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3, linewidth=0.5)
    ax.set_axisbelow(True)

    # Domain legend — preserve label order matching the bar order
    seen = []
    for *_, domain in APPS:
        if domain not in seen:
            seen.append(domain)
    handles = [mpatches.Patch(color=DOMAIN_COLORS[d], label=d) for d in seen]
    ax.legend(
        handles=handles,
        loc="upper left",
        frameon=False,
        fontsize=8.5,
        ncol=2,
        columnspacing=1.0,
        handlelength=1.2,
    )

    plt.tight_layout()
    plt.savefig(OUT_PATH)
    plt.close(fig)


def main():
    energies = load_energies()
    print(f"Loaded {len(energies)} per-move energies from {CSV_PATH.name}:")
    for csv_name, disp, board, domain in APPS:
        print(f"  {disp:<12} {board:<6}  {energies[csv_name]:>6.3f} µJ  ({domain})")
    render(energies)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
