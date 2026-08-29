# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""3-panel ED figure: conductance-noise robustness of the 9x9 Go evaluator.

Reads results/noise_sweep_9x9.csv and emits paper/figure/ED_fig_noise_sweep.pdf.

Panels:
  a) Win-rate vs σ (NN-MCTS vs random-rollout MCTS), mean ± 95% CI across seeds
  b) 1-ply move-agreement vs σ (noisy NN vs σ=0 NN) on held-out mid-game positions
  c) Terminal-position value MSE vs σ (NN value error grows with noise)
"""
import csv
import os
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

CSV_PATH = str(Path(__file__).resolve().parent.parent / "results" / "noise_sweep_9x9.csv")
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "ED_fig_noise_sweep.pdf")

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman"],
    "font.size": 10,
    "axes.linewidth": 1.0,
    "lines.linewidth": 1.8,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# Figure palette, consistent with the paper's existing figures.
FIGURE_NAVY = "#001A57"
FIGURE_ACCENT = "#C84E00"
GRAY = "#666666"


def _read_csv(path):
    rows = []
    with open(path, "r") as f:
        for row in csv.DictReader(f):
            rows.append({
                "sigma": float(row["sigma"]),
                "seed": int(row["seed"]),
                "winrate": float(row["winrate"]),
                "move_agreement": float(row["move_agreement"]),
                "term_acc": float(row["term_acc"]),
                "term_balanced_acc": float(row["term_balanced_acc"]),
                "term_value_mse": float(row["term_value_mse"]),
            })
    return rows


def _aggregate(rows, key):
    """Returns sorted (sigmas, mean, ci95) over seeds."""
    by_sigma = defaultdict(list)
    for r in rows:
        by_sigma[r["sigma"]].append(r[key])
    sigmas = sorted(by_sigma.keys())
    means = np.array([np.mean(by_sigma[s]) for s in sigmas])
    sems = np.array([np.std(by_sigma[s], ddof=1) / max(1, np.sqrt(len(by_sigma[s])))
                     if len(by_sigma[s]) > 1 else 0.0
                     for s in sigmas])
    ci95 = 1.96 * sems
    return np.array(sigmas), means, ci95


def main():
    rows = _read_csv(CSV_PATH)
    if not rows:
        print(f"No rows in {CSV_PATH}")
        sys.exit(1)

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    sigma_pct_label = "Conductance noise σ (% of G$_{center}$)"

    # --- Panel a: win-rate vs σ ---
    ax = axes[0]
    s, m, ci = _aggregate(rows, "winrate")
    ax.plot(s * 100, m, "-o", color=FIGURE_NAVY, markersize=5)
    if (ci > 0).any():
        ax.fill_between(s * 100, m - ci, m + ci, alpha=0.18, color=FIGURE_NAVY,
                        linewidth=0)
    ax.axhline(0.5, color=GRAY, linestyle="--", linewidth=0.8, alpha=0.6)
    ax.text(s.max() * 100 * 0.95, 0.51, "random", fontsize=8, color=GRAY,
            ha="right", va="bottom")
    ax.set_xlabel(sigma_pct_label)
    ax.set_ylabel("Win-rate vs random-rollout MCTS")
    ax.set_title("a", loc="left", fontweight="bold", fontsize=12)
    ax.set_ylim(0.0, 1.05)
    ax.grid(alpha=0.3)

    # --- Panel b: 1-ply move-agreement vs σ ---
    ax = axes[1]
    s, m, ci = _aggregate(rows, "move_agreement")
    ax.plot(s * 100, m, "-o", color=FIGURE_NAVY, markersize=5)
    if (ci > 0).any():
        ax.fill_between(s * 100, m - ci, m + ci, alpha=0.18, color=FIGURE_NAVY,
                        linewidth=0)
    ax.set_xlabel(sigma_pct_label)
    ax.set_ylabel("1-ply move agreement vs σ=0")
    ax.set_title("b", loc="left", fontweight="bold", fontsize=12)
    ax.set_ylim(0.0, 1.05)
    ax.grid(alpha=0.3)

    # --- Panel c: terminal value MSE vs σ ---
    ax = axes[2]
    s, m_mse, ci_mse = _aggregate(rows, "term_value_mse")
    # Also overlay balanced accuracy as a secondary axis for the physics bridge
    s2, m_acc, ci_acc = _aggregate(rows, "term_balanced_acc")
    ax.plot(s * 100, m_mse, "-o", color=FIGURE_NAVY, markersize=5,
            label="Value MSE")
    if (ci_mse > 0).any():
        ax.fill_between(s * 100, m_mse - ci_mse, m_mse + ci_mse,
                        alpha=0.18, color=FIGURE_NAVY, linewidth=0)
    ax.set_xlabel(sigma_pct_label)
    ax.set_ylabel("NN value MSE on terminals", color=FIGURE_NAVY)
    ax.tick_params(axis="y", labelcolor=FIGURE_NAVY)
    ax.set_title("c", loc="left", fontweight="bold", fontsize=12)
    ax.grid(alpha=0.3)

    ax_right = ax.twinx()
    ax_right.plot(s2 * 100, m_acc, "--s", color=FIGURE_ACCENT, markersize=4,
                  label="Balanced accuracy")
    if (ci_acc > 0).any():
        ax_right.fill_between(s2 * 100, m_acc - ci_acc, m_acc + ci_acc,
                              alpha=0.15, color=FIGURE_ACCENT, linewidth=0)
    ax_right.set_ylabel("Balanced classification accuracy",
                        color=FIGURE_ACCENT)
    ax_right.tick_params(axis="y", labelcolor=FIGURE_ACCENT)
    ax_right.set_ylim(0.0, 1.0)

    fig.suptitle("Conductance-noise robustness of 9×9 Go crossbar evaluator",
                 fontsize=11, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT_PATH)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
