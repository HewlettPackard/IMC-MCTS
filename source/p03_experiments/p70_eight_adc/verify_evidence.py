# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Check final source/artifact identities, including the preserved prior revision.
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path

from core.architecture.result_registry import ROOT,new_run,write_json


def main():
    exp=Path(__file__).resolve().parent; out=new_run(exp/'p01_checks')
    comparison=exp/'p00_runs/run_20260916_044042Z'
    tests=exp/'p01_checks/run_20260916_044101Z'
    preservation=exp/'p01_checks/run_20260916_044204Z'
    reference=ROOT/'p03_experiments/p69_parallel_selection/p00_runs/run_20260916_042741Z'
    checks=0
    for folder in (comparison,tests,preservation,reference):
        for line in (folder/'SHA256SUMS').read_text().splitlines():
            digest,name=line.split('  ',1)
            assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest,name
            checks+=1
    for table in (json.loads((comparison/'source_sha256.json').read_text()),
                  json.loads((tests/'metadata.json').read_text())['sources'],
                  json.loads((reference/'source_sha256.json').read_text())):
        for name,digest in table.items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    suite=json.loads((tests/'metadata.json').read_text())
    assert suite['tests']==203 and suite['status']=='passed'
    assert suite['failures']==suite['errors']==suite['skipped']==0
    assert json.loads((preservation/'preservation.json').read_text())['status']=='passed'
    pairs=json.loads((comparison/'verification.json').read_text())
    assert pairs['status']=='passed' and pairs['source_count']==388
    assert all(row['all_neural_states_match'] and row['full_sram_matches'] for row in pairs['comparisons'])
    record={'status':'passed','artifact_checksums':checks,'experiment_sources':388,
        'regression_tests':203,'current_sources_match':True,'prior_selection_sources_and_results_match':True,
        'new_RTL_proof':False,'physical_timing_closure':False,'whole_chip_claim':False,
        'closure_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    write_json(out/'closure.json',record)
    (out/'SHA256SUMS').write_text(hashlib.sha256((out/'closure.json').read_bytes()).hexdigest()+'  closure.json\n')
    write_json(exp/'latest.json',{'comparison':str(comparison.relative_to(ROOT)),
        'tests':str(tests.relative_to(ROOT)),'preservation':str(preservation.relative_to(ROOT)),
        'reference':str(reference.relative_to(ROOT)),'closure':str(out.relative_to(ROOT))})
    print(out,record)


if __name__=='__main__': main()
