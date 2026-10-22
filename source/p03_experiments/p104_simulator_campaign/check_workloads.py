# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
# Compact fresh results, preserving earlier runs and reference snapshots.
from pathlib import Path
import hashlib,json,time
import numpy as np
from core.algorithm.model_catalog import load_model
from core.architecture.parallel_datapath import SizedParallelDatapathGoSimulation as Sim
from core.architecture.board_sizing import board_table
from core.architecture import studio_current as c
from core.architecture.run_identity import tree_sha256
HERE=Path(__file__).resolve().parent
OUT=HERE/'p00_runs/run_20261003_063318Z'
ROOT=HERE.parents[1]
files=sorted(p for p in (ROOT/'core').rglob('*') if p.suffix in ('.py','.json') and '__pycache__' not in p.parts)
source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(OUT/'final_source_sha256.json').write_text(json.dumps(source_hashes,indent=2)+'\n')
def execute(board,iterations,model_id='random_diagnostic',seed=0,initial_board=None):
    weights,_=load_model(model_id,board)
    m=Sim(board,iterations,weights=weights,seed=seed,initial_board=initial_board);prepared=c.prepare(m)
    event_hash=hashlib.sha256();neural_hash=hashlib.sha256();start=time.perf_counter()
    for event in m.steps():
        event_hash.update(json.dumps(event,sort_keys=True,separators=(',',':')).encode())
        if event['phase']=='neural':neural_hash.update(json.dumps(m.neural.last_state,sort_keys=True,separators=(',',':')).encode())
    m.activity_record()
    report=c.price(m.memory.operations,m.cycles,m.block_active_cycles,c.capture(m),prepared)
    assert m.status=='complete' and m.completed==iterations
    assert abs(report['core_energy_uj']-report['core_average_power_mw']*m.cycles/500000)<1e-8
    return {'board_size':board,'iterations':iterations,'model_id':model_id,'seed':seed,'status':m.status,'completed':m.completed,
        'cycles':m.cycles,'phase_cycles':dict(m.phase_cycles),'tree_sha256':tree_sha256(m.memory.nodes),
        'node_sram_sha256':hashlib.sha256(m.memory.node_sram).hexdigest(),'child_sram_sha256':hashlib.sha256(m.memory.child_sram).hexdigest(),
        'events_sha256':event_hash.hexdigest(),'neural_trace_sha256':neural_hash.hexdigest(),
        'memory_operations':dict(m.memory.operations),'activity':m.activity_record(),'costs':report,'wall_seconds':time.perf_counter()-start}

reference=execute(9,5000,'go_strong_v1')
(OUT/'final_9x9_medium.json').write_text(json.dumps(reference,indent=2)+'\n')
original=json.loads((OUT/'reference_9x9_medium.json').read_text())
for key in ('cycles','phase_cycles','tree_sha256','node_sram_sha256','child_sram_sha256','memory_operations'):
    assert reference[key]==original[key],key
for key in ('core_energy_uj','core_area_mm2','core_average_power_mw'):
    assert abs(reference['costs'][key]-original['costs'][key])<1e-10,key
print('Frozen trained reference preserved',flush=True)
# A second trained model and nonempty positions check a different search census.
records=[]
for name in ('go_strong_v1','go_weak_v1'):
    for position in ('empty','sparse'):
        board=None
        if position=='sparse':
            board=np.zeros((9,9),dtype=int);board[2,2]=1;board[6,6]=-1;board[2,6]=1;board[6,2]=-1
        row=execute(9,500,name,seed=11,initial_board=board);row['position']=position;records.append(row)
        print(name,position,row['costs']['latency_ms'],flush=True)
(OUT/'representative_workloads.json').write_text(json.dumps(records,indent=2)+'\n')
# Every approved hardware budget, seed fixed and diagnostic weights explicitly labeled.
scaling=[]
for board in board_table()['boards']:
    for tier in ('low','medium','high'):
        row=execute(board['board_size'],board['iterations'][tier]);row['budget_tier']=tier;scaling.append(row)
        (OUT/'scaling_results.json').write_text(json.dumps(scaling,indent=2)+'\n')
        print('Scaling',len(scaling),row['board_size'],tier,row['iterations'],row['costs']['latency_ms'],flush=True)
(OUT/'round_09.json').write_text(json.dumps({'verdict':'PASS','trained_positions':4,'scaling_cases':18,'weights':'Seeded diagnostic weights for scaling; trained strong/weak for 9x9 workload checks','limits':'Single-position samples, not a tournament or a statistical workload distribution'},indent=2)+'\n')

assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha for name,sha in source_hashes.items()),'Source changed during final sweep'
print('Source-frozen full sweep complete',flush=True)
