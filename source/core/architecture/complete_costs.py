# Costs for the complete core retain explicit coverage and native process nodes.
# SPDX-License-Identifier: MIT
from copy import deepcopy
from core.architecture.sram_costs import load_sram_profile, sram_accounting
from core.architecture.digital_costs import digital_accounting, digital_activity
from core.architecture.crossbar_workbook import component_estimates
from core.architecture.cost_ledger import cost_ledger, scaling_policy
from core.architecture.block_power import block_power_accounting, load_power_table


def cost_configuration(memory_profile, neural_profile, memory_config):
    # These two display labels are attached after a search is saved. Neither
    # changes geometry, services, precision, capacity or cost assumptions.
    neural={k:v for k,v in neural_profile.items() if k not in ('controller_profile','timing_status')}
    return deepcopy((memory_profile,neural,memory_config))


def prepare_costs(memory_profile, neural_profile, memory_config):
    # Run-local static inputs. Every loader still verifies its raw evidence.
    digital=digital_accounting(neural_profile,memory_config)
    return {'configuration':cost_configuration(memory_profile,neural_profile,memory_config),
        'sram':load_sram_profile(memory_profile),'digital':digital,
        'power_table':load_power_table(digital['profile_sha256']),
        'estimates':component_estimates(neural_profile,memory_profile,memory_config)}


def complete_costs(memory_profile, operations, cycles, neural_profile=None, memory_config=None, phase_cycles=None, block_active_cycles=None, prepared=None):
    if prepared is not None and prepared['configuration'] != cost_configuration(memory_profile,neural_profile,memory_config):
        raise ValueError('Prepared costs belong to a different hardware configuration')
    profile=load_sram_profile(memory_profile) if prepared is None else prepared['sram']
    if profile is None: raise ValueError('Complete-core cost reporting requires a named native 22 nm SRAM profile')
    digital=None if neural_profile is None else (digital_accounting(neural_profile,memory_config,operations,phase_cycles)
        if prepared is None else digital_activity(prepared['digital'],operations,phase_cycles))
    costs = {
        'status':'partial_sram_only' if digital is None else 'partial_module_area_and_sram_energy',
        'whole_chip':{'area_mm2':None,'power_mw':None,'energy_uj':None},
        'sram':sram_accounting(profile,operations,cycles),
        'digital':digital,
        'timing_warning':digital['timing_status'] if digital is not None and digital['timing_violations'] else None,
        'coverage':[
            {'component':'SRAM macros','status':'CACTI analytical estimate','source_node_nm':22,'target_node_nm':22,'scaling_applications':0},
            {'component':'Digital modules','status':'Configuration required' if digital is None else digital['status'],
                'source_node_nm':65,'target_node_nm':22,'scaling_applications':0 if digital is None else 1},
            {'component':'CAM macro','status':'Functional interface verified; physical macro costs missing'},
            {'component':'CIM arrays and analog periphery','status':'Ideal cell-code responses; device, ADC, sample/hold, reference and driver costs unresolved'},
            {'component':'Clock, routing, I/O and weight programming','status':'Physical implementation and activity missing'}],
        'digital_conversion':None if digital is None else {
            'area':digital['area_conversion'],'power':digital['power_conversion']},
        'boundary':'Core execution from preloaded SRAM/LUT and programmed arrays through the last backpropagation. Preload and off-chip work excluded.',
        'timing':'Controller cycles at an assumed 500 MHz, with specified ideal services; physical clock closure unvalidated',
    }
    if neural_profile is not None:
        costs['block_power'] = block_power_accounting(digital,cycles,block_active_cycles,
            table=None if prepared is None else prepared['power_table'])
        policy = scaling_policy()
        costs['status'] = 'partial_sram_and_digital_estimate'
        costs['digital_conversion']['power'] = {'policy':policy['profile'],
            'dynamic_energy':policy['dynamic_energy'], 'leakage':policy['leakage']}
        estimates = component_estimates(neural_profile, memory_profile, memory_config) if prepared is None else prepared['estimates']
        costs['ledger'] = cost_ledger(estimates, costs['sram'], costs['block_power'], operations)
        costs['status'] = 'core_estimate_with_proxies_and_allowances'
        costs['coverage'][2]['status'] = 'Native22 CACTI fully associative cache proxy; all-match routing uncharacterized'
        costs['coverage'][3]['status'] = 'Workbook primitives and native22 SAR proxy; mean activity and standby assumptions'
        costs['coverage'][4]['status'] = 'Physical area/energy allowance; host I/O and weight programming excluded'
    return costs if prepared is None else deepcopy(costs)
