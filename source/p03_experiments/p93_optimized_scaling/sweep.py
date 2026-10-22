# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Execute all agreed budgets after the stable-source regression gate passes.
# SPDX-License-Identifier: MIT
import json,os,subprocess,sys,time
from pathlib import Path
from core.architecture.board_sizing import board_table
HERE=Path(__file__).resolve().parent
start=time.monotonic()
while '\nOK\n' not in (HERE/'all_tests_final.log').read_text():
    text=(HERE/'all_tests_final.log').read_text()
    if '\nFAILED (' in text:raise RuntimeError('Regression gate failed; sweep not started')
    if time.monotonic()-start>600:raise TimeoutError('Regression gate did not finish')
    time.sleep(5)
print('Full regression gate passed; starting 18 cases',flush=True)
records=[]
for row in board_table()['boards']:
    for tier in ('low','medium','high'):
        before=set((HERE/'p01_runs').glob('run_*'))
        completed=subprocess.run([sys.executable,'-B','-m','p03_experiments.p93_optimized_scaling.run',
            '--board',str(row['board_size']),'--budget',tier],check=True)
        added=set((HERE/'p01_runs').glob('run_*'))-before
        assert len(added)==1
        folder=added.pop();result=json.loads((folder/'result.json').read_text())
        assert result['status']=='complete' and result['iterations']==row['iterations'][tier]
        records.append(str(folder.relative_to(HERE)))
        (HERE/'sweep_progress.json').write_text(json.dumps({'completed':len(records),'runs':records},indent=2)+'\n')
        time.sleep(1)
(HERE/'sweep_manifest.json').write_text(json.dumps({'status':'complete','cases':18,'seed':0,
    'weights':'seeded_random_hardware_diagnostic','runs':records},indent=2)+'\n')
print('COMPLETE: 18 of 18 approved searches',flush=True)
