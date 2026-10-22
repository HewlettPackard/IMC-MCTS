# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Nonoverlapping, explicitly estimated owners for the revised core.
# SPDX-License-Identifier: MIT
from copy import deepcopy
import math
from core.architecture.adc_power_policy import adc_power_policy

from core.architecture.sram_costs import sram_accounting
from core.architecture.parallel_selection import LANES

GROUPS = {'Selection':('u_sel','cam_macro',*LANES),
    'Expansion + Backprop':('u_upd',),
    'Rollout':('cim_arrays','row_drivers','sample_hold','adc_lanes','analog_mux','u_nn'),
    'FSM + physical allowance':('top_level_glue','physical_overhead'),
    'Shared memory':('node_sram','child_sram','u_node_router','u_child_router')}

SCENARIOS = {
    'nominal':{'reserve':1.25,'ucb_reserve':1.01,'activity':0.5,'conductance':0.5,'physical':0.15,'adc':'published'},
    'low_reserve':{'reserve':1.0,'ucb_reserve':1.0,'activity':0.25,'conductance':0.25,'physical':0.10,'adc':'published'},
    'high_reserve':{'reserve':2.0,'ucb_reserve':1.05,'activity':1.0,'conductance':1.0,'physical':0.30,'adc':'published'},
    'neurosim_adc':{'reserve':1.25,'ucb_reserve':1.01,'activity':0.5,'conductance':0.5,'physical':0.15,'adc':'neurosim'}}


def estimate(model, sources, published, scenario='nominal'):
    p = SCENARIOS[scenario]
    board = model.board_size; cycles = model.cycles; elapsed_ms = cycles/500000
    if cycles <= 0: raise ValueError('A completed workload interval is required')
    for pool in ('node_sram','child_sram'):
        if model.memory.config[pool+'_bytes'] != sources['sram']['banks'][pool]*sources['sram']['bank_bytes']:
            raise ValueError('Installed SRAM and characterized banks disagree')
    catalog = sources['digital']['cases']; power = sources['power']['cases']
    scaling = sources['scaling']; af = scaling['area']['factor']; ef = scaling['dynamic_energy']['factor']
    ops = model.memory.operations; activity = model.block_active_cycles
    rows = []

    def add(key,name,count,area,dynamic,standby,source,assumptions,status='engineering_estimate',details=None):
        row = {'id':key,'component':name,'count':count,'counted':True,'scope':'preloaded_core',
            'area_um2':area,'dynamic_energy_uj':dynamic,'standby_energy_uj':standby,
            'energy_uj':dynamic+standby,'average_power_mw':(dynamic+standby)/elapsed_ms,
            'source':source,'assumptions':assumptions,'status':status,'details':details or {}}
        for k in ('area_um2','dynamic_energy_uj','standby_energy_uj'):
            assert math.isfinite(row[k]) and row[k]>=0,(key,k)
        rows.append(row)
        return row

    sram = sram_accounting(sources['sram'],ops,cycles)
    for key,pool in sram['pools'].items():
        add(key,key.replace('_',' ').title(),pool['banks'],pool['area_mm2']*1e6,
            pool['dynamic_energy_nj']/1000,pool['leakage_energy_nj']/1000,
            str(sram['source']),'Native 22 nm CACTI, all installed banks leak for the elapsed interval.',
            'native22_tool_estimate',pool)
    # Retain the 9x9 parent for smaller boards; above 9, use a disclosed whole-
    # parent board-area multiplier. It is a scenario, not per-size synthesis.
    geometry = max(1.0,board*board/81)
    cases = [('u_sel','Selection control and cache buffers','imc_cached_selector',p['reserve']*geometry),
        ('u_upd','Shared expansion and backprop control','imc_tree_update_v2',p['reserve']*geometry),
        ('top_level_glue','FSM and interconnect','imc_iteration_glue',p['reserve']*geometry),
        ('u_node_router','Node SRAM router','imc_sram_router_3bank',max(1,sources['sram']['banks']['node_sram']/3)),
        ('u_child_router','Child SRAM router','imc_sram_router_1bank',max(1,sources['sram']['banks']['child_sram']))]
    for key,name,case,mult in cases:
        d = catalog[case]; w = power[case]['powers_mw']
        dynamic = (w['idle_dynamic_mw']*cycles+(w['active_dynamic_mw']-w['idle_dynamic_mw'])*activity[key])/500000*ef*mult
        leak = w['leakage_mw']*elapsed_ms*mult
        add(key,name,1,d['area']['cell_um2']*af*mult,dynamic,leak,d['reports']['power_vectorless.rpt'],
            '65-to-22 area and dynamic-energy policy; native65 leakage proxy. Parent multiplier '+str(mult),
            details={'parent_multiplier':mult,'board_geometry_factor':geometry,'native65_area_um2':d['area']['cell_um2'],
                     'active_cycles':activity[key],'children_included':d['hierarchy']})
    d = catalog['imc_ucb_score']; w = power['imc_ucb_score']['powers_mw']
    for key in LANES:
        assert activity[key]%169==0
        scores = activity[key]//169
        # Preserve serial switching work per score when divider/sqrt overlap.
        work = (w['active_dynamic_mw']-w['idle_dynamic_mw'])*223*scores/500000*ef
        clock = w['idle_dynamic_mw']*elapsed_ms*ef
        mult = p['ucb_reserve']
        add(key,'UCB scorer '+key[-1].upper(),1,d['area']['cell_um2']*af*mult,
            (work+clock)*mult,w['leakage_mw']*elapsed_ms*mult,d['reports']['power_vectorless.rpt'],
            '223 serial busy cycles worth of non-clock switching per score; 169 actual busy cycles. Clock and native65 leakage over elapsed time. Control reserve covers two completion flags.',
            details={'scores':scores,'switch_work_energy_uj':work*mult,'clock_energy_uj':clock*mult,
                     'reserve':mult,'children_included':d['hierarchy']})
    d = catalog['imc_neural_sequencer']; w = power['imc_neural_sequencer']['powers_mw']
    acc = next(x for x in d['hierarchy'] if x['instance']=='u_accumulator')
    # Triple the old 32-slot accumulator's inclusive area as a conservative
    # allocation proxy for 96 slots, including extra decode/read mux circuitry.
    # Shared ALU is not physically replicated by the execution model.
    bit_area = acc['local_sequential_area_um2']/(32*32)
    extra_bits = (128-24)+64+1
    accumulator_banks = math.ceil(model.neural.profile['hidden_size']/32)
    native_area = d['area']['cell_um2']+(accumulator_banks-1)*acc['inclusive_area_um2']+extra_bits*bit_area
    mult = native_area/d['area']['cell_um2']*p['reserve']
    dynamic = (w['idle_dynamic_mw']*cycles+(w['active_dynamic_mw']-w['idle_dynamic_mw'])*activity['u_nn'])/500000*ef*mult
    add('u_nn','Neural digital control, registers and correction',1,native_area*af*p['reserve'],
        dynamic,w['leakage_mw']*elapsed_ms*mult,d['reports']['area_hier.rpt'],
        ('Old parent plus two extra 32-slot accumulator-area proxies, 169 added register bits and control reserve. Same one shared accumulator ALU. Power scaled by allocated area; no matching synthesis.' if accumulator_banks==3 else 'Old parent plus allocated 32-slot accumulator-area proxies, 169 added register bits and control reserve. Same one shared accumulator ALU. Power scaled by allocated area; no matching synthesis.'),
        details={'area_multiplier':mult,'added_register_bits':extra_bits,'native65_proxy_area_um2':native_area,
                 'resources':model.neural.schedule['resources'],'children_included':d['hierarchy']})
    cam = sources.get('selected_cam',sources['tools']['cam']['cam_1024_lstp'])
    search = ops.get('cam_searches',0); read = ops.get('cam_output_ids',0)
    writes = ops.get('cam_filled_rows',0)+ops.get('cam_evicted_rows',0)
    add('cam_macro','CAM key/payload macro',1,cam['area_um2'],
        (search*cam['search_energy_nj']+read*cam['read_energy_nj']+writes*cam['write_energy_nj'])/1000,
        cam['leakage_mw']*elapsed_ms,cam['source'],'Native 22 nm CACTI associative-cache proxy; all-match interface approximated.',
        'native22_tool_proxy',{'rows':model.memory.config['cam_entries'],'physical_rows':cam.get('entries',1024),'key_bits':36,'payload_bits':32})
    cells = sources['workbook']['cells']['New_Architecture']; v = lambda k:cells[k]['value']
    profile = model.neural.profile; schedule = model.neural.schedule; trace = schedule['trace']
    arrays = profile['arrays']; lanes = 8; conversions = ops.get('neural_adc_conversions',0)
    assert conversions % schedule['operations']['adc_conversions']==0
    evaluations = conversions//schedule['operations']['adc_conversions']
    input_a = p['activity']; mean_g = p['conductance']; read_v = v('L15'); ron = v('L14')*1e6
    array_pj = driver_pj = 0; bursts = 0
    for i,r in enumerate(trace):
        if r['operation']!='dac_bit_drives': continue
        end = r['end']
        for next_row in trace[i+1:]:
            if next_row['operation']=='dac_bit_drives': break
            if next_row['operation']=='shift_adds': end = next_row['end']
        count = r['active_rows'][1]-r['active_rows'][0]
        cols = arrays[r['array_id']]['columns']; on = end-r['start']; bursts += 1
        array_pj += count*input_a*cols*(v('O16')+v('O17'))*read_v**2/1000
        array_pj += count*input_a*cols*mean_g/ron*read_v**2*on*2*1000
        driver_pj += count*(2*input_a*v('O26')+v('P31')/v('C13')/v('C5'))
    physical_rows = sum(a['rows'] for a in arrays); columns = sum(a['columns'] for a in arrays)
    add('cim_arrays','8-bit 1T1M cell arrays',2,sum(a['cells'] for a in arrays)*v('C14'),
        array_pj*evaluations/1e6,0,'Mentor workbook New_Architecture C14,L14:L15,O16:O17',
        'One cell per weight, workbook cell geometry proxy. Mean activity/conductance with sustained drive. Idle bias off; off-current omitted. 256 reliable levels unvalidated.',
        details={'arrays':arrays,'input_activity':input_a,'mean_conductance':mean_g,'bursts_per_evaluation':bursts})
    driver_idle = physical_rows*.05*(2*input_a*v('O26')+v('P31')/v('C13')/v('C5'))/2
    add('row_drivers','Binary row drivers and selection',physical_rows,
        physical_rows*(v('C26')*v('C27')+v('D28')/v('C5')),
        driver_pj*evaluations/1e6,driver_idle*elapsed_ms,
        'Mentor workbook C26:C27,D28,O26,P31','One installed driver per row; workbook load proxy, 5% standby allowance.')
    # Separate external conditioning/hold stage from the ADC's internal CDAC.
    cap = published['input_capacitance_ff']; cap_ratio = cap/v('C42')
    frontend_mw = 12*1.8/1000*cap_ratio
    sample_area = cap/v('C41')+2*v('C26')+v('C40')*cap_ratio
    sample_pj = frontend_mw*(1-.05)*15*2 + cap*read_v**2/1000
    add('sample_hold','External conditioning and sample/hold',lanes,lanes*sample_area,
        conversions*sample_pj/1e6,lanes*frontend_mw*.05*elapsed_ms,
        'Mentor workbook C26,C40:C43,O40,U40; published ADC input capacitance',
        '970 fF external hold-cap budget; amplifier area/bias scale with load relative to old 85 fF proxy. 15 cycles acquisition+hold. Settling/noise not validated; ADC internal CDAC counted only in ADC.')
    if p['adc']=='published':
        area = published['area_mm2']*1e6; energy = published['energy_pj']; service_ns = 1000/published['sample_rate_msps']
        source = published['url']; status = 'unshrunk_native65_ADC_budget_for_22nm_target'
        note = 'Retain source 65 nm, 1.2 V area and energy as an analog macro budget. No unjustified geometric shrink. 10.9 ENOB is not ideal 12-bit conversion proof.'
    else:
        adc = sources['neurosim_adc12']; area = adc['area_um2']; energy = adc['energy_pj']; service_ns = adc['latency_ns']
        source = 'Pinned NeuroSim 12-bit native22 probe'; status = 'uncalibrated_tool_sensitivity_only'
        note = 'Exploratory NeuroSim extrapolation; transistor-area model and current-input energy differ from published voltage ADC. Not a confidence bound.'
    # Separate conversion events and nonconverting standby, no double count.
    occupied_lane_ms = conversions*26/1e6
    idle_lane_ms = max(0,lanes*elapsed_ms-occupied_lane_ms)
    add('adc_lanes','12-bit ADC lanes',lanes,lanes*area,conversions*energy/1e6,
        adc_power_policy()['value']*energy/service_ns*idle_lane_ms,source,
        note+' Default ADC standby allowance: 25% of published active power during nonconverting lane time (engineering assumption, not measured standby); startup calibration excluded.',status,
        {'event_energy_pj':energy,'one_lane_area_um2':area,'conversions':conversions,
         'occupied_lane_ms':occupied_lane_ms,'idle_lane_ms':idle_lane_ms,'scheduled_service_ns':26})
    mux_area = columns*(2*v('C26')+v('D28')/v('C5'))+(lanes+1)*v('C40')
    reference_mw = lanes*sources['workbook']['cells']['ADC']['D9']['value']+.52
    add('analog_mux','Column mux, references and common bias',columns,mux_area,
        conversions*2*v('O26')/1e6,reference_mw*elapsed_ms,
        'Mentor workbook C26,C40,D28,O26,Q56; ADC D9',
        'One route per installed column, eight reference buffers plus common bias. Source voltages retained; 12-bit accuracy unvalidated.')
    digital_owners = {'u_sel','u_upd','top_level_glue','u_node_router','u_child_router','u_nn',*LANES}
    base_area = sum(r['area_um2'] for r in rows)
    # Clock/routing allowance on digital dynamic only, not an extra leakage tax.
    wire_energy = .10*sum(r['dynamic_energy_uj'] for r in rows if r['id'] in digital_owners)
    add('physical_overhead','Physical area and distribution allowance',1,p['physical']*base_area,
        wire_energy,0,'Workbook D97; explicit clock/wire engineering assumption',
        str(p['physical']*100)+'% area on installed base once; 10% of digital dynamic energy. No extracted routing or clock tree.',
        details={'base_area_um2':base_area,'area_fraction':p['physical'],'dynamic_fraction':.10})
    owners = [key for keys in GROUPS.values() for key in keys]
    assert len(rows)==len(owners)==len(set(owners))==19
    assert set(r['id'] for r in rows)==set(owners)
    return {'profile':'revised_core_engineering_estimates_v1','scenario':scenario,
        'components':rows,'core_area_mm2':sum(r['area_um2'] for r in rows)/1e6,
        'core_energy_uj':sum(r['energy_uj'] for r in rows),
        'core_average_power_mw':sum(r['average_power_mw'] for r in rows),
        'latency_ms':elapsed_ms,'estimated_owners':19,'missing_owners':[],
        'status':'All scoped owners estimated; physical and analog correctness unvalidated',
        'whole_chip_area_mm2':None,'whole_chip_energy_uj':None,
        'excluded':['Host Go rules and metadata','Host I/O, pads and ESD','Weight programming, preload and ADC startup calibration'],
        'precision':'Ideal cell-code arithmetic; source ADC achieved 10.9 ENOB, not ideal 12-bit accuracy',
        'power_activity':'Vectorless digital activity plus modeled operations and mean analog activity; seed variation is not measured switching.'}
