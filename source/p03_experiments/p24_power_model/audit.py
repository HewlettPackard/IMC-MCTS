# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Recover conversion evidence and write actionable component characterization requests.
# SPDX-License-Identifier: MIT
import csv
import hashlib
import json
from pathlib import Path
import zipfile

from core.architecture.digital_costs import load_digital_profile
from core.architecture.result_registry import new_run, write_json
from core.architecture.crossbar_workbook import workbook_source
from core.architecture.cost_ledger import scaling_policy

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent


def main():
    out = new_run(HERE/'p00_runs')
    prior = ROOT/'p03_experiments/p08_cost_sources/p00_runs/run_20260909_025047Z/digital_provenance.json'
    legacy = json.loads(prior.read_text())
    checks = {}
    for name, record in legacy['source_files'].items():
        checks['historical_'+name] = hashlib.sha256((ROOT/record['path']).read_bytes()).hexdigest()==record['sha256']
    for row in legacy['rows']:
        assert abs(row['derived_area_um2']-row['source_area_um2']*(22/65)**2)<1e-8
        if row['source_power_mw'] is not None:
            assert abs(row['derived_power_mw']-row['source_power_mw']*legacy['power']['factor'])<1e-8
    checks['102_area_101_power_and_one_missing'] = len(legacy['rows'])==102 and sum(r['source_power_mw'] is not None for r in legacy['rows'])==101
    inventory = json.loads((ROOT/'p03_experiments/p16_cost_recovery/p01_sources/source_inventory.json').read_text())
    candidates = []
    with zipfile.ZipFile(inventory['archive_path']) as archive:
        for name in archive.namelist():
            if '/synthesis/' not in name or not name.endswith(('.py','.ipynb','.m','.sh')) or name.startswith('__MACOSX'): continue
            content = archive.read(name)
            candidates.append({'member':name,'sha256':hashlib.sha256(content).hexdigest(),
                'mentions_stillmaker':b'stillmaker' in content.lower(),
                'mentions_factor':b'0.09291' in content})
    checks['bounded_script_search'] = len(candidates)==9 and not any(r['mentions_stillmaker'] or r['mentions_factor'] for r in candidates)
    digital = load_digital_profile(); workbook = workbook_source()
    cells = workbook['cells']['New_Architecture']
    requirements = [
        {'component':'Iteration glue','installed':'one driven OR buffered glue block',
         'source':'p04_glue in the activity packet; exact projection of existing control logic',
         'needed':'TSMC65 area, timing, constraints, units/library identity; matched activity for energy',
         'ownership':'Excludes all six installed parents; no whole-core synthesis required'},
        {'component':'Digital module energy','installed':'six compatible parents for 9x9/H96/CAM1024',
         'source':'Seven returned module cases cover the two mutually exclusive neural variants',
         'needed':'Matching mapped VCD/SAIF, duration, gate coverage, PVT, native dynamic/leakage split and target conversion',
         'ownership':'Keep nested children inside parents; include idle clocks; no multiplication by phase count'},
        {'component':'CAM macro','installed':'1024 rows at 9x9, each 32-bit parent key + 32-bit child payload + valid bit',
         'source':'Current CAM request/response contract; 66560 logical stored bits',
         'needed':'Matching associative cell/matchline/search/row-read/fill/invalidate circuit, latency, area and activity energy',
         'ownership':'Digital cache header/control in selector; physical CAM array and sensing remain separate'},
        {'component':'Binary drive and row selection','installed':'4 arrays, 1024 row terminals, at most 16 rows active on one array',
         'source':'Current binary drive interface; workbook temporal driver is a different circuit',
         'needed':'Sharing topology, read voltage, conductance load, settle time, sustained-drive current and transition energy',
         'ownership':'Active-row limit does not determine installed driver count'},
        {'component':'ADC, reference and analog mux','installed':'3 shared 8-bit lanes; up to 43 column groups per selected 128-column array',
         'source':'Current mapped geometry; native NeuroSim SAR probe is a separate reference',
         'needed':'Range, sample rate, ENOB/error, input/common-mode load, shared reference and mux implementation, energy per conversion and idle power',
         'ownership':'No workbook sequential comparator or zero-leakage SAR model substituted for complete ADC chain'},
        {'component':'ADC sample and hold','installed':'3 shared ADC input samples in either readout mode',
         'source':'Current readout contract',
         'needed':'Acquisition time, capacitance, noise/droop, switch/charge injection, buffer drive and conversion interval',
         'ownership':'Separate from digital 24-bit ADC result registers already inside neural control'},
        {'component':'Column holding cells','installed':'0 driven, or 512 samples in four 128-column banks',
         'source':'Workbook C42/C41 capacitor-only sizing scenario, not characterized hold circuit',
         'needed':'Per-column current-to-voltage front end, 2 ns assumed capture, worst scheduled hold duration, switches/buffer/accuracy and leakage',
         'ownership':'512*85fF/(15fF/um2) = capacitor-only scenario; excluded from known area'},
        {'component':'Physical clock/routing and interface','installed':'layout and chip boundary dependent',
         'source':'Standalone synthesis wire-load reports do not supply chip-level networks',
         'needed':'Physical clock distribution/routing and operating point; separately scope preload, programming and off-chip services',
         'ownership':'Core execution excludes preload, host Go work and weight programming; disclose exclusions in application results'}]
    with (out/'component_requests.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(requirements[0])); writer.writeheader(); writer.writerows(requirements)
    write_json(out/'conversion_audit.json',{'status':'passed' if all(checks.values()) else 'failed','checks':checks,
        'policy':scaling_policy(),'legacy_area':legacy['area'],'legacy_power':legacy['power'],
        'source_archive':inventory['archive_path'],'script_search':candidates,
        'native_conditions':digital['cases']['imc_tree_update_v2']['environment'],
        'workbook_sha256':workbook['source_sha256'],
        'capacitor_scenario':{'count':512,'capacitance_ff':cells['C42']['value'],
            'density_ff_per_um2':cells['C41']['value'],'area_um2':512*cells['C42']['value']/cells['C41']['value'],
            'adopted':False,'reason':'Capacitor only; a hold cell also requires switches, conditioning and accuracy characterization'},
        'sources':scaling_policy()['sources'],'whole_chip_ppa_complete':False})
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file()))
    if not all(checks.values()): raise AssertionError(checks)
    print(out.relative_to(ROOT),len(checks),'checks passed',flush=True)


if __name__=='__main__': main()
