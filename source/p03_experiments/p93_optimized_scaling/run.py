# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Approved sized parallel search, integer and packed-memory checks, source-pinned estimates.
# SPDX-License-Identifier: MIT
import argparse
import csv
import hashlib
import json
import time
from pathlib import Path
from datetime import datetime,timezone
from core.algorithm.model_catalog import load_model
from core.architecture.board_sizing import board_hardware
from core.architecture.parallel_datapath import SizedParallelDatapathGoSimulation
from core.architecture import studio_current as costs
from p03_experiments.p84_parallel_datapath.run import result
from p03_experiments.p62_component_costs.verify_large import check_packed

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent

def save(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board',type=int,required=True)
    parser.add_argument('--budget',choices=('low','medium','high'),default='high')
    parser.add_argument('--model',default='random');args=parser.parse_args()
    shape=board_hardware(args.board);budget=shape['iterations'][args.budget]
    folder=HERE/'p01_runs'/datetime.now(timezone.utc).strftime('run_%Y%m%d_%H%M%SZ')
    folder.mkdir(parents=True,exist_ok=False)
    weights=None
    if args.model!='random':weights,_=load_model(args.model,args.board)
    model=SizedParallelDatapathGoSimulation(args.board,budget,seed=0,weights=weights)
    prepared=costs.prepare(model)
    sources=[p for p in (ROOT/'core').rglob('*') if p.suffix in ('.py','.json') and '__pycache__' not in p.parts]
    sources+=[Path(__file__),ROOT/'p03_experiments/p79_scalability/costs.py']
    save(folder/'source_sha256.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    save(folder/'configuration.json',{'board':args.board,'budget':args.budget,'iterations':budget,'model':args.model,'seed':0,
        'hardware':shape,'evaluator':model.evaluator,'status':'running'})
    save(folder/'cost_sources.json',{'sources':prepared['sources'],'published':prepared['published']})
    start=time.monotonic()
    print(folder,flush=True)
    for event in model.steps():
        if event['phase']=='iteration_commit' and model.completed%1000==0:
            print(args.board,args.budget,model.completed,'iterations',round(time.monotonic()-start,1),'wall seconds',flush=True)
    assert model.status=='complete' and model.completed==budget,(model.status,model.completed,model.termination)
    assert sum(model.phase_cycles.values())==model.cycles==model.memory.cursor
    assert model.memory.nodes[0]['visits']==budget
    assert model.memory.nodes_used<=model.memory.config['node_capacity']
    assert model.memory.edges_used<=model.memory.config['edge_capacity']
    assert model.memory.path_high_water<=model.memory.config['path_storage_entries']
    check_packed(model)
    record=result(model,args.model)
    record.update(board_size=args.board,budget=args.budget,seed=0,neural_evaluations=model.neural.evaluations,
        terminal_evaluations=model.terminal_evaluations,wall_seconds=time.monotonic()-start)
    report=costs.price(model.memory.operations,model.cycles,model.block_active_cycles,costs.capture(model),prepared)
    assert abs(report['core_energy_mj']/record['latency_ms']*1000-report['core_average_power_mw'])<1e-9
    save(folder/'result.json',record);save(folder/'costs.json',report)
    save(folder/'selection_census.json',costs.capture(model))
    save(folder/'last_neural_state.json',model.neural.last_state)
    save(folder/'verification.json',{'completion':True,'packed_memory':True,'phase_cycle_conservation':True,
        'power_unit_check':True,'physical_timing_validation':False,'analog_accuracy_validation':False})
    save(folder/'SHA256SUMS.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.json')})
    print('PASS',args.board,args.budget,record['latency_ms'],'ms',report['core_energy_mj'],'mJ',flush=True)

if __name__=='__main__':main()
