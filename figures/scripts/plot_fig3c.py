#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
"""Figure 3c: sequential endpoints on a logarithmic cost-ratio axis.

Orange: unity -> neural processor / IMC.
Blue: neural processor / IMC -> traditional processor / IMC.
The steps are multiplicative in ratio space, additive only in log space.
Opposing steps are inset so neither interval hides the other. Missing
traditional batches remain absent. No costs, fitted factors or causal
hardware/algorithm contributions are inferred.
"""
from pathlib import Path
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / 'data/figure_inputs/comparisons/fig3bc.csv'
OUT = ROOT / 'generated'
ORANGE, BLUE = '#ff7f0e', '#1f77b4'
FINAL_RED = '#c62828'

plt.rcParams.update({
    'font.family': 'serif', 'font.serif': ['DejaVu Serif'],
    'axes.linewidth': 1.0, 'hatch.linewidth': 1.2,
    'hatch.color': 'black', 'pdf.fonttype': 42,
})


def fmt(value):
    if value >= 100:
        return f'{value:,.0f}×'
    if value >= 10:
        return f'{value:.0f}×'
    return f'{value:.2f}×'


def load():
    df = pd.read_csv(DATA).set_index('platform')
    rows = []
    for name in df.index:
        if name == 'IMC-MCTS':
            continue
        for metric, unit in [('energy', 'mj'), ('latency', 'ms')]:
            imc = float(df.loc['IMC-MCTS', f'neural_{metric}_{unit}'])
            neural = float(df.loc[name, f'neural_{metric}_{unit}'])
            traditional = df.loc[name, f'trad_{metric}_{unit}']
            first = neural / imc
            total = None if pd.isna(traditional) else float(traditional / imc)
            factor = None if pd.isna(traditional) else float(traditional / neural)
            opposing = total is not None and np.log(first) * np.log(factor) < 0
            rows.append(dict(platform=name, metric=metric,
                             imc_cost=imc, neural_cost=neural,
                             traditional_cost=None if pd.isna(traditional) else float(traditional),
                             orange_start=1.0, orange_end=first,
                             blue_start=None if total is None else first,
                             blue_end=total, traditional_over_neural=factor,
                             opposing_steps=bool(opposing)))
    return [p for p in df.index if p != 'IMC-MCTS'], rows


def interval(ax, x, first, last, width, color, hatch, zorder):
    low, high = sorted([first, last])
    assert low > 0
    ax.bar(x, high - low, width, bottom=low, color=color,
           edgecolor='black' if hatch else 'white', linewidth=0.5,
           hatch='///' if hatch else None, zorder=zorder)


def draw(platforms, rows):
    fig, ax = plt.subplots(figsize=(5.5, 3.8))
    width, offset = 0.28, 0.17
    for i, name in enumerate(platforms):
        for row in [r for r in rows if r['platform'] == name]:
            latency = row['metric'] == 'latency'
            x = i + (offset if latency else -offset)
            first, total = row['orange_end'], row['blue_end']
            interval(ax, x, 1.0, first, width, ORANGE, latency, 3)
            if total is not None:
                blue_width = width * 0.60 if row['opposing_steps'] else width
                interval(ax, x, first, total, blue_width, BLUE, latency, 4)
                # An inset reverse interval leaves the orange rails visible.
                if row['opposing_steps']:
                    ax.annotate('', xy=(x, total), xytext=(x, first),
                                arrowprops={'arrowstyle': '-|>', 'lw': 0.8,
                                            'color': 'black', 'mutation_scale': 6},
                                zorder=6)
                ax.plot([x - width * 0.70, x + width * 0.70], [total, total],
                        color=FINAL_RED, lw=3.0, solid_capstyle='butt', zorder=8)

            final = first if total is None else total
            style = 'italic' if latency else 'normal'
            if row['opposing_steps'] and final < first:
                # Here the traditional endpoint is lower than the orange one.
                ax.text(x, first * 1.34, fmt(first), ha='center', va='bottom',
                        fontsize=9, fontweight='bold', color='black')
                ax.annotate(fmt(final), xy=(x + width * 0.18, final),
                            xytext=(9, -7), textcoords='offset points',
                            ha='left', va='top', fontsize=9,
                            fontweight='bold', color='black',
                            arrowprops={'arrowstyle': '-', 'lw': 0.5}, zorder=7)
            else:
                label_x = x + (0.07 if latency and final >= 1 else 0.0)
                ax.text(label_x, final * (1.30 if final >= 1 else 0.88), fmt(final),
                        ha='center', va='bottom' if final >= 1 else 'top',
                        fontsize=9, fontweight='bold', style=style,
                        color='black', zorder=7)
            if row['opposing_steps'] and first < 1:
                ax.plot([x - width * 0.48, x + width * 0.48], [first, first],
                        color=ORANGE, lw=1.2, zorder=7)
                ax.text(x, first * 0.67, fmt(first), ha='center', va='top',
                        fontsize=9, style=style, fontweight='bold',
                        color='black', zorder=7)

    ax.set_yscale('log')
    ax.set_ylabel('Processor / IMC-core cost (×)', fontsize=10.5)
    ax.set_ylim(0.06, 220_000)
    ax.set_xlim(-0.65, len(platforms) - 0.35)
    ax.axhline(1, color='#888', lw=0.8, ls='--', alpha=0.6, zorder=2)
    ax.grid(True, which='major', axis='y', alpha=0.15, lw=0.4, color='#ccc')
    ax.set_axisbelow(True)
    ax.set_facecolor('#fafafa')
    ax.tick_params(axis='both', which='major', labelsize=9.5)
    ax.set_xticks(np.arange(len(platforms)))
    platform_labels = [p.replace(' (b64)', '\nbatch 64')
                       .replace(' (b256)', '\nbatch 256') for p in platforms]
    ax.set_xticklabels(platform_labels, fontsize=9)
    for spine in ax.spines.values():
        spine.set_linewidth(0.7)
        spine.set_color('#444')
    handles = [
        mpatches.Patch(facecolor=ORANGE, edgecolor='white', label='Neural endpoint'),
        mpatches.Patch(facecolor='#bbb', edgecolor='#666', label='Energy (solid)'),
        mpatches.Patch(facecolor=BLUE, edgecolor='white', label='Traditional step'),
        mpatches.Patch(facecolor='#bbb', edgecolor='#666', hatch='/', label='Latency (hatched)'),
        Line2D([0], [0], color=FINAL_RED, lw=3.0, label='Combined ratio'),
    ]
    ax.legend(handles=handles, fontsize=9, loc='lower center',
              bbox_to_anchor=(0.5, 1.015), ncol=3, frameon=True,
              framealpha=1.0, edgecolor='#999', fancybox=False,
              handletextpad=0.5, columnspacing=1.0, labelspacing=0.45)
    fig.tight_layout()
    OUT.mkdir(exist_ok=True)
    for ext in ['pdf', 'png']:
        fig.savefig(OUT / f'fig3c_stacked.{ext}', dpi=300,
                    bbox_inches='tight', pad_inches=0.1, facecolor='white')
    plt.close(fig)


def main():
    platforms, rows = load()
    for row in rows:
        if row['blue_end'] is not None:
            assert np.isclose(row['orange_end'] * row['traditional_over_neural'], row['blue_end'], rtol=1e-12)
    draw(platforms, rows)
    (OUT / 'stacked_ratios.json').write_text(json.dumps(rows, indent=2) + '\n')
    pd.DataFrame(rows).to_csv(OUT / 'stacked_ratios.csv', index=False)
    print(json.dumps({'bars': len(rows), 'traditional_steps': sum(r['blue_end'] is not None for r in rows),
                      'inferred_batch_records': 0, 'output': str(OUT)}, indent=2))


if __name__ == '__main__':
    main()
