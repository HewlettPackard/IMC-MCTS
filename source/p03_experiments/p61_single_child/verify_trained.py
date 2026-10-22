# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Policy differential, repeatability and raw-evidence accounting at useful budgets.
# SPDX-License-Identifier: MIT
import csv
import hashlib
import resource
import time
from pathlib import Path

import numpy as np

from core.architecture.neural_mapping import NeuralMapping
from core.architecture.result_registry import ROOT, new_run, run_case, verify_run, write_json
from core.architecture.result_snapshot import freeze_repeats
from p03_experiments.p61_single_child.reference import Reference
from p03_experiments.p61_single_child.cost_oracle import Sources, compare


def main():
    out=new_run(Path(__file__).parent/'p00_runs'); print(out,flush=True)
    source=Sources(); rows=[]; pairs=[]
    for model_id in ('go_strong_v1','go_weak_v1'):
        for iterations in (500,5000):
            repeats=[]; previous_result=None
            for repeat in (1,2):
                started=time.perf_counter(); observed={}; reference=None
                def observe(event, model):
                    nonlocal reference
                    if time.perf_counter()-started>300: raise TimeoutError('Five-minute per-search guard')
                    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>2*1024**3: raise MemoryError('2 GiB host RSS guard')
                    if event['phase']=='ready':
                        mapper=NeuralMapping(*model.weights,9,turn_indicator=True)
                        def evaluate(board,player):
                            mapper.forward(board,player=player)
                            return mapper.last_state['value_q17']
                        reference=Reference(model.initial_board,evaluate,model.seed,model.exploration,model.game,model.states[0])
                        observed['model']=model
                    elif event['phase']=='iteration_commit':
                        target=reference.step()
                        assert (model.selected,model.value_q17,model.random_state,model.memory.nodes_used)==(
                            target['selected'],target['value_q17'],target['random_state'],target['nodes'])
                        assert model.memory.nodes_used<=model.completed
                        if model.completed%1000==0: print(model_id,iterations,repeat,model.completed,flush=True)
                folder,result=run_case(custom={'board_size':9,'iterations':iterations,'rules':'legacy_go',
                    'model_id':model_id,'seed':0,'exploration':1.414},runs=out/'p01_results/p01_runs',on_event=observe)
                model=observed['model']; tree=model.memory.nodes
                assert result['status']=='complete' and model.completed==iterations
                for n,target in enumerate(reference.nodes):
                    for key in ('visits','value','player','children','parent'): assert tree[n][key]==target[key],(n,key)
                    np.testing.assert_array_equal(model.board(n),target['board'])
                assert tree[0]['visits']==iterations and model.memory.cursor==model.cycles
                assert len(model.memory.node_sram)+len(model.memory.child_sram)==2*1024**2
                _,comparisons=compare(result,source)
                write_json(folder.parent/(folder.name+'_accounting.json'),comparisons)
                assert verify_run(folder)==result
                if previous_result is not None: assert previous_result==result,'Repeat changed deterministic result'
                previous_result=result; repeats.append(folder)
                chosen=max(tree[0]['children'],key=lambda n:(tree[n]['visits'],-n))
                ledger=result['costs']['ledger']; memory=model.memory.summary()
                rows.append({'model':model_id,'iterations':iterations,'repeat':repeat,'run':str(folder.relative_to(ROOT)),
                    'status':result['status'],'nodes':model.memory.nodes_used,'edges':model.memory.edges_used,
                    'node_capacity':model.memory.config['node_capacity'],'node_bytes_used':memory['node_bytes_used'],
                    'child_bytes_used':memory['child_bytes_used'],'cycles':model.cycles,'move':str(model.moves[chosen]),
                    'known_area_mm2':ledger['known_area_mm2'],'known_energy_uj':ledger['known_energy_uj'],
                    'known_power_mw':ledger['known_average_power_mw'],'elapsed_with_reference_s':time.perf_counter()-started,
                    'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
                write_json(out/'progress.json',rows); print(rows[-1],flush=True)
            pairs.append(repeats)
    snapshot=freeze_repeats(pairs,snapshots=out/'p02_snapshots')
    with (out/'summary.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    write_json(out/'metadata.json',{'status':'passed','runs':rows,'snapshot':str(snapshot.relative_to(ROOT)),
        'reference_scope':'Independent list-based selection, incremental expansion and backprop; reused fixed-point UCB and neural evaluator primitives',
        'accounting_scope':'Round 51 raw-evidence equations plus explicit exclusion of incompatible incremental controllers',
        'playing_strength_validated':False,'source_sha256':source.hashes})
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n'
        for p in sorted(out.rglob('*')) if p.is_file()))
    print('All eight trained searches, exact repeats and independent accounting passed',flush=True)


if __name__=='__main__': main()
