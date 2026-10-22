# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Reuse source-checked per-unit costs, then explicitly price four UCB instances.
# SPDX-License-Identifier: MIT
from copy import deepcopy
import hashlib
import json

from core.architecture.block_power import block_power_accounting, block_energy
from core.architecture.complete_costs import prepare_costs, cost_configuration
from core.architecture.component_inventory import included
from core.architecture.cost_ledger import cost_ledger, scaling_policy
from core.architecture.parallel_selection import LANES
from core.architecture.sram_costs import sram_accounting


def parallel_costs(model, memory_profile='cacti_22nm_lstp', selector_multiplier=1.25, prepared=None):
    spec = model.selection_spec
    if selector_multiplier not in spec['selection_parent_sensitivity']:
        raise ValueError('Unreviewed selector allowance')
    prepared = prepare_costs(memory_profile, model.neural.profile, model.serial_memory_config) if prepared is None else prepared
    if prepared['configuration'] != cost_configuration(memory_profile, model.neural.profile, model.serial_memory_config):
        raise ValueError('Prepared costs belong to a different hardware configuration')
    if model.cycles <= 0: raise ValueError('Workload power requires positive elapsed cycles')
    # Only this adapter consumes the one-instance report catalog; final owners are expanded below.
    estimates = deepcopy(prepared['estimates'])
    activity = dict(model.block_active_cycles)
    activity['u_ucb'] = activity[LANES[0]]
    for lane in LANES: activity.pop(lane)
    power = deepcopy(block_power_accounting(prepared['digital'], model.cycles, activity, prepared['power_table']))
    policy = scaling_policy()
    original = next(row for row in power['components'] if row['instance'] == 'u_ucb')
    power['components'] = [row for row in power['components'] if row['instance'] != 'u_ucb']
    for lane in LANES:
        row = deepcopy(original)
        row['instance'] = lane
        row.update(block_energy(model.block_active_cycles[lane], model.cycles-model.block_active_cycles[lane], row['powers_mw'], 500))
        row['target_22nm_dynamic_energy_nj'] = row['dynamic_energy_nj'] * policy['dynamic_energy']['factor']
        row['target_22nm_leakage_energy_nj'] = row['leakage_energy_nj'] * policy['leakage']['factor']
        row['target_22nm_energy_nj'] = row['target_22nm_dynamic_energy_nj'] + row['target_22nm_leakage_energy_nj']
        row['target_22nm_power_mw'] = row['target_22nm_energy_nj'] / row['elapsed_us']
        power['components'].append(row)
    unit = next(row for row in estimates['components'] if row.get('id') == 'u_ucb')
    estimates['components'] = [row for row in estimates['components'] if row.get('id') != 'u_ucb']
    for lane in LANES:
        row = json.loads(json.dumps(unit).replace('"u_ucb', '"' + lane))
        row['component'] = 'UCB arithmetic lane ' + lane[-1].upper()
        row['instance'] = lane
        estimates['components'].append(row)
    selector = next(row for row in estimates['components'] if row.get('id') == 'u_sel')
    selector_power = next(row for row in power['components'] if row['instance'] == 'u_sel')
    if selector.get('report_proxy') is None:
        # Other geometries retain missing costs rather than borrowing the 9x9 controller.
        selector['status'] += '; four-lane control estimate unavailable for this geometry'
    else:
        factor = selector_multiplier / selector['report_proxy']['multiplier']
        selector['area_um2'] *= factor
        selector_power['powers_mw'] = {name:value*factor for name,value in selector_power['powers_mw'].items()}
        for key in ('dynamic_energy_nj', 'leakage_energy_nj', 'energy_nj', 'average_power_mw',
                    'target_22nm_dynamic_energy_nj', 'target_22nm_leakage_energy_nj', 'target_22nm_energy_nj', 'target_22nm_power_mw'):
            selector_power[key] *= factor
        for row in (selector, selector_power):
            row['report_proxy'].update(profile=spec['profile'], sha256=spec['sha256'], multiplier=selector_multiplier,
                basis=spec['selection_parent_basis'])
        selector['status'] = spec['cost_status']
        selector['candidate_register_bits'] = spec['candidate_register_bits']
        selector['extra_control_owner'] = 'Operand slots, imc_ucb_batch wrapper, ordered batch merge and incremental selector; excludes the four UCB arithmetic parents'
    selector['children'].append(included('Four-candidate register buffer', 'u_sel', 'operand_slots',
        ['Four 32-bit child IDs', 'Four 32-bit visit counts', 'Four 64-bit Q17 value sums'],
        source='parallel_selection.json; engineering report proxy, not separate synthesis'))
    selector['children'].append(included('Batch dispatch and ordered reduction', 'u_sel', 'batch_control',
        ['Shared parent visits and exploration', 'Lane launch, completion and error handling',
         'Captured child IDs and arithmetic results', 'First-wins ordered comparison', 'Held result and reset'],
        source='rtl_synthesis/p05_parallel_selection/p00_rtl/imc_ucb_batch.sv'))
    # SRAM remains physically reserved, but no longer stores candidate operands.
    def mark_reserved(rows):
        for row in rows:
            if row['component'] == 'Candidate statistics scratch':
                row['component'] = 'Unused candidate statistics slot (16 bytes retained in SRAM)'
            mark_reserved(row.get('children', []))
    mark_reserved(estimates['components'])
    physical = next(row for row in estimates['components'] if row['id'] == 'physical_overhead')
    # Preserve the existing 15% physical-area allowance on the complete expanded inventory.
    allowance = estimates['peripheral_model']['assumptions']['layout_area_fraction']['value']
    physical['area_um2'] = allowance * sum(row['area_um2'] or 0 for row in estimates['components'] if row['id'] != 'physical_overhead')
    estimates['known_area_mm2'] = sum(row['area_um2'] or 0 for row in estimates['components']) / 1e6
    power['activity'] = model.activity_record()
    for key in ('dynamic_energy_nj', 'leakage_energy_nj', 'energy_nj',
                'target_22nm_dynamic_energy_nj', 'target_22nm_leakage_energy_nj', 'target_22nm_energy_nj'):
        values = [row[key] for row in power['components']]
        power[key] = None if any(value is None for value in values) else sum(values)
    power['average_power_mw'] = None if power['energy_nj'] is None else power['energy_nj'] / (model.cycles/500)
    power['target_22nm_power_mw'] = None if power['target_22nm_energy_nj'] is None else power['target_22nm_energy_nj'] / (model.cycles/500)
    power['boundary'] = model.activity_record()['boundary'] + ' Same source-specific 65-to-22 conversion and native65 leakage proxy.'
    sram = sram_accounting(prepared['sram'], model.memory.operations, model.cycles)
    ledger = cost_ledger(estimates, sram, power, model.memory.operations)
    ledger['profile'] = 'imc_22nm_ucb4_register_batch_v1'
    ledger['source_identities']['parallel_selection'] = spec['sha256']
    ledger['source_identities']['selector_multiplier'] = selector_multiplier
    ledger['sha256'] = hashlib.sha256(json.dumps(ledger['source_identities'],sort_keys=True).encode()).hexdigest()
    ledger['architecture_status'] = spec['timing_status']
    ledger['selection_controller_cost_status'] = spec['selection_parent_basis']
    return {'status':'experimental_core_estimate_with_proxies', 'ledger':ledger, 'block_power':power, 'sram':sram,
        'whole_chip':{'area_mm2':None,'energy_uj':None,'power_mw':None},
        'timing':'Selection batch primitive checked; complete single-child control remains a service model at assumed 500 MHz'}
