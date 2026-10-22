# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import contextlib
import hashlib
import io
from pathlib import Path
import unittest

import numpy as np

from core.architecture.accelerator_api import Accelerator, estimate
from core.architecture.neural_mapping import NeuralMapping, neural_profile


class NeuralRtlTimingTests(unittest.TestCase):
    def test_controller_cycles_and_word_cadence(self):
        model = NeuralMapping(np.zeros((162, 96)), np.zeros((96, 3)), 9,
            sram_word_cycles=2, neural_timing='rtl_serial_v1')
        schedule = model.schedule
        self.assertEqual(schedule['cycles'], 26620)
        ops = schedule['operations']
        self.assertEqual(ops['sram_request_handshakes'], 96)
        self.assertEqual(ops['adc_request_handshakes'], 1611)
        self.assertEqual(ops['divider_completion_handshakes'], 3)
        trace = schedule['trace']
        end = 0
        for index, row in enumerate(trace):
            self.assertEqual(row['start'], end)
            end = row['end']
            if row['resource'] == 'node_sram':
                self.assertEqual(row['bytes'], 4)
                self.assertEqual(row['end'] - row['start'], 2)
                self.assertEqual(trace[index - 1]['operation'], 'sram_request_handshakes')
        writes = [row for row in trace if row['region'] == 'hidden'
                  and row['operation'] == 'node_sram_write_words']
        self.assertEqual([row['start'] - writes[0]['start'] for row in writes[:8]],
                         list(range(0, 8 * 7, 7)))
        self.assertEqual(end, 26620)

    def test_timing_does_not_change_integer_inference(self):
        rng = np.random.RandomState(19)
        weights = [rng.randn(162, 96), rng.randn(96, 3)]
        board = rng.randint(-1, 2, (9, 9))
        service = NeuralMapping(*weights, 9, sram_word_cycles=2)
        rtl = NeuralMapping(*weights, 9, sram_word_cycles=2, neural_timing='rtl_serial_v1')
        self.assertEqual(service.forward(board), rtl.forward(board))
        self.assertEqual(service.last_state, rtl.last_state)
        self.assertEqual(service.schedule['cycles'], 24910)
        for name, count in service.schedule['operations'].items():
            self.assertEqual(rtl.schedule['operations'][name], count)
        for row in rtl.inference_trace():
            if 'lut_output' in row:
                self.assertEqual(row['address'], 4 * rtl.last_state['lut_indices'][row['lut_output']])

    def test_api_identity_and_partial_energy_track_new_time(self):
        options = dict(board_size=9, iterations=2, neural_mode='mapped', memory_profile='cacti_22nm_lstp')
        with contextlib.redirect_stdout(io.StringIO()):
            old = Accelerator(**options).analyze('simulate')
            new = Accelerator(**options, neural_timing='rtl_serial_v1').analyze('simulate')
            repeated = estimate(**options, neural_timing='rtl_serial_v1', mode='simulate')
        self.assertEqual(old.simulation['cycles'], 61435)
        self.assertEqual(new.simulation['cycles'], 64855)
        self.assertEqual(old.simulation['tree_sha256'], new.simulation['tree_sha256'])
        self.assertEqual(new.run_identity, repeated.run_identity)
        self.assertNotEqual(old.run_identity['configuration_sha256'], new.run_identity['configuration_sha256'])
        self.assertIsNone(new.energy_uj)
        self.assertIsNone(new.power_mw)
        self.assertIsNone(new.area_mm2)
        old_sram, new_sram = old.accounting['sram'], new.accounting['sram']
        self.assertEqual(old_sram['dynamic_energy_nj'], new_sram['dynamic_energy_nj'])
        self.assertAlmostEqual(new_sram['leakage_energy_nj'] / old_sram['leakage_energy_nj'],
                               64855 / 61435)
        data = Path(__file__).resolve().parents[1] / 'core/architecture/neural_controller_timing.json'
        sources = new.run_identity['source_sha256']
        self.assertEqual(sources['core/architecture/neural_controller_timing.json'],
                         hashlib.sha256(data.read_bytes()).hexdigest())

    def test_unverified_configurations_are_rejected(self):
        for changes in ({'board_size': 13}, {'hidden_size': 32}, {'adc_lanes': 1},
                        {'active_rows': 8}, {'sram_word_cycles': 1}, {'neural_timing': 'guessed'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                neural_profile(**(dict(board_size=9, hidden_size=96, sram_word_cycles=2,
                    neural_timing='rtl_serial_v1') | changes))
        for changes in ({'neural_mode': 'reference'}, {'memory_profile': 'reference'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Accelerator(**(dict(neural_mode='mapped', memory_profile='cacti_22nm_hp',
                    neural_timing='rtl_serial_v1') | changes))

    def test_mutated_timing_cannot_silently_fall_back(self):
        model = Accelerator(neural_mode='mapped', memory_profile='cacti_22nm_hp')
        model.neural_timing = 'guessed'
        with self.assertRaisesRegex(ValueError, 'neural_timing'):
            model.analyze('simulate')


if __name__ == '__main__':
    unittest.main()
