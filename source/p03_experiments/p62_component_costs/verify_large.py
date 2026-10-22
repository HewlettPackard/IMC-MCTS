# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Bounded large searches with exact replay, independent policy and fixed 2 MiB SRAM.
# SPDX-License-Identifier: MIT
import csv
import gc
import gzip
import hashlib
import json
from pathlib import Path
import resource
import shutil
import struct
import time

import numpy as np

from core.architecture.neural_mapping import NeuralMapping
from core.architecture.result_registry import ROOT, new_run, run_case, verify_run, write_json
from core.architecture.result_snapshot import freeze_repeats
from core.architecture.run_identity import tree_sha256
from core.simulator.tree_memory import NODE, NO_NODE
from p03_experiments.p61_single_child.reference import Reference
from p03_experiments.p62_component_costs.cost_oracle import Sources, compare, expected


def memory_signature(model):
    return {'memory':model.memory.summary(),'tree_sha256':tree_sha256(model.memory.nodes),
        'node_sram_sha256':hashlib.sha256(model.memory.node_sram).hexdigest(),
        'child_sram_sha256':hashlib.sha256(model.memory.child_sram).hexdigest(),
        'last_value_q17':model.value_q17,'random_state':model.random_state,'phase_cycles':dict(model.phase_cycles)}


def check_packed(model):
    memory=model.memory; cfg=memory.config; seen=set()
    for node_id,node in memory.nodes.items():
        address=cfg['node_base']+node_id*cfg['node_stride']
        visits,value,parent,head,count,flags=NODE.unpack_from(memory.node_sram,address)
        assert (visits,value,parent,count,flags&1)==(node['visits'],node['value'],NO_NODE if node_id==0 else node['parent'],len(node['children']),int(node['player']==-1)),('node metadata',node_id)
        packed=int.from_bytes(memory.node_sram[address+NODE.size:address+NODE.size+cfg['board_bytes']],'little')
        for index,cell in enumerate(node['board'].flat):
            assert (packed>>(2*index))&3=={0:0,1:1,-1:2}[cell],('packed board',node_id,index)
        action=address+NODE.size+cfg['board_bytes']
        remaining,tail=struct.unpack_from('<II',memory.node_sram,action)
        mask=int.from_bytes(memory.node_sram[action+8:action+8+cfg['action_mask_bytes']],'little')
        assert remaining==NO_NODE or remaining==mask.bit_count()
        assert mask>>cfg['action_slots']==0
        linked=[]; edge=head; last=NO_NODE
        while edge!=NO_NODE:
            assert edge<memory.edges_used and edge not in seen
            seen.add(edge); last=edge
            child,edge=struct.unpack_from('<II',memory.child_sram,edge*8); linked.append(child)
        assert linked==node['children'] and tail==last
    assert seen==set(range(memory.edges_used))
    assert memory.path_depth==0 and memory.nodes[0]['visits']==model.completed
    assert memory.nodes_used<=model.completed and memory.edges_used==memory.nodes_used-1
    assert cfg['node_base']+memory.nodes_used*cfg['node_stride']<=len(memory.node_sram)
    assert memory.edges_used*8<=len(memory.child_sram)


def main():
    experiment=Path(__file__).parent; out=new_run(experiment/'p02_large'); print(out,flush=True)
    source=Sources(); rows=[]; checks=[]; sensitivity=[]; completed={}
    old=ROOT/'p03_experiments/p61_single_child/p00_runs/run_20260915_210124Z'
    previous=list(csv.DictReader((old/'summary.csv').open()))
    for model_id in ('go_strong_v1','go_weak_v1'):
        prior=verify_run(ROOT/next(row['run'] for row in previous if row['model']==model_id and row['iterations']=='5000' and row['repeat']=='1'))
        for requested in (10000,50000):
            repeats=[]; before_result=None
            for repeat in (1,2):
                gc.collect(); started=time.perf_counter(); observed={}; reference=None; signature_10k=None
                assert shutil.disk_usage(out).free>3*1024**3,'At least 3 GiB free disk required'
                def observe(event,model):
                    nonlocal reference,signature_10k
                    if time.perf_counter()-started>900:raise TimeoutError('15-minute per-search guard')
                    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>2*1024**3:raise MemoryError('2 GiB host RSS guard')
                    if event['phase']=='ready':
                        observed['model']=model
                        assert len(model.memory.node_sram)+len(model.memory.child_sram)==2097152
                        if repeat==1:
                            mapper=NeuralMapping(*model.weights,9,turn_indicator=True)
                            def evaluate(board,player):
                                mapper.forward(board,player=player);return mapper.last_state['value_q17']
                            reference=Reference(model.initial_board,evaluate,model.seed,model.exploration,model.game,model.states[0])
                    elif event['phase']=='iteration_commit':
                        if reference is not None:
                            target=reference.step()
                            assert (model.selected,model.value_q17,model.random_state,model.memory.nodes_used)==(
                                target['selected'],target['value_q17'],target['random_state'],target['nodes'])
                        if model.completed==5000:
                            signature=memory_signature(model)
                            assert all(value==prior[key] for key,value in signature.items()),'5,000 prefix changed'
                        if model.completed==10000:
                            signature_10k=memory_signature(model)
                            if requested==50000: assert signature_10k==completed[model_id],'10,000 prefix changed'
                        if model.completed%1000==0:
                            progress={'model':model_id,'requested':requested,'repeat':repeat,'completed':model.completed,
                                'nodes':model.memory.nodes_used,'elapsed_s':round(time.perf_counter()-started,2),
                                'host_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
                            write_json(out/'progress.json',progress);print(progress,flush=True)
                folder,result=run_case(custom={'board_size':9,'iterations':requested,'rules':'legacy_go',
                    'model_id':model_id,'seed':0,'exploration':1.414},runs=out/'p01_results/p01_runs',on_event=observe)
                model=observed['model']
                raw=out/'p03_memory'/folder.name;raw.mkdir(parents=True)
                for name,data in [('node',model.memory.node_sram),('child',model.memory.child_sram)]:
                    (raw/(name+'.bin.gz')).write_bytes(gzip.compress(bytes(data),mtime=0))
                check_packed(model)
                if reference is not None:
                    for n,node in enumerate(reference.nodes):
                        for key in ('visits','value','player','children','parent'):assert model.memory.nodes[n][key]==node[key]
                        np.testing.assert_array_equal(model.memory.nodes[n]['board'],node['board'])
                if requested==10000:
                    assert result['status']=='complete' and model.completed==requested
                    completed[model_id]=signature_10k
                else:
                    assert result['status']=='memory_limited' and model.completed<requested
                    assert result['termination']['resource']=='nodes'
                    assert model.memory.nodes_used==model.memory.config['node_capacity']
                    assert result['metrics']['completed_iterations']==model.completed
                    assert result['metrics']['requested_iterations']==requested
                assert verify_run(folder)==result
                _,comparison=compare(result,source);checks.extend(comparison)
                if before_result is not None:
                    assert result==before_result,'Exact repeat changed result'
                    for name in ('iterations.csv','phases.jsonl'):
                        assert (folder/name).read_bytes()==(repeats[0]/name).read_bytes(),name
                before_result=result;repeats.append(folder)
                root=model.memory.nodes[0]; chosen=max(root['children'],key=lambda n:(model.memory.nodes[n]['visits'],-n))
                assert sum(model.memory.nodes[n]['visits'] for n in root['children'])==model.completed-1
                ledger=result['costs']['ledger']; memory=result['memory']
                rows.append({'model':model_id,'requested_iterations':requested,'repeat':repeat,'completed_iterations':model.completed,
                    'status':result['status'],'run':str(folder.relative_to(ROOT)),'memory_snapshot':str(raw.relative_to(ROOT)),
                    'nodes':memory['nodes_used'],'edges':memory['edges_used'],
                    'node_capacity':memory['config']['node_capacity'],'node_bytes_used':memory['node_bytes_used'],
                    'scratch_bytes_reserved':memory['scratch_bytes_reserved'],'child_bytes_used':memory['child_bytes_used'],
                    'installed_bytes':2097152,'path_high_water':memory['path_high_water'],'cycles':model.cycles,
                    'latency_ms':model.cycles/500000,'area_mm2':ledger['known_area_mm2'],'energy_uj':ledger['known_energy_uj'],
                    'average_power_mw':ledger['known_average_power_mw'],'chosen_move':str(model.moves[chosen]),
                    'wall_s_including_verification':time.perf_counter()-started,'peak_host_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
                for factor in (1.0,1.25,2.0):
                    costs=expected(result,source,multiplier=factor)
                    energy=sum(row['energy_uj'] or 0 for row in costs.values())
                    sensitivity.append({'model':model_id,'requested':requested,'repeat':repeat,'completed':model.completed,
                        'controller_multiplier':factor,'area_mm2':sum(row['area_um2'] or 0 for row in costs.values())/1e6,
                        'energy_uj':energy,'average_power_mw':energy*500000/model.cycles})
                write_json(out/'results_so_far.json',rows);print('RESULT',rows[-1],flush=True)
                reference=None;observed.clear();del model
            if requested==50000:
                try: freeze_repeats([repeats],snapshots=out/'p02_rejected_snapshots')
                except ValueError: pass
                else: raise AssertionError('Partial budgets entered complete-budget snapshots')
    for filename,values in [('summary.csv',rows),('sensitivity.csv',sensitivity),('comparisons.csv',checks)]:
        with (out/filename).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
    write_json(out/'metadata.json',{'status':'passed','runs':rows,'accounting_comparisons':len(checks),
        'source_sha256':source.hashes,'independent_policy':'First repeat of every case, every iteration and complete tree; reused integer UCB/neural primitives',
        'checks':['2 MiB physical allocation','5,000 prefix unchanged','10,000 prefix unchanged','all packed lists and remaining masks',
            'complete-iteration memory stop','exact result and full trace replay','partial-budget promotion rejected'],
        'benchmarks_executed':False,'new_synthesis':False,'playing_strength_validated':False})
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n' for p in sorted(out.rglob('*')) if p.is_file()))
    latest=json.loads((experiment/'latest.json').read_text()); latest['large']=str(out.relative_to(ROOT));write_json(experiment/'latest.json',latest)
    print('Eight large-search runs, repeats, policy and accounting passed',flush=True)


if __name__=='__main__': main()
