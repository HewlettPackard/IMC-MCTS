# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Immutable simulator runs and one current record per named canonical case.
# SPDX-License-Identifier: MIT
import argparse
from datetime import datetime, timezone
import csv
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import tarfile
import time

import numpy as np

from core.architecture.complete_costs import complete_costs
from core.architecture import studio_current as current
from core.architecture.cost_ledger import POLICY, ledger_fields
from core.architecture.digital_costs import digital_source_files, digital_timing_fields
from core.architecture.block_activity import activity_record
from core.architecture.block_power import power_source_files, write_power_csv
from core.architecture.peripheral_costs import peripheral_sources
from core.architecture.component_inventory import write_component_csv
from core.architecture.analog_readout import DRIVEN, BUFFERED, configure_readout, controller_profile, readout_spec, readout_activity
from core.architecture.column_hold_validation import VALIDATION as BUFFER_VALIDATION, TIMING_STATUS, validate_buffered_sources, validate_source_extension
from core.algorithm.model_catalog import load_model, model_record, model_sources
from core.architecture.crossbar_workbook import component_estimates, SOURCES, PROVENANCE
from core.architecture.go_simulation import GoSimulation, PROFILE as GO_PROFILE, TURN_PROFILE, RULES_SOURCE
from core.architecture.iteration_model import CompleteSimulation, PROFILE
from core.architecture.single_child import SingleChildSimulation, SingleChildGoSimulation, SingleChildPolicy
from core.architecture.single_child import PROFILE as SINGLE_PROFILE, GO_PROFILE as SINGLE_GO_PROFILE, TURN_PROFILE as SINGLE_TURN_PROFILE
from core.architecture.run_identity import build_run_identity, json_sha256, tree_sha256
from core.architecture.board_sizing import PROFILE as SIZED_HARDWARE, TABLE as SIZING_TABLE, CHARACTERIZATION as SIZED_CHARACTERIZATION
from core.architecture.board_sizing import board_hardware, memory_profile_name, memory_characterization
from core.architecture.sized_simulation import SizedSingleChildSimulation, SizedSingleChildGoSimulation

ROOT=Path(__file__).resolve().parents[2]
RESULTS=ROOT/'p04_results'
CASES=RESULTS/'p00_cases/cases.json'
RUNS=RESULTS/'p01_runs'


class RunCancelled(Exception): pass


def write_json(path, value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def catalog():
    result=json.loads(CASES.read_text())
    # Original placement cases omitted the then-default full-expansion profile.
    # Resolve those definitions explicitly without rewriting their stored bytes.
    for row in result['cases']:
        row['configuration'].setdefault('profile',PROFILE)
    return result


def configuration(value):
    allowed={'board_size','iterations','seed','initial_board','exploration','memory_limits','cam_entries','memory_profile','profile','model_id','model_perspective','rules','go_state','readout_profile','hardware_profile','component_parameters'}
    if not isinstance(value,dict) or set(value)-allowed: raise ValueError('Unknown case configuration fields')
    result={'board_size':9,'iterations':5000,'seed':0,'initial_board':None,'exploration':1.414,
        'memory_limits':{},'cam_entries':None,'memory_profile':'cacti_22nm_lstp','profile':PROFILE} | value
    rules=result.get('rules','placement')
    if rules not in ('placement','legacy_go'): raise ValueError('Unknown game rules')
    record=model_record(result.get('model_id','random_diagnostic'),result['board_size'])
    turn=bool(record and record.get('turn_indicator'))
    if turn and rules!='legacy_go': raise ValueError('Go-strong and Go-weak require Go rules')
    expected=GO_PROFILE if rules=='legacy_go' else PROFILE
    if turn: expected=TURN_PROFILE
    single=SINGLE_GO_PROFILE if rules=='legacy_go' else SINGLE_PROFILE
    if turn: single=SINGLE_TURN_PROFILE
    latest=current.is_current(result)
    if latest: current.validate_current(result)
    elif "component_parameters" in result: raise ValueError("Component parameters require the current architecture")
    sized=result.get('hardware_profile')==SIZED_HARDWARE
    if 'hardware_profile' in result and not sized: raise ValueError('Unknown installed hardware profile')
    if sized:
        shape=board_hardware(result['board_size'])
        if result['cam_entries'] is not None and (type(result['cam_entries']) is not int or result['cam_entries']!=shape['cam_entries']):
            raise ValueError('CAM override conflicts with selected board hardware')
        result['cam_entries']=shape['cam_entries']
        result['memory_profile']=memory_profile_name(result['board_size'],result['memory_profile'])
        single+='_'+SIZED_HARDWARE
    readout_spec(result.get('readout_profile',DRIVEN))
    expected=controller_profile(expected,result.get('readout_profile',DRIVEN))
    single=controller_profile(single,result.get('readout_profile',DRIVEN))
    if 'profile' not in value: result['profile']=single
    if not latest and result['profile'] not in ((single,) if sized else (expected,single)): raise ValueError('Controller profile does not match game rules or installed hardware')
    if rules!='legacy_go' and 'go_state' in result: raise ValueError('Go state requires legacy Go rules')
    if type(result.get('model_perspective',1)) is not int or result.get('model_perspective',1) not in (-1,1):
        raise ValueError('Invalid model perspective')
    if rules=='legacy_go' and result.get('model_perspective',1)!=1: raise ValueError('Go models use absolute player encoding')
    if not sized and result['memory_profile'] not in ('cacti_22nm_hp','cacti_22nm_lstp'): raise ValueError('Unknown SRAM profile')
    if not isinstance(result['memory_limits'],dict) or set(result['memory_limits'])-{'nodes','edges','path_entries'}:
        raise ValueError('Unknown memory allocation quota')
    if type(result['board_size']) is not int or result['board_size'] not in ((2,3,5,9,13,19) if sized else (2,3,5,9)): raise ValueError('Unsupported board size')
    if result['initial_board'] is None: result['initial_board']=[[0]*result['board_size'] for _ in range(result['board_size'])]
    # JSON identity refuses NaN/Infinity even before the simulator checks ranges.
    json_sha256(result)
    return result


def resolve_case(case_id=None, custom=None):
    if case_id is not None:
        if custom is not None: raise ValueError('Canonical cases cannot be combined with overrides')
        cases={row['id']:row for row in catalog()['cases']}
        if case_id not in cases: raise ValueError('Unknown canonical case')
        return configuration(cases[case_id]['configuration']),case_id
    config=configuration({} if custom is None else custom)
    return config,'custom_'+json_sha256(config)[:16]


def execution_identity(config, model):
    buffered_proof=None
    if config.get('readout_profile')==BUFFERED:
        buffered_proof=validate_buffered_sources()
        model.memory.config['timing_status']=TIMING_STATUS if not isinstance(model,GoSimulation) else 'buffered_neural_RTL_verified_host_Go_excluded'
    validation=ROOT/'core/architecture/complete_controller_validation.json'
    proof=json.loads(validation.read_text())
    validate_source_extension(proof)
    if proof['profile']!=PROFILE: raise ValueError('Complete-core proof belongs to another execution profile')
    for name,digest in proof['validated_sources'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Complete-core source changed since validation: '+name)
    evidence=ROOT/proof['evidence']['complete_rtl']['path']/'metadata.json'
    if not evidence.resolve().is_relative_to(ROOT) or hashlib.sha256(evidence.read_bytes()).hexdigest()!=proof['evidence']['complete_rtl']['metadata_sha256']:
        raise ValueError('Complete-core evidence identity changed')
    activity_evidence=ROOT/proof['activity_extension']['path']/'metadata.json'
    if not activity_evidence.resolve().is_relative_to(ROOT) or hashlib.sha256(activity_evidence.read_bytes()).hexdigest()!=proof['activity_extension']['metadata_sha256']:
        raise ValueError('Block activity evidence identity changed')
    effective={'requested':config,'memory':model.memory.config,'evaluator':model.evaluator,
        'neural_profile':model.neural.profile,'choice_policy':'xorshift32_modulo_v1',
        'workload':getattr(model,'workload','empty_cell_placement_v1'),'initial_player':model.memory.nodes[0]['player'],'clock_mhz':500,'technology_nm':22,
        'latency_boundary':'preloaded_core_execution_only','analog_services':'ideal_cell_code_currents_no_noise_or_wire_drop'}
    contract=Path(__file__).with_name('architecture_contract.json')
    effective['architecture_contract']=json.loads(contract.read_text())
    if isinstance(model,GoSimulation):
        effective['validation_scope']='Reused digital arithmetic and player-to-move values; host Go rules, metadata and terminal override are outside complete-core RTL proof'
        effective['latency_boundary']='modeled_component_work_only; host rules, metadata and interfaces excluded'
    if config.get('readout_profile')==BUFFERED:
        effective['validation_scope']=buffered_proof['scope'] if not isinstance(model,GoSimulation) else 'Buffered neural control verified with ideal interfaces; host Go rules, metadata, terminal override and interfaces are outside the complete placement-core proof'
        effective['analog_services']=model.neural.profile['readout']['analog_model']
    if model.neural.profile.get('turn_indicator'):
        model.memory.config['timing_status']='turn_input_component_schedule_not_RTL_validated'
        effective['validation_scope']='Reused integer arithmetic; the 163-input encoder and player-word read are software checked. The turn-aware sequencer, host Go rules and interfaces are outside existing RTL and synthesis evidence.'
    if isinstance(model,SingleChildPolicy):
        model.memory.config['timing_status']='single_child_architectural_services_not_RTL_validated'
        effective['validation_scope']='Single-child functional reference and packed-memory service model. Existing RTL evidence applies only to reused primitives; incremental selection, expansion, links and top-level control are not RTL validated. Host Go processing and physical timing remain excluded.'
        effective['choice_policy']='xorshift32_modulo_remaining_actions_row_major_pass_last_v1'
        effective['expansion_policy']=model.memory.config['policy']
        effective['architecture_contract']=effective['architecture_contract'] | {'execution_override':'SINGLE_CHILD_SPEC.md; incremental expansion and linked child storage'}
    if config.get('hardware_profile')==SIZED_HARDWARE:
        effective['installed_hardware']=board_hardware(model.board_size)
        effective['validation_scope']+=' Board-dependent SRAM/CAM capacities and Go path allocation are software verified; resized controllers and bank routing are not covered by matching synthesis or physical timing.'
    if current.is_current(config):
        model.memory.config['timing_status']=current.datapath_spec()['timing_status']
        effective.update(current_architecture=current.effective_architecture(current.prepare(model)),
            validation_scope=current.datapath_spec()['timing_status']+'; ideal analog arithmetic, host Go excluded',
            architecture_contract={'execution_override':current.PROFILE,'spec':'core/architecture/parallel_datapath.json'})
    identity=build_run_identity(effective)
    hardware=ROOT/'rtl_synthesis/p03_iteration_core'
    files=[validation,evidence,activity_evidence,hardware/'filelist.f']+[(hardware/name).resolve() for name in (hardware/'filelist.f').read_text().splitlines()]
    if proof.get('software_extension'): files.append(ROOT/proof['software_extension']['path'])
    if buffered_proof:
        hardware=ROOT/'rtl_synthesis/p04_column_hold'
        files += [BUFFER_VALIDATION,hardware/'filelist.f']+[(hardware/name).resolve() for name in (hardware/'filelist.f').read_text().splitlines()]
        files.append(ROOT/buffered_proof['evidence']['path']/'metadata.json')
    files.extend([SOURCES/'workbook_cells.json',SOURCES/'crossbar_reference.xlsx',PROVENANCE])
    files.extend(digital_source_files())
    files.extend(power_source_files(hashlib.sha256((ROOT/'core/architecture/digital_characterization.json').read_bytes()).hexdigest()))
    files.extend([POLICY,contract])
    files.extend(Path(__file__).with_name(name) for name in
        ('ARCHITECTURE_FIDELITY.md','COMPLETE_CORE_SPEC.md','COMPONENT_PPA_SPEC.md','BLOCK_POWER_SPEC.md','TECHNOLOGY_SPEC.md'))
    if isinstance(model,SingleChildPolicy):
        files.extend(Path(__file__).with_name(name) for name in ('SINGLE_CHILD_SPEC.md','CONTROLLER_ESTIMATE_SPEC.md'))
    files.extend(peripheral_sources()[2])
    files.extend(model_sources(config.get('model_id','random_diagnostic'),config['board_size']))
    if isinstance(model,GoSimulation): files.append(ROOT/RULES_SOURCE)
    if config.get('hardware_profile')==SIZED_HARDWARE:
        files.extend([SIZING_TABLE,SIZED_CHARACTERIZATION])
        files.extend(ROOT/name for name in memory_characterization()['source_files'])
    if current.is_current(config): files.extend(current.SOURCE_FILES)
    for path in files: identity['source_sha256'][str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    identity['simulator_sha256']=json_sha256(identity['source_sha256'])
    identity['execution_sha256']=json_sha256({key:identity[key] for key in ('configuration_sha256','simulator_sha256','runtime')})
    return identity


def new_run(root):
    root=Path(root).resolve()
    if not root.is_relative_to(ROOT): raise ValueError('Run output must stay inside the repair checkout')
    root.mkdir(parents=True,exist_ok=True)
    while True:
        out=root/datetime.now(timezone.utc).strftime('run_%Y%m%d_%H%M%SZ')
        try: out.mkdir(); return out
        except FileExistsError: time.sleep(0.05)


def current_index(runs=RUNS):
    path=Path(runs).parent/'index.json'
    return json.loads(path.read_text()) if path.exists() else {'schema_version':1,'cases':{}}


def verify_run(out):
    out=Path(out)
    metadata=json.loads((out/'metadata.json').read_text())
    if metadata['status'] not in ('complete','memory_limited'): raise ValueError('Run has no finalized result')
    for line in (out/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1)
        path=(out/name).resolve()
        if not path.is_relative_to(out.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Saved run artifact hash mismatch')
    result=json.loads((out/'result.json').read_text())
    if json_sha256(result)!=metadata['result_sha256']: raise ValueError('Saved result hash mismatch')
    return result


def _index_result(out, result):
    lock=out.parent.parent/'registry.lock'
    with lock.open('a+') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        index=current_index(out.parent); previous=index['cases'].get(result['case_id'])
        digest=json_sha256(result)
        if previous and previous['execution_sha256']==result['identity']['execution_sha256'] and previous['result_sha256']!=digest:
            raise RuntimeError('Identical execution identity produced a different deterministic result')
        index['cases'][result['case_id']]={'execution_profile':result['identity']['configuration']['requested']['profile'],'run':out.name,'result_sha256':digest,
            'configuration_sha256':result['identity']['configuration_sha256'],'execution_sha256':result['identity']['execution_sha256']}
        temporary=out.parent.parent/'index.pending.json'; write_json(temporary,index)
        os.replace(temporary,out.parent.parent/'index.json')


def run_case(case_id=None, custom=None, runs=RUNS, on_event=None):
    config,identifier=resolve_case(case_id,custom)
    out=new_run(runs); started=time.perf_counter()
    metadata={'schema_version':1,'status':'running','case_id':identifier,'started_utc':datetime.now(timezone.utc).isoformat(),
        'benchmarks_executed':False,'original_modified':False,'publicly_deployed':False}
    write_json(out/'metadata.json',metadata); write_json(out/'requested.json',config)
    model=None
    try:
        weights,evaluator=load_model(config.get('model_id','random_diagnostic'),config['board_size'],config.get('model_perspective',1))
        arguments={k:v for k,v in config.items() if k not in ('profile','memory_profile','model_id','model_perspective','rules','go_state','readout_profile','hardware_profile')}
        latest=current.is_current(config)
        incremental=latest or config['profile'].startswith('single_child_')
        sized=config.get('hardware_profile')==SIZED_HARDWARE
        if config.get('rules')=='legacy_go':
            engine=current.SizedParallelDatapathGoSimulation if latest else (SizedSingleChildGoSimulation if sized else (SingleChildGoSimulation if incremental else GoSimulation))
            model=engine(**arguments,weights=weights,go_state=config.get('go_state'),
                turn_indicator=latest or bool(evaluator and evaluator.get('turn_indicator')))
        else:
            engine=SizedSingleChildSimulation if sized else (SingleChildSimulation if incremental else CompleteSimulation)
            model=engine(**arguments,weights=weights)
        if not latest: configure_readout(model,config.get('readout_profile',DRIVEN))
        if latest and evaluator is not None:
            evaluator=evaluator | {'catalog_default_mapping':evaluator.get('mapping'),
                'mapping':'signed_8bit_weights_offset_8bit_cells',
                'encoding':'q_plus_128_with_digital_input_sum_correction'}
        if evaluator is not None: model.evaluator.update(mode='archived_checkpoint',checkpoint=evaluator)
        prepared=current.prepare(model) if latest else None
        estimates=current.inventory(prepared) if latest else component_estimates(model.neural.profile,config['memory_profile'],model.memory.config)
        identity=execution_identity(config,model)
        write_json(out/'identity.json',identity)
        with tarfile.open(out/'source_snapshot.tar.gz','w:gz') as archive:
            for name in identity['source_sha256']: archive.add(ROOT/name,arcname=name,recursive=False)
        np.savez_compressed(out/'weights.npz',weights1=model.weights[0],weights2=model.weights[1])
        if on_event: on_event({'phase':'ready','iteration':0,'cycle_end':0,'run':out.name},model)
        with (out/'phases.jsonl').open('w') as phases:
            for row in model.steps():
                phases.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n')
                if on_event: on_event(row | {'run':out.name},model)
        changed=[name for name,digest in identity['source_sha256'].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
        if changed: raise RuntimeError('Simulator source changed while running: '+', '.join(changed))
        costs=current.costs(model.memory.operations,model.cycles,model.block_active_cycles,current.capture(model),prepared) if latest else complete_costs(config['memory_profile'],model.memory.operations,model.cycles,
            model.neural.profile,model.memory.config,model.phase_cycles,model.block_active_cycles)
        write_power_csv(out/'block_power.csv',costs['block_power'])
        write_component_csv(out/'components.csv',costs['ledger'])
        result={'schema_version':1,'case_id':identifier,'status':'complete','publication_status':'diagnostic_not_task_validated',
            'identity':identity,'metrics':{'core_cycles':model.cycles,'core_latency_us':model.cycles/500,
                'completed_iterations':model.completed,'area_mm2':None,'power_mw':None,'energy_uj':None},
            'costs':costs,'phase_cycles':dict(model.phase_cycles),'memory':model.memory.summary(),
            'block_activity':model.activity_record() if latest else activity_record(dict(model.block_active_cycles),model.cycles),
            'preload':{'operations':model.preload_operations,'latency':'excluded; host interface and programming timing unspecified'},
            'tree_sha256':tree_sha256(model.memory.nodes),
            'node_sram_sha256':hashlib.sha256(model.memory.node_sram).hexdigest(),
            'child_sram_sha256':hashlib.sha256(model.memory.child_sram).hexdigest(),
            'last_value_q17':model.value_q17,'random_state':model.random_state,
            'evaluator':model.evaluator,'neural':{
                'profile':model.neural.profile | {'timing_status':'complete_core_controller_cycle_model','controller_profile':PROFILE},
                'coefficients':model.neural.coefficients,'operations_per_inference':model.neural.schedule['operations'],
                'cycles_per_inference':model.phase_cycles['neural']//model.completed-2,'owner_cycles_per_inference':2,
                'resources':model.neural.schedule['resources'] | {
                    'control_status':'Complete digital RTL verified with ideal interfaces; physical characterization remains open',
                    'resource_basis':'Mapping geometry and storage requirements; actual digital state is recorded in generic synthesis evidence'}}}
        result['component_estimates']=estimates
        result['analog_readout']=estimates['analog_readout'] if latest else readout_activity(model.neural)
        if isinstance(model,GoSimulation):
            result['application']=model.application_record()
            result['publication_status']='host_assisted_go_not_task_validated'
            result['neural']['profile']['controller_profile']=GO_PROFILE
            result['neural']['profile']['timing_status']='host_assisted_component_schedule'
            result['neural']['resources']['control_status']='Mapped neural block and player-to-move arithmetic reused; host Go rules and terminal override are outside complete-core RTL validation'
            result['costs']['boundary']='Modeled component work only; host Go processing, state metadata and successor delivery are excluded.'
            result['costs']['timing']='Component cycle estimate at assumed 500 MHz; integrated Go controller and physical timing unvalidated'
        if config.get('readout_profile')==BUFFERED:
            result['publication_status']='column_hold_candidate_not_physically_or_task_validated'
            result['neural']['profile'].update(controller_profile=config['profile'],timing_status=TIMING_STATUS)
            result['neural']['resources']['control_status']='Buffered capture, ownership and digital inference verified in RTL and generic gates with ideal interfaces; analog accuracy and physical timing remain unvalidated'
            result['costs']['timing']='RTL-checked buffered schedule at assumed 500 MHz; physical timing and analog retention unvalidated'
            if isinstance(model,GoSimulation):
                result['neural']['resources']['control_status']+='; host Go rules and interfaces excluded'
                result['costs']['timing']+='; host Go processing and interfaces excluded'
        if model.neural.profile.get('turn_indicator'):
            result['neural']['profile'].update(controller_profile=config['profile'],
                timing_status='turn_input_component_schedule_not_RTL_validated')
            result['neural']['resources']['control_status']=identity['configuration']['validation_scope']
            result['costs']['timing']='163-input component schedule at assumed 500 MHz; turn-aware digital control and physical timing unvalidated'
        if incremental:
            result.update(status=model.status,expansion_policy=model.memory.config['policy'],termination=model.termination)
            result['metrics']['requested_iterations']=model.iterations
            result['neural']['profile'].update(controller_profile=config['profile'],timing_status=model.memory.config['timing_status'])
            result['neural']['resources']['control_status']=identity['configuration']['validation_scope']
            result['costs']['timing']='Single-child architectural service estimate at assumed 500 MHz; incremental controller and physical timing unvalidated'
        if latest:
            result['architecture']=current.effective_architecture(prepared)
            result['reporting_basis']=current.capture(model)
            result['neural']['profile']=model.neural.profile
            result['neural']['cycles_per_inference']=model.neural.schedule['cycles']
            result['neural']['owner_cycles_per_inference']=0
            result['neural']['resources']['control_status']=current.datapath_spec()['timing_status']
            result['costs']['timing']=current.datapath_spec()['timing_status']
            result['publication_status']='parallel_architectural_estimate_not_physically_validated'
            if model.component_parameters:
                result['publication_status']='custom_parameter_scenario_not_physically_validated'
        write_json(out/'component_estimates.json',estimates)
        write_json(out/'result.json',result)
        with (out/'iterations.csv').open('w',newline='') as stream:
            fields=['iteration','cycle_end','selected_node','value_q17','nodes','edges','random_state']
            writer=csv.DictWriter(stream,fieldnames=fields); writer.writeheader()
            writer.writerows({key:row[key] for key in fields} for row in model.history)
        with gzip.open(out/'tree.json.gz','wt') as stream:
            json.dump({str(n):{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in node.items()}
                for n,node in model.memory.nodes.items()},stream,separators=(',',':'),allow_nan=False)
        export={'case_id':identifier,'configuration_sha256':identity['configuration_sha256'],
            'execution_profile':config['profile'],'tree_update_timing_profile':model.memory.config['tree_update_timing_profile'],
            'digital_source_commit':costs['digital']['source_commit'],
            'execution_sha256':identity['execution_sha256'],'result_sha256':json_sha256(result),
            'board_size':config['board_size'],'iterations':model.completed,'core_cycles':model.cycles,
            'core_latency_us':model.cycles/500,'sram_area_mm2':costs['sram']['area_mm2'],
            'sram_energy_uj':costs['sram']['energy_uj'],'sram_average_power_mw':costs['sram']['average_power_mw'],
            'digital_area_22nm_estimate_mm2':costs['digital']['known_area_mm2'],
            'digital_area_65nm_subtotal_um2':costs['digital']['known_native_65nm_area_um2'],
            'digital_priced_instances':costs['digital']['priced_instances'],
            'digital_profile_sha256':costs['digital']['profile_sha256'],'known_area_mm2':estimates['known_area_mm2'],
            'whole_chip_area_mm2':None,'whole_chip_energy_uj':None,'whole_chip_power_mw':None,
            'publication_status':result['publication_status'],'readout_profile':result['analog_readout']['profile']}
        export.update(digital_timing_fields(costs['digital']))
        export.update(ledger_fields(costs))
        if sized:
            export.update(hardware_profile=SIZED_HARDWARE,cam_entries=model.memory.config['cam_entries'],
                node_sram_bytes=model.memory.config['node_sram_bytes'],child_sram_bytes=model.memory.config['child_sram_bytes'],
                path_storage_entries=model.memory.config['path_storage_entries'])
        if incremental: export.update(status=model.status,requested_iterations=model.iterations,
            expansion_policy=model.memory.config['policy'],termination_reason='' if model.termination is None else model.termination['resource'])
        with (out/'summary.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(export)); writer.writeheader(); writer.writerow(export)
        metadata.update(status=result['status'],finished_utc=datetime.now(timezone.utc).isoformat(),host_runtime_s=time.perf_counter()-started,
            result_sha256=json_sha256(result),execution_sha256=identity['execution_sha256'])
        write_json(out/'metadata.json',metadata)
        files=sorted(p for p in out.iterdir() if p.is_file())
        (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
        verify_run(out)
        if result['status']=='complete': _index_result(out,result)
        return out,result
    except Exception as error:
        metadata.update(status='cancelled' if isinstance(error,RunCancelled) else 'failed',
            finished_utc=datetime.now(timezone.utc).isoformat(),host_runtime_s=time.perf_counter()-started,
            error=type(error).__name__+': '+str(error),completed_iterations=0 if model is None else model.completed)
        write_json(out/'metadata.json',metadata)
        raise


def main():
    parser=argparse.ArgumentParser(description='Run a canonical IMC-MCTS simulator case')
    parser.add_argument('--case'); parser.add_argument('--list',action='store_true')
    parser.add_argument('--board',type=int); parser.add_argument('--iterations',type=int)
    parser.add_argument('--seed',type=int)
    args=parser.parse_args()
    if args.list:
        for row in catalog()['cases']: print(row['id']+': '+row['name'])
        return
    if args.case and any(value is not None for value in (args.board,args.iterations,args.seed)):
        parser.error('Canonical cases cannot be combined with --board, --iterations or --seed')
    custom=None if args.case else {key:value for key,value in
        [('board_size',args.board),('iterations',args.iterations),('seed',args.seed)] if value is not None}
    out,result=run_case(args.case,custom)
    print(out)
    print(json.dumps(result['metrics'],indent=2))


if __name__=='__main__': main()
