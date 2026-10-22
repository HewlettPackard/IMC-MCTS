# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

import contextlib
import io
import random
import unittest
from unittest.mock import patch

import numpy as np

from core.architecture.accelerator_api import Accelerator
from core.simulator.hardware_metrics import ActivityTracker, HardwareModel, MetricsCalculator
from core.simulator.mcts_sst_components import _ns_to_cycles


class HardwareAccountingTests(unittest.TestCase):
    def setUp(self):
        self.random_state = random.getstate()
        self.numpy_state = np.random.get_state()
        random.seed(0)
        np.random.seed(0)

    def tearDown(self):
        random.setstate(self.random_state)
        np.random.set_state(self.numpy_state)

    def test_clock_quantization_never_shortens_an_operation(self):
        for delay, cycles in [(0, 1), (0.5, 1), (2, 1), (2.01, 2),
                              (2.5, 2), (3, 2), (5, 3), (7, 4), (14, 7)]:
            with self.subTest(delay_ns=delay):
                self.assertEqual(_ns_to_cycles(delay), cycles)

    def test_two_iteration_schedule_matches_independent_cycle_sum(self):
        model = Accelerator(board_size=9, iterations=2)
        with contextlib.redirect_stdout(io.StringIO()):
            result = model._run_sst_simulation()
        # 32-bit, one-cycle word service. Initialization writes 6 metadata
        # and 6 board words. Selection reads six words and pushes one ID.
        # NN stages a board (18 words), then takes the legacy seven cycles.
        # Backprop pops an ID, reads six words, adds, and writes three words.
        initialize = 12
        first = 4 + 7 + 6 + (18 + 7) + (1 + 6 + 1 + 3)
        # Expansion reads metadata/board, scans, generates 81 children
        # (6 source + 1 compute + 6 metadata + 6 board each), writes 81
        # pointers and two parent-header words. Then pushes the chosen ID.
        expansion = 6 + 18 + 1 + 81 * 19 + 81 + 2
        second = 4 + 7 + expansion + 1 + (18 + 7) + 2 * (1 + 6 + 1 + 3)
        self.assertEqual(result['simulation_cycles'], initialize + first + second)
        self.assertEqual(result['latency_us'], 3.542)

    def test_power_override_reaches_simulation_energy_and_breakdown(self):
        model = Accelerator(board_size=9, iterations=2)
        model.set_power_parameters(dac_power_mw=0.2, adc_power_mw=0.3,
                                   crossbar_power_density=9000)
        analytical = model.analyze(mode='analytical')
        with contextlib.redirect_stdout(io.StringIO()):
            simulated = model.analyze(mode='simulate')
        expected_power = 4.96 + 12.37 + 1.01 + 5.50 + 0.249
        expected_power += 81 * 0.2 + 3 * 0.3 + 0.000684 * 9000 + 1.46
        for result in (analytical, simulated):
            self.assertEqual(result.accounting['status'], 'uncalibrated_legacy_model')
            self.assertAlmostEqual(result.power_mw, expected_power)
            self.assertAlmostEqual(result.energy_uj, expected_power * result.latency_us / 1000)
            self.assertAlmostEqual(sum(result.power_breakdown[key] for key in
                ('selection', 'expansion', 'rollout', 'backprop', 'fsm', 'tcam')), result.power_mw)
            self.assertAlmostEqual(sum(result.area_breakdown[key] for key in
                ('selection', 'expansion', 'rollout', 'backprop', 'fsm', 'tcam',
                 'cam_array', 'sram_array')), result.area_mm2)
        # A sensitivity probe must not change the shared reference table.
        self.assertAlmostEqual(HardwareModel(9).total_power_mw, 32.635)

    def test_unsupported_physical_configurations_cannot_produce_numbers(self):
        settings = [('technology_nm', 65), ('clock_mhz', 1000),
                    ('nn_hidden_size', 32), ('nn_outputs', 5)]
        for field, value in settings:
            for mode in ('analytical', 'simulate'):
                with self.subTest(field=field, mode=mode):
                    model = Accelerator(board_size=9, iterations=2)
                    setattr(model, field, value)
                    with self.assertRaisesRegex(ValueError, 'supported|reference'):
                        model.analyze(mode=mode)

    def test_small_board_default_and_setter_validation(self):
        model = Accelerator(board_size=3, iterations=1)
        self.assertEqual(model.nn_hidden_size, 32)
        with self.assertRaises(ValueError):
            model.set_neural_network(hidden_size=96)
        with self.assertRaises(ValueError):
            model.set_technology(clock_mhz=250)
        self.assertEqual(model.nn_hidden_size, 32)
        self.assertEqual(model.clock_mhz, 500)
        for value in (-1, float('nan'), float('inf')):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    model.set_power_parameters(dac_power_mw=value)
        with self.assertRaises(ValueError):
            model.analyze(mode='typo')

    def test_activity_counts_new_nodes_and_actual_backprop_path(self):
        captured = {}
        collect = ActivityTracker.collect_statistics

        def capture(tracker):
            collect(tracker)
            captured['tracker'] = tracker

        with patch.object(ActivityTracker, 'collect_statistics', capture):
            with contextlib.redirect_stdout(io.StringIO()):
                Accelerator(board_size=9, iterations=2)._run_sst_simulation()
        tracker = captured['tracker']
        system = tracker.system_component
        # These now count physical 32-bit transfer words, including scratch.
        # Neither selection has children yet, so neither searches the CAM.
        self.assertEqual(tracker.tree_size, 82)
        self.assertEqual(tracker.cam_lookups, 0)
        self.assertEqual(tracker.sram_reads, 567)
        self.assertEqual(tracker.sram_writes, 1097)
        self.assertEqual(tracker.backprop_updates, sum(node['visits'] for node in system.node_storage.values()))
        phases = tracker.get_component_activity()
        self.assertEqual(phases['expansion_unit']['sram_writes'], 1062)
        self.assertEqual(phases['backprop_unit']['sram_writes'], 9)
        self.assertEqual(sum(row['sram_reads'] for row in phases.values()), tracker.sram_reads)
        self.assertEqual(sum(row['sram_writes'] for row in phases.values()), tracker.sram_writes)

    def test_evaluation_throughput_and_host_time_independence(self):
        tracker = ActivityTracker()
        tracker.total_iterations = 5
        tracker.crossbar_inferences = 3
        metrics = MetricsCalculator(HardwareModel(9), tracker)
        metrics.set_simulation_results(simulation_cycles=500, wall_clock_time_s=0.1)
        energy = metrics.get_total_energy_nj()
        self.assertEqual(metrics.get_throughput_moves_per_sec(), 3e6)
        metrics.set_simulation_results(simulation_cycles=500, wall_clock_time_s=1000)
        self.assertEqual(metrics.get_hardware_latency_us(), 1.0)
        self.assertEqual(metrics.get_total_energy_nj(), energy)


if __name__ == '__main__':
    unittest.main()
