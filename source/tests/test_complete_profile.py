# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Complete searches and saved evidence must preserve budgets and identities.
# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

import numpy as np

from core.architecture.iteration_model import CompleteSimulation
from core.architecture.result_registry import ROOT, RunCancelled, resolve_case, run_case, verify_run
from core.architecture.run_identity import tree_sha256
from core.architecture.ucb_arithmetic import score


class CompleteProfileTests(unittest.TestCase):
    def test_fixed_values_and_exact_iteration_budget(self):
        model=CompleteSimulation(2,12,weights=(np.zeros((8,32)),np.zeros((32,3))))
        events=list(model.steps())
        self.assertEqual(model.status,'complete')
        self.assertEqual(model.memory.nodes[0]['visits'],12)
        self.assertEqual(len([r for r in events if r['phase']=='iteration_commit']),12)
        for node in model.memory.nodes.values():
            expected=65535 if node['player']==1 else 65537
            self.assertEqual(node['value'],node['visits']*expected/131072)
        self.assertEqual(model.memory.path_depth,0)
        self.assertEqual(sum(model.phase_cycles.values()),model.cycles)

    def test_capacity_failure_preserves_completed_work(self):
        model=CompleteSimulation(2,3,memory_limits={'nodes':1})
        with self.assertRaises(MemoryError): list(model.steps())
        self.assertEqual(model.status,'failed')
        self.assertEqual(model.completed,1)
        self.assertEqual(model.memory.nodes_used,1)
        self.assertEqual(model.memory.edges_used,0)
        self.assertEqual(model.memory.nodes[0]['visits'],1)

    def test_observation_preserves_results(self):
        first=CompleteSimulation(2,8,seed=42); second=CompleteSimulation(2,8,seed=42)
        for row in first.steps():
            first.board(first.selected).tolist()
            dict(first.memory.operations)
        list(second.steps())
        self.assertEqual(first.cycles,second.cycles)
        self.assertEqual(tree_sha256(first.memory.nodes),tree_sha256(second.memory.nodes))
        self.assertEqual(first.random_state,second.random_state)

    def test_invalid_workload_and_one_shot(self):
        for config in ({'iterations':0},{'seed':-1},{'board_size':13},{'board_size':9.0},{'board_size':True},
                {'exploration':9},{'exploration':-0.0},{'cam_entries':128.0},
                {'board_size':2,'initial_board':[[0,0],[0,0.5]]}):
            with self.assertRaises(ValueError): CompleteSimulation(**config)
        model=CompleteSimulation(2,1); list(model.steps())
        with self.assertRaises(RuntimeError): list(model.steps())

    def test_zero_exploration_and_visited_domain(self):
        self.assertEqual(score(10,4,2.0,0.0),0.5)
        self.assertEqual(score(1,1,0.0,8.0),1.0)
        for args in ((1,0,0.0,1.0),(1,2,0.0,1.0),(2,1,0.1,1.0),(2,1,2.0,1.0),(2,1,-0.0,1.0)):
            with self.assertRaises(ValueError): score(*args)


class RegistryTests(unittest.TestCase):
    def test_repeated_records_and_tamper_detection(self):
        with tempfile.TemporaryDirectory(prefix='registry_check_',dir=ROOT) as directory:
            runs=Path(directory)/'runs'
            out,a=run_case(custom={'board_size':2,'iterations':3,'profile':'complete_serial_q32_v2'},runs=runs)
            other,b=run_case(custom={'board_size':2,'iterations':3,'profile':'complete_serial_q32_v2'},runs=runs)
            self.assertNotEqual(out,other)
            self.assertEqual(a,b)
            self.assertIsNone(a['metrics']['energy_uj'])
            self.assertEqual(a['metrics']['core_cycles'],6911)
            self.assertEqual(a['costs']['coverage'][0]['scaling_applications'],0)
            with tarfile.open(out/'source_snapshot.tar.gz','r:gz') as archive:
                self.assertIn('rtl_synthesis/p03_iteration_core/p00_rtl/imc_ucb_score.sv',archive.getnames())
            self.assertEqual(verify_run(out),a)
            with (out/'summary.csv').open('a') as stream: stream.write('changed\n')
            with self.assertRaises(ValueError): verify_run(out)

    def test_canonical_case_cannot_be_overridden(self):
        config,case=resolve_case('placement_9x9_medium_v1')
        self.assertEqual((config['board_size'],config['iterations']),(9,5000))
        self.assertEqual(case,'placement_9x9_medium_v1')
        self.assertEqual(config['profile'],'complete_serial_q32_v2')
        with self.assertRaises(ValueError): resolve_case(case,{'iterations':2})

    def test_cancelled_run_is_preserved_and_not_indexed(self):
        def cancel(row,model):
            if row.get('iteration')==2: raise RunCancelled('test cancellation')
        with tempfile.TemporaryDirectory(prefix='registry_cancel_',dir=ROOT) as directory:
            runs=Path(directory)/'runs'
            with self.assertRaises(RunCancelled): run_case(custom={'board_size':2,'iterations':3},runs=runs,on_event=cancel)
            out=next(runs.iterdir())
            metadata=json.loads((out/'metadata.json').read_text())
            self.assertEqual(metadata['status'],'cancelled')
            self.assertEqual(metadata['completed_iterations'],1)
            self.assertFalse((runs.parent/'index.json').exists())


if __name__=='__main__': unittest.main()
