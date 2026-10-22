# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Actual paired searches against the preserved four-UCB/three-ADC revision.
# SPDX-License-Identifier: MIT
from collections import Counter
import gzip
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import resource
import tarfile
import time

from core.algorithm.model_catalog import load_model
from core.architecture.analog_readout import configure_readout
from core.architecture.component_inventory import write_component_csv
from core.architecture.eight_adc import EightADCGoSimulation
from core.architecture.eight_adc_costs import eight_adc_costs,prepare_eight_adc_costs
from core.architecture.parallel_selection import FourLaneGoSimulation
from core.architecture.parallel_selection_costs import parallel_costs
from core.architecture.result_registry import ROOT,new_run,write_json
from core.architecture.run_identity import tree_sha256
from p03_experiments.p62_component_costs.verify_large import check_packed
from p03_experiments.p69_parallel_selection.run_comparison import csv_file,sha
from p03_experiments.p70_eight_adc.group_reference import replay_layer

HERE=Path(__file__).resolve().parent
REFERENCE=ROOT/'p03_experiments/p69_parallel_selection/p00_runs/run_20260916_042741Z'


def main():
    out=new_run(HERE/'p00_runs'); print(out,flush=True)
    for line in (REFERENCE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1); assert sha((REFERENCE/name).read_bytes())==digest,name
    sources=json.loads((REFERENCE/'source_sha256.json').read_text())
    extras=list((ROOT/'core/architecture').glob('eight_adc*'))+[Path(__file__),HERE/'group_reference.py',ROOT/'tests/test_eight_adc.py']
    sources.update({str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in extras})
    def source_check():
        for name,digest in sources.items(): assert sha((ROOT/name).read_bytes())==digest,name
    source_check(); write_json(out/'source_sha256.json',sources)
    with tarfile.open(out/'source_snapshot.tar.gz','w:gz') as archive:
        for name in sources: archive.add(ROOT/name,arcname=name,recursive=False)
    results=[]; checks=[]; sensitivity=[]
    for model_id,budget in [('go_strong_v1',500),('go_strong_v1',5000),('go_weak_v1',500)]:
        case=model_id+'_'+str(budget); folder=out/case; folder.mkdir()
        old=json.loads((REFERENCE/case/'ucb4_result.json').read_text())
        weights,evaluator=load_model(model_id,9)
        a=FourLaneGoSimulation(9,budget,seed=0,exploration=1.414,weights=weights,turn_indicator=True,cam_entries=1024)
        configure_readout(a,'sustained_drive_v1')
        b=EightADCGoSimulation(9,budget,seed=0,exploration=1.414,weights=weights,turn_indicator=True,cam_entries=1024)
        start=time.perf_counter(); print('START',case,flush=True); neural_matches=0
        for x,y in zip_longest(a.steps(),b.steps()):
            assert x is not None and y is not None
            for key in ('phase','iteration','selected_node','nodes','edges','path_depth'):
                assert x.get(key)==y.get(key),(case,key,x,y)
            if x['phase']=='neural':
                assert a.neural.last_state==b.neural.last_state,(case,'neural',x['iteration'])
                neural_matches+=1
            if x['phase']=='iteration_commit':
                assert a.value_q17==b.value_q17 and a.random_state==b.random_state
                if b.completed%1000==0: print(case,b.completed,'matched iterations',flush=True)
            if time.perf_counter()-start>600: raise TimeoutError('10-minute paired-search guard')
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>2*1024**3: raise MemoryError('2 GiB host RSS guard')
        assert a.status==b.status=='complete' and a.completed==b.completed==budget
        assert a.memory.node_sram==b.memory.node_sram and a.memory.child_sram==b.memory.child_sram
        assert a.cycles==old['cycles'] and tree_sha256(a.memory.nodes)==old['tree_sha256']
        assert sha(a.memory.node_sram)==old['node_sram_sha256'] and sha(a.memory.child_sram)==old['child_sram_sha256']
        for model in (a,b): check_packed(model)
        assert a.cycles-b.cycles==12255*budget
        for phase in a.phase_cycles:
            assert a.phase_cycles[phase]-b.phase_cycles[phase]==(12255*budget if phase=='neural' else 0)
        assert a.batch_counts==b.batch_counts
        changed={'neural_mux_groups','neural_adc_groups','neural_readout_words'}
        for name in set(a.memory.operations)|set(b.memory.operations):
            if name not in changed: assert a.memory.operations[name]==b.memory.operations[name],name
        assert b.memory.operations['neural_adc_groups']==624*budget
        assert b.memory.operations['neural_adc_conversions']==4800*budget
        assert b.memory.operations['neural_readout_words']==1200*budget
        # Replay the last actual inference through independent lane/word handling.
        features=b.neural.features(b.board(b.selected),b.memory._node_fields(b.selected)['player'])
        hidden,c1,_=replay_layer(features,b.neural.weight_codes[0],1)
        logits,c2,_=replay_layer(b.neural.last_state['hidden_codes'],b.neural.weight_codes[1],8)
        assert hidden==b.neural.last_state['hidden_acc'] and logits==b.neural.last_state['logits_acc']
        for name,value in (Counter(c1)+Counter(c2)).items(): assert b.neural.schedule['operations'][name]==value
        for label,model in [('adc3',a),('adc8',b)]:
            if label=='adc3':
                costs=parallel_costs(model); assert costs==old['costs']
            else:
                prepared=prepare_eight_adc_costs(model); costs=eight_adc_costs(model,prepared=prepared)
                for factor in model.rollout_spec['neural_parent_sensitivity']:
                    ledger=eight_adc_costs(model,neural_multiplier=factor,prepared=prepared)['ledger']
                    sensitivity.append({'model':model_id,'iterations':budget,'neural_parent_multiplier':factor,
                        'energy_uj':ledger['known_energy_uj'],'area_mm2':ledger['known_area_mm2'],
                        'average_power_mw':ledger['known_average_power_mw'],'cost_sha256':ledger['sha256']})
            ledger=costs['ledger']; assert ledger['missing_area']==ledger['missing_energy']==[]
            root=model.memory.nodes[0]; chosen=max(root['children'],key=lambda n:(model.memory.nodes[n]['visits'],-n))
            record={'model':model_id,'iterations':budget,'profile':label,'cycles':model.cycles,
                'selection_ms':model.phase_cycles['selection']/500000,'rollout_ms':model.phase_cycles['neural']/500000,
                'latency_ms':model.cycles/500000,'energy_uj':ledger['known_energy_uj'],
                'average_power_mw':ledger['known_average_power_mw'],'area_mm2':ledger['known_area_mm2'],
                'nodes':model.memory.nodes_used,'edges':model.memory.edges_used,'chosen_move':str(model.moves[chosen]),
                'installed_sram_bytes':len(model.memory.node_sram)+len(model.memory.child_sram),
                'tree_sha256':tree_sha256(model.memory.nodes),'node_sram_sha256':sha(model.memory.node_sram),
                'child_sram_sha256':sha(model.memory.child_sram),'cost_sha256':ledger['sha256']}
            results.append(record)
            write_json(folder/(label+'_result.json'),record|{'costs':costs,'memory':model.memory.summary(),
                'neural':model.neural.estimate(),'block_active_cycles':dict(model.block_active_cycles),
                'phase_cycles':dict(model.phase_cycles),'evaluator':evaluator})
            write_component_csv(folder/(label+'_components.csv'),ledger)
            csv_file(folder/(label+'_iterations.csv'),model.history)
            for name,data in [('node',model.memory.node_sram),('child',model.memory.child_sram)]:
                (folder/(label+'_'+name+'.bin.gz')).write_bytes(gzip.compress(bytes(data),mtime=0))
            csv_file(folder/(label+'_neural_trace.csv'),[{k:r.get(k) for k in ('phase','resource','operation','count',
                'region','address','bytes','start','end','array_id','outputs','active_rows','input_bit','columns','conversions')}
                for r in model.neural.schedule['trace']])
            print('RESULT',record,flush=True)
        checks.append({'model':model_id,'iterations':budget,'all_neural_states_match':neural_matches==budget,
            'all_iteration_choices_match':True,'full_sram_matches':True,'tree_matches_frozen_reference':True,
            'cycles_saved':a.cycles-b.cycles,'independent_lane_replay_passed':True,
            'paired_wall_seconds_with_checks':time.perf_counter()-start})
        write_json(out/'progress.json',checks)
    source_check(); csv_file(out/'summary.csv',results); csv_file(out/'sensitivity.csv',sensitivity)
    write_json(out/'verification.json',{'status':'passed','source_count':len(sources),'comparisons':checks,
        'timing_fidelity':'Architectural service model; no full eight-lane/163-input RTL proof or physical timing closure',
        'memory_bytes':2097152,'ucb_lanes':4,'adc_lanes':8,'shift_add_lanes':1,'readout_bus_bits':32,'overlap':False})
    files=sorted(p for p in out.rglob('*') if p.is_file())
    (out/'SHA256SUMS').write_text(''.join(sha(p.read_bytes())+'  '+str(p.relative_to(out))+'\n' for p in files))
    print('PASS',out,flush=True)


if __name__=='__main__': main()
