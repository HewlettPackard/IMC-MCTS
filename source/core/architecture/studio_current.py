# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Studio's explicit current architecture and reporting adapter.
# SPDX-License-Identifier: MIT
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from core.architecture.parallel_datapath import ParallelDatapathGoSimulation, SizedParallelDatapathGoSimulation, datapath_spec, candidate_pipeline, LANES
from core.architecture.offset_encoding import OffsetNeuralMapping
from core.architecture.parallel_datapath_costs import parallel_datapath_costs
from core.architecture.sram_costs import sram_accounting
from core.architecture.component_parameters import validate_parameters, parameter_sources, parameter_catalog, apply_parameters
from core.architecture.run_identity import json_sha256
from core.architecture.connected_costs import COST_PROFILE, SOURCE_FILES as CONNECTED_SOURCE_FILES, metadata as connected_metadata
from p03_experiments.p79_scalability.costs import estimate

ROOT=Path(__file__).resolve().parents[2]
PROFILE=datapath_spec()['profile']
SOURCES=ROOT/'p03_experiments/p79_scalability/p00_runs/run_20260917_155326Z'
SOURCE_FILES=[SOURCES/'sources.json',SOURCES/'published_adc.json',
    ROOT/'p03_experiments/p79_scalability/costs.py',
    ROOT/'core/architecture/parallel_datapath.json',ROOT/'core/architecture/offset_encoding.json',
    ROOT/'core/architecture/parallel_selection.json',ROOT/'core/architecture/ucb_overlap.json',
    ROOT/'core/architecture/board_sizing.json',ROOT/'core/architecture/board_memory_characterization.json',
    ROOT/'core/architecture/parallel_datapath.py',ROOT/'core/architecture/parallel_datapath_costs.py',
    ROOT/'core/architecture/component_parameters.py',ROOT/'core/architecture/interconnect_budget.py',ROOT/'core/architecture/studio_current.py',
    ROOT/'core/architecture/adc_power_policy.py',ROOT/'core/architecture/peripheral_assumptions.json',
    ROOT/'rtl_synthesis/p08_connected_paths/p00_rtl/imc_selection_path.sv',
    ROOT/'rtl_synthesis/p08_connected_paths/p00_rtl/imc_readout_path.sv',
    ROOT/'core/architecture/connected_costs.py', *CONNECTED_SOURCE_FILES]


def source_identities():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE_FILES}


def cost_identity(sources=None,parameters=None):
    return json_sha256({'profile':COST_PROFILE,'sources':source_identities() if sources is None else sources,
        'component_parameters':parameters or {}})


def current_architecture(board=9):
    from core.architecture.board_sizing import board_hardware
    shape=board_hardware(board)
    return datapath_spec() | {'installed_sram_bytes':1024*(shape['node_sram_kib']+shape['child_sram_kib']),
        'cam_entries':shape['cam_entries'],'board_size':board,'hardware_profile':'board_sized_s1_v1'} | {'label':'Current optimized design',
        'supported_boards':[2,3,5,9,13,19],'models':['go_strong_v1','go_weak_v1','random_diagnostic'],
        'cost_model_profile':COST_PROFILE,'cost_model_sha256':cost_identity(),'connected_synthesis':connected_metadata(),
        'arrays':[{'layer':1,'rows':2*board*board+1,'columns':96},{'layer':2,'rows':96,'columns':3}],
        'encoding':'offset q + 128; subtract 128 × input sum',
        'default_configuration':{'profile':PROFILE,'board_size':9,'model_id':'go_strong_v1',
            'rules':'legacy_go','memory_profile':'cacti_22nm_lstp','iterations':5000,'seed':0,'hardware_profile':'board_sized_s1_v1'}}


def effective_architecture(prepared):
    architecture=current_architecture(prepared['neural']['profile']['board_size'])
    architecture['cost_model_sha256']=cost_identity(prepared['source_sha256'],prepared['component_parameters'])
    if prepared['component_parameters']:
        architecture.update(component_parameters=prepared['component_parameters'],parameter_status='user_assumption',
            adc_service_cycles=prepared['memory']['adc_service_cycles'],ucb_busy_cycles=prepared['memory']['ucb_busy_cycles'],
            cam_service_cycles=prepared['memory']['cam_search_cycles'])
    return architecture


def is_current(config):
    return config.get('profile')==PROFILE


def validate_current(config):
    from core.architecture.board_sizing import board_hardware, memory_profile_name, PROFILE as SIZED
    shape=board_hardware(config['board_size'])
    if config.get('rules')!='legacy_go' or config.get('model_id','random_diagnostic') not in current_architecture()['models']:
        raise ValueError('Current architecture requires Go rules and supported trained or diagnostic weights')
    if config.get('model_id','random_diagnostic')!='random_diagnostic' and config['board_size']!=9:
        raise ValueError('Trained checkpoints are available only for 9x9')
    if config.get('hardware_profile',SIZED)!=SIZED or config.get('cam_entries') not in (None,shape['cam_entries']):
        raise ValueError('Hardware settings conflict with the approved board table')
    if memory_profile_name(config['board_size'],config['memory_profile'])!=memory_profile_name(config['board_size'],'cacti_22nm_lstp'):
        raise ValueError('Current architecture uses low-leakage SRAM')
    if config.get('readout_profile','sustained_drive_v1')!='sustained_drive_v1':
        raise ValueError('Current architecture uses sustained drive and two digital result banks')
    if 'component_parameters' in config: config['component_parameters']=validate_parameters(config['component_parameters'])
    config.update(cam_entries=shape['cam_entries'],hardware_profile=SIZED)


def activity(active,cycles):
    return {'profile':PROFILE,'elapsed_cycles':cycles,'blocks':{
        key:{'active_cycles':value,'idle_cycles':cycles-value} for key,value in active.items()},
        'boundary':datapath_spec()['boundary']}


def capture(model):
    return {'parents':[[n,v,count] for (n,v),count in model.parent_histogram.items()],
        'completed':model.completed}


def combine(a,b):
    parents=Counter()
    for data in (a,b):
        for n,v,count in data.get('parents',[]): parents[n,v]+=count
    return {'parents':[[n,v,c] for (n,v),c in parents.items()],
        'completed':a.get('completed',0)+b.get('completed',0)}


def prepare(model):
    from core.architecture.connected_costs import load_characterization
    load_characterization()
    sources=json.loads((SOURCES/'sources.json').read_text())
    published=json.loads((SOURCES/'published_adc.json').read_text())
    if model.memory.config.get('hardware_profile'):
        from core.architecture.board_sizing import memory_characterization, memory_profile_name
        from core.architecture.sram_costs import load_sram_profile
        sources['sram']=load_sram_profile(memory_profile_name(model.board_size,'cacti_22nm_lstp'))
        cams=sources['tools']['cam'] | memory_characterization()['cam']
        size=model.memory.config['cam_entries']
        key='cam_'+str(2048 if size==1536 else size)+'_lstp'
        sources['selected_cam']=cams[key]
    parameters=validate_parameters(getattr(model,'component_parameters',{}))
    default_sources=sources
    sources=parameter_sources(sources,parameters)
    reference=OffsetNeuralMapping(*model.weights,model.board_size,turn_indicator=True)
    reference.bind_memory(model.memory)
    return {'component_parameters':parameters,'default_sources':default_sources,'sources':sources,'published':published,'reference':reference,'reference_estimate':reference.estimate(),
        'neural':model.neural.estimate(), 'memory':deepcopy(model.memory.config),
        'source_sha256':source_identities()}


@lru_cache(maxsize=1024)
def selection_extra_cycles(n,v,busy_cycles=169):
    return n*22+171*((v+3)//4)+v-candidate_pipeline([True]*v+[False]*(n-v),busy_cycles=busy_cycles)['cycles']


def price(operations,cycles,active,basis,prepared):
    # Reconstruct the older switch-work basis from this run's actual census.
    # No reference search, saved-run energy scaling or UI-invented latency.
    ops=Counter(operations);active=Counter(active)
    evals=ops['neural_adc_conversions']//prepared['neural']['operations']['adc_conversions']
    selection_extra=0; old_active=Counter({k:v for k,v in active.items() if k not in LANES})
    for n,v,count in basis['parents']:
        selection_extra+=selection_extra_cycles(n,v,prepared['memory'].get('ucb_busy_cycles',169))*count
        for lane,name in enumerate(('u_ucb_a','u_ucb_b','u_ucb_c','u_ucb_d')):
            old_active[name]+=169*(v//4+(lane<v%4))*count
    for name in ('u_ucb_a','u_ucb_b','u_ucb_c','u_ucb_d'):old_active.setdefault(name,0)
    reference=prepared['reference']
    neural_extra=evals*(reference.schedule['cycles']-prepared['neural']['cycles'])
    old_cycles=cycles+selection_extra+neural_extra
    old_active['u_sel']+=selection_extra;old_active['u_nn']+=neural_extra
    old_active['top_level_glue']+=selection_extra+neural_extra
    # An inventory-only one-cycle idle interval is used at ready, never reported
    # as executed work. Live pricing starts after the first completed phase.
    elapsed=max(1,cycles);old_elapsed=max(1,old_cycles)
    old_model=SimpleNamespace(board_size=prepared['neural']['profile']['board_size'],cycles=old_elapsed,block_active_cycles=old_active,
        memory=SimpleNamespace(config=prepared['memory'],operations=ops),neural=reference)
    old_costs=estimate(old_model,prepared['sources'],prepared['published'])
    common={'iterations':basis['completed'],'neural_evaluations':evals,'installed_sram_bytes':prepared['memory']['node_sram_bytes']+prepared['memory']['child_sram_bytes'],
        'memory':{'config':prepared['memory'],'operations':ops}}
    current=common | {'ucb_busy_cycles':prepared['memory'].get('ucb_busy_cycles',169),'adc_service_cycles':prepared['memory'].get('adc_service_cycles',13),'cycles':elapsed,'latency_ms':elapsed/500000,'neural':prepared['neural'],
        'activity':activity(active,elapsed)}
    old=common | {'cycles':old_elapsed,'latency_ms':old_elapsed/500000,'neural':prepared['reference_estimate'],
        'activity':activity(old_active,old_elapsed)}
    report=parallel_datapath_costs(current,old,old_costs,prepared['sources'],prepared['published'])
    return apply_parameters(report,ops,prepared['component_parameters'],prepared['published'])


def components(report,prepared):
    rows=deepcopy(report['components'])
    scorers=[r for r in rows if r['id'] in LANES]
    rows=[r for r in rows if r['id'] not in LANES]
    group=deepcopy(scorers[0]);group.update(id='u_ucb',component='Parallel UCB scorers',count=16)
    for key in ('area_um2','energy_uj','dynamic_energy_uj','standby_energy_uj','average_power_mw'):
        group[key]=sum(r[key] for r in scorers)
    native=[r['details']['native65_part'] for r in scorers if r['details'].get('native65_part')]
    group['details']={'lanes':16}
    if native:
        native_fields=('area_um2','dynamic_mw','leakage_mw','switching_mw','internal_mw','reported_total_mw','active_dynamic_mw','idle_dynamic_mw')
        group['details']['native65_part']=native[0] | {key:sum(r[key] for r in native) for key in native_fields if all(key in r for r in native)}
        group['details']['native65_part'].update(instance='Sixteen disjoint UCB scorer instances',ownership='Inclusive lane areas; excluded from the selector wrapper allocation')
        group['details']['power_defaults_mw']={key:sum(r['details']['power_defaults_mw'][key] for r in scorers) for key in ('active_dynamic_mw','idle_dynamic_mw','leakage_mw')}
    group['children']=[r | {'counted':False,'included_in':'u_ucb'} for r in scorers]
    rows.insert(3,group)
    memory=prepared['memory']
    for row in rows:
        row['scope']='core';row['energy_status']=row['assumptions']
        row['cost_model']={'method':row['assumptions']}
        native=row['details'].get('native65_part')
        if native:
            row.update(native_65nm_area_um2=native['area_um2'],
                native_65nm_power={key:native[key] for key in ('dynamic_mw','leakage_mw')},
                connected_synthesis=report['connected_synthesis'])
        if row['id'] in ('u_ucb','adc_lanes','cam_macro'):
            key={'u_ucb':'ucb_busy_cycles','adc_lanes':'adc_service_cycles','cam_macro':'cam_search_cycles'}[row['id']]
            row.update(service_cycles=memory[key],service_unit={'u_ucb':'score','adc_lanes':'conversion','cam_macro':'service'}[row['id']])
        if row['id'] in ('node_sram','child_sram'):
            row.update(capacity_bytes=memory[row['id']+'_bytes'],bank_bytes=memory.get('sram_bank_bytes',512*1024))
        if row['id']=='cam_macro':row['logical_entries']=memory['cam_entries']
        if row['id']=='cim_arrays':
            row['children']=[{'id':'cim_arrays/layer_'+str(i+1),'component':f'Layer {i+1}: {a["rows"]} × {a["columns"]}',
                'count':1,'counted':False,'included_in':'cim_arrays','rows':a['rows'],'columns':a['columns']}
                for i,a in enumerate(prepared['neural']['resources']['array_dimensions'])]
        if row['id']=='u_sel':row['children']=[{'id':'u_sel/operands','component':'Connected selector wrapper: header loader, two candidate banks and ordered reduction','counted':False,'included_in':'u_sel',
            'status':'Exclusive wrapper allocation; the sixteen UCB scorers have their own disjoint owner'}]
        if row['id']=='u_nn':
            row['children']=[{'id':'u_nn/'+name,'component':label,'counted':False,'included_in':'u_nn'} for name,label in
                [('adc_results','Two 32 × 16-bit ADC result banks'),('bus','128-bit readout bus'),('staging','512-bit ADC group staging register'),
                ('accumulators','Eight connected accumulation banks, 96 × 32-bit registers'),('offset','Residual neural control, input-sum and offset correction allowance')]]
        residual=row['details'].get('residual_control_allocation')
        if residual:
            row['children'].append({'id':row['id']+'/residual_control','component':'Residual control allocation',
                'counted':False,'included_in':row['id'],'area_um2':residual['area_um2'],
                'status':residual['status'],'source':residual['basis']})
    return rows


def inventory(prepared):
    report=price({},0,dict.fromkeys(('u_sel','u_nn','u_upd','u_node_router','u_child_router','top_level_glue',*LANES),0),
        {'parents':[],'completed':0},prepared)
    rows=components(report,prepared)
    nominal=report
    if prepared['component_parameters']:
        base=prepared | {'component_parameters':{},'sources':prepared['default_sources']}
        nominal=price({},0,dict.fromkeys(('u_sel','u_nn','u_upd','u_node_router','u_child_router','top_level_glue',*LANES),0),{'parents':[],'completed':0},base)
    for row in rows:
        for key in ('energy_uj','dynamic_energy_uj','standby_energy_uj','average_power_mw'):row.pop(key,None)
        for child in row.get('children',[]):
            for key in ('energy_uj','dynamic_energy_uj','standby_energy_uj','average_power_mw'):child.pop(key,None)
    return {'architecture':effective_architecture(prepared),'components':rows,'known_area_mm2':report['core_area_mm2'],
        'installed_memory':prepared['memory'],'source_sha256':prepared['source_sha256'],
        'parameter_catalog':parameter_catalog(prepared | {'sources':prepared['default_sources']},nominal),'component_parameters':prepared['component_parameters'],
        'peripheral_model':{'profile':report['profile']},'cost_model_profile':report['profile'],
        'cost_model_sha256':cost_identity(prepared['source_sha256'],prepared['component_parameters']),
        'connected_synthesis':report['connected_synthesis'],
        'reference_crossbar':{'weight_bits':8,'cell_bits':8},
        'analog_readout':{'profile':'sustained_drive_v1','digital_adc_result_bits':1024,'readout_staging_bits':512,'adc_bits':12,
            'shared_adc_lanes':32,'installed_analog_samples':32,'digital_result_banks':2}}


def costs(operations,cycles,active,basis,prepared):
    report=price(operations,cycles,active,basis,prepared)
    rows=components(report,prepared)
    for row in rows:
        if row['id'] in active:row['active_cycles']=active[row['id']]
        for child in row.get('children',[]):
            if child['id'] in active:child['active_cycles']=active[child['id']]
    digital=[r for r in report['components'] if r['id'] in active]
    digest=cost_identity(prepared['source_sha256'],prepared['component_parameters'])
    ledger={'profile':report['profile'],'sha256':digest,'source_identities':prepared['source_sha256'],
        'components':rows,'known_area_mm2':report['core_area_mm2'],'known_energy_uj':report['core_energy_uj'],
        'known_average_power_mw':report['core_average_power_mw'],'missing_area':[],'missing_energy':[],
        'operating_point_status':report['status'],'peripheral_model':{'profile':report['profile']},
        'boundary':datapath_spec()['boundary'],'component_parameters':prepared['component_parameters'],
        'connected_synthesis':report['connected_synthesis']}
    power_rows=[{'instance':r['id'],'active_cycles':active[r['id']],'idle_cycles':cycles-active[r['id']],
        'target_22nm_energy_nj':r['energy_uj']*1000,'target_22nm_average_power_mw':r['average_power_mw'],
        'powers_mw':{},'status':'user_parameter_scenario' if r.get('parameter_status') else 'vectorless_all_elapsed_scenario' if r['details'].get('native65_part') else 'source-linked engineering proxy'} for r in digital]
    sram=sram_accounting(prepared['sources']['sram'],Counter(operations),max(1,cycles))
    if prepared['component_parameters']:
        for key,pool in sram['pools'].items():
            row=next(r for r in report['components'] if r['id']==key)
            pool.update(dynamic_energy_nj=row['dynamic_energy_uj']*1000,leakage_energy_nj=row['standby_energy_uj']*1000,area_mm2=row['area_um2']/1e6)
        sram.update(dynamic_energy_nj=sum(p['dynamic_energy_nj'] for p in sram['pools'].values()),leakage_energy_nj=sum(p['leakage_energy_nj'] for p in sram['pools'].values()),area_mm2=sum(p['area_mm2'] for p in sram['pools'].values()),parameter_status='user_assumption')
        sram.update(energy_uj=(sram['dynamic_energy_nj']+sram['leakage_energy_nj'])/1000,average_power_mw=(sram['dynamic_energy_nj']+sram['leakage_energy_nj'])/sram['latency_us'])
    return {'status':'core_estimate_with_proxies_and_allowances','ledger':ledger,'connected_synthesis':report['connected_synthesis'],
        'whole_chip':{'area_mm2':None,'energy_uj':None,'power_mw':None},
        'sram':sram,
        'digital':{'source_commit':report['connected_synthesis']['source_commit'],
            'retained_proxy_source_commit':prepared['sources']['digital']['commit'],
            'known_area_mm2':sum(r['area_um2'] for r in digital)/1e6,'known_native_65nm_area_um2':None,
            'priced_instances':len(digital),'profile_sha256':digest,'timing_violations':None},
        'block_power':{'components':power_rows,'operating_point':{'clock_mhz':500},'table_sha256':digest,
            'target_policy':report['profile']},'timing':datapath_spec()['timing_status'],
        'boundary':datapath_spec()['boundary'],'estimate':report}


@lru_cache(maxsize=12)
def _preview(model_id,board,cost_sha256):
    from core.algorithm.model_catalog import load_model
    weights,_=load_model(model_id,board)
    return inventory(prepare(SizedParallelDatapathGoSimulation(board_size=board,iterations=1,weights=weights)))


def preview(model_id,board=9):
    return _preview(model_id,board,cost_identity())


def custom_preview(model_id,board,parameters):
    from core.algorithm.model_catalog import load_model
    weights,_=load_model(model_id,board)
    return inventory(prepare(SizedParallelDatapathGoSimulation(board_size=board,iterations=1,weights=weights,component_parameters=parameters)))
