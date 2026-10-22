# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Component accounting for the executable UCB16/ADC32 design.
# SPDX-License-Identifier: MIT
from copy import deepcopy
import math
from core.architecture.adc_power_policy import adc_power_policy
from core.architecture.interconnect_budget import interconnect_budget

from core.architecture.parallel_datapath import LANES
from core.architecture.connected_costs import COST_PROFILE, native_parts, metadata

SCENARIOS = {'low_controller_activity':0.75,'nominal':1.0,'high_controller_activity':2.0}


def parallel_datapath_costs(candidate,reference,reference_costs,sources,published,scenario='nominal'):
    if scenario not in SCENARIOS: raise ValueError('Unknown controller activity scenario')
    expected_bytes = sum(sources['sram']['banks'].values())*sources['sram']['bank_bytes']
    if candidate['installed_sram_bytes']!=expected_bytes: raise ValueError('Installed and priced SRAM disagree')
    if candidate['memory']['config']['execution_profile']!='ucb16_adc32_buffered_v2':
        raise ValueError('Wrong executable hardware profile')
    t = candidate['latency_ms']; t0 = reference['latency_ms']
    if t<=0 or t0<=0: raise ValueError('Completed elapsed intervals required')
    if reference_costs['latency_ms']!=t0: raise ValueError('Reference cost/timing mismatch')
    original = {r['id']:r for r in reference_costs['components']}
    ops = candidate['memory']['operations']; old_ops = reference['memory']['operations']
    for name in ('node_sram_read_words','node_sram_write_words','child_sram_read_words',
        'child_sram_write_words','ucb_operations','neural_adc_conversions','neural_shift_adds'):
        if ops[name]!=old_ops[name]: raise ValueError('Work count changed: '+name)
    digital = sources['digital']['cases']; power = sources['power']['cases']
    af = sources['scaling']['area']['factor']; ef = sources['scaling']['dynamic_energy']['factor']
    activity = candidate['activity']['blocks']; reference_activity = reference['activity']['blocks']
    neural = candidate['neural']; rows = []

    def add(old,area,dynamic,standby,count=None,details=None,note=None):
        row = deepcopy(old)
        row.update(area_um2=area,dynamic_energy_uj=dynamic,standby_energy_uj=standby,
            energy_uj=dynamic+standby,average_power_mw=(dynamic+standby)/t)
        if count is not None: row['count'] = count
        if details is not None: row['details'] = details
        if note is not None: row['assumptions'] = note
        for k in ('area_um2','dynamic_energy_uj','standby_energy_uj'):
            if not math.isfinite(row[k]) or row[k]<0: raise ValueError('Invalid component cost '+row['id'])
        rows.append(row)
        return row

    for key in ('child_sram','node_sram'):
        row = original[key]
        standby = row['standby_energy_uj']*t/t0
        # Detail fields describe this search, not the slower reference interval.
        details = row['details'] | {'leakage_energy_nj':standby*1000,'unit_energy_pj':{a:sources['sram']['macro'][a+'_energy_nj']*1000 for a in ('read','write')}}
        add(row,row['area_um2'],row['dynamic_energy_uj'],standby,details=details)

    cases = {'u_sel':'imc_cached_selector','u_upd':'imc_tree_update_v2',
        'top_level_glue':'imc_iteration_glue','u_node_router':'imc_sram_router_3bank',
        'u_child_router':'imc_sram_router_1bank','u_nn':'imc_neural_sequencer'}
    accumulator = next(r for r in digital['imc_neural_sequencer']['hierarchy'] if r['instance']=='u_accumulator')
    bit_area = accumulator['local_sequential_area_um2']/(32*32)
    connected = native_parts()
    parameters = sources.get('connected_parameter_overrides',{})
    for key,case in cases.items():
        row = original[key]; w = power[case]['powers_mw']
        multiplier = row['details'].get('parent_multiplier',row['details'].get('area_multiplier',1))
        idle = w['idle_dynamic_mw']*ef*multiplier
        switching = (w['active_dynamic_mw']-w['idle_dynamic_mw'])*ef*multiplier
        area = row['area_um2']; details = deepcopy(row['details']); note = row['assumptions']
        if key in ('u_sel','u_nn'):
            part = deepcopy(connected[key])
            parent = digital[case]['area']['cell_um2']
            if key=='u_sel':
                residual = row['area_um2']/af
                basis = ('Existing selector budget reassigned as an engineering allowance for traversal, '
                    'CAM/cache handling, first-unvisited selection and cross-batch result control. '
                    'Candidate banks, loader, batch reduction and UCB lanes are owned by the connected region; '
                    'this is not an exact characterized residual split of the older flat selector.')
            else:
                # Remove the old 32-slot accumulator and its 24 code registers.
                # Keep 65 offset-register bits and one combinational-bank sizing
                # allowance solely for offset sum/shift/subtraction outside readout.
                residual = (parent-accumulator['inclusive_area_um2']+(65-24)*bit_area+
                    accumulator['local_combinational_area_um2'])*1.25
                basis = ('Old neural parent excluding its inclusive accumulator and 24 code registers; '
                    '65 offset-register bits retained. One old combinational-bank area is a sizing allowance '
                    'for offset sum/shift/subtraction, not a characterized bare ALU. '
                    'Connected readout exclusively owns result banks, staging and eight accumulator banks.')
                hidden = neural['profile']['hidden_size']
                projection = max(1,hidden/96)
                if projection!=1:
                    for field in ('area_um2','dynamic_mw','leakage_mw'):part[field]*=projection
                    part['projection_multiplier']=projection
                    part['projection_status']='Whole-readout size allocation for non-96-word application; not matching synthesis'
                details['reference_resources']=deepcopy(details['resources'])
                details['resources']=deepcopy(neural['resources'])
                details['readout_staging_bits']=512
            # Native default power has no measured active/idle split. Apply its
            # vectorless value over all elapsed time. Residual controller power
            # retains the source-parent area allocation and actual activity.
            default_power = sources.get('connected_default_power_cases',power)[case]['powers_mw']
            rm = residual/parent
            defaults = {'active_dynamic_mw':part['dynamic_mw']+default_power['active_dynamic_mw']*rm,
                'idle_dynamic_mw':part['dynamic_mw']+default_power['idle_dynamic_mw']*rm,
                'leakage_mw':part['leakage_mw']+default_power['leakage_mw']*rm}
            installed = defaults | {k:v for k,v in parameters.get(key,{}).items() if k in defaults}
            if installed['active_dynamic_mw']<installed['idle_dynamic_mw']:
                raise ValueError(key+' active dynamic power cannot be below idle dynamic power')
            active_ms=activity[key]['active_cycles']/500000
            switching_work=(installed['active_dynamic_mw']-installed['idle_dynamic_mw'])*active_ms*ef*SCENARIOS[scenario]
            elapsed_dynamic=installed['idle_dynamic_mw']*t*ef*SCENARIOS[scenario]
            dyn=switching_work+elapsed_dynamic
            standby=installed['leakage_mw']*t
            area=(part['area_um2']+residual)*af
            native_dynamic=part['dynamic_mw']*t*ef*SCENARIOS[scenario]
            native_standby=part['leakage_mw']*t
            custom_power=any(installed[k]!=defaults[k] for k in defaults)
            details.update(cost_basis_status='synthesis_with_residual_control_allocation',
                native65_part=part, power_defaults_mw=defaults,
                residual_control_allocation={'area_um2':residual*af,'native65_area_um2':residual,
                    'status':'engineering_allocation_not_matching_synthesis','basis':basis},
                allocation_breakdown=[
                    {'part':'connected_native_region','area_um2':part['area_um2']*af,
                     'dynamic_energy_uj':native_dynamic if not custom_power else dyn*part['area_um2']/(part['area_um2']+residual),
                     'standby_energy_uj':native_standby if not custom_power else standby*part['area_um2']/(part['area_um2']+residual),
                     'status':'native65_synthesis_target22_estimate' if not custom_power else 'user_power_allocation'},
                    {'part':'residual_control_allowance','area_um2':residual*af,
                     'dynamic_energy_uj':dyn-native_dynamic if not custom_power else dyn*residual/(part['area_um2']+residual),
                     'standby_energy_uj':standby-native_standby if not custom_power else standby*residual/(part['area_um2']+residual),
                     'status':'engineering_allocation_not_matching_synthesis'}],
                energy_breakdown_uj={'activity_dependent':switching_work,'elapsed_vectorless':elapsed_dynamic,'leakage':standby},
                active_cycles=activity[key]['active_cycles'],activity_multiplier=SCENARIOS[scenario])
            note = ('Connected digital area comes from native65 synthesis, with one target22 area conversion. '
                'Connected vectorless dynamic power is charged over elapsed time, with one stated target22 conversion; '
                'there is no characterized idle clock floor or workload calibration. Native65 leakage is carried unchanged. '+basis)
            row=deepcopy(row);row['source']=part['source'];row['status']='synthesis_with_residual_engineering_estimate'
        else:
            dyn = switching*activity[key]['active_cycles']/500000+idle*t
            standby = row['standby_energy_uj']*t/t0
            details['active_cycles'] = activity[key]['active_cycles']
        add(row,area,dyn,standby,details=details,note=note)

    exemplar = original['u_ucb_a']
    lane_totals={k:sum(connected[l][k] for l in LANES) for k in ('dynamic_mw','leakage_mw')}
    for lane in LANES:
        busy = activity[lane]['active_cycles']
        service=candidate.get('ucb_busy_cycles',169)
        if busy%service: raise ValueError('UCB activity is not an integer score count')
        scores = busy//service
        part=connected[lane]
        defaults={'active_dynamic_mw':part['dynamic_mw'],'idle_dynamic_mw':part['dynamic_mw'],'leakage_mw':part['leakage_mw']}
        installed=defaults.copy()
        for field,unit in (('active_dynamic_mw','dynamic_mw'),('idle_dynamic_mw','dynamic_mw'),('leakage_mw','leakage_mw')):
            if field in parameters.get('u_ucb',{}):
                installed[field]=parameters['u_ucb'][field]*part[unit]/lane_totals[unit]
        if installed['active_dynamic_mw']<installed['idle_dynamic_mw']:raise ValueError('UCB active dynamic power cannot be below idle power')
        work=(installed['active_dynamic_mw']-installed['idle_dynamic_mw'])*busy/500000*ef
        elapsed=installed['idle_dynamic_mw']*t*ef
        standby=installed['leakage_mw']*t
        old = exemplar | {'id':lane,'component':'UCB scorer '+str(int(lane[-2:])+1)}
        old['source']=part['source'];old['status']='native65_synthesis_target22_estimate'
        add(old,part['area_um2']*af,work+elapsed,standby,details={
            'scores':scores,'activity_dependent_energy_uj':work,'elapsed_vectorless_energy_uj':elapsed,
            'active_cycles':busy,'idle_cycles':candidate['cycles']-busy,'native65_part':part,
            'power_defaults_mw':defaults,'cost_basis_status':'connected_hierarchy_partition'},
            note='Native connected UCB lane area; target22 area/dynamic conversion applied once. Default vectorless dynamic power over elapsed time; native65 leakage proxy. No workload calibration or measured idle split.')
    cam = original['cam_macro']
    cam_source=sources.get('selected_cam',sources['tools']['cam']['cam_1024_lstp'])
    add(cam,cam['area_um2'],cam['dynamic_energy_uj'],cam['standby_energy_uj']*t/t0,details=cam['details'] | {'unit_energy_pj':{a:cam_source[a+'_energy_nj']*1000 for a in ('search','read','write')}})

    cells = sources['workbook']['cells']['New_Architecture']; v = lambda k:cells[k]['value']
    arrays = neural['resources']['array_dimensions']; trace = neural['profile']['readout_activity']
    # Same row activity and conductance scenario as the nominal reference, now
    # using the new array-on intervals computed by the executable schedule.
    pulses = candidate['memory']['operations']['neural_array_pulses']
    evaluations = ops['neural_adc_conversions']//neural['operations']['adc_conversions']
    if evaluations!=candidate.get('neural_evaluations',candidate['iterations']): raise ValueError('Unexpected evaluation count')
    on_cycles = [r['array_active_cycles'] for r in trace['arrays']]
    reference_on = [r['array_active_cycles'] for r in reference['neural']['profile']['readout_activity']['arrays']]
    # Switching and sustained conduction are separate; reconstruct the source
    # formula by layer so parallel columns cannot remove conversion work.
    from core.architecture.offset_encoding import offset_spec
    energy_pj = 0
    for layer,a in enumerate(arrays):
        bits = neural['profile'].get('layer_input_bits',[1,8])[layer]
        row_groups = (a['rows']+15)//16
        span = on_cycles[layer]//(row_groups*bits)
        if span*row_groups*bits!=on_cycles[layer]: raise ValueError('Unexpected readout burst timing')
        driven_rows = a['rows']*bits
        energy_pj += driven_rows*.5*a['columns']*(v('O16')+v('O17'))*v('L15')**2/1000
        energy_pj += driven_rows*.5*a['columns']*.5/(v('L14')*1e6)*v('L15')**2*span*2*1000
    array = original['cim_arrays']
    add(array,array['area_um2'],evaluations*energy_pj/1e6,0,details=array['details'] |
        {'array_active_cycles_per_evaluation':sum(on_cycles),'source_reference_cycles':sum(reference_on)})
    driver = original['row_drivers']
    add(driver,driver['area_um2'],driver['dynamic_energy_uj'],driver['standby_energy_uj']*t/t0)
    sample = original['sample_hold']
    add(sample,sample['area_um2']*4,sample['dynamic_energy_uj'],sample['standby_energy_uj']*4*t/t0,count=32)
    adc = original['adc_lanes']; conversions = ops['neural_adc_conversions']
    scheduled_ns=2*candidate.get('adc_service_cycles',13)
    occupied = conversions*scheduled_ns/1e6; idle_lane_ms = 32*t-occupied
    if idle_lane_ms < -1e-12: raise ValueError('ADC occupancy exceeds installed lane time')
    idle_lane_ms=max(0,idle_lane_ms)
    energy = published['energy_pj']; service_ns = 1000/published['sample_rate_msps']
    adc_policy=adc_power_policy()
    add(adc,published['area_mm2']*1e6*32,conversions*energy/1e6,
        adc_policy['value']*energy/service_ns*idle_lane_ms,count=32,
        note=adc['assumptions'],
        details={'event_energy_pj':energy,'one_lane_area_um2':published['area_mm2']*1e6,
            'conversions':conversions,'occupied_lane_ms':occupied,'idle_lane_ms':idle_lane_ms,
            'scheduled_service_ns':scheduled_ns,'adc_idle_fraction':adc_policy['value'],
            'adc_standby_assumption':adc_policy['description'],'adc_standby_source':adc_policy['source']})
    mux = original['analog_mux']; columns = sum(a['columns'] for a in arrays)
    area = columns*(2*v('C26')+v('D28')/v('C5'))+33*v('C40')
    reference_mw = 32*sources['workbook']['cells']['ADC']['D9']['value']+.52
    add(mux,area,mux['dynamic_energy_uj'],reference_mw*t,
        note='One route per installed column; 32 ADC reference buffers plus common bias. Source voltages retained; 12-bit accuracy unvalidated.')
    digital_ids = set(cases) | set(LANES)
    base_area = sum(r['area_um2'] for r in rows)
    routing=interconnect_budget(ops,sum(r['dynamic_energy_uj'] for r in rows if r['id'] in digital_ids),bus_bits=neural['resources']['readout_bus_bits'])
    add(original['physical_overhead'],.15*base_area,routing['dynamic_energy_uj'],0,
        details=routing | {'base_area_um2':base_area,'area_fraction':.15},note=routing['boundary'])
    if len(rows)!=31 or len({r['id'] for r in rows})!=31: raise AssertionError('Incorrect physical ownership')
    total = sum(r['energy_uj'] for r in rows)
    return {'profile':COST_PROFILE,'scenario':scenario,'connected_synthesis':metadata(),
        'components':rows,'estimated_owners':len(rows),'latency_ms':t,
        'core_area_mm2':sum(r['area_um2'] for r in rows)/1e6,
        'core_energy_uj':total,'core_energy_mj':total/1000,'core_average_power_mw':total/t,
        'average_energy_uj_per_iteration':total/candidate['iterations'] if candidate['iterations'] else None,
        'average_energy_mj_per_iteration':total/1000/candidate['iterations'] if candidate['iterations'] else None,
        'iterations':candidate['iterations'],'whole_chip_energy_uj':None,'whole_chip_area_mm2':None,
        'excluded':reference_costs['excluded'],'status':'Connected digital synthesis estimates with disclosed residual-control and power assumptions; full-core physical validation remains open',
        'precision':reference_costs['precision'],
        'new_hardware':{'ucb_lanes':16,'adc_lanes':32,'candidate_operand_bits':4096,
            'adc_result_bits':1024,'readout_staging_bits':512,'readout_bus_bits':128,'accumulator_lanes':8,
            'connected_digital_area_source':'native65_synthesis','residual_controls':'engineering_allocation'},
        'cost_method':'Connected native65 digital area and vectorless power; one declared target22 conversion, native65 leakage and residual-control allocations. Super-T, ADC and SRAM sources retained.'}
