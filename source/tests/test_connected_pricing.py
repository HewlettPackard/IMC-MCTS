# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import unittest
from core.architecture import studio_current as c
from core.architecture.parallel_datapath import SizedParallelDatapathGoSimulation


class ConnectedPricingTests(unittest.TestCase):
    def price(self,parameters=None):
        model=SizedParallelDatapathGoSimulation(2,12,seed=4,component_parameters=parameters)
        prepared=c.prepare(model)
        for _ in model.steps():pass
        report=c.price(model.memory.operations,model.cycles,model.block_active_cycles,c.capture(model),prepared)
        return model,prepared,report

    def test_native_dynamic_and_leakage_use_actual_elapsed_interval_once(self):
        m,p,r=self.price();t=m.cycles/500000;ef=p['sources']['scaling']['dynamic_energy']['factor']
        lanes=[x for x in r['components'] if x['id'].startswith('u_ucb_')]
        wrapper=next(x for x in r['components'] if x['id']=='u_sel')
        neural=next(x for x in r['components'] if x['id']=='u_nn')
        selection_dynamic=sum(x['dynamic_energy_uj'] for x in lanes)+wrapper['details']['allocation_breakdown'][0]['dynamic_energy_uj']
        selection_leak=sum(x['standby_energy_uj'] for x in lanes)+wrapper['details']['allocation_breakdown'][0]['standby_energy_uj']
        self.assertAlmostEqual(selection_dynamic,72.771*ef*t)
        self.assertAlmostEqual(selection_leak,8.5*t)
        self.assertAlmostEqual(neural['details']['allocation_breakdown'][0]['dynamic_energy_uj'],15.263*ef*t)
        self.assertAlmostEqual(neural['details']['allocation_breakdown'][0]['standby_energy_uj'],.246301*t)
        self.assertEqual(r['connected_synthesis']['original_packet_acceptance'],'UNVERIFIED')
        self.assertEqual(r['connected_synthesis']['power'],'VECTORLESS_ONLY')

    def test_ucb_group_override_removes_power_but_preserves_installed_area_and_search(self):
        a,p,base=self.price()
        b,q,custom=self.price({'u_ucb':{'active_dynamic_mw':0,'idle_dynamic_mw':0,'leakage_mw':0,'standby_mw':0}})
        self.assertEqual(a.memory.node_sram,b.memory.node_sram)
        self.assertEqual(a.memory.child_sram,b.memory.child_sram)
        self.assertEqual(a.cycles,b.cycles)
        lanes=[x for x in custom['components'] if x['id'].startswith('u_ucb_')]
        self.assertEqual(sum(x['energy_uj'] for x in lanes),0)
        self.assertEqual(base['core_area_mm2'],custom['core_area_mm2'])
        self.assertLess(custom['core_energy_uj'],base['core_energy_uj'])

    def test_partial_idle_override_uses_connected_group_defaults(self):
        _,_,base=self.price()
        for owner,idle in (('u_ucb',20),('u_nn',10)):
            with self.subTest(owner=owner):
                _,_,custom=self.price({owner:{'idle_dynamic_mw':idle}})
                self.assertLess(custom['core_energy_uj'],base['core_energy_uj'])
        with self.assertRaises(ValueError):self.price({'u_ucb':{'idle_dynamic_mw':1000}})


if __name__=='__main__':unittest.main()
