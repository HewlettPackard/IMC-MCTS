#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
"""Portable package wrapper around the unchanged current simulator and cost API."""
# Package-only orchestration; no simulator arithmetic or cost equations live here.
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import argparse
import hashlib
import json
from pathlib import Path
import platform
import time

from core.algorithm.model_catalog import load_model
from core.architecture.board_sizing import board_hardware
from core.architecture.parallel_datapath import SizedParallelDatapathGoSimulation
from core.architecture.run_identity import tree_sha256
from core.architecture import studio_current as current


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board',type=int,default=9,choices=(2,3,5,9,13,19))
    parser.add_argument('--iterations',type=int)
    parser.add_argument('--budget',choices=('low','medium','high'),default='medium')
    parser.add_argument('--model',default='go_strong_v1',choices=('go_strong_v1','go_weak_v1','random_diagnostic'))
    parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.model!='random_diagnostic' and args.board!=9:
        parser.error('Retained trained Go checkpoints support 9x9 only; use random_diagnostic for scaling.')
    iterations=args.iterations if args.iterations is not None else board_hardware(args.board)['iterations'][args.budget]
    weights,record=load_model(args.model,args.board)
    model=SizedParallelDatapathGoSimulation(args.board,iterations,seed=args.seed,weights=weights,turn_indicator=True)
    prepared=current.prepare(model)  # Includes unchanged connected-report hash gates.
    args.output.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter()
    event_hash=hashlib.sha256();neural_hash=hashlib.sha256()
    for row in model.steps():
        event_hash.update(canonical(row))
        if row['phase']=='neural':neural_hash.update(canonical(model.neural.last_state))
        if row['phase']=='iteration_commit' and model.completed%1000==0:
            print(f'{model.completed}/{iterations} completed; {time.perf_counter()-start:.1f} host seconds',flush=True)
    assert model.status=='complete' and model.completed==iterations,(model.status,model.completed,model.termination)
    assert sum(model.phase_cycles.values())==model.cycles==model.memory.cursor
    assert model.memory.nodes[0]['visits']==iterations
    assert model.memory.nodes_used<=model.memory.config['node_capacity']
    assert model.memory.edges_used<=model.memory.config['edge_capacity']
    assert model.memory.path_high_water<=model.memory.config['path_storage_entries']
    report=current.price(model.memory.operations,model.cycles,model.block_active_cycles,current.capture(model),prepared)
    root=model.memory.nodes[0]
    chosen=max(root['children'],key=lambda n:(model.memory.nodes[n]['visits'],-n)) if root['children'] else None
    result={'model':args.model,'model_id':args.model,'completed':model.completed,'board_size':args.board,'iterations':model.completed,'seed':args.seed,'status':model.status,
        'cycles':model.cycles,'latency_ms':model.cycles/500000,'average_latency_us_per_iteration':model.cycles/500/model.completed,
        'phase_cycles':dict(model.phase_cycles),'chosen_move':list(model.moves[chosen]) if chosen is not None else None,
        'tree_sha256':tree_sha256(model.memory.nodes),'node_sram_sha256':digest(model.memory.node_sram),
        'child_sram_sha256':digest(model.memory.child_sram),'installed_sram_bytes':len(model.memory.node_sram)+len(model.memory.child_sram),
        'memory':model.memory.summary(),'activity':model.activity_record(),'neural':model.neural.estimate(),
        'batch_counts':dict(model.batch_counts),'last_value_q17':model.value_q17,'random_state':model.random_state,
        'events_sha256':event_hash.hexdigest(),'neural_trace_sha256':neural_hash.hexdigest(),
        'memory_operations':dict(model.memory.operations),'neural_state_sha256':digest(canonical(model.neural.last_state)),'operations_sha256':digest(canonical(dict(model.memory.operations))),
        'neural_evaluations':model.neural.evaluations,'terminal_evaluations':model.terminal_evaluations,
        'profile':current.PROFILE,'cost_model_profile':current.COST_PROFILE,
        'core_energy_mj':report['core_energy_mj'],'core_average_power_mw':report['core_average_power_mw'],
        'core_area_mm2':report['core_area_mm2'],'average_energy_uj_per_iteration':report['core_energy_uj']/iterations,
        'wall_seconds':time.perf_counter()-start,'host_wall_time_is_not_chip_latency':True}
    assert abs(result['core_energy_mj']/result['latency_ms']*1000-result['core_average_power_mw'])<1e-9
    assert len({r['id'] for r in report['components']})==len(report['components'])
    config={'profile':current.PROFILE,'cost_model_profile':current.COST_PROFILE,'board_size':args.board,
        'iterations':iterations,'seed':args.seed,'model_id':args.model,'rules':'legacy_go','initial_board':'empty',
        'initial_player':1,'exploration':1.414,'hardware_profile':'board_sized_s1_v1',
        'installed_hardware':board_hardware(args.board),'weights':record,
        'python':platform.python_version(),'boundary':current.datapath_spec()['boundary']}
    items={'result.json':result,'costs.json':report,'config.json':config,
        'selection_census.json':current.capture(model),'last_neural_state.json':model.neural.last_state,
        'source_sha256.json':prepared['source_sha256'],
        'verification.json':{'completion':True,'phase_cycles_equal_elapsed':True,'finite_memory_capacity':True,
            'power_energy_time_identity':True,'unique_component_owners':True,
            'physical_or_analog_validation':False,'tournament_or_Figure_3d_reproduction':False}}
    for name,value in items.items():
        (args.output/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    (args.output/'SHA256SUMS').write_text(''.join(f'{digest((args.output/name).read_bytes())}  {name}\n' for name in sorted(items)))
    print(json.dumps({k:result[k] for k in ('status','iterations','cycles','latency_ms','core_energy_mj','core_average_power_mw','core_area_mm2')},indent=2))

if __name__=='__main__':
    main()
