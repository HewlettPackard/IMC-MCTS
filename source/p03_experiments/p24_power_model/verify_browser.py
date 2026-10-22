# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Verify the unified cost ledger through live browser controls and saved exports.
# SPDX-License-Identifier: MIT
import csv
import hashlib
from http.server import ThreadingHTTPServer
import io
import json
import math
from pathlib import Path
import sys
import threading
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright, expect
from core.architecture.result_registry import new_run, write_json, verify_run
from p05_studio.p00_app.server import Handler, Studio


def main():
    out=new_run(Path(__file__).parent/'p00_runs'); print(out.relative_to(ROOT),flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.studio=Studio(out/'p01_result_store/p00_runs')
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_address[1]}'; checks={}; errors=[]
    def fetch(path):
        with urlopen(url+path,timeout=20) as response: return json.load(response)
    try:
        driven=fetch('/api/components?board=9'); buffered=fetch('/api/components?board=9&readout=column_hold_v1')
        small=fetch('/api/components?board=3')
        checks['http_9x9_six_modules']=driven['digital']['priced_instances']==6
        checks['http_3x3_parameter_gaps']=small['digital']['priced_instances']==3
        checks['http_buffered_parent_difference']=abs(buffered['known_area_mm2']-driven['known_area_mm2']-461.760014*(22/65)**2/1e6)<1e-12
        with sync_playwright() as tool:
            browser=tool.chromium.launch(channel='chrome',headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1100})
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(url)
            expect(page.locator('#component-summary')).to_contain_text('6 digital parent instances priced')
            expect(page.locator('#component-rows')).to_contain_text('vectorless dynamic')
            expect(page.locator('#component-rows')).not_to_contain_text('Missing module report')
            expect(page.locator('#digital-timing-note')).to_contain_text('22 nm clock closure is unvalidated')
            expect(page.locator('#component-rows')).not_to_contain_text('Setup timing FAILED')
            expect(page.locator('#component-rows')).to_contain_text('u_choice')
            checks['v2_area_and_timing_limits_visible']=True
            checks['module_coverage_visible']=True
            page.locator('#readout-profile').select_option('column_hold_v1')
            expect(page.locator('#component-rows')).to_contain_text('u_column_hold')
            expect(page.locator('#readout-summary')).to_contain_text('512 column samples installed')
            checks['buffer_control_in_parent_not_added_twice']=True
            page.locator('#model').select_option('archive_9x9_h96_centered_v1')
            page.locator('#game-rules').select_option('legacy_go')
            page.locator('#execution').select_option('search'); page.locator('#iterations').fill('8')
            page.locator('#start-paused').check(); page.locator('#run').click()
            expect(page.locator('#status')).to_have_text('Paused',timeout=20000)
            page.locator('#step').click()
            expect(page.locator('#cycles')).not_to_have_text('0 controller cycles')
            session=fetch('/api/session')['job']; live=fetch('/api/jobs/'+session['id'])
            checks['live_costs_match_installed_ledger']=live['live_costs']['digital']['known_area_mm2']==buffered['digital']['known_area_mm2']
            checks['live_power_stays_unpriced']=live['live_costs']['digital']['power_mw'] is None
            page.reload(); expect(page.locator('#status')).to_have_text('Paused')
            expect(page.locator('#component-summary')).to_contain_text('6 digital parent instances priced')
            checks['reload_preserves_module_costs']=True
            page.locator('#pause').click(); expect(page.locator('#status')).to_have_text('Complete',timeout=30000)
            href=page.locator('#export-json').get_attribute('href')
            result=page.request.get(url+href).json()
            saved=out/'p01_result_store/p00_runs'/href.split('/')[-2]
            checks['export_matches_saved_run']=verify_run(saved)==result
            baseline=ROOT/'p03_experiments/p21_tree_update_costs/p00_runs/run_20260910_004229Z/p01_result_store/p00_runs/run_20260910_004231Z'
            old=verify_run(baseline)
            before=old['identity']['configuration']['requested']; after=result['identity']['configuration']['requested']
            checks['same_trained_go_configuration']=all(after[k]==v for k,v in before.items() if k!='profile')
            checks['go_state_and_traffic_preserved']=all(result[k]==old[k] for k in ('tree_sha256','node_sram_sha256','child_sram_sha256','last_value_q17','random_state')) and result['memory']['operations']==old['memory']['operations']
            with (baseline/'iterations.csv').open() as stream: previous=list(csv.DictReader(stream))
            with (saved/'iterations.csv').open() as stream: current=list(csv.DictReader(stream))
            nodes=1; delta=0
            assert len(previous)==len(current)==8
            for a,b in zip(previous,current):
                delta+=35 if int(b['nodes'])>nodes else 0; nodes=int(b['nodes'])
                assert all(a[k]==b[k] for k in a if k!='cycle_end') and int(b['cycle_end'])-int(a['cycle_end'])==delta
            checks['go_exact_v2_cycle_delta']=result['metrics']['core_cycles']-old['metrics']['core_cycles']==delta
            checks['trained_go_integration']=result['identity']['configuration']['requested']['model_id']=='archive_9x9_h96_centered_v1'
            checks['live_timing_limits']=live['live_costs']['digital']['timing_violations']==[]
            checks['v2_controller_profile']=result['identity']['configuration']['requested']['profile']=='legacy_go_host_rules_q32_column_hold_v2'
            checks['complete_and_live_area_match']=result['costs']['digital']['known_area_mm2']==live['live_costs']['digital']['known_area_mm2']
            csv_data=page.request.get(url+page.locator('#export-csv').get_attribute('href')).body()
            (out/'download.csv').write_bytes(csv_data)
            row=next(csv.DictReader(io.StringIO(csv_data.decode())))
            checks['csv_area_matches_json']=float(row['digital_area_22nm_estimate_mm2'])==result['costs']['digital']['known_area_mm2']
            checks['csv_native_timing']=row['digital_65nm_setup_violating_paths']=='0' and row['digital_65nm_timing_failed_modules']=='' and row['digital_65nm_timing_status']=='no_reported_failure_in_priced_modules'
            checks['whole_chip_not_fabricated']=row['whole_chip_energy_uj']=='' and result['metrics']['power_mw'] is None
            ledger=result['costs']['ledger']
            expect(page.locator('#cost-coverage')).to_contain_text('imc_22nm_costs_v1')
            expect(page.locator('#cost-coverage')).to_contain_text('currently SRAM only')
            page.locator('#energy-coverage summary').click()
            expect(page.locator('#energy-rows')).to_contain_text('65 nm vectorless report retained')
            checks['ledger_and_missing_energy_visible']=True
            checks['ledger_csv_identity']=row['cost_model_sha256']==ledger['sha256'] and row['cost_model_profile']==ledger['profile']
            checks['ledger_csv_energy']=float(row['known_energy_uj'])==ledger['known_energy_uj']
            checks['live_ledger_profile']=live['live_costs']['ledger']['profile']==ledger['profile']
            checks['live_ledger_energy']=math.isclose(live['live_costs']['ledger']['known_energy_uj'],live['live_costs']['sram']['energy_uj'],abs_tol=1e-12)

            page.locator('.results').screenshot(path=str(out/'desktop_timing.png'))
            page.locator('.components-panel').screenshot(path=str(out/'desktop_modules.png'))
            page.set_viewport_size({'width':390,'height':844})
            page.locator('#digital-timing-note').scroll_into_view_if_needed()
            page.screenshot(path=str(out/'mobile_modules.png'))
            checks['mobile_no_page_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            checks['no_browser_errors']=not errors
            browser.close()
        assert all(checks.values()),checks
        write_json(out/'metadata.json',{'status':'passed','checks':checks,'browser_errors':errors,
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in ['p05_studio/p00_app','p05_studio/p01_static'] for p in (ROOT/folder).iterdir() if p.is_file()}})
        (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n'
            for p in sorted(out.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
        print('Passed',len(checks),'browser/HTTP checks',flush=True)
    except Exception as error:
        write_json(out/'metadata.json',{'status':'failed','checks':checks,'browser_errors':errors,'error':str(error)})
        raise
    finally: server.shutdown(); server.server_close()


if __name__=='__main__': main()
