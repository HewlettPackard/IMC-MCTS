# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Fresh paired execution, source checks and independent accounting identities.
# SPDX-License-Identifier: MIT
from copy import deepcopy
import hashlib
from itertools import zip_longest
import json
import math
from pathlib import Path
import time
import unittest
import sys

import numpy as np

from core.algorithm.model_catalog import load_model
from core.architecture.ucb_overlap import OverlappedUCBGoSimulation
from core.architecture.result_registry import ROOT, write_json
from core.architecture.run_identity import tree_sha256
from p03_experiments.p62_component_costs.verify_large import check_packed
from p03_experiments.p79_scalability.model import DiagnosticSearch, BOARDS
from p03_experiments.p79_scalability.costs import estimate, SCENARIOS
from p03_experiments.p79_scalability.run import HERE, FROZEN, sha


def regressions(out):
    with (out/'regression_tests.txt').open('w') as stream:
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName('tests.'+p.stem)
            for p in sorted((ROOT/'tests').glob('test_*.py')))
        result = unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    write_json(out/'regression_tests.json',{'tests':result.testsRun,'failures':len(result.failures),
        'errors':len(result.errors),'skipped':len(result.skipped),'status':'passed' if result.wasSuccessful() else 'failed'})
    assert result.wasSuccessful(),str(out/'regression_tests.txt')
    print('REGRESSION PASS',result.testsRun,flush=True)


def main():
    out = ROOT/json.loads((HERE/'latest.json').read_text())['run']
    sources = json.loads((out/'sources.json').read_text()); adc = json.loads((out/'published_adc.json').read_text())
    checks = []
    for name in ('source_sha256.json','protected_sha256.json'):
        for path,digest in json.loads((out/name).read_text()).items():
            assert sha(ROOT/path)==digest,path
    for name in ('go_strong_v1','go_weak_v1'):
        weights,_ = load_model(name,9)
        for budget in (500,5000):
            model = DiagnosticSearch(9,budget,weights=weights)
            for _ in model.steps(): pass
            case = FROZEN/(name+'_'+str(budget))
            prior = json.loads((case/'overlap_result.json').read_text())
            assert model.completed==budget and model.status=='complete'
            assert model.cycles==prior['cycles']
            assert dict(model.phase_cycles)==prior['phase_cycles']
            assert tree_sha256(model.memory.nodes)==prior['tree_sha256']
            assert hashlib.sha256(model.memory.node_sram).hexdigest()==prior['node_sram_sha256']
            assert hashlib.sha256(model.memory.child_sram).hexdigest()==prior['child_sram_sha256']
            assert dict(model.memory.operations)==prior['memory']['operations']
            check_packed(model)
            known = json.loads((case/'overlap_costs.json').read_text())
            cost = estimate(model,sources,adc)
            for row in known['components']:
                if row['area_um2'] is None: continue
                new = next(x for x in cost['components'] if x['id']==row['id'])
                for key in ('area_um2','energy_uj','average_power_mw'):
                    assert math.isclose(new[key],row[key],rel_tol=1e-12),(row['id'],key,new[key],row[key])
            checks.append({'case':name+'_'+str(budget),'exact_frozen_tree_and_SRAM':True,
                'exact_cycles_and_traffic':True,'unchanged_owners_match':8,'cycles':model.cycles})
            print('PASS trained',name,budget,flush=True)
    weights,_ = load_model('go_strong_v1',9)
    a = OverlappedUCBGoSimulation(9,100,weights=weights,turn_indicator=True,cam_entries=1024)
    b = DiagnosticSearch(9,100,weights=weights)
    assert a.neural.schedule==b.neural.schedule and a.neural.coefficients==b.neural.coefficients
    for old,new in zip_longest(a.steps(),b.steps()):
        assert old==new
        if new['phase']=='neural': assert a.neural.last_state==b.neural.last_state
    checks.append({'case':'paired_100','exact_phase_trace_and_neural_states':True})
    for board in BOARDS:
        models = [DiagnosticSearch(board,20,seed=2) for _ in range(2)]
        for model in models:
            for _ in model.steps(): pass
            check_packed(model)
        a,b = models
        assert a.cycles==b.cycles and a.memory.node_sram==b.memory.node_sram
        assert a.memory.child_sram==b.memory.child_sram and a.neural.last_state==b.neural.last_state
        for scenario in SCENARIOS:
            costs = estimate(a,sources,adc,scenario)
            assert len(costs['components'])==19 and not costs['missing_owners']
            assert math.isclose(costs['core_average_power_mw']*a.cycles/500000,costs['core_energy_uj'],rel_tol=1e-12)
            physical = next(r for r in costs['components'] if r['id']=='physical_overhead')
            base = sum(r['area_um2'] for r in costs['components'] if r['id']!='physical_overhead')
            assert math.isclose(physical['area_um2'],SCENARIOS[scenario]['physical']*base,rel_tol=1e-12)
            assert costs['whole_chip_energy_uj'] is None
        original = estimate(a,sources,adc)
        a.cycles *= 2
        stretched = estimate(a,sources,adc)
        assert original['core_area_mm2']==stretched['core_area_mm2']
        for old,new in zip(original['components'],stretched['components']):
            if old['id'].startswith('u_ucb_'):
                assert old['details']['switch_work_energy_uj']==new['details']['switch_work_energy_uj']
                assert new['details']['clock_energy_uj']==2*old['details']['clock_energy_uj']
            if old['id'] in ('cim_arrays','adc_lanes','node_sram','child_sram'):
                assert old['dynamic_energy_uj']==new['dynamic_energy_uj']
        checks.append({'case':'board_'+str(board),'seed_repeat':True,'packed_memory':True,
            'cost_scenarios':4,'area_independent_of_elapsed_time':True,'UCB_switch_work_conserved':True})
    # Validate all collected rows once the sweep has finished.
    write_json(out/'candidate_verification.json',{'status':'passed','checks':checks,
        'analog_accuracy_validated':False,'new_physical_timing_validated':False})
    print('Candidate checks passed',len(checks),flush=True)
    regressions(out)


if __name__=='__main__':
    if '--regressions-only' in sys.argv:
        regressions(ROOT/json.loads((HERE/'latest.json').read_text())['run'])
    else: main()
