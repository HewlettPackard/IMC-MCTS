# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Isolated Chrome verifies new proxy labels, grouped rows and downloadable evidence.
# SPDX-License-Identifier: MIT
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import traceback

from playwright.sync_api import sync_playwright

from core.architecture.result_registry import ROOT, new_run, verify_run, write_json
from p05_studio.p00_app.server import Handler, Studio, Job
from p03_experiments.p62_component_costs.cost_oracle import Sources, compare, flatten, check


class QuietHandler(Handler):
    def log_message(self,*args): pass


def main():
    experiment=Path(__file__).parent; out=new_run(experiment/'p00_runs'); print(out,flush=True)
    record=json.loads((ROOT/json.loads((experiment/'latest.json').read_text())['costs']/'metadata.json').read_text())
    server=ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
    server.studio=Studio(out/'p01_results/p01_runs')
    threading.Thread(target=server.serve_forever,daemon=True).start()
    checks=[]; errors=[]; failure=None
    def passed(name): checks.append(name); print('PASS',name,flush=True)
    try:
        with sync_playwright() as tool:
            browser=tool.chromium.launch(channel='chrome',headless=True)
            page=browser.new_page(viewport={'width':1500,'height':1100},accept_downloads=True)
            page.set_default_timeout(20000); page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_address[1]}'); page.wait_for_function('!state.loading')
            for case in record['cases']:
                folder=ROOT/case['run']; result=verify_run(folder); oracle,_=compare(result,Sources())
                config=result['identity']['configuration']['requested']
                server.studio.runs=folder.parent
                job=Job(config,result['case_id'],False,folder.parent)
                job.status,job.run,job.result,job.sequence='complete',folder.name,result,1
                server.studio.jobs={job.id:job}
                page.evaluate('job=>{document.getElementById("execution").value="search";applyConfiguration(job.configuration);attachJob(job);}',job.payload())
                page.evaluate('r=>{state.chartTiming={cycles:r.metrics.core_cycles,phases:r.phase_cycles};renderComponents(r.component_estimates,r.costs);}',result)
                if page.locator('#expand-components').inner_text()!='Collapse all parts': page.locator('#expand-components').click()
                rows=page.locator('#component-rows tr[data-component]').evaluate_all('rs=>Object.fromEntries(rs.map(r=>[r.dataset.component,[...r.querySelectorAll("td")].map(c=>c.innerText)]))')
                assert set(rows)=={part['id'] for part,owner in flatten(result['costs']['ledger']['components'])}
                for owner in ('u_sel','u_upd','u_nn','top_level_glue'):
                    assert 'Controller report proxy + 25%' in rows[owner][5]
                    assert abs(float(rows[owner][2].replace(',',''))-oracle[owner]['area_um2'])<.000501
                    assert abs(float(rows[owner][3].replace(',',''))-oracle[owner]['average_power_mw'])<.000000501
                    page.locator(f'tr[data-component="{owner}"] details').evaluate('e=>e.open=true')
                    assert 'not matching synthesis' in page.locator(f'tr[data-component="{owner}"] details').inner_text()
                assert '4 controller estimates use report proxies' in page.locator('#component-summary').inner_text()
                passed(case['label']+': all parts, proxy disclosures and displayed values')
                for metric,field,divisor in [('area','area_um2',1e6),('energy','energy_uj',1),('power','average_power_mw',1)]:
                    check(float(page.locator('#pie-'+metric).get_attribute('data-total')),sum(row[field] or 0 for row in oracle.values())/divisor,'pie total')
                    assert page.locator('#pie-'+metric).get_attribute('data-missing')=='0'
                passed(case['label']+': charts include estimates and show zero missing core groups')
                for control,name in [('export-json','result.json'),('export-csv','summary.csv'),('export-components','components.csv')]:
                    with page.expect_download() as event: page.locator('#'+control).click()
                    assert event.value.failure() is None
                    assert Path(event.value.path()).read_bytes()==(folder/name).read_bytes()
                passed(case['label']+': JSON and CSV downloads match saved bytes')
                if case==record['cases'][0]:
                    page.locator('.components-panel').screenshot(path=str(out/'components.png'))
            # A real new 500-iteration run tests the normal live-to-final path.
            server.studio=Studio(out/'p01_results/p01_runs')
            page.evaluate('localStorage.clear()'); page.reload(); page.wait_for_function('!state.loading')
            page.select_option('#board-size','9'); page.select_option('#model','go_strong_v1'); page.select_option('#iterations','500')
            page.locator('#animation-speed').fill('100'); page.locator('#animation-speed').dispatch_event('input')
            page.locator('#run-one').click(); page.wait_for_function("state.status==='awaiting_move'",timeout=180000)
            actual=server.studio.jobs[page.evaluate('state.job')]
            result=verify_run(actual.play.out/'p01_searches'/actual.play.moves[0]['search_run'])
            compare(result,Sources()); assert result['costs']['ledger']['missing_energy']==[]
            assert '4 controller costs use older report proxies' in page.locator('#cost-coverage').inner_text()
            passed('Fresh one-move Go-strong run: modeled core costs and live/final coverage')
            page.locator('#finish').click();page.wait_for_function("state.status==='complete'")
            page.select_option('#iterations','5000')
            assert page.locator('#export-json').get_attribute('aria-disabled')=='true'
            assert page.locator('#pie-energy').get_attribute('data-total') in (None,'')
            passed('Configuration change clears workload estimates and exports')
            assert not errors; passed('No browser errors'); browser.close()
    except Exception:
        failure=traceback.format_exc();print(failure,flush=True)
    finally:
        for job in server.studio.jobs.values():
            if job.status not in ('complete','memory_limited','failed','cancelled'):job.action('cancel')
        server.shutdown();server.server_close()
        write_json(out/'metadata.json',{'status':'failed' if failure else 'passed','checks':checks,'errors':errors,'failure':failure})
        (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n' for p in sorted(out.rglob('*')) if p.is_file()))
    assert failure is None,failure


if __name__=='__main__': main()
