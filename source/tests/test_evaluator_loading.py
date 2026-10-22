# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import pickle
import random
import tempfile
import unittest

import numpy as np

from core.architecture.hardware_functional_model import CrossbarNNFunctional
from core.architecture.accelerator_api import Accelerator
from core.algorithm.evaluator import encode_board
from core.simulator.mcts_sst_components import RolloutUnitComponent
from core.simulator.runs.run_5x5_hardware_metrics import create_simulation
from py_sst_cpp.components.performance_config import PerformanceLevel
from py_sst_cpp.core.component import ComponentId
from py_sst_cpp.core.config import Params


class EvaluatorLoadingTests(unittest.TestCase):
    def setUp(self):
        self.numpy_state = np.random.get_state()
        self.random_state = random.getstate()
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(np.random.set_state, self.numpy_state)
        self.addCleanup(random.setstate, self.random_state)
        self.path = Path(self.directory.name) / 'model.pkl'
        self.path.write_bytes(pickle.dumps({
            'weights1': np.zeros((8, 32)),
            'weights2': np.zeros((32, 3)),
        }))
        self.rollout = RolloutUnitComponent(
            ComponentId(1, 'rollout'), Params({'board_size': 2})
        )
        self.spec = {
            'schema_version': 1,
            'checkpoint_sha256': hashlib.sha256(self.path.read_bytes()).hexdigest(),
            'board_size': 2, 'input_size': 8, 'hidden_size': 32, 'output_size': 3,
            'input_encoding': 'interleaved_black_white', 'turn_indicator': False,
            'weight_transform': 'identity', 'output_order': ['white', 'draw', 'black'],
            'value_perspective': 'black', 'arithmetic_dtype': 'float64',
        }

    def write_model(self, model):
        self.path.write_bytes(pickle.dumps(model))
        self.spec['checkpoint_sha256'] = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def assert_both_reject(self, spec, message):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, message):
                self.rollout.load_weights(self.path, evaluator_spec=spec)
            with self.assertRaisesRegex(ValueError, message):
                CrossbarNNFunctional(self.path, board_size=2, evaluator_spec=spec)

    def test_event_rejects_undeclared_checkpoint(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'evaluator_spec'):
                self.rollout.load_weights(self.path)

    def test_functional_rejects_undeclared_checkpoint(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'evaluator_spec'):
                CrossbarNNFunctional(self.path, board_size=2)

    def test_changed_file_is_rejected_before_pickle_decode(self):
        self.path.write_bytes(b'not a pickle')
        self.assert_both_reject(self.spec, 'checkpoint_sha256 mismatch')
        self.assertFalse(self.rollout._weights_trained)
        self.assertEqual(self.rollout.evaluator_info['mode'], 'random_diagnostic')

    def test_unsupported_specifications_are_rejected(self):
        cases = [
            ('schema_version', 2, 'schema_version'),
            ('board_size', 3, 'Board mismatch'),
            ('input_size', 9, 'input_size'),
            ('input_encoding', 'planar_player_relative', 'input_encoding'),
            ('turn_indicator', True, 'turn_indicator'),
            ('turn_indicator', 0, 'turn_indicator'),
            ('weight_transform', 'guess_from_range', 'weight_transform'),
            ('output_order', ['black', 'draw', 'white'], 'output_order'),
            ('value_perspective', 'current_player', 'value_perspective'),
            ('arithmetic_dtype', 'float32', 'arithmetic_dtype'),
            ('hidden_size', True, 'positive integer'),
            ('output_size', 3.0, 'positive integer'),
        ]
        for key, value, message in cases:
            with self.subTest(field=key, value=value):
                spec = copy.deepcopy(self.spec)
                spec[key] = value
                self.assert_both_reject(spec, message)
        for spec in ({**self.spec, 'hidden_szie': 32}, {k: v for k, v in self.spec.items() if k != 'weight_transform'}):
            self.assert_both_reject(spec, 'evaluator_spec fields')

    def test_wrong_matrices_and_metadata_are_rejected(self):
        cases = [
            ({'weights1': np.zeros((9, 32))}, 'weights1 shape mismatch'),
            ({'weights2': np.zeros((32, 2))}, 'weights2 shape mismatch'),
            ({'weights1': np.full((8, 32), np.nan)}, 'non-finite'),
            ({'weights2': np.full((32, 3), np.inf)}, 'non-finite'),
            ({'weights1': np.ones((8, 32), dtype=complex)}, 'real numeric'),
            ({'weights2': np.full((32, 3), '50')}, 'real numeric'),
            ({'input_size': 9}, 'metadata input_size'),
            ({'hidden_size': 96}, 'metadata hidden_size'),
            ({'weight_transform': 'centered_50'}, 'metadata weight_transform'),
        ]
        for changed, message in cases:
            with self.subTest(message=message):
                model = {'weights1': np.zeros((8, 32)), 'weights2': np.zeros((32, 3))}
                self.write_model({**model, **changed})
                self.assert_both_reject(self.spec, message)

    def test_event_rejects_different_hidden_size_while_functional_uses_explicit_size(self):
        self.write_model({'weights1': np.zeros((8, 4)), 'weights2': np.zeros((4, 3))})
        self.spec['hidden_size'] = 4
        with self.assertRaisesRegex(ValueError, 'hidden_size mismatch'):
            self.rollout.load_weights(self.path, evaluator_spec=self.spec)
        self.assertEqual(self.rollout.hidden_size, 32)
        self.assertEqual(self.rollout.weights1.shape, (8, 32))
        with contextlib.redirect_stdout(io.StringIO()):
            functional = CrossbarNNFunctional(self.path, board_size=2, evaluator_spec=self.spec)
        self.assertEqual(functional.hidden_size, 4)
        self.assertEqual(functional.forward(np.zeros((2, 2)))[0], 0.5)

    def test_failed_reload_preserves_the_previous_evaluator(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.rollout.load_weights(self.path, evaluator_spec=self.spec)
        old_weights = [self.rollout.weights1.copy(), self.rollout.weights2.copy()]
        old_info = copy.deepcopy(self.rollout.evaluator_info)
        self.write_model({'weights1': np.ones((8, 32)), 'weights2': np.ones((31, 3))})
        with self.assertRaisesRegex(ValueError, 'weights2 shape mismatch'):
            self.rollout.load_weights(self.path, evaluator_spec=self.spec)
        np.testing.assert_array_equal(self.rollout.weights1, old_weights[0])
        np.testing.assert_array_equal(self.rollout.weights2, old_weights[1])
        self.assertEqual(self.rollout.evaluator_info, old_info)
        self.assertTrue(self.rollout._weights_trained)

    def test_centered_and_identity_specs_match_a_known_answer(self):
        # This board activates inputs 0 and 5. The three active hidden units
        # have pre-ReLU values 1, 2, -1, giving output logits [0, 1, 2].
        board = np.array([[1, 0], [-1, 0]])
        weights1 = np.full((8, 32), 50.0)
        weights1[0, 0] = 100
        weights1[[0, 5], 1] = 100
        weights1[0, 2] = 0
        weights2 = np.full((32, 3), 50.0)
        weights2[0, 1] = 100
        weights2[1, 2] = 100
        expected_probabilities = np.exp([0.0, 1.0, 2.0])
        expected_probabilities /= expected_probabilities.sum()
        expected_value = expected_probabilities[2] + 0.5 * expected_probabilities[1]
        for transform in ('centered_50', 'identity'):
            with self.subTest(transform=transform):
                arrays = (weights1, weights2)
                if transform == 'identity':
                    arrays = tuple((w - 50.0) / 50.0 for w in arrays)
                self.write_model(dict(zip(('weights1', 'weights2'), arrays)))
                self.spec['weight_transform'] = transform
                with contextlib.redirect_stdout(io.StringIO()):
                    self.rollout.load_weights(self.path, evaluator_spec=self.spec)
                    functional = CrossbarNNFunctional(self.path, board_size=2, evaluator_spec=self.spec)
                value, probabilities = functional.forward(board)
                np.testing.assert_allclose(probabilities, expected_probabilities, atol=1e-14, rtol=0)
                self.assertAlmostEqual(value, expected_value, places=14)
                self.assertAlmostEqual(self.rollout._nn_forward(board), expected_value, places=14)
                json.dumps(self.rollout.evaluator_info, allow_nan=False)
        self.spec['output_order'][0] = 'changed_by_caller'
        self.assertEqual(self.rollout.evaluator_info['spec']['output_order'], ['white', 'draw', 'black'])

    def test_centered_conductance_domain_and_signed_adc_boundary(self):
        self.spec['weight_transform'] = 'centered_50'
        self.write_model({'weights1': np.full((8, 32), -1.0), 'weights2': np.zeros((32, 3))})
        self.assert_both_reject(self.spec, 'conductances in')
        self.write_model({'weights1': np.full((8, 32), 50.0), 'weights2': np.full((32, 3), 50.0)})
        with self.assertRaisesRegex(ValueError, 'signed ADC'):
            CrossbarNNFunctional(self.path, board_size=2, evaluator_spec=self.spec, adc_bits=8)

    def test_board_encoding_is_explicit(self):
        np.testing.assert_array_equal(
            encode_board(np.array([[1, 0], [-1, 1]]), 2),
            [1, 0, 0, 0, 0, 1, 1, 0],
        )
        for board in (np.zeros((3, 3)), np.array([[1, 2], [0, 0]])):
            with self.assertRaises(ValueError):
                encode_board(board, 2)

    def test_runner_propagates_load_errors_and_records_actual_state(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'supplied together'):
                create_simulation(2, PerformanceLevel.LOW, weights_file=self.path)
            with self.assertRaisesRegex(ValueError, 'checkpoint_sha256 mismatch'):
                create_simulation(2, PerformanceLevel.LOW, weights_file=self.path,
                                  evaluator_spec={**self.spec, 'checkpoint_sha256': '0' * 64})
            simulation, system = create_simulation(
                2, PerformanceLevel.LOW, weights_file=self.path, evaluator_spec=self.spec
            )
        rollout = simulation.get_component('rollout')
        self.assertIs(rollout.node_storage, system.node_storage)
        self.assertIs(rollout.system_component, system)
        self.assertTrue(system._rollout_weights_loaded)
        self.assertEqual(system.evaluator_info['spec'], self.spec)

    def test_api_distinguishes_random_diagnostics_from_no_evaluation(self):
        model = Accelerator(board_size=2, iterations=2)
        with contextlib.redirect_stdout(io.StringIO()):
            simulation = model.analyze(mode='simulate')
        analytical = model.analyze(mode='analytical')
        self.assertEqual(simulation.evaluator['mode'], 'random_diagnostic')
        self.assertEqual(simulation.evaluator['input_size'], 8)
        self.assertEqual(len(simulation.evaluator['weight_sha256']), 2)
        self.assertEqual(analytical.evaluator['mode'], 'not_executed')
        self.assertEqual(simulation.evaluator['hardware_mapping'], 'unverified')


if __name__ == '__main__':
    unittest.main()
