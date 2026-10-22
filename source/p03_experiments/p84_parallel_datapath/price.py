# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Price the new execution artifacts, never replace historical results.
# SPDX-License-Identifier: MIT
import csv
import hashlib
import json
from pathlib import Path

from core.architecture.parallel_datapath_costs import parallel_datapath_costs, SCENARIOS
from core.architecture.result_registry import ROOT, write_json

HERE = Path(__file__).resolve().parent
SOURCES = ROOT/'p03_experiments/p79_scalability/p00_runs/run_20260917_155326Z'


def main():
    run = ROOT/json.loads((HERE/'latest.json').read_text())['run']
    sources = json.loads((SOURCES/'sources.json').read_text())
    published = json.loads((SOURCES/'published_adc.json').read_text())
    paths = [Path(__file__),ROOT/'core/architecture/parallel_datapath_costs.py',
        SOURCES/'sources.json',SOURCES/'published_adc.json']
    summary = []; rows = []
    for model in ('go_strong_v1','go_weak_v1'):
        folder = run/'p00_data'/model
        current = json.loads((folder/'candidate.json').read_text())
        old = json.loads((folder/'reference.json').read_text())
        costs_path = SOURCES/'p01_trained'/(model+'_5000')/'nominal.json'
        costs = json.loads(costs_path.read_text()); paths.append(costs_path)
        paths.extend([folder/'candidate.json',folder/'reference.json'])
        for scenario in SCENARIOS:
            result = parallel_datapath_costs(current,old,costs,sources,published,scenario)
            assert abs(sum(r['energy_uj'] for r in result['components'])-result['core_energy_uj'])<1e-9
            assert abs(result['core_average_power_mw']*result['latency_ms']-result['core_energy_uj'])<1e-9
            assert abs(result['average_energy_uj_per_iteration']*5000-result['core_energy_uj'])<1e-9
            write_json(folder/(scenario+'_costs.json'),result)
            summary.append({'model':model,'scenario':scenario,'iterations':5000,
                'latency_ms_per_move':current['latency_ms'],
                'average_latency_us_per_iteration':current['average_latency_us_per_iteration'],
                'energy_mj_per_move':result['core_energy_mj'],
                'average_energy_mj_per_iteration':result['average_energy_mj_per_iteration'],
                'average_energy_uj_per_iteration':result['average_energy_uj_per_iteration'],
                'average_power_mw':result['core_average_power_mw'],'area_mm2':result['core_area_mm2']})
            if scenario=='nominal':
                for part in result['components']: rows.append({'model':model,**part})
        print(model,summary[-2],flush=True)
    for name,data in [('energy_comparison.csv',summary),('components.csv',rows)]:
        with (run/name).open('w') as stream:
            writer = csv.DictWriter(stream,fieldnames=list(data[0])); writer.writeheader(); writer.writerows(data)
    manifest = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    write_json(run/'cost_source_sha256.json',manifest)
    verification = json.loads((run/'verification.json').read_text())
    verification.update(energy_status='engineering_estimates_reconciled',physical_cost_validation=False,
        component_owners=31,energy_scenarios=3,per_iteration_scope='full-search average, not an isolated first iteration')
    write_json(run/'verification.json',verification)
    for p in (Path(__file__),ROOT/'core/architecture/parallel_datapath_costs.py'):
        (run/'p02_sources'/p.name).write_bytes(p.read_bytes())
    print('Energy accounting reconciled',run,flush=True)


if __name__=='__main__': main()
