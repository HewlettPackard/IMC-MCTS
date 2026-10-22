/* SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP */
/* The UI observes the backend; it never calculates replacement simulator results. */
/* SPDX-License-Identifier: MIT */
const $ = id => document.getElementById(id);
const names = {selection:'Selection', expansion:'Expansion', neural:'Rollout', backpropagation:'Backprop', iteration_commit:'FSM finish',move_commit:'Place chosen move'};
const state = {catalog:[], models:[], job:null, jobError:'', status:'ready', snapshot:null, seq:0, inputBoard:[], boardTab:'played', inspected:'selection', programJob:null,execution:'play',boardKey:null,loading:true,componentData:null,componentCosts:null,componentExpanded:new Set(),componentCollapsedGroups:new Set()};
state.componentParameters={};state.parameterCatalog=null;
const studioClient=localStorage.getItem('imc-studio-client') || crypto.randomUUID().replaceAll('-','');
localStorage.setItem('imc-studio-client',studioClient);
const active = () => ['queued','running','paused','cancelling','awaiting_move','awaiting_human'].includes(state.status);
const latestHardware=()=>state.architectureMode==='current';
const singleChild = () => {if(latestHardware())return true;const profile=state.snapshot?.memory?.execution_profile || state.catalog.find(item=>item.id===$('case').value)?.configuration.profile;return !profile || profile.startsWith('single_child_');};
const memoryNotice = limit => limit ? `Memory limit reached (${limit.resource}). Finished ${num(limit.completed_iterations)} of ${num(limit.requested_iterations)} requested iterations. The saved result contains completed work only.` : '';
function savedProfileLabel(profile,costProfile) {
  if(profile!==state.architecture?.profile)return 'Historical';
  return costProfile===state.architecture?.cost_model_profile?'Current':'Current architecture · historical costs'+(costProfile?' ('+costProfile+')':'');
}
const num = (n, digits=0) => Number(n).toLocaleString('en-US',{maximumFractionDigits:digits});
const iterationPresets={};
state.hardwareTable=[];state.hardwareProfile=null;state.architectureMode='current';state.architecture=null;
const sizedHardware=()=>state.hardwareProfile==='board_sized_s1_v1';
function renderHardware(memory) {
  const row=state.hardwareTable.find(item=>item.board_size===Number($('board-size').value));
  if(!row)return;
  const node=memory?.node_sram_bytes ?? (sizedHardware()?row.node_sram_kib*1024:1536*1024);
  const child=memory?.child_sram_bytes ?? (sizedHardware()?row.child_sram_kib*1024:512*1024);
  const cam=memory?.cam_entries ?? (sizedHardware()?row.cam_entries:1024);
  const bank=memory?.sram_bank_bytes ?? (sizedHardware()?row.sram_bank_kib*1024:512*1024);
  $('hardware-summary').textContent=`${num(cam)} CAM entries · ${num(node/1024)} KiB node + ${num(child/1024)} KiB child SRAM`;
  $('node-detail').textContent=`${num(node/bank)} × ${num(bank/1024)} KiB${memory?.node_stride?` · ${memory.node_stride} bytes per node`:''}`;
  $('child-detail').textContent=`${num(child/bank)} × ${num(bank/1024)} KiB · child links`;
  for(const [pool,count] of [['node',node/bank],['child',child/bank]]) {
    const banks=$(pool+'-banks');banks.replaceChildren();
    for(let i=0;i<count;i++)banks.append(document.createElement('i'));
  }
}
const configInputs = ['architecture-profile','case','board-size','iterations','seed','exploration','memory-profile','nodes','edges','path','start-paused','execution','game-rules','model','readout-profile','opponent','architecture-side','opponent-model','opponent-iterations','opponent-seed'];

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {headers:{'X-Studio-Client':studioClient}} : {method:'POST',headers:{'Content-Type':'application/json','X-Studio-Client':studioClient},body:JSON.stringify(body)});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || `Request failed (${response.status})`);
  return value;
}
function message(text) {
  const value=[...new Set([state.jobError,text].filter(Boolean))].join(' ');
  $('message').textContent=value; $('message').hidden=!value;
}
function resetBoard() { const size=Number($('board-size').value); state.inputBoard=Array.from({length:size},()=>Array(size).fill(0)); renderBoard(); }
function custom() {
  if(active()) return;
  const policyChanged=!singleChild()||!sizedHardware();
  state.hardwareProfile='board_sized_s1_v1';
  if(state.job) resetRunView();
  $('case').value='';state.chartTiming=null;
  if(state.componentData) renderComponents(state.componentData);
  else renderBreakdown(null,null);
  renderHardware();
  if(policyChanged) { renderIterationOptions(Number($('iterations').value)); modelNote(); refreshComponents(); }
}
function renderIterationOptions(selected) {
  const select=$('iterations'),tier=select.selectedOptions[0]?.dataset.tier || 'low';
  const values=iterationPresets[Number($('board-size').value)],tiers=['low','medium','high'];
  select.replaceChildren();
  if(!values)return;
  values.forEach((count,index)=>{const option=document.createElement('option');option.value=count;option.dataset.tier=tiers[index];option.textContent=`${num(count)} (${tiers[index]})`;select.append(option);});
  if(selected!=null&&!values.includes(Number(selected))) {
    const saved=document.createElement('option');saved.value=selected;saved.textContent=`${num(selected)} (saved)`;saved.hidden=true;select.append(saved);
  }
  select.value=selected ?? values[tiers.indexOf(tier)];
}
function modeControls() {
  const play=$('execution').value==='play', go=$('game-rules').value==='legacy_go';
  $('iterations-label').textContent=play?'Iterations / move':'Search iterations';
  $('run-label').textContent=play?'Until game ends':'Run search';
  $('run-one').hidden=!play;
  $('mode-note').textContent=go?'Legacy Go includes captures, suicide prevention, simple ko, passing and Chinese area scoring (6.5 komi). Rule processing is outside modeled core time.':play?'Each move gets the search budget below. The chosen piece is placed, and play continues until full.':'Explore candidate positions for one move. Search iterations do not permanently add pieces to the board.';
  if(!state.job) { state.execution=play?'play':'search'; selectBoardTab(play?'played':'live'); }
  opponentControls();
}
function applyCase(id) {
  const item=state.catalog.find(item=>item.id===id); if(!item) return;
  if(active()) return;
  if(state.job) resetRunView();
  applyConfiguration(item.configuration);
  refreshComponents();
}
function applyConfiguration(config) {
  state.componentParameters=structuredClone(config.component_parameters || {});
  state.architectureMode=config.profile===state.architecture?.profile?'current':'historical';
  $('architecture-profile').value=state.architectureMode;
  state.executionProfile=config.profile || null;
  state.hardwareProfile=config.hardware_profile || null;
  $('board-size').value=config.board_size; renderIterationOptions(config.iterations); $('seed').value=config.seed ?? 0;
  $('exploration').value=config.exploration ?? 1.414; $('memory-profile').value=config.memory_profile?.endsWith('_hp')?'cacti_22nm_hp':'cacti_22nm_lstp';
  for(const [id,key] of [['nodes','nodes'],['edges','edges'],['path','path_entries']]) $(id).value=config.memory_limits?.[key] ?? '';
  $('game-rules').value=config.rules || 'placement';
  $('readout-profile').value=config.readout_profile || 'sustained_drive_v1';
  renderModelOptions(config.model_id || 'random_diagnostic'); modeControls();
  resetBoard();
  if(config.initial_board) state.inputBoard=config.initial_board.map(row=>row.slice());
  renderBoard(); renderHardware(); renderParameterEditor();
}
function readConfiguration() {
  for(const id of configInputs) if(!$(id).reportValidity()) return null;
  if(latestHardware())for(const input of document.querySelectorAll('#parameter-fields input'))if(!input.reportValidity())return null;
  const limits={};
  for(const [id,key] of [['nodes','nodes'],['edges','edges'],['path','path_entries']]) if($(id).value!=='') limits[key]=Number($(id).value);
  const config={board_size:Number($('board-size').value),iterations:Number($('iterations').value),seed:Number($('seed').value),
    exploration:Number($('exploration').value),memory_profile:$('memory-profile').value,memory_limits:limits,
    initial_board:state.inputBoard.map(row=>row.slice())};
  if(latestHardware()) {config.profile=state.architecture.profile;config.hardware_profile='board_sized_s1_v1';}
  else if(sizedHardware())config.hardware_profile=state.hardwareProfile;
  else if(state.executionProfile)config.profile=state.executionProfile;
  if(latestHardware()&&Object.keys(state.componentParameters).length)config.component_parameters=structuredClone(state.componentParameters);
  config.model_id=$('model').value;
  if($('game-rules').value==='legacy_go') config.rules='legacy_go';
  if($('readout-profile').value==='column_hold_v1') config.readout_profile='column_hold_v1';
  return config;
}
function controls() {
  const waiting=['awaiting_move','awaiting_human'].includes(state.status);
  $('run').disabled=state.loading||!$('model').value||active()&&!waiting; $('run-one').disabled=state.loading||!$('model').value||active()&&!waiting;
  for(const id of configInputs) $(id).disabled=state.loading||active();
  for(const input of document.querySelectorAll('#parameter-fields input,#parameter-reset'))input.disabled=state.loading||active();
  $('pause').disabled=!['running','paused','awaiting_human'].includes(state.status);
  $('pause').textContent=state.status==='paused' ? 'Resume' : 'Pause';
  $('step').disabled=!['running','paused'].includes(state.status);
  $('cancel').disabled=!active() || state.status==='cancelling';
  $('status').className='status '+state.status;
  $('status').textContent=({memory_limited:'Memory limit reached',awaiting_move:'Choose the next move',awaiting_human:'Your turn · '+(state.snapshot?.play?.player_to_move===1?'Black':'White')})[state.status] || state.status[0].toUpperCase()+state.status.slice(1);
  $('finish').hidden=!waiting;
  $('pass-move').hidden=state.status!=='awaiting_human'||$('game-rules').value!=='legacy_go';
  if(latestHardware()) for(const id of ['game-rules','readout-profile','memory-profile','case']) $(id).disabled=true;
  $('architecture-summary').textContent=latestHardware()?'16 UCB · 32 ADC · two arrays · board-sized memories':'Historical hardware, kept under its original profile.';
  opponentControls();
}
async function runSearch(until='end') {
  if(['awaiting_move','awaiting_human'].includes(state.status))return act(until==='one'?'one':'until_end');
  const previousStatus=state.status;
  try {
    message(''); const config=readConfiguration(); if(!config) return;
    const body={mode:$('start-paused').checked ? 'paused' : 'live',execution:$('execution').value,
      studio_options:{speed:Number($('animation-speed').value),play_until:until,opponent:$('opponent').value,architecture_side:$('architecture-side').value,
        opponent_config:$('opponent').value==='engine'?{iterations:Number($('opponent-iterations').value),seed:Number($('opponent-seed').value),model_id:$('opponent-model').value}:{}}};
    if($('case').value) body.case_id=$('case').value; else body.configuration=config;
    state.status='queued'; controls();
    const job=await api('/api/jobs',body);
    attachJob(job);
  } catch(error) { state.status=previousStatus; controls(); message(error.message); }
}
function attachJob(job) {
  resetRunView();
  state.job=job.id; state.jobError=job.error || memoryNotice(job.result?.termination || job.snapshot?.termination); state.status=job.status; state.snapshot=job.snapshot||null;
  state.execution=job.execution || 'search'; state.boardKey=null;
  message('');
  $('animation-speed').value=job.speed??85; speedLabel();
  if(job.studio_options){$('opponent').value=job.studio_options.opponent;$('architecture-side').value=job.studio_options.architecture_side || 'black';opponentControls();
    const other=job.studio_options.opponent_config||{};$('opponent-iterations').value=other.iterations??100;$('opponent-seed').value=other.seed??1;
    $('opponent-model').value=other.model_id||$('model').value;
    if(!$('opponent-model').value) renderOpponentModels();}
  selectBoardTab(state.execution==='play'?'played':'live');
  $('results-title').textContent=state.execution==='play'?'Session results and evidence':'Search results and evidence';
  $('results-description').textContent=state.execution==='play'?'Sum of per-move core searches on one reused chip. Display pauses and host move commits are excluded.':'This search explores one fixed starting position. Its result is one decision budget.';
  $('export-moves').hidden=state.execution!=='play';
  $('run-name').textContent=job.run || 'Preparing a fresh run'; $('identity').textContent=job.case_id;
  $('arrays').textContent='Loading this model’s programmed cells…';
  if(job.snapshot?.event||job.snapshot?.play){renderSnapshot(job.snapshot,job.live_costs);StudioViews.update(job.tree,job.snapshot);state.seq=job.sequence;}
  PipelineView.update(job.pipeline,job.snapshot,job.status);
  modelNote(); controls(); poll(job.id);
}
async function act(action,value) {
  const id=state.job;
  if(!id) return;
  try {
    const job=await api(`/api/jobs/${id}/actions`,value===undefined?{action}:{action,value});
    if(state.job!==id) return;
    if(job.error) state.jobError=job.error;
    message('');
  } catch(error) { if(state.job===id) message(error.message); }
}
async function poll(id) {
  if(state.job!==id) return;
  try {
    const job=await api(`/api/jobs/${id}?after=${state.seq}${StudioViews.query()}${PipelineView.query()}`);
    if(state.job!==id) return;
    const changed=state.seq!==job.sequence||state.status!==job.status;
    state.status=job.status; state.seq=job.sequence; state.snapshot=job.snapshot;
    state.jobError=job.error || memoryNotice(job.result?.termination || job.snapshot?.termination);
    controls();
    if(changed&&(job.snapshot?.event||job.snapshot?.play)) renderSnapshot(job.snapshot,job.live_costs);
    StudioViews.update(job.tree,job.snapshot);
    PipelineView.update(job.pipeline,job.snapshot,job.status);
    if(state.jobError) message('');
    if(state.programJob!==id+job.snapshot?.program_key && job.snapshot?.program_key) {
      $('arrays').textContent='Loading this model’s programmed cells…';
      const program=await api(`/api/jobs/${id}/program?key=${encodeURIComponent(job.snapshot.program_key)}`);
      if(state.job!==id)return;
      if(program?.key===job.snapshot.program_key) { renderProgram(program); renderComponents(program.component_estimates,job.live_costs); state.programJob=id+program.key; }
    }
    if(job.result) {
      renderMetrics(job.result.metrics.core_cycles,job.result.costs);
      renderComponents(job.result.component_estimates,job.result.costs);
      $('run-name').textContent=job.run;
      $('identity').textContent=`Execution ${job.result.execution_sha256}`;
      for(const [id,file] of [['export-json','result.json'],['export-csv','summary.csv'],['export-power','block_power.csv'],['export-components','components.csv'],['export-source','source_snapshot.tar.gz'],['export-moves','moves.csv']]) {
        if(id==='export-power' && !job.result?.costs?.block_power) continue;
        if(id==='export-components' && !job.result?.costs?.ledger?.peripheral_model) continue;
        if(id==='export-moves' && state.execution!=='play') continue;
        $(id).href=`${job.export_base || '/api/runs/'+job.run}/${file}?download=1`; $(id).classList.remove('disabled'); $(id).setAttribute('aria-disabled','false');
      }
      await refreshRuns();
    }
    if(active()) setTimeout(()=>poll(id),70);
  } catch(error) { if(state.job!==id) return; message(error.message); if(active()) setTimeout(()=>poll(id),700); }
}
function selectBoardTab(tab) {
  state.boardTab=tab;
  for(const name of ['played','live','input']) $(name+'-tab').classList.toggle('active',name===tab);
  renderBoard();
}
function searchMove(s,run=null) {
  if(!s?.play) return null;
  const moves=s.play.moves || [];
  if(run!==null) return moves.find(move=>move.search_run===run)?.move ?? s.play.current_move;
  return s.event?.phase==='move_commit'
    ? [...moves].reverse().find(move=>move.search_run)?.move ?? null : s.play.current_move;
}
function renderBoard() {
  const live=state.snapshot?.board, play=state.snapshot?.play;
  $('played-tab').hidden=state.execution!=='play'; $('placements').hidden=state.execution!=='play';
  const board=state.boardTab==='input' ? state.inputBoard : state.boardTab==='played' && play ? play.board : live || state.inputBoard;
  const last=state.boardTab==='played'?play?.moves.at(-1):null;
  const human=state.boardTab==='played'&&state.status==='awaiting_human';
  const editable=state.boardTab==='input' && !active() || human;
  const container=$('board'), key=JSON.stringify([board,state.boardTab,editable,last?.move]);
  if(key!==state.boardKey) {
    state.boardKey=key; container.replaceChildren(); container.style.setProperty('--board-size',board.length);
    container.classList.toggle('editable',editable);
    for(let row=0;row<board.length;row++) for(let col=0;col<board.length;col++) {
    const value=board[row][col], cell=document.createElement('button');
    cell.className='cell'+(value===1?' black':value===-1?' white':'');
    if(last && row===last.row && col===last.column) cell.classList.add('last-move');
    cell.title=`Row ${row+1}, column ${col+1}: ${value===1?'black':value===-1?'white':'empty'}`;
    cell.setAttribute('aria-label',cell.title); cell.setAttribute('aria-disabled',String(!editable));
    if(!editable) cell.tabIndex=-1;
    cell.onclick=()=>{ if(!editable) return;if(human){act('human_move',[row,col]);return;} state.inputBoard[row][col]=value===0?1:value===1?-1:0; custom(); renderBoard(); };
    container.append(cell);
    }
  }
  const occupied=board.flat().filter(value=>value!==0).length;
  $('board-caption').textContent=state.boardTab==='input'
    ? (editable?'Click a cell to cycle empty, black and white. This creates a custom case.':'Initial board for this job. Configuration is locked while it runs.')
    : state.boardTab==='played' && play
      ? play.rules==='legacy_go' ? `${play.terminal?'Game finished':'Go in progress'} · ${occupied} stones · captures B ${play.captures['1']}, W ${play.captures['-1']} · area B ${num(play.score[0],1)}, W ${num(play.score[1],1)} (with komi)` : play.completed_moves===play.total_moves ? `Board full · ${occupied} pieces placed` : `${occupied} / ${board.length**2} cells occupied · ${play.player_to_move===1?'Black':'White'} to move`
      : live ? `Exploring node ${state.snapshot.selected_node} · ${occupied} hypothetical pieces${play?' · move '+searchMove(state.snapshot):'. The search starts from the same root each iteration.'}`
      : 'The board starts with black to play. Chosen pieces will stay here.';
  if(human)$('board-caption').textContent='Your turn. Click an empty intersection'+($('game-rules').value==='legacy_go'?' or pass.':'.');
}
function renderSnapshot(s,costs) {
  if(!s.memory) {
    renderBoard();renderMoves(s.play);renderMetrics(s.display_cycles || 0,costs);
    const finished=Boolean(s.play.terminal), budget=Math.max(1,s.play.total_moves);
    $('phase-description').textContent=finished?'Game finished.':'Waiting for the first computer search.';
    $('progress-label').textContent=finished?`${s.play.completed_moves} moves · game finished`:`${s.play.completed_moves} / ${s.play.total_moves} moves`;
    $('progress').max=budget;$('progress').value=finished?budget:s.play.completed_moves;
    $('progress-percent').textContent=num(finished?100:100*s.play.completed_moves/budget,1)+'%';
    $('run-name').textContent=s.run;
    return;
  }
  const phase=s.event.phase;
  StudioViews.activity(s,state.status,Number($('animation-speed').value));
  for(const element of document.querySelectorAll('.stage')) element.classList.toggle('active',active() && element.dataset.phase===phase);
  const play=s.play, phases=s.phase_cycles, finished=Boolean(play?.terminal);
  $('phase-description').textContent=(play?finished?`Game finished after ${play.completed_moves} moves · `:`Move ${searchMove(s)} / ${play.total_moves} · `:'')+(s.termination?`Memory limit reached · ${num(s.completed)} of ${num(s.budget)} iterations`:phase==='ready'?'Preparing this search.':phase==='move_commit'?`Search complete · ${num(s.completed)} iterations`:`${names[phase] || phase} · iteration ${num(s.event.iteration)} of ${num(s.budget)}`);
  const budget=Math.max(1,play?play.total_moves:s.budget);
  const progress=finished?budget:play?play.completed_moves+(phase==='move_commit'?0:s.completed/s.budget):s.completed;
  $('progress-label').textContent=play?finished?`${play.completed_moves} moves · game finished`:`${play.completed_moves} / ${play.total_moves} moves · ${num(s.completed)} / ${num(s.budget)} iterations`:`${num(s.completed)} / ${num(s.budget)} iterations`;
  $('progress-percent').textContent=`${num(100*Math.min(progress,budget)/budget,1)}%`;
  $('progress').max=budget; $('progress').value=Math.min(progress,budget);
  $('selected').textContent=num(s.selected_node); $('depth').textContent=num(s.path_depth);
  $('value').textContent=s.neural ? num((s.display_black_value_q17 ?? s.value_q17)/131072,4) : '—';
  $('node-usage').textContent=`${num(s.nodes)} / ${num(s.memory.node_capacity)}`;
  $('edge-usage').textContent=`${num(s.edges)} / ${num(s.memory.edge_capacity)}`;
  $('cam-usage').textContent=`${num(s.cam_rows)} / ${num(s.memory.cam_entries)}`;
  for(const [id,n,d] of [['node-meter',s.nodes,s.memory.node_capacity],['edge-meter',s.edges,s.memory.edge_capacity],['cam-meter',s.cam_rows,s.memory.cam_entries]]) $(id).style.width=`${Math.min(100,100*n/Math.max(1,d))}%`;
  renderHardware(s.memory);
  const count=Math.round(24*s.cam_rows/s.memory.cam_entries);
  [...$('cam-cells').children].forEach((cell,i)=>cell.classList.toggle('filled',i<count));
  for(const key of ['selection','expansion','neural','backpropagation']) $(key+'-count').textContent=num(phases[key]||0)+' cycles';
  if(s.neural) for(const [i,key] of ['white','draw','black'].entries()) {
    const value=(s.display_probabilities_q16 || s.neural.probabilities_q16)[i]/65536;
    $('prob-'+key).style.width=`${100*value}%`; $('prob-'+key+'-value').textContent=num(100*value,1)+'%';
  }
  const children=[...s.root_children].sort((a,b)=>b.visits-a.visits).slice(0,5), container=$('root-children');
  container.replaceChildren();
  if(!children.length) { const p=document.createElement('p'); p.textContent='Children appear after expansion.'; container.append(p); }
  for(const child of children) {
    const row=document.createElement('div'); row.className='root-child';
    const label=document.createElement('span'); label.textContent=`Node ${child.id}`;
    const meter=document.createElement('i'), fill=document.createElement('b'); fill.style.width=`${100*child.visits/Math.max(1,children[0].visits)}%`; meter.append(fill);
    const value=document.createElement('strong'); value.textContent=num(child.visits); row.title=child.black_value===null?'Unvisited':`Black value: ${num(child.black_value,4)}`;
    row.append(label,meter,value); container.append(row);
  }
  $('run-name').textContent=s.run;
  renderBoard(); renderTimeline(s.display_phase_cycles || phases); renderInspector(); renderMetrics(s.display_cycles ?? s.cycles,costs);
  renderMoves(play);
}
function renderMoves(play) {
  if(play) {
    $('move-count').textContent=play.terminal?`${play.completed_moves} moves`:`${play.completed_moves} / ${play.total_moves}`;
    const history=$('move-history'); history.replaceChildren();
    if(!play.moves.length) history.textContent=state.status==='awaiting_human'?'Your opening move.':'Searching for the first move…';
    for(const move of [...play.moves].reverse()) {
      const row=document.createElement('div'); row.className='move-entry';
      const piece=document.createElement('i'); piece.className=move.player===1?'black':'white';
      const label=document.createElement('span'); label.textContent=`${move.move}. ${move.player===1?'Black':'White'} · ${move.pass_move?'Pass':`R${move.row+1} C${move.column+1}`}`;
      const timing=document.createElement('small'); timing.textContent=num(move.core_latency_us/1000,3)+' ms';
      row.append(piece,label,timing); history.append(row);
    }
  }
}
function metric(id,value,unit,digits=3) {
  const element=$(id); element.replaceChildren();
  if(value===undefined || value===null) { element.textContent='—'; return; }
  element.append(document.createTextNode(num(value,digits)+' '));
  const suffix=document.createElement('em'); suffix.textContent=unit; element.append(suffix);
}
function renderMetrics(cycles,costs) {
  state.chartTiming={cycles,phases:state.snapshot?.display_phase_cycles || state.snapshot?.phase_cycles || {}};
  metric('latency',cycles/500 >= 1000 ? cycles/500000 : cycles/500,cycles/500 >= 1000?'ms':'µs');
  $('cycles').textContent=num(cycles)+' controller cycles'+(costs?.digital?.timing_violations?.length?'; assumed 500 MHz, native timing failed':'');
  const ledger=costs?.ledger;
  $('metric-energy-scope').textContent=state.execution==='play'?'Total across completed and current searches':'One search for one move';
  metric('energy',ledger?.known_energy_uj ?? costs?.sram.energy_uj,'µJ');
  metric('power',ledger?.known_average_power_mw ?? costs?.sram.average_power_mw,'mW');
  metric('area',ledger?.known_area_mm2 ?? costs?.sram.area_mm2,'mm²',4);
  $('energy-coverage').hidden=!ledger;
  if(ledger) {
    const approximate=ledger.components.some(part=>part.block_power?.target_22nm_energy_nj!=null);
    $('cost-coverage').textContent=ledger.peripheral_model ? `Core estimate includes CAM/analog proxies and physical allowances. ${ledger.missing_area.length} core groups lack area; ${ledger.missing_energy.length} lack energy. Host I/O and programming are excluded. Digital leakage uses the 65 nm estimate. Model: ${ledger.profile}.` : `${approximate?'SRAM + available digital estimates. Digital dynamic power is scaled to 22 nm; leakage uses the 65 nm estimate.':'This saved result covers SRAM energy only.'} ${ledger.missing_area.length} component groups need area costs; ${ledger.missing_energy.length} need energy costs. Full-chip PPA is pending. Model: ${ledger.profile}.`;
    if(ledger.connected_synthesis)$('cost-coverage').textContent+=' Default connected digital power uses an all-elapsed vectorless scenario, without a characterized idle-clock split. User overrides and remaining control allocations are engineering assumptions.';
    if(ledger.controller_report_proxy_components?.length) $('cost-coverage').textContent+=` ${ledger.controller_report_proxy_components.length} controller costs use older report proxies with a 25% allowance, not matching synthesis.`;
    const rows=$('energy-rows'); rows.replaceChildren();
    for(const part of ledger.components) {
      const tr=document.createElement('tr');
      const block=part.block_power;
      const active=(part.active_cycles ?? block?.active_cycles)==null?'n/a':num(part.active_cycles ?? block.active_cycles);
      const idle=block?.idle_cycles==null?'n/a':num(block.idle_cycles);
      const evidence=block?({pending_calibration:'Active/idle power calibration and 22 nm conversion pending.',
        missing_activity:'Activity counters unavailable for this run.',
        missing_configuration:'Matching block characterization needed for this configuration.',
        vectorless_activity_estimate:'Estimated switching; idle clocks included. 22 nm dynamic estimate; 65 nm leakage proxy.',
        vectorless_all_elapsed_scenario:'Connected native65 vectorless dynamic estimate applied over elapsed time; no characterized active/idle clock split. Dynamic energy scaled to 22 nm; leakage retained at native65.',
        user_parameter_scenario:'Custom per-run analytical assumptions replace the default cost coefficients; source characterization is retained as reference.',
        native65_model_estimate:'65 nm block estimate available; 22 nm conversion pending.'}[block.status] || part.energy_status):part.energy_status;
      for(const value of [part.component,active,idle,part.energy_uj===null?(part.scope==='outside_core'?'Excluded':'Needs estimate'):num(part.energy_uj,6),evidence]) {
        const td=document.createElement('td'); td.textContent=value; tr.append(td);
      }
      rows.append(tr);
    }
  }
  if(state.componentData) renderComponents(state.componentData,costs);
}
function renderTimeline(phases) {
  const total=Object.values(phases).reduce((a,b)=>a+b,0); $('timeline-total').textContent=num(total)+' cycles';
  const container=$('timeline'); container.replaceChildren();
  for(const [phase,value] of Object.entries(phases)) {
    const segment=document.createElement('button'); segment.className=phase; segment.style.width=`${100*value/Math.max(1,total)}%`;
    segment.title=`${names[phase]}: ${num(value)} cycles (${num(100*value/Math.max(1,total),2)}%)`;
    segment.setAttribute('aria-label',segment.title); segment.onclick=()=>inspect(phase); container.append(segment);
  }
}
const descriptions={
  selection:['Choose a path','Read node statistics, obtain ordered child IDs from the parent-link CAM, and score visited children. The first unvisited child has priority; equal scores keep the first child.'],
  expansion:['Make room for new children','Check node, edge and path capacity before allocating all empty-cell children in row-major order. A seeded xorshift32 choice appends one child to the path.'],
  neural:['Rollout: estimate the board value','Our rollout uses the mapped neural network: two differential CIM layers, three shared ADC lanes, integer activations and output probabilities. Cell responses are ideal in this model.'],
  backpropagation:['Update the value along the path','Update the packed visit count and exact Q17 value sum from leaf to root. White-to-play nodes accumulate the complement of the black-player value.'],
  iteration_commit:['FSM finish: one final cycle','The global FSM increments the completed-iteration counter after Backprop. This takes one cycle per completed iteration. Other control cycles remain included in their owning stage; this is only the finishing step.']
};
function inspect(phase) { state.inspected=phase; renderInspector(); }
function renderInspector() {
  const incremental={
    selection:['Choose a path','Stop at a parent with untried moves. Once all its moves have children, use UCB to choose where to continue.'],
    expansion:['Add one child','Choose one untried legal move, store one successor and link it to its parent. Keep the other moves available for later visits.'],
    iteration_commit:['Finish and check memory','Finish the iteration, then check the node, child-link and path budgets. This modeled finish takes four cycles.']};
  if(latestHardware()) incremental.neural=['Rollout: estimate the board value','Two offset-encoded 8-bit 1T1M arrays share 32 twelve-bit ADCs. Two result banks overlap conversion and 128-bit readout, followed by eight accumulator lanes and input-sum correction.'];
  const phase=state.inspected, [title,description]=(singleChild()&&incremental[phase]) || descriptions[phase] || descriptions.selection;
  $('inspector-tag').textContent=(names[phase]||phase).toUpperCase(); $('inspector-title').textContent=title; $('inspector-copy').textContent=description;
  const s=state.snapshot, container=$('inspector-stats'); container.replaceChildren(); if(!s?.operations) return;
  const op=s.operations;
  const values=phase==='selection'?[['UCB scores',op.ucb_operations||0],['CAM hits',op.cam_hits||0],['CAM misses',op.cam_misses||0]]:
    phase==='neural'?[['Array pulses',op.neural_array_pulses||0],['ADC conversions',op.neural_adc_conversions||0]]:
    phase==='expansion'?[['Allocated nodes',s.nodes],['Child pointers',s.edges]]:
    [['Completed iterations',s.completed],['Node writes',op.node_sram_write_words||0]];
  for(const [label,value] of values) { const span=document.createElement('span'); span.append(document.createTextNode(label+' ')); const b=document.createElement('b'); b.textContent=num(value); span.append(b); container.append(span); }
}
function renderProgram(program) {
  PipelineView.program(program);
  const container=$('arrays'); container.replaceChildren();
  const current=program.profile.model===state.architecture?.profile;
  const maxCode=2**(program.profile.cell_bits||4)-1;
  $('cell-code-range').textContent=`Cell codes 0–${maxCode}`;
  program.arrays.forEach((array,index)=>{
    const tile=document.createElement('div'); tile.className='array-tile';
    const canvas=document.createElement('canvas'); canvas.width=current?array.columns:128; canvas.height=current?array.rows:256;
    canvas.setAttribute('aria-label',`Array ${index+1}, layer ${array.layer}, ${array.rows} active rows and ${array.columns} programmed columns`);
    canvas.title=`Layer ${array.layer}: ${array.rows} × ${array.columns} programmed cells ${current?'(one 8-bit cell per weight)':'in a 256 × 128 array'}`;
    const context=canvas.getContext('2d'); context.fillStyle='#f1f5f7'; context.fillRect(0,0,canvas.width,canvas.height);
    const cells=atob(array.cells);
    for(let row=0;row<array.rows;row++) for(let col=0;col<array.columns;col++) {
      const t=cells.charCodeAt(row*array.columns+col)/maxCode;
      context.fillStyle=`rgb(${Math.round(224-202*t)},${Math.round(240-179*t)},${Math.round(234-138*t)})`;
      context.fillRect(col,row,1,1);
    }
    const label=document.createElement('small'); label.textContent=`L${array.layer} · array ${index+1}`;
    tile.append(canvas,label); container.append(tile);
  });
}
async function refreshRuns() {
  const index=await api('/api/runs'), container=$('saved-runs'); container.replaceChildren();
  const entries=Object.entries(index.cases).reverse();
  if(!entries.length) container.textContent='Complete a single-position search to create its first immutable result record.';
  for(const [id,item] of entries.slice(0,10)) {
    const row=document.createElement('div'); row.className='saved-row'; const info=document.createElement('div');
    const label=document.createElement('span');
    const caseName=state.catalog.find(c=>c.id===id)?.name || (id.startsWith('custom_')?'Search configuration '+id.slice(7):id);
    label.textContent=savedProfileLabel(item.execution_profile,item.cost_model_profile)+' · '+caseName;
    const code=document.createElement('code'); code.textContent=item.run+' · '+item.result_sha256.slice(0,16); info.append(label,code);
    const links=document.createElement('div');
    for(const [name,file] of [['JSON','result.json'],['CSV','summary.csv']]) {
      const a=document.createElement('a'); a.href=`/api/runs/${item.run}/${file}?download=1`; a.textContent=name; links.append(a,document.createTextNode('  '));
    }
    row.append(info,links); container.append(row);
  }
  const plays=await api('/api/plays'), sessions=$('saved-plays'); sessions.replaceChildren();
  if(!plays.sessions.length) sessions.textContent='Completed placement sessions will appear here.';
  for(const item of plays.sessions) {
    const row=document.createElement('div'); row.className='saved-row';
    const label=document.createElement('span'); label.textContent=`${savedProfileLabel(item.architecture_profile,item.cost_model_profile)} · ${item.run} · ${item.moves} moves${item.status==='memory_limited'?' · memory limit reached':''}`;
    const link=document.createElement('a'); link.href=`/api/plays/${item.run}/moves.csv?download=1`; link.textContent='Move CSV';
    row.append(label,link); sessions.append(row);
  }
}
function renderModelOptions(selected) {
  const select=$('model'); select.replaceChildren();
  const size=Number($('board-size').value), rules=$('game-rules').value;
  for(const model of state.models.filter(m=>m.paper_model)) {
    const option=document.createElement('option'); option.value=model.id; option.textContent=model.label+(model.available?'':' · unavailable');
    option.disabled=!model.available||model.board_size!==size||model.rules!==rules||(latestHardware()&&!state.architecture?.models.includes(model.id));
    option.title=model.reason || '9 × 9 Go'; select.append(option);
  }
  const archived=state.models.find(m=>m.id===selected&&!m.paper_model&&m.available&&m.board_size===size);
  {const option=document.createElement('option');option.value='random_diagnostic';option.textContent='Random weights · hardware diagnostic';select.append(option);}
  if(archived) {
    // Restore saved case/session identities without adding archives to the paper menu.
    const option=document.createElement('option'); option.value=selected; option.hidden=true;
    option.textContent=archived?archived.label:'Random weights · saved diagnostic'; select.append(option);
  }
  const available=[...select.options].filter(o=>!o.disabled);
  select.value=available.some(o=>o.value===selected)?selected:(available[0]?.value || '');
  renderOpponentModels(); modelNote(); controls();
}
function renderOpponentModels() {
  const other=$('opponent-model'),previous=other.value;
  const size=Number($('board-size').value),rules=$('game-rules').value;
  const selected=state.models.find(m=>m.id===$('model').value),turn=!!selected?.turn_indicator;
  other.replaceChildren();
  if(!turn) { const option=document.createElement('option');option.value='random_diagnostic';option.textContent='Random weights';other.append(option); }
  for(const model of state.models.filter(m=>m.available&&m.board_size===size&&!!m.turn_indicator===turn&&(!m.rules||m.rules===rules))) {
    const option=document.createElement('option');option.value=model.id;option.textContent=model.label;other.append(option);
  }
  other.value=previous;
  if(!other.value) other.value=[...other.options].some(o=>o.value===$('model').value)?$('model').value:(other.options[0]?.value || '');
}
function modelNote() {
  const model=state.models.find(m=>m.id===$('model').value), go=$('game-rules').value==='legacy_go';
  $('model-availability').hidden=!!$('model').value;
  $('model-availability').textContent='Go-strong and Go-weak need 9 × 9 Go. Other application models are not available yet. Saved diagnostics are under Advanced.';
  if(Number($('board-size').value)>9) $('model-availability').textContent='Use random weights for the hardware scaling study. Trained checkpoints are available for 9 × 9 only.';
  $('model-note').textContent=model?.paper_model?`${model.label} · recovered tournament weights, including whose turn it is. Playing strength has not been remeasured.`:model?`Saved checkpoint · ${model.hidden_units} hidden units, zero-padded to ${model.hardware_hidden_units}. Mapped task quality is unverified.`:'Seeded random weights for reproducible architecture diagnostics.';
  $('fidelity-note').textContent=go?'Legacy Go uses a host-assisted component schedule. Game rules, metadata and interfaces are outside billed hardware time. Integrated Go RTL and physical timing remain unvalidated.':'complete_serial_q32_v2 · Digital timing is checked against RTL with ideal interfaces. Physical timing and application quality remain unvalidated.';
  if($('readout-profile').value==='column_hold_v1') $('fidelity-note').textContent='Buffered capture and readout control is checked in RTL and generic gates with ideal interfaces. Costs use analytical estimates; analog accuracy and physical timing remain unvalidated.'+(go?' Host Go rules and metadata are excluded.':'');
  if(model?.turn_indicator) $('fidelity-note').textContent='Turn-aware Go uses a component schedule estimate. The 163-input controller has no matching synthesis report; its area and power are excluded from known totals. Host Go rules and physical timing remain unvalidated.';
  if(singleChild()) $('fidelity-note').textContent='Single-child expansion · '+(sizedHardware()?'memory sized for this board.':'preserved fixed-memory profile.')+' Architectural timing estimate; unmatched controller costs are excluded. This historical profile uses the older reference scorer and rollout.'+(go?' Host Go rules are outside billed chip time.':'');
  if(latestHardware()) $('fidelity-note').textContent='Current optimized architecture: '+state.architecture.profile+' · '+state.architecture.cost_model_profile+'. Executable service timing at assumed 500 MHz. Connected native65 synthesis estimates use vectorless power and retained control allowances. Integrated physical timing, full-design equivalence and analog accuracy remain unvalidated. Host Go rules are excluded.';
  $('workload-note').textContent=(go?'Legacy Go rules and scoring. Host rule processing and state metadata are excluded from reported hardware time. ':'Empty-cell placement diagnostic. ')+(model?'Archived checkpoint with explicit signed mapping. Playing strength has not been remeasured.':'Random evaluator; no trained playing-strength claim.');
  StudioViews.activity(state.snapshot?.event?state.snapshot:{event:{phase:'ready'},activity:[]},state.status,Number($('animation-speed').value));
}
function componentSections(parts) {
  const sections=[
    {id:'selection',name:'Selection',owners:['u_sel','u_ucb','cam_macro'],parts:[]},
    {id:'expansion',name:'Expansion',owners:['u_upd'],parts:[]},
    {id:'rollout',name:'Rollout',owners:['u_nn','cim_arrays','row_drivers','sample_hold','adc_lanes','analog_mux','column_hold'],parts:[]},
    {id:'backprop',name:'Backprop',owners:[],parts:[],note:'Uses the shared tree-update controller listed under Expansion.'},
    {id:'fsm',name:'FSM',owners:['top_level_glue','physical_overhead'],parts:[]},
    {id:'memory',name:'Shared memory',owners:['node_sram','child_sram','u_node_router','u_child_router'],parts:[]},
    {id:'other',name:'Other parts',owners:[],parts:[]},
    {id:'external',name:'External',owners:[],parts:[],note:'Outside the timed core.'}
  ];
  const backpropIds=new Set(['u_upd/functions_1','u_upd/u_codec']);
  for(const original of parts) {
    const id=original.id || original.instance;
    const section=original.scope==='outside_core'?sections[7]:sections.find(group=>group.owners.includes(id)) || sections[6];
    let part=original;
    if(id==='u_upd') {
      sections[3].parts.push(...(original.children || []).filter(child=>backpropIds.has(child.id)));
      part={...original,children:(original.children || []).filter(child=>!backpropIds.has(child.id))};
    }
    section.parts.push(part);
  }
  return sections.filter(group=>!['other','external'].includes(group.id) || group.parts.length);
}
function renderComponents(data,costs=null) {
  if(!data) return;
  state.componentData=data;state.componentCosts=costs;
  const ledger=costs?.ledger, parts=ledger?.components || data.components;
  const owners=new Map();
  function registerOwner(part,owner){owners.set(part.id,owner);for(const sub of part.children || [])registerOwner(sub,owner);}
  for(const part of parts)registerOwner(part,part);
  const average=part=>part.average_power_mw ?? (part.energy_uj!=null&&costs?.sram?.latency_us?part.energy_uj*1000/costs.sram.latency_us:null);
  const sections=componentSections(parts);
  const rows=$('component-rows');rows.replaceChildren();
  function append(part,depth,group) {
    const tr=document.createElement('tr');tr.dataset.component=part.id || part.instance || part.component;tr.dataset.depth=depth;
    const child=part.counted===false && part.scope!=='outside_core', external=part.scope==='outside_core';
    const owner=owners.get(part.id) || part;
    const missingArea=child&&owner.area_um2==null, missingPower=child&&costs&&average(owner)==null;
    tr.dataset.group=group;tr.className=external?'component-excluded':child?'component-child':'component-parent';
    const name=document.createElement('td');name.style.paddingLeft=(8+depth*18)+'px';
    if(part.children?.length) {
      const toggle=document.createElement('button');toggle.className='component-toggle';
      const opened=state.componentExpanded.has(part.id);toggle.setAttribute('aria-expanded',String(opened));
      toggle.textContent=(opened?'▾ ':'▸ ')+part.component;
      toggle.onclick=()=>{if(opened)state.componentExpanded.delete(part.id);else state.componentExpanded.add(part.id);renderComponents(state.componentData,state.componentCosts);};
      name.append(toggle);
    } else name.textContent=part.component;
    if(part.rtl_instance){const code=document.createElement('small');code.textContent=part.rtl_instance;name.append(code);}
    tr.append(name);
    const count=document.createElement('td');count.textContent=part.count==null?(external?'External':'Unspecified'):num(part.count);tr.append(count);
    const area=document.createElement('td');area.className='ppa-number';
    area.textContent=external||missingArea?'Excluded':part.area_um2==null?(child?'Included':'Needs report'):num(part.area_um2,3);
    if(child&&!missingArea&&part.area_um2!=null){const note=document.createElement('small');note.textContent='within parent';area.append(note);}tr.append(area);
    const power=document.createElement('td');power.className='ppa-number';
    const avg=average(part);
    power.textContent=external||missingPower?'Excluded':child?(costs?'Included':'Run search'):avg!=null?num(avg,6):costs?'Needs estimate':'Run search';tr.append(power);
    const time=document.createElement('td');time.className='ppa-number';
    const active=part.active_cycles ?? part.block_power?.active_cycles;
    if(external||child)time.textContent=external?'Excluded':(owner.active_cycles ?? owner.block_power?.active_cycles ?? owner.service_cycles)!=null?'Included':costs?'Not recorded':'Run search';
    else if(active!=null){time.textContent=num(active);const label=document.createElement('small');label.textContent='active/service';time.append(label);}
    else if(part.service_cycles!=null){time.textContent=num(part.service_cycles);const label=document.createElement('small');label.textContent='per '+part.service_unit;time.append(label);}
    else time.textContent=costs?'Not recorded':'Run search';
    tr.append(time);
    const evidence=document.createElement('td');
    if(child) {
      evidence.textContent=missingArea||missingPower
        ? `Part of an unestimated parent; ${missingArea&&missingPower?'area and power':missingArea?'area':'power'} excluded from known totals. Timing is included only where the parent records it.`
        : part.details?.native65_part?'Connected native65 hierarchy area, scaled once and included in this owner; vectorless power is preliminary.':part.area_um2==null?'Included in the owning module where that metric is estimated.':part.rtl_instance?'Area from the parent’s synthesis hierarchy; included once.':'Area included in the owning module.';
    }
    else {
      const detail=document.createElement('details'),summary=document.createElement('summary');
      summary.textContent=external?'Outside timed core':part.id==='physical_overhead'?'Engineering allowance':!!part.parameter_status?'Custom user assumption':part.details?.native65_part?'Connected RTL synthesis estimate':part.report_proxy?'Controller report proxy + allowance':['node_sram','child_sram','cam_macro'].includes(part.id)?'CACTI analytical estimate':part.id==='adc_lanes'?'Published 65 nm ADC proxy':part.id==='cim_arrays'?'Super-T workbook estimate':part.cost_model?'Source-linked engineering estimate':part.native_65nm_power?'Synthesis report estimate':part.area_um2==null?'Matching report needed':'Analytical estimate';
      const text=document.createElement('p');text.textContent=part.status;
      if(part.energy_status)text.textContent+=' '+part.energy_status;
      if(part.cost_model?.method)text.textContent+=' '+part.cost_model.method;
      if(part.report_proxy)text.textContent+=' '+part.report_proxy.allowance_basis+' Reference parameters: '+JSON.stringify(part.report_proxy.reference_parameters)+'. '+part.report_proxy.sensitivity_status+'.';
      if(part.native_65nm_power)text.textContent+=` ${part.details?.native65_part?'Connected native 65 nm portion':'Native 65 nm'}: ${num(part.native_65nm_area_um2,3)} µm², ${num(part.native_65nm_power.dynamic_mw,4)} mW dynamic, ${num(part.native_65nm_power.leakage_mw,4)} mW leakage.`;
      if(part.details?.native65_part)text.textContent+=' '+part.details.native65_part.ownership+'. Native source power is vectorless; default active and idle values are equal assumptions, not separate characterizations. User overrides are retained separately.';
      if(part.details?.residual_control_allocation)text.textContent+=' Residual control allowance: '+num(part.details.residual_control_allocation.area_um2,3)+' µm² at the target node. '+part.details.residual_control_allocation.basis;
      if(part.timing)text.textContent+=` Native setup slack ${num(part.timing.critical_slack_ns,2)} ns at ${part.timing.constraint_ns} ns; ${part.timing.violating_setup_paths} violating paths.`;
      if(part.checks?.max_capacitance_violations)text.textContent+=` ${part.checks.max_capacitance_violations} capacitance violations remain.`;
      if(part.checks?.warning_notes)text.textContent+=' '+part.checks.warning_notes;
      detail.append(summary,text);
      if(part.source){const source=document.createElement('small');source.className='component-source';source.textContent=part.source;detail.append(source);}
      evidence.append(detail);
    }
    tr.append(evidence);rows.append(tr);
    if(state.componentExpanded.has(part.id))for(const sub of part.children || [])append(sub,depth+1,group);
  }
  for(const section of sections) {
    const tr=document.createElement('tr');tr.className='component-group';tr.dataset.group=section.id;
    const cell=document.createElement('th');cell.colSpan=6;cell.scope='row';
    const toggle=document.createElement('button'),opened=!state.componentCollapsedGroups.has(section.id);
    toggle.className='component-toggle';toggle.setAttribute('aria-expanded',String(opened));toggle.textContent=(opened?'▾ ':'▸ ')+section.name;
    toggle.onclick=()=>{if(opened)state.componentCollapsedGroups.add(section.id);else state.componentCollapsedGroups.delete(section.id);renderComponents(state.componentData,state.componentCosts);};
    cell.append(toggle);
    if(section.note){const note=document.createElement('small');note.textContent=section.note;cell.append(note);}
    tr.append(cell);rows.append(tr);
    if(opened)for(const part of section.parts)append(part,1,section.id);
  }
  function allOpen(items){return items.every(part=>!part.children?.length || (state.componentExpanded.has(part.id)&&allOpen(part.children)));}
  $('expand-components').textContent=allOpen(parts)&&sections.every(group=>!state.componentCollapsedGroups.has(group.id))?'Collapse all parts':'Show all parts';
  const modern=ledger?.peripheral_model || (!ledger&&data.peripheral_model);
  const missing=parts.filter(part=>part.counted!==false&&part.scope!=='outside_core'&&part.area_um2==null).length;
  $('component-summary').textContent=`${modern?'Known core area estimate':'Saved area subtotal'}: ${num(ledger?.known_area_mm2 ?? data.known_area_mm2,6)} mm². `+(missing?`${missing} core groups lack area estimates. `:'')+(modern?'Includes analytical estimates and a layout allowance. Expand a module to see its parts.':'Historical costs are preserved with their original coverage.');
  const proxyCount=parts.filter(part=>part.report_proxy).length;
  if(proxyCount) $('component-summary').textContent+=` ${proxyCount} controller estimates use report proxies with a 25% allowance; matching synthesis remains unavailable.`;
  $('component-time-note').textContent='Power is each part’s average contribution over the same search or session. Cycles show active/service time at 500 MHz and can overlap. “Included” means counted in the parent for that column. Unestimated parts are excluded from known totals. '+(!costs?'Run a search to fill workload power and activity.':'');
  const failed=data.digital?.timing_violations || [];
  const connected=ledger?.connected_synthesis || data.connected_synthesis;
  $('digital-timing-note').textContent=connected
    ? `Connected native65 selection/readout synthesis constraints: ${connected.current_stage_constraint_closure} at ${connected.clock_period_ns} ns. Original packet acceptance: ${connected.original_packet_acceptance}; full-design equivalence: ${connected.equivalence}. Missing evidence: ${connected.missing_native_evidence.join(', ') || 'none'}. Simulation assumes 500 MHz; physical timing and analog accuracy remain unvalidated.`
    : failed.length
    ? '65 nm timing warning: '+failed.map(row=>`${row.case}: ${num(row.critical_slack_ns,2)} ns slack, ${num(row.violating_setup_paths)} setup violations`).join('; ')+'. Displayed latency assumes 500 MHz.'
    : 'Controller latency assumes 500 MHz. Physical timing and analog accuracy remain unvalidated.';
  const readout=data.analog_readout;
  if(readout)$('readout-summary').textContent=readout.profile==='column_hold_v1'
    ? `Rollout: arrays → ${readout.installed_analog_samples} column holding cells → ${readout.shared_adc_lanes} shared ADC lanes → digital accumulation.`
    : `Rollout: arrays stay driven → ${readout.shared_adc_lanes} shared sample/hold and ADC lanes → digital accumulation.`;
  if(readout)$('readout-summary').textContent+=' Digital buffers and neural SRAM are listed under their owners; cost coverage follows each parent.';
  StudioViews.architecture(data);
  Microarchitecture.render(data);
  AreaView.render(data,costs);
  renderBreakdown(data,costs);
}
function renderBreakdown(data,costs) {
  const size=Number($('board-size').value),budget=Number($('iterations').value);
  CostCharts.render(data,costs,costs?state.chartTiming:null,{
    configuration:`${size} × ${size} · ${num(budget)} ${$('execution').value==='play'?'iterations / move':'search iterations'}`,
    status:costs?(state.status==='memory_limited'?'Memory-limited result':state.status==='complete'?'Completed run':state.execution==='play'?'Session so far':'Search so far'):'Configuration preview',
    unavailable:latestHardware()&&state.architecture&&!state.architecture.supported_boards.includes(size)?'This architecture does not support this board size.':null});
}
function expandComponents() {
  const parts=state.componentCosts?.ledger?.components || state.componentData?.components || [];
  const all=[];function collect(rows){for(const row of rows){if(row.children?.length){all.push(row.id);collect(row.children);}}}collect(parts);
  const open=all.some(id=>!state.componentExpanded.has(id)) || componentSections(parts).some(group=>state.componentCollapsedGroups.has(group.id));
  state.componentExpanded=new Set(open?all:[]);state.componentCollapsedGroups.clear();
  $('expand-components').textContent=open?'Collapse all parts':'Show all parts';renderComponents(state.componentData,state.componentCosts);
}
async function refreshComponents() {
  const request=(state.componentRequest || 0)+1;state.componentRequest=request;
  state.componentData=null;state.componentCosts=null;state.chartTiming=null;
  Microarchitecture.render(null);
  AreaView.render(null);
  $('component-rows').replaceChildren();renderBreakdown(null,null);
  $('component-summary').textContent='Loading this configuration…';
  try {
    const data=await api(`/api/components?board=${$('board-size').value}&memory=${$('memory-profile').value}&readout=${$('readout-profile').value}&model=${encodeURIComponent($('model').value||'random_diagnostic')}&expansion=${singleChild()?'single':'legacy'}&rules=${$('game-rules').value}&hardware=${sizedHardware()?state.hardwareProfile:''}&architecture=${latestHardware()?state.architecture?.profile:''}`);
    if(request===state.componentRequest&&!active()){
      state.parameterCatalog=data.parameter_catalog;renderParameterEditor();
      const preview=latestHardware()&&Object.keys(state.componentParameters).length?await api('/api/component-preview',{board_size:Number($('board-size').value),model_id:$('model').value,component_parameters:state.componentParameters}):data;
      if(request===state.componentRequest&&!active()){renderComponents(preview);renderHardware(preview.installed_memory);}
    }
  } catch(error) { if(request===state.componentRequest)message(error.message); }
}
async function calculateCrossbar() {
  try {
    if(!$('crossbar-size').reportValidity()) return;
    const value=await api(`/api/crossbar?size=${$('crossbar-size').value}`);
    const ref=value.sequential_reference;
    $('crossbar-reference').textContent=`22 nm · ${value.size} × ${value.size}: differential pair with periphery ${num(value.crossbar_pair_area_um2,3)} µm²; ${value.weight_bits}-bit MVM unit ${num(value.mvm_unit_area_um2,3)} µm². Sequential-converter reference: ${num(ref.mvm_energy_pj,3)} pJ per MVM, ${num(ref.read_duration_ns,0)} ns, ${num(ref.average_power_mw,3)} mW. These workbook estimates describe its temporal circuit; the active chip uses a different readout.`;
  } catch(error) { message(error.message); }
}
async function init() {
  $('expand-components').onclick=expandComponents;
  $('parameter-reset').onclick=()=>{state.componentParameters={};custom();refreshComponents();};
  $('parameter-download').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({schema:'component_unit_parameters_v1',architecture:state.architecture?.profile,cost_model_profile:state.componentData?.cost_model_profile,cost_model_sha256:state.componentData?.cost_model_sha256,source_sha256:state.componentData?.source_sha256,connected_synthesis:state.componentData?.connected_synthesis,board_size:Number($('board-size').value),component_parameters:state.componentParameters,defaults:state.parameterCatalog},null,2)],{type:'application/json'}));a.download='imc-component-values.json';a.click();URL.revokeObjectURL(a.href);};
  StudioViews.init();
  AreaView.init();
  PipelineView.init();
  renderIterationOptions();
  controls();
  resetBoard(); for(let i=0;i<24;i++) $('cam-cells').append(document.createElement('i'));
  $('run').onclick=()=>runSearch('end');$('run-one').onclick=()=>runSearch('one'); $('pause').onclick=()=>act(state.status==='paused'?'resume':'pause'); $('step').onclick=()=>act('step'); $('cancel').onclick=()=>act('cancel');
  $('finish').onclick=()=>act('finish');$('pass-move').onclick=()=>act('human_move',[-1,-1]);
  $('new-game').onclick=newGame;
  for(const id of ['opponent','architecture-side']) $(id).onchange=()=>{custom();opponentControls();};
  $('animation-speed').oninput=()=>{speedLabel();if(state.job)act('speed',Number($('animation-speed').value));};
  $('tree-history').onchange=async()=>{try{if($('tree-history').value==='live')StudioViews.live();else StudioViews.showArchive(await api(`/api/jobs/${state.job}/tree/${$('tree-history').value}`));}catch(error){message(error.message);}};
  $('architecture-profile').onchange=()=>{
    if(active())return;
    if(state.job)resetRunView();
    const current=$('architecture-profile').value==='current';
    applyConfiguration(current?state.architecture.default_configuration:{board_size:9,iterations:500,seed:0,model_id:'go_strong_v1',rules:'legacy_go',hardware_profile:'board_sized_s1_v1'});
    $('case').value='';controls();refreshComponents();
  };
  $('case').onchange=()=>applyCase($('case').value);
  $('execution').onchange=()=>{ custom();modeControls(); }; modeControls();
  $('board-size').onchange=()=>{ state.componentParameters={};renderIterationOptions(); custom(); for(const id of ['nodes','edges','path'])$(id).value=''; resetBoard(); renderModelOptions(); renderHardware(); refreshComponents(); };
  $('game-rules').onchange=()=>{ custom(); modeControls(); renderModelOptions(); refreshComponents(); };
  $('model').onchange=()=>{ custom(); renderOpponentModels(); modelNote(); controls(); refreshComponents(); };
  $('readout-profile').onchange=()=>{ custom(); modelNote(); refreshComponents(); };
  $('calculate-crossbar').onclick=calculateCrossbar;
  for(const id of ['iterations','seed','exploration','memory-profile','nodes','edges','path','opponent-model','opponent-iterations','opponent-seed']) $(id).onchange=custom;
  for(const tab of ['played','live','input']) $(tab+'-tab').onclick=()=>selectBoardTab(tab);
  for(const stage of document.querySelectorAll('.stage')) stage.onclick=()=>inspect(stage.dataset.phase);
  $('memory-profile').onchange=()=>{ custom(); refreshComponents(); };
  $('refresh-runs').onclick=()=>refreshRuns().catch(error=>message(error.message));
  try {
    const [data,models,hardware,architecture]=await Promise.all([api('/api/catalog'),api('/api/models'),api('/api/board-hardware'),api('/api/architecture')]); state.catalog=data.cases; state.models=models.models;state.architecture=architecture;
    state.hardwareTable=hardware.boards;
    for(const row of hardware.boards)iterationPresets[row.board_size]=['low','medium','high'].map(tier=>row.iterations[tier]);
    renderIterationOptions();renderHardware();
    for(const item of data.cases) { const option=document.createElement('option'); option.value=item.id; option.textContent='Historical · '+item.name+(item.configuration.profile&&!item.configuration.profile.startsWith('single_child_')?' · legacy full expansion':''); $('case').append(option); }
    applyConfiguration(state.architecture.default_configuration);
    $('case').value='';renderModelOptions($('model').value);modeControls();opponentControls();speedLabel();await refreshRuns(); await refreshComponents(); await calculateCrossbar();
    const saved=await api('/api/snapshot'), frozen=saved.snapshot;
    if(frozen) {
      $('snapshot-note').textContent=`${frozen.id} · Each row was reproduced by two independent runs. Values below come from the saved CSV. Preserved profiles are named in each row. Core estimates only; playing strength is unvalidated.`;
      $('snapshot-csv').href=`/api/snapshots/${frozen.id}/summary.csv`;
      $('snapshot-csv').hidden=false;
      const body=$('snapshot-table').querySelector('tbody');body.replaceChildren();
      for(const row of saved.rows) {
        const tr=document.createElement('tr'),label=document.createElement('th');
        label.textContent='Historical · '+(state.catalog.find(c=>c.id===row.case_id)?.name || row.case_id)+(row.execution_profile?.startsWith('single_child_')?' · single-child':' · legacy full expansion');
        label.title=`${row.execution_profile || ''} · ${row.model_id} · ${row.execution_sha256}`;
        tr.append(label);
        for(const [key,digits] of [['core_cycles',0],['core_latency_us',3],['known_energy_uj',6],['known_average_power_mw',6],['known_area_mm2',9]]) {
          const cell=document.createElement('td');cell.dataset.field=key;cell.dataset.value=row[key] ?? '';
          cell.textContent=row[key]==null||row[key]===''?'Unavailable':num(Number(row[key]),digits);tr.append(cell);
        }
        body.append(tr);
      }
      $('snapshot-table').hidden=!saved.rows.length;
    }
    const session=await api('/api/session');
    if(session.job) {
      $('case').value=state.catalog.some(c=>c.id===session.job.case_id)?session.job.case_id:'';
      $('execution').value=session.job.execution || 'search';modeControls();
      applyConfiguration(session.job.configuration); attachJob(session.job);
    }
  } catch(error) { message(error.message); }
  finally {state.loading=false;controls();}
}
function opponentControls(){
  const self=$('opponent').value==='self',play=$('execution').value==='play';
  $('opponent-settings').hidden=$('opponent').value!=='engine';
  $('architecture-side').disabled=state.loading||active()||self||!play;
  $('opponent').querySelector('option[value="human"]').textContent='Me · '+($('architecture-side').value==='white'?'Black':'White');
  $('side-note').textContent=!play?'Side selection applies to games.':self?'Self-play uses both sides.':'';
  $('side-note').hidden=play&&!self;
}
function speedLabel(){const value=Number($('animation-speed').value);$('speed-value').textContent=value<30?'Slow':value<60?'Detailed':value<90?'Fast':'Fastest';document.documentElement.style.setProperty('--flow-time',`${Math.max(.18,2*(1-value/100))}s`);}
function resetRunView(){
  state.job=null;state.jobError='';state.snapshot=null;state.status='ready';state.seq=0;state.programJob=null;state.boardKey=null;
  state.execution=$('execution').value;state.chartTiming=null;state.componentCosts=null;
  StudioViews.reset();PipelineView.reset();renderBoard();renderInspector();controls();message('');
  $('progress').value=0;$('progress-label').textContent='Ready to play';$('progress-percent').textContent='0%';
  for(const id of ['export-json','export-csv','export-power','export-components','export-source','export-moves']){$(id).removeAttribute('href');$(id).classList.add('disabled');$(id).setAttribute('aria-disabled','true');}
  $('run-name').textContent='No saved run';$('identity').textContent='';$('move-history').replaceChildren();$('move-count').textContent='0';
  $('results-title').textContent='Results and evidence';$('results-description').textContent='Run this configuration to see its results.';
  for(const id of ['latency','energy','power','area','value','prob-white-value','prob-draw-value','prob-black-value'])$(id).textContent='—';
  $('cycles').textContent='Assumed 500 MHz clock';$('selected').textContent='0';$('depth').textContent='0';
  for(const key of ['selection','expansion','neural','backpropagation'])$(key+'-count').textContent='0 cycles';
  for(const id of ['node-meter','edge-meter','cam-meter','prob-white','prob-draw','prob-black'])$(id).style.width='0%';
  $('node-usage').textContent='0 nodes';$('edge-usage').textContent='0 pointers';$('cam-usage').textContent='0 rows';
  $('root-children').replaceChildren();$('timeline').replaceChildren();$('timeline-total').textContent='No activity yet';$('energy-coverage').hidden=true;$('energy-rows').replaceChildren();
  $('arrays').replaceChildren();$('phase-description').textContent='Ready for a new search.';$('tree-caption').textContent='Branches appear as the search explores possible moves.';
  [...$('cam-cells').children].forEach(cell=>cell.classList.remove('filled'));
  for(const stage of document.querySelectorAll('.stage')) stage.classList.remove('active');
  $('cost-coverage').textContent='22 nm target. Area, energy and timing have separate source coverage.';
  StudioViews.activity({event:{phase:'ready'},activity:[]},'ready',Number($('animation-speed').value));
  if(state.componentData) renderComponents(state.componentData);
  else renderBreakdown(null,null);
}
async function newGame(){try{
  if(active()){const id=state.job;await api(`/api/jobs/${id}/actions`,{action:'cancel'});for(let i=0;i<100;i++){const job=await api(`/api/jobs/${id}`);if(['cancelled','complete','memory_limited','failed'].includes(job.status))break;await new Promise(r=>setTimeout(r,100));if(i===99)throw new Error('The current search is still stopping. Try again in a moment.');}}
  resetRunView();resetBoard();
  await refreshComponents();
}catch(error){message(error.message);}}
init();

function renderParameterEditor() {
  $('parameter-editor').hidden=!latestHardware()||!state.parameterCatalog;
  const root=$('parameter-fields');const opened=new Set([...root.querySelectorAll('details[open]')].map(node=>node.dataset.group));root.replaceChildren();
  if(!state.parameterCatalog)return;
  for(const group of state.parameterCatalog.groups) {
    const details=document.createElement('details'),summary=document.createElement('summary');details.dataset.group=group.id;details.open=opened.has(group.id);summary.textContent=group.label;details.append(summary);
    for(const field of group.fields) {
      const label=document.createElement('label');label.textContent=field.label+' ('+field.unit+')';
      const input=document.createElement('input');input.type='number';input.required=true;input.min=field.minimum;input.max=field.maximum;input.step=field.integer?'1':'any';input.value=state.componentParameters[group.id]?.[field.key] ?? field.default;input.dataset.group=group.id;input.dataset.field=field.key;input.setAttribute('aria-label',group.label+': '+label.textContent);
      input.oninvalid=()=>{for(let parent=input.parentElement;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;};
      input.onchange=()=>{
        if(active()||!input.reportValidity())return;
        const value=Number(input.value);if(!Number.isFinite(value)||input.value==='')return;
        state.componentParameters[group.id] ||= {};
        if(value===field.default)delete state.componentParameters[group.id][field.key];else state.componentParameters[group.id][field.key]=value;
        if(!Object.keys(state.componentParameters[group.id]).length)delete state.componentParameters[group.id];
        custom();refreshComponents();
      };
      label.append(input);details.append(label);
    }root.append(details);
  }
  $('parameter-status').textContent=Object.keys(state.componentParameters).length?'Custom assumptions, saved with the run':state.architecture?.connected_synthesis?'Default source values; connected digital power is vectorless with equal assumed active/idle values':'Default source values';
  controls();
}
