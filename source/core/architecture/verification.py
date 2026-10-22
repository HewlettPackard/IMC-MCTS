# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
# Verify saved single-child reference results without changing simulator behavior.
import math


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_result(result, contract):
    metrics = result['metrics']
    identity = result['identity']['configuration']
    memory = result['memory']
    ledger = result['costs']['ledger']
    require(identity['requested'] == contract['configuration'], 'configuration mismatch')
    require(identity['evaluator'] == contract['evaluator'], 'evaluator weights or numerical mapping mismatch')
    require(identity['choice_policy'] == contract['choice_policy'], 'algorithm policy mismatch')
    require(identity['latency_boundary'] == contract['latency_boundary'], 'measurement boundary mismatch')
    require(identity['clock_mhz'] == contract['clock_mhz'], 'clock mismatch')
    require(metrics['completed_iterations'] == metrics['requested_iterations'] == contract['configuration']['iterations'], 'incomplete search')
    cycles = metrics['core_cycles']
    require(isinstance(cycles, int) and cycles > 0, 'invalid hardware cycles')
    require(cycles == sum(result['phase_cycles'].values()) == memory['last_completion_cycle'], 'cycle accounting mismatch')
    require(math.isclose(metrics['core_latency_us'], cycles / contract['clock_mhz'], rel_tol=1e-12), 'hardware latency must come from modeled cycles')
    for used, capacity in [('nodes_used','node_capacity'), ('edges_used','edge_capacity'), ('path_high_water','path_entries')]:
        require(0 <= memory[used] <= memory['config'][capacity], 'memory capacity exceeded: ' + used)
    require(memory['node_bytes_used'] + memory['scratch_bytes_reserved'] <= memory['config']['node_sram_bytes'], 'node SRAM overflow')
    require(memory['child_bytes_used'] <= memory['config']['child_sram_bytes'], 'child SRAM overflow')
    rows = ledger['components']
    ids = [row['id'] for row in rows]
    require(len(ids) == len(set(ids)), 'duplicate cost owner')
    require(set(ids) == set(contract['cost_owners']), 'missing or unexpected cost owner')
    require(ledger['source_identities'] == contract['cost_sources'], 'cost source mismatch')
    require(ledger['policy'] == contract['scaling_policy'], 'technology scaling mismatch')
    for row in rows:
        for key in ('area_um2','energy_uj'):
            value = row[key]
            require(value is None or (math.isfinite(value) and value >= 0), 'invalid component cost')
        if row['area_um2'] is not None or row['energy_uj'] is not None:
            require(bool(row.get('source')), 'cost lacks provenance')
    area = sum(row['area_um2'] or 0 for row in rows) / 1e6
    energy = sum(row['energy_uj'] or 0 for row in rows)
    require(math.isclose(area, ledger['known_area_mm2'], rel_tol=1e-10, abs_tol=1e-12), 'area sum mismatch')
    require(math.isclose(energy, ledger['known_energy_uj'], rel_tol=1e-10, abs_tol=1e-12), 'energy sum mismatch')
    require(math.isclose(energy * 1000 / metrics['core_latency_us'], ledger['known_average_power_mw'], rel_tol=1e-10), 'power/energy/time mismatch')
    for key in ('whole_chip_area_mm2','whole_chip_energy_uj','whole_chip_power_mw'):
        require(ledger[key] is None, 'unsupported whole-chip claim')
    return {'status':'PASS', 'scope':'single-child reference schema, finite storage, accounting and claim boundary'}


def summarize(checks):
    stages = {}
    for stage in ('algorithm','hardware','circuit','cost','reproducibility','claims'):
        rows = [row for row in checks if row['stage'] == stage]
        status = 'PASS'
        if not rows or any(row['status'] == 'UNVERIFIED' for row in rows):
            status = 'UNVERIFIED'
        if any(row['status'] == 'FAIL' for row in rows):
            status = 'FAIL'
        stages[stage] = {'status':status, 'checks':rows}
    failed = any(row['status'] == 'FAIL' for row in stages.values())
    verified = all(row['status'] == 'PASS' for row in stages.values())
    return {'stages':stages, 'verification_failed':failed, 'all_stages_verified':verified,
        'publication_ready':False, 'publication_note':'Scientific interpretation and matched task-quality/baseline evidence require separate review.'}


def exit_code(report, strict=False):
    return 1 if report['verification_failed'] else (2 if strict and not report['all_stages_verified'] else 0)


def audit_current_result(result,contract):
    # This checks executable/model bookkeeping, never circuit accuracy.
    from core.architecture.component_parameters import validate_parameters,OWNERS
    metrics=result['metrics'];configuration=result['identity']['configuration'];memory=result['memory']['config']
    ledger=result['costs']['ledger'];report=result['costs']['estimate'];architecture=result['architecture']
    require(configuration['requested']==contract['configuration'],'configuration mismatch')
    require(configuration['evaluator']==contract['evaluator'],'evaluator mismatch')
    require(ledger['source_identities']==contract['cost_sources'],'cost source mismatch')
    parameters=validate_parameters(configuration['requested'].get('component_parameters',{}))
    require(ledger.get('component_parameters',{})==parameters,'parameter provenance mismatch')
    require(architecture['profile']=='ucb16_adc32_buffered_v2','wrong current architecture')
    cycles=metrics['core_cycles'];completed=metrics['completed_iterations']
    require(type(cycles) is int and cycles>0,'invalid cycles')
    require(completed==metrics['requested_iterations']==configuration['requested']['iterations'],'incomplete search')
    require(cycles==sum(result['phase_cycles'].values())==result['memory']['last_completion_cycle'],'cycle accounting mismatch')
    require(result['phase_cycles']['iteration_commit']==4*completed,'current FSM finish must take four cycles')
    require(math.isclose(metrics['core_latency_us'],cycles/500,rel_tol=1e-12),'latency units mismatch')
    for used,capacity in [('nodes_used','node_capacity'),('edges_used','edge_capacity'),('path_high_water','path_storage_entries')]:
        require(0<=result['memory'][used]<=memory[capacity],'capacity exceeded: '+used)
    require(result['memory']['node_bytes_used']+result['memory']['scratch_bytes_reserved']<=memory['node_sram_bytes'],'node SRAM exceeded')
    require(result['memory']['child_bytes_used']<=memory['child_sram_bytes'],'child SRAM exceeded')
    rows=ledger['components'];ids=[row['id'] for row in rows]
    require(len(ids)==len(set(ids)) and set(ids)==set(OWNERS),'missing or duplicate component owner')
    for row in rows:
        require(bool(row.get('source')),'component provenance missing')
        for key in ('area_um2','dynamic_energy_uj','standby_energy_uj','energy_uj','average_power_mw'):
            require(type(row[key]) in (float,int) and math.isfinite(row[key]) and row[key]>=0,'invalid '+key)
        require(math.isclose(row['energy_uj'],row['dynamic_energy_uj']+row['standby_energy_uj'],rel_tol=1e-12,abs_tol=1e-12),'component energy mismatch')
        require(math.isclose(row['energy_uj'],row['average_power_mw']*cycles/500000,rel_tol=1e-12,abs_tol=1e-12),'component power units mismatch')
    area=sum(row['area_um2'] for row in rows)/1e6;energy=sum(row['energy_uj'] for row in rows)
    require(math.isclose(area,ledger['known_area_mm2'],rel_tol=1e-12),'area sum mismatch')
    require(math.isclose(energy,ledger['known_energy_uj'],rel_tol=1e-12),'energy sum mismatch')
    require(math.isclose(energy,ledger['known_average_power_mw']*cycles/500000,rel_tol=1e-12),'power/energy/time mismatch')
    require(math.isclose(energy,report['core_energy_uj'],rel_tol=1e-12),'report/ledger mismatch')
    require(all(value is None for value in result['costs']['whole_chip'].values()),'unsupported whole-chip claim')
    require(result['publication_status'] in ('parallel_architectural_estimate_not_physically_validated','custom_parameter_scenario_not_physically_validated'),'unsupported validation claim')
    return {'status':'PASS','scope':'Current-profile configuration, finite storage, source ownership, service and unit accounting; physical feasibility and analog accuracy unverified'}
