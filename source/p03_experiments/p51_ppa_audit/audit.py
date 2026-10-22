# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Bounded evidence audit; all new workloads stay in this experiment.
# SPDX-License-Identifier: MIT
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

from core.architecture.result_registry import configuration, new_run, run_case, verify_run, write_json
from p03_experiments.p51_ppa_audit.oracle import ROOT, FROZEN, Sources, compare, expected, flatten, check

EXPERIMENT = Path(__file__).parent


def save_csv(path, rows):
    with (gzip.open(path, 'wt', newline='') if path.suffix == '.gz' else path.open('w', newline='')) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def exports(folder, result, oracle):
    rows = list(csv.DictReader((folder / 'components.csv').open()))
    assert len(rows) == len(flatten(result['costs']['ledger']['components']))
    assert len(rows) == len({r['id'] for r in rows})
    for row in rows:
        if row['counted'] != 'True':
            assert row['energy_uj'] == row['average_power_mw'] == ''
            continue
        for field in ('area_um2', 'energy_uj', 'average_power_mw', 'active_cycles'):
            check(None if not row[field] else float(row[field]), oracle[row['id']][field], 'CSV ' + row['id'] + '.' + field)
    summary = next(csv.DictReader((folder / 'summary.csv').open()))
    for field in ('known_area_mm2', 'known_energy_uj', 'known_average_power_mw'):
        check(float(summary[field]), result['costs']['ledger'][field], 'summary ' + field)
    assert summary['configuration_sha256'] == result['identity']['configuration_sha256']
    assert summary['cost_model_sha256'] == result['costs']['ledger']['sha256']


def evidence_matrix(result, oracle, source):
    rows = []
    for part, owner in flatten(result['costs']['ledger']['components']):
        external = owner in ('chip_io', 'weight_programming')
        counted = part['id'] == owner and not external
        for field, units in [('area_um2', 'um2'), ('average_power_mw', 'mW'), ('energy_uj', 'uJ'), ('active_cycles', 'cycles')]:
            value = part.get(field)
            if external:
                status = 'outside_core_uncharacterized'
            elif not counted:
                status = 'included_hierarchical_area' if value is not None else 'included_in_owner_no_separate_measurement'
            elif value is None:
                status = 'missing_compatible_characterization'
            elif field == 'active_cycles':
                status = 'modeled_occupancy_not_additive_latency'
            elif owner.startswith('u_') or owner == 'top_level_glue':
                status = 'scaled_synthesis_area' if field == 'area_um2' else 'vectorless_activity_estimate_with_native65_leakage_proxy'
            elif owner.endswith('_sram'):
                status = 'native22_CACTI_analytical_macro'
            elif owner == 'physical_overhead':
                status = 'physical_implementation_allowance'
            else:
                status = 'analog_or_CAM_proxy_unvalidated'
            sources = oracle[owner]['sources']
            digital = owner.startswith('u_') or owner == 'top_level_glue'
            memory = owner.endswith('_sram') or owner == 'cam_macro'
            native_node = '65' if digital else '22' if memory or owner == 'adc_lanes' else 'workbook source-specific; projected 22' if not external else 'unknown'
            native_pvt = 'TT 1.0 V 25 C' if digital else ('CACTI ' + result['costs']['sram']['profile'] + '; 360 K; macro voltage in operating_points.json') if memory else 'HP 0.85 V 360 K; read 0.4 V' if owner == 'adc_lanes' else 'workbook primitive-specific; analog bias 1.8 V; temperature unspecified'
            conversion = 'area x (22/65)^2 once; dynamic energy x (22/65)*(0.8/1.0)^2 once; native65 leakage unchanged; no delay scaling' if digital else 'no additional node scaling; source-specific proxy or allowance'
            if field == 'active_cycles' and not external:
                sources = sources + ['core/architecture/BLOCK_POWER_SPEC.md', 'core/architecture/NEURAL_RTL_SPEC.md', 'core/architecture/COMPONENT_PPA_SPEC.md']
            for path in sources:
                source.bytes(path)
            rows.append({'id': part['id'], 'owner': owner, 'part': part['component'], 'counted': counted,
                'metric': field, 'value': value, 'units': units, 'evidence_class': status,
                'source_node_nm': native_node if not external else '', 'target_node_nm': 22 if not external else None,
                'source_operating_point': native_pvt if not external else '', 'conversion': conversion if not external else '',
                'target_operating_point': 'nominal 500 MHz; common voltage/temperature and closure unvalidated' if not external else '',
                'count': part.get('count'), 'required_parameters': json.dumps(oracle[owner].get('parameters', {}), sort_keys=True),
                'source_paths': ';'.join(sources), 'source_sha256': ';'.join(source.hashes[path] for path in sources),
                'source_note': part.get('status', ''), 'cost_model_sha256': result['costs']['ledger']['sha256']})
    return rows


def sensitivity(result, source):
    baseline = expected(result, source)
    base_energy = sum(r['energy_uj'] or 0 for r in baseline.values())
    base_area = sum(r['area_um2'] or 0 for r in baseline.values()) / 1e6
    scenarios = [('baseline', {})]
    for name in ('digital_dynamic_multiplier', 'digital_leakage_multiplier', 'reference_multiplier'):
        scenarios.extend([(name + '_0.5', {name: .5}), (name + '_2', {name: 2})])
    for name in ('driver_idle_fraction', 'frontend_bias_ua', 'clock_wire_power_fraction', 'layout_area_fraction'):
        scenarios.extend([(name + '_0.5', {name: source.assumptions[name] * .5}), (name + '_2', {name: source.assumptions[name] * 2})])
    for scale in (10, 100):
        scenarios.append(('adc_energy_multiplier_' + str(scale), {'adc_energy_multiplier': scale}))
    for name in ('input_activity', 'mean_conductance'):
        for value in (.25, .75):
            scenarios.append((name + '_' + str(value), {name: value}))
    rows = []
    for label, overrides in scenarios:
        estimates = expected(result, source, overrides)
        energy = sum(r['energy_uj'] or 0 for r in estimates.values())
        area = sum(r['area_um2'] or 0 for r in estimates.values()) / 1e6
        rows.append({'scenario': label, 'known_energy_uj': energy, 'energy_change_percent': (energy / base_energy - 1) * 100,
            'known_area_mm2': area, 'area_change_percent': (area / base_area - 1) * 100,
            'status': 'one_at_a_time_assumption_stress_not_confidence_interval', 'overrides': json.dumps(overrides, sort_keys=True)})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', type=Path)
    args = parser.parse_args()
    out = args.resume.resolve() if args.resume else new_run(EXPERIMENT / 'p00_runs')
    assert out.is_relative_to(EXPERIMENT.resolve() / 'p00_runs')
    assert not (out / 'FROZEN').exists(), 'Completed audit is frozen; create a new audit directory'
    print(out, flush=True)
    source = Sources()
    all_comparisons, matrix, cases = [], [], []
    frozen = verify_run((ROOT / FROZEN).parent)

    def audit_case(label, folder, result):
        oracle, checks = compare(result, source)
        exports(folder, result, oracle)
        all_comparisons.extend({'case': label} | row for row in checks)
        matrix.extend({'case': label} | row for row in evidence_matrix(result, oracle, source))
        record = {'label': label, 'run': str(folder.relative_to(ROOT)), 'result_sha256': hashlib.sha256((folder / 'result.json').read_bytes()).hexdigest(),
            'configuration_sha256': result['identity']['configuration_sha256'],
            'cost_model_sha256': result['costs']['ledger']['sha256'], 'inventory_rows': len(flatten(result['costs']['ledger']['components'])),
            'core_cycles': result['metrics']['core_cycles'], 'latency_us': result['metrics']['core_latency_us']}
        for name in ('known_area_mm2', 'known_energy_uj', 'known_average_power_mw', 'missing_area', 'missing_energy'):
            record[name] = result['costs']['ledger'][name]
        cases.append(record)
        print('PASS', label, len(checks), 'owner checks', flush=True)
        return oracle

    oracle = audit_case('frozen_9x9_5000', (ROOT / FROZEN).parent, frozen)
    write_json(out / 'reference.json', {'origin': FROZEN, 'result_sha256': cases[0]['result_sha256'],
        'configuration': frozen['identity']['configuration'], 'configuration_sha256': frozen['identity']['configuration_sha256'],
        'cost_model_sha256': frozen['costs']['ledger']['sha256'], 'expected_owners': oracle,
        'status': 'accounting_verified_physical_PPA_unvalidated', 'production_coefficients_changed': False})
    save_csv(out / 'sensitivity.csv', sensitivity(frozen, source))
    def probe(label, config):
        previous = sorted((out / 'p01_probes' / label).glob('run_*'))
        if previous:
            result = verify_run(previous[-1])
            assert result['identity']['configuration']['requested'] == configuration(config)
            return previous[-1], result
        return run_case(custom=config, runs=out / 'p01_probes' / label)

    unsupported = []
    for size in (13, 19):
        try:
            configuration({'board_size': size})
        except ValueError as error:
            assert str(error) == 'Unsupported board size'
            unsupported.append({'board_size': size, 'status': 'correctly_rejected_no_PPA_claim', 'message': str(error)})
        else:
            raise AssertionError('Larger-board contract changed; extend the oracle before adopting its costs')
    for size in (2, 3, 5, 9):
        for flavor in ('lstp', 'hp'):
            for readout in ('sustained_drive_v1', 'column_hold_v1'):
                label = f'placement_{size}_{flavor}_{readout}'
                folder, result = probe(label, {'board_size': size, 'iterations': 4, 'memory_profile': 'cacti_22nm_' + flavor,
                    'readout_profile': readout})
                audit_case(label, folder, result)
    for model in ('go_strong_v1', 'go_weak_v1'):
        for flavor in ('lstp', 'hp'):
            for readout in ('sustained_drive_v1', 'column_hold_v1'):
                label = model + '_' + flavor + '_' + readout
                folder, result = probe(label, {'board_size': 9, 'iterations': 4, 'rules': 'legacy_go', 'model_id': model,
                    'memory_profile': 'cacti_22nm_' + flavor, 'readout_profile': readout})
                estimates = audit_case(label, folder, result)
                assert estimates['u_nn']['area_um2'] is None and estimates['u_nn']['energy_uj'] is None

    # Reuse a saved isolated two-move session; do not control the user's live game.
    session_path = ROOT / 'p03_experiments/p49_result_state/p00_runs/run_20260914_201417Z/p01_results/p02_plays/run_20260914_201418Z'
    session = verify_run(session_path)
    moves = []
    for folder in sorted((session_path / 'p01_searches').glob('run_*')):
        result = verify_run(folder)
        estimates = audit_case('retained_session_' + folder.name, folder, result)
        moves.append((result, estimates))
    for row in session['costs']['ledger']['components']:
        costs = [part[row['id']]['energy_uj'] for _, part in moves]
        check(row['energy_uj'], None if any(v is None for v in costs) else sum(costs), 'session energy ' + row['id'])
        check(row['area_um2'], moves[0][1][row['id']]['area_um2'], 'session area not duplicated ' + row['id'])
    check(session['metrics']['core_cycles'], sum(r['metrics']['core_cycles'] for r, _ in moves), 'session cycle sum')
    write_json(out / 'session_check.json', {'status': 'passed', 'session': str(session_path.relative_to(ROOT)), 'moves': len(moves), 'area_counted_once': True, 'energy_and_cycles_summed': True})
    save_csv(out / 'comparisons.csv', all_comparisons)
    save_csv(out / 'evidence_matrix.csv.gz', matrix)
    # The original uncompressed matrix was an intermediate in this new audit only.
    if (out / 'evidence_matrix.csv').exists():
        (out / 'evidence_matrix.csv').unlink()
    write_json(out / 'operating_points.json', {'digital_source': {'node_nm': 65, 'voltage_v': 1, 'temperature_c': 25, 'corner': 'TT'},
        'digital_target': {'node_nm': 22, 'voltage_v': .8, 'temperature_c': None, 'corner': None, 'clock_mhz': 500, 'physical_closure': False},
        'sram': {k: v['macro'] for k, v in source.sram_catalog.items()}, 'cam': source.tools['cam'], 'adc': source.tools['adc'],
        'workbook_primitives': source.cells, 'workbook_conversion_note': 'D28 and P31 contain the workbook\'s own 16-to-22 projection; D25=1.5011 and P25=1/0.7, not the digital65 geometric rule. Cached formula values retained.',
        'frontend': {'supply_v': source.assumptions['analog_supply_v'], 'bias_ua': source.assumptions['frontend_bias_ua'], 'temperature': None},
        'outside_core': ['Host I/O, pads, ESD, package, host Go work', 'Weight programming, write/verify, preload interface'],
        'nonadditive_timing': 'Per-component occupancy overlaps; only exclusive phase cycles add to elapsed cycles'})
    write_json(out / 'sources.json', source.hashes)
    write_json(out / 'metadata.json', {'status': 'passed', 'cases': cases, 'owner_metric_checks': len(all_comparisons),
        'evidence_matrix_rows': len(matrix), 'source_files': len(source.hashes), 'source_checks': source.checks,
        'new_searches': 24, 'iterations_per_new_search': 4, 'unsupported_sizes': unsupported, 'source_calculations_independent': True,
        'large_workloads_executed': False, 'physical_validation_claimed': False})
    (out / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + str(p.relative_to(out)) + '\n'
        for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS'))
    write_json(EXPERIMENT / 'latest.json', {'audit': str(out.relative_to(ROOT))})
    print('Audit passed', len(cases), 'cases;', len(all_comparisons), 'owner checks', flush=True)


if __name__ == '__main__':
    main()
