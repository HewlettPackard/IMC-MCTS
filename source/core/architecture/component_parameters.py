# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Per-run unit values. Source files and historical estimates stay immutable.
# SPDX-License-Identifier: MIT
from copy import deepcopy
import math
from core.architecture.adc_power_policy import adc_power_policy
from core.architecture.interconnect_budget import interconnect_budget

DIGITAL={'u_sel':'imc_cached_selector','u_upd':'imc_tree_update_v2',
    'top_level_glue':'imc_iteration_glue','u_node_router':'imc_sram_router_3bank',
    'u_child_router':'imc_sram_router_1bank','u_nn':'imc_neural_sequencer','u_ucb':'imc_ucb_score'}
OWNERS=tuple(DIGITAL)+('node_sram','child_sram','cam_macro','cim_arrays',
    'row_drivers','sample_hold','adc_lanes','analog_mux','physical_overhead')
COMMON={'area_um2':('Installed group area','µm²',0,1e12),
    'standby_mw':('Installed standby / bias power','mW',0,1e6)}
POWER={key:(label,'mW at source 65 nm',0,1e6) for key,label in
    [('active_dynamic_mw','Active dynamic power'),('idle_dynamic_mw','Idle dynamic power'),
     ('leakage_mw','Source leakage power')]}
ENERGY=('Dynamic energy per event','pJ',0,1e12)
FIELDS={key:dict(COMMON) for key in OWNERS}
for key in DIGITAL:FIELDS[key].update(POWER)
for key in ('node_sram','child_sram'):
    FIELDS[key].update(read_energy_pj=('Energy per 32-bit read','pJ',0,1e12),
        write_energy_pj=('Energy per 32-bit write','pJ',0,1e12))
FIELDS['cam_macro'].update(search_energy_pj=('Energy per search','pJ',0,1e12),
    read_energy_pj=('Energy per output read','pJ',0,1e12),
    write_energy_pj=('Energy per row write','pJ',0,1e12))
for key,label in [('row_drivers','Energy per driven row'),('sample_hold','Energy per sample'),
                  ('adc_lanes','Energy per conversion'),('analog_mux','Energy per conversion')]:
    FIELDS[key]['energy_pj']=(label,'pJ',0,1e12)
FIELDS['cim_arrays'].update(cell_area_um2=('Area per Super-T cell','µm²',0,1e6),
    resistance_mohm=('On resistance','MΩ',1e-12,1e12),read_voltage_v=('Read voltage','V',1e-12,100),
    cell_capacitance_ff=('Cell capacitance','fF',0,1e12),wire_capacitance_ff=('Wire capacitance per cell','fF',0,1e12))
for key in ('adc_lanes','u_ucb','cam_macro'):
    FIELDS[key]['service_cycles']=('Service duration at assumed 500 MHz','cycles',1,4096)
FIELDS['physical_overhead']={'area_fraction':('Area allowance fraction','fraction',0,1),
    'dynamic_fraction':('Digital dynamic-energy allowance fraction','fraction',0,1),
    'readout_capacitance_ff_per_bit':('Readout total capacitance per bit (set allowance to zero)','fF/bit',0,1e9),
    'readout_voltage_v':('Readout wire scenario voltage','V',1e-12,100),
    'readout_rise_probability':('Readout 0-to-1 probability per bit per transfer','probability',0,1)}
CELL_FIELDS={'cell_area_um2':'C14','resistance_mohm':'L14','read_voltage_v':'L15',
    'cell_capacitance_ff':'O16','wire_capacitance_ff':'O17'}


def validate_parameters(value):
    if value is None:return {}
    if not isinstance(value,dict) or set(value)-set(FIELDS):raise ValueError('Unknown component parameter group')
    result={}
    for component,fields in value.items():
        if not isinstance(fields,dict) or set(fields)-set(FIELDS[component]):raise ValueError('Unknown parameter for '+component)
        result[component]={}
        for key,number in fields.items():
            label,unit,low,high=FIELDS[component][key]
            if type(number) not in (int,float) or not math.isfinite(number) or not low<=number<=high:
                raise ValueError(component+'.'+key+' must be finite and in ['+str(low)+','+str(high)+'] '+unit)
            if key=='service_cycles' and type(number) is not int:raise ValueError('Service cycles must be an integer')
            result[component][key]=number
        if not result[component]:del result[component]
    route=result.get('physical_overhead',{})
    if route.get('readout_capacitance_ff_per_bit',0)>0 and route.get('dynamic_fraction',0.10)!=0:
        raise ValueError('Set dynamic_fraction to zero before supplying readout capacitance; routing cannot be counted twice')
    return result


def parameter_sources(sources,parameters):
    parameters=validate_parameters(parameters)
    if not parameters:return sources
    result=deepcopy(sources)
    result['connected_default_power_cases']=deepcopy(sources['power']['cases'])
    result['connected_parameter_overrides']=parameters
    for component,case in DIGITAL.items():
        if component in ('u_sel','u_nn','u_ucb'):
            # Their fields describe installed connected groups, not the older
            # single scorer/parent. Resolve and validate against new defaults.
            continue
        powers=result['power']['cases'][case]['powers_mw']
        powers.update({k:v for k,v in parameters.get(component,{}).items() if k in POWER})
        if powers['active_dynamic_mw']<powers['idle_dynamic_mw']:
            raise ValueError(component+' active dynamic power cannot be below idle dynamic power')
    cells=result['workbook']['cells']['New_Architecture']
    for key,address in CELL_FIELDS.items():
        if key in parameters.get('cim_arrays',{}):cells[address]['value']=parameters['cim_arrays'][key]
    return result


def parameter_catalog(prepared,report):
    rows={r['id']:r for r in report['components']}; sources=prepared['sources']; published=prepared['published']
    ucb=[r for r in report['components'] if r['id'].startswith('u_ucb_')]
    rows['u_ucb']={'component':'Sixteen UCB scorers','area_um2':sum(r['area_um2'] for r in ucb),
        'standby_energy_uj':sum(r['standby_energy_uj'] for r in ucb),'source':ucb[0]['source'],
        'details':{'power_defaults_mw':{key:sum(r['details']['power_defaults_mw'][key] for r in ucb) for key in POWER}}}
    cells=sources['workbook']['cells']['New_Architecture']; v=lambda k:cells[k]['value']
    cam=sources.get('selected_cam',sources['tools']['cam']['cam_1024_lstp'])
    macro=sources['sram']['macro']; t=report['latency_ms']
    frontend=12*1.8/1000*published['input_capacitance_ff']/v('C42')
    defaults={key:{'area_um2':row['area_um2'],'standby_mw':row['standby_energy_uj']/t} for key,row in rows.items() if key in FIELDS}
    for key,case in DIGITAL.items():
        defaults[key].update(rows[key].get('details',{}).get('power_defaults_mw',sources['power']['cases'][case]['powers_mw']))
    for key in ('node_sram','child_sram'):
        defaults[key].update(read_energy_pj=macro['read_energy_nj']*1000,write_energy_pj=macro['write_energy_nj']*1000)
    defaults['cam_macro'].update({k+'_energy_pj':cam[k+'_energy_nj']*1000 for k in ('search','read','write')})
    defaults['cim_arrays'].update({k:v(address) for k,address in CELL_FIELDS.items()})
    defaults['row_drivers']['energy_pj']=v('O26')+v('P31')/v('C13')/v('C5')
    defaults['sample_hold']['energy_pj']=frontend*.95*15*2+published['input_capacitance_ff']*v('L15')**2/1000
    defaults['adc_lanes'].update(energy_pj=published['energy_pj'],standby_mw=32*adc_power_policy()['value']*published['energy_pj']/(1000/published['sample_rate_msps']),service_cycles=13)
    defaults['analog_mux']['energy_pj']=2*v('O26')
    defaults['u_ucb']['service_cycles']=169;defaults['cam_macro']['service_cycles']=3
    defaults['physical_overhead']={'area_fraction':.15,'dynamic_fraction':.10,'readout_capacitance_ff_per_bit':0,
        'readout_voltage_v':0.8,'readout_rise_probability':0.25}
    groups=[]
    for key in OWNERS:
        fields=[]
        for name,(label,unit,low,high) in FIELDS[key].items():
            fields.append({'key':name,'label':label,'unit':unit,'default':defaults[key][name],
                'minimum':low,'maximum':high,'integer':name=='service_cycles'})
        groups.append({'id':key,'label':rows[key]['component'],'source':rows[key]['source'],'fields':fields})
    return {'schema':'component_unit_parameters_v1','groups':groups,
        'scope':'Per-run analytical assumptions; editing values does not establish physical feasibility',
        'clock_mhz_assumed':500,'timing_components':['adc_lanes','u_ucb','cam_macro']}


def apply_parameters(report,operations,parameters,published):
    parameters=validate_parameters(parameters)
    if not parameters:return report
    result=deepcopy(report); t=result['latency_ms']; grouped={}
    for row in result['components']:
        key='u_ucb' if row['id'].startswith('u_ucb_') else row['id']
        grouped.setdefault(key,[]).append(row)
    for key,fields in parameters.items():
        if key=='physical_overhead':continue
        group_area=sum(row['area_um2'] for row in grouped[key])
        group_standby=sum(row['standby_energy_uj'] for row in grouped[key])
        for row in grouped[key]:
            # A UCB-group override preserves each native lane's share. The
            # sixteen synthesized lanes have slightly different cell areas.
            area_share=row['area_um2']/group_area if key=='u_ucb' and group_area else 1/len(grouped[key])
            standby_share=row['standby_energy_uj']/group_standby if key=='u_ucb' and group_standby else 1/len(grouped[key])
            if 'area_um2' in fields:row['area_um2']=fields['area_um2']*area_share
            if 'standby_mw' in fields:
                duration=row['details']['idle_lane_ms']/32 if key=='adc_lanes' else t
                row['standby_energy_uj']=fields['standby_mw']*duration*standby_share
                if key=='adc_lanes':
                    row['details'].update(adc_standby_assumption='ADC standby power neglected' if fields['standby_mw']==0 else 'User-specified ADC standby power',
                        adc_standby_source='Explicit per-run parameter',adc_idle_fraction=None)
            if key in ('node_sram','child_sram') and any(k in fields for k in ('read_energy_pj','write_energy_pj')):
                original=row['details']; source=original.get('unit_energy_pj',{})
                if not source:raise ValueError('SRAM unit-energy basis is missing')
                row['dynamic_energy_uj']=sum(operations.get(key+'_'+action+'_words',0)*fields.get(action+'_energy_pj',source[action])/1e6 for action in ('read','write'))
            if key=='cam_macro' and any(k in fields for k in ('search_energy_pj','read_energy_pj','write_energy_pj')):
                source=row['details']['unit_energy_pj']
                counts={'search':operations.get('cam_searches',0),'read':operations.get('cam_output_ids',0),
                    'write':operations.get('cam_filled_rows',0)+operations.get('cam_evicted_rows',0)}
                row['dynamic_energy_uj']=sum(counts[a]*fields.get(a+'_energy_pj',source[a])/1e6 for a in counts)
            event={'row_drivers':'neural_dac_bit_drives','sample_hold':'neural_samples',
                'adc_lanes':'neural_adc_conversions','analog_mux':'neural_adc_conversions'}.get(key)
            if event and 'energy_pj' in fields:row['dynamic_energy_uj']=operations.get(event,0)*fields['energy_pj']/1e6
            if row['details'].get('allocation_breakdown') and any(k in fields for k in ('area_um2','standby_mw')):
                row['details']['default_allocation_breakdown']=row['details'].pop('allocation_breakdown')
                row['details']['allocation_status']='Default allocation retained as reference; user area/standby overrides replace parent totals without characterized part splits'
            row['details']['parameter_overrides']=fields
            row['parameter_status']='User-provided analytical assumptions'
            row['assumptions']+=' Per-run unit-value overrides are user assumptions, not newly characterized hardware.'
            if key in ('node_sram','child_sram'):
                row['details'].update(dynamic_energy_nj=row['dynamic_energy_uj']*1000,
                    leakage_energy_nj=row['standby_energy_uj']*1000,area_mm2=row['area_um2']/1e6)
    overhead=grouped['physical_overhead'][0]
    fractions=parameters.get('physical_overhead',{})
    af=fractions.get('area_fraction',.15); df=fractions.get('dynamic_fraction',.10)
    base=sum(r['area_um2'] for r in result['components'] if r is not overhead)
    overhead['area_um2']=base*af
    routing=interconnect_budget(operations,sum(r['dynamic_energy_uj'] for key,rows in grouped.items() if key in DIGITAL for r in rows),fractions)
    overhead['dynamic_energy_uj']=routing['dynamic_energy_uj']
    overhead['details'].update(routing,base_area_um2=base,area_fraction=af)
    overhead['assumptions']=routing['boundary']
    if fractions:
        overhead['details']['parameter_overrides']=fractions
        overhead['parameter_status']='User-provided analytical assumptions'
    for row in result['components']:
        row['energy_uj']=row['dynamic_energy_uj']+row['standby_energy_uj'];row['average_power_mw']=row['energy_uj']/t
        if any(not math.isfinite(row[k]) or row[k]<0 for k in ('area_um2','dynamic_energy_uj','standby_energy_uj')):raise ValueError('Invalid override cost for '+row['id'])
    total=sum(r['energy_uj'] for r in result['components']); n=result['iterations']
    result.update(core_area_mm2=sum(r['area_um2'] for r in result['components'])/1e6,core_energy_uj=total,
        core_energy_mj=total/1000,core_average_power_mw=total/t,
        average_energy_uj_per_iteration=total/n if n else None,average_energy_mj_per_iteration=total/1000/n if n else None,
        parameter_overrides=parameters,parameter_status='Custom per-run analytical scenario')
    return result
