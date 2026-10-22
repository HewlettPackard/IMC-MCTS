# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Approximate missing physical costs using pinned tools and workbook primitives.
# SPDX-License-Identifier: MIT
import hashlib
import json
import math
from pathlib import Path

from core.architecture.analog_readout import BUFFERED, column_groups
from core.architecture.component_inventory import included
from py_sst_cpp.components.board_config import BoardSize, get_board_config

ROOT = Path(__file__).resolve().parents[2]
ASSUMPTIONS = Path(__file__).with_name('peripheral_assumptions.json')


def peripheral_sources():
    policy = json.loads(ASSUMPTIONS.read_text())
    record = policy['tool_record']; path = ROOT/record['path']
    if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
        raise ValueError('Peripheral tool record changed')
    tools = json.loads(path.read_text())
    for name,digest in tools['source_files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Peripheral source changed: '+name)
    for name,row in policy['assumptions'].items():
        value = row['value']
        if isinstance(value,bool) or not math.isfinite(value) or (value <= 0 and not (name == 'adc_idle_fraction' and value == 0)):
            raise ValueError('Invalid peripheral assumption: '+name)
        if ('fraction' in row['unit'] or name in ('input_activity','mean_conductance')) and value > 1:
            raise ValueError('Invalid activity fraction: '+name)
    return policy, tools, [ASSUMPTIONS,path]+[ROOT/name for name in tools['source_files']]


def peripheral_components(profile, memory_profile, memory, workbook, arrays):
    policy, tools, sources = peripheral_sources()
    p = {name:row['value'] for name,row in policy['assumptions'].items()}
    cells = workbook['cells']['New_Architecture']; v = lambda key:cells[key]['value']
    adc_cells = workbook['cells']['ADC']; adc = tools['adc']
    rows = profile['array_rows']; cols = profile['array_columns']; lanes = profile['adc_lanes']
    if (profile['adc_bits'],profile['active_rows'],profile['cell_bits']) != (8,16,4):
        raise ValueError('Peripheral estimate requires the supported 8-bit ADC, 16-row, 4-bit-cell mapping')
    buffered = profile.get('readout',{}).get('profile') == BUFFERED
    period = 1000/profile['clock_mhz']; services = profile['service_cycles']
    physical_rows = arrays*rows; physical_cols = arrays*cols
    activity = p['input_activity']; mean_g = p['mean_conductance']
    read_v = v('L15'); ron = v('L14')*1e6
    if not math.isclose(adc['column_ohm'],ron/(profile['active_rows']*activity*mean_g)):
        raise ValueError('ADC probe does not match the assumed mean column resistance')
    # Integrate the actual serialized topology with explicit mean activity.
    bursts = drive_cycles = driver_energy = array_energy = hold_energy = hold_cycles = 0
    frontend_mw = p['frontend_bias_ua']*p['analog_supply_v']/1000
    sample_area = v('C42')/v('C41')+2*v('C26')+v('C40')
    sample_cap_pj = v('C42')*read_v**2/1000
    for inputs,outputs,bits in ((profile['input_size'],profile['hidden_size'],1),
                                (profile['hidden_size'],profile['outputs'],8)):
        per_array = cols//(profile['weight_slices']*profile['sign_branches'])
        for output in range(0,outputs,per_array):
            mapped_cols = min(per_array,outputs-output)*profile['weight_slices']*profile['sign_branches']
            groups = column_groups(mapped_cols,profile)
            on = services['drive']+services['array_settle']+(1 if buffered else groups[-1]['end_cycle'])
            for start in range(0,inputs,profile['active_rows']):
                active_rows = min(profile['active_rows'],inputs-start)
                for bit in range(bits):
                    bursts += 1; drive_cycles += on
                    capacitance_pj = active_rows*activity*cols*(v('O16')+v('O17'))*read_v**2/1000
                    current_pj = active_rows*activity*mapped_cols*mean_g/ron*read_v**2*on*period*1000
                    array_energy += capacitance_pj+current_pj
                    driver_energy += active_rows*(2*activity*v('O26')+v('P31')/v('C13')/v('C5'))
                    if buffered:
                        # Each column stays biased through its own sampling time.
                        hold_energy += sum(g['count']*(g['sample_cycle']+1)*period*frontend_mw*(1-v('U40')) for g in groups)
                        hold_energy += mapped_cols*sample_cap_pj
                        hold_cycles += groups[-1]['sample_cycle']+1
    def component(identifier, name, count, area, dynamic, standby, operation, active, service, unit, source, note, parts):
        return {'id':identifier,'component':name,'count':count,'area_um2':area,'source':source,
            'status':note,'scope':'core','cost_model':{'event_energy_pj':dynamic,'standby_mw':standby,
                'operation':operation,'cycles_per_event':active},
            'service_cycles':service,'service_unit':unit,
            'children':[included(label,identifier,i,subparts) for i,(label,subparts) in enumerate(parts)]}
    result = []
    entries = (memory or {}).get('cam_entries',get_board_config(BoardSize(profile['board_size'])).cam_entries)
    physical_entries = max(128,2**math.ceil(math.log2(entries)))
    flavor = 'hp' if memory_profile.endswith('_hp') else 'lstp'
    cam = tools['cam'].get(f'cam_{physical_entries}_{flavor}')
    if (memory or {}).get('hardware_profile') == 'board_sized_s1_v1' and cam is None:
        from core.architecture.board_sizing import memory_characterization
        cam = memory_characterization()['cam'].get(f'cam_{physical_entries}_{flavor}')
    row = component('cam_macro','CAM macro',1,None,0,0,'cam_searches',3,3,'request',
        None,'No compatible CAM proxy for this capacity',[
            ('Associative parent keys and validity',['Searchline drivers','CAM cells','Matchline precharge and sensing']),
            ('Child payload and row access',['32-bit child IDs','Row decoder and write drivers','Payload read and output wiring'])])
    row['logical_entries'] = entries; row['physical_entries'] = physical_entries
    if cam:
        row.update(area_um2=cam['area_um2'],source=cam['source'],
            status=f'CACTI native 22 nm proxy, {physical_entries} rows; 33-bit key/valid padded to 36 bits plus 32-bit payload. All-match interface is approximated.',
            tool_timing_ns=max(cam['access_ns'],cam['cycle_ns']))
        row['cost_model'] = {'cam':cam}
    else: row['cost_model'] = None
    result.append(row)
    result.append(component('row_drivers','Binary row drivers and row selection',physical_rows,
        physical_rows*(v('C26')*v('C27')+v('D28')/v('C5')),driver_energy/bursts,
        physical_rows*p['driver_idle_fraction']*(2*activity*v('O26')+v('P31')/v('C13')/v('C5'))/period,
        'neural_array_pulses',drive_cycles/bursts,services['drive'],'burst',
        'New_Architecture!C26:C28,D28,O26,P31',
        'Workbook driver budget: one per physical row; digital width reduced to one bit, analog switch budget retained. 5% standby allowance.',
        [('Row switches and drive',['One binary drive per row terminal','Analog voltage switches','Row selection and digital drive','Level shifting and isolation within the driver budget'])]))
    result.append(component('sample_hold','Sample-and-hold lanes',lanes,lanes*sample_area,
        frontend_mw*(1-v('U40'))*(services['sample_hold']+1+services['adc_group'])*period+sample_cap_pj,
        lanes*frontend_mw*v('U40'),'neural_adc_conversions',None,services['sample_hold'],'ADC group',
        'New_Architecture!C26,C40:C43,O40,U40',
        'Workbook capacitor, switch and amplifier proxy; acquisition plus conversion hold, 5% standby bias. Accuracy unvalidated.',
        [('Input conditioning',['Current-to-voltage amplifier','Capture switch','85 fF hold capacitor','Reset and buffer'])]))
    result.append(component('adc_lanes','8-bit ADC lanes',lanes,lanes*adc['area_um2'],adc['energy_pj'],
        lanes*p['adc_idle_fraction']*adc['energy_pj']/adc['latency_ns'],
        'neural_adc_conversions',None,services['adc_group'],'ADC group',policy['tool_record']['path'],
        'Native 22 nm NeuroSim SAR estimate; 9 ns model, 18 ns scheduled service. Default ADC standby allowance: 25% of active power; reference and S/H priced separately. This is an engineering assumption, not measured idle power.',
        [('SAR conversion',['Comparator','Internal capacitor DAC','SAR decision logic','Local conversion clock'])]))
    mux_count = physical_cols
    result.append(component('analog_mux','Reference and analog multiplexers',mux_count,
        mux_count*(2*v('C26')+v('D28')/v('C5'))+(lanes+1)*v('C40'),
        2*v('O26'),lanes*adc_cells['D9']['value']+p['reference_bias_mw'],
        'neural_adc_conversions',None,services['mux'],'ADC group',
        'New_Architecture!C26,C40,D28,O26,Q56; ADC!D9',
        'One switched route per physical column; three reference buffers and one shared bias budget. Source bias voltages retained.',
        [('Column selection',['Transmission gates','Column-select decode','Array-to-ADC routes']),
         ('Shared references',['ADC reference buffers','Common read/reference bias'])]))
    if buffered:
        result.append(component('column_hold','Analog column holding cells',physical_cols,physical_cols*sample_area,
            hold_energy/bursts,physical_cols*frontend_mw*v('U40'),'neural_array_pulses',hold_cycles/bursts,1,'parallel capture',
            'New_Architecture!C26,C40:C43,O40,U40',
            'Workbook front-end/capacitor/switch proxy at each column; active bias until sampling and 5% standby. Hold accuracy unvalidated.',
            [('Column sample banks',['Per-column conditioning amplifier','Capture/reset switches','85 fF storage per column','Output buffering'])]))
    cim = {'event_energy_pj':array_energy/bursts,'standby_mw':0,'operation':'neural_array_pulses',
        'cycles_per_event':drive_cycles/bursts,
        'method':'Workbook CV² plus V²/R over scheduled sustained drive; mean input and cell conductance fractions 0.5. Idle read bias off; no off-state device current modeled.'}
    return result, cim, {'profile':policy['profile'],'sha256':hashlib.sha256(ASSUMPTIONS.read_bytes()).hexdigest(),
        'tool_record_sha256':policy['tool_record']['sha256'],'assumptions':policy['assumptions'],
        'burst_template':{'bursts_per_inference':bursts,'drive_cycles_per_inference':drive_cycles},
        'boundary':policy['boundary']}


def peripheral_energy(row, operations, cycles, period_ns=2):
    model = row.get('cost_model')
    if model is None: return {}
    if 'cam' in model:
        cam = model['cam']
        search = operations.get('cam_searches',0); read = operations.get('cam_output_ids',0)
        write = operations.get('cam_filled_rows',0)+operations.get('cam_evicted_rows',0)
        dynamic = (search*cam['search_energy_nj']+read*cam['read_energy_nj']+write*cam['write_energy_nj'])/1000
        standby = cam['leakage_mw']*cycles*period_ns/1e6
        active = 3*(search+read+write)
    else:
        count = operations.get(model['operation'],0)
        dynamic = count*model['event_energy_pj']/1e6
        standby = model['standby_mw']*cycles*period_ns/1e6
        active = None if model['cycles_per_event'] is None else round(count*model['cycles_per_event'])
        groups = operations.get('neural_adc_groups',0)
        if row['id'] == 'sample_hold': active = groups*(1+1+9)
        if row['id'] == 'adc_lanes': active = groups*9
        if row['id'] == 'analog_mux': active = groups
    return {'dynamic_energy_uj':dynamic,'standby_energy_uj':standby,'leakage_energy_uj':None,
        'energy_uj':dynamic+standby,'active_cycles':active,
        'active_us':None if active is None else active*period_ns/1000,
        'average_power_mw':(dynamic+standby)*1e6/(cycles*period_ns),
        'energy_status':'Analytical cost proxy with explicit standby assumptions; not measured power'}
