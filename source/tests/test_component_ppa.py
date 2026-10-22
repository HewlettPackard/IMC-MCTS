# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Verify source-derived costs, complete ownership and workload PPA exports.
# SPDX-License-Identifier: MIT
import csv
import math
from pathlib import Path
import re
import tempfile
import unittest

from core.architecture.analog_readout import BUFFERED, configure_readout
from core.architecture.component_inventory import inventory_rows, write_component_csv
from core.architecture.complete_costs import complete_costs
from core.architecture.crossbar_workbook import component_estimates, workbook_source
from core.architecture.iteration_model import CompleteSimulation
from core.architecture.peripheral_costs import peripheral_sources
from core.architecture.result_registry import ROOT


class ComponentPPATests(unittest.TestCase):
    def model_costs(self, buffered=False, size=9, cycles=None):
        model = CompleteSimulation(size,4)
        if buffered: configure_readout(model,BUFFERED)
        list(model.steps())
        costs = complete_costs('cacti_22nm_lstp',model.memory.operations,model.cycles if cycles is None else cycles,
            model.neural.profile,model.memory.config,model.phase_cycles,model.block_active_cycles)
        return model,costs

    def test_all_default_core_owners_have_costs_and_export_once(self):
        model,costs = self.model_costs(); ledger = costs['ledger']
        rows = inventory_rows(ledger['components'])
        self.assertEqual(len({r['id'] for r in rows}),len(rows))
        self.assertEqual(ledger['missing_area'],[]); self.assertEqual(ledger['missing_energy'],[])
        self.assertIsNone(ledger['whole_chip_area_mm2'])
        self.assertEqual(len(ledger['excluded_components']),2)
        owners = [r for r in rows if r['counted']]
        self.assertAlmostEqual(sum(r['area_um2'] for r in owners)/1e6,ledger['known_area_mm2'])
        self.assertAlmostEqual(sum(r['average_power_mw'] for r in owners),ledger['known_average_power_mw'])
        self.assertTrue(all(0<=r['active_cycles']<=model.cycles for r in owners))
        self.assertGreater(sum(r['active_cycles'] for r in owners),model.cycles)
        self.assertGreater(len(rows),180)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'components.csv'; write_component_csv(path,ledger)
            with path.open() as stream: exported = list(csv.DictReader(stream))
            self.assertEqual(len(exported),len(rows))
            total = sum(float(r['area_um2']) for r in exported if r['counted']=='True')/1e6
            self.assertAlmostEqual(total,ledger['known_area_mm2'])
            for row in exported:
                if row['included_in']: self.assertEqual(row['average_power_mw'],'')

    def test_every_rtl_instance_is_present_even_without_matching_costs(self):
        paths = {'u_sel':'rtl_synthesis/p02_search_control/p00_rtl/imc_cached_selector.sv',
            'u_ucb':'rtl_synthesis/p03_iteration_core/p00_rtl/imc_ucb_score.sv',
            'u_upd':'rtl_synthesis/p03_iteration_core/p00_rtl/imc_tree_update.sv',
            'u_nn':'rtl_synthesis/p01_mapped_core/p00_rtl/imc_neural_sequencer.sv',
            'u_node_router':'rtl_synthesis/p01_mapped_core/p00_rtl/imc_sram_router.sv',
            'u_child_router':'rtl_synthesis/p01_mapped_core/p00_rtl/imc_sram_router.sv'}
        for buffered,size in ((False,9),(True,9),(False,3)):
            model,costs = self.model_costs(buffered=buffered,size=size)
            rows = {r['id']:r for r in costs['ledger']['components']}
            top = 'rtl_synthesis/p04_column_hold/p00_rtl/imc_buffered_iteration_core.sv' if buffered else 'rtl_synthesis/p03_iteration_core/p00_rtl/imc_iteration_core.sv'
            instances = set(re.findall(r'\b(u_\w+)\s*\(', (ROOT/top).read_text()))
            self.assertEqual(instances,set(paths))
            for parent,path in paths.items():
                if buffered and parent=='u_nn': path='rtl_synthesis/p04_column_hold/p00_rtl/imc_buffered_neural_sequencer.sv'
                expected = set(re.findall(r'\b(u_\w+)\s*\(', (ROOT/path).read_text()))
                actual = {r['rtl_instance'] for r in rows[parent]['children'] if 'rtl_instance' in r}
                self.assertEqual(expected,actual,(parent,size,buffered))
                known = [r['area_um2'] for r in rows[parent]['children'] if r['area_um2'] is not None]
                self.assertLessEqual(sum(known),rows[parent]['area_um2'] or 0)

    def test_native_tools_and_workbook_counts_are_not_rescaled_twice(self):
        policy,tools,_ = peripheral_sources(); model,costs = self.model_costs()
        rows = {r['id']:r for r in costs['ledger']['components']}
        self.assertEqual(rows['cam_macro']['area_um2'],tools['cam']['cam_1024_lstp']['area_um2'])
        self.assertEqual(rows['adc_lanes']['area_um2'],3*tools['adc']['area_um2'])
        self.assertEqual(rows['row_drivers']['count'],1024)
        self.assertEqual(rows['analog_mux']['count'],512)
        self.assertEqual(rows['sample_hold']['count'],3)
        cells = workbook_source()['cells']['New_Architecture']
        self.assertEqual(rows['cim_arrays']['area_um2'],4*256*128*cells['C14']['value'])
        for source in tools['cam'].values():
            self.assertEqual(source['physical_tag_bits'],36)
            self.assertLess(source['access_ns'],6)
        self.assertLess(tools['adc']['latency_ns'],18)

    def test_more_idle_time_adds_standby_but_not_more_work(self):
        model,first = self.model_costs()
        second = complete_costs('cacti_22nm_lstp',model.memory.operations,model.cycles*2,
            model.neural.profile,model.memory.config,model.phase_cycles,model.block_active_cycles)
        rows = {r['id']:r for r in second['ledger']['components']}
        for row in first['ledger']['components']:
            if row.get('cost_model'):
                later=rows[row['id']]
                self.assertEqual(row['dynamic_energy_uj'],later['dynamic_energy_uj'])
                self.assertAlmostEqual(2*row['standby_energy_uj'],later['standby_energy_uj'])
                self.assertEqual(row['active_cycles'],later['active_cycles'])

    def test_buffered_design_adds_storage_and_shortens_array_drive(self):
        model,driven = self.model_costs(); buffered_model,buffered = self.model_costs(buffered=True)
        a={r['id']:r for r in driven['ledger']['components']}; b={r['id']:r for r in buffered['ledger']['components']}
        self.assertNotIn('column_hold',a); self.assertEqual(b['column_hold']['count'],512)
        self.assertLess(b['cim_arrays']['active_cycles'],a['cim_arrays']['active_cycles'])
        self.assertLess(b['cim_arrays']['dynamic_energy_uj'],a['cim_arrays']['dynamic_energy_uj'])
        self.assertGreater(b['column_hold']['area_um2'],512*85/15)
        self.assertGreater(b['column_hold']['standby_energy_uj'],0)
        self.assertEqual(a['adc_lanes']['dynamic_energy_uj'],b['adc_lanes']['dynamic_energy_uj'])
        self.assertEqual(buffered['ledger']['missing_energy'],[])


if __name__ == '__main__': unittest.main()
