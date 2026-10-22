# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

import contextlib
import io
import random
import unittest
from unittest.mock import patch

import numpy as np

from core.architecture.accelerator_api import Accelerator
from py_sst_cpp.core import Simulation


class SimulationIterationTests(unittest.TestCase):
    def setUp(self):
        self.random_state = random.getstate()
        self.numpy_state = np.random.get_state()

    def tearDown(self):
        random.setstate(self.random_state)
        np.random.set_state(self.numpy_state)

    def test_custom_budgets_reach_the_event_simulator(self):
        for budget in (1, 200, 6000):
            with self.subTest(iterations=budget):
                random.seed(0)
                np.random.seed(0)
                model = Accelerator(board_size=9, iterations=budget)
                with contextlib.redirect_stdout(io.StringIO()):
                    result = model._run_sst_simulation()
                self.assertEqual(result['total_iterations'], budget)

    def test_medium_preset_still_completes(self):
        random.seed(0)
        np.random.seed(0)
        model = Accelerator(board_size=9, play_strength='medium')
        with contextlib.redirect_stdout(io.StringIO()):
            result = model._run_sst_simulation()
        self.assertEqual(result['total_iterations'], 5000)

    def test_partial_search_cannot_return_performance_metrics(self):
        run = Simulation.run

        def stop_early(simulation, end_time=None):
            return run(simulation, end_time=1)

        model = Accelerator(board_size=9, iterations=200)
        with patch.object(Simulation, 'run', stop_early):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, 'requested 200, completed 0'):
                    model.analyze(mode='simulate')


if __name__ == '__main__':
    unittest.main()
