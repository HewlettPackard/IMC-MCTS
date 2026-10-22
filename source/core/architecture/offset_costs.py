# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Preserve reusable costs, and leave changed hardware explicitly unpriced.
# SPDX-License-Identifier: MIT
from copy import copy, deepcopy
import hashlib
import json
from types import SimpleNamespace

from core.architecture.parallel_selection_costs import parallel_costs


def offset_costs(model):
    if model.neural.profile['model'] != 'ucb4_offset_w8_cell8_adc12_v1':
        raise ValueError('Offset cost inventory requires the offset execution model')
    reference = copy(model)
    reference.neural = SimpleNamespace(profile=model.reference_neural_profile)
    prior = parallel_costs(reference)
    unchanged = {'node_sram','child_sram','cam_macro','u_sel','u_upd','top_level_glue',
                 'u_node_router','u_child_router','u_ucb_a','u_ucb_b','u_ucb_c','u_ucb_d'}
    rows = [deepcopy(r) for r in prior['ledger']['components'] if r['id'] in unchanged]
    descriptions = [
        ('cim_arrays','8-bit 1T1M cell arrays',2,'256 cell levels and custom array layout need device characterization'),
        ('row_drivers','Binary row drivers',259,'Custom rows, load and cell-current range need driver characterization'),
        ('sample_hold','12-bit readout sample/hold lanes',8,'Noise, settling and hold error must support the new conversion precision'),
        ('adc_lanes','12-bit ADC lanes',8,'No matching 12-bit ADC area, energy or achieved ENOB evidence'),
        ('analog_mux','Column mux and references',99,'99 installed column routes and eight reference lanes; new range/accuracy need characterization'),
        ('u_nn','Neural digital logic with offset correction',1,'96 accumulators, 128-bit ADC register and input-sum/correction logic need a compatible controller estimate'),
        ('physical_overhead','Clock distribution and physical allowance',1,'15% policy retained; full base area and changed clock/wire costs are unavailable')]
    for identifier,name,count,reason in descriptions:
        rows.append({'id':identifier,'component':name,'count':count,'scope':'core','counted':True,
            'area_um2':None,'energy_uj':None,'average_power_mw':None,'dynamic_energy_uj':None,
            'leakage_energy_uj':None,'status':'uncharacterized_offset_hardware',
            'source':'offset_encoding.json; dimensions and resource counts from executed mapping',
            'assumptions':reason,'children':[]})
    by_id = {r['id']:r for r in rows}
    for array in model.neural.profile['arrays']:
        by_id['cim_arrays']['children'].append(array | {
            'id':'cim_arrays/layer_'+str(array['layer']), 'component':'Layer '+str(array['layer'])+' array',
            'area_um2':None,'counted':False,'status':'Part of unestimated parent; excluded from known totals'})
    by_id['u_nn']['resources'] = model.neural.schedule['resources']
    known_area = sum(r['area_um2'] or 0 for r in rows)/1e6
    known_energy = sum(r['energy_uj'] or 0 for r in rows)
    sources = prior['ledger']['source_identities'] | {'offset_contract':model.rollout_spec['sha256'],
        'offset_schedule':model.neural.schedule['schedule_sha256']}
    return {'profile':model.rollout_spec['profile'], 'status':'partial_costs_changed_hardware_uncharacterized',
        'components':rows,'known_area_mm2':known_area,'known_energy_uj':known_energy,
        'known_average_power_mw':known_energy/(model.cycles/500000) if model.cycles else None,
        'missing_area':[r['component'] for r in rows if r['area_um2'] is None],
        'missing_energy':[r['component'] for r in rows if r['energy_uj'] is None],
        'core_area_mm2':None,'core_energy_uj':None,'core_average_power_mw':None,
        'whole_chip_area_mm2':None,'whole_chip_energy_uj':None,'whole_chip_power_mw':None,
        'boundary':model.rollout_spec['boundary'], 'source_identities':sources,
        'sha256':hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest(),
        'reuse_policy':'Only unchanged digital/CAM/SRAM owners are priced, using this workload activity and elapsed time; native65 leakage and prior engineering proxies remain assumptions',
        'excluded':['Host rules and metadata','Host I/O and pads','Weight programming and preload']}
