# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
"""Negative controls for the legacy numerical-portability regression."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from p03_experiments.p104_simulator_campaign.legacy_reference import (
    structure_sha256, verify_reference,
)


class LegacyReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'reference.json'
        self.tree = {
            0: {'parent': -1, 'visits': 2, 'value': 1.25,
                'board': np.zeros((2, 2), dtype=np.int8), 'player': 1, 'children': [1, 2]},
            1: {'parent': 0, 'visits': 1, 'value': 0.75,
                'board': np.array([[1, 0], [0, 0]], dtype=np.int8), 'player': -1, 'children': []},
            2: {'parent': 0, 'visits': 0, 'value': 0.0,
                'board': np.array([[0, 1], [0, 0]], dtype=np.int8), 'player': -1, 'children': []},
        }
        values = b'{"0":1.25,"1":0.75}\n'
        (self.path.parent / 'values.json').write_bytes(values)
        self.reference = {
            'schema_version': 2, 'structure_encoder_version': 1,
            'configuration': {'board_size': 2},
            'nodes': 3, 'visited_nodes': 2, 'structure_sha256': structure_sha256(self.tree),
            'values_file': 'values.json', 'values_sha256': hashlib.sha256(values).hexdigest(),
            'value_rtol': 1e-14, 'value_atol': 2e-14,
        }
        self.path.write_text(json.dumps(self.reference))

    def test_roundoff_is_tolerated_without_changing_discrete_state(self):
        self.tree[1]['value'] = np.nextafter(self.tree[1]['value'], np.inf)
        self.assertEqual(verify_reference(self.tree, self.path), {'nodes': 3, 'visited_nodes': 2})

    def test_discrete_changes_are_rejected(self):
        for field, changed in [('children', [2, 1]), ('visits', 3), ('parent', 1),
                               ('board', np.ones((2, 2), dtype=np.int8)), ('player', -1)]:
            with self.subTest(field=field):
                tree = copy.deepcopy(self.tree)
                tree[0][field] = changed
                with self.assertRaisesRegex(AssertionError, 'structure'):
                    verify_reference(tree, self.path)

    def test_meaningful_value_change_is_rejected(self):
        self.tree[1]['value'] += 1e-8
        with self.assertRaisesRegex(AssertionError, 'accumulated value'):
            verify_reference(self.tree, self.path)

    def test_board_shape_and_integer_aliases_are_rejected(self):
        for board in (np.zeros((1, 4), dtype=np.int8), np.full((2, 2), 256),
                      np.full((2, 2), 0.5)):
            with self.subTest(board=board):
                tree = copy.deepcopy(self.tree)
                tree[0]['board'] = board
                with self.assertRaisesRegex(AssertionError, 'board shape or cell'):
                    verify_reference(tree, self.path)

    def test_nonfinite_and_unvisited_nonzero_values_are_rejected(self):
        for node, value, message in [(1, float('nan'), 'Nonfinite'),
                                     (2, float('inf'), 'Nonfinite'), (2, 1e-30, 'Nonzero unvisited')]:
            with self.subTest(node=node, value=value):
                tree = copy.deepcopy(self.tree)
                tree[node]['value'] = value
                with self.assertRaisesRegex(AssertionError, message):
                    verify_reference(tree, self.path)

    def test_corrupted_value_fixture_is_rejected(self):
        (self.path.parent / 'values.json').write_text('{"0":1.0,"1":0.75}')
        with self.assertRaisesRegex(AssertionError, 'fixture hash'):
            verify_reference(self.tree, self.path)

    def test_visited_set_is_checked_independently(self):
        self.reference['visited_nodes'] = 1
        self.path.write_text(json.dumps(self.reference))
        with self.assertRaisesRegex(AssertionError, 'visited node set'):
            verify_reference(self.tree, self.path)


if __name__ == '__main__':
    unittest.main()
