# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Schedule ownership, exact arithmetic and search-preservation checks.
# SPDX-License-Identifier: MIT
from collections import Counter
from itertools import zip_longest
import unittest

import numpy as np

from core.algorithm.model_catalog import load_model
from core.architecture.go_simulation import LegacyGo, state_record
from core.architecture.offset_encoding import offset_dot
from core.architecture.parallel_datapath import (LANES,ParallelDatapathGoSimulation,
    candidate_pipeline,column_pipeline,parallel_dot,check_intervals)
from core.architecture.ucb_overlap import OverlappedUCBGoSimulation


def run_pair(test,budget=110,model='go_strong_v1',**kwargs):
    weights,_ = load_model(model,9)
    options = {'weights':weights,'turn_indicator':True,'cam_entries':1024,'seed':0,**kwargs}
    a = OverlappedUCBGoSimulation(9,budget,**options)
    b = ParallelDatapathGoSimulation(9,budget,**options)
    for old,new in zip_longest(a.steps(),b.steps()):
        test.assertIsNotNone(old); test.assertIsNotNone(new)
        for key in ('phase','iteration','selected_node','nodes','edges','path_depth'):
            test.assertEqual(old.get(key),new.get(key),key)
        if old['phase']=='neural':
            test.assertEqual(a.neural.last_state,b.neural.last_state)
            test.assertEqual(a.neural.last_offset,b.neural.last_offset)
        if old['phase']=='iteration_commit':
            test.assertEqual(a.value_q17,b.value_q17); test.assertEqual(a.random_state,b.random_state)
    test.assertEqual((a.status,a.completed,a.termination),(b.status,b.completed,b.termination))
    test.assertEqual(a.memory.node_sram,b.memory.node_sram)
    test.assertEqual(a.memory.child_sram,b.memory.child_sram)
    for key in ('node_sram_read_words','node_sram_write_words','child_sram_read_words',
        'child_sram_write_words','ucb_operations','neural_adc_conversions','neural_shift_adds'):
        test.assertEqual(a.memory.operations[key],b.memory.operations[key],key)
    test.assertEqual(sum(b.phase_cycles.values()),b.cycles)
    test.assertEqual(b.memory.cursor,b.cycles)
    test.assertEqual(sum(b.block_active_cycles[k] for k in LANES),169*b.memory.operations['ucb_operations'])
    test.assertEqual(len(b.memory.node_sram)+len(b.memory.child_sram),2097152)
    b.activity_record()
    return a,b


class ParallelDatapathTests(unittest.TestCase):
    def test_pipeline_known_intervals_and_backpressure(self):
        # Three groups: conversions ready at 16,32,48; last drains 4+4 cycles.
        p = column_pipeline(96)
        self.assertEqual(p['cycles'],56)
        self.assertEqual([g['ready'] for g in p['groups']],[16,32,48])
        self.assertEqual(column_pipeline(3)['cycles'],18)
        self.assertEqual(column_pipeline(96,banks=1)['cycles'],72)
        for outputs in (1,3,31,32,33,95,96,97):
            for adc in (1,13,29):
                for bus,alu in ((32,1),(128,8)):
                    a = column_pipeline(outputs,bus_bits=bus,accumulators=alu,adc_cycles=adc,banks=1)
                    b = column_pipeline(outputs,bus_bits=bus,accumulators=alu,adc_cycles=adc,banks=2)
                    self.assertLessEqual(b['cycles'],a['cycles'])
                    self.assertEqual(sum(g['count'] for g in b['groups']),outputs)
                    # Independent cycle occupancy check, including consumer-limited cases.
                    occupied = Counter()
                    for event in b['trace']:
                        for tick in range(event['start'],event['end']):
                            occupied[event['resource'],tick] += 1
                    self.assertTrue(all(v==1 for v in occupied.values()))
                    for bank in (0,1):
                        live = Counter(t for g in b['groups'] if g['bank']==bank
                            for t in range(g['start'],g['end']))
                        self.assertTrue(all(v==1 for v in live.values()))

    def test_candidate_loader_preserves_one_port_and_bounded_banks(self):
        # Each full load is 16*(6*(1+2)+4)=352 cycles; scorer takes 187.
        p = candidate_pipeline([True]*32)
        self.assertEqual(p['cycles'],891)
        self.assertEqual([g['ready'] for g in p['groups']],[352,704])
        self.assertEqual(candidate_pipeline([True]*32,banks=1)['cycles'],1078)
        for n in (1,2,15,16,17,31,32,33,81,82):
            for last in (False,True):
                for busy in (1,169,1000):
                    visits = [True]*(n-1)+[last]
                    p = candidate_pipeline(visits,busy_cycles=busy)
                    self.assertEqual(sum(g['valid_lanes'] for g in p['groups']),sum(visits))
                    self.assertEqual(sum(e['end']-e['start'] for e in p['trace']
                        if e['resource']=='node_sram'),12*n)
                    self.assertEqual(sum(e['operation']=='candidate_read' for e in p['trace']),6*n)
                    self.assertTrue(all(g['count']<=16 for g in p['groups']))
        with self.assertRaises(ValueError): candidate_pipeline([True,False,True])

    def test_conflicts_and_invalid_resources_are_rejected(self):
        with self.assertRaises(AssertionError):
            check_intervals([{'resource':'adc','start':0,'end':3},
                {'resource':'adc','start':2,'end':4}],[])
        with self.assertRaises(AssertionError):
            check_intervals([], [{'bank':0,'start':0,'ready':1,'consume':1,'end':4},
                {'bank':0,'start':3,'ready':4,'consume':4,'end':5}])
        for kwargs in ({'outputs':0},{'outputs':3,'bus_bits':24},{'outputs':3,'banks':0}):
            with self.assertRaises(ValueError): column_pipeline(**kwargs)

    def test_banked_dot_matches_dense_signed_math_at_extremes_and_tails(self):
        rng = np.random.RandomState(84)
        for n,m,bits in ((163,96,1),(96,3,8),(17,33,8),(5,1,1)):
            q = rng.randint(-128,128,(n,m)); q[:,0] = -128
            kernel = column_pipeline(m)
            for x in (np.zeros(n,dtype=int),np.full(n,2**bits-1,dtype=int),rng.randint(0,2**bits,n)):
                y,detail = parallel_dot(x,q+128,bits,kernel)
                np.testing.assert_array_equal(y,x@q)
                z,other = offset_dot(x,q+128,bits)
                np.testing.assert_array_equal(y,z); self.assertEqual(detail,other)

    def test_trained_searches_and_nonempty_white_turn(self):
        game = LegacyGo(9); state = game.initial_state()
        for move in ((2,2),(6,6),(2,3)): state = game.apply_move(state,move)
        for model in ('go_strong_v1','go_weak_v1'):
            for options in ({},{'seed':3,'initial_board':state['board'],'go_state':state_record(state)}):
                with self.subTest(model=model,options=bool(options)):
                    a,b = run_pair(self,model=model,**options)
                    self.assertLess(b.cycles,a.cycles)
                    self.assertEqual(b.neural.schedule['cycles'],2666)
                    self.assertEqual(b.neural.schedule['operations']['adc_conversions'],1200)
                    self.assertEqual(b.neural.schedule['resources']['adc_register_bits'],1024)
                    self.assertEqual(b.neural.schedule['resources']['accumulator_register_bits'],3072)
                    self.assertEqual(b.memory.config['node_ports'],1)
                    self.assertGreater(sum(b.batch_counts.values()),0)

    def test_capacity_stop_and_extreme_exploration(self):
        for limits in ({'nodes':3},{'edges':2},{'path_entries':1}):
            a,b = run_pair(self,budget=50,memory_limits=limits)
            self.assertEqual(b.status,'memory_limited')
        for exploration in (0.,8.): run_pair(self,exploration=exploration)


if __name__=='__main__': unittest.main()
