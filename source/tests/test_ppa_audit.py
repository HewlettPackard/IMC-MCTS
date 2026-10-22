# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Independent evidence and deliberate corruptions guard against mixed PPA versions.
# SPDX-License-Identifier: MIT
import ast
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import unittest

from core.architecture.complete_costs import complete_costs
from p03_experiments.p51_ppa_audit.oracle import ROOT, FROZEN, Sources, compare, expected

AUDIT = ROOT / 'p03_experiments/p51_ppa_audit/p00_runs/run_20260914_204720Z'


class PPAAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = Sources()
        cls.result = json.loads((ROOT / FROZEN).read_text())

    def test_frozen_reference_and_raw_sources_still_match(self):
        record = json.loads((AUDIT / 'reference.json').read_text())
        self.assertEqual(hashlib.sha256((ROOT / FROZEN).read_bytes()).hexdigest(), record['result_sha256'])
        self.assertEqual(self.result['identity']['configuration_sha256'], record['configuration_sha256'])
        self.assertEqual(self.result['costs']['ledger']['sha256'], record['cost_model_sha256'])
        values, _ = compare(self.result, self.sources)
        def same(actual,expected):
            if isinstance(expected,dict):
                self.assertEqual(set(actual),set(expected))
                for key in expected:same(actual[key],expected[key])
            elif isinstance(expected,list):
                self.assertEqual(len(actual),len(expected))
                for a,b in zip(actual,expected):same(a,b)
            elif isinstance(expected,float):
                self.assertTrue(math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-12),(actual,expected))
            else:self.assertEqual(actual,expected)
        same(values,record['expected_owners'])
        for path, sha in json.loads((AUDIT / 'sources.json').read_text()).items():
            source=ROOT/path
            if path=='core/architecture/peripheral_assumptions.json':
                source=ROOT/'p03_experiments/p105_adc_standby/p00_sources/peripheral_assumptions_v1.json'
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), sha, path)

    def test_oracle_has_no_production_or_numerical_library_imports(self):
        syntax = ast.parse((ROOT / 'p03_experiments/p51_ppa_audit/oracle.py').read_text())
        allowed = {'csv', 'gzip', 'hashlib', 'json', 'math', 'pathlib', 're', 'xml', 'zipfile'}
        for node in ast.walk(syntax):
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module.split('.')[0], allowed)
            if isinstance(node, ast.Import):
                self.assertTrue(all(n.name.split('.')[0] in allowed for n in node.names))

    def test_current_calculator_matches_independent_frozen_workload(self):
        result = deepcopy(self.result)
        result['costs'] = complete_costs(result['costs']['sram']['profile'], result['memory']['operations'],
            result['metrics']['core_cycles'], result['neural']['profile'], result['memory']['config'],
            result['phase_cycles'], {k: v['active_cycles'] for k, v in result['block_activity']['blocks'].items()})
        compare(result, self.sources)

    def test_wrong_area_power_energy_or_cycles_is_rejected(self):
        for field in ('area_um2', 'average_power_mw', 'energy_uj', 'active_cycles', 'count'):
            result = deepcopy(self.result)
            row = next(r for r in result['costs']['ledger']['components'] if r['id'] == 'u_nn')
            row[field] += 1
            with self.subTest(field=field), self.assertRaises(AssertionError):
                compare(result, self.sources)

    def test_shared_parent_or_children_cannot_be_counted_twice(self):
        result = deepcopy(self.result)
        result['costs']['ledger']['components'].append(deepcopy(result['costs']['ledger']['components'][0]))
        with self.assertRaises(AssertionError):
            compare(result, self.sources)
        result = deepcopy(self.result)
        parent = next(r for r in result['costs']['ledger']['components'] if r['id'] == 'u_nn')
        parent['children'][0]['average_power_mw'] = 1
        with self.assertRaises(AssertionError):
            compare(result, self.sources)

    def test_paper_models_remain_partial_for_both_readouts(self):
        for model in ('go_strong_v1', 'go_weak_v1'):
            for readout in ('sustained_drive_v1', 'column_hold_v1'):
                path = next((AUDIT / 'p01_probes' / (model + '_lstp_' + readout)).glob('run_*/result.json'))
                result = json.loads(path.read_text())
                values, _ = compare(result, self.sources)
                self.assertIsNone(values['u_nn']['area_um2'])
                self.assertIsNone(values['u_nn']['energy_uj'])
                next(r for r in result['costs']['ledger']['components'] if r['id'] == 'u_nn')['area_um2'] = 5579.364
                with self.assertRaises(AssertionError):
                    compare(result, self.sources)

    def test_changed_workbook_value_and_clock_are_detected(self):
        sources = deepcopy(self.sources)
        sources.cells['New_Architecture']['C14']['value'] *= (22 / 65) ** 2
        with self.assertRaises(AssertionError):
            compare(self.result, sources)
        result = deepcopy(self.result)
        result['neural']['profile']['clock_mhz'] = 1000
        with self.assertRaises(AssertionError):
            compare(result, self.sources)

    def test_more_elapsed_time_is_not_more_installed_area(self):
        longer = deepcopy(self.result)
        longer['metrics']['core_cycles'] *= 2
        a = expected(self.result, self.sources)
        b = expected(longer, self.sources)
        self.assertEqual([r['area_um2'] for r in a.values()], [r['area_um2'] for r in b.values()])
        self.assertEqual(a['adc_lanes']['dynamic_energy_uj'], b['adc_lanes']['dynamic_energy_uj'])
        self.assertEqual(2 * a['adc_lanes']['standby_energy_uj'], b['adc_lanes']['standby_energy_uj'])
        self.assertGreater(b['u_nn']['energy_uj'], a['u_nn']['energy_uj'])


if __name__ == '__main__':
    unittest.main()
