# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Explicit closest-report estimates for reviewed single-child controller geometry.
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path

ASSUMPTIONS = Path(__file__).with_name('controller_estimates.json')


def estimate_policy():
    data = ASSUMPTIONS.read_bytes()
    policy = json.loads(data)
    if policy['profile'] != 'single_child_controller_report_proxies_v1':
        raise ValueError('Unknown controller estimate policy')
    if policy['nominal_multiplier'] != 1.25 or policy['sensitivity_multipliers'] != [1.0, 1.25, 2.0]:
        raise ValueError('Controller allowance differs from reviewed scenarios')
    return policy | {'sha256': hashlib.sha256(data).hexdigest()}


def controller_estimate(instance, record, neural, memory):
    policy = estimate_policy()
    scope = policy['scope']
    eligible = (record is not None and instance in policy['owners'] and
        memory.get('policy') == 'evaluate_root_then_single_untried_child_v1' and
        memory.get('tree_update_timing_profile') == 'single_child_serial_services_v1' and
        neural['board_size'] == scope['board_size'] and neural['hidden_size'] == scope['hidden_size'] and
        neural['input_size'] in scope['input_sizes'] and
        all(memory.get(key) == scope[key] for key in ('cam_entries', 'node_sram_bytes', 'child_sram_bytes', 'neural_bytes')))
    if not eligible:
        return None
    return {'profile': policy['profile'], 'sha256': policy['sha256'],
        'multiplier': policy['nominal_multiplier'], 'reference_parameters': record['parameters'],
        'reference_native_65nm_area_um2': record['area']['cell_um2'],
        'reference_native_65nm_power': record['power'], 'reference_reports': record['reports'],
        'method': policy['method'], 'basis': policy['owners'][instance],
        'allowance_basis': policy['allowance_basis'], 'sensitivity_status': policy['sensitivity_status'],
        'status': policy['status']}
