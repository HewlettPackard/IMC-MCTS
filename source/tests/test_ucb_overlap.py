# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Exact search preservation and cycle savings tied to the separate RTL candidate.
# SPDX-License-Identifier: MIT
import hashlib
from itertools import zip_longest
import json
import unittest

from core.algorithm.model_catalog import load_model
from core.architecture.go_simulation import LegacyGo, state_record
from core.architecture.offset_encoding import OffsetGoSimulation
from core.architecture.parallel_selection import LANES
from core.architecture.result_registry import ROOT
from core.architecture.ucb_overlap import OverlappedUCBGoSimulation, overlap_spec
from core.architecture.ucb_overlap_costs import overlap_costs


def models(iterations=120, model_id='go_strong_v1', **kwargs):
    weights,_ = load_model(model_id,9)
    options = {'weights':weights,'turn_indicator':True,'cam_entries':1024,'seed':0,'exploration':1.414,**kwargs}
    return OffsetGoSimulation(9,iterations,**options), OverlappedUCBGoSimulation(9,iterations,**options)


def compare(test,a,b):
    for x,y in zip_longest(a.steps(),b.steps()):
        test.assertIsNotNone(x); test.assertIsNotNone(y)
        for key in ('phase','iteration','selected_node','nodes','edges','path_depth'):
            test.assertEqual(x.get(key),y.get(key),key)
        if x['phase']=='neural': test.assertEqual(a.neural.last_state,b.neural.last_state)
        if x['phase']=='iteration_commit':
            test.assertEqual(a.random_state,b.random_state)
            test.assertEqual(a.value_q17,b.value_q17)
    test.assertEqual((a.status,a.completed,a.termination),(b.status,b.completed,b.termination))
    test.assertEqual(a.memory.node_sram,b.memory.node_sram)
    test.assertEqual(a.memory.child_sram,b.memory.child_sram)
    test.assertEqual(a.memory.operations,b.memory.operations)
    test.assertEqual(a.batch_counts,b.batch_counts)
    saved = 54*sum(a.batch_counts.values())
    test.assertEqual(a.cycles-b.cycles,saved)
    for phase in a.phase_cycles:
        test.assertEqual(a.phase_cycles[phase]-b.phase_cycles[phase],saved if phase=='selection' else 0)
    for i,lane in enumerate(LANES):
        scores = sum(count for n,count in b.batch_counts.items() if n>i)
        test.assertEqual(b.block_active_cycles[lane],169*scores)
        test.assertEqual(a.block_active_cycles[lane]-b.block_active_cycles[lane],54*scores)
    test.assertEqual(sum(b.block_active_cycles[lane] for lane in LANES),169*b.memory.operations['ucb_operations'])
    test.assertEqual(b.memory.cursor,b.cycles)
    b.activity_record()


class UCBOverlapTests(unittest.TestCase):
    def test_timing_profile_is_bound_to_checked_rtl(self):
        spec = overlap_spec()
        proof = ROOT/spec['timing_source']
        timing = json.loads(proof.read_text())
        self.assertEqual(timing['status'],'passed')
        self.assertEqual(timing['vectors'],358)
        for key in ('single_accept_to_valid_cycles','arithmetic_active_cycles',
                    'batch_accepted_to_valid_base_cycles','batch_reduction_cycles_per_child',
                    'caller_request_and_capture_cycles','saved_cycles_per_batch'):
            self.assertEqual(spec[key],timing[key],key)
        for name,expected in json.loads((proof.parent/'source_sha256.json').read_text()).items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),expected,name)

    def test_trained_searches_preserve_seeds_players_and_nonempty_positions(self):
        engine = LegacyGo(9)
        state = engine.initial_state()
        for move in ((2,2),(6,6),(2,3)): state = engine.apply_move(state,move)
        for model_id in ('go_strong_v1','go_weak_v1'):
            for options in ({'seed':0},{'seed':3,'initial_board':state['board'],'go_state':state_record(state)}):
                with self.subTest(model=model_id,seed=options['seed']):
                    a,b = models(model_id=model_id,**options)
                    compare(self,a,b)
                    self.assertGreater(sum(b.batch_counts.values()),0)
                    self.assertEqual(a.neural.profile,b.neural.profile)
                    self.assertEqual(a.neural.schedule,b.neural.schedule)
                    self.assertEqual(b.memory.config['ucb_lanes'],4)
                    for key in ('node_ports','child_ports','node_capacity','edge_capacity','neural_bytes'):
                        self.assertEqual(a.memory.config[key],b.memory.config[key],key)
                    self.assertEqual(b.memory.config['node_ports'],1)
                    self.assertEqual(b.memory.config['child_ports'],1)
                    self.assertEqual(len(b.memory.node_sram)+len(b.memory.child_sram),2*1024*1024)
                    self.assertNotEqual(a.memory.config['execution_profile'],b.memory.config['execution_profile'])
                    self.assertNotEqual(a.selection_spec['sha256'],b.selection_spec['sha256'])
                    self.assertNotIn('ucb_cycles',b.memory.config)
                    self.assertEqual(b.memory.config['reference_serial_ucb_cycles'],225)
                    self.assertEqual(b.memory.config['ucb_batch_service_cycles'],'171 + valid_children (1..4)')

    def test_partial_batches_ties_and_coefficient_boundaries(self):
        for exploration in (0.,1.414,8.):
            a,b = models(1,exploration=exploration)
            for count in range(1,5):
                candidates = [(8+i,{'visits':7,'value':3.5}) for i in range(count)]
                before = [m.memory.cursor for m in (a,b)]
                x,y = [m._batch(32,candidates) for m in (a,b)]
                self.assertEqual(x,y); self.assertEqual(y[0],8)
                self.assertEqual(a.memory.cursor-before[0],225+count)
                self.assertEqual(b.memory.cursor-before[1],171+count)
            for invalid in ([],[(0,{'visits':0,'value':0})],[(i,{'visits':1,'value':0}) for i in range(5)]):
                for model in (a,b):
                    with self.assertRaises(ValueError): model._batch(8,invalid)

    def test_capacity_failures_preserve_state_and_partial_work(self):
        for limits in ({'nodes':3},{'edges':2},{'path_entries':1}):
            with self.subTest(limits=limits):
                a,b = models(50,memory_limits=limits)
                compare(self,a,b)
                self.assertEqual(b.status,'memory_limited')

    def test_changed_ucb_costs_exclude_old_power_and_all_child_prices(self):
        _,b = models(120)
        list(b.steps())
        costs = overlap_costs(b)
        rows = {r['id']:r for r in costs['components']}
        for lane in LANES:
            row = rows[lane]
            for key in ('area_um2','energy_uj','average_power_mw','dynamic_energy_uj','leakage_energy_uj'):
                self.assertIsNone(row[key],key)
            self.assertNotIn('block_power',row)
            self.assertEqual(row['active_cycles'],b.block_active_cycles[lane])
            self.assertEqual(len(row['children']),5)
            for child in row['children']:
                self.assertFalse(child['counted'])
                self.assertIn('unestimated parent',child['status'])
        self.assertEqual(len(costs['missing_area']),11)
        self.assertEqual(len(costs['missing_energy']),11)
        for key in ('core_area_mm2','core_energy_uj','core_average_power_mw',
                    'whole_chip_area_mm2','whole_chip_energy_uj','whole_chip_power_mw'):
            self.assertIsNone(costs[key],key)
        self.assertAlmostEqual(costs['known_area_mm2'],sum(r['area_um2'] or 0 for r in rows.values())/1e6)
        self.assertAlmostEqual(costs['known_energy_uj'],sum(r['energy_uj'] or 0 for r in rows.values()))
        self.assertAlmostEqual(costs['known_average_power_mw']*b.cycles/500000,costs['known_energy_uj'])
        self.assertEqual(costs['profile'],b.memory.config['execution_profile'])
        self.assertEqual(costs['source_identities']['overlapped_ucb'],b.selection_spec['sha256'])
        self.assertEqual(b.activity_record()['arithmetic_work_per_score'],{'divider_bit_steps':160,'sqrt_bit_pairs':52})
        with self.assertRaises(ValueError): overlap_costs(models(1)[0])


if __name__ == '__main__': unittest.main()
