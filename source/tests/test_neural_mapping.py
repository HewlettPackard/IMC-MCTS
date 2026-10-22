# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import contextlib
import io
import json
import unittest
from dataclasses import asdict

import numpy as np

from core.architecture.accelerator_api import Accelerator
from core.architecture.neural_mapping import (
    NeuralMapping, neural_profile, round_divide, round_shift, sliced_dot,
)
from core.simulator.tree_memory import TreeMemory, memory_config


class NeuralMappingTests(unittest.TestCase):
    def test_signed_slices_match_an_independent_integer_product(self):
        rng = np.random.RandomState(17)
        for inputs, outputs, bits in ((18, 3, 1), (162, 96, 1), (96, 3, 8), (258, 35, 8)):
            with self.subTest(shape=(inputs, outputs)):
                x = rng.randint(0, 2**bits, size=inputs)
                weights = rng.randint(-127, 128, size=(inputs, outputs))
                actual = sliced_dot(x, weights, input_bits=bits)
                expected = np.array([sum(int(x[i]) * int(weights[i, j])
                    for i in range(inputs)) for j in range(outputs)])
                np.testing.assert_array_equal(actual, expected)

    def test_eight_bit_adc_covers_maximum_cell_sum(self):
        x = np.ones(16, dtype=int)
        weights = np.full((16, 3), 127)
        np.testing.assert_array_equal(sliced_dot(x, weights, input_bits=1), [2032] * 3)
        with self.assertRaisesRegex(ValueError, 'ADC'):
            neural_profile(board_size=9, hidden_size=96, active_rows=32)

    def test_rounding_is_signed_nearest_even(self):
        self.assertEqual([round_shift(value, 1) for value in [-5, -3, -1, 1, 3, 5]], [-2, -2, 0, 0, 2, 2])
        self.assertEqual(round_shift(3, -2), 12)

    def test_mapping_counts_both_layers_and_all_cells(self):
        model = NeuralMapping(np.zeros((162, 96)), np.zeros((96, 3)), board_size=9)
        estimate = model.estimate()
        self.assertEqual(estimate['resources']['logical_weights'], 15840)
        self.assertEqual(estimate['resources']['mapped_cells'], 63360)
        self.assertEqual(estimate['resources']['array_count'], 4)
        self.assertEqual(estimate['resources']['allocated_cells'], 131072)
        self.assertEqual(estimate['operations']['array_pulses'], 33 + 48)
        self.assertEqual(estimate['operations']['adc_conversions'], 33 * 128 + 48 * 12)
        self.assertEqual(estimate['operations']['adc_groups'], 33 * 43 + 48 * 4)

    def test_known_inference_preserves_integer_intermediates(self):
        weights1 = np.zeros((8, 32))
        weights2 = np.zeros((32, 3))
        weights1[0, 0] = 1
        weights2[0, 2] = 1
        model = NeuralMapping(weights1, weights2, board_size=2)
        value = model.forward(np.array([[1, 0], [0, 0]]))
        np.testing.assert_array_equal(model.last_state['logits_q12'], [0, 0, 4096])
        self.assertEqual(model.last_state['hidden_codes'][0], 64)
        expected = (np.e + 0.5) / (np.e + 2)
        self.assertLess(abs(value - expected), 1e-5)

    def test_complete_serial_schedule_matches_hand_count(self):
        model = NeuralMapping(np.zeros((162, 96)), np.zeros((96, 3)), board_size=9)
        estimate = model.estimate(capture_trace=True)
        self.assertEqual(estimate['phase_cycles'], {'layer1': 21540, 'layer2': 3103, 'output': 171})
        self.assertEqual(estimate['cycles'], 24814)
        self.assertEqual(estimate['storage_bytes'], 16512)
        self.assertEqual(estimate['coefficient_initialization_words'], 4097)
        previous_end = 0
        for row in estimate['trace']:
            self.assertEqual(row['start'], previous_end)
            self.assertGreater(row['end'], row['start'])
            previous_end = row['end']
        self.assertEqual(previous_end, estimate['cycles'])

    def test_trace_identifies_array_pulses_and_actual_lut_addresses(self):
        weights1 = np.zeros((8, 32))
        weights2 = np.zeros((32, 3))
        weights1[0, 0] = 1
        weights2[0, 2] = 1
        model = NeuralMapping(weights1, weights2, board_size=2)
        model.forward(np.array([[1, 0], [0, 0]]))
        trace = model.inference_trace()
        pulses = [row for row in trace if row['operation'] == 'array_pulses']
        self.assertEqual(pulses[0]['active_rows'], [0, 8])
        self.assertEqual(pulses[0]['input_bit'], 0)
        reads = [row for row in trace if row['region'] == 'exp_lut']
        self.assertEqual([row['address'] for row in reads], [1024, 1024, 0])
        self.assertEqual(len(model.storage), model.profile['storage_bytes'])

    def test_mapped_api_uses_schedule_and_withholds_incompatible_ppa(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result = Accelerator(board_size=9, iterations=2, neural_mode='mapped',
                capture_memory_trace=True).analyze('simulate')
        self.assertEqual(result.simulation['cycles'], 1771 + 2 * (24814 - 7) + 4097)
        self.assertEqual(result.simulation['neural']['evaluations'], 2)
        self.assertEqual(result.simulation['neural']['cumulative_operations']['adc_conversions'], 2 * 4800)
        self.assertEqual(result.simulation['memory']['scratch_bytes_reserved'], 16752 + 16512)
        self.assertIsNone(result.energy_uj)
        self.assertIsNone(result.power_mw)
        self.assertIsNone(result.area_mm2)
        self.assertIsNone(result.energy_efficiency_miter_per_j)
        self.assertIn('unavailable', str(result))
        self.assertEqual(result.accounting['status'], 'unavailable_for_mapped_neural_geometry')
        self.assertEqual(result.evaluator['neural_mode'], 'mapped')

    def test_reference_mode_retains_previous_numerical_and_timing_case(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result = Accelerator(board_size=9, iterations=2, neural_mode='reference').analyze('simulate')
        self.assertEqual(result.simulation['cycles'], 1771)
        self.assertEqual(result.simulation['tree_sha256'], 'b093e460c6dfd0761d66ad6be8c53763daad0ebb34a532cf284506b9f895751d')
        self.assertIsNotNone(result.area_mm2)

    def test_unsupported_modes_and_mapped_power_overrides_are_rejected(self):
        with self.assertRaises(ValueError):
            Accelerator(neural_mode='guessed')
        model = Accelerator(neural_mode='mapped')
        with self.assertRaisesRegex(ValueError, 'simulate'):
            model.analyze('analytical')
        with self.assertRaisesRegex(ValueError, 'PPA'):
            model.set_power_parameters(dac_power_mw=0.2)

    def test_nonreal_and_nonfinite_weights_are_rejected(self):
        for weights in (np.ones((8, 32), dtype=complex), np.full((8, 32), np.nan)):
            with self.subTest(dtype=str(weights.dtype)):
                with self.assertRaises(ValueError):
                    NeuralMapping(weights, np.zeros((32, 3)), board_size=2)

    def test_divider_rounding_and_width_limits(self):
        self.assertEqual([round_divide(n, 2) for n in (1, 3, 5, 7)], [0, 2, 2, 4])
        self.assertEqual(round_divide(2**47, 2**31), 2**16)
        for numerator, denominator in ((2**48, 1), (1, 0), (1, 2**32), (-1, 1)):
            with self.assertRaises(OverflowError):
                round_divide(numerator, denominator)

    def test_adc_sharing_changes_time_without_changing_inference(self):
        rng = np.random.RandomState(19)
        weights1, weights2 = rng.randn(18, 35), rng.randn(35, 3)
        cycles, values = [], []
        for lanes in (1, 3, 32):
            model = NeuralMapping(weights1, weights2, 3, adc_lanes=lanes)
            values.append(model.forward(np.array([[1, -1, 0], [0, 1, 0], [-1, 0, 0]])))
            cycles.append(model.schedule['cycles'])
        self.assertEqual(values[0], values[1])
        self.assertEqual(values[1], values[2])
        self.assertGreater(cycles[0], cycles[1])
        self.assertGreater(cycles[1], cycles[2])

    def test_partial_rows_use_aligned_sram_words(self):
        model = NeuralMapping(np.ones((8, 5)), np.ones((5, 3)), 2, active_rows=2)
        self.assertGreater(model.forward(np.array([[1, 0], [0, 0]])), 0)
        for row in model.inference_trace():
            if row['resource'] != 'node_sram':
                continue
            capacity = 4 if row['region'] == 'board' else model.profile['storage'][row['region']]['bytes']
            self.assertEqual(row['address'] % 4, 0)
            self.assertLessEqual(row['address'] + row['bytes'], capacity)

    def test_intermediates_occupy_the_allocated_tree_sram(self):
        model = NeuralMapping(np.ones((8, 32)), np.ones((32, 3)), 2)
        config = memory_config(Accelerator(board_size=2).base_config,
                               neural_scratch_bytes=model.profile['storage_bytes'])
        memory = TreeMemory(config, {}, capture_trace=True)
        model.bind_memory(memory)
        memory.neural = model
        model.forward(np.array([[1, 0], [0, 0]]))
        memory.complete_neural()
        base = config['neural_base']
        self.assertEqual(list(memory.node_sram[base:base + 32]), model.last_state['hidden_codes'])
        lut = model.profile['storage']['exp_lut']
        self.assertEqual(int.from_bytes(memory.node_sram[base + lut['offset']:base + lut['offset'] + 4], 'little'), 2**30)
        self.assertEqual(memory.operations['node_sram_read_words'], model.schedule['operations']['node_sram_read_words'])
        self.assertEqual(memory.transactions[-1]['lut_indices'], model.last_state['lut_indices'])
        with self.assertRaises(MemoryError):
            model._read('hidden', 33, 'u1')

    def test_neural_scratch_reduces_node_capacity(self):
        reference = memory_config(Accelerator(board_size=9).base_config)
        mapped = memory_config(Accelerator(board_size=9).base_config, neural_scratch_bytes=16512)
        self.assertEqual(reference['node_capacity'], 32419)
        self.assertEqual(mapped['node_capacity'], 32075)
        with self.assertRaises(ValueError):
            Accelerator(neural_mode='mapped', memory_limits={'nodes': 32419})

    def test_trace_capture_keeps_identity_and_results_and_json_has_null_ppa(self):
        with contextlib.redirect_stdout(io.StringIO()):
            a = Accelerator(board_size=3, iterations=4, neural_mode='mapped').analyze('simulate')
            b = Accelerator(board_size=3, iterations=4, neural_mode='mapped', capture_memory_trace=True).analyze('simulate')
        self.assertEqual(a.run_identity, b.run_identity)
        self.assertEqual(a.simulation['cycles'], b.simulation['cycles'])
        self.assertEqual(a.simulation['tree_sha256'], b.simulation['tree_sha256'])
        self.assertEqual(a.simulation['memory']['schedule_sha256'], b.simulation['memory']['schedule_sha256'])
        decoded = json.loads(json.dumps(asdict(a), allow_nan=False))
        self.assertIsNone(decoded['energy_uj'])
        self.assertEqual(decoded['area_breakdown'], {})
        self.assertNotIn('neural internal transfers', a.simulation['activity']['operation_count_basis']['excluded'])

    def test_loading_new_weights_cannot_leave_an_old_resident_mapping(self):
        from core.simulator.mcts_sst_components import RolloutUnitComponent
        from py_sst_cpp.core.component import ComponentId
        from py_sst_cpp.core.config import Params

        rollout = RolloutUnitComponent(ComponentId(3, 'rollout'), Params({'board_size': 2, 'seed': 0}))
        rollout.neural_mapping = NeuralMapping(rollout.weights1, rollout.weights2, 2)
        with self.assertRaisesRegex(RuntimeError, 'mapping'):
            rollout.load_weights('unused.pkl')


if __name__ == '__main__':
    unittest.main()
