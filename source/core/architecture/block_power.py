# Report-based block power with explicit activity and target-process assumptions.
# SPDX-License-Identifier: MIT
import csv
import hashlib
import json
import math
from pathlib import Path
import re

from core.architecture.block_activity import BLOCKS, PROFILE, activity_record
from core.architecture.cost_ledger import scaling_policy
from core.architecture.digital_costs import CHARACTERIZATION, power_mw

ROOT = Path(__file__).resolve().parents[2]
TABLE = Path(__file__).with_name('block_power_coefficients.json')
POWER_FIELDS = ('active_dynamic_mw', 'idle_dynamic_mw', 'leakage_mw')
METHOD = 'vectorless_clock_floor_v1'


def report_power(path):
    text = Path(path).read_text()
    unit = re.search(r'Dynamic Power Units\s*=\s*([\d.eE+-]+)\s*([munp]?W)\b', text)
    clock = re.search(r'^\s*clock_network\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s', text, re.M)
    if unit is None or clock is None:
        raise ValueError('Missing clock power or dynamic power units')
    factor = float(unit[1]) * {'W':1000, 'mW':1, 'uW':.001, 'nW':1e-6, 'pW':1e-9}[unit[2]]
    values = {'dynamic_mw':power_mw(text, 'Total Dynamic Power'),
        'clock_dynamic_mw':(float(clock[1]) + float(clock[2])) * factor,
        'leakage_mw':power_mw(text, 'Cell Leakage Power')}
    if any(not math.isfinite(value) or value < 0 for value in values.values()) or values['clock_dynamic_mw'] > values['dynamic_mw']:
        raise ValueError('Invalid clock/dynamic report split')
    return values


def load_power_table(catalog_sha256):
    data = TABLE.read_bytes()
    table = json.loads(data)
    if table['schema_version'] != 2 or table['activity_profile'] != PROFILE or table['method'] != METHOD:
        raise ValueError('Unsupported block power activity model')
    if table['catalog_sha256'] != catalog_sha256:
        raise ValueError('Block power table belongs to a different synthesis catalog')
    catalog_data = CHARACTERIZATION.read_bytes()
    if hashlib.sha256(catalog_data).hexdigest() != catalog_sha256:
        raise ValueError('Block power catalog identity changed')
    catalog = json.loads(catalog_data)
    expected = {'node_nm': 65, 'clock_mhz': 500, 'voltage_v': 1.0,
        'temperature_c': 25, 'corner': 'tt_typical_max_1p00v_25c'}
    if table['operating_point'] != expected:
        raise ValueError('Block power operating point differs from native reports')
    for case, row in table['cases'].items():
        native = catalog['cases'][case]
        if row['parameters'] != native['parameters'] or native['rtl_status'] != 'matches_active_sources':
            raise ValueError('Power configuration differs from active synthesis: ' + case)
        powers = row['powers_mw']
        if set(powers) != set(POWER_FIELDS):
            raise ValueError('Unknown or missing power coefficients: ' + case)
        for value in powers.values():
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                raise ValueError('Invalid block power coefficient: ' + case)
        if any(value is not None for value in powers.values()):
            evidence = row.get('evidence')
            report = native['reports']['power_vectorless.rpt']
            expected_sources = {report:catalog['source_files'][report]}
            if not evidence or evidence.get('method') != METHOD or evidence.get('sources') != expected_sources:
                raise ValueError('Missing matching report evidence: ' + case)
            for name, sha in evidence['sources'].items():
                path = (ROOT / name).resolve()
                if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                    raise ValueError('Block power report source changed: ' + case)
            values = report_power(ROOT / report)
            expected_powers = {'active_dynamic_mw':values['dynamic_mw'],
                'idle_dynamic_mw':values['clock_dynamic_mw'], 'leakage_mw':values['leakage_mw']}
            if powers != expected_powers or row['report_power_mw'] != values:
                raise ValueError('Power coefficients differ from source report: ' + case)
    table['sha256'] = hashlib.sha256(data).hexdigest()
    return table


def block_energy(active_cycles, idle_cycles, powers, clock_mhz):
    if any(type(n) is not int or n < 0 for n in (active_cycles, idle_cycles)):
        raise ValueError('Activity cycles must be nonnegative integers')
    if type(clock_mhz) not in (int, float) or not math.isfinite(clock_mhz) or clock_mhz <= 0:
        raise ValueError('Clock must be finite and positive')
    if set(powers) != set(POWER_FIELDS):
        raise ValueError('Missing or unknown power coefficient')
    for value in powers.values():
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError('Power coefficients must be finite and nonnegative')
    active_us = active_cycles / clock_mhz; idle_us = idle_cycles / clock_mhz
    elapsed_us = active_us + idle_us
    dynamic = None if any(powers[k] is None for k in POWER_FIELDS[:2]) else (
        powers['active_dynamic_mw'] * active_us + powers['idle_dynamic_mw'] * idle_us)
    leakage = None if powers['leakage_mw'] is None else powers['leakage_mw'] * elapsed_us
    energy = None if dynamic is None or leakage is None else dynamic + leakage
    return {'active_cycles': active_cycles, 'idle_cycles': idle_cycles,
        'active_us': active_us, 'idle_us': idle_us, 'elapsed_us': elapsed_us,
        'dynamic_energy_nj': dynamic, 'leakage_energy_nj': leakage, 'energy_nj': energy,
        'average_power_mw': None if energy is None or elapsed_us == 0 else energy / elapsed_us}


def block_power_accounting(digital, cycles, active, table=None):
    table = load_power_table(digital['profile_sha256']) if table is None else table
    if table['catalog_sha256'] != digital['profile_sha256']:
        raise ValueError('Prepared power table belongs to a different synthesis catalog')
    policy = scaling_policy()
    activity = None if active is None else activity_record(dict(active), cycles)
    rows = []
    for component in digital['components']:
        instance = component['instance']; case = component['case']
        entry = table['cases'].get(case)
        compatible = entry is not None and component['native_65nm_area_um2'] is not None and (
            entry['parameters'] == component['parameters_required'])
        powers = dict.fromkeys(POWER_FIELDS) if not compatible else entry['powers_mw']
        proxy = component.get('report_proxy')
        if proxy is not None:
            if entry is None or entry['parameters'] != proxy['reference_parameters']:
                raise ValueError('Controller proxy has no matching reference power report')
            powers = {key: value*proxy['multiplier'] if value is not None else None for key,value in entry['powers_mw'].items()}
            compatible = True
        row = {'instance': instance, 'case': case, 'source_node_nm': 65, 'powers_mw': dict(powers),
            'active_cycles': None, 'idle_cycles': None, 'active_us': None, 'idle_us': None,
            'elapsed_us': cycles / table['operating_point']['clock_mhz'],
            'dynamic_energy_nj': None, 'leakage_energy_nj': None, 'energy_nj': None, 'average_power_mw': None,
            'status': 'missing_activity' if activity is None else 'missing_configuration' if not compatible else 'pending_calibration'}
        if activity is not None:
            row.update(block_energy(**activity['blocks'][instance], powers=powers,
                clock_mhz=table['operating_point']['clock_mhz']))
        if row['energy_nj'] is not None: row['status'] = 'vectorless_activity_estimate'
        if proxy is not None:
            row.update(report_proxy=proxy,status='controller_report_proxy_estimate' if row['energy_nj'] is not None else row['status'])
        row['method'] = METHOD
        if proxy is not None: row['method'] += '_with_controller_report_proxy'
        row['report_source'] = '' if not compatible else next(iter(entry['evidence']['sources']))
        row['target_22nm_dynamic_energy_nj'] = None if row['dynamic_energy_nj'] is None else row['dynamic_energy_nj'] * policy['dynamic_energy']['factor']
        row['target_22nm_leakage_energy_nj'] = None if row['leakage_energy_nj'] is None else row['leakage_energy_nj'] * policy['leakage']['factor']
        row['target_22nm_energy_nj'] = None if row['energy_nj'] is None else row['target_22nm_dynamic_energy_nj'] + row['target_22nm_leakage_energy_nj']
        row['target_22nm_power_mw'] = None if row['target_22nm_energy_nj'] is None or row['elapsed_us'] == 0 else row['target_22nm_energy_nj'] / row['elapsed_us']
        rows.append(row)
    if len(rows) != len(BLOCKS) or {row['instance'] for row in rows} != set(BLOCKS):
        raise ValueError('Power model requires each installed block exactly once')
    totals = {key: None if any(row[key] is None for row in rows) else sum(row[key] for row in rows)
        for key in ('dynamic_energy_nj', 'leakage_energy_nj', 'energy_nj',
            'target_22nm_dynamic_energy_nj', 'target_22nm_leakage_energy_nj', 'target_22nm_energy_nj')}
    duration = cycles / table['operating_point']['clock_mhz']
    return {'profile': table['profile'], 'table_sha256': table['sha256'], 'activity': activity,
        'source_node_nm': 65, 'operating_point': table['operating_point'], 'components': rows, **totals,
        'average_power_mw': None if totals['energy_nj'] is None or duration == 0 else totals['energy_nj'] / duration,
        'target_22nm_power_mw': None if totals['target_22nm_energy_nj'] is None or duration == 0 else totals['target_22nm_energy_nj'] / duration,
        'target_policy': policy['profile'], 'method': METHOD,
        'status': 'partial_or_missing_activity' if totals['energy_nj'] is None else 'vectorless_activity_estimate',
        'boundary': 'Installed digital parents once. Assumed active switching and clock-only idle; target dynamic uses geometric C and V squared. Target leakage carries native65 power as an unvalidated proxy. Array, memory and periphery are separate.'}


def power_source_files(catalog_sha256):
    table = load_power_table(catalog_sha256)
    sources = {name for row in table['cases'].values() if row.get('evidence')
        for name in row['evidence']['sources']}
    return [TABLE] + [ROOT / name for name in sorted(sources)]


def write_power_csv(path, power):
    rows = [{key: value for key, value in row.items() if key != 'powers_mw'} |
        row['powers_mw'] | {'clock_mhz': power['operating_point']['clock_mhz'],
            'table_sha256': power['table_sha256'], 'target_policy':power['target_policy'],
            'target_leakage_status':'native65_power_proxy'} for row in power['components']]
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
