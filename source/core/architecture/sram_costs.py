# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import hashlib
import json
import math
from numbers import Integral
from pathlib import Path


def load_sram_profile(name):
    if name == 'reference':
        return None
    profiles = json.loads(Path(__file__).with_name('sram_characterization.json').read_text())
    if name.startswith('cacti_22nm_s1_'):
        from core.architecture.board_sizing import memory_characterization
        profiles = memory_characterization()['sram']
    if name not in profiles:
        raise ValueError(f'Unknown memory_profile: {name}')
    profile = profiles[name]
    macro = profile['macro']
    if (macro['technology_nm'] != 22 or profile['clock_mhz'] != 500
            or macro['banks'] != 1 or macro['word_bytes'] != 4
            or macro['capacity_bytes'] != profile['bank_bytes']
            or profile['scaling'] != {'source_node_nm': 22, 'target_node_nm': 22, 'factor': 1, 'applications': 0}):
        raise ValueError('Incompatible SRAM characterization or duplicate technology scaling')
    cycles = math.ceil(max(macro['access_ns'], macro['cycle_ns']) / 2)
    if cycles != profile['macro_service_cycles']:
        raise ValueError('SRAM service timing conflicts with CACTI output')
    profile['sram_word_cycles'] = cycles + profile['routing_cycles']
    profile['profile_sha256'] = hashlib.sha256(json.dumps(profile, sort_keys=True,
                                                        allow_nan=False).encode()).hexdigest()
    profile['name'] = name
    return profile


def sram_accounting(profile, operations, cycles):
    if isinstance(cycles, bool) or not isinstance(cycles, Integral) or cycles <= 0:
        raise ValueError('Elapsed simulation cycles must be a positive integer')
    macro = profile['macro']
    latency_us = cycles / profile['clock_mhz']
    pools = {}
    for pool, banks in profile['banks'].items():
        counts = {action: operations.get(pool + '_' + action + '_words', 0)
                  for action in ('read', 'write')}
        if any(isinstance(n, bool) or not isinstance(n, Integral) or n < 0 for n in counts.values()):
            raise ValueError('SRAM access counts must be nonnegative integers')
        dynamic = sum(counts[action] * macro[action + '_energy_nj'] for action in counts)
        # All installed macros leak for the complete modeled search, including
        # idle neural/control phases. No unmodeled power gating is assumed.
        leakage = banks * macro['leakage_mw'] * latency_us
        pools[pool] = {'banks': banks, 'capacity_bytes': banks * profile['bank_bytes'],
            'read_words': int(counts['read']), 'write_words': int(counts['write']),
            'dynamic_energy_nj': dynamic, 'leakage_energy_nj': leakage,
            'area_mm2': banks * macro['area_mm2']}
    dynamic = sum(pool['dynamic_energy_nj'] for pool in pools.values())
    leakage = sum(pool['leakage_energy_nj'] for pool in pools.values())
    return {'status': 'partial_sram_tool_estimate', 'profile': profile['name'],
        'profile_sha256': profile['profile_sha256'], 'source': profile['source'],
        'pools': pools, 'latency_us': latency_us,
        'dynamic_energy_nj': dynamic, 'leakage_energy_nj': leakage,
        'energy_uj': (dynamic + leakage) / 1000,
        'average_power_mw': (dynamic + leakage) / latency_us,
        'area_mm2': sum(pool['area_mm2'] for pool in pools.values()),
        'excluded': ['bank selection and chip routing', 'CAM and CIM arrays',
                     'converters, digital datapaths, and controllers',
                     'clock distribution, chip I/O, and weight programming'],
        'calibration': 'CACTI ITRS analytical estimate; no foundry macro or silicon validation'}
