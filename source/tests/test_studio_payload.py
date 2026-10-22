# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Cost rendering must not hold the simulation lock or mix two snapshots.
# SPDX-License-Identifier: MIT
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from p05_studio.p00_app.server import Job


class StudioPayloadTests(unittest.TestCase):
    def test_slow_cost_response_allows_control_and_keeps_one_snapshot(self):
        job = Job({'memory_profile': 'cacti_22nm_lstp'}, 'test', False, Path('.'))
        job.program = {'profile': {'board_size': 9}}
        job.snapshot = {'cycles': 10, 'operations': {'node_sram_read_words': 2},
            'memory': {}, 'phase_cycles': {'selection': 10}, 'block_active_cycles': {},
            'event': {'phase': 'selection'}}
        entered, release = threading.Event(), threading.Event()
        received = []

        def slow_costs(memory_profile, operations, cycles, profile, memory, phases, active, prepared=None):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('Test failed to release cost calculation')
            return {'cycles': cycles, 'operations': operations, 'phase_cycles': phases}

        with patch('p05_studio.p00_app.server.complete_costs', side_effect=slow_costs):
            worker = threading.Thread(target=lambda: received.append(job.payload()))
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                available = job.condition.acquire(timeout=.25)
                if available:
                    try:
                        job.action('pause')
                        job.snapshot['cycles'] = 20
                        job.snapshot['operations']['node_sram_read_words'] = 4
                        job.snapshot['phase_cycles']['selection'] = 20
                    finally:
                        job.condition.release()
                self.assertTrue(available, 'PPA calculation blocked execution controls')
            finally:
                release.set()
                worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertTrue(job.paused)
        self.assertEqual(received[0]['snapshot']['cycles'], 10)
        self.assertEqual(received[0]['snapshot']['operations']['node_sram_read_words'], 2)
        self.assertEqual(received[0]['live_costs'], {'cycles': 10,
            'operations': {'node_sram_read_words': 2}, 'phase_cycles': {'selection': 10}})


if __name__ == '__main__':
    unittest.main()
