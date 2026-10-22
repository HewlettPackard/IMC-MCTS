# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Eight analog lanes plus explicit changed-neural-controller cost ownership.
# SPDX-License-Identifier: MIT
from copy import copy, deepcopy
import hashlib
import json
from types import SimpleNamespace

from core.architecture.complete_costs import cost_configuration, prepare_costs
from core.architecture.component_inventory import included
from core.architecture.crossbar_workbook import component_estimates
from core.architecture.cost_ledger import cost_ledger
from core.architecture.parallel_selection_costs import parallel_costs


def prepare_eight_adc_costs(model,memory_profile='cacti_22nm_lstp'):
    return {'configuration':cost_configuration(memory_profile,model.neural.profile,model.memory.config),
        'reference':prepare_costs(memory_profile,model.reference_neural_profile,model.serial_memory_config),
        'estimates':component_estimates(model.neural.profile,memory_profile,model.memory.config)}


def eight_adc_costs(model,memory_profile='cacti_22nm_lstp',neural_multiplier=None,prepared=None):
    spec=model.rollout_spec
    neural_multiplier=spec['neural_parent_multiplier'] if neural_multiplier is None else neural_multiplier
    if neural_multiplier not in spec['neural_parent_sensitivity']: raise ValueError('Unreviewed neural allowance')
    if model.neural.profile['adc_lanes']!=8 or model.neural.profile['readout']['profile']!='sustained_drive_v1':
        raise ValueError('Costs require eight ADCs with sustained drive')
    prepared=prepare_eight_adc_costs(model,memory_profile) if prepared is None else prepared
    if prepared['configuration']!=cost_configuration(memory_profile,model.neural.profile,model.memory.config):
        raise ValueError('Prepared costs belong to a different hardware configuration')
    # Borrow only source-checked per-parent reports. Activity/cycles are this run's.
    reference=copy(model); reference.neural=SimpleNamespace(profile=model.reference_neural_profile)
    prior=parallel_costs(reference,memory_profile,prepared=prepared['reference'])
    power=prior['block_power']; estimates=deepcopy(prepared['estimates'])
    owners={row['instance'] for row in power['components']}
    digital=[deepcopy(row) for row in prior['ledger']['components'] if row['id'] in owners]
    estimates['components']=[row for row in estimates['components'] if row['id'] not in owners|{'u_ucb'}]+digital
    estimates['digital']=deepcopy(prepared['reference']['digital'])
    neural=next(row for row in digital if row['id']=='u_nn')
    neural_power=next(row for row in power['components'] if row['instance']=='u_nn')
    proxy=neural.get('report_proxy')
    if proxy is None:
        # No compatible inherited controller proxy: never fill an unreviewed size.
        neural.update(area_um2=None,native_65nm_area_um2=None,native_65nm_power=None,timing=None,
            status='Eight-lane neural controller cost unavailable for this geometry',includes=[])
        neural_power['powers_mw']=dict.fromkeys(neural_power['powers_mw'])
        neural_power['status']='missing_eight_lane_controller_characterization'
        for key in ('dynamic_energy_nj','leakage_energy_nj','energy_nj','average_power_mw',
                    'target_22nm_dynamic_energy_nj','target_22nm_leakage_energy_nj',
                    'target_22nm_energy_nj','target_22nm_power_mw'):
            neural_power[key]=None
    else:
        factor=neural_multiplier/proxy['multiplier']
        neural['area_um2']*=factor
        neural_power['powers_mw']={k:v*factor for k,v in neural_power['powers_mw'].items()}
        for key in ('dynamic_energy_nj','leakage_energy_nj','energy_nj','average_power_mw',
                    'target_22nm_dynamic_energy_nj','target_22nm_leakage_energy_nj',
                    'target_22nm_energy_nj','target_22nm_power_mw'):
            neural_power[key]*=factor
        for row in (neural,neural_power):
            row['report_proxy'].update(profile=spec['profile'],sha256=spec['sha256'],multiplier=neural_multiplier,
                basis=spec['neural_parent_basis'],allowance_basis=spec['neural_parent_basis'])
        neural['status']='Eight-lane/163-input digital-controller engineering report proxy; not matching synthesis'
    neural['children'].append(included('Eight-lane ADC result handling','u_nn','adc8_control',
        ['64-bit ADC result register (40 bits more than reference)',
         'Up to eight valid lanes, including four-lane layer-two tail',
         'Two sequential 32-bit bus words per full group',
         'Eight ordered updates through the existing one-lane accumulator'],source='eight_adc.json; included in whole-parent neural estimate'))
    neural['adc_register_bits']=64
    mux=next(row for row in estimates['components'] if row['id']=='analog_mux')
    mux['status']='One switched route per physical column; eight reference buffers and one shared bias budget. Source bias voltages retained.'
    physical=next(row for row in estimates['components'] if row['id']=='physical_overhead')
    fraction=estimates['peripheral_model']['assumptions']['layout_area_fraction']['value']
    physical['area_um2']=fraction*sum(row['area_um2'] or 0 for row in estimates['components'] if row['id']!='physical_overhead')
    estimates['known_area_mm2']=sum(row['area_um2'] or 0 for row in estimates['components'])/1e6
    for key in ('dynamic_energy_nj','leakage_energy_nj','energy_nj',
                'target_22nm_dynamic_energy_nj','target_22nm_leakage_energy_nj','target_22nm_energy_nj'):
        values=[row[key] for row in power['components']]
        power[key]=None if any(v is None for v in values) else sum(values)
    for key,energy in [('average_power_mw','energy_nj'),('target_22nm_power_mw','target_22nm_energy_nj')]:
        power[key]=None if power[energy] is None else power[energy]/(model.cycles/500)
    ledger=cost_ledger(estimates,prior['sram'],power,model.memory.operations)
    ledger['profile']=spec['profile']
    ledger['source_identities'].update(parallel_selection=model.selection_spec['sha256'],
        selector_multiplier=model.selection_spec['selection_parent_multiplier'],
        eight_adc_rollout=spec['sha256'],neural_multiplier=neural_multiplier)
    ledger['sha256']=hashlib.sha256(json.dumps(ledger['source_identities'],sort_keys=True).encode()).hexdigest()
    ledger['architecture_status']=spec['timing_status']
    ledger['neural_controller_cost_status']=spec['neural_parent_basis']
    return {'status':'experimental_core_estimate_with_proxies','ledger':ledger,'block_power':power,
        'sram':prior['sram'],'whole_chip':{'area_mm2':None,'energy_uj':None,'power_mw':None},
        'boundary':spec['boundary'],'timing':spec['timing_status']}
