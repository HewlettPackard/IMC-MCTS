# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Board-size selection is an installed hardware choice, separate from run quotas.
# SPDX-License-Identifier: MIT
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from core.simulator.tree_memory import memory_config
from core.simulator.incremental_memory import incremental_config
from py_sst_cpp.components.board_config import BoardSize, get_board_config

PROFILE = 'board_sized_s1_v1'
TABLE = Path(__file__).with_name('board_sizing.json')
CHARACTERIZATION = Path(__file__).with_name('board_memory_characterization.json')
ROOT = Path(__file__).resolve().parents[2]


def board_table():
    data = json.loads(TABLE.read_text())
    if data['profile'] != PROFILE:
        raise ValueError('Unknown board-sizing table')
    return data


def board_hardware(board):
    if type(board) is not int:
        raise ValueError('Board size must be an integer')
    row = next((r for r in board_table()['boards'] if r['board_size'] == board), None)
    if row is None:
        raise ValueError('Unsupported board size')
    if row['iterations']['high'] != 2*row['iterations']['medium']:
        raise ValueError('High budget must be twice medium')
    return deepcopy(row)


def memory_profile_name(board, name):
    board_hardware(board)
    choices = {base: f'cacti_22nm_s1_b{board}_{flavor}'
        for flavor in ('hp', 'lstp') for base in (f'cacti_22nm_{flavor}', f'cacti_22nm_s1_b{board}_{flavor}')}
    if name not in choices:
        raise ValueError('SRAM characterization does not match the selected board')
    return choices[name]


def memory_characterization():
    record = json.loads(CHARACTERIZATION.read_text())
    for name, digest in record['source_files'].items():
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Board-sized memory evidence changed: '+name)
    return record


def sized_memory(profile, limits=None, rules='placement', incremental=True):
    row = board_hardware(profile['board_size'])
    shape = SimpleNamespace(**vars(get_board_config(BoardSize(profile['board_size']))))
    shape.node_sram_kb = row['node_sram_kib']
    shape.children_sram_kb = row['child_sram_kib']
    shape.cam_entries = row['cam_entries']
    config = memory_config(shape, neural_scratch_bytes=profile['storage_bytes'])
    # Go can pass and capture. Reserve its full move bound before any following
    # partition, even if this search starts partway through a game.
    entries = (2 if rules == 'legacy_go' else 1)*shape.board_size**2+1
    extra = 4*(entries-config['path_storage_entries'])
    for key in ('working_offset', 'stats_offset', 'cache_offset', 'neural_base', 'node_base'):
        config[key] += extra
    config.update(path_entries=entries, path_storage_entries=entries,
        node_capacity=(config['node_sram_bytes']-config['node_base'])//config['node_stride'],
        hardware_profile=PROFILE, sram_bank_bytes=row['sram_bank_kib']*1024,
        node_sram_banks=row['node_sram_kib']//row['sram_bank_kib'],
        child_sram_banks=row['child_sram_kib']//row['sram_bank_kib'],
        hardware_table_sha256=hashlib.sha256(TABLE.read_bytes()).hexdigest())
    config.update(sram_word_cycles=2,cam_search_cycles=3,cam_row_write_cycles=3,cam_output_cycles=3,
        ucb_cycles=225,cam_row_bits=65,cam_payload_bits=64)
    capacity = incremental_config(config)
    for name, key in [('nodes', 'node_capacity'), ('edges', 'edge_capacity'), ('path_entries', 'path_entries')]:
        if name not in (limits or {}):
            continue
        value = limits[name]
        if type(value) is not int or not 0 < value <= capacity[key]:
            raise ValueError(name+' quota exceeds the selected board hardware')
        config[key] = value
    if set(limits or {})-{'nodes', 'edges', 'path_entries'}:
        raise ValueError('Unknown memory allocation quota')
    return incremental_config(config) if incremental else config
