# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Close the experiment by verifying saved bytes, sources, coverage and actual budgets.
# SPDX-License-Identifier: MIT
import csv
import gzip
import hashlib
import json
from pathlib import Path

from core.architecture.result_registry import ROOT, new_run, verify_run, write_json


def main():
    experiment=Path(__file__).parent; out=new_run(experiment/'p00_runs')
    latest=json.loads((experiment/'latest.json').read_text())
    cost=json.loads((ROOT/latest['costs']/'metadata.json').read_text())
    large=json.loads((ROOT/latest['large']/'metadata.json').read_text())
    tests=experiment/'p00_runs/run_20260915_212955Z'
    browser=experiment/'p00_runs/run_20260915_212954Z'
    unit=json.loads((tests/'metadata.json').read_text());ui=json.loads((browser/'metadata.json').read_text())
    assert all(record['status']=='passed' for record in (cost,large,unit,ui))
    assert unit['tests']==188 and unit['failures']==unit['errors']==unit['skipped']==0
    assert len(ui['checks'])==27 and ui['errors']==[]
    for name,sha in unit['sources'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    checked=[]
    for entry in cost['cases']+large['runs']:
        folder=ROOT/entry['run'];result=verify_run(folder)
        assert result['costs']['ledger']['missing_area']==result['costs']['ledger']['missing_energy']==[]
        assert len(result['costs']['ledger']['controller_report_proxy_components'])==4
        for name,sha in result['identity']['source_sha256'].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,('source drift',name)
        if 'memory_snapshot' in entry:
            for pool,length in [('node',1572864),('child',524288)]:
                data=gzip.decompress((ROOT/entry['memory_snapshot']/(pool+'.bin.gz')).read_bytes())
                assert len(data)==length
                assert hashlib.sha256(data).hexdigest()==result[pool+'_sram_sha256']
            summary=next(csv.DictReader((folder/'summary.csv').open()))
            assert int(summary['iterations'])==entry['completed_iterations']
            assert int(summary['requested_iterations'])==entry['requested_iterations']
            assert summary['status']==entry['status']
        checked.append(entry['run'])
    assert len(large['runs'])==8 and len(set(row['area_mm2'] for row in large['runs']))==1
    metadata={'status':'passed','tested_python_sources_match':True,'saved_run_sources_match':True,
        'verified_runs':checked,'tests':188,'browser_checks':27,'browser_errors':[],
        'cost_comparisons':cost['comparisons'],'large_comparisons':large['accounting_comparisons'],
        'large_memory_snapshots':8,'installed_memory_bytes':2097152,
        'controller_characterization_complete':False,'whole_chip_ppa_available':False}
    write_json(out/'metadata.json',metadata)
    (out/'SHA256SUMS').write_text(hashlib.sha256((out/'metadata.json').read_bytes()).hexdigest()+'  metadata.json\n')
    latest.update(tests=str(tests.relative_to(ROOT)),browser=str(browser.relative_to(ROOT)),closure=str(out.relative_to(ROOT)))
    write_json(experiment/'latest.json',latest)
    print(out,metadata,flush=True)


if __name__=='__main__':main()
