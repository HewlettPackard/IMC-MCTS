# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Check the persistent studio and exact frozen exports without starting a job.
# SPDX-License-Identifier: MIT
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect
from core.architecture.result_registry import ROOT, write_json
from core.architecture.result_snapshot import latest_snapshot


def main():
    out=Path(__file__).parent/'p00_runs'/datetime.now(timezone.utc).strftime('run_%Y%m%d_%H%M%SZ')
    out.mkdir(parents=True,exist_ok=False); url='http://127.0.0.1:4781'; checks={}; errors=[]
    snapshot=latest_snapshot(); saved=ROOT/'p04_results/p04_snapshots'/snapshot['id']
    def fetch(path):
        with urlopen(url+path,timeout=20) as response: return response.read()
    health=json.loads(fetch('/api/health'))
    checks['health']=health['status']=='ok'
    checks['cost_model_version']=health['cost_model_profile']=='imc_22nm_costs_v1'
    digital=json.loads(fetch('/api/components?board=9'))['digital']
    checks['digital_6_matching_modules']=digital['priced_instances']==6
    checks['native_v2_report']=digital['timing_violations']==[] and next(r for r in digital['components'] if r['instance']=='u_upd')['native_65nm_area_um2']==35855.520030
    checks['digital_catalog_identity']=digital['profile_sha256']==hashlib.sha256((ROOT/'core/architecture/digital_characterization.json').read_bytes()).hexdigest()
    checks['snapshot_manifest']=json.loads(fetch('/api/snapshot'))['snapshot']==snapshot
    for name in ['summary.csv','manifest.json','SHA256SUMS']:
        checks['saved_'+name]=fetch('/api/snapshots/'+snapshot['id']+'/'+name)==(saved/name).read_bytes()
    with sync_playwright() as tool:
        browser=tool.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1100})
        page.on('pageerror',lambda e:errors.append(str(e))); page.goto(url)
        expect(page.locator('#snapshot-csv')).to_be_visible()
        expect(page.locator('#component-summary')).to_contain_text('6 digital parent instances priced')
        expect(page.locator('#component-rows')).to_contain_text('vectorless dynamic')
        expect(page.locator('#digital-timing-note')).to_contain_text('22 nm clock closure is unvalidated')
        checks['physical_timing_limit_visible']=True
        checks['module_costs_visible_in_running_studio']=True
        data=page.request.get(url+page.locator('#snapshot-csv').get_attribute('href')).body()
        (out/'download.csv').write_bytes(data); checks['browser_download_exact']=data==(saved/'summary.csv').read_bytes()
        if json.loads(fetch('/api/session'))['job'] is None:
            expect(page.locator('#readout-profile')).to_have_value('sustained_drive_v1')
            page.locator('#readout-profile').select_option('column_hold_v1')
            expect(page.locator('#fidelity-note')).to_contain_text('control is checked in RTL')
            expect(page.locator('#readout-summary')).to_contain_text('512 column samples installed')
            checks['new_scope_and_default_visible']=True
        else: checks['active_session_preserved']=True
        page.locator('.components-panel').screenshot(path=str(out/'live_components.png'))
        browser.close()
    checks['no_browser_errors']=not errors
    record={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'studio_url':url,
        'snapshot':snapshot['id'],'browser_errors':errors}
    write_json(out/'metadata.json',record)
    paths=sorted(p for p in out.iterdir() if p.is_file())
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in paths))
    print(out.relative_to(ROOT)); print(json.dumps(record))
    if record['status']!='passed': raise AssertionError('Live studio verification failed')


if __name__=='__main__': main()
