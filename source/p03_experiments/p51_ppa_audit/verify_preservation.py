# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Read-only integrity checks for original projects, frozen data and this audit.
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import subprocess

from core.architecture.result_registry import ROOT, write_json
from core.architecture.result_snapshot import SNAPSHOTS, verify_snapshot
from p03_experiments.p35_component_ppa.verify_preservation import digest, entries


def main():
    experiment = Path(__file__).parent
    before = json.loads((experiment / 'before.json').read_text())
    errors = []
    for name, sha in before['protected_sha256'].items():
        if digest(ROOT / name) != sha:
            errors.append('protected:' + name)
    for name, sha in before['static_sha256'].items():
        if digest(ROOT / name) != sha:
            errors.append('studio:' + name)
    if digest(ROOT / 'PLAN_ROUND_47.md') != before['preexisting_docs']['PLAN_ROUND_47.md']:
        errors.append('preexisting proposal')
    original = json.loads((ROOT.parent / 'p00_recovery/run_20260908_182606Z/source_manifest.json').read_text())
    actual = entries(Path(original['source']))
    errors.extend('master:' + name for name in set(actual) | set(original['entries']) if actual.get(name) != original['entries'].get(name))
    old = json.loads((ROOT / 'p03_experiments/p42_reference_validation/before.json').read_text())
    for group in ('old_checkout_sources', 'old_user_files'):
        for name, sha in old[group].items():
            if digest(Path(old['original_repair_checkout']) / name) != sha:
                errors.append('older checkout:' + name)
    for name in before['user_directories']:
        if not (ROOT / name).is_dir():
            errors.append('user folder:' + name)
    snapshots = [verify_snapshot(path)['id'] for path in sorted(SNAPSHOTS.glob('run_*'))]
    assert len(snapshots) == 14
    declarations = 0
    for sums in experiment.rglob('SHA256SUMS'):
        for line in sums.read_text().splitlines():
            sha, name = line.split('  ', 1)
            path = (sums.parent / name).resolve()
            if not path.is_relative_to(ROOT) or digest(path) != sha:
                errors.append('audit artifact:' + str(path))
            declarations += 1
    changed = subprocess.check_output(['git', 'diff', '--name-only', before['baseline']], cwd=ROOT, text=True).splitlines()
    allowed = {'ARCH_MENTOR.md', 'PLAN_ROUND_50.md', 'PLAN_ROUND_51.md', 'tests/test_ppa_audit.py'}
    errors.extend('scope:' + name for name in changed if name not in allowed and not name.startswith(('p03_experiments/p50_ppa_assurance/', 'p03_experiments/p51_ppa_audit/')))
    result = {'status': 'failed' if errors else 'passed', 'errors': errors,
        'protected_files': len(before['protected_sha256']), 'unchanged_studio_files': len(before['static_sha256']),
        'master_files': sum(r['type'] == 'file' for r in actual.values()), 'master_directories': sum(r['type'] == 'directory' for r in actual.values()),
        'older_checkout_files': sum(len(old[g]) for g in ('old_checkout_sources', 'old_user_files')),
        'snapshots': snapshots, 'user_directories': len(before['user_directories']), 'artifact_declarations': declarations,
        'changed_tracked_paths': changed, 'master_git_commands': False, 'benchmarks_executed': False,
        'production_changed': False, 'existing_results_changed': False}
    write_json(experiment / 'preservation.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('snapshots', 'changed_tracked_paths')}, indent=2), flush=True)
    assert not errors, errors


if __name__ == '__main__':
    main()
