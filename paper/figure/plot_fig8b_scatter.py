#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Fig 8b - IMC-MCTS energy-vs-latency scatter (traditional vs neural MCTS).

Ported into the paper repro tier from the original generator
  the original hardware-benchmark Figure 8 analysis script
(panel 8b). Self-contained: reuses the SAME measured points as fig8a, read from
paper/results/fig8a_gain_bars.csv; external 04_Tools_Scripts save_fig dependency dropped.

Open markers = Traditional MCTS, filled = Neural MCTS; arrows trace the algorithmic
(traditional -> neural) step on each platform; the green star is the IMC-MCTS ASIC.

Run:  python paper/figure/plot_fig8b_scatter.py
Out:  paper/figure/fig8b_gain_scatter.{png,pdf}
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "results" / "fig8a_gain_bars.csv"
OUTDIR = HERE

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["DejaVu Serif"] + plt.rcParams["font.serif"]
plt.rcParams["axes.linewidth"] = 1.0
plt.rcParams["pdf.fonttype"] = 42
FONT = {"axis_label": 12, "tick": 9.5, "annotation": 7.5, "legend": 7.5}

# CSV platform name -> scatter display name
NAME = {"AMD TR": "AMD TR", "Xeon": "Intel Xeon", "H100": "NVIDIA H100",
        "H100 (b64)": "H100 batch-64", "H100 (b256)": "H100 batch-256",
        "IMC-MCTS": "IMC-MCTS"}

STY = {
    "AMD TR":         {"color": "#2166ac", "marker": "s", "size": 80},
    "Intel Xeon":     {"color": "#e08214", "marker": "D", "size": 70},
    "NVIDIA H100":    {"color": "#b2182b", "marker": "^", "size": 90},
    "H100 batch-64":  {"color": "#b2182b", "marker": "^", "size": 65},
    "H100 batch-256": {"color": "#b2182b", "marker": "^", "size": 65},
    "IMC-MCTS":       {"color": "#1a9641", "marker": "*", "size": 400},
}
LABELS = {
    "AMD TR":         {"traditional": ("AMD TR", (300, 15_500), "left", "center")},
    "Intel Xeon":     {"traditional": ("Xeon", (500, 5_500), "left", "center")},
    "NVIDIA H100":    {"traditional": ("H100", (3500, 350_000), "right", "bottom")},
    "H100 batch-64":  {"neural": ("b64", (5, 18_000), "right", "bottom")},
    "H100 batch-256": {"neural": ("b256", (3, 8_000), "right", "bottom")},
    "IMC-MCTS":       {"neural": ("IMC-MCTS\n(this work)", (5.5, 250), "left", "bottom")},
}


def load_scatter():
    df = pd.read_csv(DATA).set_index("platform")
    data = {}
    for csv_name, disp in NAME.items():
        row = df.loc[csv_name]
        d = {"neural": (float(row["neural_energy_mj"]), float(row["neural_latency_ms"]))}
        if pd.notna(row["trad_energy_mj"]):
            d["traditional"] = (float(row["trad_energy_mj"]), float(row["trad_latency_ms"]))
        data[disp] = d
    return data


def main():
    scatter_data = load_scatter()
    fig, ax = plt.subplots(figsize=(5.5, 3.8))
    ax.set_facecolor("#fafafa")
    ax.set_axisbelow(True)
    ax.grid(True, which="major", alpha=0.25, linewidth=0.6, color="#cccccc")
    ax.grid(True, which="minor", alpha=0.12, linewidth=0.3, color="#dddddd")
    ax.fill_between([1.0, 8], 100, 350, color="#1a9641", alpha=0.08, zorder=1)  # IMC zone

    for name, d in scatter_data.items():
        s = STY[name]
        for variant in ("traditional", "neural"):
            if variant not in d:
                continue
            e, l = d[variant]
            if variant == "traditional":
                ax.scatter(l, e, marker=s["marker"], s=s["size"], facecolors="none",
                           edgecolors=s["color"], linewidths=2.2, zorder=5)
            else:
                ax.scatter(l, e, marker=s["marker"], s=s["size"], facecolors=s["color"],
                           edgecolors="white", linewidths=0.8, zorder=6)
            lcfg = LABELS.get(name, {}).get(variant)
            if lcfg:
                text, pos, ha, va = lcfg
                ours = name == "IMC-MCTS"
                ax.annotate(text, (l, e), xytext=pos,
                            fontsize=FONT["legend"] if ours else FONT["annotation"],
                            fontweight="bold" if ours else "normal",
                            color=s["color"], alpha=0.9 if ours else 0.8,
                            arrowprops=dict(arrowstyle="-", color=s["color"],
                                            alpha=0.5 if ours else 0.3, lw=0.7),
                            ha=ha, va=va)

    # algorithmic (traditional -> neural) step on each full platform
    for name in ("AMD TR", "Intel Xeon", "NVIDIA H100"):
        d = scatter_data[name]
        if "traditional" in d and "neural" in d:
            e_t, l_t = d["traditional"]
            e_n, l_n = d["neural"]
            c = STY[name]["color"]
            ax.plot([l_t, l_n], [e_t, e_n], linestyle="--" if name == "Intel Xeon" else "-",
                    color=c, alpha=0.45, lw=2.0, zorder=4)
            ax.annotate("", xy=(l_n, e_n), xytext=(np.sqrt(l_t * l_n), np.sqrt(e_t * e_n)),
                        arrowprops=dict(arrowstyle="->", color=c, alpha=0.5, lw=1.5), zorder=4)

    # H100 batching chain: neural -> b64 -> b256
    chain = [scatter_data["NVIDIA H100"]["neural"],
             scatter_data["H100 batch-64"]["neural"],
             scatter_data["H100 batch-256"]["neural"]]
    for j in range(len(chain) - 1):
        e0, l0 = chain[j]
        e1, l1 = chain[j + 1]
        ax.plot([l0, l1], [e0, e1], "--", color="#b2182b", alpha=0.3, lw=1.2, zorder=3)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Latency (ms)", fontsize=FONT["axis_label"])
    ax.set_ylabel("Energy (mJ)", fontsize=FONT["axis_label"])
    ax.tick_params(axis="both", which="major", labelsize=FONT["tick"])
    ax.set_xlim(1.0, 6000)
    ax.set_ylim(100, 500_000)
    for sp in ax.spines.values():
        sp.set_linewidth(0.7)
        sp.set_color("#444")

    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="none", markeredgecolor="#555",
               markersize=8, linestyle="None", markeredgewidth=1.8, label="Traditional MCTS"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#555", markeredgecolor="white",
               markersize=8, linestyle="None", markeredgewidth=0.8, label="Neural MCTS"),
        Line2D([0, 1], [0, 0], color="#555", lw=1.5, linestyle="-", marker=">", markersize=4,
               label="Algorithmic gain"),
    ]
    leg = ax.legend(handles=handles, fontsize=FONT["legend"], loc="lower right",
                    framealpha=0.95, edgecolor="#ccc", fancybox=True, borderpad=0.7, handletextpad=0.5)
    leg.get_frame().set_linewidth(0.5)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUTDIR / f"fig8b_gain_scatter.{ext}", format=ext, dpi=300,
                    bbox_inches="tight", pad_inches=0.1, facecolor="white")
    print(f"Saved fig8b_gain_scatter.{{png,pdf}} to {OUTDIR}")
    plt.close(fig)


if __name__ == "__main__":
    main()
