#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Fig 8a - IMC-MCTS gain decomposition bar chart (hardware x algorithmic).

Ported into the paper repro tier from the original generator
  the original hardware-benchmark Figure 8 analysis script
(self-contained here: external 04_Tools_Scripts/plotstyle save_fig dependency dropped;
raw data externalised to paper/results/fig8a_gain_bars.csv; rendering kept identical).

Data: per-platform energy (mJ) + latency (ms) for traditional (random-rollout) MCTS,
neural MCTS, and the IMC-MCTS ASIC at 9x9 Go / 5000 iterations (Table 6). Gains are
expressed as "how many x worse than IMC-MCTS":
    hardware gain    = neural / IMC          (substrate swap: CPU/GPU NN-MCTS -> IMC ASIC)
    algorithmic gain = traditional / neural  (random-rollout -> NN-guided, same hardware)
    total            = traditional / IMC     = hardware x algorithmic
H100 batch variants (b64/b256) have no traditional baseline, so they reuse H100's
algorithmic factor (same hardware, same traditional reference). For Xeon energy the
algorithmic gain is <1 (neural is slightly worse than traditional), so total < hardware:
the green algo layer is hidden and a red tick marks the penalty at the total level.

Run:  python paper/figure/plot_fig8a_gain.py
Out:  paper/figure/fig8a_gain_bars.{png,pdf}
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "results" / "fig8a_gain_bars.csv"
OUTDIR = HERE

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["DejaVu Serif"] + plt.rcParams["font.serif"]
plt.rcParams["axes.linewidth"] = 1.0
plt.rcParams["hatch.linewidth"] = 1.2
plt.rcParams["hatch.color"] = "black"
plt.rcParams["pdf.fonttype"] = 42  # editable vector text

FONT = {"axis_label": 12, "tick": 9.5, "annotation": 7.5,
        "legend": 7.5, "bar_label": 6.5, "group_label": 9}
C_HW, C_ALGO = "#ff7f0e", "#1f77b4"  # orange = hardware, blue = algorithmic


def load_gains():
    df = pd.read_csv(DATA).set_index("platform")
    imc_e = float(df.loc["IMC-MCTS", "neural_energy_mj"])
    imc_l = float(df.loc["IMC-MCTS", "neural_latency_ms"])
    platforms = [p for p in df.index if p != "IMC-MCTS"]

    gains = {}
    for name in platforms:
        ne, nl = df.loc[name, "neural_energy_mj"], df.loc[name, "neural_latency_ms"]
        g = {"hw_e": ne / imc_e, "hw_l": nl / imc_l}
        te, tl = df.loc[name, "trad_energy_mj"], df.loc[name, "trad_latency_ms"]
        if pd.notna(te):
            g["algo_e"], g["algo_l"] = te / ne, tl / nl
            g["all_e"], g["all_l"] = te / imc_e, tl / imc_l
        gains[name] = g

    # batch variants reuse H100's algorithmic factor (same HW + traditional baseline)
    h_algo_e = df.loc["H100", "trad_energy_mj"] / df.loc["H100", "neural_energy_mj"]
    h_algo_l = df.loc["H100", "trad_latency_ms"] / df.loc["H100", "neural_latency_ms"]
    for name in platforms:
        if "all_e" not in gains[name]:
            gains[name]["algo_e"], gains[name]["algo_l"] = h_algo_e, h_algo_l
            gains[name]["all_e"] = gains[name]["hw_e"] * h_algo_e
            gains[name]["all_l"] = gains[name]["hw_l"] * h_algo_l
    return platforms, gains


def fmt(v):
    if v >= 100:
        return f"{v:,.0f}×"
    if v >= 10:
        return f"{v:.0f}×"
    return f"{v:.1f}×"


def render(platforms, gains):
    n = len(platforms)
    x = np.arange(n)
    bw, gap = 0.28, 0.06
    x_e = x - bw / 2 - gap / 2   # energy bars (left)
    x_l = x + bw / 2 + gap / 2   # latency bars (right)

    fig, ax = plt.subplots(figsize=(5.5, 3.8))
    for i, name in enumerate(platforms):
        g = gains[name]
        # Energy (solid): algo layer to total (behind), hardware layer to hw (front)
        ax.bar(x_e[i], g["all_e"], bw, color=C_ALGO, edgecolor="white", linewidth=0.3, zorder=2)
        ax.bar(x_e[i], g["hw_e"], bw, color=C_HW, edgecolor="white", linewidth=0.5, zorder=3)
        if g["all_e"] < g["hw_e"]:  # algo < 1 -> penalty tick at total
            ax.plot([x_e[i] - bw * 0.45, x_e[i] + bw * 0.45], [g["all_e"], g["all_e"]],
                    color="#d62728", linewidth=1.8, zorder=4, solid_capstyle="round")
        ax.text(x_e[i], max(g["all_e"], g["hw_e"]) * 1.25, fmt(g["all_e"]), ha="center",
                va="bottom", fontsize=FONT["bar_label"], color="#333", fontweight="bold")
        # Latency (hatched)
        ax.bar(x_l[i], g["all_l"], bw, color=C_ALGO, edgecolor="black", linewidth=0.3, hatch="///", zorder=2)
        ax.bar(x_l[i], g["hw_l"], bw, color=C_HW, edgecolor="black", linewidth=0.5, hatch="///", zorder=3)
        if g["all_l"] < g["hw_l"]:
            ax.plot([x_l[i] - bw * 0.45, x_l[i] + bw * 0.45], [g["all_l"], g["all_l"]],
                    color="#d62728", linewidth=1.8, zorder=4, solid_capstyle="round")
        ax.text(x_l[i], max(g["all_l"], g["hw_l"]) * 1.25, fmt(g["all_l"]), ha="center",
                va="bottom", fontsize=FONT["bar_label"], color="#333", fontweight="bold", style="italic")

    ax.set_yscale("log")
    ax.set_ylabel("IMC-MCTS Gain (×)", fontsize=FONT["axis_label"])
    ax.axhline(y=1, color="#888", linewidth=0.8, linestyle="--", alpha=0.5, zorder=1)
    ax.tick_params(axis="both", which="major", labelsize=FONT["tick"])
    ax.grid(True, which="major", axis="y", alpha=0.15, linewidth=0.4, color="#ccc")
    ax.set_axisbelow(True)
    ax.set_facecolor("#fafafa")
    for sp in ax.spines.values():
        sp.set_linewidth(0.7)
        sp.set_color("#444")
    ax.set_ylim(0.8, 12_000)
    ax.set_xticks(x)
    ax.set_xticklabels([p.replace(" (", "\n(") for p in platforms], fontsize=FONT["group_label"])

    handles = [
        mpatches.Patch(facecolor=C_HW, edgecolor="white", label="Hardware gain"),
        mpatches.Patch(facecolor=C_ALGO, edgecolor="white", label="Algorithmic gain"),
        mpatches.Patch(facecolor="#bbbbbb", edgecolor="#666", label="Energy (solid)"),
        mpatches.Patch(facecolor="#bbbbbb", edgecolor="#666", hatch="/", label="Latency (hatched)"),
    ]
    ax.legend(handles=handles, fontsize=FONT["legend"], loc="lower center",
              bbox_to_anchor=(0.5, 1.0), ncol=4, frameon=False,
              handletextpad=0.4, columnspacing=1.0)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUTDIR / f"fig8a_gain_bars.{ext}", format=ext, dpi=300,
                    bbox_inches="tight", pad_inches=0.1, facecolor="white")
    plt.close(fig)


def main():
    platforms, gains = load_gains()
    for name in platforms:
        g = gains[name]
        print(f"  {name:12s}  energy {fmt(g['all_e']):>8s}  latency {fmt(g['all_l']):>8s}")
    render(platforms, gains)
    print(f"Saved fig8a_gain_bars.{{png,pdf}} to {OUTDIR}")


if __name__ == "__main__":
    main()
