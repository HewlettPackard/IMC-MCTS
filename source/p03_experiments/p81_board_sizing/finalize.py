# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Bind the board-sizing evidence without rewriting historical results.
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import tarfile

from core.architecture.board_sizing import board_table, memory_characterization
from core.architecture.result_registry import ROOT, write_json
from core.architecture.result_snapshot import verify_snapshot
from p03_experiments.p35_component_ppa.verify_preservation import entries

HERE = Path(__file__).parent
OUT = ROOT / json.loads((HERE / 'latest.json').read_text())['run']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    log = (OUT / 'tests_all_final.log').read_text()
    assert 'Ran 255 tests' in log and '\nOK\n' in log
    assert '\nFAILED' not in log and '\nFAIL:' not in log and '\nERROR:' not in log
    assert read(OUT / 'browser_checks.json')['status'] == 'passed'
    assert read(OUT / 'reference_before.json') == read(OUT / 'reference_after.json')
    memory_characterization()
    for name, digest in read(OUT / 'sweep_source_sha256.json').items():
        assert sha(ROOT / name) == digest, name
    reference = read(OUT / 'high_budget_results.json')
    optimized = read(OUT / 'optimized_high_budget_results.json')['rows']
    capacity = []
    for model, rows in [('studio_reference', reference), ('optimized_figure', optimized)]:
        assert len(rows) == 6
        for setting, row in zip(board_table()['boards'], rows):
            memory = row['memory']
            assert row['board_size'] == setting['board_size']
            assert row['status'] == 'complete'
            assert row.get('completed_iterations', row.get('completed')) == setting['iterations']['high']
            assert memory['cam_entries'] == setting['cam_entries']
            assert memory['node_sram_bytes'] == 1024 * setting['node_sram_kib']
            assert memory['child_sram_bytes'] == 1024 * setting['child_sram_kib']
            assert setting['iterations']['high'] + 1 <= memory['node_capacity']
            assert setting['iterations']['high'] <= memory['edge_capacity']
            assert memory['path_storage_entries'] == 2 * setting['board_size']**2 + 1
            assert sum(row['phase_cycles'].values()) == row['cycles']
            if model == 'studio_reference':
                pools = row['costs']['sram']['pools']
                assert pools['node_sram']['capacity_bytes'] == memory['node_sram_bytes']
                assert pools['child_sram']['capacity_bytes'] == memory['child_sram_bytes']
            capacity.append({'engine': model, 'board_size': row['board_size'],
                'completed': setting['iterations']['high'], 'node_capacity': memory['node_capacity']})

    changed = {
        'core/architecture/result_registry.py', 'core/architecture/crossbar_workbook.py',
        'core/architecture/sram_costs.py', 'core/architecture/peripheral_costs.py',
        'core/architecture/digital_costs.py', 'core/architecture/column_hold_controller_validation.json',
        'core/architecture/complete_controller_validation.json', 'p05_studio/p00_app/server.py',
        'p05_studio/p01_static/index.html', 'p05_studio/p01_static/visuals.js', 'p05_studio/p01_static/app.js',
        'tests/test_tree_update_revision.py', 'p05_studio/README.md'}
    prior = read(OUT / 'before_sha256.json')
    observed = {name for name, digest in prior.items() if sha(ROOT / name) != digest}
    assert observed <= changed, observed - changed
    preserved = len(prior) - len(observed)

    old_run = ROOT / 'p03_experiments/p79_scalability/p00_runs/run_20260917_155326Z'
    paper_run = ROOT / 'p03_experiments/p80_blue_scaling_table/p00_runs/run_20260917_162012Z'
    paper = read(paper_run / 'metadata.json')
    prior_checks = 0
    for name, digest in read(old_run / 'protected_sha256.json').items():
        path = Path(name)
        relative = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else None
        if relative in changed or (relative and relative.startswith('p05_studio/p02_runtime/')):
            continue
        if name == paper['live_source']:
            assert sha(path) == paper['after_sha256']
        else:
            assert sha(path) == digest, name
        prior_checks += 1
    artifact_count = 0
    for folder in (old_run, paper_run):
        for line in (folder / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            assert sha(folder / name) == digest, name
            artifact_count += 1

    master = read(ROOT.parent / 'p00_recovery/run_20260908_182606Z/source_manifest.json')
    assert entries(Path(master['source'])) == master['entries']
    old = read(ROOT / 'p03_experiments/p42_reference_validation/before.json')
    old_count = 0
    for field in ('old_checkout_sources', 'old_user_files'):
        for name, digest in old[field].items():
            assert sha(Path(old['original_repair_checkout']) / name) == digest, name
            old_count += 1
    snapshots = list((ROOT / 'p04_results/p04_snapshots').glob('run_*'))
    for folder in snapshots:
        verify_snapshot(folder)
    write_json(OUT / 'verification.json', {'status': 'passed', 'regression_tests': 255,
        'reference_records_identical': 32, 'completed_high_budget_cases': capacity,
        'browser_checks_passed': True, 'cost_capacity_matching': True,
        'pre_edit_sources_preserved': preserved, 'allowed_existing_source_changes': sorted(observed),
        'prior_protected_files_checked': prior_checks, 'prior_round_artifacts_checked': artifact_count,
        'original_master_files_preserved': sum(r['type'] == 'file' for r in master['entries'].values()),
        'older_checkout_files_preserved': old_count, 'frozen_snapshots_preserved': len(snapshots),
        'paper_unchanged_since_round_80': True, 'optimized_compute_promoted_to_studio': False,
        'new_RTL_validation': False, 'physical_PPA_validated': False})
    sources = []
    for folder in ('core', 'p05_studio/p00_app', 'p05_studio/p01_static', 'tests'):
        sources += [p for p in (ROOT / folder).rglob('*') if p.is_file() and p.suffix in ('.py', '.json', '.js', '.html', '.css')]
    sources += [p for p in HERE.iterdir() if p.is_file()]
    sources += [ROOT / 'PLAN_ROUND_81.md', ROOT / 'ARCH_MENTOR.md', ROOT / 'p05_studio/README.md']
    source_map = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    write_json(OUT / 'source_sha256.json', source_map)
    with tarfile.open(OUT / 'source_snapshot.tar.gz', 'w:gz') as archive:
        for name in sorted(source_map):
            archive.add(ROOT / name, arcname=name, recursive=False)
    # Live server logs continue to grow; they are process observations, not frozen evidence.
    excluded = {'SHA256SUMS', 'studio_server.log', 'finalize.log'}
    (OUT / 'SHA256SUMS').write_text(''.join(sha(p) + '  ' + str(p.relative_to(OUT)) + '\n'
        for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in excluded))
    print('PASS: 255 tests, 12 high-budget cases, browser and preservation checks')


if __name__ == '__main__':
    main()
