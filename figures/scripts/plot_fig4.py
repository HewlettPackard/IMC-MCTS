# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import csv
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT.parent/'data/figure_inputs/applications'
OUT=ROOT/'generated'
COLORS={'Strategy':'#1f77b4','Navigation':'#2ca02c','Science':'#d62728','Puzzle':'#9467bd'}


def style():
    plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],
        'axes.linewidth':1.0,'savefig.dpi':300,'savefig.bbox':'tight','pdf.fonttype':42})


def quality():
    rows=list(csv.DictReader((HERE/'quality.csv').open()))
    fig,ax=plt.subplots(figsize=(6.4,3.8))
    values=[float(r['sgg']) for r in rows]
    bars=ax.bar(range(8),values,color=[COLORS[r['domain']] for r in rows],edgecolor='black',linewidth=.6,width=.75)
    for bar,value in zip(bars,values):
        ax.text(bar.get_x()+bar.get_width()/2,value+.012,f'{value:+.2f}',ha='center',va='bottom',fontsize=8.5)
    ax.set_xticks(range(8));ax.set_xticklabels(['Connect Four','Othello','Hex','Go','FrozenLake','MiniGrid','HP Protein Fold','Minesweeper'],rotation=35,ha='right',fontsize=9)
    ax.set_ylabel('Search Guidance Gain (SGG)',fontsize=10);ax.set_xlabel('Application',fontsize=10)
    ax.set_ylim(0,.66);ax.tick_params(axis='y',labelsize=9)
    ax.axhline(.05,color='black',ls='--',lw=.7)
    ax.text(7.45,.065,'+0.05 heuristic cutoff',ha='right',fontsize=8.5,fontstyle='italic')
    ax.grid(axis='y',alpha=.3,linewidth=.5);ax.set_axisbelow(True)
    ax.legend(handles=[mpatches.Patch(color=color,label=label) for label,color in COLORS.items()],loc='upper left',fontsize=8.5,frameon=True)
    fig.tight_layout();fig.savefig(OUT/'5b_sgg_bars.pdf');fig.savefig(OUT/'5b_sgg_bars.png');plt.close(fig)


def energy():
    rows=list(csv.DictReader((HERE/'energy.csv').open()))
    fig,ax=plt.subplots(figsize=(6.4,3.8))
    labels=[f'{name}\n{r["board"]}×{r["board"]}' for name,r in zip(['Connect 4','Othello','Hex','Go','FrozenLake','MiniGrid','HP Protein','Minesweeper'],rows)]
    values=[float(r['energy_mj']) for r in rows]
    bars=ax.bar(range(8),values,color=[COLORS[r['domain']] for r in rows],edgecolor='black',linewidth=.6,width=.75)
    for bar,value in zip(bars,values):
        ax.text(bar.get_x()+bar.get_width()/2,value+max(values)*.025,f'{value:.1f}',ha='center',va='bottom',fontsize=8.5)
    ax.set_xticks(range(8));ax.set_xticklabels(labels,fontsize=9)
    ax.set_ylabel('Estimated energy per decision (mJ)',fontsize=10)
    ax.set_ylim(0,max(values)*1.18);ax.tick_params(axis='y',labelsize=9)
    ax.spines['top'].set_visible(False);ax.spines['right'].set_visible(False)
    ax.grid(axis='y',alpha=.3,linewidth=.5);ax.set_axisbelow(True)
    ax.legend(handles=[mpatches.Patch(color=color,label=label) for label,color in COLORS.items()],
        loc='upper left',frameon=False,fontsize=8.5,ncol=2,columnspacing=1,handlelength=1.2)
    fig.tight_layout();fig.savefig(OUT/'5c_energy_bars.pdf');fig.savefig(OUT/'5c_energy_bars.png');plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True);style();quality();energy()


if __name__=='__main__':main()
