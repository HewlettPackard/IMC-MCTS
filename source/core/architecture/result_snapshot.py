# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Freeze verified repeats into one immutable, source-linked diagnostic table.
# SPDX-License-Identifier: MIT
import csv
import hashlib
import json
from pathlib import Path

from core.architecture.result_registry import ROOT, RESULTS, new_run, verify_run, write_json
from core.architecture.run_identity import json_sha256
from core.architecture.digital_costs import digital_timing_fields
from core.architecture.cost_ledger import ledger_fields

SNAPSHOTS=RESULTS/'p04_snapshots'


def summary_row(run, result, include_readout=None, include_digital=None, include_timing=None, include_revision=None, include_ledger=None):
    config=result['identity']['configuration']['requested']
    sram=result['costs']['sram']
    row={'case_id':result['case_id'],'run':str(Path(run).relative_to(ROOT)),
        'result_sha256':json_sha256(result),'configuration_sha256':result['identity']['configuration_sha256'],
        'execution_sha256':result['identity']['execution_sha256'],
        'board_size':config['board_size'],'iterations':config['iterations'],'seed':config['seed'],
        'rules':config.get('rules','placement'),'model_id':config.get('model_id','random_diagnostic'),
        'memory_profile':config['memory_profile'],'core_cycles':result['metrics']['core_cycles'],
        'core_latency_us':result['metrics']['core_latency_us'],'sram_energy_uj':sram['energy_uj'],
        'sram_average_power_mw':sram['average_power_mw'],'sram_area_mm2':sram['area_mm2'],
        'known_area_mm2':result['component_estimates']['known_area_mm2'],
        'whole_chip_area_mm2':result['metrics']['area_mm2'],
        'whole_chip_energy_uj':result['metrics']['energy_uj'],
        'whole_chip_power_mw':result['metrics']['power_mw'],
        'publication_status':result['publication_status']}
    # Preserve verification of the earlier snapshot schema byte for byte.
    if include_readout is None: include_readout='analog_readout' in result
    if include_readout:
        readout=result.get('analog_readout',{})
        row['readout_profile']=readout.get('profile',config.get('readout_profile','sustained_drive_v1'))
        row['maximum_column_hold_ns']=readout.get('maximum_column_hold_ns',0)
    if include_digital is None: include_digital=result['costs'].get('digital') is not None
    if include_digital:
        digital=result['costs'].get('digital') or {}
        row['digital_area_22nm_estimate_mm2']=digital.get('known_area_mm2')
        row['digital_area_65nm_subtotal_um2']=digital.get('known_native_65nm_area_um2')
        row['digital_priced_instances']=digital.get('priced_instances')
        row['digital_profile_sha256']=digital.get('profile_sha256')
    if include_timing is None: include_timing='timing_violations' in (result['costs'].get('digital') or {})
    if include_timing: row.update(digital_timing_fields(result['costs'].get('digital')))
    memory=result['identity']['configuration']['memory']
    if include_revision is None: include_revision='tree_update_timing_profile' in memory
    if include_revision:
        row.update(execution_profile=config['profile'],tree_update_timing_profile=memory.get('tree_update_timing_profile'),
            digital_source_commit=(result['costs'].get('digital') or {}).get('source_commit'))
    if include_ledger is None: include_ledger='ledger' in result['costs']
    if include_ledger: row.update(ledger_fields(result['costs']))
    return row


def freeze_repeats(pairs, snapshots=SNAPSHOTS):
    rows=[]; records=[]; cases=set()
    for first,second in pairs:
        first=Path(first).resolve(); second=Path(second).resolve()
        if first==second or not first.is_relative_to(ROOT) or not second.is_relative_to(ROOT):
            raise ValueError('Each configuration needs two distinct retained runs in the repair checkout')
        a=verify_run(first); b=verify_run(second)
        if a['status']!='complete' or b['status']!='complete': raise ValueError('Canonical snapshots require the entire requested iteration budget')
        if a!=b: raise ValueError('Repeat results differ: '+a['case_id'])
        if a['case_id'] in cases: raise ValueError('Duplicate case in snapshot')
        cases.add(a['case_id']); rows.append(summary_row(first,a,include_readout=True,include_digital=True,include_timing=True,include_revision=True,include_ledger=True))
        records.append({'case_id':a['case_id'],'runs':[str(p.relative_to(ROOT)) for p in (first,second)],
            'result_sha256':json_sha256(a),'execution_sha256':a['identity']['execution_sha256']})
    if not rows: raise ValueError('A result snapshot needs at least one verified pair')
    out=new_run(snapshots)
    with (out/'summary.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    write_json(out/'manifest.json',{'schema_version':6,'id':out.name,'status':'repeat_verified_diagnostics',
        'publication_ready':False,'cases':records,
        'boundary':'One row per exact configuration. Nominal controller latency, native SRAM energy and available report-based digital energy. Digital dynamic energy uses an explicit 65-to-22 approximation; leakage retains native65 power as a proxy. Whole-chip costs and physical timing remain unvalidated. No playing-strength claim.',
        'verification':'Both independent runs must have exactly equal deterministic result JSON; wall time lives in separate metadata.'})
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n'
        for p in sorted(out.iterdir()) if p.is_file()))
    verify_snapshot(out)
    write_json(out.parent/'latest.json',{'snapshot':out.name})
    return out


def verify_snapshot(out):
    out=Path(out).resolve()
    if not out.is_relative_to(ROOT): raise ValueError('Snapshot must stay in the repair checkout')
    for line in (out/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1); path=(out/name).resolve()
        if not path.is_relative_to(out) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Snapshot artifact hash mismatch')
    manifest=json.loads((out/'manifest.json').read_text())
    with (out/'summary.csv').open(newline='') as stream: rows=list(csv.DictReader(stream))
    if len(rows)!=len(manifest['cases']): raise ValueError('Snapshot row count differs')
    for row,case in zip(rows,manifest['cases']):
        runs=[(ROOT/name).resolve() for name in case['runs']]
        if len(runs)!=2 or runs[0]==runs[1] or any(not p.is_relative_to(ROOT) for p in runs):
            raise ValueError('Invalid snapshot repeat paths')
        a,b=[verify_run(p) for p in runs]
        if a!=b or json_sha256(a)!=case['result_sha256'] or a['case_id']!=case['case_id'] or a['identity']['execution_sha256']!=case['execution_sha256']:
            raise ValueError('Saved repeat identity differs')
        include_readout=True if manifest['schema_version']>=2 else None
        expected={k:'' if v is None else str(v) for k,v in summary_row(runs[0],a,
            include_readout=include_readout,include_digital=manifest['schema_version']>=3,
            include_timing=manifest['schema_version']>=4,include_revision=manifest['schema_version']>=5,
            include_ledger=manifest['schema_version']>=6).items()}
        if row!=expected: raise ValueError('Snapshot CSV does not match saved run')
    return manifest


def latest_snapshot(snapshots=SNAPSHOTS):
    pointer=Path(snapshots)/'latest.json'
    if not pointer.exists(): return None
    name=json.loads(pointer.read_text())['snapshot']
    if Path(name).name!=name: raise ValueError('Invalid snapshot name')
    return verify_snapshot(pointer.parent/name)
