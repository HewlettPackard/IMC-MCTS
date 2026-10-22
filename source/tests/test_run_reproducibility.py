# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

import contextlib
import hashlib
import io
import json
import random
from pathlib import Path
import unittest
from dataclasses import asdict
from unittest.mock import patch

import numpy as np

from core.architecture.accelerator_api import Accelerator, estimate
from core.architecture.run_identity import tree_sha256
from p03_experiments.p104_simulator_campaign.legacy_reference import verify_reference


class RunReproducibilityTests(unittest.TestCase):
    def setUp(self):
        self.random_state = random.getstate()
        self.numpy_state = np.random.get_state()

    def tearDown(self):
        random.setstate(self.random_state)
        np.random.set_state(self.numpy_state)

    def test_default_calls_ignore_unrelated_random_draws(self):
        model = Accelerator(board_size=9, iterations=200)
        with contextlib.redirect_stdout(io.StringIO()):
            first = model._run_sst_simulation()
            random.seed(873)
            np.random.seed(901)
            random.random()
            np.random.randn(17)
            second = model._run_sst_simulation()
        self.assertEqual(first['evaluator'], second['evaluator'])
        self.assertEqual(first['tree_sha256'], second['tree_sha256'])
        self.assertEqual(first['simulation_cycles'], second['simulation_cycles'])

    def test_simulation_does_not_consume_caller_random_streams(self):
        random.seed(821)
        np.random.seed(213)
        expected_python = random.getstate()
        expected_numpy = np.random.get_state()
        with contextlib.redirect_stdout(io.StringIO()):
            Accelerator(board_size=3, iterations=75)._run_sst_simulation()
        self.assertEqual(random.getstate(), expected_python)
        actual_numpy = np.random.get_state()
        self.assertEqual(actual_numpy[0], expected_numpy[0])
        np.testing.assert_array_equal(actual_numpy[1], expected_numpy[1])
        self.assertEqual(actual_numpy[2:], expected_numpy[2:])

    def test_reordered_seeds_keep_their_own_tree_and_weights(self):
        results = []
        with contextlib.redirect_stdout(io.StringIO()):
            for seed in (17, 42, 17):
                results.append(Accelerator(board_size=3, iterations=200, seed=seed).analyze('simulate'))
        self.assertEqual(results[0].run_identity, results[2].run_identity)
        self.assertEqual(results[0].simulation['tree_sha256'], results[2].simulation['tree_sha256'])
        self.assertEqual(results[0].energy_uj, results[2].energy_uj)
        self.assertNotEqual(results[0].evaluator['weight_sha256'], results[1].evaluator['weight_sha256'])
        self.assertNotEqual(results[0].run_identity['configuration_sha256'], results[1].run_identity['configuration_sha256'])

    def test_equivalent_preset_and_custom_case_has_one_identity(self):
        fixture_path = (Path(__file__).resolve().parents[1] /
                        'p03_experiments/p104_simulator_campaign/legacy_placement_reference.json')
        checked = []

        def check_tree(tree):
            checked.append(verify_reference(tree, fixture_path))
            return tree_sha256(tree)

        with contextlib.redirect_stdout(io.StringIO()), patch(
            'core.architecture.accelerator_api.tree_sha256', side_effect=check_tree
        ):
            preset = Accelerator(board_size=9, play_strength='medium', seed=0).analyze('simulate')
            custom = estimate(board_size=9, iterations=5000, mode='simulate', seed=0)
        self.assertEqual(preset.iterations, 5000)
        self.assertEqual(preset.run_identity, custom.run_identity)
        # Same-runtime identities remain byte-exact. Cross-runtime legacy values
        # use a separate tight numerical contract, with exact discrete state.
        self.assertEqual(preset.simulation['tree_sha256'], custom.simulation['tree_sha256'])
        self.assertEqual(checked, [{'nodes': 6562, 'visited_nodes': 5000}] * 2)
        self.assertEqual(preset.simulation['completed_iterations'], 5000)
        self.assertEqual(custom.simulation['completed_iterations'], 5000)
        self.assertEqual(preset.simulation['cycles'], 10987522)
        self.assertEqual(custom.simulation['cycles'], preset.simulation['cycles'])
        # Tree/evaluator behavior stays fixed; timing now includes bounded
        # memory work and four inter-phase controller cycles per iteration.
        self.assertEqual(preset.simulation['cycles'],
                         sum(preset.simulation['memory']['phase_cycles'].values()) + 4 * 5000)

    def test_identity_records_effective_power_and_distinguishes_modes(self):
        model = Accelerator(board_size=9, iterations=2, seed=0)
        analytical = model.analyze('analytical')
        with contextlib.redirect_stdout(io.StringIO()):
            original = model.analyze('simulate')
            model.set_power_parameters(dac_power_mw=0.2)
            changed = model.analyze('simulate')
        self.assertNotEqual(analytical.run_identity['configuration_sha256'], original.run_identity['configuration_sha256'])
        self.assertNotEqual(changed.run_identity['configuration_sha256'], original.run_identity['configuration_sha256'])
        self.assertEqual(changed.simulation['tree_sha256'], original.simulation['tree_sha256'])
        self.assertNotEqual(changed.energy_uj, original.energy_uj)
        identity = changed.run_identity
        self.assertEqual(identity['configuration']['hardware']['dac_power_per_channel_mw'], 0.2)
        self.assertEqual(identity['configuration']['workload']['iterations'], 2)
        self.assertEqual(identity['configuration']['workload']['initial_board'], [[0] * 9 for _ in range(9)])
        self.assertEqual(identity['configuration']['workload']['rules'], 'empty_cell_placement_v1')
        self.assertEqual(identity['configuration']['evaluator']['mode'], 'random_diagnostic')
        canonical = json.dumps(identity['configuration'], sort_keys=True, separators=(',', ':'), allow_nan=False)
        self.assertEqual(identity['configuration_sha256'], hashlib.sha256(canonical.encode()).hexdigest())
        self.assertIn('core/simulator/mcts_sst_components.py', identity['source_sha256'])
        self.assertIn('numpy', identity['runtime'])
        json.dumps(asdict(changed), allow_nan=False)

    def test_invalid_seed_and_budget_fail_before_execution(self):
        for seed in (-1, 2**32, True, 1.5, '0', None):
            with self.subTest(seed=seed):
                with self.assertRaisesRegex(ValueError, 'seed'):
                    Accelerator(board_size=9, iterations=2, seed=seed)
        for budget in (0, -1, True, 1.5, '2'):
            for mode in ('analytical', 'simulate'):
                with self.subTest(budget=budget, mode=mode):
                    model = Accelerator(board_size=9, iterations=2)
                    model.iterations = budget
                    with self.assertRaisesRegex(ValueError, 'iterations'):
                        model.analyze(mode)


if __name__ == '__main__':
    unittest.main()
