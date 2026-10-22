# Bounded tree storage and serialized transactions for the single-core model.
# SPDX-License-Identifier: MIT
import hashlib
import math
import struct
from collections import Counter, deque
from numbers import Integral

import numpy as np


NODE = struct.Struct('<IdIIHH')
NO_NODE = 2**32 - 1
TREE_POLICY = 'evaluate_root_then_expand_all_placement_v1'


def memory_config(board_config, limits=None, neural_scratch_bytes=0):
    if (isinstance(neural_scratch_bytes, bool) or not isinstance(neural_scratch_bytes, Integral)
            or neural_scratch_bytes < 0 or neural_scratch_bytes % 4):
        raise ValueError('Neural scratch must be a nonnegative whole number of SRAM words')
    positions = board_config.board_size**2
    board_bytes = ((2 * positions + 7) // 8 + 3) // 4 * 4
    path_entries = positions + 1
    working_offset = 4 * path_entries
    stats_offset = working_offset + board_bytes
    cache_offset = stats_offset + 16
    node_base = cache_offset + 16 * board_config.cam_entries
    neural_base = node_base
    node_base += neural_scratch_bytes
    node_bytes = int(board_config.node_sram_kb * 1024)
    child_bytes = int(board_config.children_sram_kb * 1024)
    config = {
        'model': 'parent_link_cache_serial_v1',
        'policy': TREE_POLICY,
        'arithmetic': 'binary64_reference_values_and_ucb1',
        'node_format': '<IdIIHH',
        'board_encoding': 'row_major_2bit_0empty_1black_2white',
        'flags': 'bit0 white-to-move; bits1..15 cache-header index valid only after CAM hit',
        'board_size': board_config.board_size,
        'node_sram_bytes': node_bytes, 'child_sram_bytes': child_bytes,
        'node_record_bytes': NODE.size, 'board_bytes': board_bytes,
        'node_stride': NODE.size + board_bytes, 'node_base': node_base,
        'working_offset': working_offset, 'stats_offset': stats_offset,
        'cache_offset': cache_offset,
        'path_storage_entries': path_entries, 'path_entries': path_entries,
        'node_capacity': (node_bytes - node_base) // (NODE.size + board_bytes),
        'edge_capacity': child_bytes // 4,
        'cam_entries': board_config.cam_entries,
        'cam_row_bits': board_config.cam_bits_per_entry,
        'cam_policy': 'whole_parent_lists_fifo',
        'word_bytes': 4, 'node_ports': 1, 'child_ports': 1, 'ucb_lanes': 1,
        'sram_word_cycles': max(1, math.ceil(board_config.sram_access_delay_ns / 2)),
        'cam_search_cycles': max(1, math.ceil(board_config.cam_lookup_delay_ns / 2)),
        'cam_row_write_cycles': max(1, math.ceil(board_config.sram_access_delay_ns / 2)),
        'cam_output_cycles': 1,
        'ucb_cycles': max(1, math.ceil(board_config.selection_delay_ns / 2)),
        'expand_cycles': max(1, math.ceil(board_config.expansion_delay_ns / 2)),
        'update_cycles': max(1, math.ceil(board_config.backprop_delay_ns / 2)),
        'rollout_cycles': max(1, math.ceil(board_config.rollout_total_latency_ns / 2)),
        'timing_status': 'serialized_service_model_uncalibrated',
        'timing_source': 'rounded board_config delays at 500 MHz; one-word service and one-ID output are explicit design assumptions',
        'scratch_source': 'bounded SRAM partitions; no new SRAM macro capacity',
    }
    if neural_scratch_bytes:
        config['neural_base'] = neural_base
        config['neural_bytes'] = neural_scratch_bytes
    names = {'nodes': 'node_capacity', 'edges': 'edge_capacity', 'path_entries': 'path_entries'}
    for name, value in (limits or {}).items():
        if name not in names:
            raise ValueError(f'Unknown memory limit: {name}')
        key = names[name]
        if isinstance(value, bool) or not isinstance(value, Integral) or not 0 < value <= config[key]:
            raise ValueError(f'{name} must be a positive integer within physical capacity {config[key]}')
        config[key] = int(value)
    return config


class TreeMemory:
    def __init__(self, config, nodes, capture_trace=False):
        self.config = dict(config)
        if any(config[name] != value for name, value in
               [('word_bytes', 4), ('node_ports', 1), ('child_ports', 1), ('ucb_lanes', 1)]):
            raise ValueError('Only 32-bit single-port SRAM and one UCB lane are implemented')
        for name, value in config.items():
            if name.endswith('_cycles') and (isinstance(value, bool) or not isinstance(value, Integral) or value <= 0):
                raise ValueError(f'{name} must be a positive integer')
        if config['node_capacity'] <= 0 or config['node_capacity'] >= NO_NODE:
            raise ValueError('Invalid node capacity')
        if config['cam_row_bits'] < 65 or config['cam_entries'] < config['board_size']**2:
            raise ValueError('CAM must hold a complete child list with parent/child IDs and validity')
        if config['cam_entries'] > 2**15:
            raise ValueError('CAM header index exceeds the node flag field')
        if config['node_base'] + config['node_capacity'] * config['node_stride'] > config['node_sram_bytes']:
            raise ValueError('Node allocation exceeds physical SRAM')
        if config['edge_capacity'] * 4 > config['child_sram_bytes']:
            raise ValueError('Child allocation exceeds physical SRAM')
        if (config['path_storage_entries'] * 4 > config['working_offset']
                or config['working_offset'] + config['board_bytes'] > config['stats_offset']
                or config['stats_offset'] + 16 > config['cache_offset']
                or config['cache_offset'] + 16 * config['cam_entries'] > config['node_base']):
            raise ValueError('Scratch, CAM metadata, and node partitions overlap')
        if not 0 < config['path_entries'] <= config['path_storage_entries']:
            raise ValueError('Path allocation exceeds reserved storage')
        if config.get('neural_bytes', 0) and (
                config['neural_base'] < config['cache_offset'] + 16 * config['cam_entries']
                or config['neural_base'] + config['neural_bytes'] > config['node_base']):
            raise ValueError('Neural scratch overlaps tree/cache storage')
        self.nodes = nodes
        self.neural = None
        self.node_sram = bytearray(config['node_sram_bytes'])
        self.child_sram = bytearray(config['child_sram_bytes'])
        self.nodes_used = 0
        self.edges_used = 0
        self.path_depth = 0
        self.path_high_water = 0
        self.cam = {}
        self.cache_fifo = deque()
        self.free_rows = deque(range(config['cam_entries']))
        self.free_headers = deque(range(config['cam_entries']))
        self.cam_high_water = 0
        self.cursor = 0
        self.phase = 'initialize'
        self.iteration = 0
        self.operations = Counter()
        self.phase_operations = {}
        self.phase_cycles = Counter()
        self.capture_trace = capture_trace
        self.transactions = []
        self.schedule_hash = hashlib.sha256()

    def begin(self, phase, iteration, cycle):
        if cycle < self.cursor:
            raise RuntimeError(f'{phase} starts before prior memory work completes')
        self.phase = phase
        self.iteration = iteration
        self.cursor = cycle

    def _record(self, resource, operation, address, size, words, cycles):
        start = self.cursor
        self.cursor += cycles
        self.phase_cycles[self.phase] += cycles
        self.schedule_hash.update(
            f'{self.phase}|{self.iteration}|{resource}|{operation}|{address}|{size}|{words}|{start}|{self.cursor}\n'.encode())
        if self.capture_trace:
            self.transactions.append({'phase': self.phase, 'iteration': self.iteration,
                'resource': resource, 'operation': operation, 'address': address,
                'bytes': size, 'words': words, 'start': start, 'end': self.cursor})

    def count(self, operation, amount=1):
        self.operations[operation] += amount
        self.phase_operations.setdefault(self.phase, Counter())[operation] += amount

    def transfer(self, resource, operation, address, size):
        capacity = self.config['node_sram_bytes' if resource == 'node_sram' else 'child_sram_bytes']
        if resource not in ('node_sram', 'child_sram') or operation not in ('read', 'write'):
            raise ValueError('Unknown SRAM transaction')
        if address < 0 or size <= 0 or address % 4 or size % 4 or address + size > capacity:
            raise MemoryError('Unaligned or out-of-bounds SRAM transaction')
        words = size // 4
        self.count(f'{resource}_{operation}_words', words)
        self._record(resource, operation, address, size, words, words * self.config['sram_word_cycles'])

    def compute(self, operation, count=1):
        cycles = self.config[operation + '_cycles'] * count
        self.count(operation + '_operations', count)
        self._record('compute', operation, 0, 0, 0, cycles)

    def node_address(self, node_id):
        if not 0 <= node_id < self.config['node_capacity']:
            raise MemoryError(f'Node ID {node_id} exceeds node capacity')
        return self.config['node_base'] + node_id * self.config['node_stride']

    def _node_fields(self, node_id):
        if not 0 <= node_id < self.nodes_used:
            raise KeyError(f'Node {node_id} is not allocated')
        visits, value, parent, start, count, flags = NODE.unpack_from(self.node_sram, self.node_address(node_id))
        return {'visits': visits, 'value': value, 'parent': -1 if parent == NO_NODE else parent,
            'children_start': start, 'children_count': count, 'player': -1 if flags & 1 else 1,
            'cache_header': flags >> 1}

    def reserve_children(self, count):
        if count < 0 or count > self.config['board_size']**2:
            raise ValueError('Invalid child count')
        if self.nodes_used + count > self.config['node_capacity']:
            raise MemoryError(f'node capacity: need {self.nodes_used + count}, have {self.config["node_capacity"]}')
        if self.edges_used + count > self.config['edge_capacity']:
            raise MemoryError(f'child-pointer capacity: need {self.edges_used + count}, have {self.config["edge_capacity"]}')

    def allocate_node(self, node_id, node):
        if node_id != self.nodes_used:
            raise ValueError('Node IDs must be allocated consecutively')
        address = self.node_address(node_id)
        board = np.asarray(node['board'])
        if board.shape != (self.config['board_size'], self.config['board_size']) or not np.isin(board, [-1, 0, 1]).all():
            raise ValueError('Expected a placement board with cells in {-1, 0, 1}')
        if node['children'] or node['player'] not in (-1, 1) or not math.isfinite(node['value']):
            raise ValueError('Invalid new node')
        if (node_id == 0 and node['parent'] != -1) or (node_id > 0 and not 0 <= node['parent'] < node_id):
            raise ValueError('A new node must link to an allocated parent, or be root zero')
        parent = NO_NODE if node['parent'] == -1 else node['parent']
        packed_node = NODE.pack(node['visits'], node['value'], parent, NO_NODE, 0, int(node['player'] == -1))
        bits = 0
        for index, value in enumerate(board.flat):
            bits |= (2 if value == -1 else int(value)) << (2 * index)
        packed_board = bits.to_bytes(self.config['board_bytes'], 'little')
        self.transfer('node_sram', 'write', address, NODE.size)
        self.transfer('node_sram', 'write', address + NODE.size, len(packed_board))
        self.node_sram[address:address + NODE.size] = packed_node
        self.node_sram[address + NODE.size:address + self.config['node_stride']] = packed_board
        self.nodes[node_id] = node
        self.nodes_used += 1

    def read_node(self, node_id):
        node = self._node_fields(node_id)
        self.transfer('node_sram', 'read', self.node_address(node_id), NODE.size)
        return node

    def read_board(self, node_id):
        self._node_fields(node_id)
        address = self.node_address(node_id) + NODE.size
        size = self.config['board_bytes']
        scratch = self.config['working_offset']
        self.transfer('node_sram', 'read', address, size)
        self.transfer('node_sram', 'write', scratch, size)
        self.node_sram[scratch:scratch + size] = self.node_sram[address:address + size]
        self.transfer('node_sram', 'read', scratch, size)
        bits = int.from_bytes(self.node_sram[scratch:scratch + size], 'little')
        board = np.zeros((self.config['board_size'], self.config['board_size']), dtype=int)
        for index in range(board.size):
            value = (bits >> (2 * index)) & 3
            if value == 3:
                raise ValueError('Invalid packed board cell')
            board.flat[index] = -1 if value == 2 else value
        return board

    def attach_children(self, parent_id, children):
        node = self._node_fields(parent_id)
        if node['children_count'] or len(children) != len(set(children)):
            raise ValueError('Child lists are allocated once without duplicates')
        if self.edges_used + len(children) > self.config['edge_capacity']:
            raise MemoryError('child-pointer capacity exceeded')
        if len(children) > self.config['cam_entries'] or len(children) > 65535:
            raise MemoryError('Child list exceeds CAM capacity')
        for child in children:
            if self._node_fields(child)['parent'] != parent_id:
                raise ValueError('Child parent does not match its list')
        if children:
            start = self.edges_used
            for child in children:
                address = 4 * self.edges_used
                self.transfer('child_sram', 'write', address, 4)
                struct.pack_into('<I', self.child_sram, address, child)
                self.edges_used += 1
            address = self.node_address(parent_id) + 16
            self.transfer('node_sram', 'write', address, 8)
            struct.pack_into('<IHH', self.node_sram, address, start, len(children), int(node['player'] == -1))
            self.nodes[parent_id]['children'] = list(children)

    def lookup_children(self, parent_id, node=None):
        node = self.read_node(parent_id) if node is None else node
        count = node['children_count']
        if not count:
            return []
        self.count('cam_searches')
        self._record('cam', 'search', parent_id, 0, 0, self.config['cam_search_cycles'])
        if parent_id in self.cam:
            self.count('cam_hits')
            header = node['cache_header']
        else:
            self.count('cam_misses')
            while len(self.free_rows) < count:
                victim = self.cache_fifo.popleft()
                header, rows, children = self.cam.pop(victim)
                self.transfer('node_sram', 'read', self.config['cache_offset'] + header * 16, 16)
                for row in rows:
                    self._record('cam', 'invalidate', row, 0, 0, self.config['cam_row_write_cycles'])
                    self.free_rows.append(row)
                self.count('cam_evicted_rows', len(rows))
                self.free_headers.append(header)
            rows = []
            children = []
            for index in range(count):
                address = (node['children_start'] + index) * 4
                self.transfer('child_sram', 'read', address, 4)
                child = struct.unpack_from('<I', self.child_sram, address)[0]
                row = self.free_rows.popleft()
                rows.append(row)
                children.append(child)
                self._record('cam', 'fill', row, 8, 0, self.config['cam_row_write_cycles'])
            header = self.free_headers.popleft()
            address = self.config['cache_offset'] + header * 16
            self.transfer('node_sram', 'write', address, 16)
            struct.pack_into('<IIII', self.node_sram, address, parent_id, rows[0], count, 1)
            flags_address = self.node_address(parent_id) + 20
            self.transfer('node_sram', 'write', flags_address, 4)
            struct.pack_into('<HH', self.node_sram, flags_address, count,
                             (header << 1) | int(node['player'] == -1))
            self.cam[parent_id] = (header, rows, children)
            self.cache_fifo.append(parent_id)
            self.count('cam_filled_rows', count)
            self.cam_high_water = max(self.cam_high_water, self.config['cam_entries'] - len(self.free_rows))
            self.count('cam_searches')
            self._record('cam', 'search_after_fill', parent_id, 0, 0, self.config['cam_search_cycles'])
        address = self.config['cache_offset'] + header * 16
        self.transfer('node_sram', 'read', address, 16)
        stored_parent, first_row, stored_count, valid = struct.unpack_from('<IIII', self.node_sram, address)
        if (stored_parent, stored_count, valid) != (parent_id, count, 1):
            raise RuntimeError('CAM header does not describe the matched child list')
        expected_rows = [(first_row + index) % self.config['cam_entries'] for index in range(count)]
        if self.cam[parent_id][1] != expected_rows:
            raise RuntimeError('CAM FIFO rows are not in child-list order')
        children = self.cam[parent_id][2]
        self.count('cam_output_ids', count)
        self._record('cam', 'output', parent_id, 4 * count, 0, count * self.config['cam_output_cycles'])
        return list(children)

    def reset_path(self):
        if self.path_depth:
            raise RuntimeError('Previous path has not been consumed')

    def check_path_room(self):
        if self.path_depth >= self.config['path_entries']:
            raise MemoryError('path capacity exceeded')

    def push_path(self, node_id):
        self.check_path_room()
        self._node_fields(node_id)
        address = self.path_depth * 4
        self.transfer('node_sram', 'write', address, 4)
        struct.pack_into('<I', self.node_sram, address, node_id)
        self.path_depth += 1
        self.path_high_water = max(self.path_high_water, self.path_depth)

    def pop_path(self):
        if not self.path_depth:
            raise MemoryError('Cannot pop an empty path')
        address = (self.path_depth - 1) * 4
        self.transfer('node_sram', 'read', address, 4)
        node_id = struct.unpack_from('<I', self.node_sram, address)[0]
        self.path_depth -= 1
        return node_id

    def stage_candidate(self, child_id, child):
        address = self.config['stats_offset']
        self.transfer('node_sram', 'write', address, 16)
        struct.pack_into('<IId', self.node_sram, address, child_id, child['visits'], child['value'])
        self.transfer('node_sram', 'read', address, 16)
        self.count('candidate_checks')

    def update_stats(self, node_id, visits, value):
        self._node_fields(node_id)
        if not 0 <= visits < 2**32 or not math.isfinite(value):
            raise OverflowError('Node statistics are outside the reference representation')
        address = self.node_address(node_id)
        self.transfer('node_sram', 'write', address, 12)
        struct.pack_into('<Id', self.node_sram, address, visits, value)
        self.nodes[node_id]['visits'] = visits
        self.nodes[node_id]['value'] = value

    def summary(self):
        result = {'config': dict(self.config), 'nodes_used': self.nodes_used,
            'edges_used': self.edges_used, 'node_bytes_used': self.nodes_used * self.config['node_stride'],
            'scratch_bytes_reserved': self.config['node_base'], 'child_bytes_used': self.edges_used * 4,
            'path_high_water': self.path_high_water, 'path_entries_used': self.path_depth,
            'cam_high_water': self.cam_high_water, 'cam_rows_used': self.config['cam_entries'] - len(self.free_rows),
            'operations': dict(self.operations), 'phase_cycles': dict(self.phase_cycles),
            'phase_operations': {phase: dict(counts) for phase, counts in self.phase_operations.items()},
            'schedule_sha256': self.schedule_hash.hexdigest(),
            'last_completion_cycle': self.cursor,
            'functional_memory': 'packed metadata and boards; host node dict is an observation mirror',
            'physical_status': 'uncalibrated timing; binary64 arithmetic and cache/control circuitry not synthesized',
        }
        if self.capture_trace:
            result['transactions'] = self.transactions
        return result

    def complete_neural(self):
        schedule = self.neural.schedule
        self.count('rollout_operations')
        for name, count in schedule['operations'].items():
            self.count(name if name.startswith('node_sram_') else 'neural_' + name, count)
        self._record('neural', 'execute_template', self.config['neural_base'],
                     self.config['neural_bytes'], 0, schedule['cycles'])
        indices = self.neural.last_state['lut_indices']
        self.schedule_hash.update(f"neural|{schedule['schedule_sha256']}|{indices}\n".encode())
        if self.capture_trace:
            self.transactions[-1]['template_sha256'] = schedule['schedule_sha256']
            self.transactions[-1]['lut_indices'] = list(indices)
