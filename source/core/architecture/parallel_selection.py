# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Opt-in four-lane UCB selection with serial SRAM loads and register forwarding.
# SPDX-License-Identifier: MIT
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from core.architecture.block_activity import BLOCKS, phase_activity
from core.architecture.single_child import SingleChildSimulation, SingleChildGoSimulation
from core.architecture.ucb_arithmetic import score
from core.simulator.tree_memory import NO_NODE

SPEC = Path(__file__).with_suffix('.json')
LANES = ('u_ucb_a', 'u_ucb_b', 'u_ucb_c', 'u_ucb_d')


def selection_spec():
    raw = SPEC.read_bytes()
    spec = json.loads(raw)
    if spec['profile'] != 'ucb4_register_batch_v1' or spec['lanes'] != 4:
        raise ValueError('Unsupported parallel selection profile')
    return spec | {'sha256': hashlib.sha256(raw).hexdigest()}


class FourLaneSelection:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.selection_spec = selection_spec()
        self.serial_memory_config = deepcopy(self.memory.config)
        self.memory.config.update(ucb_lanes=4, selection_profile=self.selection_spec['profile'],
            selection_spec_sha256=self.selection_spec['sha256'],
            execution_profile=self.memory.config['execution_profile'] + '_ucb4_registers_v1',
            timing_status='UCB_batch_RTL_checked_with_architectural_single_child_control')
        self.block_active_cycles.pop('u_ucb')
        self.block_active_cycles.update(dict.fromkeys(LANES, 0))
        self.batch_counts = Counter()
        self.capture_selection_batches = False
        self.selection_batches = []

    def _batch(self, parent_visits, candidates):
        count = len(candidates)
        if not 1 <= count <= len(LANES): raise ValueError('A batch needs one to four visited candidates')
        if any(node['visits'] == 0 for _, node in candidates): raise ValueError('Unvisited priority belongs to selection')
        spec = self.selection_spec
        cycles = spec['batch_accepted_to_valid_base_cycles'] + count * spec['batch_reduction_cycles_per_child'] + spec['caller_request_and_capture_cycles']
        start = self.memory.cursor
        self.memory.control('ucb_batch_service', cycles)
        self.memory.count('ucb_operations', count)
        self.memory.count('ucb_batches')
        self.batch_counts[count] += 1
        best = None; best_score = float('-inf')
        for lane, (child, node) in enumerate(candidates):
            value = score(parent_visits, node['visits'], node['value'], self.exploration)
            self.block_active_cycles[LANES[lane]] += spec['arithmetic_active_cycles']
            if value > best_score: best = child; best_score = value
        if self.capture_selection_batches:
            self.selection_batches.append({'start': start, 'end': self.memory.cursor,
                'children': [child for child, _ in candidates], 'best_child': best, 'best_score': best_score})
        return best, best_score

    def _select(self):
        memory = self.memory; memory.reset_path(); current = 0
        memory.control('selection_start', 2)
        while True:
            node = memory.read_node(current); memory.push_path(current)
            memory.control('decode_node_and_branch', 3)
            if not node['visits']: break
            remaining = memory.remaining(current)
            if remaining == NO_NODE: remaining = self._actions(current)
            memory.control('check_remaining_actions')
            if remaining or not node['children_count']: break
            children = memory.lookup_children(current, node)
            best = None; best_score = float('-inf'); pending = []
            for child in children:
                candidate = memory.read_node(child)
                memory.count('candidate_checks')
                memory.control('candidate_control', self.selection_spec['candidate_control_cycles'])
                if not candidate['visits']:
                    # Preserve the reference's prior score work and first-unvisited rule.
                    if pending: self._batch(node['visits'], pending)
                    pending = []; best = child
                    break
                pending.append((child, candidate))
                if len(pending) == len(LANES):
                    winner, value = self._batch(node['visits'], pending)
                    if value > best_score: best = winner; best_score = value
                    pending = []
            if pending:
                winner, value = self._batch(node['visits'], pending)
                if value > best_score: best = winner; best_score = value
            if best is None: raise RuntimeError('No valid child in a nonempty list')
            current = best
        self.selected = current
        return memory.cursor - self.cycles

    def _phase(self, name, action):
        self.memory.begin(name, self.completed + 1, self.cycles)
        before = self.memory.operations.copy()
        lane_before = [self.block_active_cycles[lane] for lane in LANES]
        duration = action()
        remainder = self.cycles + duration - self.memory.cursor
        if remainder < 0: raise AssertionError('Controller schedule is shorter than its services')
        self.memory._record('controller', 'aggregated_control_and_compute', 0, 0, 0, remainder)
        operations = self.memory.operations - before
        operations['ucb_operations'] = 0
        active = phase_activity(name, duration, operations)
        active.pop('u_ucb')
        self.block_active_cycles.update(active)
        if any(not 0 <= self.block_active_cycles[lane] - count <= duration
               for lane, count in zip(LANES, lane_before)):
            raise AssertionError('Physical lane occupancy exceeds phase time')
        self.cycles += duration; self.phase_cycles[name] += duration
        return {'phase': name, 'iteration': self.completed + 1, 'cycles': duration, 'cycle_end': self.cycles,
            'selected_node': self.selected, 'path_depth': self.memory.path_depth,
            'nodes': self.memory.nodes_used, 'edges': self.memory.edges_used,
            'cam_rows': sum(len(item[1]) for item in self.memory.cam.values())}

    def activity_record(self):
        expected = set(BLOCKS) - {'u_ucb'} | set(LANES)
        if set(self.block_active_cycles) != expected: raise ValueError('Incorrect physical block inventory')
        blocks = {}
        for name, active in self.block_active_cycles.items():
            if type(active) is not int or not 0 <= active <= self.cycles:
                raise ValueError('Invalid physical block occupancy')
            blocks[name] = {'active_cycles': active, 'idle_cycles': self.cycles - active}
        return {'profile': self.selection_spec['profile'], 'elapsed_cycles': self.cycles, 'blocks': blocks,
            'boundary': 'Ten digital parents: four identical UCB units, with selector/batch control estimated together. No power gating.'}


class FourLaneSimulation(FourLaneSelection, SingleChildSimulation):
    pass


class FourLaneGoSimulation(FourLaneSelection, SingleChildGoSimulation):
    pass
