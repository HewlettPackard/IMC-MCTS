# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Fresh regressions and read-only checks of the protected research artifacts.
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import time
import unittest

from core.architecture.result_registry import ROOT, new_run, write_json
from core.architecture.result_snapshot import verify_snapshot
from p03_experiments.p35_component_ppa.verify_preservation import digest, entries

HERE = Path(__file__).resolve().parent


def main():
    out = new_run(HERE/'p01_checks')
    names = ['offset_encoding','eight_adc','parallel_selection','controller_estimates','single_child',
        'studio_play','tree_memory','result_snapshot','column_hold_validation','trace_reuse','studio_payload',
        'prepared_costs','studio_views','studio_pipeline','neural_mapping','neural_rtl_timing','complete_profile',
        'analog_readout','go_value_convention','workbook_models_go','paper_models','run_reproducibility',
        'ppa_audit','component_ppa','digital_costs','sram_costs','block_power','cost_ledger']
    suite = unittest.defaultTestLoader.loadTestsFromNames(['tests.test_'+n for n in names])
    print(out,suite.countTestCases(),'tests',flush=True)
    start = time.perf_counter()
    with (out/'tests.txt').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    errors = []
    baseline = json.loads((HERE/'baseline.json').read_text())
    before = json.loads((ROOT/baseline['run']/'protected_sha256.json').read_text())
    for name,expected in before.items():
        if not (ROOT/name).is_file() or digest(ROOT/name)!=expected: errors.append(name)
    master = json.loads((ROOT.parent/'p00_recovery/run_20260908_182606Z/source_manifest.json').read_text())
    if entries(Path(master['source']))!=master['entries']: errors.append('preserved master')
    older = json.loads((ROOT/'p03_experiments/p42_reference_validation/before.json').read_text())
    for field in ('old_checkout_sources','old_user_files'):
        for name,expected in older[field].items():
            if digest(Path(older['original_repair_checkout'])/name)!=expected: errors.append('older checkout: '+name)
    frozen = list((ROOT/'p04_results/p04_snapshots').glob('run_*'))
    for folder in frozen: verify_snapshot(folder)
    record = {'status':'passed' if result.wasSuccessful() and not errors else 'failed',
        'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'skipped':len(result.skipped),'preservation_errors':errors,'protected_files':len(before),
        'master_files':sum(r['type']=='file' for r in master['entries'].values()),
        'older_checkout_files':len(older['old_checkout_sources'])+len(older['old_user_files']),
        'frozen_snapshots':len(frozen),'elapsed_seconds':time.perf_counter()-start,
        'benchmarks_executed':False,'master_git_commands':False,'modules':names}
    write_json(out/'verification.json',record)
    sources = list((ROOT/'core/architecture').glob('offset*'))+[ROOT/'tests/test_offset_encoding.py']+list(HERE.glob('*.py'))
    write_json(out/'source_sha256.json',{str(p.relative_to(ROOT)):digest(p) for p in sources})
    (out/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file()))
    write_json(HERE/'latest_checks.json',{'run':str(out.relative_to(ROOT))})
    print({k:v for k,v in record.items() if k!='modules'},flush=True)
    assert result.wasSuccessful(),(out/'tests.txt').read_text()
    assert not errors,errors


if __name__ == '__main__': main()
