# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
from http.server import ThreadingHTTPServer
import json,threading
from pathlib import Path
from playwright.sync_api import sync_playwright
from core.architecture.result_registry import ROOT,verify_run
from core.architecture.board_sizing import board_table
from p05_studio.p00_app.server import Handler,Studio
OUT=ROOT/'p03_experiments/p93_optimized_scaling/p03_studio_checks'
class Quiet(Handler):
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Quiet);server.studio=Studio(OUT/'p01_browser_runs')
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}';checks=[];errors=[]
try:
 with sync_playwright() as tool:
  browser=tool.chromium.launch(channel='chrome',headless=True)
  page=browser.new_page(viewport={'width':1550,'height':1150},accept_downloads=True)
  page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url)
  page.wait_for_function('!state.loading')
  assert page.locator('#architecture-profile').input_value()=='current'
  for row in board_table()['boards']:
   b=row['board_size'];page.select_option('#board-size',str(b))
   page.wait_for_function('(b)=>state.componentData?.architecture?.board_size===b',arg=b)
   presets=page.locator('#iterations option').evaluate_all('xs=>xs.filter(x=>!x.hidden).map(x=>Number(x.value))')
   assert presets==list(row['iterations'].values()),(b,presets)
   assert page.locator('#run-one').is_enabled()
   preview=page.evaluate('state.componentData');arch=preview['architecture']
   assert arch['arrays'][0]['rows']==2*b*b+1
   assert preview['installed_memory']['node_sram_bytes']==row['node_sram_kib']*1024
   assert preview['installed_memory']['child_sram_bytes']==row['child_sram_kib']*1024
   if b!=9:assert page.locator('#model').input_value()=='random_diagnostic'
   checks.append({'board':b,'budgets':presets,'architecture':arch,'summary':page.locator('#hardware-summary').inner_text()})
  page.locator('#chip-panel').screenshot(path=str(OUT/'studio_19x19_architecture.png'))
  page.locator('#advanced > summary').click();page.locator('#start-paused').check()
  page.locator('#run-one').click();page.wait_for_function("state.status==='paused'",timeout=30000)
  job_id=page.evaluate('state.job');job=page.request.get(url+'/api/jobs/'+job_id).json()
  assert job['configuration']['hardware_profile']=='board_sized_s1_v1'
  assert job['snapshot']['memory']['node_sram_bytes']==3584*1024
  assert job['snapshot']['memory']['path_storage_entries']==723
  page.locator('#cancel').click();page.wait_for_function("state.status==='cancelled'",timeout=30000)
  page.locator('#new-game').click();page.select_option('#board-size','2')
  page.locator('#start-paused').uncheck();page.select_option('#iterations','50')
  page.locator('#animation-speed').fill('100');page.locator('#animation-speed').dispatch_event('input')
  page.locator('#run-one').click();page.wait_for_function("state.status==='awaiting_move'",timeout=30000)
  page.reload();page.wait_for_function("!state.loading && state.status==='awaiting_move'",timeout=30000)
  assert page.locator('#board-size').input_value()=='2'
  page.locator('#finish').click();page.wait_for_function("state.status==='complete'",timeout=30000)
  job_id=page.evaluate('state.job');job=server.studio.jobs[job_id];saved=verify_run(job.play.out)
  for selector,name in [('#export-json','result.json'),('#export-csv','summary.csv')]:
   with page.expect_download() as info:page.locator(selector).click()
   target=OUT/('browser_'+name);info.value.save_as(target)
   assert target.read_bytes()==(job.play.out/name).read_bytes()
  page.select_option('#board-size','13')
  page.wait_for_function('state.componentData?.architecture?.board_size===13')
  assert page.locator('#status').inner_text()=='Ready'
  assert page.locator('#export-json').get_attribute('href') is None
  assert not errors,errors
  (OUT/'browser_checks.json').write_text(json.dumps({'status':'passed','boards':checks,'page_errors':errors,'checks':['six current board previews and presets','19x19 live allocation','pause and cancel','completed current 2x2 move','reload','verified saved JSON and CSV exports','stale results cleared']},indent=2)+'\n')
  print('PASS: current optimized Studio board scaling and exports')
  browser.close()
finally:server.shutdown();server.server_close()
