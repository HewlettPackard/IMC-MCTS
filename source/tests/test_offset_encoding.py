# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Signed-output equivalence, finite ADC range, service accounting and PPA gaps.
# SPDX-License-Identifier: MIT
from collections import Counter
from itertools import zip_longest
import unittest

import numpy as np

from core.algorithm.model_catalog import load_model
from core.architecture.eight_adc import EightADCGoSimulation
from core.architecture.offset_encoding import OffsetNeuralMapping, OffsetGoSimulation, offset_dot
from core.architecture.offset_costs import offset_costs
from p03_experiments.p75_offset_encoding.scalar_reference import replay_layer


def models(iterations=1, model_id='go_strong_v1', **kwargs):
    weights,_ = load_model(model_id,9)
    options = {'weights':weights,'turn_indicator':True,'cam_entries':1024,'seed':0,'exploration':1.414,**kwargs}
    return EightADCGoSimulation(9,iterations,**options), OffsetGoSimulation(9,iterations,**options)


class OffsetEncodingTests(unittest.TestCase):
    def test_extremes_zero_and_partial_row_groups_match_signed_dot(self):
        np.random.seed(23)
        for size in (1,15,16,17,96,163):
            for bits in (1,8):
                q = np.random.randint(-127,128,(size,9))
                q[:,0] = -127; q[:,1] = 0; q[:,2] = 127
                for inputs in (np.zeros(size,dtype=np.int64),np.full(size,2**bits-1),np.random.randint(0,2**bits,size)):
                    got,info = offset_dot(inputs,q+128,bits)
                    np.testing.assert_array_equal(got,inputs@q)
                    scalar,_,_ = replay_layer(inputs,q,bits)
                    self.assertEqual(got.tolist(),scalar)
                    self.assertEqual(info['correction'],128*int(inputs.sum()))
        _,info = offset_dot(np.ones(16,dtype=int),np.full((16,1),255),1)
        self.assertEqual(info['peak_adc_code'],4080)

    def test_rejects_unrepresentable_adc_and_invalid_codes(self):
        for adc in (8,11):
            with self.assertRaises(ValueError): offset_dot(np.ones(16,dtype=int),np.ones((16,1),dtype=int),1,adc_bits=adc)
        for inputs,cells in [(np.array([-1]),np.array([[128]])),(np.array([2]),np.array([[128]])),
                             (np.array([1]),np.array([[256]])),(np.array([1.]),np.array([[128]]))]:
            with self.assertRaises(ValueError): offset_dot(inputs,cells,1)

    def test_trained_models_both_players_preserve_every_neural_intermediate(self):
        np.random.seed(57)
        for model_id in ('go_strong_v1','go_weak_v1'):
            a,b = models(model_id=model_id)
            self.assertEqual(a.neural.coefficients,b.neural.coefficients)
            for i in range(12):
                board = np.random.choice([-1,0,1],(9,9)) if i else np.zeros((9,9),dtype=int)
                for player in (-1,1):
                    self.assertEqual(a.neural.forward(board,player),b.neural.forward(board,player))
                    self.assertEqual(a.neural.last_state,b.neural.last_state)
                    self.assertEqual(a.neural.storage,b.neural.storage)
            first,c1,_ = replay_layer(b.neural.features(board,player),b.neural.weight_codes[0],1)
            second,c2,_ = replay_layer(b.neural.last_state['hidden_codes'],b.neural.weight_codes[1],8)
            self.assertEqual(first,b.neural.last_state['hidden_acc'])
            self.assertEqual(second,b.neural.last_state['logits_acc'])
            for key,value in (Counter(c1)+Counter(c2)).items():
                self.assertEqual(value,b.neural.schedule['operations'][key],key)

    def test_custom_arrays_and_real_register_capacity(self):
        _,b = models()
        r = b.neural.schedule['resources']
        self.assertEqual([(a['rows'],a['columns']) for a in r['array_dimensions']],[(163,96),(96,3)])
        self.assertEqual((r['array_count'],r['mapped_cells'],r['allocated_cells']),(2,15936,15936))
        self.assertEqual((r['installed_row_drivers'],r['installed_column_routes']),(259,99))
        self.assertEqual((r['adc_register_bits'],r['adc_payload_bits'],r['accumulator_register_bits']),(128,96,3072))
        self.assertEqual(len(b.memory.node_sram)+len(b.memory.child_sram),2*1024*1024)
        self.assertEqual(b.neural.profile['weight_slices'],1)
        self.assertEqual(b.neural.profile['sign_branches'],1)

    def test_trace_covers_every_service_without_overlap_or_free_correction(self):
        _,b = models()
        schedule = b.neural.schedule
        expected = {'adc_groups':180,'adc_conversions':1200,'readout_words':624,
            'shift_adds':1200,'array_pulses':59,'offset_input_adds':259,'offset_subtracts':99,
            'offset_shifts':2,'offset_sum_clears':2,'node_sram_read_words':44,'node_sram_write_words':31}
        for key,value in expected.items(): self.assertEqual(schedule['operations'][key],value,key)
        cursor = 0
        for row in schedule['trace']:
            self.assertEqual(row['start'],cursor)
            self.assertGreater(row['end'],row['start'])
            cursor = row['end']
            if row['operation']=='adc_groups':
                self.assertEqual(row['end']-row['start'],13)
                self.assertIn(row['conversions'],(3,8))
            if row['operation'] in ('offset_input_adds','offset_subtracts','shift_adds','readout_words'):
                self.assertEqual(row['end']-row['start'],row['count'])
        self.assertEqual(cursor,sum(schedule['phase_cycles'].values()))
        self.assertEqual(cursor,schedule['cycles'])
        list(b.steps())
        self.assertEqual(b.phase_cycles['neural'],cursor)
        activity = b.neural.profile['readout_activity']
        # 11 L1 bursts of 12 groups; 48 L2 bursts with one three-lane group.
        self.assertEqual(activity['array_active_cycles'],11*(4+12*(1+1+1+13+4+8))+48*(4+1+1+1+13+2+3))

    def test_adc_service_sensitivity_changes_time_only(self):
        weights,_ = load_model('go_strong_v1',9)
        ref = OffsetNeuralMapping(*weights)
        for cycles in (17,25):
            other = OffsetNeuralMapping(*weights,adc_service_cycles=cycles)
            self.assertEqual(other.schedule['cycles']-ref.schedule['cycles'],180*(cycles-13))
            self.assertNotEqual(other.schedule['schedule_sha256'],ref.schedule['schedule_sha256'])
            for model in (ref,other): model.forward(np.zeros((9,9),dtype=int),1)
            self.assertEqual(ref.last_state,other.last_state)

    def test_search_preserves_every_iteration_tree_and_sram(self):
        for model_id in ('go_strong_v1','go_weak_v1'):
            a,b = models(100,model_id)
            for x,y in zip_longest(a.steps(),b.steps()):
                self.assertIsNotNone(x); self.assertIsNotNone(y)
                for key in ('phase','iteration','selected_node','nodes','edges','path_depth'):
                    self.assertEqual(x.get(key),y.get(key),key)
                if x['phase']=='neural': self.assertEqual(a.neural.last_state,b.neural.last_state)
                if x['phase']=='iteration_commit':
                    self.assertEqual(a.random_state,b.random_state)
                    self.assertEqual(a.value_q17,b.value_q17)
            self.assertEqual(a.memory.node_sram,b.memory.node_sram)
            self.assertEqual(a.memory.child_sram,b.memory.child_sram)
            self.assertEqual(a.batch_counts,b.batch_counts)
            for phase in a.phase_cycles:
                if phase!='neural': self.assertEqual(a.phase_cycles[phase],b.phase_cycles[phase])

    def test_capacity_failure_remains_explicit(self):
        a,b = models(50,memory_limits={'nodes':3})
        for model in (a,b): list(model.steps())
        self.assertEqual((a.status,a.completed),(b.status,b.completed))
        self.assertEqual(b.status,'memory_limited')
        self.assertEqual(a.memory.node_sram,b.memory.node_sram)

    def test_new_analog_and_correction_costs_cannot_inherit_old_prices(self):
        _,b = models(4)
        list(b.steps())
        costs = offset_costs(b)
        rows = {r['id']:r for r in costs['components']}
        for key in ('cim_arrays','row_drivers','sample_hold','adc_lanes','analog_mux','u_nn','physical_overhead'):
            self.assertIsNone(rows[key]['area_um2'],key)
            self.assertIsNone(rows[key]['energy_uj'],key)
        self.assertIsNone(costs['core_area_mm2']); self.assertIsNone(costs['core_energy_uj'])
        self.assertEqual(rows['adc_lanes']['count'],8)
        self.assertEqual(rows['row_drivers']['count'],259)
        self.assertEqual(len(costs['missing_area']),7)
        self.assertAlmostEqual(costs['known_area_mm2'],sum(r['area_um2'] or 0 for r in rows.values())/1e6)
        self.assertAlmostEqual(costs['known_energy_uj'],sum(r['energy_uj'] or 0 for r in rows.values()))
        self.assertGreater(rows['node_sram']['area_um2'],0)


if __name__ == '__main__': unittest.main()
