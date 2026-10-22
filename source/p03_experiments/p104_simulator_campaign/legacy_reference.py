# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
"""Portable regression contract for the legacy floating-point placement search.

Production run identities still hash exact floating-point bytes. This test-only
contract requires exact discrete search state and separately checks every value.
"""
import hashlib
import json
import math
from pathlib import Path
import struct


def structure_sha256(tree):
    """Version 1: original tree encoder with only its float64 value omitted."""
    digest = hashlib.sha256()
    for node_id, node in sorted(tree.items()):
        digest.update(struct.pack('!QqQ', node_id, node['parent'], node['visits']))
        digest.update(node['board'].astype('int8').tobytes())
        digest.update(json.dumps([node['player'], node['children']]).encode())
    return digest.hexdigest()


def verify_reference(tree, fixture_path):
    """Reject structural or meaningful numerical drift; return checked counts."""
    fixture_path = Path(fixture_path)
    reference = json.loads(fixture_path.read_text())
    if reference['schema_version'] != 2 or reference['structure_encoder_version'] != 1:
        raise ValueError('Unsupported legacy reference schema or encoder')
    value_path = fixture_path.parent / reference['values_file']
    if value_path.parent.resolve() != fixture_path.parent.resolve():
        raise ValueError('Legacy values must be beside their reference')
    raw = value_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference['values_sha256']:
        raise AssertionError('Legacy value fixture hash mismatch')
    expected = json.loads(raw)
    size = reference['configuration']['board_size']
    for key, node in tree.items():
        board = node['board']
        if board.shape != (size, size) or any(cell not in (-1, 0, 1) for cell in board.flat):
            raise AssertionError(f'Invalid legacy board shape or cell at node {key}')
    if len(tree) != reference['nodes'] or structure_sha256(tree) != reference['structure_sha256']:
        raise AssertionError('Legacy discrete tree structure differs')
    visited = {str(key) for key, node in tree.items() if node['visits'] > 0}
    if visited != set(expected) or len(visited) != reference['visited_nodes']:
        raise AssertionError('Legacy visited node set differs')
    for key, node in tree.items():
        value = float(node['value'])
        if not math.isfinite(value):
            raise AssertionError(f'Nonfinite legacy value at node {key}')
        if node['visits'] == 0:
            if value != 0.0:
                raise AssertionError(f'Nonzero unvisited value at node {key}')
        else:
            target = float(expected[str(key)])
            if not math.isfinite(target) or not math.isclose(
                value, target, rel_tol=reference['value_rtol'], abs_tol=reference['value_atol']
            ):
                raise AssertionError(f'Legacy accumulated value differs at node {key}')
    return {'nodes': len(tree), 'visited_nodes': len(visited)}
