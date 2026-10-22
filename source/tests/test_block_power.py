# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Block accounting must preserve idle clocks, elapsed leakage and missing costs.
# SPDX-License-Identifier: MIT
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.architecture.block_activity import BLOCKS, activity_record
from core.architecture.iteration_model import CompleteSimulation


class BlockActivityTests(unittest.TestCase):
    def test_each_phase_partitions_time_without_changing_the_search(self):
        model = CompleteSimulation(9, 4)
        for event in model.steps():
            activity = activity_record(dict(model.block_active_cycles), model.cycles)
            for row in activity['blocks'].values():
                self.assertEqual(row['active_cycles'] + row['idle_cycles'], model.cycles)
        self.assertEqual(model.cycles, 114074)
        self.assertEqual(dict(model.block_active_cycles), {'u_sel': 2110, 'u_ucb': 223,
            'u_nn': 106484, 'u_upd': 5460, 'u_node_router': 4108,
            'u_child_router': 324, 'top_level_glue': 114074})

    def test_invalid_time_and_missing_instances_fail(self):
        good = dict.fromkeys(BLOCKS, 0)
        for bad in ({}, good | {'u_sel': -1}, good | {'u_sel': 2}, good | {'u_sel': True}):
            with self.assertRaises(ValueError): activity_record(bad, 1)


class BlockPowerTests(unittest.TestCase):
    def test_energy_units_idle_and_leakage(self):
        from core.architecture.block_power import block_energy
        powers = {'active_dynamic_mw': 10, 'idle_dynamic_mw': 2, 'leakage_mw': 1}
        result = block_energy(100, 400, powers, 500)
        self.assertAlmostEqual(result['dynamic_energy_nj'], 3.6)
        self.assertAlmostEqual(result['leakage_energy_nj'], 1)
        self.assertAlmostEqual(result['energy_nj'], 4.6)
        self.assertAlmostEqual(result['average_power_mw'], 4.6)
        waiting = block_energy(100, 900, powers, 500)
        self.assertAlmostEqual(waiting['dynamic_energy_nj'], 5.6)
        self.assertAlmostEqual(waiting['leakage_energy_nj'], 2)
        self.assertAlmostEqual(waiting['average_power_mw'], 3.8)

    def test_missing_coefficients_are_not_zero(self):
        from core.architecture.block_power import block_energy
        result = block_energy(100, 400, {'active_dynamic_mw': None,
            'idle_dynamic_mw': None, 'leakage_mw': 1}, 500)
        self.assertIsNone(result['dynamic_energy_nj'])
        self.assertEqual(result['leakage_energy_nj'], 1)
        self.assertIsNone(result['energy_nj'])
        self.assertIsNone(result['average_power_mw'])
        for value in (-1, float('nan'), float('inf'), True):
            with self.assertRaises(ValueError):
                block_energy(100, 400, {'active_dynamic_mw': value,
                    'idle_dynamic_mw': 0, 'leakage_mw': 0}, 500)

    def test_report_estimates_and_ledger_keep_native_nodes_separate(self):
        from core.architecture.complete_costs import complete_costs
        model = CompleteSimulation(9, 2); list(model.steps())
        costs = complete_costs('cacti_22nm_lstp', model.memory.operations, model.cycles,
            model.neural.profile, model.memory.config, model.phase_cycles, model.block_active_cycles)
        power = costs['block_power']
        self.assertEqual(len(power['components']), 7)
        self.assertEqual(power['source_node_nm'], 65)
        self.assertGreater(power['energy_nj'], 0)
        self.assertEqual(power['status'], 'vectorless_activity_estimate')
        self.assertIsNone(costs['ledger']['whole_chip_power_mw'])
        self.assertAlmostEqual(costs['ledger']['known_energy_uj'], costs['sram']['energy_uj'] + power['target_22nm_energy_nj']/1000 + costs['ledger']['peripheral_energy_uj'])
        self.assertLess(power['target_22nm_energy_nj'], power['energy_nj'])
        update = next(row for row in costs['ledger']['components'] if row['id'] == 'u_upd')
        self.assertEqual(update['block_power']['active_cycles'], model.block_active_cycles['u_upd'])
        self.assertIn('block_power', costs['ledger']['source_identities'])

    def test_profile_rejects_wrong_binding_and_unsourced_numbers(self):
        from core.architecture.block_power import TABLE, load_power_table
        original = json.loads(TABLE.read_text())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'table.json'
            bad = copy.deepcopy(original); bad['catalog_sha256'] = '0' * 64
            path.write_text(json.dumps(bad))
            with patch('core.architecture.block_power.TABLE', path):
                with self.assertRaisesRegex(ValueError, 'catalog'): load_power_table(original['catalog_sha256'])
            bad = copy.deepcopy(original)
            bad['cases']['imc_ucb_score']['powers_mw']['active_dynamic_mw'] = 1
            path.write_text(json.dumps(bad))
            with patch('core.architecture.block_power.TABLE', path):
                with self.assertRaisesRegex(ValueError, 'source report'): load_power_table(original['catalog_sha256'])
            bad = copy.deepcopy(original); bad['cases']['imc_ucb_score']['evidence']['sources'] = {}
            path.write_text(json.dumps(bad))
            with patch('core.architecture.block_power.TABLE', path):
                with self.assertRaisesRegex(ValueError, 'evidence'): load_power_table(original['catalog_sha256'])

    def test_native_subtotal_counts_overlapping_blocks_once(self):
        from core.architecture.block_power import TABLE, block_power_accounting
        from core.architecture.digital_costs import digital_accounting
        model = CompleteSimulation(9, 1)
        digital = digital_accounting(model.neural.profile, model.memory.config)
        table = json.loads(TABLE.read_text()); table['sha256'] = 'synthetic_unit_test_only'
        for entry in table['cases'].values():
            entry['powers_mw'] = {'active_dynamic_mw': 6, 'idle_dynamic_mw': 2, 'leakage_mw': 1}
        active = dict.fromkeys(BLOCKS, 100); active['top_level_glue'] = 500
        with patch('core.architecture.block_power.load_power_table', return_value=table):
            result = block_power_accounting(digital, 500, active)
            self.assertAlmostEqual(result['energy_nj'], 29.8)
            self.assertAlmostEqual(result['average_power_mw'], 29.8)
            self.assertAlmostEqual(result['target_22nm_energy_nj'], 22.8*(22/65)*.8**2 + 7)
            bad = copy.deepcopy(digital); bad['components'].pop()
            with self.assertRaisesRegex(ValueError, 'exactly once'): block_power_accounting(bad, 500, active)
            bad = copy.deepcopy(digital); bad['components'][0]['parameters_required']['BOARD_SIZE'] = 5
            self.assertIsNone(block_power_accounting(bad, 500, active)['energy_nj'])

    def test_report_units_and_clock_pin_power_are_separate(self):
        from core.architecture.block_power import report_power
        text = '''Dynamic Power Units = 1mW
Total Dynamic Power = 6000 uW
Cell Leakage Power = 100000 nW
clock_network 1.5000 0.5000 10.0 2.0100 ( 50%) i
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'power.rpt'; path.write_text(text)
            for name,value in {'dynamic_mw':6, 'clock_dynamic_mw':2, 'leakage_mw':.1}.items():
                self.assertAlmostEqual(report_power(path)[name],value)
            path.write_text(text.replace('1mW','1000uW'))
            self.assertEqual(report_power(path)['clock_dynamic_mw'],2)
            path.write_text(text.replace('1.5000','8.5000'))
            with self.assertRaisesRegex(ValueError,'split'): report_power(path)
            path.write_text(text.replace('clock_network','missing_clock'))
            with self.assertRaisesRegex(ValueError,'clock power'): report_power(path)

    def test_idle_clock_floor_and_leakage_persist_for_every_parent(self):
        from core.architecture.block_power import TABLE, block_power_accounting
        from core.architecture.digital_costs import digital_accounting
        model = CompleteSimulation(9,1)
        digital = digital_accounting(model.neural.profile,model.memory.config)
        idle = block_power_accounting(digital,500,dict.fromkeys(BLOCKS,0))
        busy = block_power_accounting(digital,500,dict.fromkeys(BLOCKS,500))
        for quiet,working in zip(idle['components'],busy['components']):
            self.assertEqual(quiet['dynamic_energy_nj'],quiet['powers_mw']['idle_dynamic_mw'])
            self.assertEqual(working['dynamic_energy_nj'],working['powers_mw']['active_dynamic_mw'])
            self.assertEqual(quiet['leakage_energy_nj'],working['leakage_energy_nj'])
            self.assertEqual(quiet['target_22nm_leakage_energy_nj'],quiet['leakage_energy_nj'])
            self.assertGreater(quiet['energy_nj'],0)
        zero = block_power_accounting(digital,0,dict.fromkeys(BLOCKS,0))
        self.assertEqual(zero['energy_nj'],0)
        self.assertIsNone(zero['target_22nm_power_mw'])

    def test_small_configuration_only_prices_compatible_parents(self):
        from core.architecture.complete_costs import complete_costs
        model = CompleteSimulation(3,2); list(model.steps())
        costs = complete_costs('cacti_22nm_lstp',model.memory.operations,model.cycles,
            model.neural.profile,model.memory.config,model.phase_cycles,model.block_active_cycles)
        power = costs['block_power']
        self.assertIsNone(power['target_22nm_energy_nj'])
        priced = [r for r in power['components'] if r['target_22nm_energy_nj'] is not None]
        self.assertEqual({r['instance'] for r in priced},{'u_ucb','u_node_router','u_child_router'})
        self.assertAlmostEqual(costs['ledger']['known_energy_uj'],costs['sram']['energy_uj'] + sum(r['target_22nm_energy_nj'] for r in priced)/1000 + costs['ledger']['peripheral_energy_uj'])
        self.assertIsNone(costs['ledger']['whole_chip_energy_uj'])


if __name__ == '__main__': unittest.main()
