# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
# Consistent units at nested reporting boundaries.
import unittest
from core.architecture.parallel_datapath import SizedParallelDatapathGoSimulation
from core.architecture import studio_current as costs

class ParallelCostUnitsTests(unittest.TestCase):
    def test_sram_detail_energy_matches_current_search_interval(self):
        model = SizedParallelDatapathGoSimulation(2, 12, seed=0)
        prepared = costs.prepare(model)
        for _ in model.steps():
            pass
        report = costs.price(model.memory.operations, model.cycles,
            model.block_active_cycles, costs.capture(model), prepared)
        for row in report['components']:
            self.assertAlmostEqual(row['energy_uj'], row['average_power_mw'] * report['latency_ms'])
            if row['id'] in ('node_sram', 'child_sram'):
                detail = row['details']
                self.assertAlmostEqual(detail['dynamic_energy_nj'], row['dynamic_energy_uj'] * 1000)
                self.assertAlmostEqual(detail['leakage_energy_nj'], row['standby_energy_uj'] * 1000)
                self.assertAlmostEqual(detail['area_mm2'], row['area_um2'] / 1e6)

    def test_adc_default_and_explicit_standby_scenario(self):
        model=SizedParallelDatapathGoSimulation(2,12,seed=0)
        prepared=costs.prepare(model)
        for _ in model.steps():pass
        args=(model.memory.operations,model.cycles,model.block_active_cycles,costs.capture(model))
        nominal=costs.price(*args,prepared)
        adc=next(r for r in nominal['components'] if r['id']=='adc_lanes')
        self.assertAlmostEqual(adc['standby_energy_uj'],0.25*1.96*adc['details']['idle_lane_ms'])
        self.assertEqual(adc['details']['adc_idle_fraction'],0.25)
        self.assertAlmostEqual(adc['dynamic_energy_uj'],49*model.memory.operations['neural_adc_conversions']/1e6)
        self.assertIn('25% of published active power',adc['assumptions'])
        self.assertIn('core/architecture/peripheral_assumptions.json',prepared['source_sha256'])
        catalog=costs.parameter_catalog(prepared,nominal)
        group=next(g for g in catalog['groups'] if g['id']=='adc_lanes')
        self.assertAlmostEqual(next(f['default'] for f in group['fields'] if f['key']=='standby_mw'),32*0.25*1.96)
        omitted=costs.price(*args,prepared|{'component_parameters':{'adc_lanes':{'standby_mw':0}}})
        self.assertEqual(next(r for r in omitted['components'] if r['id']=='adc_lanes')['standby_energy_uj'],0)
        self.assertAlmostEqual(nominal['core_energy_uj']-omitted['core_energy_uj'],adc['standby_energy_uj'])
        scenario=costs.price(*args,prepared|{'component_parameters':{'adc_lanes':{'standby_mw':2}}})
        extra=2*adc['details']['idle_lane_ms']/32-adc['standby_energy_uj']
        self.assertAlmostEqual(scenario['core_energy_uj']-nominal['core_energy_uj'],extra)
        self.assertEqual(scenario['latency_ms'],nominal['latency_ms'])
        self.assertEqual(scenario['core_area_mm2'],nominal['core_area_mm2'])
        for before,after in zip(nominal['components'],scenario['components']):
            if before['id']!='adc_lanes':self.assertEqual(before,after)
