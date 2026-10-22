# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# One versioned ledger for installed area and workload energy coverage.
# SPDX-License-Identifier: MIT
import hashlib
import json
import math
from pathlib import Path

from core.architecture.peripheral_costs import peripheral_energy

POLICY = Path(__file__).with_name('technology_scaling.json')


def scaling_policy():
    policy = json.loads(POLICY.read_text())
    if policy['target_node_nm'] != 22 or policy['clock_mhz'] != 500:
        raise ValueError('Cost policy does not match the supported node/clock')
    if policy['area']['applications'] != 1 or not math.isclose(policy['area']['factor'], (22/65)**2, rel_tol=0, abs_tol=1e-16):
        raise ValueError('Digital area must receive one geometric conversion')
    expected_dynamic = (22/65) * (0.8/1.0)**2
    if (policy['profile'] != 'imc_22nm_costs_v2' or
            policy['dynamic_energy']['method'] != 'geometric_capacitance_voltage_squared' or
            policy['dynamic_energy']['applications'] != 1 or
            not math.isclose(policy['dynamic_energy']['factor'], expected_dynamic, rel_tol=0, abs_tol=1e-16) or
            policy['dynamic_energy']['capacitance_ratio'] != 22/65 or
            policy['digital_source']['voltage_v'] != 1.0 or policy['digital_target']['voltage_v'] != 0.8 or
            policy['leakage']['method'] != 'native65_power_proxy' or
            policy['leakage']['applications'] != 1 or policy['leakage']['factor'] != 1.0):
        raise ValueError('Power scaling differs from the reviewed approximation')
    if policy['legacy_power']['adopted'] or policy['delay']['physical_closure']:
        raise ValueError('Unsupported legacy power or physical timing claim')
    return policy


def cost_ledger(estimates, sram, block_power=None, operations=None):
    policy = scaling_policy()
    operations = {} if operations is None else operations
    cycles = round(sram['latency_us']*500)
    components = []
    for index, original in enumerate(estimates['components']):
        row = dict(original)
        row['id'] = row.get('id', row.get('instance', 'component_' + str(index)))
        row['dynamic_energy_uj'] = None
        row['leakage_energy_uj'] = None
        row['energy_uj'] = None
        row['average_power_mw'] = None
        row['active_cycles'] = None
        row['active_us'] = None
        row['energy_status'] = 'Missing compatible workload and operating-point characterization'
        for pool, costs in sram['pools'].items():
            if row['component'] == pool.replace('_', ' ').title():
                row['dynamic_energy_uj'] = costs['dynamic_energy_nj']/1000
                row['leakage_energy_uj'] = costs['leakage_energy_nj']/1000
                row['energy_uj'] = row['dynamic_energy_uj'] + row['leakage_energy_uj']
                row['energy_status'] = 'Native 22 nm CACTI accesses plus all-bank leakage over elapsed time'
                row['active_cycles'] = (costs['read_words']+costs['write_words'])*row['service_cycles']
        if row.get('native_65nm_power') is not None:
            row['energy_status'] = '65 nm vectorless report retained; matched activity and 22 nm conversion pending'
        if block_power is not None:
            match = next((item for item in block_power['components'] if item['instance'] == row['id']), None)
            if match is not None:
                row['block_power'] = match
                row['active_cycles'] = match['active_cycles']
                row['energy_status'] = 'Report-based activity estimate: ' + match['status'] + '; 22 nm dynamic scaling, native65 leakage proxy'
                if match['target_22nm_energy_nj'] is not None:
                    row['dynamic_energy_uj'] = match['target_22nm_dynamic_energy_nj']/1000
                    row['leakage_energy_uj'] = match['target_22nm_leakage_energy_nj']/1000
                    row['energy_uj'] = row['dynamic_energy_uj'] + row['leakage_energy_uj']
        row.update(peripheral_energy(row, operations, cycles))
        if row['id'] == 'physical_overhead':
            fraction = estimates['peripheral_model']['assumptions']['clock_wire_power_fraction']['value']
            energy = sum(item['target_22nm_energy_nj'] or 0 for item in block_power['components'])/1000 if block_power else 0
            available = block_power is not None and any(item['target_22nm_energy_nj'] is not None for item in block_power['components'])
            row.update(dynamic_energy_uj=None,leakage_energy_uj=None,energy_uj=fraction*energy if available else None,
                active_cycles=cycles,energy_status='10% of available digital energy reserved for physical clock and wire overhead; no added schedule cycles')
        if row.get('scope') == 'outside_core': row['energy_status'] = 'Excluded from the preloaded-core boundary; not a zero cost'
        if row['energy_uj'] is not None: row['average_power_mw'] = row['energy_uj']*1000/sram['latency_us']
        if row['active_cycles'] is not None: row['active_us'] = row['active_cycles']/500
        components.append(row)
    ids = [row['id'] for row in components]
    if len(ids) != len(set(ids)):
        raise ValueError('Installed component appears twice in the cost ledger')
    core = [row for row in components if row.get('scope','core') == 'core']
    missing_area = [row['component'] for row in core if row['area_um2'] is None]
    missing_energy = [row['component'] for row in core if row['energy_uj'] is None]
    known_area = sum(row['area_um2'] or 0 for row in components)/1e6
    known_energy = sum(row['energy_uj'] or 0 for row in components)
    if not math.isclose(known_area, estimates['known_area_mm2'], abs_tol=1e-12):
        raise ValueError('Component inventory and cost ledger area disagree')
    digital_energy = sum(row['target_22nm_energy_nj'] or 0 for row in block_power['components'])/1000 if block_power is not None else 0
    peripheral_energy_total = sum(row['energy_uj'] or 0 for row in core if row.get('cost_model') is not None or row['id']=='physical_overhead')
    if not math.isclose(known_energy, sram['energy_uj'] + digital_energy + peripheral_energy_total, abs_tol=1e-12):
        raise ValueError('Known energy must reconcile to its characterized sources')
    identities = {'policy': hashlib.sha256(POLICY.read_bytes()).hexdigest(),
        'digital': estimates['digital']['profile_sha256'], 'sram': sram['profile_sha256'],
        'workbook': estimates['source_sha256']}
    identities.update(peripherals=estimates['peripheral_model']['sha256'], peripheral_tools=estimates['peripheral_model']['tool_record_sha256'])
    proxy_ids=[row['id'] for row in core if row.get('report_proxy')]
    if proxy_ids: identities['controller_estimates']=estimates['digital']['controller_estimate_sha256']
    if block_power is not None: identities['block_power'] = block_power['table_sha256']
    return {'profile': 'imc_22nm_components_v4' if proxy_ids else 'imc_22nm_components_v3',
        'sha256': hashlib.sha256(json.dumps(identities, sort_keys=True).encode()).hexdigest(),
        'source_identities': identities, 'technology_nm': 22, 'policy': policy,
        'status': 'core_estimate_with_proxies_and_allowances', 'components': components,
        'peripheral_model':estimates['peripheral_model'], 'peripheral_energy_uj':peripheral_energy_total,
        'known_area_mm2': known_area, 'known_energy_uj': known_energy,
        'known_average_power_mw': known_energy*1000/sram['latency_us'],
        'modeled_core_area_mm2': None if missing_area else known_area,
        'modeled_core_energy_uj': None if missing_energy else known_energy,
        'whole_chip_area_mm2': None, 'whole_chip_energy_uj': None, 'whole_chip_power_mw': None,
        'excluded_components':[row['component'] for row in components if row.get('scope') == 'outside_core'],
        'missing_area': missing_area, 'missing_energy': missing_energy,
        **({'controller_report_proxy_components':proxy_ids} if proxy_ids else {}),
        'operating_point_status': 'Source-specific conditions; a common 22 nm physical operating point is unvalidated',
        'boundary': 'Installed owners counted once. SRAM, digital reports, CAM/analog proxies and physical allowances form the modeled-core estimate. Nested costs are included in parents. Host I/O and programming are excluded. Cycles overlap; timing and analog accuracy remain unvalidated.'}


def ledger_fields(costs):
    ledger = costs.get('ledger')
    if ledger is None:
        return {name: None for name in ('cost_model_profile', 'cost_model_sha256',
            'known_energy_uj', 'known_average_power_mw', 'missing_area_components',
            'missing_energy_components', 'operating_point_status')}
    return {'cost_model_profile': ledger['profile'], 'cost_model_sha256': ledger['sha256'],
        'known_energy_uj': ledger['known_energy_uj'],
        'known_average_power_mw': ledger['known_average_power_mw'],
        'missing_area_components': ';'.join(ledger['missing_area']),
        'missing_energy_components': ';'.join(ledger['missing_energy']),
        'operating_point_status': ledger['operating_point_status']}
