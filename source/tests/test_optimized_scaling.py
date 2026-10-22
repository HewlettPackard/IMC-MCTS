# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Shared parallel architecture across the approved hardware sizes.
# SPDX-License-Identifier: MIT
import unittest
from itertools import zip_longest
import numpy as np
from core.algorithm.model_catalog import load_model
from core.architecture.board_sizing import board_hardware
from core.architecture.neural_mapping import NeuralMapping
from core.architecture.parallel_datapath import (ParallelDatapathGoSimulation,
    SizedParallelDatapathGoSimulation, parallel_dot, column_pipeline, candidate_pipeline)
from core.architecture.run_identity import tree_sha256
from p03_experiments.p81_board_sizing.optimized import SizedOptimizedSearch


class OptimizedScalingTests(unittest.TestCase):
    def test_nine_trained_reference_preserved(self):
        for name in ('go_strong_v1','go_weak_v1'):
            weights,_=load_model(name,9)
            a=ParallelDatapathGoSimulation(9,110,weights=weights,turn_indicator=True,cam_entries=1024)
            b=SizedParallelDatapathGoSimulation(9,110,weights=weights)
            for x,y in zip_longest(a.steps(),b.steps()):
                self.assertEqual(x,y)
                self.assertEqual(a.neural.last_state,b.neural.last_state)
            self.assertEqual(a.memory.operations,b.memory.operations)
            self.assertEqual(tree_sha256(a.memory.nodes),tree_sha256(b.memory.nodes))
            self.assertEqual(a.block_active_cycles,b.block_active_cycles)
            self.assertEqual(a.neural.schedule,b.neural.schedule)

    def test_scaled_search_matches_prior_policy(self):
        for board,budget in ((2,35),(3,35),(5,40),(13,175),(19,365)):
            a=SizedOptimizedSearch(board,budget,seed=7)
            b=SizedParallelDatapathGoSimulation(board,budget,seed=7)
            for x,y in zip_longest(a.steps(),b.steps()):
                self.assertIsNotNone(x);self.assertIsNotNone(y)
                for key in ('phase','iteration','selected_node','nodes','edges','path_depth'):
                    self.assertEqual(x.get(key),y.get(key))
                self.assertEqual(a.neural.last_state,b.neural.last_state)
            self.assertEqual(a.status,'complete');self.assertEqual(b.status,'complete')
            self.assertEqual(a.memory.node_sram,b.memory.node_sram)
            self.assertEqual(a.memory.child_sram,b.memory.child_sram)
            self.assertLess(b.cycles,a.cycles)
            b.activity_record()

    def test_studio_sized_inventory_and_export(self):
        import tempfile
        from pathlib import Path
        from core.architecture import studio_current as c
        from core.architecture.result_registry import run_case, verify_run, ROOT
        for board in (2,13,19):
            with tempfile.TemporaryDirectory(dir=ROOT/'p03_experiments/p93_optimized_scaling') as folder:
                out,_=run_case(custom=c.current_architecture()['default_configuration'] | {
                    'board_size':board,'model_id':'random_diagnostic','iterations':3},runs=Path(folder))
                saved=verify_run(out)
                shape=board_hardware(board)
                architecture=saved['architecture']
                self.assertEqual(architecture['board_size'],board)
                self.assertEqual(architecture['arrays'][0]['rows'],2*board**2+1)
                self.assertEqual(architecture['installed_sram_bytes'],1024*(shape['node_sram_kib']+shape['child_sram_kib']))
                preview=c.preview('random_diagnostic',board)
                self.assertEqual(preview['architecture'],architecture)
                self.assertAlmostEqual(preview['known_area_mm2'],saved['costs']['ledger']['known_area_mm2'])

    def test_all_sizes_integer_oracle_and_capacity(self):
        rng=np.random.RandomState(93)
        for board in (2,3,5,9,13,19):
            m=SizedParallelDatapathGoSimulation(board,3)
            oracle=NeuralMapping(*m.weights,board,sram_word_cycles=2,turn_indicator=True)
            for player in (-1,1):
                position=rng.choice([-1,0,1],size=(board,board))
                self.assertEqual(m.neural.forward(position,player),oracle.forward(position,player))
                self.assertEqual(m.neural.last_state,oracle.last_state)
            shape=board_hardware(board);config=m.memory.config
            self.assertGreaterEqual(config['node_capacity'],shape['iterations']['high']+1)
            self.assertGreaterEqual(config['edge_capacity'],shape['iterations']['high'])
            self.assertGreaterEqual(config['path_storage_entries'],2*board**2+1)
            self.assertEqual(config['cam_entries'],shape['cam_entries'])
            self.assertEqual(m.neural.profile['arrays'][0]['rows'],2*board**2+1)
            self.assertEqual(m.neural.schedule['resources']['adc_register_bits'],1024)
        for rows in (9,19,51,163,339,723):
            q=rng.randint(-128,128,(rows,96))
            for x in (np.ones(rows,dtype=int),rng.randint(0,2,rows)):
                result,_=parallel_dot(x,q+128,1,column_pipeline(96))
                np.testing.assert_array_equal(result,x@q)
        for count in (170,171,361,362):
            schedule=candidate_pipeline([True]*count)
            self.assertEqual(sum(g['count'] for g in schedule['groups']),count)
            self.assertTrue(all(g['count']<=16 for g in schedule['groups']))

if __name__=='__main__':unittest.main()
