# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import plotstyle
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT.parent/'data/figure_inputs/resources'
OUT=ROOT/'generated'
BOARDS=[2,3,5,9,13,19]
COMPONENTS = ['Selection','Expansion','Rollout','Backprop','FSM','Shared memory']

COLORS = ['#6BB6FF','#2ca02c','#ff7f0e','#9467bd','#808080','#c7b388']

TIERS = ['Low','Medium','High']

PATTERNS = ['','///','xxx']

def panel(ax,rows,metric):
    ax.set_facecolor(plotstyle.BACKGROUNDS['white'])
    ax.grid(True,alpha=.3,linewidth=.5,axis='y')
    x_pos = np.arange(len(BOARDS)); width = .25; drawn = []
    for i,tier in enumerate(TIERS):
        selected = [next(r for r in rows if r['board_size']==f'{b}x{b}' and r['play_strength']==tier) for b in BOARDS]
        bottom = np.zeros(len(BOARDS)); x = x_pos+i*width
        for component,color in zip(COMPONENTS,COLORS):
            values = np.array([r[component] for r in selected])
            ax.bar(x,values,width,bottom=bottom,label=component if i==0 else '',color=color,
                   hatch=PATTERNS[i],edgecolor='black',linewidth=.5)
            for board,value in zip(BOARDS,values):
                drawn.append({'board_size':board,'tier':tier,'metric':metric,'group':component,'value':float(value)})
            bottom += values
        if metric=='power_mw':
            for position,value,row in zip(x,bottom,selected):
                if row['status']!='complete': ax.text(position,value*1.04,'*',ha='center',va='bottom',fontsize=12)
    ax.set_xlabel('Board Size',fontsize=plotstyle.FONT_SIZES['large'])
    ax.set_ylabel('Area (mm²)' if metric=='area_mm2' else 'Power (mW)',fontsize=plotstyle.FONT_SIZES['large'])
    ax.set_xticks(x_pos+width)
    ax.set_xticklabels([f'{b}x{b}' for b in BOARDS],fontsize=plotstyle.FONT_SIZES['medium'])
    ax.set_xlim([-.3,len(BOARDS)-.3]); ax.set_yscale('log')
    ax.set_ylim([.001,10] if metric=='area_mm2' else [1,2000])
    if metric=='area_mm2':
        ax.legend(loc='upper center',bbox_to_anchor=(.5,1.2),fontsize=12,framealpha=.9,ncol=3)
    else:
        handles = [Patch(facecolor='white',edgecolor='black',hatch=h,label=f'{tier} Play Strength') for h,tier in zip(PATTERNS,TIERS)]
        ax.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,1.2),fontsize=12,framealpha=.9,ncol=2)
    ax.tick_params(axis='both',which='major',labelsize=12)
    return drawn
def main():
    OUT.mkdir(exist_ok=True)
    plt.rcParams.update({'pdf.fonttype':42,'ps.fonttype':42,'mathtext.fontset':'stix'})
    for metric,name in [('area_mm2','1a_area_breakdown'),('power_mw','1b_power_breakdown')]:
        rows=list(csv.DictReader((DATA/(name+'.csv')).open()))
        for row in rows:
            for component in COMPONENTS: row[component]=float(row[component])
        fig,ax=plt.subplots(figsize=(7,5))
        panel(ax,rows,metric)
        if metric=='power_mw':
            for text in ax.get_legend().get_texts():text.set_text(text.get_text().replace('Play Strength','Budget'))
        fig.tight_layout(rect=[0,0,1,.95])
        for ext in ('pdf','png'):plotstyle.save_fig(fig,OUT/(name+'.'+ext),format=ext)
        plt.close(fig)
if __name__=='__main__':main()
