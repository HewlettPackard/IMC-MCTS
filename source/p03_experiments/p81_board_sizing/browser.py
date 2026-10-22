# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright,expect
from core.architecture.result_registry import ROOT,verify_run
from core.architecture.board_sizing import board_table
from p05_studio.p00_app.server import Handler,Studio
OUT=ROOT/json.loads((Path(__file__).parent/'latest.json').read_text())['run']
class Quiet(Handler):
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Quiet);server.studio=Studio(OUT/'p02_browser/p01_runs')
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}';checks=[];errors=[]
try:
 with sync_playwright() as tool:
  browser=tool.chromium.launch(channel='chrome',headless=True)
  page=browser.new_page(viewport={'width':1550,'height':1150},accept_downloads=True)
  page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url)
  page.wait_for_function('!state.loading')
  for row in board_table()['boards']:
   b=row['board_size'];page.select_option('#board-size',str(b))
   page.wait_for_function('(b)=>state.componentData?.installed_memory?.board_size===b',arg=b)
   presets=page.locator('#iterations option').evaluate_all('xs=>xs.map(x=>Number(x.value))')
   assert presets==list(row['iterations'].values()),(b,presets)
   assert page.locator('#run-one').is_enabled()
   actual=page.locator('#hardware-summary').inner_text()
   assert f"{row['cam_entries']:,}" in actual
   preview=page.evaluate('state.componentData')
   assert preview['installed_memory']['node_sram_bytes']==row['node_sram_kib']*1024
   assert preview['installed_memory']['child_sram_bytes']==row['child_sram_kib']*1024
   if b!=9:assert page.locator('#model').input_value()=='random_diagnostic'
   checks.append({'board':b,'budgets':presets,'summary':actual})
  # Inspect a large live allocation and save a completed one-move session.
  page.locator('#advanced > summary').click()
  page.locator('#start-paused').check()
  page.locator('#animation-speed').fill('100');page.locator('#animation-speed').dispatch_event('input')
  page.locator('#run-one').click();page.wait_for_function("state.status==='paused'",timeout=30000)
  job_id=page.evaluate('state.job');job=page.request.get(url+'/api/jobs/'+job_id).json()
  assert job['configuration']['hardware_profile']=='board_sized_s1_v1'
  assert job['snapshot']['memory']['node_sram_bytes']==3584*1024
  assert job['snapshot']['memory']['path_storage_entries']==723
  page.screenshot(path=str(OUT/'studio_19x19_paused.png'))
  page.locator('#cancel').click();page.wait_for_function("state.status==='cancelled'",timeout=30000)
  page.locator('#new-game').click();page.select_option('#board-size','2')
  page.locator('#start-paused').uncheck();page.select_option('#iterations','50')
  page.locator('#run-one').click();page.wait_for_function("state.status==='awaiting_move'",timeout=30000)
  page.reload();page.wait_for_function("!state.loading && state.status==='awaiting_move'",timeout=30000)
  assert page.locator('#board-size').input_value()=='2'
  assert '192 KiB' in page.locator('#hardware-summary').inner_text()
  page.locator('#finish').click();page.wait_for_function("state.status==='complete'",timeout=30000)
  job_id=page.evaluate('state.job');job=server.studio.jobs[job_id];saved=verify_run(job.play.out)
  requested=json.loads((job.play.out/'requested.json').read_text())
  assert requested['hardware_profile']=='board_sized_s1_v1'
  pool=saved['costs']['sram']['pools'];assert pool['node_sram']['capacity_bytes']==192*1024
  assert pool['child_sram']['capacity_bytes']==64*1024
  for selector,name in [('#export-json','result.json'),('#export-csv','summary.csv')]:
   with page.expect_download() as info:page.locator(selector).click()
   target=OUT/('browser_'+name);info.value.save_as(target)
   assert target.read_bytes()==(job.play.out/name).read_bytes()
  page.select_option('#board-size','13')
  page.wait_for_function('state.componentData?.installed_memory?.board_size===13')
  assert page.locator('#status').inner_text()=='Ready'
  assert page.locator('#latency').inner_text()=='—'
  assert page.locator('#export-json').get_attribute('href') is None
  page.screenshot(path=str(OUT/'studio_13x13_ready.png'))
  # Restoring a saved reference case must keep its fixed-memory identity.
  page.locator('#advanced > summary').click()
  page.select_option('#case','placement_2x2_medium_v1')
  page.wait_for_function('state.hardwareProfile===null')
  assert '1,536 KiB' in page.locator('#hardware-summary').inner_text()
  page.select_option('#iterations','400')
  page.wait_for_function("state.componentData?.installed_memory?.hardware_profile==='board_sized_s1_v1'")
  assert '192 KiB' in page.locator('#hardware-summary').inner_text()
  assert not errors,errors
  (OUT/'browser_checks.json').write_text(json.dumps({'status':'passed','boards':checks,'page_errors':errors,
    'checks':['six board previews','presets from server','large live allocation','pause/cancel','reload restored hardware','saved session and downloaded JSON/CSV','stale results cleared','legacy case restored then converted explicitly by edit']},indent=2)+'\n')
  print('PASS: board changes, large live allocation, reload, saved exports and reference case isolation')
  browser.close()
finally:server.shutdown();server.server_close()
