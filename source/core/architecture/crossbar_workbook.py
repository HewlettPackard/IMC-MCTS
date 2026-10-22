# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Explicit 22 nm area equations from the preserved mentor workbook candidate.
# SPDX-License-Identifier: MIT
import hashlib
import json
import math
from pathlib import Path

from core.architecture.sram_costs import load_sram_profile
from core.architecture.analog_readout import BUFFERED, readout_inventory
from core.architecture.digital_costs import digital_accounting
from core.architecture.peripheral_costs import peripheral_components
from core.architecture.component_inventory import attach_inventory

ROOT=Path(__file__).resolve().parents[2]
SOURCES=ROOT/'p03_experiments/p15_workbook_models/p01_sources'
WORKBOOK_SHA256='bce447d0a6f2e74a2b51062bfc4e5683061479814ff417171f887ea75615f3d0'
PROVENANCE=ROOT/'p03_experiments/p16_cost_recovery/p01_sources/workbook_provenance.json'


def workbook_source():
    record=json.loads((SOURCES/'workbook_cells.json').read_text())
    if record['source_sha256']!=WORKBOOK_SHA256 or hashlib.sha256((SOURCES/'crossbar_reference.xlsx').read_bytes()).hexdigest()!=WORKBOOK_SHA256:
        raise ValueError('Crossbar workbook identity changed')
    provenance=json.loads(PROVENANCE.read_text())
    if provenance['source_sha256']!=WORKBOOK_SHA256: raise ValueError('Recovered workbook provenance does not match')
    record['identity_status']=provenance['identity_status']
    record['recovery']=provenance
    return record


def reference_crossbar(size):
    if type(size) is not int or not 1<=size<=4096: raise ValueError('Crossbar side must be an integer from 1 to 4096')
    record=workbook_source(); cells=record['cells']['New_Architecture']
    v=lambda cell: cells[cell]['value']
    # Preserve the sheet's differential pair, temporal drive and sequential-area boundary.
    array=2*size**2*v('C14')
    analog_drivers=size*v('C26')*v('C27')
    digital_drivers=size*v('D28')
    integrators=size*(v('C40')+v('C43')+v('C45'))
    comparators=size*v('C52')
    routing=2*size*0.1*math.sqrt(array)+10*0.1*math.sqrt(integrators/array)*array  # D60
    slices=v('C65')/v('C66')
    parts={'differential_cell_pair':array,'analog_temporal_drivers':analog_drivers,
        'digital_temporal_drivers':digital_drivers,'integrators':integrators,
        'sequential_comparators':comparators,'analog_routing':routing}
    # The saved totals mix comparator area with a different ADC's energy.
    # This reference consistently uses the sequential-comparator columns.
    energies={
        'differential_cell_pair':(size/v('C13'))**2*v('O22'),
        'analog_temporal_drivers':size/v('C13')*v('O30'),
        'digital_temporal_drivers':size/v('C13')*v('P31'),
        'integrators':size/v('C13')*v('O46'),
        'sequential_comparators':size/v('C13')*v('O53')}
    energy=slices*(energies['differential_cell_pair']+energies['analog_temporal_drivers']+energies['integrators'])+energies['digital_temporal_drivers']+energies['sequential_comparators']
    return {'profile':'mentor_workbook_22nm_reference_v1','size':size,'source_sha256':WORKBOOK_SHA256,
        'source_status':record['identity_status'],'source_sheet':'New_Architecture','technology_nm':22,
        'parts_um2':parts,'crossbar_pair_area_um2':sum(parts.values()),
        'mvm_unit_area_um2':slices*(array+analog_drivers+integrators+routing)+digital_drivers+comparators,
        'weight_bits':v('C65'),'cell_bits':v('C66'),'weight_slices':slices,
        'formula_cells':['C15','D30','D31','C46','C53','D60','D64','D67'],
        'sequential_reference':{'parts_energy_pj':energies,'mvm_energy_pj':energy,
            'read_duration_ns':v('C9'),'average_power_mw':energy/v('C9'),
            'source_cells':['O22','O30','P31','O46','O53','C9'],
            'method':'Literal workbook energy terms, fixed temporal precision and proportional column counts; no active-chip adoption',
            'status':'Reference estimate only; array current, analog operating conditions, wires and physical timing unvalidated'},
        'reconciliation':{'area_converter':'C53 sequential comparators','saved_energy_converter':'Q53 alternative ADC',
            'saved_256_mvm_energy_pj':v('P67'),'sequential_256_mvm_energy_pj':v('P67')-v('Q53')+v('O53'),
            'standby_split_status':'Not adopted: O41 multiplies an already timed C9 by C3 again; O47+O48 does not reproduce O46',
            'digital_driver_scaling':'16 to 22 nm already applied in D28 and P31; no additional 65 to 22 conversion'},
        'boundary':'Workbook reference architecture; not the active simulator chip or its shared-ADC bank.',
        'energy_status':'Sequential reference energy uses matching area/energy circuitry; active binary/shared-ADC costs remain uncharacterized.'}


def component_estimates(profile, memory_profile, memory_config=None):
    record=workbook_source(); cell_area=record['cells']['New_Architecture']['C14']['value']
    readout=readout_inventory(profile)
    digital=digital_accounting(profile,memory_config)
    rows=profile['array_rows']; cols=profile['array_columns']
    outputs=cols//(profile['weight_slices']*profile['sign_branches'])
    arrays=math.ceil(profile['input_size']/rows)*math.ceil(profile['hidden_size']/outputs)+math.ceil(profile['hidden_size']/rows)*math.ceil(profile['outputs']/outputs)
    sram=load_sram_profile(memory_profile)
    if (memory_config or {}).get('hardware_profile') == 'board_sized_s1_v1':
        for pool,banks in sram['banks'].items():
            if banks*sram['bank_bytes'] != memory_config[pool+'_bytes']:
                raise ValueError('SRAM cost profile differs from the installed board hardware')
    components=[]
    for pool,banks in sram['banks'].items():
        components.append({'id':pool,'component':pool.replace('_',' ').title(),'count':banks,
            'area_um2':banks*sram['macro']['area_mm2']*1e6,'status':'Native 22 nm CACTI',
            'source':'core/architecture/sram_characterization.json','service_cycles':sram['macro_service_cycles'],
            'service_unit':'32-bit word; routing separate'})
    peripherals, cim_cost, peripheral_model = peripheral_components(profile,memory_profile,memory_config,record,arrays)
    components.append({'id':'cim_arrays','component':'CIM cell arrays','count':arrays,'area_um2':arrays*rows*cols*cell_area,
        'status':'22 nm workbook cell-area estimate; periphery excluded','source':'New_Architecture!C14',
        'cost_model':cim_cost,'service_cycles':profile['service_cycles']['array_settle'],'service_unit':'array settle',
        'rows':rows,'columns':cols,'cell_area_um2':cell_area,
        'accounting':'Physical tile columns already contain both signs and weight slices; no extra factor of two.'})
    components.extend(digital['components'])
    for row in digital['components']: row['id'] = row['instance']
    components.extend(peripherals)
    subtotal = sum(row['area_um2'] or 0 for row in components)
    components.append({'id':'physical_overhead','component':'Clock distribution and physical routing allowance','count':1,
        'area_um2':subtotal*peripheral_model['assumptions']['layout_area_fraction']['value'],
        'source':'New_Architecture!D97; peripheral_assumptions.json',
        'status':'15% area allowance and 10% digital-energy allowance; not an extracted physical network',
        'scope':'core','service_unit':'included in the assumed clock and routing schedule'})
    for identifier,name,reason in [
        ('chip_io','Chip I/O, pads and host interface','Outside preloaded-core execution; host transfers, pads, ESD and package costs are not estimated'),
        ('weight_programming','Weight programming interface','Outside preloaded-core execution; programming drivers, write/verify and preload costs are not estimated')]:
        components.append({'id':identifier,'component':name,'count':None,'area_um2':None,'status':reason,'source':None,'scope':'outside_core'})
    attach_inventory(components,profile,memory_config,digital['area_conversion']['factor'])
    if (memory_config or {}).get('hardware_profile') == 'board_sized_s1_v1':
        for row in components:
            if row['id'] in ('node_sram','child_sram'):
                row['capacity_bytes'] = row['count']*sram['bank_bytes']
                row['bank_bytes'] = sram['bank_bytes']
                row['source'] = 'core/architecture/board_memory_characterization.json'
                row['children'][0]['component'] = f"{sram['bank_bytes']//1024} KiB SRAM banks"
    cells=record['cells']['New_Architecture']
    capacitor_scenario={'source':'New_Architecture!C42 / C41 (integrator capacitor, not a characterized hold cell)',
        'capacitance_ff':cells['C42']['value'],'density_ff_per_um2':cells['C41']['value'],
        'installed_capacitor_area_um2':readout['installed_analog_samples']*cells['C42']['value']/cells['C41']['value'],
        'status':'Capacitor-only reference, not an additional area charge. The column-hold estimate includes these capacitors with switches and amplifiers when installed; physical compatibility is unvalidated.'}
    return {'profile':'component_ppa_inventory_v5','technology_nm':22,'components':components,'digital':digital,
        'known_area_mm2':sum(row['area_um2'] or 0 for row in components)/1e6,'whole_chip_area_mm2':None,
        'whole_chip_energy_uj':None,'whole_chip_power_mw':None,'source_sha256':WORKBOOK_SHA256,
        'source_status':record['identity_status'],'scaling_applications':0,'peripheral_model':peripheral_model,
        'resource_requirements':{'installed_arrays':arrays,'physical_row_terminals':arrays*rows,
            'physical_column_terminals':arrays*cols,'peak_active_rows':profile['active_rows'],
            'active_arrays':1,'shared_adc_lanes':profile['adc_lanes'],'shared_sample_hold_lanes':profile['adc_lanes'],
            'maximum_column_groups':math.ceil(cols/profile['adc_lanes']),
            'analog_retention':('All mapped columns captured before shared conversion; array disabled after capture' if readout['profile']==BUFFERED else 'Existing RTL keeps the selected array driven throughout all column groups; analog operating point uncharacterized'),
            'digital_ownership':digital['accounting']+' Buffered capture control is included inside the buffered neural parent.',
            'go_state_and_rules':'Host Go rules and metadata have no cost or storage allocation in the validated placement core'},
        'boundary':'Modeled core area: SRAM, CIM, matching digital parents, CAM/analog proxies and physical allowance. Host I/O and programming excluded; no full-chip signoff.',
        'analog_readout':readout,'readout_activity':profile.get('readout_activity'),
        'column_capacitor_scenario':capacitor_scenario,
        'reference_crossbar':reference_crossbar(256)}
