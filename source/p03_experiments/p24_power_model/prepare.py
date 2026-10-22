# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Build a portable activity packet from matched native reports and verified fixtures.
# SPDX-License-Identifier: MIT
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from core.architecture.digital_costs import load_digital_profile
from p03_experiments.p12_complete_core import fixtures_complete
from p03_experiments.p18_buffered_hardware import fixtures_buffered
from p03_experiments.p24_power_model.glue import project_glue

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
OWNERS = {'u_sel': 'imc_cached_selector', 'u_upd': 'imc_tree_update_v2',
    'u_ucb': 'imc_ucb_score', 'u_nn': 'imc_neural_sequencer',
    'u_node_router': 'imc_sram_router_3bank', 'u_child_router': 'imc_sram_router_1bank'}


def main():
    out = HERE/'p01_packets'/datetime.now(timezone.utc).strftime('run_%Y%m%d_%H%M%SZ')
    out.mkdir(parents=True, exist_ok=False)
    for folder in ('p00_rtl', 'p01_tests', 'p02_fixtures', 'p03_native', 'p04_glue', 'p05_flow'):
        (out/folder).mkdir()
    profile = load_digital_profile()
    record = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'checkpoint': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'synthesis_commit': profile['commit'], 'source_sha256': {}, 'variants': {}, 'cases': {},
        'clock_period_ns': 2, 'characterization': 'Short diagnostic workloads; no automatic extrapolation to canonical searches',
        'target_node_nm': 22, 'native_power_node_nm': 65, 'server_power_completed': False}
    rtl = {}
    for variant, folder, builder in [('driven','p03_iteration_core',fixtures_complete),
                                    ('buffered','p04_column_hold',fixtures_buffered)]:
        hardware = ROOT/'rtl_synthesis'/folder
        names = []
        for line in (hardware/'filelist.f').read_text().splitlines():
            path = (hardware/line).resolve()
            content = path.read_bytes()
            target = out/'p00_rtl'/path.name
            if target.exists() and target.read_bytes() != content:
                raise ValueError('Conflicting RTL basename')
            target.write_bytes(content)
            record['source_sha256'][str(path.relative_to(ROOT))] = hashlib.sha256(content).hexdigest()
            names.append('p00_rtl/'+path.name)
            rtl[path.stem] = content.decode()
        top = 'imc_iteration_core' if variant == 'driven' else 'imc_buffered_iteration_core'
        bench = hardware/'p01_tests'/('tb_'+top+'.sv')
        record['source_sha256'][str(bench.relative_to(ROOT))] = hashlib.sha256(bench.read_bytes()).hexdigest()
        text = bench.read_text().replace('always #5 clk=~clk;', 'always #1 clk=~clk;').replace('#1;', '#0.1;')
        text = text.replace('    initial begin\n', '    string activity_path;\n    realtime activity_start;\n    initial begin\n', 1)
        before = '        tick(); @(negedge clk); start=0;'
        after = '''        tick();
        if (!$value$plusargs("ACTIVITY=%s",activity_path)) $fatal(1,"missing ACTIVITY");
        activity_start=$realtime;
        $dumpfile(activity_path); $dumpvars(0,@@SCOPE@@);
        @(negedge clk); start=0;'''
        if text.count(before) != 1: raise ValueError('Unexpected start handshake')
        text = text.replace(before, after)
        text = text.replace('        saved_requests=transaction_index;',
            '        $display("ACTIVITY_WINDOW start_ns=%0.3f end_ns=%0.3f cycles=%0d",activity_start,$realtime,cycle_count);\n        $dumpoff;\n        saved_requests=transaction_index;')
        (out/'p01_tests'/('tb_'+top+'.sv.in')).write_text(text)
        for header in (hardware/'p01_tests').glob('*.svh'):
            shutil.copyfile(header,out/'p01_tests'/header.name)
            record['source_sha256'][str(header.relative_to(ROOT))] = hashlib.sha256(header.read_bytes()).hexdigest()
        glue, body, wrapper = project_glue(rtl[top], rtl)
        (out/'p04_glue'/(glue+'.sv')).write_text(body)
        (out/'p04_glue'/(top+'.sv')).write_text(wrapper)
        owners = dict(OWNERS)
        if variant == 'buffered': owners['u_nn']='imc_buffered_neural_sequencer'
        record['variants'][variant] = {'top': top, 'filelist': names, 'owners': owners,
            'glue_top': glue, 'glue_parameters': 'BOARD_SIZE=9,CAM_ENTRIES=1024,HIDDEN=96,ADDR_W=21'}
        for label, iterations, ragged in [('empty',4,False),('ragged',12,True)]:
            name = variant+'_'+label
            cfg = builder.make_complete(out/'p02_fixtures'/name,9,iterations,ragged)
            record['cases'][name] = {'variant': variant, 'fixture': 'p02_fixtures/'+name,
                'iterations': iterations, 'ucb_operations': cfg['operations'].get('ucb_operations',0),
                'expected_cycles': cfg['core_cycles']}
            print(name, cfg['core_cycles'], 'cycles, UCB requests',record['cases'][name]['ucb_operations'],flush=True)
    needed = set(OWNERS.values()) | {'imc_buffered_neural_sequencer'}
    record['modules'] = {}
    for case in sorted(needed):
        source = ROOT/profile['cases'][case]['reports']['area.rpt']
        target = out/'p03_native'/case
        target.mkdir()
        for name in ('mapped.v','mapped.ddc','applied.sdc','run_details.txt','area.rpt','qor.rpt'):
            path = source.with_name(name)
            shutil.copyfile(path,target/name)
            record['source_sha256'][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        record['modules'][case] = {'design': profile['cases'][case]['design'],
            'parameters': profile['cases'][case]['parameters']}
    for name in ('replay.py','power.tcl','synth_glue.tcl'):
        shutil.copyfile(HERE/name,out/'p05_flow'/name)
    shutil.copyfile(HERE/'PACKET.md',out/'README.md')
    (out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    files = {}
    for path in sorted(out.rglob('*')):
        if path.is_file(): files[str(path.relative_to(out))]=hashlib.sha256(path.read_bytes()).hexdigest()
    (out/'SHA256SUMS').write_text(''.join(digest+'  '+name+'\n' for name,digest in files.items()))
    print(out.relative_to(ROOT),flush=True)


if __name__ == '__main__': main()
