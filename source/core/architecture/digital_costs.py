# Native module reports and nonoverlapping installed hardware costs.
# SPDX-License-Identifier: MIT
import hashlib
from copy import deepcopy
import json
import math
from pathlib import Path
import re

from core.architecture.analog_readout import BUFFERED, readout_spec
from core.architecture.tree_update_timing import PROFILE as TREE_UPDATE_PROFILE, EXTRA_EXPANSION_CYCLES
from core.architecture.cost_ledger import scaling_policy
from core.architecture.controller_estimates import ASSUMPTIONS as CONTROLLER_ESTIMATES, controller_estimate
from py_sst_cpp.components.board_config import BoardSize, get_board_config

ROOT=Path(__file__).resolve().parents[2]
CHARACTERIZATION=Path(__file__).with_name('digital_characterization.json')
AREA_FACTOR=scaling_policy()['area']['factor']
REPORTS=('run_details.txt','area.rpt','area_hier.rpt','qor.rpt',
    'power_vectorless.rpt','constraints.rpt','check_design_postcompile.rpt','synthesis.log')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(text, label):
    match=re.search(r'^\s*'+re.escape(label)+r'\s*:\s*([-+\d.eE]+)',text,re.M)
    if match is None: raise ValueError('Missing report field: '+label)
    value=float(match[1])
    if not math.isfinite(value): raise ValueError('Nonfinite report field: '+label)
    return value


def power_mw(text, label):
    match=re.search(re.escape(label)+r'\s*=\s*([-+\d.eE]+)\s+([munp]?W)\b',text)
    if match is None: raise ValueError('Missing power field: '+label)
    value=float(match[1])*{'W':1000,'mW':1,'uW':.001,'nW':1e-6,'pW':1e-9}[match[2]]
    if not math.isfinite(value) or value<0: raise ValueError('Invalid power: '+label)
    return value


def build_characterization(source, verify_all=True):
    source=Path(source).resolve()
    if not source.is_relative_to(ROOT): raise ValueError('Synthesis import must be inside the repair project')
    manifest_path=source/'import_manifest.json'
    manifest=json.loads(manifest_path.read_text())
    consumed={str(manifest_path.relative_to(ROOT)):digest(manifest_path)}

    def checked(name):
        original=source/name; path=original.resolve()
        if not path.is_relative_to(source) or original.is_symlink() or digest(path)!=manifest['files'][name]:
            raise ValueError('Synthesis import hash mismatch: '+name)
        consumed[str(path.relative_to(ROOT))]=manifest['files'][name]
        return path

    if verify_all:
        for name in manifest['files']: checked(name)
        # Large netlists/DDCs are retained in the import, not repeated in every run.
        consumed={str(manifest_path.relative_to(ROOT)):digest(manifest_path)}
    for name in ('synth/run_dc.tcl','filelist.f'): checked(name)
    script=checked('synth/run_all.sh').read_text().replace('\\\n',' ')
    expected={}
    for case,top,params,sequential in re.findall(r'^run_one (\w+) (\w+)\s+"([^"]*)" ([01])',script,re.M):
        expected[case]={'top':top,'parameters':dict((k,int(v)) for k,v in
            (item.split('=') for item in params.split(',') if item)), 'sequential':sequential=='1'}
    if not expected: raise ValueError('No synthesis cases in the supplied run script')
    # The root tree-update report is historical. Its replacement has a separate
    # source packet and case name, even though both modules have the same top.
    for name in sorted(n for n in manifest['files'] if n.endswith('.sv') and '/' not in n):
        checked(name)
        if name=='imc_tree_update.sv': continue
        matches=list((ROOT/'rtl_synthesis').glob('*/p00_rtl/'+name))
        if len(matches)!=1 or digest(matches[0])!=manifest['files'][name]:
            raise ValueError('Synthesized RTL no longer matches the repair project: '+name)
        consumed[str(matches[0].relative_to(ROOT))]=manifest['files'][name]
    folders=list((source/'results').iterdir())
    packet='p00_tree_update_v2/'
    if packet+'VALIDATION.json' in manifest['files']:
        handoff=json.loads(checked(packet+'VALIDATION.json').read_text())
        bindings={'imc_round_divider.sv':'p01_mapped_core','imc_q17_codec.sv':'p03_iteration_core',
            'imc_tree_update.sv':'p03_iteration_core'}
        if set(handoff['rtl_sha256'])!=set(bindings) or set(checked(packet+'filelist.f').read_text().splitlines())!=set(bindings):
            raise ValueError('Unexpected tree-update dependency list')
        if handoff['added_cycles_per_nonempty_expansion']!=EXTRA_EXPANSION_CYCLES or handoff['extra_sram_transactions']!=0:
            raise ValueError('Tree-update schedule differs from characterized revision')
        for name,owner in bindings.items():
            rtl=checked(packet+name); active=ROOT/'rtl_synthesis'/owner/'p00_rtl'/name
            if digest(rtl)!=handoff['rtl_sha256'][name] or digest(active)!=digest(rtl):
                raise ValueError('Synthesized tree-update v2 RTL no longer matches the repair project: '+name)
            consumed[str(active.relative_to(ROOT))]=digest(active)
        for record in handoff['validation'].values():
            metadata=ROOT/record['run']/'metadata.json'
            if not metadata.resolve().is_relative_to(ROOT) or digest(metadata)!=record['metadata_sha256']:
                raise ValueError('Tree-update handoff evidence identity changed')
            consumed[str(metadata.relative_to(ROOT))]=digest(metadata)
        expected['imc_tree_update_v2']={'top':handoff['top'],'parameters':handoff['parameters'], 'sequential':True}
        folders.extend((source/packet/'results').iterdir())
    glue_names={}
    packet='p01_power_activity/'
    if packet+'VALIDATION.json' in manifest['files']:
        released=json.loads(checked(packet+'manifest.json').read_text())
        validation=json.loads(checked(packet+'VALIDATION.json').read_text())
        if validation['status']!='local_validation_passed': raise ValueError('Unverified glue packet')
        proof=validation['proofs']['glue']; evidence=ROOT/proof['run']/'metadata.json'
        if not evidence.resolve().is_relative_to(ROOT) or digest(evidence)!=proof['metadata_sha256']:
            raise ValueError('Glue reconstruction evidence changed')
        consumed[str(evidence.relative_to(ROOT))]=digest(evidence)
        replay=json.loads(evidence.read_text()); tested=evidence.parent.parents[1]
        if replay['status']!='passed' or len(replay['results'])!=4 or digest(tested/'manifest.json')!=replay['packet_manifest_sha256']:
            raise ValueError('Incomplete glue reconstruction proof')
        consumed[str((tested/'manifest.json').relative_to(ROOT))]=digest(tested/'manifest.json')
        for name,sha in released['source_sha256'].items():
            if not name.endswith(('.sv','.vh')): continue
            active=ROOT/name
            if not active.resolve().is_relative_to(ROOT) or digest(active)!=sha:
                raise ValueError('Glue packet RTL differs from active sources: '+name)
            consumed[name]=sha
        for top in ('imc_iteration_glue','imc_buffered_iteration_glue'):
            rtl=checked(packet+'p04_glue/'+top+'.sv')
            original=tested/'p04_glue'/rtl.name
            if digest(rtl)!=digest(original): raise ValueError('Glue source differs from reconstructed proof')
            consumed[str(original.relative_to(ROOT))]=digest(original)
        checked(packet+'p05_flow/synth_glue.tcl')
        for folder in sorted((source/packet/'p06_runs').glob('glue_*')):
            details=dict(line.split('=',1) for line in checked(str((folder/'run_details.txt').relative_to(source))).read_text().splitlines() if '=' in line)
            top=details['top']
            if top not in ('imc_iteration_glue','imc_buffered_iteration_glue'): raise ValueError('Unknown glue top')
            if details.get('scope')!='top_level_glue_only_children_excluded' or details.get('packet_manifest_sha256')!=digest(source/packet/'manifest.json'):
                raise ValueError('Glue scope or packet identity mismatch')
            if details.get('packet_sha256sum_validation')!='PASS' or not re.fullmatch('[0-9a-f]{64}',details.get('library_sha256','')):
                raise ValueError('Missing glue library/packet provenance')
            netlist=checked(str((folder/'mapped.v').relative_to(source))).read_text()
            if re.findall(r'^\s*module\s+(\w+)',netlist,re.M)!=[top]: raise ValueError('Glue netlist includes unexpected hierarchy')
            expected[top]={'top':top,'parameters':{'BOARD_SIZE':9,'HIDDEN':96,'CAM_ENTRIES':1024,'ADDR_W':21},
                'sequential':True,'ownership':'Glue only; six installed parents excluded'}
            glue_names[folder.name]=top; folders.append(folder)
    cases={}
    for folder in sorted(folders):
        if not folder.is_dir(): continue
        case=glue_names.get(folder.name,folder.name); is_glue=folder.name in glue_names
        if case not in expected: raise ValueError('Unexpected synthesis case: '+case)
        if case in cases: raise ValueError('Duplicate synthesis case: '+case)
        names=tuple(n for n in REPORTS if n!='area_hier.rpt')+('units.rpt',) if is_glue else REPORTS
        reports={name:checked(str((folder/name).relative_to(source))).read_text() for name in names}
        details=dict(line.split('=',1) for line in reports['run_details.txt'].splitlines() if '=' in line)
        spec=expected[case]
        params=dict((k,int(v)) for k,v in (item.split('=') for item in details['parameters'].split(',') if item))
        if details['top']!=spec['top'] or params!=spec['parameters']:
            raise ValueError('Report parameters differ from run script: '+folder.name)
        required={'technology':'TSMC 65nm','area_unit':'square micrometers','time_unit':'1 ns',
            'capacitance_unit':'1 pF','power':'vectorless; no workload activity supplied'}
        if is_glue: required['power']+='; diagnostic only'
        if any(details.get(k)!=v for k,v in required.items()): raise ValueError('Unsupported report units or method: '+folder.name)
        area=reports['area.rpt']; power=reports['power_vectorless.rpt']; qor=reports['qor.rpt']
        designs=[re.search(r'^Design\s*:\s*(\S+)',reports[n],re.M)[1] for n in ('area.rpt','power_vectorless.rpt','qor.rpt')+(('units.rpt',) if is_glue else ('area_hier.rpt',))]
        expected_design=spec['top'] if is_glue else spec['top']+''.join('_'+k+str(v) for k,v in params.items())
        if set(designs)!={expected_design}: raise ValueError('Mismatched report design: '+folder.name)
        corner=re.search(r'Operating Conditions:\s*(\S+)\s+Library:\s*(\S+)',power)
        if corner is None or corner[1]!=details['corner'] or corner[2]!=details['library']+'_'+details['corner']:
            raise ValueError('Mismatched library/PVT: '+folder.name)
        voltage=re.search(r'Global Operating Voltage\s*=\s*([\d.]+)',power)
        if voltage is None or float(voltage[1])!=float(details['voltage'].split()[0]): raise ValueError('Voltage mismatch: '+folder.name)
        if re.search(r'^\s*Error:',reports['synthesis.log'],re.M): raise ValueError('Synthesis error: '+folder.name)
        cell_area=number(area,'Total cell area')
        if cell_area<=0 or number(area,'Number of macros/black boxes')!=0:
            raise ValueError('Missing cells or unpriced black box: '+folder.name)
        if not math.isclose(cell_area,number(qor,'Cell Area'),abs_tol=.00001): raise ValueError('Area and QoR reports disagree')
        hierarchy=[]
        for line in reports.get('area_hier.rpt','').splitlines():
            fields=line.split()
            if len(fields)!=7 or fields[0]==expected_design: continue
            try: global_area,percent,comb,seq,black=map(float,fields[1:6])
            except ValueError: continue
            hierarchy.append({'instance':fields[0],'design':fields[6],'inclusive_area_um2':global_area,
                'local_combinational_area_um2':comb,'local_sequential_area_um2':seq,'local_black_box_area_um2':black})
        warning_codes=sorted(set(re.findall(r'\(([A-Z]+-\d+)\)', '\n'.join(line for name in
            ('synthesis.log','power_vectorless.rpt','check_design_postcompile.rpt') for line in reports[name].splitlines() if line.startswith('Warning:')))))
        constraint_types=sorted(set(re.findall(r'^   ([a-z_]+)\s*$',reports['constraints.rpt'],re.M)))
        cases[case]=spec | {
            'rtl_status':'historical_replaced_by_v2' if folder.name=='imc_tree_update' else 'matches_active_sources',
            'design':expected_design,'source_node_nm':65,'environment':details,
            'area':{'cell_um2':cell_area,'combinational_um2':number(area,'Combinational area'),
                'sequential_um2':number(area,'Noncombinational area'),
                'units_basis':'run_details.txt declaration; no report_units or library hash supplied',
                'status':'Standalone mapped standard cells; wire-load estimate, no physical layout'},
            'hierarchy':hierarchy,
            'power':{'method':'vectorless','source_node_nm':65,'voltage_v':float(details['voltage'].split()[0]),
                'dynamic_mw':power_mw(power,'Total Dynamic Power'),
                'internal_mw':power_mw(power,'Cell Internal Power'),'switching_mw':power_mw(power,'Net Switching Power'),
                'leakage_mw':power_mw(power,'Cell Leakage Power'),
                'workload_energy_uj':None,'target_22nm_power_mw':None,
                'status':'Unannotated switching; includes register clock-pin power. Diagnostic only, no workload or 22 nm adoption.'},
            'timing':{'constraint_ns':float(details['clock_period_ns']),
                'constraint_kind':'clock period' if spec['sequential'] else 'input-to-output max delay',
                'critical_path_ns':number(qor,'Critical Path Length'),
                'critical_slack_ns':number(qor,'Critical Path Slack'),
                'violating_setup_paths':int(number(qor,'No. of Violating Paths')),
                'status':'Rounded standalone synthesis timing at 65 nm; system/22 nm closure unvalidated'},
            'checks':{'max_capacitance_violations':int(number(qor,'Max Cap Violations')),
                'max_transition_violations':int(number(qor,'Max Trans Violations')),
                'constraint_categories':constraint_types,'warning_codes':warning_codes,
                'check_design_return':reports['check_design_postcompile.rpt'].strip().splitlines()[-1],
                'status':'Reports retained with warnings; no physical signoff claim'},
            'reports':{name:str((folder/name).relative_to(ROOT)) for name in names}}
        if is_glue:
            if number(qor,'Hierarchical Cell Count')!=0 or number(area,'Number of sequential cells')<=0:
                raise ValueError('Glue contains children or lost its state')
            for label in ('1.0e-09 Second(ns)','1.0e-12 Farad(pF)','1 Volt'):
                if label not in reports['units.rpt']: raise ValueError('Glue report units mismatch')
            if float(details['clock_period_ns'])!=2 or float(details['voltage'].split()[0])!=1 or details['temperature']!='25 C':
                raise ValueError('Glue operating point differs from characterized modules')
            lint=set(re.findall(r'\((LINT-\d+)\)',reports['check_design_postcompile.rpt']))
            if lint-{'LINT-29','LINT-31','LINT-52'}: raise ValueError('Unreviewed postcompile glue warning')
            categories={}; category=None
            for line in reports['constraints.rpt'].splitlines():
                match=re.fullmatch(r'   ([a-z_]+)\s*',line)
                if match: category=match[1]; categories[category]=0
                elif '(VIOLATED' in line:
                    if category is None: raise ValueError('Constraint violation without category')
                    categories[category]+=1
            cases[case]['checks']['constraint_violation_counts']=categories
            cases[case]['checks']['warning_notes']='Projected boundary has feedthrough, shared-output and constant aliases; multiport and zero-leakage-objective violations retained. Physical signoff is not established.'
            cases[case]['area']['units_basis']='Native report_units plus declared square-micrometer cell area; library SHA-256 recorded in run_details.txt'
    return {'schema_version':3 if glue_names else 2,'profile':'tsmc65_modules_tree_update_v2'+('_glue_v1' if glue_names else ''),
        'source_import':str(source.relative_to(ROOT)),'repository':manifest['repository'],'commit':manifest['commit'],
        'source_files':dict(sorted(consumed.items())), 'cases':cases,
        'missing_cases':sorted(set(expected)-set(cases)),
        'area_conversion':{'source_node_nm':65,'target_node_nm':22,'factor':AREA_FACTOR,'applications':1,
            'method':'Geometric standard-cell area estimate; not a 22 nm synthesis or layout result'},
        'power_conversion':{'applications':0,'factor':None,'status':'No validated 65-to-22 power model supplied'}}


def load_digital_profile():
    profile=json.loads(CHARACTERIZATION.read_text())
    expected=build_characterization(ROOT/profile['source_import'],verify_all=False)
    if profile!=expected: raise ValueError('Digital characterization differs from its source reports')
    profile['profile_sha256']=digest(CHARACTERIZATION)
    return profile


def digital_source_files():
    profile=load_digital_profile()
    return [CHARACTERIZATION,CONTROLLER_ESTIMATES]+[ROOT/name for name in profile['source_files']]


def digital_accounting(neural_profile, memory_config=None, operations=None, phase_cycles=None):
    profile=load_digital_profile()
    board=neural_profile['board_size']
    memory={'cam_entries':get_board_config(BoardSize(board)).cam_entries,
        'neural_bytes':neural_profile['storage_bytes'],'node_sram_bytes':1572864,'child_sram_bytes':524288}
    if memory_config is not None: memory.update(memory_config)
    bank_bytes = 524288
    address_bits = 21
    if memory.get('hardware_profile') == 'board_sized_s1_v1':
        from core.architecture.board_sizing import board_hardware
        shape = board_hardware(board)
        bank_bytes = shape['sram_bank_kib']*1024
        if (memory['node_sram_bytes'],memory['child_sram_bytes'],memory['cam_entries']) != (shape['node_sram_kib']*1024,shape['child_sram_kib']*1024,shape['cam_entries']):
            raise ValueError('Hardware costs do not match the board-sizing table')
        address_bits = max(21,(max(memory['node_sram_bytes'],memory['child_sram_bytes'])-1).bit_length())
    if any(type(memory[k]) is not int or memory[k]<=0 or memory[k]%bank_bytes for k in ('node_sram_bytes','child_sram_bytes')):
        raise ValueError('Digital router costs require whole 512 KiB banks')
    tree_params={'BOARD_SIZE':board,'CAM_ENTRIES':memory['cam_entries'],'NEURAL_BYTES':memory['neural_bytes'],'ADDR_W':address_bits}
    neural_params={'INPUTS':neural_profile['input_size'],'HIDDEN':neural_profile['hidden_size'],
        'ADDR_W':address_bits,'SRAM_BYTES':memory['node_sram_bytes']}
    buffered=readout_spec(neural_profile.get('readout',{}).get('profile','sustained_drive_v1'))['profile']==BUFFERED
    neural='imc_buffered_neural_sequencer' if buffered else 'imc_neural_sequencer'
    router={'BANK_BYTE_W':bank_bytes.bit_length()-1,'ADDR_W':address_bits}
    phases=['selection','expansion','neural','backpropagation','iteration_commit']
    blocks=[
        ('u_sel','Selection controller and digital cache buffers','imc_cached_selector',tree_params,['selection']),
        ('u_ucb','UCB arithmetic and lookup tables','imc_ucb_score',{},['selection']),
        ('u_nn','Neural controller, accumulation, scaling and divider',neural,neural_params,['neural']),
        ('u_upd','Expansion and backpropagation controller','imc_tree_update_v2',tree_params,['expansion','backpropagation']),
        ('u_node_router','Node SRAM router','imc_sram_router_3bank',router | {'BANKS':memory['node_sram_bytes']//bank_bytes},phases[:-1]),
        ('u_child_router','Child SRAM router','imc_sram_router_1bank',router | {'BANKS':memory['child_sram_bytes']//bank_bytes},['selection','expansion','backpropagation']),
        ('top_level_glue','Iteration orchestration, arbitration and interconnect',
            'imc_buffered_iteration_glue' if buffered else 'imc_iteration_glue',
            {'BOARD_SIZE':board,'HIDDEN':neural_profile['hidden_size'],'CAM_ENTRIES':memory['cam_entries'],'ADDR_W':address_bits},phases)]
    components=[]
    fixed_geometry={'outputs':3,'array_rows':256,'array_columns':128,'active_rows':16,
        'adc_lanes':3,'adc_bits':8,'dac_bits':1,'weight_bits':8,'cell_bits':4,
        'weight_slices':2,'sign_branches':2,'hidden_bits':8,'accumulator_bits':32,'divider_numerator_bits':48}
    for instance,name,case,parameters,owners in blocks:
        record=profile['cases'].get(case)
        compatible=record is not None and record['parameters']==parameters
        update_mismatch=instance in ('u_upd','top_level_glue') and memory_config is not None and memory_config.get('tree_update_timing_profile')!=TREE_UPDATE_PROFILE
        tree_memory_mismatch=instance in ('u_sel','u_upd','top_level_glue') and (memory['node_sram_bytes'],memory['child_sram_bytes'])!=(1572864,524288)
        if instance=='top_level_glue' and memory['neural_bytes']!=16512: tree_memory_mismatch=True
        geometry_mismatch=instance in ('u_nn','top_level_glue') and any(neural_profile.get(k)!=v for k,v in fixed_geometry.items())
        incremental_mismatch=instance in ('u_sel','u_upd','top_level_glue') and memory.get('policy')=='evaluate_root_then_single_untried_child_v1'
        compatible=compatible and not geometry_mismatch and not update_mismatch and not tree_memory_mismatch and not incremental_mismatch
        row={'component':name,'instance':instance,'count':1,'case':case,'parameters_required':parameters,
            'owner_phases':owners,'area_um2':None,'native_65nm_area_um2':None,
            'source_node_nm':65,'target_node_nm':22,'scaling_applications':0,
            'source':None if record is None else record['reports']['area.rpt'],
            'status':'Missing module report' if record is None else 'Parameter mismatch; available '+str(record['parameters']),
            'includes':[],'native_65nm_power':None,'timing':None,'checks':None}
        if geometry_mismatch: row['status']='Neural geometry or precision differs from synthesized RTL'
        if update_mismatch: row['status']='Tree-update schedule differs from characterized v2 RTL'
        if tree_memory_mismatch: row['status']='SRAM capacities differ from synthesized NODE_BYTES/CHILD_BYTES defaults'
        if incremental_mismatch: row['status']='Single-child action/link layout and controller schedule need matching RTL characterization; excluded from known totals'
        if compatible:
            row.update(area_um2=record['area']['cell_um2']*AREA_FACTOR,native_65nm_area_um2=record['area']['cell_um2'],
                scaling_applications=1,status='65 nm synthesis, geometrically scaled to 22 nm; standalone estimate',
                includes=record['hierarchy'],native_65nm_power=record['power'],timing=record['timing'],checks=record['checks'])
            if record['timing']['violating_setup_paths'] or record['timing']['critical_slack_ns']<0:
                row['status']+='; reported area at failed native setup timing'
            if instance=='top_level_glue': row['status']+='; coordination logic only, child modules excluded'
        elif not any(neural_profile.get(k)!=v for k,v in fixed_geometry.items()):
            proxy=controller_estimate(instance,record,neural_profile,memory)
            if proxy is not None:
                row.update(area_um2=record['area']['cell_um2']*proxy['multiplier']*AREA_FACTOR,
                    scaling_applications=1,report_proxy=proxy,
                    status='Engineering report proxy with 25% whole-parent allowance; not matching synthesis. '+proxy['basis'])
        components.append(row)
    violations=[{'instance':row['instance'],'case':row['case'],'source_node_nm':65,
        'constraint_ns':row['timing']['constraint_ns'],'critical_slack_ns':row['timing']['critical_slack_ns'],
        'violating_setup_paths':row['timing']['violating_setup_paths']}
        for row in components if row.get('timing') and
        (row['timing']['violating_setup_paths'] or row['timing']['critical_slack_ns']<0)]
    result={'profile':profile['profile'],'profile_sha256':profile['profile_sha256'],'source_commit':profile['commit'],
        'status':'partial_module_area_estimate','components':components,
        'priced_instances':sum(row['area_um2'] is not None for row in components),
        'known_native_65nm_area_um2':sum(row['native_65nm_area_um2'] or 0 for row in components),
        'known_area_mm2':sum(row['area_um2'] or 0 for row in components)/1e6,
        'whole_digital_area_mm2':None,'power_mw':None,'energy_uj':None,
        'timing_violations':violations,
        'area_conversion':profile['area_conversion'],'power_conversion':profile['power_conversion'],
        'accounting':'One installed instance per parent; children already included. Expansion/backpropagation share u_upd; phases and iterations do not replicate hardware.',
        'activity_status':'Owner phase cycles overlap across cooperating blocks; these are not measured switching, gating or additive latency.',
        'power_status':'Native 65 nm vectorless reports are diagnostics only; 22 nm digital workload energy and power remain uncharacterized.',
        'timing_status':('Native 65 nm setup timing failed for '+', '.join(row['case'] for row in violations)+'. ' if violations else '')+
            'Latency uses the RTL-checked schedule at an assumed 500 MHz; 22 nm clock closure is unvalidated. No scaling of delay.'}
    if memory.get('policy')=='evaluate_root_then_single_untried_child_v1':
        result['timing_status']='Single-child architectural service estimate at assumed 500 MHz; incremental controller and physical timing are not RTL validated'
    proxies=[row['instance'] for row in components if row.get('report_proxy')]
    if proxies:
        result.update(status='module_area_estimate_with_controller_proxies',report_proxy_instances=proxies,
            controller_estimate_sha256=next(row['report_proxy']['sha256'] for row in components if row.get('report_proxy')))
    return digital_activity(result,operations,phase_cycles)


def digital_activity(digital, operations=None, phase_cycles=None):
    result=deepcopy(digital)
    for row in result['components']:
        instance=row['instance']
        if phase_cycles is not None:
            row['owner_phase_cycles']=sum(phase_cycles.get(phase,0) for phase in row['owner_phases'])
        if operations is not None:
            if instance=='u_ucb': row['requests']=operations.get('ucb_operations',0)
            if instance in ('u_node_router','u_child_router'):
                pool='node_sram' if instance=='u_node_router' else 'child_sram'
                row['word_requests']={op:operations.get(pool+'_'+op+'_words',0) for op in ('read','write')}
    return result


def digital_timing_fields(digital):
    violations=None if digital is None else digital.get('timing_violations')
    return {'digital_65nm_setup_violating_paths':None if violations is None else sum(row['violating_setup_paths'] for row in violations),
        'digital_65nm_timing_failed_modules':None if violations is None else ';'.join(row['case'] for row in violations),
        'digital_65nm_timing_status':None if violations is None else
            ('reported_setup_failure' if violations else 'no_reported_failure_in_priced_modules')}
