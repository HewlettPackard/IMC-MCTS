# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Focused regressions for execution, observation, source binding and PPA.
# SPDX-License-Identifier: MIT
import hashlib
from pathlib import Path
import time
import unittest

from core.architecture.result_registry import ROOT, new_run, write_json


def main():
    out = new_run(Path(__file__).parent / 'p00_runs')
    names = ['single_child','studio_play','tree_memory','result_snapshot','column_hold_validation','trace_reuse', 'studio_payload', 'prepared_costs', 'studio_views', 'studio_pipeline',
        'neural_mapping', 'neural_rtl_timing', 'complete_profile', 'analog_readout',
        'go_value_convention', 'workbook_models_go', 'paper_models', 'run_reproducibility',
        'ppa_audit', 'component_ppa', 'digital_costs', 'sram_costs', 'block_power', 'cost_ledger']
    suite = unittest.defaultTestLoader.loadTestsFromNames(['tests.test_' + name for name in names])
    print(out, suite.countTestCases(), 'tests', flush=True)
    started = time.perf_counter()
    with (out / 'tests.txt').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    record = {'status': 'passed' if result.wasSuccessful() else 'failed', 'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
        'elapsed_s': time.perf_counter() - started, 'modules': names,
        'sources': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for prefix in ('core', 'p05_studio/p00_app') for p in (ROOT / prefix).rglob('*.py')}}
    write_json(out / 'metadata.json', record)
    (out / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n'
        for p in sorted(out.iterdir()) if p.is_file()))
    print({k:v for k,v in record.items() if k not in ('sources', 'modules')}, flush=True)
    assert result.wasSuccessful(), (out / 'tests.txt').read_text()


if __name__ == '__main__':
    main()
