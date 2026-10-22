# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Reuse existing rendering functions and styles, with source-linked current data.
# SPDX-License-Identifier: MIT
import csv,hashlib,json,shutil,subprocess,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from p03_experiments.p79_scalability.plot import panel,plotstyle,COMPONENTS
from core.architecture.parallel_datapath import LANES
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'p04_figures'

def savecsv(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    manifest=json.loads((HERE/'sweep_manifest.json').read_text());assert manifest['cases']==18
    OUT.mkdir(exist_ok=True)
    folders=[HERE/name for name in manifest['runs']]
    # Use the same trained primary point in every 9x9 medium presentation.
    primary=HERE/'p01_runs/run_20260929_064147Z'
    folders=[primary if json.loads((p/'result.json').read_text())['board_size']==9 and json.loads((p/'result.json').read_text())['budget']=='medium' else p for p in folders]
    sources=json.loads((primary/'cost_sources.json').read_text())['sources']
    parent=sources['digital']['cases']['imc_tree_update_v2']
    fraction=next(x['inclusive_area_um2'] for x in parent['hierarchy'] if x['instance']=='u_codec')/parent['area']['cell_um2']
    totals=[];owners=[];tables={k:[] for k in ('area_mm2','power_mw')}
    for folder in folders:
        r=json.loads((folder/'result.json').read_text());c=json.loads((folder/'costs.json').read_text())
        assert r['status']=='complete';b=r['board_size'];tier=r['budget'].title()
        total={'board_size':b,'tier':tier,'iterations':r['iterations'],'completed_iterations':r['iterations'],'status':r['status'],
            'model':r['model'],'latency_ms':r['latency_ms'],'energy_mj':c['core_energy_mj'],
            'power_mw':c['core_average_power_mw'],'area_mm2':c['core_area_mm2'],'run':str(folder.relative_to(HERE))}
        totals.append(total)
        for part in c['components']:owners.append({'board_size':b,'tier':tier,**part})
        for metric,field,scale in [('area_mm2','area_um2',1e-6),('power_mw','average_power_mw',1)]:
            v={p['id']:p[field]*scale for p in c['components']}
            row={'board_size':f'{b}x{b}','play_strength':tier,
                'Selection':sum(v[k] for k in ('u_sel','cam_macro',*LANES)),
                'Expansion':v['u_upd']*(1-fraction),'Backprop':v['u_upd']*fraction,
                'Rollout':sum(v[k] for k in ('cim_arrays','row_drivers','sample_hold','adc_lanes','analog_mux','u_nn')),
                'FSM':v['top_level_glue']+v['physical_overhead'],
                'Shared memory':sum(v[k] for k in ('node_sram','child_sram','u_node_router','u_child_router')),
                'status':'complete','model':r['model']}
            assert abs(sum(row[k] for k in COMPONENTS)-total[metric])<1e-9
            tables[metric].append(row)
    savecsv(OUT/'totals.csv',totals)
    # Components have different detail fields, retained losslessly as JSON.
    (OUT/'components.json').write_text(json.dumps(owners,indent=2)+'\n')
    plt.rcParams.update({'pdf.fonttype':42,'ps.fonttype':42,'mathtext.fontset':'stix'})
    for metric,name in [('area_mm2','fig2d_area'),('power_mw','fig2e_power')]:
        savecsv(OUT/(name+'.csv'),tables[metric]);fig,ax=plt.subplots(figsize=(7,5))
        panel(ax,tables[metric],metric);fig.tight_layout(rect=[0,0,1,.95])
        for ext in ('pdf','png'):plotstyle.save_fig(fig,OUT/(name+'.'+ext),format=ext)
        plt.close(fig)
    # The existing 3b/c plotters already encode the approved style and viewport.
    previous=ROOT/'p03_experiments/p86_parallel_figures/p00_runs/run_20260917_172512Z'
    for name in ('p00_data','p01_plotters','p02_figures'):(OUT/name).mkdir(exist_ok=True)
    rows=list(csv.DictReader((previous/'p00_data/fig3bc.csv').open()))
    cost=json.loads((primary/'costs.json').read_text())
    for row in rows:
        if row['platform']=='IMC-MCTS':
            row['neural_energy_mj']=str(cost['core_energy_mj']);row['neural_latency_ms']=str(cost['latency_ms'])
    savecsv(OUT/'p00_data/fig3bc.csv',rows)
    for p in (previous/'p01_plotters').glob('*.py'):
        target=OUT/'p01_plotters'/p.name;shutil.copy2(p,target)
        subprocess.run([sys.executable,'-B',str(target)],check=True)
    (OUT/'provenance.json').write_text(json.dumps({'runs':[str(p.relative_to(HERE)) for p in folders],
        'nine_medium':'Trained Go-strong primary; remaining cells seeded diagnostic weights',
        'styles':'Reused p79 panel and exact p86 plotters; no new panel letters or titles',
        'shared_update_display_fraction':fraction,
        'gain_status':'Historical numerical ratios only, unmatched workload/boundary; batched algorithm factor extrapolated',
        'files':{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file()}},indent=2)+'\n')
    print('Generated resource and comparison panels',OUT)

if __name__=='__main__':main()
