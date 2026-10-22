# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Full paired searches through the executable parallel architecture.
# SPDX-License-Identifier: MIT
import csv
import gzip
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import platform
import subprocess
import time

from core.algorithm.model_catalog import load_model
from core.architecture.parallel_datapath import ParallelDatapathGoSimulation, datapath_spec
from core.architecture.ucb_overlap import OverlappedUCBGoSimulation
from core.architecture.result_registry import ROOT, new_run, write_json
from core.architecture.run_identity import tree_sha256
from p03_experiments.p62_component_costs.verify_large import check_packed

HERE = Path(__file__).resolve().parent
FROZEN = ROOT/'p03_experiments/p77_ucb_overlap/p01_searches/run_20260917_152440Z'


def sha(data): return hashlib.sha256(data).hexdigest()


def result(model,model_id):
    root = model.memory.nodes[0]
    chosen = max(root['children'],key=lambda n:(model.memory.nodes[n]['visits'],-n))
    return {'model':model_id,'iterations':model.completed,'status':model.status,
        'cycles':model.cycles,'latency_ms':model.cycles/500000,
        'average_latency_us_per_iteration':model.cycles/500/model.completed,
        'phase_cycles':dict(model.phase_cycles),'chosen_move':list(model.moves[chosen]),
        'tree_sha256':tree_sha256(model.memory.nodes),
        'node_sram_sha256':sha(model.memory.node_sram),'child_sram_sha256':sha(model.memory.child_sram),
        'installed_sram_bytes':len(model.memory.node_sram)+len(model.memory.child_sram),
        'memory':model.memory.summary(),'activity':model.activity_record(),
        'neural':model.neural.estimate(),'batch_counts':dict(model.batch_counts)}


def main():
    out = new_run(HERE/'p00_runs'); print(out,flush=True)
    paths = [p for d in ('core','tests') for p in (ROOT/d).rglob('*')
        if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts]
    paths.extend(HERE.glob('*.py')); paths.append(ROOT/'PLAN_ROUND_84.md')
    for model_id in ('go_strong_v1','go_weak_v1'):
        _,info = load_model(model_id,9)
        paths.extend(ROOT/info[k] for k in ('file','binary_snapshot'))
    sources = {str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths}
    write_json(out/'source_sha256.json',sources)
    snapshot = out/'p02_sources'; snapshot.mkdir()
    for p in [Path(__file__),ROOT/'core/architecture/parallel_datapath.py',
        ROOT/'core/architecture/parallel_datapath.json',ROOT/'tests/test_parallel_datapath.py',ROOT/'PLAN_ROUND_84.md']:
        (snapshot/p.name).write_bytes(p.read_bytes())
    write_json(out/'config.json',datapath_spec() | {'board_size':9,'iterations':5000,'seed':0,
        'exploration':1.414,'cam_entries':1024,'models':['go_strong_v1','go_weak_v1'],
        'initial_board':'empty','player':1,'komi':6.5,'host_wall_time_is_not_chip_latency':True})
    metadata = {'status':'running','python':platform.python_version(),'git_head':subprocess.check_output(
        ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'dirty_sources_pinned':True,
        'method':'new paired functional searches with explicit buffered resource schedules',
        'timing':'architectural service at assumed 500 MHz, not physical timing closure'}
    write_json(out/'metadata.json',metadata)
    all_rows = []; checks = []; begin = time.perf_counter()
    for model_id in ('go_strong_v1','go_weak_v1'):
        folder = out/'p00_data'/model_id; folder.mkdir(parents=True)
        weights,evaluator = load_model(model_id,9)
        options = {'weights':weights,'turn_indicator':True,'cam_entries':1024,'seed':0,'exploration':1.414}
        a = OverlappedUCBGoSimulation(9,5000,**options)
        b = ParallelDatapathGoSimulation(9,5000,**options)
        start = time.perf_counter(); matches = 0; log = []
        with gzip.open(folder/'paired_iterations.jsonl.gz','wt') as stream:
            for old,new in zip_longest(a.steps(),b.steps()):
                assert old is not None and new is not None
                for key in ('phase','iteration','selected_node','nodes','edges','path_depth'):
                    assert old.get(key)==new.get(key),(key,old,new)
                if old['phase']=='neural':
                    assert a.neural.last_state==b.neural.last_state
                    assert a.neural.last_offset==b.neural.last_offset
                    matches += 1
                if old['phase']=='iteration_commit':
                    assert a.value_q17==b.value_q17 and a.random_state==b.random_state
                    row = {k:new[k] for k in ('iteration','selected_node','value_q17','nodes','edges','random_state')}
                    row.update(reference_cycles=a.cycles,candidate_cycles=b.cycles)
                    stream.write(json.dumps(row,separators=(',',':'))+'\n')
                    if b.completed%1000==0:
                        print(model_id,b.completed,'identical iterations',flush=True)
                if time.perf_counter()-start>600: raise TimeoutError('Ten-minute paired-search limit')
        assert a.status==b.status=='complete' and a.completed==b.completed==5000
        assert a.memory.node_sram==b.memory.node_sram and a.memory.child_sram==b.memory.child_sram
        assert tree_sha256(a.memory.nodes)==tree_sha256(b.memory.nodes)
        traffic = ('node_sram_read_words','node_sram_write_words','child_sram_read_words',
            'child_sram_write_words','ucb_operations','neural_adc_conversions','neural_shift_adds')
        for key in traffic: assert a.memory.operations[key]==b.memory.operations[key],key
        for phase in ('expansion','backpropagation','iteration_commit'):
            assert a.phase_cycles[phase]==b.phase_cycles[phase],phase
        prior = json.loads((FROZEN/(model_id+'_5000')/'overlap_result.json').read_text())
        for model in (a,b):
            check_packed(model)
            assert sum(model.phase_cycles.values())==model.cycles==model.memory.cursor
        reference = result(a,model_id); candidate = result(b,model_id)
        for key in ('cycles','phase_cycles','tree_sha256','node_sram_sha256','child_sram_sha256'):
            assert reference[key]==prior[key],key
        write_json(folder/'reference.json',reference); write_json(folder/'candidate.json',candidate)
        write_json(folder/'evaluator.json',evaluator)
        write_json(folder/'neural_schedule.json',b.neural.estimate(capture_trace=True))
        write_json(folder/'column_pipelines.json',b.neural.kernels)
        write_json(folder/'selection_pipelines.json',[
            {'candidates':len(k),'visited':sum(k),'schedule':v} for k,v in b.pipeline_cache.items()])
        write_json(folder/'selection_census.json',{'parents':[
            {'candidates':n,'visited':v,'occurrences':c} for (n,v),c in b.parent_histogram.items()],
            'region_cycles':b.selection_region_cycles,'last_region':b.last_selection_region})
        write_json(folder/'last_neural_state.json',b.neural.last_state)
        for region in ('node_sram','child_sram'):
            (folder/(region+'.bin.gz')).write_bytes(gzip.compress(getattr(b.memory,region),mtime=0))
        for label,x in [('reference',reference),('candidate',candidate)]:
            all_rows.append({'model':model_id,'hardware':label,'iterations':x['iterations'],
                'cycles':x['cycles'],'latency_ms':x['latency_ms'],
                'average_latency_us_per_iteration':x['average_latency_us_per_iteration'],
                'selection_ms':x['phase_cycles']['selection']/500000,
                'rollout_ms':x['phase_cycles']['neural']/500000,'chosen_move':str(x['chosen_move']),
                'installed_sram_bytes':x['installed_sram_bytes']})
        check = {'model':model_id,'neural_matches':matches,'exact_tree':True,'exact_sram':True,
            'same_memory_traffic':True,'same_scalar_work':True,'frozen_reference_reproduced':True,
            'wall_seconds':time.perf_counter()-start}
        checks.append(check); write_json(out/'progress.json',checks)
        print('PASS',model_id,'reference',a.cycles/500000,'candidate',b.cycles/500000,'ms',flush=True)
    for name,digest in sources.items(): assert sha((ROOT/name).read_bytes())==digest,name
    protected = json.loads((HERE/'protected_sha256.json').read_text())
    for name,digest in protected.items(): assert sha((ROOT/name).read_bytes())==digest,name
    with (out/'comparison.csv').open('w') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(all_rows[0])); writer.writeheader(); writer.writerows(all_rows)
    write_json(out/'verification.json',{'status':'passed','checks':checks,
        'preserved_files':len(protected),'source_identities':len(sources),'energy_status':'pending_estimation',
        'new_RTL_or_physical_timing_validation':False,'CPU_GPU_runs':False})
    metadata.update(status='complete',wall_seconds=time.perf_counter()-begin)
    write_json(out/'metadata.json',metadata)
    write_json(HERE/'latest.json',{'run':str(out.relative_to(ROOT))})
    print('DONE',out,flush=True)


if __name__=='__main__': main()
