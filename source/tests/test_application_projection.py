# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import unittest
import numpy as np
from core.architecture.application_projection import APPLICATIONS, NeuralProjection, ApplicationCensus, project_costs
from core.architecture.parallel_datapath import check_intervals
from generalizability.games import GAME_REGISTRY
from copy import deepcopy


class ApplicationProjectionTests(unittest.TestCase):
    def test_offset_dot_with_enhanced_inputs_and_wide_hidden(self):
        rng=np.random.RandomState(7)
        for shape in APPLICATIONS:
            model=NeuralProjection(shape)
            for inputs,outputs,bits in [(shape['inputs'],shape['hidden'],shape['input_bits']), (shape['hidden'],3,8)]:
                x=rng.randint(0,2**bits,inputs).astype(np.int64)
                q=rng.randint(-127,128,(inputs,outputs)).astype(np.int64)
                result,details=model.checked_dot(x,q,bits)
                np.testing.assert_array_equal(result,x@q)
                self.assertLessEqual(details['peak_adc_code'],4080)

    def test_schedules_census_and_storage(self):
        for shape in APPLICATIONS:
            model=NeuralProjection(shape)
            check_intervals(model.schedule['trace'],[])
            expected=((shape['inputs']+15)//16)*shape['input_bits']*shape['hidden']
            expected+=((shape['hidden']+15)//16)*8*3
            self.assertEqual(model.schedule['operations']['adc_conversions'],expected)
            self.assertEqual(model.schedule['resources']['accumulator_register_bits'],shape['hidden']*32)
            self.assertEqual(model.profile['storage']['hidden']['bytes'],shape['hidden'])
            serial=NeuralProjection(shape,False)
            for op in ['adc_conversions','shift_adds','node_sram_read_words','node_sram_write_words']:
                self.assertEqual(model.schedule['operations'][op],serial.schedule['operations'][op])
            self.assertLess(model.schedule['cycles'],serial.schedule['cycles'])

    def test_small_task_workload_and_component_conservation(self):
        config=APPLICATIONS[0]
        game=deepcopy(GAME_REGISTRY[config['key']]);game.key=config['key']
        census=ApplicationCensus(game,100);census.search(game.initial_state(),1)
        report=project_costs(config,census)
        self.assertEqual(report['iterations'],100)
        self.assertEqual(report['workload']['nodes'],101)
        self.assertEqual(len(report['components']),31)
        self.assertAlmostEqual(sum(r['energy_uj'] for r in report['components']),report['core_energy_uj'])
        self.assertAlmostEqual(report['core_energy_uj']/report['latency_ms'],report['core_average_power_mw'])
        self.assertLessEqual(report['workload']['nodes'],report['memory_admission']['node_capacity'])

    def test_illegal_signed_weights_are_rejected(self):
        model=NeuralProjection(APPLICATIONS[0])
        with self.assertRaises(ValueError):model.checked_dot(np.ones(16,dtype=np.int64),np.full((16,3),128),1)


if __name__=='__main__':unittest.main()
