# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import argparse
import contextlib
import gzip
import hashlib
import io
import json
import math
import os
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from core.architecture.accelerator_api import Accelerator
from core.architecture.sram_costs import load_sram_profile
from p03_experiments.p07_neural_mapping.run import check_trace, save_trace
from p03_experiments.p08_cost_sources.audit_digital import audit
from p03_experiments.p08_cost_sources.characterize import sha, write_json


ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / 'p03_experiments/p07_neural_mapping/p00_runs/run_20260909_020327Z/p00_data'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    data = out / 'p02_simulation'
    data.mkdir()
    paths = [path for package in ('core', 'py_sst_cpp', 'tests')
             for path in sorted((ROOT / package).rglob('*.py'))]
    paths += [ROOT/'core/architecture/sram_characterization.json', ROOT/'pyproject.toml', ROOT/'Makefile',
              ROOT/'p03_experiments/p07_neural_mapping/run.py']
    paths += list(sorted(Path(__file__).parent.glob('*.py')))
    hashes = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    write_json(out/'source_sha256.json', hashes)
    with tarfile.open(out/'source_snapshot.tar.gz', 'w:gz') as archive:
        for path in paths:
            archive.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    write_json(out/'digital_provenance.json', audit())
    metadata = {'started_utc': datetime.now(timezone.utc).isoformat(), 'status': 'running',
        'argv': [sys.executable, '-B', '-m', 'p03_experiments.p08_cost_sources.run', '--out', str(out)],
        'starting_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'baseline_sha256': {p.name: sha(p) for p in BASELINE.glob('*.json') if p.name in (
            'reference_5000.json', 'mapped_2.json', 'mapped_200.json', 'mapped_5000.json')},
        'environment': {name: os.environ.get(name) for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS')},
        'evidence_class': 'partial_analytical_SRAM_costs_with_uncalibrated_serial_chip_timing',
        'benchmarks_executed': False}
    write_json(out/'metadata.json', metadata)
    checks = {}
    results = {}
    cases = [('reference_5000', 5000, 'reference', 'reference', False),
             ('mapped_2', 2, 'mapped', 'reference', False),
             ('mapped_5000', 5000, 'mapped', 'reference', False),
             ('lstp_2', 2, 'mapped', 'cacti_22nm_lstp', True),
             ('lstp_200', 200, 'mapped', 'cacti_22nm_lstp', True),
             ('lstp_5000', 5000, 'mapped', 'cacti_22nm_lstp', False),
             ('hp_5000', 5000, 'mapped', 'cacti_22nm_hp', False),
             ('lstp_200_repeat', 200, 'mapped', 'cacti_22nm_lstp', False)]
    for name, iterations, neural_mode, memory_profile, capture in cases:
        print('Simulating', name, flush=True)
        with contextlib.redirect_stdout(io.StringIO()):
            result = asdict(Accelerator(board_size=9, iterations=iterations, seed=0,
                neural_mode=neural_mode, memory_profile=memory_profile,
                capture_memory_trace=capture).analyze('simulate'))
        memory = result['simulation']['memory']
        if capture:
            transactions = memory.pop('transactions')
            template = result['simulation']['neural'].pop('trace')
            save_trace(data/f'{name}.transactions.jsonl.gz', transactions)
            save_trace(data/f'{name}.neural_template.jsonl.gz', template)
            checks.update({name+':'+key: bool(value) for key, value in check_trace(result, transactions, template).items()})
            for row in transactions:
                if row['resource'] in ('node_sram', 'child_sram'):
                    checks[name+':physical_word_service'] = checks.get(name+':physical_word_service', True) and (
                        row['end']-row['start'] == row['bytes']//4*2)
        baseline_name = ('reference_' if neural_mode == 'reference' else 'mapped_') + str(iterations)
        baseline = json.loads((BASELINE/(baseline_name+'.json')).read_text())
        if memory_profile == 'reference':
            for key in ('cycles', 'tree_sha256'):
                checks[name+':'+key+'_preserved'] = result['simulation'][key] == baseline['simulation'][key]
            checks[name+':memory_preserved'] = memory == baseline['simulation']['memory']
            checks[name+':evaluator_preserved'] = result['evaluator'] == baseline['evaluator']
        else:
            profile = load_sram_profile(memory_profile)
            cost = result['accounting']['sram']
            operations = memory['operations']
            reads = operations.get('node_sram_read_words', 0) + operations.get('child_sram_read_words', 0)
            writes = operations.get('node_sram_write_words', 0) + operations.get('child_sram_write_words', 0)
            checks[name+':same_work'] = operations == baseline['simulation']['memory']['operations']
            checks[name+':tree_preserved'] = result['simulation']['tree_sha256'] == baseline['simulation']['tree_sha256']
            checks[name+':exact_cycle_delta'] = result['simulation']['cycles'] == baseline['simulation']['cycles'] + reads + writes
            checks[name+':elapsed_time'] = result['latency_us'] == result['simulation']['cycles']/500
            checks[name+':whole_chip_cost_unavailable'] = all(result[key] is None for key in ('energy_uj', 'area_mm2', 'power_mw'))
            checks[name+':dynamic_access_energy'] = math.isclose(cost['dynamic_energy_nj'],
                reads * profile['macro']['read_energy_nj'] + writes * profile['macro']['write_energy_nj'], rel_tol=1e-12)
            checks[name+':leakage_full_duration'] = math.isclose(cost['leakage_energy_nj'],
                4 * profile['macro']['leakage_mw'] * result['latency_us'], rel_tol=1e-12)
            checks[name+':energy_units'] = math.isclose(cost['energy_uj']*1000,
                cost['dynamic_energy_nj'] + cost['leakage_energy_nj'], rel_tol=1e-12)
            checks[name+':average_power_units'] = math.isclose(cost['average_power_mw']*result['latency_us'],
                cost['energy_uj']*1000, rel_tol=1e-12)
            checks[name+':exact_capacity'] = memory['config']['node_sram_bytes'] + memory['config']['child_sram_bytes'] == 2*1024**2
        write_json(data/(name+'.json'), result)
        results[name] = result
    first, repeated = results['lstp_200'], results['lstp_200_repeat']
    checks['repeat:identity'] = first['run_identity'] == repeated['run_identity']
    checks['repeat:memory'] = first['simulation']['memory'] == repeated['simulation']['memory']
    checks['repeat:cost'] = first['accounting'] == repeated['accounting']
    checks['profile:distinct_identity'] = results['hp_5000']['run_identity']['configuration_sha256'] != results['lstp_5000']['run_identity']['configuration_sha256']
    checks['profile:same_search_timing'] = results['hp_5000']['simulation']['cycles'] == results['lstp_5000']['simulation']['cycles']
    command = ['make', 'check', f'PYTHON={sys.executable} -B']
    print('Running make check', flush=True)
    with tempfile.TemporaryDirectory(prefix='python_cache_', dir=out) as cache:
        tested = subprocess.run(command, cwd=ROOT, env=dict(os.environ, PYTHONPYCACHEPREFIX=cache),
                                capture_output=True, timeout=180)
    for stream in ('stdout', 'stderr'):
        (out/('make_check.'+stream+'.gz')).write_bytes(gzip.compress(getattr(tested, stream), mtime=0))
    metadata['make_check'] = {'argv': command, 'returncode': tested.returncode}
    checks['make_check'] = tested.returncode == 0
    checks['sources_unchanged'] = all(sha(ROOT/name) == value for name, value in hashes.items())
    write_json(out/'checks.json', checks)
    metadata.update(status='passed' if all(checks.values()) else 'failed', finished_utc=datetime.now(timezone.utc).isoformat())
    write_json(out/'metadata.json', metadata)
    print(f'{sum(checks.values())}/{len(checks)} checks passed', flush=True)
    if not all(checks.values()):
        raise RuntimeError('Evidence checks failed; inspect saved logs')


if __name__ == '__main__':
    main()
