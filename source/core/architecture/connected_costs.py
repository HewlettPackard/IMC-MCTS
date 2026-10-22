# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Native connected-path owners. Target scaling is applied by the caller once.
# SPDX-License-Identifier: MIT
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CHARACTERIZATION = Path(__file__).with_name('connected_characterization.json')
COST_PROFILE = 'ucb16_adc32_buffered_estimate_v6'
PROFILE = 'connected_native65_p08_resize_v1'
LANES = tuple('u_ucb_' + str(i).zfill(2) for i in range(16))
_NUMBER = r'([-+\d.eE]+)'


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path(name):
    path = ROOT / name
    if Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('Unsafe connected evidence path: ' + name)
    return path


def _one(text, pattern, label):
    values = re.findall(pattern, text, re.M)
    if len(values) != 1:
        raise ValueError('Expected one connected report row: ' + label)
    numbers = tuple(float(value) for value in values[0]) if isinstance(values[0], tuple) else (float(values[0]),)
    if any(not math.isfinite(value) or value < 0 for value in numbers):
        raise ValueError('Invalid connected report value: ' + label)
    return numbers


def _power(text, instance, design=None):
    suffix = r'\s+\(' + re.escape(design) + r'[^)]*\)' if design else ''
    switch, internal, leak, total = _one(text, r'^\s*' + re.escape(instance) + suffix +
        r'\s+' + _NUMBER + r'\s+' + _NUMBER + r'\s+' + _NUMBER + r'\s+' + _NUMBER + r'\s+[\d.]+\s*$', instance)
    # Native report headers explicitly declare dynamic mW and leakage uW.
    return {'switching_mw': switch, 'internal_mw': internal,
        'dynamic_mw': switch + internal, 'leakage_mw': leak / 1000,
        'reported_total_mw': total}


def _parse_payload(configuration):
    tops = {}; parts = {}; report_root = configuration['report_root']
    for top in ('imc_selection_path', 'imc_readout_path'):
        folder = report_root + '/after_resize/' + top + '/'
        area_name = folder + 'area.rpt'; hierarchy_name = folder + 'area_hier.rpt'
        power_name = folder + 'vectorless_power.rpt'
        area_text = _path(area_name).read_text(); hierarchy = _path(hierarchy_name).read_text()
        power_text = _path(power_name).read_text()
        if ('Dynamic Power Units = 1mW' not in power_text or
                'Leakage Power Units = 1uW' not in power_text or
                'Global Operating Voltage = 1' not in power_text):
            raise ValueError('Unexpected native connected power units or voltage')
        area = _one(area_text, r'^\s*Total cell area:\s*' + _NUMBER + r'\s*$', top)[0]
        tops[top] = {'area_um2': area, **_power(power_text, top),
            'source': area_name, 'power_source': power_name, 'top': top}
        if top == 'imc_readout_path':
            parts['u_nn'] = tops[top] | {'id': 'u_nn', 'instance': top,
                'ownership': 'Inclusive connected readout; result banks, staging and eight accumulator banks included once'}
            continue
        for index, lane in enumerate(LANES):
            instance = 'u_batch/genblk1[' + str(index) + '].u_score'
            lane_area = _one(hierarchy, r'^' + re.escape(instance) + r'\s+' + _NUMBER + r'\s+', instance)[0]
            # Power report prints immediate scorers relative to u_batch.
            powers = _power(power_text, 'genblk1[' + str(index) + '].u_score', 'imc_ucb_score_overlap')
            parts[lane] = {'id': lane, 'area_um2': lane_area, **powers,
                'source': hierarchy_name, 'power_source': power_name, 'top': top,
                'instance': instance, 'ownership': 'Inclusive scorer; divider, sqrt, log and value children included once'}
        wrapper = {'id': 'u_sel', 'source': area_name, 'power_source': power_name,
            'top': top, 'instance': top + '/exclusive_wrapper',
            'ownership': 'Exclusive connected selection wrapper: inclusive top minus sixteen inclusive scorers; retains report rounding remainder'}
        for key in ('area_um2', 'switching_mw', 'internal_mw', 'dynamic_mw', 'leakage_mw', 'reported_total_mw'):
            wrapper[key] = tops[top][key] - math.fsum(parts[lane][key] for lane in LANES)
            if wrapper[key] < 0 or not math.isfinite(wrapper[key]):
                raise ValueError('Negative connected selection residual: ' + key)
        parts['u_sel'] = wrapper
    review = json.loads(_path(report_root + '/REVIEW.json').read_text())
    provenance = json.loads(_path(report_root + '/run_provenance.json').read_text())
    if review['closure'] != 'UNVERIFIED' or review['equivalence'] != 'UNVERIFIED' or review['power'] != 'VECTORLESS_ONLY':
        raise ValueError('Changed original connected acceptance boundary')
    timing = {}
    for top in tops:
        record = review['cases'][top]['stages']['after_resize']
        if record['closure'] != 'PASS' or any(record['qor_violation_counts'].values()):
            raise ValueError('Connected final-stage physical reports do not pass')
        if record['cell_area_um2'] != tops[top]['area_um2']:
            raise ValueError('Connected area and review disagree')
        timing[top] = {'setup_slack_ns': record['setup_slack_ns'],
            'hold_slack_ns': record['hold_slack_ns'], 'constraint_counts': record['qor_violation_counts'],
            'other_report_entries': record['violation_counts'], 'warnings': record['timing_warnings']}
    metadata = {'profile': PROFILE, 'cost_profile': COST_PROFILE, 'source_node_nm': 65,
        'voltage_v': 1.0, 'temperature_c': 25, 'clock_period_ns': 2.0, 'clock_mhz': 500,
        'corner': 'tt_typical_max_1p00v_25c', 'stage': 'after_resize',
        'current_stage_constraint_closure': 'PASS', 'original_packet_acceptance': review['closure'],
        'missing_native_evidence': review['missing_native_evidence'], 'equivalence': review['equivalence'],
        'power': review['power'], 'power_scenario': 'all_elapsed_vectorless',
        'power_scenario_boundary': 'Active and idle coefficients both equal native vectorless dynamic power over actual elapsed time; no inferred clock-only split or workload annotation',
        'source_repository': configuration['source_repository'], 'source_commit': provenance['git_commit'],
        'result_commit': configuration['result_commit'], 'library_sha256': provenance['library_sha256'],
        'tool_version': review['tool_version']['native_version'], 'timing_by_top': timing,
        'scope': 'Connected digital header-response selection and ADC-code readout regions; residual full-core control, offset correction, memories and analog circuits are separate',
        'report_precision': 'Native top area uses six decimal places. Child area and hierarchy power are report-rounded; exclusive wrapper absorbs subtraction remainder. No extra child sum or clock floor is added.',
        'physical_implementation': 'UNVERIFIED: no CTS, routed layout or physical signoff',
        'target22_status': 'Native65 inputs only; caller applies reviewed target22 assumptions once; no delay scaling'}
    for part in parts.values():
        part['active_dynamic_mw'] = part['dynamic_mw']
        part['idle_dynamic_mw'] = part['dynamic_mw']
        part['power_method'] = 'all_elapsed_vectorless_no_clock_split'
    return {'native_tops': tops, 'parts': parts, 'metadata': metadata}


def load_characterization():
    data = json.loads(CHARACTERIZATION.read_text())
    if data['schema_version'] != 1 or data['profile'] != PROFILE or data['cost_profile'] != COST_PROFILE:
        raise ValueError('Unsupported connected characterization')
    for name, digest in data['source_files'].items():
        if _digest(_path(name)) != digest:
            raise ValueError('Connected evidence hash mismatch: ' + name)
    report_root = data['configuration']['report_root']
    artifacts = dict((line.split(None, 1)[1].lstrip('*'), line.split(None, 1)[0])
        for line in _path(report_root + '/ARTIFACT_SHA256SUMS').read_text().splitlines() if line.strip())
    native = dict((line.split(None, 1)[1].lstrip('*'), line.split(None, 1)[0])
        for line in _path(report_root + '/NATIVE_SHA256SUMS').read_text().splitlines() if line.strip())
    for name, digest in data['source_files'].items():
        relative = str(Path(name).relative_to(report_root))
        original = ('p00_previous/p00_baseline/p00_source/p06_connected_paths/source_provenance.json'
            if relative == 'source_provenance.json' else relative)
        if relative not in ('ARTIFACT_SHA256SUMS', 'NATIVE_SHA256SUMS') and artifacts.get(original) != digest:
            raise ValueError('Connected evidence differs from original artifact manifest: ' + name)
        if relative.startswith('after_resize/') and native.get(relative) != digest:
            raise ValueError('Connected evidence differs from original native manifest: ' + name)
    bindings = json.loads(_path(report_root + '/source_provenance.json').read_text())['rtl_source_sha256']
    if bindings != data['rtl_source_sha256']:
        raise ValueError('Connected RTL bindings differ from returned provenance')
    for name, digest in data['rtl_source_sha256'].items():
        if _digest(_path(name)) != digest:
            raise ValueError('Connected RTL binding hash mismatch: ' + name)
    parsed = _parse_payload(data['configuration'])
    if any(data[key] != parsed[key] for key in parsed):
        raise ValueError('Connected characterization differs from native reports')
    result = deepcopy(data)
    result['sha256'] = _digest(CHARACTERIZATION)
    return result


@lru_cache(maxsize=1)
def _loaded():
    # Evidence is immutable during one process. New source adoption restarts
    # Studio; explicit load_characterization() remains a fresh integrity check.
    return load_characterization()


def metadata():
    data = _loaded()
    return data['metadata'] | {'characterization_sha256': data['sha256']}


def native_parts():
    return deepcopy(_loaded()['parts'])


_catalog = json.loads(CHARACTERIZATION.read_text())
SOURCE_FILES = [Path(__file__).resolve(), CHARACTERIZATION] + [_path(name) for name in sorted(set(_catalog['source_files']) | set(_catalog['rtl_source_sha256']))]
