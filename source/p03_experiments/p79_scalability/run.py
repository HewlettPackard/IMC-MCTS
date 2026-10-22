# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Cost retained trained runs, then execute one growing search per scaling case.
# SPDX-License-Identifier: MIT
import csv
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace

from core.architecture.result_registry import ROOT, write_json
from core.architecture.run_identity import tree_sha256
from p03_experiments.p79_scalability.model import DiagnosticSearch, BOARDS
from p03_experiments.p79_scalability.costs import estimate, GROUPS, SCENARIOS

HERE = Path(__file__).resolve().parent
FROZEN = ROOT/'p03_experiments/p77_ucb_overlap/p01_searches/run_20260917_152440Z'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_file(path,rows):
    with path.open('w',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def result(model, requested):
    root = model.memory.nodes[0]
    chosen = max(root['children'],key=lambda n:(model.memory.nodes[n]['visits'],-n)) if root['children'] else None
    return {'board_size':model.board_size,'seed':model.seed,'requested_iterations':requested,
        'completed_iterations':model.completed,'status':'complete' if model.completed==requested else model.status,
        'cycles':model.cycles,'latency_ms':model.cycles/500000,'phase_cycles':dict(model.phase_cycles),
        'chosen_move':model.moves.get(chosen),'nodes':model.memory.nodes_used,'edges':model.memory.edges_used,
        'installed_sram_bytes':len(model.memory.node_sram)+len(model.memory.child_sram),
        'memory':model.memory.summary(),'activity':model.activity_record(),'batch_counts':dict(model.batch_counts),
        'tree_sha256':tree_sha256(model.memory.nodes),
        'node_sram_sha256':hashlib.sha256(model.memory.node_sram).hexdigest(),
        'child_sram_sha256':hashlib.sha256(model.memory.child_sram).hexdigest(),
        'termination':model.termination,'neural_evaluations':model.neural.evaluations}


def main():
    out = ROOT/json.loads((HERE/'latest.json').read_text())['run']
    sources = json.loads((out/'sources.json').read_text()); published = json.loads((out/'published_adc.json').read_text())
    data = out/'p00_data'; data.mkdir(exist_ok=True)
    paths = [p for directory in ('core','p05_studio/p00_app') for p in (ROOT/directory).rglob('*')
             if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts]
    paths += list(HERE.glob('*.py'))
    bound = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    write_json(out/'execution_source_sha256.json',bound)
    write_json(out/'config.json',{'boards_and_budgets':BOARDS,'primary_seed':0,'sensitivity_seeds':[1,2],
        'hidden_units':96,'weight_recipe':'RandomState(seed) normal, sqrt(2/fan_in), turn-aware inputs',
        'selection':'four overlapped UCB scorers, sequential SRAM loads',
        'rollout':'two offset arrays, 8-bit weights/cells, eight 12-bit ADCs, no overlap',
        'installed_sram_bytes':2097152,'cam_entries':1024,'clock_mhz_assumed':500,
        'scenarios':SCENARIOS,'task':'empty-board one-move hardware diagnostic, not playing strength',
        'time_limit_seconds_per_search':300})
    trained = []
    for case in ('go_strong_v1_500','go_strong_v1_5000','go_weak_v1_500','go_weak_v1_5000'):
        source = FROZEN/case; folder = out/'p01_trained'/case; folder.mkdir(parents=True,exist_ok=True)
        record = json.loads((source/'overlap_result.json').read_text())
        neural = json.loads((source/'unchanged_neural.json').read_text())
        batches = json.loads((source/'ucb_batches.json').read_text())
        model = SimpleNamespace(board_size=9,cycles=record['cycles'],
            block_active_cycles={k:v['active_cycles'] for k,v in batches['activity']['blocks'].items()},
            memory=SimpleNamespace(config=record['memory']['config'],operations=record['memory']['operations']),
            neural=SimpleNamespace(profile=neural['profile'],schedule=neural))
        for scenario in SCENARIOS:
            costs = estimate(model,sources,published,scenario)
            write_json(folder/(scenario+'.json'),costs)
            trained.append({'case':case,'scenario':scenario,'cycles':record['cycles'],
                'latency_ms':record['latency_ms'],'area_mm2':costs['core_area_mm2'],
                'power_mw':costs['core_average_power_mw'],'energy_uj':costs['core_energy_uj']})
        write_json(folder/'source.json',{'source':str(source.relative_to(ROOT)),
            'files':{p.name:sha(p) for p in source.glob('*.json')},'cycles':record['cycles'],
            'tree_sha256':record['tree_sha256'],'node_sram_sha256':record['node_sram_sha256'],
            'child_sram_sha256':record['child_sram_sha256']})
    csv_file(data/'trained_reconciliation.csv',trained)
    print('Four trained cases repriced without replay or changed results',flush=True)
    totals = []; component_rows = []; group_rows = []; sensitivity = []
    for seed in (0,1,2):
        for board,budgets in BOARDS.items():
            if seed: budgets = (budgets[1],)
            model = DiagnosticSearch(board,max(budgets),seed=seed)
            start = time.perf_counter(); captured = set()
            folder = out/'p02_sweep'/('b'+str(board)+'_seed'+str(seed)); folder.mkdir(parents=True,exist_ok=True)
            write_json(folder/'evaluator.json',model.evaluator)
            write_json(folder/'neural.json',model.neural.estimate(capture_trace=True))

            def save(requested):
                state = result(model,requested)
                costs = estimate(model,sources,published)
                write_json(folder/(str(requested)+'_result.json'),state)
                write_json(folder/(str(requested)+'_costs.json'),costs)
                row = {'board_size':board,'seed':seed,'requested_iterations':requested,
                    'completed_iterations':model.completed,'status':state['status'],
                    'area_mm2':costs['core_area_mm2'],'power_mw':costs['core_average_power_mw'],
                    'energy_uj':costs['core_energy_uj'],'cycles':model.cycles,'latency_ms':model.cycles/500000,
                    'node_capacity':model.memory.config['node_capacity'],'nodes':model.memory.nodes_used,
                    'source_result':str((folder/(str(requested)+'_result.json')).relative_to(ROOT))}
                if seed==0:
                    tier = ('Low','Medium','High')[BOARDS[board].index(requested)]
                    totals.append(row | {'tier':tier})
                    for group,owners in GROUPS.items():
                        parts = [r for r in costs['components'] if r['id'] in owners]
                        group_rows.append({'board_size':board,'tier':tier,'requested_iterations':requested,
                            'completed_iterations':model.completed,'status':state['status'],'group':group,
                            'area_mm2':sum(r['area_um2'] for r in parts)/1e6,
                            'power_mw':sum(r['average_power_mw'] for r in parts)})
                        for r in parts:
                            component_rows.append({'board_size':board,'tier':tier,'group':group,
                                **{k:r[k] for k in ('id','component','count','area_um2','energy_uj','average_power_mw','source','status','assumptions')}})
                    for scenario in SCENARIOS:
                        c = estimate(model,sources,published,scenario)
                        sensitivity.append(row | {'scenario':scenario,'area_mm2':c['core_area_mm2'],
                            'power_mw':c['core_average_power_mw'],'energy_uj':c['core_energy_uj']})
                else: sensitivity.append(row | {'scenario':'seed_variation'})
                captured.add(requested)
                print('SAVED',board,seed,requested,model.completed,state['status'],flush=True)

            for step in model.steps():
                if step['phase']!='iteration_commit': continue
                if model.completed in budgets: save(model.completed)
                if model.completed%5000==0: print('PROGRESS',board,seed,model.completed,flush=True)
                if time.perf_counter()-start > 300:
                    model.status = 'wall_time_limit'; break
            for requested in budgets:
                if requested not in captured: save(requested)
            write_json(folder/'execution.json',{'wall_seconds':time.perf_counter()-start,
                'model_status':model.status,'completed':model.completed,'requested':model.iterations})
            # Flush each search, preserving useful results if a later case fails.
            csv_file(data/'totals.csv',totals); csv_file(data/'resource_groups.csv',group_rows)
            csv_file(data/'components.csv',component_rows); csv_file(data/'sensitivity.csv',sensitivity)
    for name,digest in bound.items(): assert sha(ROOT/name)==digest,name
    (out/'data_SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(out))+'\n' for p in sorted(data.glob('*.csv'))))
    write_json(out/'sweep_status.json',{'status':'complete','primary_cases':len(totals),
        'fully_completed_budgets':sum(r['status']=='complete' for r in totals),
        'capacity_limited':sum(r['status']=='memory_limited' for r in totals),
        'wall_time_limited':sum(r['status']=='wall_time_limit' for r in totals),
        'source_files_bound':len(bound),'scalability_accuracy_claim':False})
    print('SWEEP DONE',flush=True)


if __name__ == '__main__': main()
