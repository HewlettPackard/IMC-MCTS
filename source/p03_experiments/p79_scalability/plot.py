# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Original Figure 2d/e styling, fed only by updated experiment tables.
# SPDX-License-Identifier: MIT
import csv
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

from core.architecture.result_registry import ROOT, write_json
from p03_experiments.p79_scalability.model import BOARDS
from p03_experiments.p79_scalability.run import csv_file

sys.path.insert(0,str(ROOT/'paper/figure'))
import plotstyle

HERE = Path(__file__).resolve().parent
COMPONENTS = ['Selection','Expansion','Rollout','Backprop','FSM','Shared memory']
COLORS = ['#6BB6FF','#2ca02c','#ff7f0e','#9467bd','#808080','#c7b388']
TIERS = ['Low','Medium','High']; PATTERNS = ['','///','xxx']


def read(path):
    with path.open() as stream: return list(csv.DictReader(stream))


def make_table(run):
    totals = read(run/'p00_data/totals.csv')
    owners = read(run/'p00_data/components.csv')
    source = json.loads((run/'sources.json').read_text())['digital']['cases']['imc_tree_update_v2']
    codec = next(r['inclusive_area_um2'] for r in source['hierarchy'] if r['instance']=='u_codec')
    fraction = codec/source['area']['cell_um2']
    tables = {'area_mm2':[],'power_mw':[]}
    for total in totals:
        parts = {r['id']:r for r in owners if r['board_size']==total['board_size'] and r['tier']==total['tier']}
        for metric,field,factor in [('area_mm2','area_um2',1e-6),('power_mw','average_power_mw',1)]:
            values = {k:float(v[field])*factor for k,v in parts.items()}
            row = {'board_size':total['board_size']+'x'+total['board_size'],'play_strength':total['tier'],
                'Selection':sum(values[k] for k in ('u_sel','cam_macro','u_ucb_a','u_ucb_b','u_ucb_c','u_ucb_d')),
                'Expansion':values['u_upd']*(1-fraction),
                'Rollout':sum(values[k] for k in ('cim_arrays','row_drivers','sample_hold','adc_lanes','analog_mux','u_nn')),
                'Backprop':values['u_upd']*fraction,
                'FSM':values['top_level_glue']+values['physical_overhead'],
                'Shared memory':sum(values[k] for k in ('node_sram','child_sram','u_node_router','u_child_router')),
                'requested_iterations':total['requested_iterations'],'completed_iterations':total['completed_iterations'],
                'status':total['status']}
            assert abs(sum(row[k] for k in COMPONENTS)-float(total[metric]))<1e-10
            tables[metric].append(row)
    for metric,rows in tables.items(): csv_file(run/'p00_data'/('figure_'+metric+'.csv'),rows)
    write_json(run/'figure_allocation.json',{'shared_parent':'u_upd','backprop_fraction':fraction,
        'basis':'Dedicated u_codec inclusive area / tree-update parent area from retained hierarchy.',
        'Expansion':'Choice divider and all shared parent control; remainder after dedicated backprop codec.',
        'Backprop':'Dedicated value codec; includes the same share of the parent engineering reserve.',
        'power':'Parent energy apportioned by fixed area fraction for display; no independently characterized child power.',
        'FSM':'Glue plus disclosed physical area/distribution allowance.',
        'ownership':'Original 19-owner ledger is authoritative. Fractions sum to one; no added hardware.',
        'play_strength_labels':'Original configuration names retained; random-weight sweep does not measure playing strength.'})
    return tables


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
    run = ROOT/json.loads((HERE/'latest.json').read_text())['run']
    assert json.loads((run/'sweep_status.json').read_text())['status']=='complete'
    for line in (run/'data_SHA256SUMS').read_text().splitlines():
        digest,name = line.split('  ',1)
        assert hashlib.sha256((run/name).read_bytes()).hexdigest()==digest
    tables = make_table(run)
    out = run/'p03_figures'; out.mkdir(exist_ok=True)
    plt.rcParams.update({'pdf.fonttype':42,'ps.fonttype':42,'mathtext.fontset':'stix'})
    drawn = []
    for metric,name in [('area_mm2','fig2d_estimated'),('power_mw','fig2e_estimated')]:
        fig,ax = plt.subplots(figsize=(7,5))
        drawn += panel(ax,tables[metric],metric)
        fig.tight_layout(rect=[0,0,1,.95])
        for ext in ('pdf','png'): plotstyle.save_fig(fig,out/(name+'.'+ext),format=ext)
        plt.close(fig)
    fig,axes = plt.subplots(1,2,figsize=(14,5))
    for ax,metric in zip(axes,('area_mm2','power_mw')): panel(ax,tables[metric],metric)
    fig.tight_layout(rect=[0,0,1,.95])
    for ext in ('pdf','png'): plotstyle.save_fig(fig,out/('fig2de_estimated.'+ext),format=ext)
    plt.close(fig)
    write_json(run/'render_check.json',{'status':'passed','drawn_segments':drawn,
        'all_18_configurations_shown':True,'panel_letters':False,'titles':False,'footer_notes':False,
        'original_axis_labels':True,'original_plotstyle_sha256':hashlib.sha256((ROOT/'paper/figure/plotstyle.py').read_bytes()).hexdigest(),
        'whole_chip_claim':False,'adc_macro_budget':'Native65 source area/energy retained as explicit analog budget',
        'plotter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    print('Saved original-style figures:',out,flush=True)


if __name__=='__main__': main()
