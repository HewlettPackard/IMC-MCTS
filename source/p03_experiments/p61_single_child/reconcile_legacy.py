# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Reconcile the default path with retained RTL stimuli before extending bindings.
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import tempfile

from core.architecture.result_registry import ROOT, new_run, write_json
from p03_experiments.p12_complete_core import fixtures_complete
from p03_experiments.p18_buffered_hardware import fixtures_buffered
from p03_experiments.p45_studio_paper_models.controls import controls


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    experiment=Path(__file__).parent; out=new_run(experiment/'p00_runs')
    baseline=ROOT/'p03_experiments/p45_studio_paper_models/before_controls.json'
    before=json.loads(baseline.read_text()); after=controls()
    checks={name:before[name]==after[name] for name in before}
    old=ROOT/'p03_experiments/p23_tree_update_integration/p00_runs/run_20260910_014700Z'
    retained={}
    cases=[('small',2,12,False,5,7),('three',3,5,False,None,None),
        ('five',5,5,True,None,None),('full',9,4,False,None,None),('ragged',9,7,True,None,None)]
    for mode,builder in [('driven',fixtures_complete),('buffered',fixtures_buffered)]:
        for label,size,iterations,ragged,hidden,cam in cases:
            name=mode+'_'+label
            if not (old/name).is_dir(): continue
            with tempfile.TemporaryDirectory(dir=out) as temporary:
                generated=Path(temporary)/name
                current=builder.make_complete(generated,size,iterations,ragged,hidden,cam)
                prior=json.loads((old/name/'fixture.json').read_text())
                for filename in ('initial_node.hex','initial_child.hex','expected_node.hex',
                    'expected_child.hex','transactions.hex','iterations.hex','adc.hex'):
                    sha=digest(old/name/filename); retained[name+'/'+filename]=sha
                    checks[name+'_'+filename]=digest(generated/filename)==sha
                for field in ('phases','history','operations','core_cycles','hidden_shift','logit_shift'):
                    checks[name+'_'+field]=current[field]==prior[field]
            print('Reconciled',name,flush=True)
    assert all(checks.values()),[name for name,passed in checks.items() if not passed]
    sources=['core/architecture/'+name+'.py' for name in ('neural_mapping','iteration_model','analog_readout',
        'digital_costs','block_power','complete_costs','component_inventory','go_simulation')]
    hashes={name:digest(ROOT/name) for name in sources}
    metadata={'status':'passed','checks':checks,'validated_sources':hashes,
        'baseline':'55967e8e5e6e7dd7a7b22f15d4a4f315f1cb6536',
        'before_controls_sha256':digest(baseline),
        'retained_fixture_sha256':retained,
        'scope':'Legacy full-expansion paths only. Single-child profiles are explicitly outside this RTL proof. Exact SRAM, ADC, transactions, cycles and old-profile costs. No turn-aware RTL validation or synthesis.',
        'rtl_executed':False,'benchmarks_executed':False}
    write_json(out/'metadata.json',metadata)
    write_json(out/'source_sha256.json',hashes | {str(Path(__file__).relative_to(ROOT)):digest(Path(__file__))})
    for filename in ('complete_controller_validation.json','column_hold_controller_validation.json'):
        path=ROOT/'core/architecture'/filename; proof=json.loads(path.read_text())
        for name,sha in proof['validated_sources'].items():
            assert name in hashes or digest(ROOT/name)==sha,name
        proof['validated_sources'].update({name:sha for name,sha in hashes.items() if name in proof['validated_sources']})
        proof['software_extension']={'path':str((out/'metadata.json').relative_to(ROOT)),
            'sha256':digest(out/'metadata.json'),'scope':metadata['scope']}
        write_json(path,proof)
    (out/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file()))
    print('Passed',len(checks),'checks; extended board-only source bindings:',out,flush=True)


if __name__=='__main__': main()
