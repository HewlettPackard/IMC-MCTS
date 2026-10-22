# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Repeat canonical searches with one ledger while preserving all prior numerical results.
# SPDX-License-Identifier: MIT
import csv
import hashlib
import json
import math
from pathlib import Path

from core.architecture.result_registry import ROOT, catalog, new_run, run_case, verify_run, write_json
from core.architecture.result_snapshot import SNAPSHOTS, freeze_repeats, verify_snapshot
from core.architecture.cost_ledger import ledger_fields


def main():
    out = new_run(Path(__file__).parent/'p00_runs')
    checks = {}; pairs = []; records = []
    prior = verify_snapshot(SNAPSHOTS/'run_20260910_015927Z')
    for snapshot in sorted(SNAPSHOTS.glob('run_*')):
        verify_snapshot(snapshot); checks['preserved_'+snapshot.name]=True
    named = {case['id'] for case in catalog()['cases']}
    print(out.relative_to(ROOT),flush=True)
    for case in prior['cases']:
        old = verify_run(ROOT/case['runs'][0])
        config = old['identity']['configuration']['requested']
        arguments = {'case_id':case['case_id']} if case['case_id'] in named else {'custom':config}
        first,result = run_case(**arguments); second,repeat = run_case(**arguments)
        name = case['case_id']; pairs.append((first,second))
        checks[name+'_exact_repeat'] = result==repeat
        for key in ('metrics','tree_sha256','node_sram_sha256','child_sram_sha256','last_value_q17',
                    'random_state','preload','evaluator','analog_readout','phase_cycles','memory','component_estimates'):
            checks[name+'_'+key+'_unchanged'] = result[key]==old[key]
        checks[name+'_prior_costs_preserved'] = {k:v for k,v in result['costs'].items() if k!='ledger'}==old['costs']
        ledger = result['costs']['ledger']
        checks[name+'_ledger_area_reconciles'] = math.isclose(ledger['known_area_mm2'],result['component_estimates']['known_area_mm2'],abs_tol=1e-12)
        checks[name+'_ledger_energy_reconciles'] = math.isclose(ledger['known_energy_uj'],result['costs']['sram']['energy_uj'],abs_tol=1e-12)
        checks[name+'_whole_chip_pending'] = all(ledger[k] is None for k in ('whole_chip_area_mm2','whole_chip_energy_uj','whole_chip_power_mw'))
        checks[name+'_single_target'] = ledger['technology_nm']==22 and ledger['policy']['area']['applications']==1
        checks[name+'_policy_archived'] = 'core/architecture/technology_scaling.json' in result['identity']['source_sha256']
        checks[name+'_distinct_execution_identity'] = result['identity']['execution_sha256']!=old['identity']['execution_sha256']
        with (first/'summary.csv').open() as stream: row=next(csv.DictReader(stream))
        checks[name+'_csv_ledger_matches'] = all(row[k]==str(v) for k,v in ledger_fields(result['costs']).items())
        records.append({'case_id':name,'runs':[str(p.relative_to(ROOT)) for p in (first,second)],
            'core_cycles':result['metrics']['core_cycles'],'known_area_mm2':ledger['known_area_mm2'],
            **ledger_fields(result['costs'])})
        write_json(out/'progress.json',{'checks':checks,'records':records})
        print(name,result['metrics']['core_cycles'],'cycles; ledger verified',flush=True)
    if not all(checks.values()): raise AssertionError({k:v for k,v in checks.items() if not v})
    snapshot = freeze_repeats(pairs)
    write_json(out/'metadata.json',{'status':'passed','checks':checks,'records':records,
        'snapshot':str(snapshot.relative_to(ROOT)),'benchmarks_executed':False,'full_physical_ppa':False})
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file()))
    print('Passed',len(checks),'checks;',snapshot.name,flush=True)


if __name__=='__main__': main()
