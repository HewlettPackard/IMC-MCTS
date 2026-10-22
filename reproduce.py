#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
"""Run the supported reviewer-package checks. Figure 3d is deliberately excluded."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def read(relative):
    return json.loads((ROOT / relative).read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def near(a, b, label):
    if not math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-10):
        raise ValueError(f'{label}: {a!r} != {b!r}')


def verify_manifest():
    records = read('MANIFEST.json')['files']
    for row in records:
        path = ROOT / row['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError(f'Missing or changed frozen input: {row["path"]}')
    return len(records)


def verify_ledger(record):
    costs = record.get('costs', record)
    rows = costs['components']
    if len(rows) != len({row['id'] for row in rows}):
        raise ValueError('Duplicate top-level component ownership')
    near(sum(row['energy_uj'] for row in rows), costs['core_energy_uj'], 'component energy sum')
    near(sum(row['area_um2'] for row in rows) / 1e6, costs['core_area_mm2'], 'component area sum')
    near(costs['core_energy_mj'] * 1000, costs['core_energy_uj'], 'mJ to microjoules')
    near(costs['core_energy_mj'] * 1000 / costs['latency_ms'], costs['core_average_power_mw'], 'E/T power')
    for row in rows:
        if min(row['area_um2'], row['energy_uj']) < 0:
            raise ValueError('Negative component energy or area')
        near(row['energy_uj'], row['dynamic_energy_uj'] + row['standby_energy_uj'], 'active plus standby')
        near(row['energy_uj'], row['average_power_mw'] * costs['latency_ms'], 'component P times T')
    if 'cycles' in record:
        near(record['cycles'] / 500000, costs['latency_ms'], 'cycles to milliseconds')
        near(sum(record['phase_cycles'].values()), record['cycles'], 'phase conservation')
        near(costs['core_energy_uj'] / record['iterations'], costs['average_energy_uj_per_iteration'], 'search-average E/N')
        if record['completed'] != record['iterations'] or record['status'] != 'complete':
            raise ValueError('Incomplete retained search')


def verify_data():
    hero = read('data/primary/hero.json')
    scaling = read('data/scaling/diagnostic_results.json')
    grid = read('configs/scaling.json')
    expected = {(r['board_size'], r['iterations']) for r in grid}
    observed = {(r['board_size'], r['iterations']) for r in scaling}
    if expected != observed or len(scaling) != 18:
        raise ValueError('Scaling grid is incomplete or duplicated')
    for record in [hero] + scaling:
        verify_ledger(record)
        if record['costs']['profile'] != 'ucb16_adc32_buffered_estimate_v6':
            raise ValueError('Wrong retained cost profile')
    if any(r['model_id'] != 'random_diagnostic' for r in scaling):
        raise ValueError('Diagnostic scaling was relabelled as trained')
    if hero['board_size'] != 9 or hero['iterations'] != 5000 or hero['model_id'] != 'go_strong_v1':
        raise ValueError('Wrong primary configuration')
    applications = list((ROOT / 'data/applications/p00_costs').glob('*/costs.json'))
    if len(applications) != 8:
        raise ValueError('Expected eight application cost ledgers')
    for path in applications:
        verify_ledger(json.loads(path.read_text()))

    comparisons = list(csv.DictReader((ROOT / 'data/baselines/fig3bc.csv').open()))
    index = read('data/baselines/index.json')
    mapping = {'AMD TR': ('amd_traditional', 'amd_neural'),
               'Xeon': ('xeon_traditional', 'xeon_neural'),
               'H100': ('gpu_fair', 'gpu_neural'),
               'H100 (b64)': (None, 'gpu_neural_batch64'),
               'H100 (b256)': (None, 'gpu_neural_batch256')}
    means_checked = 0
    for row in comparisons:
        if row['platform'] == 'IMC-MCTS':
            near(row['neural_energy_mj'], hero['costs']['core_energy_mj'], 'plotted IMC energy')
            near(row['neural_latency_ms'], hero['costs']['latency_ms'], 'plotted IMC latency')
            continue
        for prefix, source_id in zip(['trad', 'neural'], mapping[row['platform']]):
            if source_id is None:
                if row[prefix + '_energy_mj'] or row[prefix + '_latency_ms']:
                    raise ValueError('Inferred traditional batch record')
                continue
            path = ROOT / index[source_id]['path']
            trials = [r for r in csv.DictReader(path.open()) if r['board_size'].split('x')[0] == '9']
            if len(trials) != 5 or any(int(r['iterations']) != 5000 for r in trials):
                raise ValueError('Wrong board, budget or trial count')
            near(statistics.mean(float(r['total_energy_uj']) for r in trials) / 1000,
                 row[prefix + '_energy_mj'], 'archived mean energy')
            near(statistics.mean(float(r['total_latency_ms']) for r in trials),
                 row[prefix + '_latency_ms'], 'archived mean latency')
            means_checked += 1
    ratios = read('data/baselines/stacked_ratios.json')
    for row in ratios:
        near(row['neural_cost'] / row['imc_cost'], row['orange_end'], 'neural ratio')
        if row['traditional_cost'] is not None:
            near(row['traditional_cost'] / row['imc_cost'], row['blue_end'], 'combined ratio')
            near(row['orange_end'] * row['traditional_over_neural'], row['blue_end'], 'multiplicative factors')
    # The display dataset substitutes the trained hero only at 9x9-medium.
    for row in csv.DictReader((ROOT / 'data/scaling/display_totals.csv').open()):
        trained = int(row['board_size']) == 9 and row['budget'] == 'medium'
        source = hero if trained else next(r for r in scaling if (r['board_size'], r['iterations']) == (int(row['board_size']), int(row['iterations'])))
        if row['model'] != source['model_id']:
            raise ValueError('Wrong displayed model identity')
        for shown, key in [('energy_mj', 'core_energy_mj'), ('latency_ms', 'latency_ms'),
                           ('power_mw', 'core_average_power_mw'), ('area_mm2', 'core_area_mm2')]:
            near(row[shown], source['costs'][key], 'displayed ' + shown)
    return dict(saved_searches=19, diagnostic_cases=18, application_ledgers=8,
                archived_processor_means=means_checked, ratio_records=len(ratios),
                figure3d='ON_HOLD_EXCLUDED', figure4a='ARCHIVED_DATA_REPLOT_ONLY')


def run_command(command, cwd, log):
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
               PYTHONDONTWRITEBYTECODE='1', MPLBACKEND='Agg')
    env.pop('PYTHONPATH', None)
    with log.open('w') as handle:
        result = subprocess.run(command, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}); see {log}\n' + log.read_text(errors='replace')[-2000:])


RUNTIME_SOURCE = ROOT / 'source'


def hydrate_source(destination, store):
    import importlib.util
    spec = importlib.util.spec_from_file_location('release_artifacts', ROOT / 'source/imc_mcts_release/artifacts.py')
    artifacts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(artifacts)
    artifacts.verify_store(store)
    shutil.copytree(ROOT / 'source', destination, ignore=shutil.ignore_patterns('__pycache__', '.DS_Store'))
    artifacts.overlay_artifacts(store, destination)
    return destination


def execute_case(config, expected, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-B', 'reproduce_runtime.py', '--board', str(config['board_size']),
               '--iterations', str(config['iterations']), '--model', config['model_id'],
               '--seed', str(config['seed']), '--output', str(destination)]
    start = time.perf_counter()
    run_command(command, RUNTIME_SOURCE, destination.with_suffix('.log'))
    actual = json.loads((destination / 'result.json').read_text())
    costs = json.loads((destination / 'costs.json').read_text())
    for field in ['cycles', 'phase_cycles', 'tree_sha256', 'node_sram_sha256', 'child_sram_sha256']:
        if actual[field] != expected[field]:
            raise ValueError(f'{destination.name}: changed {field}')
    for field in ['events_sha256', 'neural_trace_sha256']:
        if actual[field] != expected[field]:
            raise ValueError(f'{destination.name}: changed {field}')
    operations = hashlib.sha256(json.dumps(expected['memory_operations'], sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    if actual['operations_sha256'] != operations:
        raise ValueError('Changed memory-operation census')
    for field in ['latency_ms', 'core_energy_mj', 'core_average_power_mw', 'core_area_mm2']:
        near(costs[field], expected['costs'][field], destination.name + ' ' + field)
    if costs['profile'] != expected['costs']['profile']:
        raise ValueError('Wrong live cost profile')
    result = dict(board_size=config['board_size'], iterations=config['iterations'],
                  model_id=config['model_id'], status='PASS', cycles=actual['cycles'],
                  checked_hashes=[k for k in ['tree_sha256', 'node_sram_sha256', 'child_sram_sha256', 'events_sha256', 'neural_trace_sha256'] if k in actual],
                  host_seconds=time.perf_counter() - start,
                  hardware_latency_ms=costs['latency_ms'])
    save(destination / 'comparison.json', result)
    print(f"PASS {config['board_size']}x{config['board_size']} {config['iterations']} {config['model_id']}", flush=True)
    return result


def main():
    global RUNTIME_SOURCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['verify', 'hero', 'scaling', 'figures', 'tests', 'all', 'studio'])
    parser.add_argument('--artifacts', type=Path, help='Checksum-verified external input store for full execution.')
    parser.add_argument('--output', type=Path, help='New output directory. Default: outputs/run_<UTC>.')
    parser.add_argument('--jobs', type=int, choices=[1, 2], default=1)
    parser.add_argument('--port', type=int, default=4784, help='Local Studio port, used only by studio.')
    parser.add_argument('--verify-render', action='store_true', help='Compare figure pixels using optional PyMuPDF.')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535')
    checked = verify_manifest()
    data = verify_data()
    output = (args.output or ROOT / 'outputs' / datetime.now(timezone.utc).strftime('run_%Y%m%d_%H%M%S_%fZ')).resolve()
    output.mkdir(parents=True, exist_ok=False)
    if args.command == 'studio':
        studio_source = output / 'studio_source'
        hydrate_source(studio_source, args.artifacts)
        runs = studio_source / 'p04_results' / 'p01_runs'
        runs.mkdir(parents=True, exist_ok=True)
        save(runs.parent / 'index.json', dict(schema_version=1, cases={}))
        save(output / 'studio_launcher.json', dict(status='LAUNCHED', port=args.port, registry=str(runs), figure3d='ON_HOLD_EXCLUDED'))
        print(f'Studio outputs: {output}', flush=True)
        os.chdir(studio_source)
        env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
        env.pop('PYTHONPATH', None)
        code = 'import sys; from p05_studio.p00_app.server import serve; serve(port=int(sys.argv[1]), runs=sys.argv[2])'
        os.execve(sys.executable, [sys.executable, '-B', '-c', code, str(args.port), str(runs)], env)
    if args.command in ('hero', 'scaling', 'tests', 'all'):
        RUNTIME_SOURCE = hydrate_source(output / 'runtime_source', args.artifacts)
    report = dict(status='RUNNING', manifest_files_checked=checked, retained_data_checks=data,
                  figure3d='ON_HOLD_EXCLUDED', physical_validation=False)
    save(output / 'verification.json', report)
    try:
        if args.command in ['hero', 'all']:
            report['hero'] = execute_case(read('configs/hero.json'), read('data/primary/hero.json'), output / 'hero')
        if args.command in ['scaling', 'all']:
            retained = {(r['board_size'], r['iterations']): r for r in read('data/scaling/diagnostic_results.json')}
            def execute(config):
                name = f"diagnostic_{config['board_size']}x{config['board_size']}_{config['budget']}"
                return execute_case(config, retained[config['board_size'], config['iterations']], output / name)
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                report['scaling'] = list(pool.map(execute, read('configs/scaling.json')))
        if args.command in ['figures', 'all']:
            command = [sys.executable, '-B', 'figures/regenerate.py']
            if args.verify_render: command.append('--verify-render')
            run_command(command, ROOT, output / 'figures.log')
            report['figures'] = read('figures/generated/replot_verification.json')
        if args.command in ['tests', 'all']:
            test_source = output / 'native_test_source'
            shutil.copytree(RUNTIME_SOURCE, test_source, ignore=shutil.ignore_patterns('__pycache__', '.DS_Store'))
            run_command([sys.executable, '-B', 'verify_runtime.py', '--report', str(output / 'native_tests.json')], test_source, output / 'tests.log')
            shutil.rmtree(test_source)
            report['native_tests'] = 'PASS; see tests.log for count and scope'
    except Exception as exc:
        report['status'] = 'FAIL'
        report['error'] = str(exc)
        save(output / 'verification.json', report)
        raise
    report['status'] = 'PASS'
    save(output / 'verification.json', report)
    print(json.dumps(dict(status='PASS', command=args.command, report=str(output / 'verification.json')), indent=2))


if __name__ == '__main__':
    main()
