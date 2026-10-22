# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Bind the finished tables, verify every cost identity and preserve old artifacts.
# SPDX-License-Identifier: MIT
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import tarfile

import numpy as np

from core.architecture.result_registry import ROOT, write_json
from core.architecture.result_snapshot import verify_snapshot
from p03_experiments.p35_component_ppa.verify_preservation import entries
from p03_experiments.p79_scalability.run import HERE, sha
from p03_experiments.p79_scalability.model import BOARDS


def read(path):
    with path.open() as stream: return list(csv.DictReader(stream))


def main():
    out = ROOT/json.loads((HERE/'latest.json').read_text())['run']
    status = json.loads((out/'sweep_status.json').read_text())
    assert status['status']=='complete' and status['primary_cases']==18
    assert json.loads((out/'candidate_verification.json').read_text())['status']=='passed'
    tests = json.loads((out/'regression_tests.json').read_text())
    review = json.loads((out/'regression_review.json').read_text())
    assert tests['tests']==249 and tests['failures']==1 and tests['errors']==tests['skipped']==0
    assert review['isolated_reproduction'] and review['passed']==248
    for name,digest in review['unchanged_HEAD_sources'].items(): assert sha(ROOT/name)==digest
    checks = 0
    for folder in ('p01_trained','p02_sweep'):
        for path in (out/folder).rglob('*.json'):
            cost = json.loads(path.read_text())
            if cost.get('profile')!='revised_core_engineering_estimates_v1': continue
            rows = cost['components']; assert len(rows)==len({r['id'] for r in rows})==19
            assert math.isclose(sum(r['area_um2'] for r in rows)/1e6,cost['core_area_mm2'],rel_tol=1e-12)
            assert math.isclose(sum(r['energy_uj'] for r in rows),cost['core_energy_uj'],rel_tol=1e-12)
            for row in rows:
                assert math.isclose(row['average_power_mw']*cost['latency_ms'],row['energy_uj'],rel_tol=1e-12)
                assert math.isclose(row['dynamic_energy_uj']+row['standby_energy_uj'],row['energy_uj'],rel_tol=1e-12)
                assert row['source'] and row['status'] and row['assumptions']
                checks += 1
            assert cost['whole_chip_area_mm2'] is None and cost['whole_chip_energy_uj'] is None
    totals = read(out/'p00_data/totals.csv')
    coverage = []
    for board,budgets in BOARDS.items():
        rows = [r for r in totals if int(r['board_size'])==board]
        assert len(rows)==3 and {int(r['requested_iterations']) for r in rows}==set(budgets)
        assert len({r['area_mm2'] for r in rows})==1
        for row in rows:
            result = json.loads((ROOT/row['source_result']).read_text())
            assert result['installed_sram_bytes']==2097152
            assert sum(result['phase_cycles'].values())==result['cycles']
            assert result['latency_ms']==result['cycles']/500000
            assert result['memory']['nodes_used']<=result['memory']['config']['node_capacity']
            assert result['completed_iterations']<=result['requested_iterations']
            if result['status']=='complete': assert result['completed_iterations']==result['requested_iterations']
            if result['status']=='memory_limited': assert result['termination']['reason']=='memory_limit'
            coverage.append({'board_size':board,'tier':row['tier'],
                'completed':int(row['completed_iterations']),'requested':int(row['requested_iterations']),
                'status':row['status'],'limit':result['termination']['resource'] if result['termination'] else None})
    primary = {(r['board_size'],r['requested_iterations']):r for r in totals}
    seeds = []
    sensitivity = read(out/'p00_data/sensitivity.csv')
    for board,budgets in BOARDS.items():
        reference = primary[(str(board),str(budgets[1]))]
        rows = [reference]+[r for r in sensitivity if int(r['board_size'])==board and r['scenario']=='seed_variation']
        assert len(rows)==3
        assert len({r['area_mm2'] for r in rows})==1
        seeds.append({'board_size':board,'requested_iterations':budgets[1],
            'power_min_mw':min(float(r['power_mw']) for r in rows),
            'power_max_mw':max(float(r['power_mw']) for r in rows),
            'completed_counts':[int(r['completed_iterations']) for r in rows],
            'all_completed':all(r['status']=='complete' for r in rows)})
    checked = {}
    for name in ('source_sha256.json','execution_source_sha256.json','protected_sha256.json'):
        record = json.loads((out/name).read_text())
        for path,digest in record.items(): assert sha(ROOT/path)==digest,path
        checked[name] = len(record)
    # Preserve the original project, older checkout and old frozen results.
    master = json.loads((ROOT.parent/'p00_recovery/run_20260908_182606Z/source_manifest.json').read_text())
    assert entries(Path(master['source']))==master['entries']
    old = json.loads((ROOT/'p03_experiments/p42_reference_validation/before.json').read_text())
    old_count = 0
    for field in ('old_checkout_sources','old_user_files'):
        for name,digest in old[field].items():
            assert sha(Path(old['original_repair_checkout'])/name)==digest,name
            old_count += 1
    snapshots = list((ROOT/'p04_results/p04_snapshots').glob('run_*'))
    for folder in snapshots: verify_snapshot(folder)
    write_json(out/'verification.json',{'status':'accounting_passed_with_preexisting_test_failure','component_rows_checked':checks,
        'regression_tests':tests,'regression_review':review,'source_and_protected_checks':checked,'coverage':coverage,
        'seed_sensitivity':seeds,'unchanged_original_files':sum(r['type']=='file' for r in master['entries'].values()),
        'unchanged_old_checkout_files':old_count,'unchanged_frozen_snapshots':len(snapshots),
        'area_invariant_to_budget':True,'19_owners_counted_once':True,
        'preloaded_core_estimate_complete':True,'physical_validation_complete':False,
        'whole_chip_PPA_available':False,'paper_updated':False})
    final_sources = [p for p in HERE.iterdir() if p.is_file() and p.suffix in ('.py','.md')]
    final_sources += [ROOT/'PLAN_ROUND_79.md',ROOT/'ARCH_MENTOR.md']
    write_json(out/'final_source_sha256.json',{str(p.relative_to(ROOT)):sha(p) for p in final_sources})
    execution = json.loads((out/'execution_source_sha256.json').read_text())
    execution.update({str(p.relative_to(ROOT)):sha(p) for p in final_sources})
    with tarfile.open(out/'source_snapshot.tar.gz','w:gz') as archive:
        for name in sorted(execution): archive.add(ROOT/name,arcname=name,recursive=False)
    write_json(out/'environment.json',{'python':platform.python_version(),'numpy':np.__version__,
        'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'dirty_checkout':True,'source_snapshot':'source_snapshot.tar.gz',
        'commands':['python -B -m p03_experiments.p79_scalability.prepare',
                    'python -B -m p03_experiments.p79_scalability.run',
                    'python -B -m p03_experiments.p79_scalability.verify',
                    'python -B -m p03_experiments.p79_scalability.plot',
                    'python -B -m p03_experiments.p79_scalability.finalize']})
    (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(out))+'\n'
        for p in sorted(out.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
    print('FINAL PASS',checks,'component rows,',len(coverage),'configurations',flush=True)


if __name__=='__main__': main()
