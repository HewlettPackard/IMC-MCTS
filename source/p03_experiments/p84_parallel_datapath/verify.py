# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Independently reconcile stored execution, physical owners and source identity.
# SPDX-License-Identifier: MIT
import gzip
import hashlib
import json
import math
from pathlib import Path
import re

from core.architecture.result_registry import ROOT, write_json
from core.architecture.result_snapshot import verify_snapshot
from p03_experiments.p35_component_ppa.verify_preservation import entries

HERE = Path(__file__).resolve().parent


def read(path): return json.loads(path.read_text())


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    run = ROOT/read(HERE/'latest.json')['run']
    checked = 0
    for path in (HERE/'protected_sha256.json',run/'source_sha256.json',run/'cost_source_sha256.json'):
        for name,digest in read(path).items():
            assert sha(ROOT/name)==digest,name
            checked += 1
    checked_components = 0
    for model in ('go_strong_v1','go_weak_v1'):
        folder = run/'p00_data'/model
        current = read(folder/'candidate.json'); old = read(folder/'reference.json')
        assert current['iterations']==old['iterations']==5000
        assert current['status']==old['status']=='complete'
        assert sum(current['phase_cycles'].values())==current['cycles']
        assert current['cycles']*2/1e6==current['latency_ms']
        for field in ('tree_sha256','node_sram_sha256','child_sram_sha256','chosen_move'):
            assert current[field]==old[field],(model,field)
        for kind in ('node','child'):
            with gzip.open(folder/(kind+'_sram.bin.gz'),'rb') as stream:
                assert hashlib.sha256(stream.read()).hexdigest()==current[kind+'_sram_sha256']
        previous_area = None
        for scenario in ('low_controller_activity','nominal','high_controller_activity'):
            costs = read(folder/(scenario+'_costs.json'))
            parts = {r['id']:r for r in costs['components']}
            assert len(parts)==len(costs['components'])==31
            assert costs['whole_chip_area_mm2'] is None and costs['whole_chip_energy_uj'] is None
            t_seconds = current['cycles']*2e-9
            for row in parts.values():
                assert row['area_um2']>=0 and row['dynamic_energy_uj']>=0 and row['standby_energy_uj']>=0
                assert math.isclose(row['dynamic_energy_uj']+row['standby_energy_uj'],row['energy_uj'],rel_tol=1e-12)
                assert math.isclose(row['average_power_mw']*1e-3*t_seconds,row['energy_uj']*1e-6,rel_tol=1e-12)
                checked_components += 1
            area = sum(r['area_um2'] for r in parts.values())
            energy_j = sum(r['energy_uj']*1e-6 for r in parts.values())
            assert math.isclose(area/1e6,costs['core_area_mm2'],rel_tol=1e-12)
            assert math.isclose(energy_j*1000,costs['core_energy_mj'],rel_tol=1e-12)
            assert math.isclose(energy_j/t_seconds*1000,costs['core_average_power_mw'],rel_tol=1e-12)
            assert math.isclose(costs['average_energy_uj_per_iteration']*5000,energy_j*1e6,rel_tol=1e-12)
            if previous_area is not None: assert area==previous_area
            previous_area = area
            assert parts['adc_lanes']['count']==parts['sample_hold']['count']==32
            assert sum(k.startswith('u_ucb_') for k in parts)==16
            # Scalar conversions are preserved despite more parallel lanes.
            conversions = current['memory']['operations']['neural_adc_conversions']
            assert conversions==old['memory']['operations']['neural_adc_conversions']==6000000
            assert math.isclose(parts['adc_lanes']['dynamic_energy_uj'],conversions*49e-6,rel_tol=1e-12)
            assert parts['adc_lanes']['area_um2']==32*98000
            for name in ('node_sram','child_sram'):
                previous = read(ROOT/'p03_experiments/p79_scalability/p00_runs/run_20260917_155326Z/p01_trained'/(model+'_5000')/'nominal.json')
                source = next(r for r in previous['components'] if r['id']==name)
                assert parts[name]['area_um2']==source['area_um2']
                assert parts[name]['dynamic_energy_uj']==source['dynamic_energy_uj']
    log = (run/'regression.log').read_text()
    tests = int(re.search(r'Ran (\d+) tests',log).group(1))
    assert tests==261 and '\nOK\n' in log and '\nFAILED' not in log
    master = read(ROOT.parent/'p00_recovery/run_20260908_182606Z/source_manifest.json')
    assert entries(Path(master['source']))==master['entries']
    old = read(ROOT/'p03_experiments/p42_reference_validation/before.json')
    old_count = 0
    for field in ('old_checkout_sources','old_user_files'):
        for name,digest in old[field].items():
            assert sha(Path(old['original_repair_checkout'])/name)==digest,name
            old_count += 1
    snapshots = list((ROOT/'p04_results/p04_snapshots').glob('run_*'))
    for folder in snapshots: verify_snapshot(folder)
    report = {'status':'passed','regression_tests':tests,'manifest_entries_checked':checked,
        'component_records_checked':checked_components,'models':2,'cost_scenarios':3,
        'unit_reconciliation':'SI joules / seconds = watts, independently of displayed prefixes',
        'original_master_files_preserved':sum(r['type']=='file' for r in master['entries'].values()),
        'older_checkout_files_preserved':old_count,'frozen_snapshots_preserved':len(snapshots),
        'new_integrated_RTL_validated':False,'physical_PPA_validated':False,'promoted_to_Studio':False}
    write_json(run/'final_verification.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
