# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Real Chrome on an isolated studio; all test sessions stay in this experiment.
# SPDX-License-Identifier: MIT
import csv
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import traceback

from playwright.sync_api import sync_playwright, expect

from core.architecture.result_registry import ROOT, new_run, verify_run, write_json
from p05_studio.p00_app.server import Handler, Studio


class QuietHandler(Handler):
    def log_message(self, *args): pass


def main():
    out=new_run(Path(__file__).parent/'p00_runs'); print(out,flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
    server.studio=Studio(out/'p01_results/p01_runs')
    threading.Thread(target=server.serve_forever,daemon=True).start()
    checks={}; errors=[]; failure=None; results={}
    def check(name, value):
        checks[name]=bool(value); print('PASS' if value else 'FAIL',name,flush=True)
        assert value,name
    try:
        with sync_playwright() as tool:
            browser=tool.chromium.launch(channel='chrome',headless=True)
            page=browser.new_page(viewport={'width':1500,'height':1100},accept_downloads=True)
            page.set_default_timeout(20000)
            wait=page.wait_for_function
            def diagnosed_wait(*args,**kwargs):
                try: return wait(*args,**kwargs)
                except Exception:
                    write_json(out/'client_at_failure.json',page.evaluate("()=>({state,message:document.getElementById('message').textContent})"))
                    page.screenshot(path=str(out/'failure.png'),full_page=True)
                    raise
            page.wait_for_function=diagnosed_wait
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_address[1]}')
            page.wait_for_function('!state.loading')
            page.locator('#advanced').evaluate('e=>e.open=true')
            page.select_option('#case','placement_2x2_medium_v1')
            check('legacy_saved_case_explicit', 'legacy full expansion' in page.locator('#case option:checked').inner_text())
            page.select_option('#iterations','50')
            page.wait_for_function("state.componentData?.components?.some(r=>r.children?.some(c=>c.id==='u_sel/incremental'))")
            check('legacy_to_custom_refreshes_preview','Single-child expansion' in page.locator('#fidelity-note').text_content())
            page.locator('#animation-speed').fill('100'); page.locator('#animation-speed').dispatch_event('input')
            page.locator('#start-paused').check()
            page.locator('#run-one').click()
            page.wait_for_function("state.status==='paused'")
            check('new_default_is_single_child',page.evaluate("state.snapshot.memory.policy==='evaluate_root_then_single_untried_child_v1'"))
            page.locator('#step').click()
            page.wait_for_function("state.snapshot.event.phase==='selection'")
            check('step_has_one_phase',page.evaluate('state.snapshot.completed===0&&state.snapshot.cycles===26'))
            page.locator('#pause').click()
            page.wait_for_function("state.status==='awaiting_move'",timeout=60000)
            first=server.studio.jobs[page.evaluate('state.job')]
            first_search=verify_run(first.play.out/'p01_searches'/first.play.moves[0]['search_run'])
            results['first_search']=first_search['metrics']
            check('one_move_actual_iterations',first.play.moves[0]['search_iterations']==50)
            check('one_child_per_iteration_bound',first_search['memory']['nodes_used']<=50)
            check('root_branches_are_real_boards',len(first.play.model.memory.nodes[0]['children'])==4)
            check('search_panel_correct_move','Move 1 / 4' in page.locator('#phase-description').inner_text())
            phases=first.pipeline.payload()['phases']
            commit=phases[-1]
            check('pipeline_four_cycle_commit',commit['phase']=='iteration_commit' and commit['end']-commit['start']==4)
            page.locator('#expand-components').click()
            text=page.locator('#component-rows').inner_text()
            check('remaining_action_state_is_listed','remaining' in text.lower() and 'bitmap' in text.lower())
            check('linked_child_storage_is_listed','Linked child records' in text)
            rows=page.locator('#component-rows tr[data-component]').evaluate_all("rs=>Object.fromEntries(rs.map(r=>[r.dataset.component,[...r.querySelectorAll('td')].map(c=>c.innerText)]))")
            check('changed_controller_costs_excluded',all(rows[k][2:4]==['Excluded','Excluded'] for k in ('u_sel/incremental','u_upd/incremental','top_level_glue/incremental')))
            page.locator('#tree-node').fill('999999999');page.locator('#tree-inspect').click()
            check('invalid_node_stats_clear',page.locator('#tree-node-stats').inner_text()=='')
            page.locator('#tree-root').click()
            page.locator('#tree-panel').screenshot(path=str(out/'tree.png'))
            page.locator('.components-panel').screenshot(path=str(out/'components.png'))
            page.reload();page.wait_for_function("state.status==='awaiting_move'")
            check('reload_keeps_new_policy',page.evaluate('singleChild()'))
            page.locator('#run').click()
            page.wait_for_function("state.status==='complete'",timeout=60000)
            session=verify_run(first.play.out);results['full_session']=session['metrics']
            check('four_moves_complete',session['metrics']['completed_moves']==4 and session['metrics']['completed_iterations']==200)
            check('session_phase_sum',sum(session['phase_cycles'].values())==session['metrics']['core_cycles'])
            for control,filename in (('export-json','result.json'),('export-csv','summary.csv')):
                expect(page.locator('#'+control)).to_have_attribute('aria-disabled','false')
                with page.expect_download() as event: page.locator('#'+control).click()
                data=Path(event.value.path()).read_bytes()
                check(filename+'_download_matches_saved_bytes',data==(first.play.out/filename).read_bytes())
                (out/('export_'+filename)).write_bytes(data)
            page.select_option('#iterations','200')
            check('config_change_clears_exports',page.locator('#export-json').get_attribute('aria-disabled')=='true')
            check('config_change_clears_latency',page.locator('#latency').inner_text()=='—')

            # Same first search after pause/step/reload must equal an uninterrupted search.
            page.locator('#new-game').click();page.locator('#advanced').evaluate('e=>e.open=true')
            page.select_option('#iterations','50');page.locator('#start-paused').uncheck()
            page.locator('#run-one').click();page.wait_for_function("state.status==='awaiting_move'",timeout=60000)
            repeated=server.studio.jobs[page.evaluate('state.job')]
            other=verify_run(repeated.play.out/'p01_searches'/repeated.play.moves[0]['search_run'])
            check('interrupted_and_uninterrupted_identical',other==first_search)
            page.locator('#finish').click();page.wait_for_function("state.status==='complete'")

            # A deliberately tiny allocation quota must commit completed work only.
            page.locator('#new-game').click();page.locator('#advanced').evaluate('e=>e.open=true')
            page.locator('#nodes').evaluate("e=>{for(let d=e.parentElement;d;d=d.parentElement)if(d.tagName==='DETAILS')d.open=true;}")
            page.locator('#nodes').fill('3');page.locator('#nodes').dispatch_event('change')
            page.locator('#run').click();page.wait_for_function("state.status==='memory_limited'",timeout=60000)
            limited=server.studio.jobs[page.evaluate('state.job')]
            saved=verify_run(limited.play.out); results['limited']=saved['metrics']
            check('limited_session_actual_completed',saved['metrics']['completed_iterations']==3 and len(saved['moves'])==1)
            check('limited_session_requested_and_actual',saved['moves'][0]['requested_iterations']==50 and saved['moves'][0]['search_iterations']==3)
            check('limited_session_reason_visible','Finished 3 of 50' in page.locator('#message').inner_text())
            check('limited_not_marked_complete','Memory limit reached'==page.locator('#status').inner_text())
            record=next(csv.DictReader((limited.play.out/'moves.csv').open()))
            check('limited_csv_actual_counts',(record['search_iterations'],record['requested_iterations'],record['search_status'])==('3','50','memory_limited'))
            page.reload();page.wait_for_function("state.status==='memory_limited'")
            check('limited_reason_survives_reload','Finished 3 of 50' in page.locator('#message').inner_text())
            page.screenshot(path=str(out/'memory_limited.png'),full_page=True)
            check('all_saved_sessions_preserved',len(list((out/'p01_results/p02_plays').glob('run_*')))==3)

            page.locator('#new-game').click();page.locator('#advanced').evaluate('e=>e.open=true')
            page.locator('#nodes').evaluate("e=>{for(let d=e.parentElement;d;d=d.parentElement)if(d.tagName==='DETAILS')d.open=true;}")
            page.locator('#nodes').fill('1');page.locator('#nodes').dispatch_event('change')
            page.locator('#run-one').click();page.wait_for_function("state.status==='failed'",timeout=60000)
            failed=server.studio.jobs[page.evaluate('state.job')]
            check('no_root_move_not_fabricated',not failed.play.moves and 'no move was placed' in page.locator('#message').inner_text())
            page.reload();page.wait_for_function("state.status==='failed'")
            check('failure_explanation_survives_reload','no move was placed' in page.locator('#message').inner_text())
            check('no_browser_errors',not errors)
            browser.close()
    except Exception:
        failure=traceback.format_exc();print(failure,flush=True)
        results['jobs_at_failure']={key:{'status':job.status,'error':job.error,'snapshot':job.snapshot} for key,job in server.studio.jobs.items()}
    finally:
        for job in server.studio.jobs.values():
            if job.status not in ('complete','memory_limited','failed','cancelled'): job.action('cancel')
        server.shutdown(); server.server_close()
        write_json(out/'metadata.json',{'status':'failed' if failure else 'passed','checks':checks,'errors':errors,'failure':failure,'results':results,
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                for root in ('p05_studio','core') for p in (ROOT/root).rglob('*') if p.is_file() and p.suffix in ('.py','.js','.css','.html')}})
        (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n'
            for p in sorted(out.rglob('*')) if p.is_file()))
    assert failure is None,failure


if __name__=='__main__': main()
