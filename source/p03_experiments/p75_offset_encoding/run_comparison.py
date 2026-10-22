# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Paired complete searches, with outputs and assumptions owned by this experiment.
# SPDX-License-Identifier: MIT
from collections import Counter
import csv
import gzip
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import platform
import resource
import subprocess
import tarfile
import time

from core.algorithm.model_catalog import load_model
from core.architecture.eight_adc import EightADCGoSimulation
from core.architecture.offset_encoding import OffsetGoSimulation, offset_spec
from core.architecture.offset_costs import offset_costs
from core.architecture.result_registry import ROOT, new_run, write_json
from core.architecture.run_identity import tree_sha256
from p03_experiments.p62_component_costs.verify_large import check_packed
from p03_experiments.p75_offset_encoding.scalar_reference import replay_layer

HERE = Path(__file__).resolve().parent
CASES = [('go_strong_v1',500),('go_strong_v1',5000),('go_weak_v1',500),('go_weak_v1',5000)]
FROZEN = ROOT/'p03_experiments/p70_eight_adc/p00_runs/run_20260916_044042Z'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    out = new_run(HERE/'p00_runs')
    print(out,flush=True)
    start = time.perf_counter()
    paths = []
    for directory in ('core','tests','p05_studio/p00_app'):
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts)
    paths.extend(HERE.glob('*.py'))
    paths.extend([ROOT/'p04_results/p03_models/paper_catalog.json',ROOT/'p04_results/p03_models/catalog.json'])
    for model_id,_ in CASES:
        _,record = load_model(model_id,9)
        paths.extend(ROOT/record[key] for key in ('file','binary_snapshot'))
    sources = {str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths}
    write_json(out/'source_sha256.json',sources)
    with tarfile.open(out/'source_snapshot.tar.gz','w:gz') as archive:
        for name in sources: archive.add(ROOT/name,arcname=name,recursive=False)
    write_json(out/'config.json',{'cases':CASES,'offset':offset_spec(),'board_size':9,'seed':0,
        'exploration':1.414,'cam_entries':1024,'installed_sram_bytes':2097152,
        'reference':'ucb4_adc8_serial_rollout_v1','initial_board':'empty','player':1,'komi':6.5})
    write_json(out/'metadata.json',{'status':'running','python':platform.python_version(),
        'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'source_snapshot':'source_snapshot.tar.gz','command':'python -B -m p03_experiments.p75_offset_encoding.run_comparison',
        'working_tree_dirty':True,'timing_kind':'modeled architectural service, not physical measurement'})
    rows = []
    sensitivities = []
    checks = []
    for model_id,budget in CASES:
        case = model_id+'_'+str(budget)
        folder = out/case
        folder.mkdir()
        weights,record = load_model(model_id,9)
        options = {'weights':weights,'turn_indicator':True,'seed':0,'exploration':1.414,'cam_entries':1024}
        a = EightADCGoSimulation(9,budget,**options)
        b = OffsetGoSimulation(9,budget,**options)
        neural_matches = 0
        print('START',case,flush=True)
        case_start = time.perf_counter()
        with gzip.open(folder/'paired_iterations.jsonl.gz','wt') as stream:
            for old,new in zip_longest(a.steps(),b.steps()):
                assert old is not None and new is not None
                for key in ('phase','iteration','selected_node','nodes','edges','path_depth'):
                    assert old.get(key)==new.get(key),(case,key,old,new)
                if old['phase']=='neural':
                    assert a.neural.last_state==b.neural.last_state,(case,'neural',old['iteration'])
                    neural_matches += 1
                if old['phase']=='iteration_commit':
                    assert a.value_q17==b.value_q17 and a.random_state==b.random_state
                    fields = {k:new[k] for k in ('iteration','selected_node','value_q17','nodes','edges','random_state')}
                    fields.update(reference_cycle=a.cycles,offset_cycle=b.cycles)
                    stream.write(json.dumps(fields,separators=(',',':'))+'\n')
                    if b.completed%1000==0: print(case,b.completed,'iterations match',flush=True)
                if time.perf_counter()-case_start>600: raise TimeoutError('Ten-minute paired-case limit')
                if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>2*1024**3: raise MemoryError('Two-GiB host RSS limit')
        assert a.status==b.status=='complete' and a.completed==b.completed==budget
        assert a.memory.node_sram==b.memory.node_sram and a.memory.child_sram==b.memory.child_sram
        assert tree_sha256(a.memory.nodes)==tree_sha256(b.memory.nodes)
        assert a.batch_counts==b.batch_counts
        for phase in a.phase_cycles:
            if phase!='neural': assert a.phase_cycles[phase]==b.phase_cycles[phase]
        for model in (a,b): check_packed(model)
        frozen = FROZEN/case/'adc8_result.json'
        if frozen.exists():
            prior = json.loads(frozen.read_text())
            assert a.cycles==prior['cycles']
            assert tree_sha256(a.memory.nodes)==prior['tree_sha256']
            assert sha(a.memory.node_sram)==prior['node_sram_sha256']
        features = b.neural.features(b.board(b.selected),b.memory._node_fields(b.selected)['player'])
        hidden,c1,_ = replay_layer(features,b.neural.weight_codes[0],1)
        logits,c2,_ = replay_layer(b.neural.last_state['hidden_codes'],b.neural.weight_codes[1],8)
        assert hidden==b.neural.last_state['hidden_acc'] and logits==b.neural.last_state['logits_acc']
        for key,value in (Counter(c1)+Counter(c2)).items(): assert value==b.neural.schedule['operations'][key]
        write_json(folder/'evaluator.json',record)
        write_json(folder/'offset_neural.json',b.neural.estimate(capture_trace=True))
        write_json(folder/'last_neural_state.json',b.neural.last_state)
        write_json(folder/'last_offset_correction.json',b.neural.last_offset)
        write_json(folder/'offset_costs.json',offset_costs(b))
        for label,model in [('reference',a),('offset',b)]:
            root = model.memory.nodes[0]
            chosen = max(root['children'],key=lambda n:(model.memory.nodes[n]['visits'],-n))
            row = {'model':model_id,'iterations':budget,'mapping':label,'cycles':model.cycles,
                'latency_ms':model.cycles/500000,'rollout_ms':model.phase_cycles['neural']/500000,
                'selection_ms':model.phase_cycles['selection']/500000,'nodes':model.memory.nodes_used,
                'chosen_move':str(model.moves[chosen]),'installed_sram_bytes':len(model.memory.node_sram)+len(model.memory.child_sram)}
            rows.append(row)
            write_json(folder/(label+'_result.json'),row | {'phase_cycles':dict(model.phase_cycles),
                'memory':model.memory.summary(),'tree_sha256':tree_sha256(model.memory.nodes),
                'node_sram_sha256':sha(model.memory.node_sram),'child_sram_sha256':sha(model.memory.child_sram)})
        for region in ('node_sram','child_sram'):
            with gzip.open(folder/(region+'.bin.gz'),'wb') as stream: stream.write(getattr(b.memory,region))
        for service in b.rollout_spec['adc_service_scenarios']:
            added = (service-13)*b.neural.schedule['operations']['adc_groups']*budget
            sensitivities.append({'model':model_id,'iterations':budget,'adc_service_cycles':service,
                'rollout_ms':(b.phase_cycles['neural']+added)/500000,'total_search_ms':(b.cycles+added)/500000,
                'status':'conditional service scenario; no physical timing validation'})
        checks.append({'case':case,'neural_matches':neural_matches,'completed':budget,
            'exact_tree':True,'exact_full_sram':True,'scalar_lane_word_replay':True,
            'frozen_reference_checked':frozen.exists(),'wall_seconds':time.perf_counter()-case_start})
        write_json(out/'progress.json',checks)
        print('PASS',case,'reference ms',a.cycles/500000,'offset ms',b.cycles/500000,flush=True)
    for name,values in [('comparison.csv',rows),('adc_sensitivity.csv',sensitivities)]:
        with (out/name).open('w') as stream:
            writer = csv.DictWriter(stream,fieldnames=list(values[0])); writer.writeheader(); writer.writerows(values)
    for name,digest in sources.items(): assert sha((ROOT/name).read_bytes())==digest,name
    write_json(out/'verification.json',{'status':'passed','checks':checks,'sources_unchanged':len(sources),
        'elapsed_seconds':time.perf_counter()-start,'core_ppa_available':False})
    metadata = json.loads((out/'metadata.json').read_text())
    metadata.update(status='complete',elapsed_seconds=time.perf_counter()-start)
    write_json(out/'metadata.json',metadata)
    (out/'SHA256SUMS').write_text(''.join(sha(p.read_bytes())+'  '+str(p.relative_to(out))+'\n'
        for p in sorted(out.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
    write_json(HERE/'latest.json',{'run':str(out.relative_to(ROOT))})
    print('DONE',out,flush=True)


if __name__ == '__main__': main()
