# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Verify frozen evidence, originals and user sessions without modifying them.
# SPDX-License-Identifier: MIT
import json
from pathlib import Path

from core.architecture.result_registry import ROOT, new_run, write_json
from core.architecture.result_snapshot import verify_snapshot
from p03_experiments.p35_component_ppa.verify_preservation import digest, entries


def main():
    experiment=Path(__file__).parent;out=new_run(experiment/'p00_runs');errors=[]
    prior=ROOT/'p03_experiments/p61_single_child'
    before=json.loads((ROOT/json.loads((prior/'baseline.json').read_text())['run']/'before.json').read_text())
    for name,sha in before['protected_sha256'].items():
        if not (ROOT/name).is_file() or digest(ROOT/name)!=sha:errors.append(name)
    master=json.loads((ROOT.parent/'p00_recovery/run_20260908_182606Z/source_manifest.json').read_text())
    if entries(Path(master['source']))!=master['entries']:errors.append('preserved master')
    old=json.loads((ROOT/'p03_experiments/p42_reference_validation/before.json').read_text())
    for field in ('old_checkout_sources','old_user_files'):
        for name,sha in old[field].items():
            if digest(Path(old['original_repair_checkout'])/name)!=sha:errors.append('older checkout: '+name)
    snapshots=list((ROOT/'p04_results/p04_snapshots').glob('run_*'))
    for folder in snapshots:verify_snapshot(folder)
    declarations=0
    for folder in (prior,experiment):
        for sums in folder.rglob('SHA256SUMS'):
            for line in sums.read_text().splitlines():
                sha,name=line.split('  ',1)
                if digest(sums.parent/name)!=sha:errors.append(str(sums.parent/name))
                declarations+=1
    record={'status':'failed' if errors else 'passed','errors':errors,
        'protected_files':len(before['protected_sha256']),
        'master_files':sum(row['type']=='file' for row in master['entries'].values()),
        'older_checkout_files':len(old['old_checkout_sources'])+len(old['old_user_files']),
        'frozen_snapshots':len(snapshots),'artifact_declarations':declarations,
        'benchmarks_executed':False,'master_git_commands':False}
    write_json(out/'metadata.json',record)
    (out/'SHA256SUMS').write_text(digest(out/'metadata.json')+'  metadata.json\n')
    print(out,record,flush=True);assert not errors,errors


if __name__=='__main__':main()
