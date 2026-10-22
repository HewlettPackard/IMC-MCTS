# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Reused display work must preserve resolved addresses and ordered services.
# SPDX-License-Identifier: MIT
from copy import deepcopy
import unittest

import numpy as np

from core.architecture.analog_readout import DRIVEN, BUFFERED, configure_readout
from core.architecture.iteration_model import CompleteSimulation
from core.architecture.neural_mapping import NeuralMapping
from p05_studio.p00_app.visualization import activity_groups


class TraceReuseTests(unittest.TestCase):
    def test_filtered_trace_matches_full_trace_after_each_inference(self):
        weights1 = np.zeros((8, 32))
        weights2 = np.zeros((32, 3))
        weights1[0, 0] = 1
        weights2[0, 2] = 1
        model = NeuralMapping(weights1, weights2, 2)
        with self.assertRaises(RuntimeError):
            model.inference_trace(resource='node_sram')
        addresses = []
        for board in (np.array([[1, 0], [0, 0]]), np.zeros((2, 2), dtype=int)):
            model.forward(board)
            full = model.inference_trace()
            for resource in ('node_sram', 'array', 'absent'):
                expected = [row for row in full if row['resource'] == resource]
                actual = model.inference_trace(resource=resource)
                self.assertEqual(actual, expected)
                if actual:
                    actual[0]['address'] = -123
                    self.assertEqual(model.inference_trace(resource=resource), expected)
            addresses.append([r['address'] for r in full if r['region'] == 'exp_lut'])
        self.assertEqual(addresses, [[1024, 1024, 0], [0, 0, 0]])

    def test_cached_groups_match_all_phases_and_switching_readout(self):
        cache = {}
        for mode in (DRIVEN, BUFFERED, DRIVEN):
            with self.subTest(mode=mode):
                model = CompleteSimulation(3, 8, 17)
                configure_readout(model, mode)
                ready = {'phase': 'ready'}
                self.assertEqual(activity_groups(ready, model, cache), [])
                for event in model.steps():
                    transactions = deepcopy(model.memory.transactions)
                    expected = activity_groups(event, model)
                    model.memory.transactions = transactions
                    actual = activity_groups(event, model, cache)
                    self.assertEqual(actual, expected)
                    self.assertEqual(model.memory.transactions, [])
                    if event['phase'] == 'neural':
                        self.assertEqual(any(g['resource'] == 'column_hold' for g in actual), mode == BUFFERED)
                        actual[0]['count'] = -1
                        actual[0]['first']['address'] = -1
                        self.assertEqual(activity_groups(event, model, cache), expected)
                self.assertFalse(model.memory.capture_trace)

    def test_cached_first_lut_address_is_resolved_again(self):
        model = CompleteSimulation(2, 2)
        model.neural.forward(model.initial_board)
        # Isolate a dynamically addressed group that happens to start at a LUT read.
        template = next(deepcopy(r) for r in model.neural.schedule['trace'] if 'lut_output' in r)
        model.neural.schedule['trace'] = [template]
        cache = {}
        for index in (7, 123, 0):
            model.neural.last_state['lut_indices'][template['lut_output']] = index
            group = activity_groups({'phase': 'neural'}, model, cache)[0]
            self.assertEqual(group['first']['address'], index * 4)
        self.assertEqual(model.neural.schedule['trace'], [template])
        replacement = template | {'operation': 'replacement', 'count': 9}
        model.neural.schedule['trace'] = [replacement]
        group = activity_groups({'phase': 'neural'}, model, cache)[0]
        self.assertEqual((group['operation'], group['count']), ('replacement', 9))


if __name__ == '__main__':
    unittest.main()
