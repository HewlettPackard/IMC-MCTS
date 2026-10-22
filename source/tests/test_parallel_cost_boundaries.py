# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import unittest
from core.architecture import studio_current as c
from core.architecture.component_parameters import validate_parameters
from core.architecture.parallel_datapath import SizedParallelDatapathGoSimulation

class CurrentCostBoundaryTests(unittest.TestCase):
    def report(self,board=2,parameters=None):
        m=SizedParallelDatapathGoSimulation(board,2,seed=0,component_parameters=parameters)
        p=c.prepare(m)
        for _ in m.steps():pass
        r=c.price(m.memory.operations,m.cycles,m.block_active_cycles,c.capture(m),p)
        return m,p,r

    def test_current_and_reference_resources_are_separate_for_all_boards(self):
        for board in (2,3,5,9,13,19):
            with self.subTest(board=board):
                m,p,r=self.report(board)
                nn=next(x for x in r['components'] if x['id']=='u_nn')['details']
                self.assertEqual(nn['resources'],p['neural']['resources'])
                self.assertEqual(nn['resources']['adc_lanes'],32)
                self.assertEqual(nn['resources']['readout_bus_bits'],128)
                self.assertEqual(nn['resources']['accumulator_banks'],8)
                self.assertEqual(nn['reference_resources']['adc_lanes'],8)
                preview=next(x for x in c.components(r,p) if x['id']=='u_nn')
                self.assertEqual(preview['details']['resources'],p['neural']['resources'])

    def test_connected_regions_and_residual_allocations_sum_without_duplicate_children(self):
        m,p,r=self.report()
        for row in r['components']:
            if row['id'] not in ('u_sel','u_nn'):continue
            detail=row['details']
            self.assertEqual(detail['cost_basis_status'],'synthesis_with_residual_control_allocation')
            parts=detail['allocation_breakdown']
            for key in ('area_um2','dynamic_energy_uj','standby_energy_uj'):
                self.assertAlmostEqual(sum(x[key] for x in parts),row[key])
            energy=detail['energy_breakdown_uj']
            self.assertAlmostEqual(energy['activity_dependent']+energy['elapsed_vectorless'],row['dynamic_energy_uj'])
            self.assertAlmostEqual(energy['leakage'],row['standby_energy_uj'])
            self.assertEqual(parts[0]['status'],'native65_synthesis_target22_estimate')
            self.assertEqual(parts[1]['status'],'engineering_allocation_not_matching_synthesis')
        nn=next(x for x in r['components'] if x['id']=='u_nn')
        self.assertNotIn('extra_accumulator_bank_logic_proxies',nn['details'])
        self.assertIn('offset sum/shift/subtraction',nn['details']['residual_control_allocation']['basis'])
        af=p['sources']['scaling']['area']['factor']
        selection=[x for x in r['components'] if x['id']=='u_sel' or x['id'].startswith('u_ucb_')]
        self.assertAlmostEqual(sum(x['details']['native65_part']['area_um2'] for x in selection),1538770.569904)
        self.assertAlmostEqual(nn['details']['native65_part']['area_um2']*af,104753.280035*af)
        self.assertAlmostEqual(nn['details']['residual_control_allocation']['area_um2'],5281.774746202959,places=6)

    def test_bus_capacitance_counts_full_beats_and_replaces_allowance(self):
        values={'dynamic_fraction':0,'readout_capacitance_ff_per_bit':100,
            'readout_voltage_v':0.8,'readout_rise_probability':0.25}
        m,p,r=self.report(parameters={'physical_overhead':values})
        row=next(x for x in r['components'] if x['id']=='physical_overhead')
        n=m.memory.operations['neural_readout_words']
        expected=n*128*100*0.8**2*0.25/1e9
        self.assertAlmostEqual(row['dynamic_energy_uj'],expected)
        self.assertEqual(row['details']['readout_transfers'],n)
        self.assertEqual(row['details']['readout_bus_bits'],128)
        self.assertEqual(row['details']['method'],'user_capacitive_readout_wire_only')
        self.assertEqual(row['details']['global_dynamic_allowance_uj'],0)
        with self.assertRaises(ValueError):
            validate_parameters({'physical_overhead':{'readout_capacitance_ff_per_bit':100}})
        with self.assertRaises(ValueError):
            validate_parameters({'physical_overhead':values|{'dynamic_fraction':0.1}})

if __name__=='__main__':unittest.main()
