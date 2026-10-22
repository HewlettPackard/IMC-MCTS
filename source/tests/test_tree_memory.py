# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import contextlib
import io
import unittest

import numpy as np

from core.architecture.accelerator_api import Accelerator


class TreeMemoryTests(unittest.TestCase):
    def memory(self, **limits):
        from core.simulator.tree_memory import TreeMemory, memory_config
        config = memory_config(Accelerator(board_size=2).base_config)
        config.update(limits)
        return TreeMemory(config, {}, capture_trace=True)

    def test_api_reports_actual_memory_transactions(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result = Accelerator(board_size=9, iterations=2).analyze('simulate')
        memory = result.simulation['memory']
        self.assertEqual(memory['nodes_used'], 82)
        self.assertEqual(memory['edges_used'], 81)
        self.assertEqual(memory['path_high_water'], 2)
        self.assertGreater(memory['operations']['node_sram_write_words'], 81)
        self.assertEqual(memory['path_entries_used'], 0)

    def test_root_zero_and_all_board_symbols_round_trip(self):
        memory = self.memory()
        board = np.array([[0, 1], [-1, 0]])
        node = {'visits': 7, 'value': 1.23456789012345, 'parent': -1,
                'children': [], 'board': board, 'player': -1}
        memory.begin('initialize', 0, 0)
        memory.allocate_node(0, node)
        decoded = memory.read_node(0)
        self.assertEqual(decoded['value'], node['value'])
        self.assertEqual(decoded['parent'], -1)
        self.assertEqual(decoded['player'], -1)
        np.testing.assert_array_equal(memory.read_board(0), board)
        memory.push_path(0)
        self.assertEqual(memory.pop_path(), 0)
        self.assertEqual(memory.path_depth, 0)

    def test_exact_fit_and_atomic_one_node_overflow(self):
        memory = self.memory(node_capacity=5, edge_capacity=4)
        memory.begin('initialize', 0, 0)
        root = {'visits': 1, 'value': 0.5, 'parent': -1,
                'children': [], 'board': np.zeros((2, 2), dtype=int), 'player': 1}
        memory.allocate_node(0, root)
        memory.reserve_children(4)
        for child in range(1, 5):
            node = dict(root, parent=0, children=[], board=root['board'].copy())
            memory.allocate_node(child, node)
        memory.attach_children(0, [1, 2, 3, 4])
        self.assertEqual(memory.nodes_used, 5)
        self.assertEqual(memory.edges_used, 4)
        before = bytes(memory.node_sram), bytes(memory.child_sram)
        with self.assertRaisesRegex(MemoryError, 'node capacity'):
            memory.reserve_children(1)
        self.assertEqual(before, (bytes(memory.node_sram), bytes(memory.child_sram)))
        addresses = [memory.node_address(node) for node in range(5)]
        self.assertEqual(len(set(addresses)), 5)

    def test_child_pool_overflow_and_path_overflow_are_explicit(self):
        memory = self.memory(edge_capacity=1, path_entries=1)
        memory.begin('initialize', 0, 0)
        node = {'visits': 0, 'value': 0.0, 'parent': -1,
                'children': [], 'board': np.zeros((2, 2), dtype=int), 'player': 1}
        memory.allocate_node(0, node)
        with self.assertRaisesRegex(MemoryError, 'child-pointer capacity'):
            memory.reserve_children(2)
        memory.push_path(0)
        with self.assertRaisesRegex(MemoryError, 'path capacity'):
            memory.push_path(0)
        self.assertEqual(memory.pop_path(), 0)
        with self.assertRaisesRegex(MemoryError, 'empty path'):
            memory.pop_path()

    def test_parent_cache_eviction_and_refill_preserve_links(self):
        memory = self.memory(cam_entries=4)
        memory.begin('initialize', 0, 0)
        for node_id in range(9):
            node = {'visits': 1, 'value': 0.5, 'parent': -1 if node_id == 0 else (0 if node_id <= 4 else 1),
                    'children': [], 'board': np.zeros((2, 2), dtype=int), 'player': 1}
            memory.allocate_node(node_id, node)
        memory.attach_children(0, [1, 2, 3, 4])
        memory.attach_children(1, [5, 6, 7, 8])
        first = memory.lookup_children(0)
        self.assertEqual(first, [1, 2, 3, 4])
        self.assertEqual(memory.lookup_children(0), first)
        self.assertEqual(memory.lookup_children(1), [5, 6, 7, 8])
        self.assertEqual(memory.lookup_children(0), first)
        stats = memory.summary()
        self.assertEqual(stats['operations']['cam_hits'], 1)
        self.assertEqual(stats['operations']['cam_misses'], 3)
        self.assertEqual(stats['operations']['cam_evicted_rows'], 8)
        self.assertLessEqual(stats['cam_high_water'], 4)

    def test_single_port_transactions_never_overlap(self):
        memory = self.memory()
        memory.begin('probe', 0, 7)
        memory.transfer('node_sram', 'read', 0, 24)
        memory.transfer('node_sram', 'write', 24, 12)
        trace = memory.transactions
        self.assertEqual([(event['start'], event['end']) for event in trace], [(7, 13), (13, 16)])
        self.assertEqual([event['words'] for event in trace], [6, 3])

    def test_wrapped_cache_lists_keep_order_and_read_their_header(self):
        memory = self.memory(cam_entries=4)
        for node_id in range(6):
            memory.allocate_node(node_id, {'visits': 1, 'value': 0.5,
                'parent': -1 if node_id == 0 else (0 if node_id <= 3 else 1),
                'children': [], 'board': np.zeros((2, 2), dtype=int), 'player': 1})
        memory.attach_children(0, [1, 2, 3])
        memory.attach_children(1, [4, 5])
        memory.lookup_children(0)
        memory.lookup_children(1)
        start = memory.cursor
        self.assertEqual(memory.lookup_children(1), [4, 5])
        # Six metadata words, one CAM search, four header words, two IDs.
        self.assertEqual(memory.cursor - start, 13)

    def test_unsupported_port_or_service_settings_are_rejected(self):
        for settings in ({'node_ports': 2}, {'word_bytes': 8}, {'sram_word_cycles': 0}):
            with self.subTest(settings=settings):
                with self.assertRaises(ValueError):
                    self.memory(**settings)

    def test_api_capacity_failure_cannot_return_partial_metrics(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(MemoryError, 'node capacity'):
                Accelerator(board_size=9, iterations=2, memory_limits={'nodes': 81}).analyze('simulate')

    def test_selection_costs_each_candidate_on_the_declared_single_lane(self):
        from core.simulator.tree_memory import TreeMemory, memory_config
        from core.simulator.mcts_sst_components import SelectionUnitComponent, IterationStartEvent
        from py_sst_cpp.core import Simulation
        from py_sst_cpp.core.component import ComponentId
        from py_sst_cpp.core.config import Params

        class Response:
            def send(self, event, delay):
                self.event = event
                self.delay = delay

        for count, expected_cycles in ((1, 35), (81, 1315)):
            with self.subTest(children=count):
                nodes = {}
                memory = TreeMemory(memory_config(Accelerator(board_size=9).base_config), nodes)
                for node_id in range(count + 1):
                    memory.allocate_node(node_id, {'visits': 100 if node_id == 0 else 1,
                        'value': 0.5, 'parent': -1 if node_id == 0 else 0, 'children': [],
                        'board': np.zeros((9, 9), dtype=int), 'player': 1})
                memory.attach_children(0, list(range(1, count + 1)))
                memory.lookup_children(0)
                selection = SelectionUnitComponent(ComponentId(1, 'selection'), Params({'board_size': 9}))
                selection.node_storage = nodes
                selection.memory = memory
                response = Response()
                selection.add_link('to_system', response)
                simulation = Simulation('fanout')
                simulation.add_component('selection', selection)
                simulation.schedule_event(memory.cursor, IterationStartEvent(1), selection, selection.handle_iteration_start)
                with contextlib.redirect_stdout(io.StringIO()):
                    simulation.run()
                # Root/leaf metadata and stack = 14 cycles. CAM hit and
                # the ordered-list header read add five cycles.
                # Per candidate: one ID output, six metadata words, eight
                # scratch words, one UCB operation = 16 cycles.
                self.assertEqual(response.delay, expected_cycles)
                self.assertEqual(response.event.path, [0, 1])
                self.assertEqual(memory.operations['ucb_operations'], count)

    def test_event_errors_propagate_and_leave_error_state(self):
        from py_sst_cpp.core import Simulation
        from py_sst_cpp.core.event import EmptyEvent
        from py_sst_cpp.core.simulation import SimulationState

        def fail(event):
            raise MemoryError('test capacity failure')

        simulation = Simulation('failure')
        simulation.schedule_event(1, EmptyEvent(), None, fail)
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(MemoryError, 'test capacity failure'):
                simulation.run()
        self.assertEqual(simulation.state, SimulationState.ERROR)

    def test_limits_change_identity_but_do_not_resize_the_physical_chip(self):
        with contextlib.redirect_stdout(io.StringIO()):
            original = Accelerator(board_size=9, iterations=2).analyze('simulate')
            limited = Accelerator(board_size=9, iterations=2, memory_limits={'nodes': 82}).analyze('simulate')
        self.assertEqual(original.area_mm2, limited.area_mm2)
        self.assertEqual(original.simulation['tree_sha256'], limited.simulation['tree_sha256'])
        self.assertNotEqual(original.run_identity['configuration_sha256'], limited.run_identity['configuration_sha256'])
        for limits in ({'nodes': 0}, {'nodes': True}, {'nodes': 10**9}, {'unknown': 1}):
            with self.subTest(limits=limits):
                with self.assertRaises(ValueError):
                    Accelerator(memory_limits=limits)
        with self.assertRaisesRegex(ValueError, 'simulate mode'):
            Accelerator(memory_limits={'nodes': 82}).analyze('analytical')


if __name__ == '__main__':
    unittest.main()
