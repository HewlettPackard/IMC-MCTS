# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Accounting and waveform boundaries that prevent mixed-node or mixed-workload totals.
# SPDX-License-Identifier: MIT
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.architecture.complete_costs import complete_costs
from core.architecture.cost_ledger import POLICY, cost_ledger, scaling_policy
from core.architecture.crossbar_workbook import component_estimates
from core.architecture.iteration_model import CompleteSimulation
from p03_experiments.p24_power_model.replay import gate_top, normalize_vcd


class CostLedgerTests(unittest.TestCase):
    def setUp(self):
        self.model = CompleteSimulation(9,2)
        list(self.model.steps())

    def costs(self, cycles=None):
        m = self.model
        return complete_costs('cacti_22nm_lstp',m.memory.operations,m.cycles if cycles is None else cycles,
            m.neural.profile,m.memory.config,m.phase_cycles)

    def test_missing_energy_is_not_zero_or_vectorless_power(self):
        costs = self.costs(); ledger = costs['ledger']
        self.assertAlmostEqual(ledger['known_energy_uj'],costs['sram']['energy_uj']+ledger['peripheral_energy_uj'])
        self.assertIsNone(ledger['whole_chip_energy_uj'])
        self.assertIsNone(ledger['whole_chip_power_mw'])
        update = [r for r in ledger['components'] if r['id']=='u_upd']
        self.assertEqual(len(update),1)
        self.assertGreater(update[0]['native_65nm_power']['dynamic_mw'],0)
        self.assertIsNone(update[0]['energy_uj'])
        self.assertEqual(update[0]['scaling_applications'],1)
        self.assertNotIn('CAM macro',ledger['missing_area'])
        self.assertNotIn('CIM cell arrays',ledger['missing_energy'])
        self.assertIn(update[0]['component'],ledger['missing_energy'])

    def test_leakage_uses_elapsed_time_and_power_is_energy_over_time(self):
        first = self.costs(); second = self.costs(self.model.cycles*2)
        self.assertEqual(first['sram']['dynamic_energy_nj'],second['sram']['dynamic_energy_nj'])
        self.assertEqual(first['sram']['leakage_energy_nj']*2,second['sram']['leakage_energy_nj'])
        self.assertEqual(first['ledger']['known_area_mm2'],second['ledger']['known_area_mm2'])
        self.assertAlmostEqual(second['ledger']['known_average_power_mw'],
            1000*second['ledger']['known_energy_uj']/second['sram']['latency_us'])

    def test_duplicate_parent_and_unreviewed_scaling_fail(self):
        m = self.model
        estimates = component_estimates(m.neural.profile,'cacti_22nm_lstp',m.memory.config)
        duplicate = copy.deepcopy(next(r for r in estimates['components'] if r.get('instance')=='u_upd'))
        estimates['components'].append(duplicate)
        with self.assertRaisesRegex(ValueError,'appears twice'): cost_ledger(estimates,self.costs()['sram'])
        policy = json.loads(POLICY.read_text())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'policy.json'
            for metric in ('dynamic_energy','leakage'):
                bad = copy.deepcopy(policy); bad[metric]['factor']=policy['legacy_power']['factor']
                path.write_text(json.dumps(bad))
                with patch('core.architecture.cost_ledger.POLICY',path):
                    with self.assertRaisesRegex(ValueError,'reviewed'): scaling_policy()


class ActivityBoundaryTests(unittest.TestCase):
    def test_vcd_rebases_only_counted_cycles_and_excludes_reset_tail(self):
        text = '$timescale\n 1ps\n$end\n$var wire 1 ! clk $end\n$enddefinitions $end\n#7100\n$dumpvars\n0!\n$end\n#8000\n1!\n#9000\n0!\n#11100\n$dumpoff\nx!\n$end\n#20000\n0!\n'
        with tempfile.TemporaryDirectory() as folder:
            raw = Path(folder)/'raw.vcd'; target=Path(folder)/'out.vcd'; raw.write_text(text)
            window = normalize_vcd(raw,target,'7.100','11.100',2)
            self.assertEqual(window['duration_ns'],4)
            self.assertEqual(window['unknown_value_events'],0)
            self.assertIn('#0\n$dumpvars',target.read_text())
            self.assertTrue(target.read_text().endswith('#4000\n'))
            self.assertNotIn('x!',target.read_text())
            with self.assertRaisesRegex(ValueError,'counted'): normalize_vcd(raw,target,'7.100','11.100',3)

    def test_gate_parent_replacement_cannot_remove_other_instances(self):
        source = '''module core;
    imc_router #(.BANKS(3), .W(W)) u_node_router (
        .clk(clk)
    );
    imc_update #(.W(W)) u_upd (
        .clk(clk)
    );
endmodule
'''
        gate = '    module imc_update_W21 (clk);\n input clk;\nendmodule\n'
        replaced, mapped = gate_top(source,gate,'u_upd','imc_update_W21')
        self.assertIn('imc_router #(.BANKS(3), .W(W)) u_node_router',replaced)
        self.assertIn('activity__imc_update_W21 u_upd (',replaced)
        self.assertIn('module activity__imc_update_W21',mapped)
        with self.assertRaisesRegex(ValueError,'replacement count'): gate_top(source,gate,'u_missing','imc_update_W21')


if __name__=='__main__': unittest.main()
