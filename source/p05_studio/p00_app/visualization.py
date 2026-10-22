# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Observation-only tree checkpoints and counted hardware activity groups.
# SPDX-License-Identifier: MIT
from collections import deque
from copy import deepcopy


RESOURCES = {
    'node_sram': ['node_router', 'node_sram'],
    'child_sram': ['child_router', 'child_sram'],
    'cam': ['selector', 'cam'], 'compute': ['ucb'],
    'controller': ['glue'], 'neural_controller': ['sequencer'],
    'binary_drivers': ['drivers'], 'array': ['arrays'],
    'column_hold': ['column_hold'], 'column_mux': ['mux'],
    'sample_hold': ['sample_hold'], 'adc_bank': ['adc'],
    'readout_bus': ['readout'], 'shift_add_lane': ['accumulator'],
    'accumulator_registers': ['accumulator'], 'activation_lane': ['activation'],
    'selection_loader':['candidates'], 'score_controller':['selector'], 'ucb_bank':['ucb'],
    'shift_add_lanes':['accumulator'], 'offset_alu':['correction'], 'input_sum':['correction'], 'offset_correction':['correction'],
    'scale_lane': ['output'], 'output_alu': ['output'], 'divider': ['divider'],
}


class Visualization:
    def __init__(self):
        self.key = None
        self.nodes = {}
        self.revision = 0
        self.changes = deque(maxlen=128)
        self.path = []

    def observe(self, event, model, perspective=1):
        key = event['run']
        if self.key != key:
            self.key = key
            self.nodes = {}
            self.changes.clear()
            self.path = []
        # Node IDs are allocated monotonically; only the current path's stats change.
        path = []
        node_id = model.selected
        while node_id >= 0:
            path.append(node_id)
            node_id = model.memory.nodes[node_id]['parent']
        self.path = list(reversed(path))
        changed = []
        candidates = set(range(len(self.nodes), model.memory.nodes_used)) | set(path)
        for node_id in sorted(candidates):
            source = model.memory.nodes[node_id]
            old = self.nodes.get(node_id)
            if old is None:
                board = (model.board(node_id) * perspective).tolist()
                move = getattr(model, 'moves', {}).get(node_id)
                if move is None and source['parent'] >= 0:
                    parent = model.board(source['parent'])
                    positions = (model.board(node_id) != parent).nonzero()
                    move = [int(positions[0][0]), int(positions[1][0])] if len(positions[0]) else None
                row = {'id': node_id, 'parent': source['parent'], 'board': board,
                    'move': move, 'player': int(source['player']) * perspective}
            else:
                row = dict(old)
            row.update(visits=source['visits'], value_sum=source['value'], children=len(source['children']))
            if old != row:
                self.nodes[node_id] = row
                changed.append(row)
        self.revision += 1
        self.changes.append((self.revision, changed))

    def payload(self, after=0, key=None):
        reset = key != self.key or not self.changes or after < self.changes[0][0]-1 or after > self.revision
        if reset:
            nodes = list(self.nodes.values())
        else:
            nodes = {}
            for revision, rows in self.changes:
                if revision > after:
                    nodes.update((row['id'], row) for row in rows)
            nodes = list(nodes.values())
        return {'key': self.key, 'revision': self.revision, 'reset': reset,
            'nodes': nodes, 'total': len(self.nodes), 'path': self.path}


def activity_groups(event, model, cache=None):
    phase = event['phase']
    transactions = model.memory.transactions
    model.memory.transactions = []
    if phase == 'ready':
        model.memory.capture_trace = True
        return []
    if phase == 'iteration_commit' and (model.completed == model.iterations or model.status=='memory_limited'):
        model.memory.capture_trace = False
    if phase == 'neural':
        # The resolved neural schedule has layer/array/row/column context. Its
        # service cycle positions do not include all outer-controller gaps.
        source = 'resolved_neural_schedule'
        if cache is not None:
            if model.neural.last_state is None:
                raise RuntimeError('Run an inference before requesting its resolved trace')
            trace = model.neural.schedule['trace']
            if cache.get('trace') is not trace:
                cache.update(trace=trace, groups=group_records(trace, phase, source))
            # Counts and service positions are fixed for this mapping. Only
            # the first record's LUT address can depend on the current input.
            groups = deepcopy(cache['groups'])
            for group in groups:
                first = group['first']
                if 'lut_output' in first:
                    first['address'] = model.neural.last_state['lut_indices'][first['lut_output']] * 4
            return groups
        records = model.neural.inference_trace()
    else:
        records = [r for r in transactions if r['resource']!='parallel_selection']+getattr(model,'selection_trace',[]) if phase=='selection' else transactions
        source = 'ordered_memory_services'
    return group_records(records, phase, source)


def group_records(records, phase, source):
    groups = {}
    for row in records:
        key = (row.get('phase', phase), row['resource'], row['operation'])
        if key not in groups:
            groups[key] = {'stage': key[0], 'resource': key[1], 'operation': key[2],
                'blocks': RESOURCES.get(key[1], ['glue']), 'count': 0, 'records': 0,
                'service_cycles': 0, 'source': source, 'first': dict(row)}
        group = groups[key]
        group['count'] += row.get('count', row.get('words', 0)) or 1
        group['records'] += 1
        group['service_cycles'] += row.get('end', 0)-row.get('start', 0)
    return list(groups.values())
