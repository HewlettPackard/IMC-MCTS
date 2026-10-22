/* SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP */
/* Original renderer; all search state and activity come from the local simulator. */
/* SPDX-License-Identifier: MIT */
const StudioViews = (() => {
  const el=id=>document.getElementById(id), ns='http://www.w3.org/2000/svg';
  const svg=(tag,attrs={},text)=>{const n=document.createElementNS(ns,tag); for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,v); if(text!==undefined)n.textContent=text; return n;};
  const blocks={
    selector:[24,65,228,42,'Cached selector','Find the next child to visit.',['Request control','Child ID cache','Best-child comparison']],
    cam:[24,122,108,50,'Parent CAM','Associative lookup of a parent’s child list.',['Parent key','Valid rows','Child IDs']],
    ucb:[144,122,108,50,'UCB scorer','Balance promising moves with less explored moves.',['Log table','Integer square root','Division','Score comparison']],
    update:[24,261,228,42,'Shared tree update','One physical Tree update module (u_upd) performs Expansion and Backpropagation.',['Node / edge capacity','Board scan','Child record writer','Parent list update']],
    allocator:[24,319,108,48,'Child allocator','Allocation logic inside the shared Tree update module.',['Node / edge counters','Capacity checks','Record addresses']],
    choice:[144,319,108,48,'Seeded choice','Choose a child within the same shared Tree update module.',['Xorshift32 state','Child index','Path append']],
    backprop:[24,456,228,42,'Tree update · backprop','Backprop reuses u_upd from Expansion. It reads the path and updates each ancestor.',['Path reader','Player perspective','Visit / value update','Record writeback']],
    stats:[24,514,108,48,'Visit / value','Statistics arithmetic inside the shared Tree update module.',['Visit increment','Q17 value sum','White-player complement']],
    codec:[144,514,108,48,'Q17 codec','Representation conversion inside u_upd. Its area and power follow the parent’s coverage.',['Value decode','Q17 conversion','Value encode']],
    path:[326,547,236,40,'Path & board scratch','Reserved regions of node SRAM, not additional physical memories.',['Path entries','Working board','Child statistics']],
    glue:[326,65,236,48,'Global FSM','The finite state machine coordinates the four stages and finishes each iteration. The pipeline shows the finish cycles for this execution profile.',['Stage sequencing','Request ownership','Iteration completion and memory budget']],
    counter:[326,129,112,48,'Iteration counter','State inside the global FSM. It increments after Backprop finishes.',['Budget register','Completed count','Last-iteration check']],
    handshake:[450,129,112,48,'Start / done','Control and handshake state inside the global FSM.',['Start / ready','Result / acknowledgement','Error propagation']],
    node_router:[326,309,112,48,'Node router','Route one request to the selected node bank.',['Bank decode','Request registers','Response holding']],
    child_router:[450,309,112,48,'Child router','Route requests to child-pointer storage.',['Request registers','Response holding']],
    node_sram:[326,380,236,66,'Node SRAM','Nodes, boards and reserved scratch share the installed banks.',['Nodes & boards','Path & working board','Hidden values','Logits & LUT']],
    child_sram:[326,471,236,54,'Child SRAM','Child records and their ordering across the installed banks.',['Child IDs','List storage','Single read/write port']],
    sequencer:[638,65,224,38,'Neural sequencer','Schedule both mapped layers and their shared resources.',['Layer / tile counters','SRAM handshake','ADC handshake']],
    drivers:[638,133,104,42,'Input drivers','Drive the selected input bits into active array rows.',['Row selection','Bit drive']],
    arrays:[758,133,104,42,'CIM layers','Programmed differential cell slices for layers 1 and 2.',['Layer 1 arrays','Layer 2 arrays','Signed cell slices']],
    column_hold:[638,207,104,42,'Column hold','Optional bank that holds array outputs during conversion.',['Sample bank','Capture control']],
    mux:[758,207,104,42,'Column mux','Select the next group of columns.',['Column group','Shared ADC routing']],
    sample_hold:[638,281,104,42,'Sample / hold','Hold values at the ADC inputs.',['Shared S/H lanes']],
    adc:[758,281,104,42,'ADC bank','Convert selected analog column values into digital codes.',['Three shared lanes','8-bit conversion']],
    readout:[638,355,104,42,'Readout bus','Transfer converted values to accumulation.',['32-bit transfer','ADC result registers']],
    accumulator:[758,355,104,42,'Accumulator','Combine bit slices and differential contributions.',['Shift / add lane','32 × 32-bit registers']],
    activation:[638,429,104,42,'Activation','Rescale hidden-layer outputs and store them in SRAM.',['ReLU','Scale / round','8-bit hidden values']],
    output:[758,429,104,42,'Output logic','Form the three outcome probabilities and board value.',['Logits','Exponential LUT','Probability / value']],
    divider:[638,503,224,48,'Integer divider','Normalize the three output probabilities.',['Numerator','Denominator','Remainder','Quotient']],
  };
  const internals={
    selector:[['Request control',['Node metadata reader','Path writer','Request / response state']],['Child ID cache',['Parent headers','FIFO replacement','Valid entries','Child ID buffer']],['Candidate comparison',['First-unvisited priority','First-tie selection','Best score / child registers']]],
    cam:[['Parent match',['Parent ID keys','Valid / match bits']],['Cached child list',['Child IDs','Group length / location']]],
    ucb:[['Log table',['Parent visit lookup','Log approximation']],['Integer square root',['Radicand','Root / remainder state']],['Division',['Value / visits','Exploration normalization']],['Score comparison',['Q32 arithmetic','Best score register']]],
    update:[['Allocation',['Node / edge capacity checks','Packed addresses','Child count']],['Child construction',['Working-board reader','Empty-cell scan','Node record initialization','Child-record writer']],['Seeded child choice',['Xorshift32 state','Modulo candidate count','Path append']],['Parent update',['List head and count','Tail link for incremental expansion']]],
    backprop:[['Path reader',['Path pointer','Ancestor node ID','Node metadata reader']],['Statistics update',['Visit increment','Player complement','Q17 value accumulation']],['Q17 codec',['Packed value decode','Fixed-point conversion','Packed value encode']],['Writeback',['Visit word','Value words','Memory handshake']]],
    glue:[['Global FSM',['Selection start / wait','Expansion start / wait','Rollout start / wait','Backprop start / wait']],['Iteration completion',['Completed counter','Budget comparison','Finish / next iteration']],['Shared request ownership',['Node interface owner','Child interface owner','Response routing']],['Control state',['Start / ready','Result / acknowledgement','Error propagation']]],
    node_router:[['Request registers',['Read / write','Byte address','Write data']],['Bank decode',['Installed-bank selection','Alignment / bounds check']],['Response holding',['Read data','Valid / error','Consumer acknowledgement']]],
    child_router:[['Request registers',['Read / write','Byte address','Write data']],['Bank decode',['Installed-bank selection','Alignment / bounds check']],['Response holding',['Read data','Valid / error','Consumer acknowledgement']]],
    node_sram:[['Installed native SRAM banks',['Node records','Packed board positions']],['Reserved scratch regions',['Selected path','Working board','Child statistics']],['Rollout storage',['Hidden vector','Logits','Exponential LUT','Probabilities / value']]],
    sequencer:[['Local FSM',['Input read','Drive / settle','Mux / sample / convert','Accumulate / writeback']],['Loop state',['Layer','Array / tile','Input bit','Row / column group']],['Interfaces',['SRAM requests / responses','ADC requests / responses','Accumulator commands','Divider start / result']],['Output schedule',['Maximum logit','LUT address / reads','Exponential sum','Probability / value writes']]],
    arrays:[['Layer 1',['Row tiles','Output tiles']],['Layer 2',['Hidden inputs','Three outputs']],['Differential cell slices',['Positive / negative branches','Low / high 4-bit slices']]],
    accumulator:[['Shift / add lane',['Input-bit shift','Cell-slice shift','Signed add / subtract','Overflow check']],['32 × 32-bit registers',['Write decode','Read mux','Clear control']]],
    activation:[['Signed scale lane',['Multiply / shift','Round to nearest','Clamp to hidden range']],['ReLU',['Negative-value clamp','8-bit hidden writeback']]],
    output:[['Logits',['Maximum of three','Subtract maximum']],['Exponential LUT',['Address calculation','SRAM table reads','Sum of three exponentials']],['Probability / value',['Three normalized probabilities','Black value reduction','Result registers']]],
    divider:[['Restoring division',['48-bit numerator','32-bit denominator','Remainder / quotient','Bit counter']],['Rounding and control',['Round to nearest, ties to even','Start / ready','Done / error']]],
  };
  blocks.candidates=[0,0,0,0,'Candidate operand banks','Hold the next candidates while the current group is scored.',['Two banks','16 × 128 bits per bank','Ordered reduction']];
  blocks.correction=[0,0,0,0,'Offset correction','Subtract 128 times the input sum from each accumulated column. This recovers signed dot products from unsigned cell conductances.',['Input sum','Shift by 7','Subtract once per output']];
  const originalBlocks=JSON.parse(JSON.stringify(blocks)),originalInternals=JSON.parse(JSON.stringify(internals));
  function architecture(data){
    for(const id of Object.keys(blocks))blocks[id]=JSON.parse(JSON.stringify(originalBlocks[id]));
    for(const id of Object.keys(internals))internals[id]=JSON.parse(JSON.stringify(originalInternals[id]));
    if(!data?.architecture)return;
    const firstRows=data.architecture.arrays[0].rows;
    Object.assign(blocks,{
      ucb:[0,0,0,0,'16 parallel UCB scorers','Score up to 16 visited children concurrently. Each scorer overlaps division and square root; ties retain child order.',['16 lanes',`${data.installed_memory?.ucb_busy_cycles ?? 169} busy cycles per scorer`,'Ordered winner reduction']],
      arrays:[0,0,0,0,'Two 8-bit 1T1M arrays',`Layer 1 is ${firstRows} × 96; layer 2 is 96 × 3. One unsigned 8-bit cell stores each offset-encoded weight.`,['q + 128','256 ideal levels','Two physical arrays']],
      adc:[0,0,0,0,'32 shared 12-bit ADCs',`Convert a column group in ${data.installed_memory?.adc_service_cycles ?? 13} modeled cycles. ADCs are shared between the two layers.`,['32 lanes','12-bit code',`${data.installed_memory?.adc_service_cycles ?? 13}-cycle service`]],
      readout:[0,0,0,0,'128-bit readout and result banks','Two 32 × 16-bit result banks feed a 512-bit staging register before accumulation. Eight padded ADC codes travel per bus word.',['Two result banks','128-bit bus','512-bit staging','Backpressure / ownership']],
      accumulator:[0,0,0,0,'Eight accumulator lanes','Accumulate bit-serial products into 96 banked 32-bit registers. Offset correction follows accumulation.',['Eight ALUs','96 × 32-bit registers','No differential branches']]});
    internals.ucb=[['16 lanes',['One divider and square root per lane','Overlapping arithmetic',`${data.installed_memory?.ucb_busy_cycles ?? 169} active cycles per score`]],['Shared ordered reduction',['First unvisited child','First tie wins']]];
    internals.arrays=[[`${firstRows} × 96`,['Board channels and turn bit','96 hidden outputs']],['96 × 3',['Three outcome logits']],['Offset encoding',['8-bit signed weights stored as q + 128','Digital input-sum correction']]];
    internals.accumulator=[['Eight ALUs',['Input-bit shift','Unsigned accumulation']],['96 × 32-bit registers',['Eight banks of 12 words','Conflict-checked writes']]];
  }
  const stageName=name=>({selection:'Selection',expansion:'Expansion',neural:'Rollout',backpropagation:'Backprop',iteration_commit:'FSM finish'})[name]||name.replaceAll('_',' ');
  let snapshot=null, selectedBlock='glue', paused=false;
  const openedUnits=new Set();
  function chip() { Microarchitecture.init(blocks,inspectBlock); }
  function inspectBlock(id) {
    selectedBlock=id;const b=blocks[id];el('block-title').textContent=b[4];el('block-description').textContent=b[5];
    document.querySelectorAll('.chip-block').forEach(n=>n.classList.toggle('selected',n.dataset.block===id));
    const detail=el('block-stats');detail.replaceChildren();
    const units=document.createElement('div');units.className='subblocks';
    for(const unit of internals[id]||b[6]){if(Array.isArray(unit)){const d=document.createElement('details'),s=document.createElement('summary'),list=document.createElement('ul'),key=id+':'+unit[0];d.open=openedUnits.has(key);d.ontoggle=()=>{if(d.open)openedUnits.add(key);else openedUnits.delete(key);};s.textContent=unit[0];for(const part of unit[1]){const li=document.createElement('li');li.textContent=part;list.append(li);}d.append(s,list);units.append(d);}else{const n=document.createElement('span');n.textContent=unit;units.append(n);}}detail.append(units);
    const owner={allocator:'update',choice:'update',backprop:'update',stats:'update',codec:'update',counter:'glue',handshake:'glue'}[id]||id;
    const phase=snapshot?.event?.phase;
    const matches= !['update','allocator','choice'].includes(id)||phase==='expansion';
    const backMatches= !['backprop','stats','codec'].includes(id)||phase==='backpropagation';
    const groups=(snapshot?.activity||[]).filter(g=>matches&&backMatches&&g.blocks.includes(owner));
    const list=document.createElement('ul');list.className='operation-list';
    for(const g of groups){const li=document.createElement('li');li.textContent=`${stageName(g.stage)} · ${g.operation.replaceAll('_',' ')} × ${g.count.toLocaleString()}`;list.append(li);}
    if(!groups.length){const li=document.createElement('li');li.className='empty-activity';li.textContent='No recorded service for this block in the current phase.';list.append(li);}detail.append(list);
    const note=document.createElement('small');note.textContent='Recorded service groups, in first-use order. Repeated work is counted together; controller gaps are not internal signal timing.';detail.append(note);
  }
  function activity(s,status,speed){
    snapshot=s;paused=status==='paused';document.body.classList.toggle('playback-paused',paused);
    document.documentElement.style.setProperty('--flow-time',`${Math.max(.18,2*(1-speed/100))}s`);
    const groups=s.activity||[],index=s.activity_index??-1;
    const shown=index<0?groups:groups.slice(index,index+1), ids=new Set(shown.flatMap(g=>g.blocks));
    const running=['running','paused'].includes(status);
    ids.delete('update');
    if(running&&s.event.phase==='expansion')ids.add('update');
    if(running&&s.event.phase==='backpropagation'){ids.add('backprop');ids.add('update');}
    if(running&&s.event.phase==='selection')ids.add('selector');
    if(running&&s.event.phase==='neural')ids.add('sequencer');
    if(running&&s.event.phase!=='ready')ids.add('glue');
    if(running&&s.event.phase==='iteration_commit')ids.add('counter');
    document.querySelectorAll('.chip-group').forEach(n=>n.classList.toggle('phase-active',running&&((n.dataset.stages||n.dataset.stage||'').split(' ').includes(s.event.phase)||n.classList.contains('control')&&s.event.phase!=='ready')));
    document.querySelectorAll('.chip-block').forEach(n=>n.classList.toggle('flow-active',running&&ids.has(n.dataset.block)));
    document.querySelectorAll('.chip-link').forEach(n=>n.classList.toggle('flow-active',running&&ids.has(n.dataset.from)&&ids.has(n.dataset.to)));
    const held=document.getElementById('readout-profile')?.value==='column_hold_v1';
    document.querySelector('[data-block="column_hold"]')?.classList.toggle('uninstalled',!held);
    document.querySelector('[data-from="column_hold"]')?.classList.toggle('unused-route',!held);
    for(const line of document.querySelectorAll('[data-from="arrays"]'))line.classList.toggle('unused-route',held?line.dataset.to==='mux':line.dataset.to==='column_hold');
    el('flow-caption').textContent=index>=0?`${stageName(shown[0].stage)} · ${shown[0].operation.replaceAll('_',' ')} × ${shown[0].count.toLocaleString()}`:
      groups.length?`${groups.length} recorded activity groups · slow down to inspect each`:'Choose a block to look inside.';
    inspectBlock(selectedBlock);
    AreaView.activity();
  }

  let nodes=new Map(),children=new Map(),key=null,revision=0,path=[],positions=new Map(),collapsed=new Set();
  let archive=null,selected=null,follow=true,pan={x:0,y:18},zoom=.9,canvas,ctx,width=0,height=560,dirty=true,drag=null,firstView=true;
  let bounds={left:0,right:0,bottom:0},painted=[];
  const card={width:92,height:134,board:76};
  const currentNodes=()=>archive?.nodes||nodes;
  function reset(){nodes=new Map();children=new Map();key=null;revision=0;path=[];positions.clear();collapsed.clear();archive=null;selected=null;follow=true;firstView=true;zoom=.9;el('tree-history').replaceChildren(new Option('Current search','live'));el('tree-board').replaceChildren();el('tree-node-stats').textContent='Select a board to inspect its node.';el('tree-node').value=0;el('tree-branch').disabled=true;layout();}
  function update(data,s){
    if(!data)return;
    const history=el('tree-history'),old=history.value,moves=s?.play?.moves.filter(m=>m.search_run)||[];
    if(history.options.length!==moves.length+1){history.replaceChildren(new Option('Current search','live'));for(const move of moves)history.add(new Option('Move '+move.move,String(move.move)));history.value=old;}
    if(data.revision===revision&&data.key===key&&!data.reset)return;
    if(data.reset||key!==data.key){const changed=key!==data.key;nodes=new Map();key=data.key;if(changed&&!archive){collapsed.clear();selected=0;follow=true;firstView=true;zoom=.9;}}
    for(const n of data.nodes)nodes.set(n.id,n);
    revision=data.revision;path=data.path||[];
    if(!archive){if(follow){for(const id of path)collapsed.delete(id);selected=path.at(-1)??0;}layout();
      el('tree-caption').textContent=`${s?.play?'Move '+searchMove(s,key)+' · ':''}${nodes.size.toLocaleString()} nodes · iteration ${s?.event?.phase==='move_commit'?s.completed:s?.event?.iteration??0}`;
    }
  }
  function layout(){
    const data=currentNodes();children=new Map();for(const n of data.values()){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}
    positions=new Map();const levels=[];
    function visit(id,depth){if(!levels[depth])levels[depth]=[];levels[depth].push(id);
      if(!collapsed.has(id))for(const child of children.get(id)||[])visit(child,depth+1);
    }
    if(data.has(0))visit(0,0);
    // Keep siblings readable even when another branch has thousands of descendants.
    levels.forEach((row,depth)=>row.forEach((id,index)=>positions.set(id,{x:(index-(row.length-1)/2)*112,y:depth*194+card.height/2})));
    const root=positions.get(0)?.x||0;bounds={left:0,right:0,bottom:0};for(const p of positions.values()){p.x-=root;bounds.left=Math.min(bounds.left,p.x-card.width/2);bounds.right=Math.max(bounds.right,p.x+card.width/2);bounds.bottom=Math.max(bounds.bottom,p.y+card.height/2);}
    el('tree-empty').hidden=data.size>0;
    el('tree-coverage').textContent=data.size?`${positions.size.toLocaleString()} board positions in the view · ${data.size.toLocaleString()} total nodes.${positions.size<data.size?' Some branches are manually collapsed.':''}`:'';
    if(firstView&&data.size){pan={x:width/2,y:18};firstView=false;}
    if(follow&&!archive)keepSelectedVisible();dirty=true;
    inspectNode(false);
  }
  function fit(){follow=false;zoom=Math.min(1,(width-50)/Math.max(100,bounds.right-bounds.left),(height-70)/Math.max(150,bounds.bottom));
    pan={x:width/2-(bounds.left+bounds.right)/2*zoom,y:20};inspectNode();dirty=true;
  }
  function keepSelectedVisible(){const p=positions.get(selected);if(!p)return;const x=p.x*zoom+pan.x,y=p.y*zoom+pan.y;
    if(x<card.width*zoom||x>width-card.width*zoom)pan.x=width/2-p.x*zoom;
    if(y-card.height*zoom/2<8||y+card.height*zoom/2>height-45)pan.y=height*.58-p.y*zoom;
  }
  function focus(id=selected){const p=positions.get(id);if(!p)return;zoom=Math.max(.75,zoom);pan={x:width/2-p.x*zoom,y:id===0?18:height*.55-p.y*zoom};dirty=true;
  }
  function inspectNode(sync=true){const n=currentNodes().get(selected),input=el('tree-node'),board=el('tree-board'),error=el('tree-node-error');
    const invalid=selected!==null&&!n,message=invalid?(Number.isSafeInteger(selected)&&selected>=0?`Node ${selected} is not in this tree.`:'Enter a whole-number node ID (0 or higher).'):'';
    if(error.textContent!==message)error.textContent=message;error.hidden=!message;input.setAttribute('aria-invalid',String(invalid));
    el('tree-follow').classList.toggle('active',follow&&!archive);if(sync)dirty=true;
    board.replaceChildren();
    if(!n){el('tree-node-stats').textContent=invalid?'':'Select a board to inspect its node.';el('tree-branch').disabled=true;el('tree-branch').textContent='Collapse children';return;}
    input.value=n.id;board.style.setProperty('--size',n.board.length);
    for(const row of n.board)for(const cell of row){const e=document.createElement('i');e.className=cell===1?'black':cell===-1?'white':'';board.append(e);}
    const player=n.player===1?'Black':'White',mean=n.visits?Number(n.value_sum)/n.visits:null;
    el('tree-node-stats').textContent=`${n.visits.toLocaleString()} visits · ${n.children} children · ${player} value sum ${Number(n.value_sum).toFixed(3)} (${player} to play) · Black value ${mean===null?'unvisited':(n.player===1?mean:1-mean).toFixed(4)}`;
    el('tree-branch').disabled=!n.children;el('tree-branch').textContent=collapsed.has(n.id)?`Show ${n.children} children`:'Collapse children';
  }
  function setSelected(id,center=false){selected=id;follow=false;if(!currentNodes().has(id)){inspectNode();return;}
    let parent=currentNodes().get(id).parent,changed=false;while(currentNodes().has(parent)){changed=collapsed.delete(parent)||changed;parent=currentNodes().get(parent).parent;}if(changed)layout();if(center)focus(id);inspectNode();}
  function drawBoard(n,p,active){const left=p.x-card.width/2,top=p.y-card.height/2;
    ctx.fillStyle=active?'#e8f6f0':'#fff';ctx.fillRect(left,top,card.width,card.height);
    ctx.strokeStyle=n.id===selected?'#153e5b':active?'#249c8a':n.visits?'#6c93c1':'#c8d5df';ctx.lineWidth=n.id===selected?2:1;ctx.strokeRect(left,top,card.width,card.height);
    const bx=p.x-card.board/2,by=top+20,size=n.board.length,pad=5,step=(card.board-2*pad)/Math.max(1,size-1);
    ctx.fillStyle='#f2e7d0';ctx.fillRect(bx,by,card.board,card.board);ctx.strokeStyle='#b8a582';ctx.lineWidth=.6;ctx.beginPath();
    for(let i=0;i<size;i++){const d=pad+i*step;ctx.moveTo(bx+pad,by+d);ctx.lineTo(bx+card.board-pad,by+d);ctx.moveTo(bx+d,by+pad);ctx.lineTo(bx+d,by+card.board-pad);}ctx.stroke();
    for(let row=0;row<size;row++)for(let col=0;col<size;col++){const value=n.board[row][col];if(!value)continue;const x=bx+pad+col*step,y=by+pad+row*step;ctx.beginPath();ctx.arc(x,y,Math.min(9,step*.4),0,2*Math.PI);ctx.fillStyle=value===1?'#203147':'#ffffff';ctx.fill();ctx.strokeStyle=value===1?'#203147':'#ad9c7e';ctx.lineWidth=.65;ctx.stroke();
      if(n.move&&n.move[0]===row&&n.move[1]===col){ctx.beginPath();ctx.arc(x,y,Math.min(3,step*.13),0,2*Math.PI);ctx.fillStyle=value===1?'#83ddc5':'#1d977c';ctx.fill();}}
    if(zoom>.26){ctx.fillStyle='#506b80';ctx.font='10px -apple-system, sans-serif';ctx.textAlign='left';ctx.fillText('#'+n.id,left+6,top+13);ctx.textAlign='center';ctx.fillStyle='#29445a';ctx.fillText(n.visits.toLocaleString()+' visits',p.x,top+111);ctx.fillStyle='#657d8e';ctx.font='9px -apple-system, sans-serif';ctx.fillText((n.player===1?'Black':'White')+' sum '+Number(n.value_sum).toFixed(2),p.x,top+125);}
  }
  function draw(){
    if(dirty&&ctx){dirty=false;painted=[];ctx.clearRect(0,0,width,height);ctx.save();ctx.translate(pan.x,pan.y);ctx.scale(zoom,zoom);
      const data=currentNodes(),active=new Set(archive?.path||path);
      for(const [id,p] of positions){const n=data.get(id),parent=positions.get(n.parent);if(!parent)continue;
        const top=parent.y+card.height/2,bottom=p.y-card.height/2;
        if(bottom*zoom+pan.y<0||top*zoom+pan.y>height||Math.max(parent.x,p.x)*zoom+pan.x<0||Math.min(parent.x,p.x)*zoom+pan.x>width)continue;
        ctx.strokeStyle=active.has(id)&&active.has(n.parent)?'#249c8a':'#c7d4df';ctx.lineWidth=(active.has(id)?2:1)/zoom;ctx.beginPath();ctx.moveTo(parent.x,top);ctx.bezierCurveTo(parent.x,(top+bottom)/2,p.x,(top+bottom)/2,p.x,bottom);ctx.stroke();
      }
      for(const [id,p] of positions){if((p.x+card.width/2)*zoom+pan.x<0||(p.x-card.width/2)*zoom+pan.x>width||(p.y+card.height/2)*zoom+pan.y<0||(p.y-card.height/2)*zoom+pan.y>height)continue;
        drawBoard(data.get(id),p,active.has(id));painted.push(id);
      }ctx.restore();
    }requestAnimationFrame(draw);
  }
  function initTree(){canvas=el('tree-canvas');ctx=canvas.getContext('2d');
    new ResizeObserver(()=>{const previous=width;width=canvas.clientWidth;height=canvas.clientHeight;const d=devicePixelRatio||1;canvas.width=width*d;canvas.height=height*d;ctx.setTransform(d,0,0,d,0,0);pan.x+=(width-previous)/2;if(follow)keepSelectedVisible();dirty=true;}).observe(canvas);
    canvas.onpointerdown=e=>{canvas.setPointerCapture(e.pointerId);drag={x:e.clientX,y:e.clientY,px:pan.x,py:pan.y,moved:false};};
    canvas.onpointermove=e=>{if(drag){const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>4){drag.moved=true;follow=false;el('tree-follow').classList.remove('active');}pan={x:drag.px+dx,y:drag.py+dy};dirty=true;}};
    canvas.onpointerup=e=>{if(drag&&!drag.moved){const rect=canvas.getBoundingClientRect(),x=(e.clientX-rect.left-pan.x)/zoom,y=(e.clientY-rect.top-pan.y)/zoom;let nearest=null,distance=Infinity;
      for(const [id,p] of positions){if(Math.abs(p.x-x)>card.width/2||Math.abs(p.y-y)>card.height/2)continue;const d=Math.hypot(p.x-x,p.y-y);if(d<distance){distance=d;nearest=id;}}if(nearest!==null)setSelected(nearest);}drag=null;};
    canvas.onwheel=e=>{e.preventDefault();const rect=canvas.getBoundingClientRect();scale(Math.exp(-e.deltaY*.0015),e.clientX-rect.left,e.clientY-rect.top);};
    el('tree-plus').onclick=()=>scale(1.3);el('tree-minus').onclick=()=>scale(1/1.3);el('tree-fit').onclick=fit;
    el('tree-inspect').onclick=()=>setSelected(el('tree-node').valueAsNumber,true);
    el('tree-branch').onclick=()=>{follow=false;if(collapsed.has(selected))collapsed.delete(selected);else collapsed.add(selected);layout();};
    el('tree-all').onclick=()=>{collapsed.clear();layout();};
    el('tree-root').onclick=()=>{selected=0;follow=false;focus(0);inspectNode();};
    el('tree-follow').onclick=()=>{archive=null;el('tree-history').value='live';follow=true;selected=path.at(-1)??0;for(const id of path)collapsed.delete(id);layout();focus();};
    el('expand-tree').onclick=()=>{const large=el('tree-panel').classList.toggle('maximized');el('expand-tree').textContent=large?'Close large view':'Enlarge';};
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){el('tree-panel').classList.remove('maximized');el('expand-tree').textContent='Enlarge';}});
    draw();
  }
  function scale(factor,x=width/2,y=height/2){const next=Math.max(.0001,Math.min(3,zoom*factor)),ratio=next/zoom;pan={x:x+(pan.x-x)*ratio,y:y+(pan.y-y)*ratio};zoom=next;follow=false;inspectNode();dirty=true;}
  function showArchive(data){archive={nodes:new Map(data.nodes.map(n=>[n.id,n])),path:data.path||[]};selected=0;follow=false;collapsed.clear();layout();focus(0);el('tree-caption').textContent=`Reviewing move ${data.move} · ${data.nodes.length.toLocaleString()} nodes`;}
  return {init(){chip();initTree();},activity,update,reset,showArchive,architecture,parts(){return blocks;},
    live(){archive=null;follow=true;selected=path.at(-1)??0;collapsed.clear();layout();focus();el('tree-caption').textContent=`Current search · ${nodes.size.toLocaleString()} nodes`;},
    query(){return `&tree_after=${revision}&tree_key=${encodeURIComponent(key||'')}`;},
    node(){return currentNodes().get(selected);},debug(){return {nodes:[...nodes.values()],key,revision,path,displayed:positions.size,painted,selected,zoom,card,collapsed:[...collapsed],points:[...positions].map(([id,p])=>({id,x:p.x*zoom+pan.x,y:p.y*zoom+pan.y}))};}};
})();

/* Cycle intervals from the simulator, with a shared neural service template. */
/* SPDX-License-Identifier: MIT */
const PipelineView = (() => {
  const el=id=>document.getElementById(id), number=n=>Math.round(n).toLocaleString();
  const groups=[
    ['selection','Selection','#3469bc',['selector','cam','candidates','ucb']],
    ['expansion','Expansion','#a5752e',['update','allocator','choice']],
    ['neural','Rollout','#218d83',['sequencer','drivers','arrays','column_hold','mux','sample_hold','adc','readout','accumulator','correction','activation','output','divider']],
    ['backpropagation','Backprop','#7964ad',['backprop','stats','codec']],
    ['fsm','FSM','#62758a',['glue','counter','handshake']],
    ['memory','Shared memory','#457789',['node_router','child_router','node_sram','child_sram','path']],
  ];
  const resources={selection_loader:'candidates',score_controller:'selector',ucb_bank:'ucb',shift_add_lanes:'accumulator',offset_alu:'correction',cam:'cam',compute:'ucb',controller:'glue',neural_controller:'sequencer',
    node_sram:'node_sram',child_sram:'child_sram',binary_drivers:'drivers',array:'arrays',
    column_hold:'column_hold',column_mux:'mux',sample_hold:'sample_hold',adc_bank:'adc',
    readout_bus:'readout',shift_add_lane:'accumulator',accumulator_registers:'accumulator',
    activation_lane:'activation',scale_lane:'output',output_alu:'output',divider:'divider'};
  const included={selector:'Selection',update:'Expansion',allocator:'Expansion',choice:'Expansion',
    backprop:'Backprop',stats:'Backprop',codec:'Backprop',glue:'stage control',handshake:'FSM',
    node_router:'SRAM service',child_router:'SRAM service',path:'Node SRAM'};
  const rowHeight=32,axis=44,pad=12;
  let canvas,ctx,width=0,rows=[],parts={},opened=new Set(),phases=[],key=null,revision=0;
  let program=null,snapshot={},status='ready',mode='live',follow=true,left=0,span=1,drag=null,hits=[],painted=0;
  const currentIteration=()=>phases.at(-1)?.iteration||1;
  const shown=()=>mode==='recent'?phases:phases.filter(p=>p.iteration===(mode==='live'?currentIteration():Number(mode)));
  const bounds=()=>{const list=shown();return [list[0]?.start||0,list.at(-1)?.end||1];};
  const pretty=s=>s.replaceAll('_',' ');
  const phaseName=p=>groups.find(g=>g[0]===p)?.[1]||(p==='iteration_commit'?'FSM finish':pretty(p));

  function followState(){el('pipeline-follow').classList.toggle('active',follow);el('pipeline-follow').setAttribute('aria-pressed',String(follow));}
  function pin(){follow=false;if(mode==='live'&&phases.length)mode=String(currentIteration());el('pipeline-iteration').value=mode;followState();}
  function fit(){const [start,end]=bounds();left=start;span=Math.max(1,end-start);draw();}
  function limits(){const [start,end]=bounds();span=Math.max(4,Math.min(span,Math.max(4,end-start)));left=Math.max(start,Math.min(left,end-span));}
  function zoom(factor,x=width/2){pin();const ratio=Math.max(0,Math.min(1,(x-pad)/Math.max(1,width-2*pad))),at=left+span*ratio;span/=factor;left=at-span*ratio;limits();draw();}

  function labels(){
    rows=[];const list=el('pipeline-labels');list.replaceChildren();
    const title=document.createElement('div');title.className='pipeline-axis-label';title.textContent='Blocks / parts';list.append(title);
    for(const [id,name,color,children] of groups){
      rows.push({id,name,color,group:id,header:true});
      const button=document.createElement('button');button.className='pipeline-group-label';button.dataset.group=id;
      button.setAttribute('aria-expanded',String(opened.has(id)));button.style.setProperty('--group-color',color);
      button.textContent=(opened.has(id)?'▾ ':'▸ ')+name;button.onclick=()=>{opened.has(id)?opened.delete(id):opened.add(id);labels();draw();};list.append(button);
      if(!opened.has(id))continue;
      for(const child of children){
        const name=parts[child][4];rows.push({id:child,name,color,group:id,header:false});
        const b=document.createElement('button');b.className='pipeline-part-label';b.textContent=name;b.title=parts[child][5];b.dataset.part=child;
        b.onclick=()=>{el('pipeline-inspector').textContent=name+': '+parts[child][5]+' Parts: '+parts[child][6].join(', ')+'.';};list.append(b);
      }
    }
    el('pipeline-parts').textContent=opened.size===6?'Hide parts':'Show parts';
    el('pipeline-parts').setAttribute('aria-expanded',String(opened.size===6));
    canvas.style.height=(axis+rows.length*rowHeight)+'px';
    resize();
  }

  function resize(){
    width=canvas.clientWidth;const d=window.devicePixelRatio||1,height=axis+rows.length*rowHeight;
    canvas.width=Math.round(width*d);canvas.height=Math.round(height*d);ctx.setTransform(d,0,0,d,0,0);draw();
  }

  function draw(){
    if(!ctx||width<1)return;
    const height=axis+rows.length*rowHeight,plotWidth=Math.max(1,width-2*pad),x=c=>pad+(c-left)/span*plotWidth;
    ctx.clearRect(0,0,width,height);hits=[];painted=0;
    const rowIndex=new Map(rows.map((r,i)=>[r.id,i]));
    rows.forEach((row,i)=>{ctx.fillStyle=row.header?'#f3f6f9':i%2?'#ffffff':'#fbfcfd';ctx.fillRect(0,axis+i*rowHeight,width,rowHeight);ctx.strokeStyle='#e4eaf0';ctx.beginPath();ctx.moveTo(0,axis+(i+1)*rowHeight);ctx.lineTo(width,axis+(i+1)*rowHeight);ctx.stroke();});
    const target=span/Math.max(2,Math.floor(width/100)),base=10**Math.floor(Math.log10(Math.max(1,target)));
    const step=([1,2,5,10].find(n=>n*base>=target)||10)*base;
    ctx.font='11px system-ui';ctx.fillStyle='#62758a';ctx.textAlign='left';ctx.fillText('Cycles',pad,13);
    for(let cycle=Math.ceil(left/step)*step;cycle<=left+span;cycle+=step){
      const xx=x(cycle);ctx.strokeStyle='#dfe6ec';ctx.beginPath();ctx.moveTo(xx,axis-6);ctx.lineTo(xx,height);ctx.stroke();
      ctx.textAlign=xx>width-45?'right':xx<45?'left':'center';ctx.fillStyle='#62758a';ctx.fillText(number(cycle),xx,31);
    }
    ctx.textAlign='left';
    const active=snapshot.activity?.[snapshot.activity_index];
    const timed=new Set(),list=shown();
    function bar(rowId,start,end,label,kind,phase,resource,operation,stage){
      const index=rowIndex.get(rowId);if(index===undefined||end<=start)return;
      timed.add(rowId);if(end<left||start>left+span)return;
      const row=rows[index],xx=Math.max(pad,x(start)),right=Math.min(width-pad,x(end)),ww=right-xx;
      if(ww<=0)return;
      const yy=axis+index*rowHeight+7,hh=18;
      const selected=['running','paused'].includes(status)&&phase.iteration===currentIteration()&&phase.phase===snapshot.event?.phase&&active&&active.resource===resource&&active.operation===operation&&active.stage===stage;
      ctx.globalAlpha=kind==='phase'?.18:Math.min(1,ww/.8);ctx.fillStyle=kind==='gap'?'#62758a':row.color;ctx.fillRect(xx,yy,Math.max(.8,ww),hh);ctx.globalAlpha=1;
      if(kind==='phase'||selected){ctx.strokeStyle=row.color;ctx.lineWidth=selected?2:1;ctx.strokeRect(xx+.5,yy+.5,Math.max(0,ww-1),hh-1);ctx.lineWidth=1;}
      if(kind==='gap'){
        ctx.save();ctx.beginPath();ctx.rect(xx,yy,ww,hh);ctx.clip();ctx.strokeStyle='#ffffffa0';
        for(let stripe=xx-hh;stripe<right;stripe+=7){ctx.beginPath();ctx.moveTo(stripe,yy+hh);ctx.lineTo(stripe+hh,yy);ctx.stroke();}ctx.restore();
      }
      if(ww>80){ctx.save();ctx.beginPath();ctx.rect(xx+3,yy,ww-6,hh);ctx.clip();ctx.fillStyle=kind==='phase'?row.color:'#fff';ctx.font='11px system-ui';ctx.fillText(label,xx+6,yy+13);ctx.restore();}
      hits.push({row:rowId,index,start,end,label,kind,iteration:phase.iteration,stage,resource,operation});painted++;
    }
    for(const phase of list){
      if(phase.end<left||phase.start>left+span)continue;
      if(phase.phase!=='iteration_commit')bar(phase.phase,phase.start,phase.end,phaseName(phase.phase),'phase',phase);
      const service=(record,offset=0)=>{
        const [resource,operation,a,b,stage]=record,start=a+offset,end=b+offset;
        const id=resource==='controller'&&phase.phase!=='iteration_commit'?({selection:'selector',expansion:'update',neural:'sequencer',backpropagation:'backprop'}[phase.phase]||'glue'):resources[resource];
        const kind=operation==='aggregated_control_and_compute'?'gap':'service',label=pretty(operation);
        // Aggregated phase control is not separately attributed to the global
        // FSM, selector, updater or neural sequencer in the source trace.
        if(kind==='gap'){bar(phase.phase,start,end,'Control',kind,phase,resource,operation,stage);return;}
        bar(id,start,end,label,kind,phase,resource,operation,stage);
        if(resource==='node_sram'||resource==='child_sram')bar('memory',start,end,resource==='node_sram'?'Node SRAM':'Child SRAM','service',phase,resource,operation,stage);
        if(resource==='controller'&&phase.phase==='iteration_commit')bar('fsm',start,end,'Finish',kind,phase,resource,operation,stage);
        if(operation==='iteration_finish')bar('counter',start,end,'Finish','service',phase,resource,operation,stage);
      };
      for(const record of phase.services)service(record);
      if(phase.phase==='neural'&&program?.key===snapshot.program_key&&program.pipeline)
        for(const record of program.pipeline.services)service(record,phase.start);
    }
    rows.forEach((row,i)=>{
      if(row.header||timed.has(row.id))return;
      let note=included[row.id]?'Included in '+included[row.id]:'No scheduled work here';
      if(row.id==='sequencer'&&!program?.pipeline?.services.some(r=>r[0]==='neural_controller'))note='Included in Rollout';
      if(row.id==='column_hold'&&program?.profile?.readout?.profile!=='column_hold_v1')note='Not installed';
      ctx.fillStyle='#81909f';ctx.font='10px system-ui';ctx.fillText(note,pad,axis+i*rowHeight+20);
    });
    if(!phases.length){ctx.fillStyle='#62758a';ctx.font='12px system-ui';ctx.fillText('Waiting for a computer search',pad,axis+20);}
    const end=phases.at(-1)?.end;
    if(end!==undefined&&end>=left&&end<=left+span){
      const xx=x(end);ctx.setLineDash([4,4]);ctx.strokeStyle='#172d46';ctx.beginPath();ctx.moveTo(xx,axis-6);ctx.lineTo(xx,height);ctx.stroke();ctx.setLineDash([]);
    }
  }

  function update(data,s={},nextStatus='ready'){
    snapshot=s;status=nextStatus;
    if(!data){draw();return;}
    const changed=data.key!==key||data.revision!==revision;
    if(data.key!==key){mode='live';follow=true;left=0;span=1;el('pipeline-inspector').textContent='Choose a bar to see its cycles and operation.';}
    key=data.key;revision=data.revision;
    if(data.phases!==null)phases=data.phases;
    const iterations=[...new Set(phases.map(p=>p.iteration))];
    if(mode!=='live'&&mode!=='recent'&&!iterations.includes(Number(mode))){mode='live';follow=true;}
    const select=el('pipeline-iteration');
    if(changed){
      select.replaceChildren(new Option('Follow latest iteration','live'),new Option('Recent iterations','recent'));
      for(const i of [...iterations].reverse())select.add(new Option('Iteration '+number(i),String(i)));
    }
    select.value=mode;followState();
    const list=shown(),play=s.play,move=play?'Move '+(play.moves?.find(m=>m.search_run===key)?.move||play.current_move)+' · ':'';
    el('pipeline-caption').textContent=phases.length?move+(mode==='recent'?'Iterations '+iterations[0]+'–'+iterations.at(-1):'Iteration '+(mode==='live'?currentIteration():mode))+' · '+number(list[0]?.start||0)+' to '+number(list.at(-1)?.end||0)+' cycles'+(status==='paused'?' · Paused':''):'Start a move to see when each part works.';
    if(follow&&changed)fit();else draw();
  }

  function init(){
    canvas=el('pipeline-canvas');ctx=canvas.getContext('2d');parts=StudioViews.parts();labels();
    new ResizeObserver(resize).observe(canvas);
    el('pipeline-iteration').onchange=()=>{mode=el('pipeline-iteration').value;follow=mode==='live';followState();fit();update({key,revision,phases:null},snapshot,status);};
    el('pipeline-parts').onclick=()=>{opened=opened.size===6?new Set():new Set(groups.map(g=>g[0]));labels();};
    el('pipeline-fit').onclick=fit;el('pipeline-plus').onclick=()=>zoom(2);el('pipeline-minus').onclick=()=>zoom(.5);
    el('pipeline-follow').onclick=()=>{mode='live';follow=true;followState();fit();update({key,revision,phases:null},snapshot,status);};
    el('expand-pipeline').onclick=()=>{const large=el('pipeline-panel').classList.toggle('maximized');el('expand-pipeline').textContent=large?'Close large view':'Enlarge';};
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){el('pipeline-panel').classList.remove('maximized');el('expand-pipeline').textContent='Enlarge';}});
    canvas.onwheel=e=>{e.preventDefault();zoom(Math.exp(-e.deltaY*.002),e.clientX-canvas.getBoundingClientRect().left);};
    canvas.onpointerdown=e=>{canvas.setPointerCapture(e.pointerId);drag={x:e.clientX,left,moved:false};};
    canvas.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag.x;if(Math.abs(dx)>4){drag.moved=true;pin();left=drag.left-dx/Math.max(1,width-2*pad)*span;limits();draw();}};
    canvas.onpointerup=e=>{
      if(drag&&!drag.moved){
        const rect=canvas.getBoundingClientRect(),index=Math.floor((e.clientY-rect.top-axis)/rowHeight),cycle=left+(e.clientX-rect.left-pad)/Math.max(1,width-2*pad)*span;
        const hit=hits.findLast(b=>b.index===index&&cycle>=b.start&&cycle<b.end);
        if(hit)el('pipeline-inspector').textContent=rows[index].name+' · '+hit.label+' · cycles '+number(hit.start)+'–'+number(hit.end)+' ('+number(hit.end-hit.start)+' cycles) · iteration '+hit.iteration+(hit.stage&&hit.stage!==phases.find(p=>p.iteration===hit.iteration&&p.start<=hit.start&&p.end>=hit.end)?.phase?' · '+pretty(hit.stage):'')+(hit.kind==='gap'?' · Grouped at stage end; exact RTL position is unresolved.':'');
      }
      drag=null;
    };
    canvas.onpointercancel=()=>{drag=null;};
    canvas.onkeydown=e=>{
      if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();pin();left+=span*.2*(e.key==='ArrowLeft'?-1:1);limits();draw();}
      else if(['+','=','-'].includes(e.key)){e.preventDefault();zoom(e.key==='-'?.5:2);}
    };
  }
  function reset(){
    phases=[];key=null;revision=0;program=null;snapshot={};status='ready';mode='live';follow=true;left=0;span=1;
    el('pipeline-iteration').replaceChildren(new Option('Follow latest iteration','live'));followState();
    el('pipeline-caption').textContent='Start a move to see when each part works.';el('pipeline-inspector').textContent='Choose a bar to see its cycles and operation.';draw();
  }
  return {init,update,reset,program(p){program=p;draw();},
    query(){return '&pipeline_after='+revision+'&pipeline_key='+encodeURIComponent(key||'');},
    debug(){return {key,revision,mode,follow,left,span,phases,rows,painted,hits,width,axis,rowHeight};}};
})();

/* Pies use only counted ledger parents and exclusive phase-cycle totals. */
const CostCharts = (() => {
  const ns='http://www.w3.org/2000/svg',cards={};
  const colors={selection:'#3f70b6',expansion:'#ce8735',rollout:'#278c81',backprop:'#8665af',fsm:'#6c7f96',memory:'#b76b58',overhead:'#979eaa',other:'#6f7078'};
  const groups=[
    {id:'selection',name:'Selection',owners:['u_sel','u_ucb','cam_macro']},
    {id:'expansion',name:'Expansion + Backprop',owners:['u_upd']},
    {id:'rollout',name:'Rollout',owners:['u_nn','cim_arrays','row_drivers','sample_hold','adc_lanes','analog_mux','column_hold']},
    {id:'fsm',name:'FSM',owners:['top_level_glue']},
    {id:'memory',name:'Shared memory',owners:['node_sram','child_sram','u_node_router','u_child_router']},
    {id:'overhead',name:'Physical allowance',owners:['physical_overhead']},
    {id:'other',name:'Other parts',owners:[]}
  ];
  const stages=[{id:'selection',name:'Selection'},{id:'expansion',name:'Expansion'},
    {id:'rollout',name:'Rollout'},{id:'backprop',name:'Backprop'},
    {id:'fsm',name:'FSM finish'},{id:'other',name:'Other stages'}];
  const phaseGroup={selection:'selection',expansion:'expansion',neural:'rollout',backpropagation:'backprop',iteration_commit:'fsm'};
  const finite=n=>typeof n==='number'&&Number.isFinite(n)&&n>=0;
  const number=n=>n.toLocaleString('en-US',{maximumFractionDigits:n>=100?1:n>=1?3:4});
  const percent=n=>n>0&&n<.1?'<0.1%':n.toLocaleString('en-US',{maximumFractionDigits:1})+'%';
  const element=(tag,className,text)=>{const node=document.createElement(tag);if(className)node.className=className;if(text!=null)node.textContent=text;return node;};
  const svg=(tag,attrs={})=>{const node=document.createElementNS(ns,tag);for(const [key,value] of Object.entries(attrs))node.setAttribute(key,value);return node;};

  function summarize(data,costs,timing) {
    const parts=(costs?.ledger?.components || data?.components || []).filter(p=>p.counted!==false&&p.scope!=='outside_core');
    const result={};
    for(const [id,field,scale,unit] of [['area','area_um2',1e6,'mm²'],['energy','energy_uj',1,'µJ'],['power','average_power_mw',1,'mW']]) {
      const ready=id==='area'?parts.length>0:!!costs?.ledger&&costs.sram?.latency_us>0;
      const rows=groups.map(group=>({...group,value:0,missing:[]}));
      if(ready) for(const part of parts) {
        const group=rows.find(row=>row.owners.includes(part.id || part.instance)) || rows.at(-1);
        let value=part[field];
        if(id==='power'&&value==null&&finite(part.energy_uj))value=part.energy_uj*1000/costs.sram.latency_us;
        if(finite(value))group.value+=value/scale;
        else group.missing.push(part.component);
      }
      result[id]={id,rows,ready,unit,total:rows.reduce((sum,row)=>sum+row.value,0),missing:rows.flatMap(row=>row.missing)};
    }
    const rows=stages.map(row=>({...row,value:0,missing:[]}));
    for(const [phase,cycles] of Object.entries(timing?.phases || {})) {
      if(finite(cycles))rows.find(row=>row.id===(phaseGroup[phase] || 'other')).value+=cycles/500;
    }
    const total=rows.reduce((sum,row)=>sum+row.value,0),elapsed=finite(timing?.cycles)?timing.cycles/500:0;
    result.latency={id:'latency',rows,ready:total>0,unit:'µs',total,missing:[],
      incomplete:Math.abs(total-elapsed)>1e-9};
    return result;
  }

  function create(id,title) {
    const root=element('article','pie-card');root.id='pie-'+id;root.dataset.metric=id;
    const header=element('div','pie-heading'),heading=element('h3','',title),badge=element('span','pie-badge');
    header.append(heading,badge);
    const drawing=element('div','pie-drawing'),chart=svg('svg',{viewBox:'0 0 160 160',role:'group','aria-label':title+' breakdown'});
    chart.append(svg('circle',{cx:80,cy:80,r:58,fill:'none',stroke:'#e8edf2','stroke-width':22}));
    const center=element('div','pie-center'),value=element('strong'),unit=element('small');center.append(value,unit);
    drawing.append(chart,center);
    const legend=element('ul','pie-legend'),foot=element('p','pie-coverage'),empty=element('p','pie-empty');
    const nodes={};
    const highlight=key=>{for(const [name,row] of Object.entries(nodes)){row.circle.style.opacity=key&&key!==name?'.25':'1';row.button.classList.toggle('highlighted',key===name);}};
    for(const group of id==='latency'?stages:groups) {
      const circle=svg('circle',{cx:80,cy:80,r:58,fill:'none',stroke:colors[group.id],'stroke-width':22,
        pathLength:100,transform:'rotate(-90 80 80)',tabindex:0,role:'img','data-group':group.id});
      const tooltip=svg('title');circle.append(tooltip);chart.append(circle);
      const item=element('li'),button=element('button','pie-key');button.type='button';button.dataset.group=group.id;
      const swatch=element('i','pie-swatch');swatch.style.background=colors[group.id];swatch.setAttribute('aria-hidden','true');
      const label=element('span','pie-name',group.name),quantity=element('small','pie-quantity'),share=element('b','pie-percent');
      label.append(quantity);button.append(swatch,label,share);item.append(button);legend.append(item);
      for(const node of [circle,button]) {
        node.addEventListener('mouseenter',()=>highlight(group.id));node.addEventListener('mouseleave',()=>highlight(null));
        node.addEventListener('focus',()=>highlight(group.id));node.addEventListener('blur',()=>highlight(null));
      }
      nodes[group.id]={circle,tooltip,item,button,quantity,share};
    }
    root.append(header,drawing,empty,legend,foot);document.getElementById('pie-grid').append(root);
    return {root,badge,value,unit,foot,empty,nodes};
  }

  function render(data,costs,timing,context={}) {
    document.getElementById('breakdown-configuration').textContent=context.configuration || '';
    document.getElementById('breakdown-status').textContent=context.unavailable?'Not available yet':context.status;
    const summaries=summarize(data,costs,timing);
    for(const [id,title] of [['area','Area'],['energy','Energy'],['power','Power'],['latency','Latency']]) {
      const card=cards[id] || (cards[id]=create(id,title)),summary=summaries[id];
      const ready=summary.ready&&!context.unavailable,divisor=id==='latency'&&summary.total>=1000?1000:1;
      const unit=divisor===1000?'ms':summary.unit;
      card.root.dataset.total=ready?String(summary.total):'';card.root.dataset.unit=summary.unit;
      card.root.dataset.missing=summary.missing.length;card.root.dataset.ready=String(ready);
      card.value.textContent=ready?number(summary.total/divisor):context.unavailable?'Unavailable':'Waiting';
      card.unit.textContent=ready?(id==='power'?'mW average':unit):id==='area'?'for estimate':'for activity';
      card.badge.textContent=!ready?'':summary.missing.length?'Partial':id==='latency'?'Simulated':'Estimate';
      card.badge.classList.toggle('partial',summary.missing.length>0);
      card.empty.hidden=ready;
      card.empty.textContent=context.unavailable || (id==='area'?'Loading this configuration.':'Updates when a search runs.');
      card.foot.textContent=!ready?'':summary.missing.length?`${summary.missing.length} part${summary.missing.length===1?'':'s'} not estimated. Percentages use known costs.`:
        id==='latency'?(summary.incomplete?'Stage breakdown is incomplete.':'Memory time is included in each stage.'):
        id==='area'?'Installed area stays fixed during a run.':id==='energy'?'Energy accumulated so far.':'Average over the same simulated time.';
      card.foot.title=summary.missing.join('; ');
      let offset=0;
      for(const row of summary.rows) {
        const node=card.nodes[row.id],share=ready&&summary.total>0?100*row.value/summary.total:0;
        node.circle.style.display=ready&&row.value>0?'':'none';
        node.circle.setAttribute('stroke-dasharray',`${share} ${Math.max(0,100-share)}`);
        node.circle.setAttribute('stroke-dashoffset',-offset);offset+=share;
        node.item.hidden=!ready||(row.value===0&&!row.missing.length);
        node.item.dataset.value=row.value;node.item.dataset.share=share;
        node.quantity.textContent=row.value===0&&row.missing.length?'Not estimated':number(row.value/divisor)+' '+unit;
        node.share.textContent=row.value===0&&row.missing.length?'n/a':percent(share);
        const label=`${row.name}: ${number(row.value/divisor)} ${unit}, ${percent(share)}${row.missing.length?'; some parts not estimated':''}`;
        node.tooltip.textContent=label;node.circle.setAttribute('aria-label',label);node.button.setAttribute('aria-label',label);
        node.button.title=row.missing.length?'Not estimated: '+row.missing.join('; '):label;
      }
    }
  }
  return {render,summarize};
})();

/* Relative component footprints, sourced from the same inventory as the table. */
const AreaView = (() => {
  const el=id=>document.getElementById(id), ns='http://www.w3.org/2000/svg';
  const svg=(tag,attrs={},text)=>{const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;};
  const groups={
    rollout:['u_nn','cim_arrays','row_drivers','sample_hold','adc_lanes','analog_mux','column_hold'],
    readout:['sample_hold','adc_lanes','analog_mux','column_hold'],
    selection:['u_sel','u_ucb','cam_macro'],update:['u_upd'],fsm:['top_level_glue'],
    memory:['node_sram','child_sram','u_node_router','u_child_router'],
  };
  const names={cim_arrays:'CIM cell arrays',row_drivers:'Row drivers',analog_mux:'Column mux & references',sample_hold:'Sample / hold',adc_lanes:'ADC bank',column_hold:'Column holding bank',u_nn:'Neural digital logic',u_sel:'Selection control',u_ucb:'UCB scorer',u_upd:'Expansion + Backprop',cam_macro:'Parent CAM',top_level_glue:'FSM & interconnect',node_sram:'Node SRAM',child_sram:'Child SRAM',u_node_router:'Node router',u_child_router:'Child router',physical_overhead:'Physical allowance'};
  const owners={candidates:'u_sel',correction:'u_nn',selector:'u_sel',cam:'cam_macro',ucb:'u_ucb',update:'u_upd',allocator:'u_upd',choice:'u_upd',backprop:'u_upd',stats:'u_upd',codec:'u_upd',glue:'top_level_glue',counter:'top_level_glue',handshake:'top_level_glue',node_router:'u_node_router',child_router:'u_child_router',node_sram:'node_sram',child_sram:'child_sram',path:'node_sram',sequencer:'u_nn',drivers:'row_drivers',arrays:'cim_arrays',column_hold:'column_hold',mux:'analog_mux',sample_hold:'sample_hold',adc:'adc_lanes',readout:'u_nn',accumulator:'u_nn',activation:'u_nn',output:'u_nn',divider:'u_nn'};
  let parts=[],selected='cim_arrays',signature=null;
  const known=p=>typeof p.area_um2==='number'&&Number.isFinite(p.area_um2)&&p.area_um2>=0;
  const number=n=>n.toLocaleString(undefined,{maximumFractionDigits:3});
  const name=p=>names[p.id]||p.component;
  const section=p=>Object.keys(groups).find(key=>key!=='readout'&&groups[key].includes(p.id))||'other';
  function inventory(data,costs){return (costs?.ledger?.components||data?.components||[]).filter(p=>p.counted!==false&&p.scope!=='outside_core').map(p=>({...p,id:p.id||p.instance||p.component}));}

  // Recursive balanced cuts preserve area ratios, including very small parts.
  // There is no minimum footprint, logarithmic scaling or per-instance recount.
  function layout(rows,x=16,y=16,w=868,h=448){
    rows=rows.filter(p=>known(p)&&p.area_um2>0).slice().sort((a,b)=>b.area_um2-a.area_um2||a.id.localeCompare(b.id));
    if(!rows.length)return [];
    if(rows.length===1)return [{part:rows[0],x,y,w,h}];
    const total=rows.reduce((sum,p)=>sum+p.area_um2,0);let sum=0,cut=1,best=Infinity;
    for(let i=1;i<rows.length;i++){sum+=rows[i-1].area_um2;const error=Math.abs(total/2-sum);if(error<best){best=error;cut=i;}}
    const a=rows.slice(0,cut),b=rows.slice(cut),fraction=a.reduce((sum,p)=>sum+p.area_um2,0)/total;
    return w>=h?[...layout(a,x,y,w*fraction,h),...layout(b,x+w*fraction,y,w*(1-fraction),h)]:
      [...layout(a,x,y,w,h*fraction),...layout(b,x,y+h*fraction,w,h*(1-fraction))];
  }
  function pattern(defs,id,path,dots=false){const p=svg('pattern',{id,width:12,height:12,patternUnits:'userSpaceOnUse'});p.append(svg('path',{d:path,fill:'none',stroke:'#587988','stroke-width':.65,opacity:.5}));if(dots)p.append(svg('circle',{cx:6,cy:6,r:1.5,fill:'#527c73',opacity:.65}));defs.append(p);}
  function symbol(g,p,x,y,w,h){
    if(w<45||h<35)return;
    const cx=x+w/2,cy=y+h/2;
    if(['cim_arrays','node_sram','child_sram','cam_macro'].includes(p.id)){
      const count=p.id==='cam_macro'?1:Math.max(1,p.count||1),cols=count%2===0?2:1,rows=Math.ceil(count/cols);
      for(let i=0;i<count;i++){
        const bx=x+(i%cols)*w/cols,by=y+Math.floor(i/cols)*h/rows,bw=w/cols,bh=h/rows;
        g.append(svg('rect',{x:bx+5,y:by+5,width:Math.max(0,bw-10),height:Math.max(0,bh-10),fill:p.id==='cim_arrays'?'url(#unit-cells)':'url(#unit-grid)',class:'unit-symbol'}));
        if(p.id==='cim_arrays'&&bw>110&&bh>70){const first=p.children?.find(c=>c.id.endsWith('/layer_1'))?.count;const label=first==null?'Array '+(i+1):`L${i<first?1:2} · array ${i+1}`;g.append(svg('rect',{x:bx+8,y:by+8,width:86,height:18,fill:'#fffffff0'}),svg('text',{x:bx+13,y:by+21,class:'unit-symbol-label'},label));}
        if(i%cols)g.append(svg('path',{d:`M ${bx} ${by} v ${bh}`,class:'unit-bank-divider'}));
        if(i>=cols)g.append(svg('path',{d:`M ${bx} ${by} h ${bw}`,class:'unit-bank-divider'}));
      }
    }else if(p.id==='row_drivers'){
      const n=Math.min(12,Math.floor(w/22));
      for(let i=0;i<n;i++){const dx=x+(i+.5)*w/n;g.append(svg('path',{d:`M ${dx-5} ${y+12} h 10 v ${h-24} h -10 Z M ${dx-8} ${cy} h 16`,class:'unit-circuit'}));}
    }else if(['adc_lanes','sample_hold'].includes(p.id)){
      const n=Math.min(p.count||1,8),step=w/n;
      for(let i=0;i<n;i++){const dx=x+(i+.5)*step,r=Math.min(24,step*.3,h*.25);g.append(svg('path',{d:p.id==='adc_lanes'?`M ${dx-r} ${cy+r} L ${dx} ${cy-r} L ${dx+r} ${cy+r} Z`:`M ${dx-5} ${cy-r} v ${2*r} M ${dx+5} ${cy-r} v ${2*r} M ${dx-r} ${cy} H ${dx-5} M ${dx+5} ${cy} H ${dx+r}`,class:'unit-circuit'}));}
    }else if(['analog_mux','column_hold'].includes(p.id)){
      const r=Math.min(w*.3,100),d=Math.min(h*.25,30);
      g.append(svg('path',{d:`M ${cx-r} ${cy-d} H ${cx+r} L ${cx+r*.6} ${cy+d} H ${cx-r*.6} Z M ${cx} ${cy+d} V ${y+h-8}`,class:'unit-circuit'}));
    }else if(p.id==='physical_overhead'){
      g.append(svg('rect',{x,y,width:w,height:h,fill:'url(#unit-hatch)',class:'unit-symbol'}));
    }else{
      const labels=p.id==='u_nn'?['Seq.','Acc.','Scale','Divide']:p.id==='u_ucb'?['Log','√','÷','Score']:p.id==='u_upd'?['Expand','Backprop']:p.id==='top_level_glue'?['FSM','Arbitrate']:['Control','Registers'];
      if(w>140&&h>110){const n=labels.length,step=(w-24)/n;
        labels.forEach((label,i)=>{const bx=x+12+i*step,by=y+h-52;g.append(svg('rect',{x:bx+2,y:by,width:step-7,height:32,class:'unit-circuit'}),svg('text',{x:bx+step/2-1,y:by+21,class:'unit-symbol-label','text-anchor':'middle'},label));if(i<n-1)g.append(svg('path',{d:`M ${bx+step-5} ${by+16} h 7`,class:'unit-wire'}));});
      }
    }
  }
  function select(id){selected=id;detail();document.querySelectorAll('[data-area-part]').forEach(n=>{const chosen=n.dataset.areaPart===id;n.classList.toggle('selected',chosen);n.setAttribute('aria-pressed',String(chosen));});}
  function detail(){
    const box=el('area-detail');box.replaceChildren();const p=parts.find(p=>p.id===selected);if(!p)return;
    const title=document.createElement('h4');title.textContent=name(p);box.append(title);
    const line=document.createElement('p');line.className='unit-facts';
    line.textContent=`${p.count==null?'Count unspecified':number(p.count)+' installed'} · ${known(p)?number(p.area_um2)+' µm² at 22 nm':'Area not estimated'}`;
    if(p.id==='cim_arrays')line.textContent+=` · ${p.rows} × ${p.columns} cells per array`;
    box.append(line);
    if(p.id==='cim_arrays'){
      const layers=document.createElement('p');layers.textContent=(p.children||[]).filter(c=>c.id.includes('/layer_')).map(c=>`${c.component}: ${c.count}`).join(' · ');box.append(layers);
    }
    const status=document.createElement('p');status.className='unit-source-status';status.textContent=!known(p)?'No compatible area estimate for this configuration.':p.id==='physical_overhead'?'Engineering allowance for clocks, wiring and layout spacing.':p.details?.native65_part?'Connected native65 synthesis area, scaled once to 22 nm. Disclosed residual control remains an engineering allocation.':p.report_proxy?'Controller estimate from an older synthesis report, with the stated allowance.':p.id==='cim_arrays'?'Cell area from the mentor workbook. Peripherals have their own footprints.':p.native_65nm_power?'Digital synthesis area, scaled from 65 nm to 22 nm.':['node_sram','child_sram'].includes(p.id)?'Native 22 nm CACTI estimate, including the bank peripherals.':'Analytical component estimate. Open Area source for its assumptions.';box.append(status);
    if(p.details?.native65_part){
      const native=p.details.native65_part,note=document.createElement('p');
      note.textContent=`Native65 connected portion: ${number(native.area_um2)} µm². ${native.ownership}. Power is a preliminary all-elapsed vectorless scenario; active and idle values are equal assumptions. Original packet acceptance and full-design equivalence remain unverified.`;box.append(note);
    }
    if(p.details?.residual_control_allocation){const note=document.createElement('p'),residual=p.details.residual_control_allocation;note.textContent=`Residual control allocation: ${number(residual.area_um2)} µm² at the target node. ${residual.basis}`;box.append(note);}
    if(p.children?.length){
      const heading=document.createElement('p');heading.textContent='Inside this component';heading.className='unit-inside-title';box.append(heading);
      const list=document.createElement('div');list.className='unit-internals';
      for(const child of p.children){const d=document.createElement('details'),summary=document.createElement('summary');summary.textContent=child.component;d.append(summary);
        const note=document.createElement('small');note.textContent=!known(p)?'Parent area is unestimated; excluded from the area map.':known(child)?`${number(child.area_um2)} µm², already within this parent.`:'Included in the parent; separate area unavailable.';d.append(note);
        if(child.children?.length){const ul=document.createElement('ul');for(const nested of child.children){const li=document.createElement('li');li.textContent=nested.component;ul.append(li);}d.append(ul);}list.append(d);
      }box.append(list);
    }
    if(p.source||p.status){const d=document.createElement('details'),s=document.createElement('summary'),basis=document.createElement('p'),source=document.createElement('code');d.className='unit-source';s.textContent='Area source';basis.textContent=[p.status,p.cost_model?.method].filter(Boolean).join(' ');source.textContent=p.source||'Source unavailable';d.append(s,basis,source);box.append(d);}
  }
  function draw(){
    const scope=el('area-scope').value,shown=scope==='whole'?parts:parts.filter(p=>groups[scope].includes(p.id));
    const total=shown.reduce((sum,p)=>sum+(known(p)?p.area_um2:0),0),whole=parts.reduce((sum,p)=>sum+(known(p)?p.area_um2:0),0);
    const map=el('area-map');map.replaceChildren();map.dataset.areaUm2=total;
    el('area-title').textContent=el('area-scope').selectedOptions[0].textContent;
    el('area-total').textContent=parts.length?number(total)+' µm²':'No estimate';
    el('area-context').textContent=!parts.length?'Choose a supported configuration to load its component areas.':scope==='whole'?`${number(whole/1e6)} mm² known core estimate, including the labeled physical allowance. Shared modules are counted once.`:`${number(whole?100*total/whole:0)}% of the known core area · enlarged to compare these parts. ${scope==='update'?'Both stages use one physical Tree update module.':''}`;
    if(total>0){
      const view=svg('svg',{viewBox:'0 0 900 480',role:'group','aria-label':'Area-proportional component footprints'}),defs=svg('defs');
      pattern(defs,'unit-grid','M 0 0 H 12 M 0 0 V 12');pattern(defs,'unit-cells','M 0 6 H 12 M 6 0 V 12',true);pattern(defs,'unit-hatch','M -3 3 L 3 -3 M 0 12 L 12 0 M 9 15 L 15 9');view.append(defs);
      for(const [i,tile] of layout(shown).entries()){
        const {part:p,x,y,w,h}=tile,label=name(p),clipId='area-clip-'+i;
        const clip=svg('clipPath',{id:clipId});clip.append(svg('rect',{x,y,width:w,height:h}));defs.append(clip);
        const g=svg('g',{class:'area-part '+section(p),role:'button',tabindex:0,'aria-label':`${label}, ${number(p.area_um2)} square micrometers, ${number(100*p.area_um2/total)} percent`,'data-area-part':p.id,'data-area-um2':p.area_um2,'data-pixel-area':w*h});
        g.append(svg('rect',{x,y,width:w,height:h,class:'unit-footprint'}));
        const interior=svg('g',{'clip-path':`url(#${clipId})`,'aria-hidden':'true'});symbol(interior,p,x,y,w,h);
        if(w>108&&h>54){
          const lines=label.length>22&&w<230?label.split(' & ').map((s,j)=>j?'& '+s:s):[label];
          const size=w<150?11:14,cy=y+h*.34,lh=size+5;
          const readable=lines.every(s=>s.length*size*.6<w-12);
          if(readable){const height=lines.length*lh+22;interior.append(svg('rect',{x:x+4,y:cy-lh,width:w-8,height,fill:'#fffffff0'}));lines.forEach((line,j)=>interior.append(svg('text',{x:x+w/2,y:cy+j*lh,'text-anchor':'middle',class:'unit-name','font-size':size},line)));interior.append(svg('text',{x:x+w/2,y:cy+lines.length*lh,'text-anchor':'middle',class:'unit-quantity'},p.id==='cim_arrays'?(p.rows?`${p.count} × ${p.rows} × ${p.columns}`:`${p.count} custom arrays`):p.count>1?`${number(p.count)} installed`:number(p.area_um2)+' µm²'));}
        }
        g.append(interior,svg('rect',{x:x+2,y:y+2,width:Math.max(0,w-4),height:Math.max(0,h-4),class:'unit-highlight'}),svg('title',{},`${label}: ${number(p.area_um2)} µm² (${number(100*p.area_um2/total)}% of this view). ${p.status||''}`));
        g.onclick=()=>select(p.id);g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(p.id);}};view.append(g);
      }map.append(view);
    }else{const empty=document.createElement('p');empty.textContent=parts.length?'Area is not estimated for these components.':'No area data for this configuration.';empty.className='area-empty';map.append(empty);}
    const list=el('area-parts');list.replaceChildren();
    for(const p of shown){const button=document.createElement('button');button.dataset.areaPart=p.id;button.className='area-part-key '+section(p);button.onclick=()=>select(p.id);
      const label=document.createElement('span'),value=document.createElement('small');label.textContent=name(p);value.textContent=known(p)?`${number(p.area_um2)} µm² · ${number(total?100*p.area_um2/total:0)}%`:'No area estimate';button.append(label,value);list.append(button);}
    const missing=shown.filter(p=>!known(p));
    el('area-coverage').textContent=missing.length?`Not sized: ${missing.map(name).join(', ')}. These parts are excluded from the known area total.`:parts.length?'Small parts retain their true area ratio. Use the list to select them. Internal details are already included in their parent.':'';
    if(!shown.some(p=>p.id===selected))selected=shown[0]?.id||null;select(selected);activity();
  }
  function render(data,costs=null){
    const next=inventory(data,costs),key=JSON.stringify([costs?.ledger?.profile,costs?.ledger?.sha256,data?.cost_model_profile,data?.cost_model_sha256,next.map(p=>[p.id,p.area_um2,p.count,p.rows,p.columns,p.status,p.source,p.cost_model,p.parameter_status,p.details?.native65_part,p.details?.residual_control_allocation,p.children])]);
    parts=next;if(key!==signature){signature=key;draw();}else activity();
  }
  function activity(){
    const active=new Set([...document.querySelectorAll('.chip-block.flow-active')].map(n=>owners[n.dataset.block]));
    document.querySelectorAll('[data-area-part]').forEach(n=>n.classList.toggle('flow-active',active.has(n.dataset.areaPart)));
  }
  function mode(area){el('chip-dataflow').hidden=area;el('chip-area').hidden=!area;el('area-focus').hidden=!area;el('chip-flow-mode').setAttribute('aria-pressed',String(!area));el('chip-area-mode').setAttribute('aria-pressed',String(area));}
  function init(){el('chip-flow-mode').onclick=()=>mode(false);el('chip-area-mode').onclick=()=>mode(true);el('area-scope').onchange=draw;}
  return {init,render,activity,layout,inventory};
})();

/* Physical grouping for the reference Studio. Counts come from its inventory. */
const Microarchitecture = (() => {
  const ns='http://www.w3.org/2000/svg', el=id=>document.getElementById(id);
  const svg=(tag,attrs={},text)=>{const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;};
  let blocks,inspect,data=null,signature=null,view,wires,units;
  const number=n=>!Number.isFinite(n)?'…':n.toLocaleString('en-US');
  const text=(g,x,y,label,cls='micro-label',anchor='middle')=>{const n=svg('text',{x,y,class:cls,'text-anchor':anchor},label);g.append(n);return n;};
  function frame(x,y,w,h,title,stages,color='neutral'){
    const g=svg('g',{class:'chip-group micro-group '+color,'data-stages':stages});
    g.append(svg('rect',{x,y,width:w,height:h,class:'micro-frame'}),svg('path',{d:`M ${x} ${y+33} H ${x+w}`,class:'micro-rule'}));
    text(g,x+14,y+22,title,'micro-heading','start');view.append(g);return g;
  }
  function block(id,x,y,w,h,label,kind='logic',shape='rect'){
    const g=svg('g',{class:'chip-block micro-block '+kind,'data-block':id,role:'button',tabindex:0,'aria-label':label||blocks[id][4]});
    const attrs={class:'micro-body'};
    g.append(shape==='mux'?svg('path',{...attrs,d:`M ${x} ${y} H ${x+w} L ${x+w-17} ${y+h} H ${x+17} Z`}):shape==='alu'?svg('path',{...attrs,d:`M ${x} ${y} H ${x+w*.4} L ${x+w*.5} ${y+10} L ${x+w*.6} ${y} H ${x+w} L ${x+w-16} ${y+h} H ${x+16} Z`}):svg('rect',{...attrs,x,y,width:w,height:h}));
    if(label)text(g,x+w/2,y+h/2+5,label);
    g.append(svg('title',{},blocks[id][5]));g.onclick=()=>inspect(id);g.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();inspect(id);}};units.append(g);return g;
  }
  function wire(from,to,d,label,x,y,control=false,both=false){
    const attrs={d,class:'chip-link micro-wire'+(control?' control-link':''),'marker-end':'url(#micro-arrow)'};
    if(from)attrs['data-from']=from;if(to)attrs['data-to']=to;if(both)attrs['marker-start']='url(#micro-arrow)';
    wires.append(svg('path',attrs));if(label)text(wires,x,y,label,'micro-bus-label');
  }
  function grid(g,x,y,w,h,columns=12,rows=5){
    for(let i=0;i<=columns;i++)g.append(svg('path',{d:`M ${x+i*w/columns} ${y} v ${h}`,class:'micro-grid-line'}));
    for(let i=0;i<=rows;i++)g.append(svg('path',{d:`M ${x} ${y+i*h/rows} h ${w}`,class:'micro-grid-line'}));
  }
  function plate(g,x,y,w,line1,line2){
    g.append(svg('rect',{x:x-w/2,y:y-17,width:w,height:line2?43:25,class:'micro-plate'}));
    text(g,x,y,line1);if(line2)text(g,x,y+19,line2,'micro-small');
  }
  function miniature(g,x,y,w,h,label){g.append(svg('rect',{x,y,width:w,height:h,class:'micro-part'}));text(g,x+w/2,y+h/2+4,label,'micro-small');}
  function draw(){
    const parts=data?.components||[],part=id=>parts.find(p=>(p.id||p.instance)===id)||{};
    const arrays=part('cim_arrays'),adc=part('adc_lanes'),current=!!data?.architecture;
    const shape=i=>current?(arrays.children?.find(c=>c.id===`cim_arrays/layer_${i}`)||arrays):arrays;
    const layer=i=>arrays.children?.find(c=>c.id===`cim_arrays/layer_${i}`)?.count;
    const lanes=adc.count,bits=data?.analog_readout?.adc_bits||(lanes?data?.analog_readout?.digital_adc_result_bits/lanes:null);
    const cellBits=data?.reference_crossbar?.cell_bits,weightBits=data?.reference_crossbar?.weight_bits;
    const node=part('node_sram'),child=part('child_sram'),ucb=part('u_ucb');
    view=svg('svg',{viewBox:'0 0 1120 938',class:'microarchitecture',role:'group','aria-label':'IMC-MCTS microarchitecture: control, tree search, neural rollout and shared SRAM'});
    const defs=svg('defs'),marker=svg('marker',{id:'micro-arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:5,markerHeight:5,orient:'auto-start-reverse'});
    marker.append(svg('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'context-stroke'}));defs.append(marker);view.append(defs);
    text(view,16,23,'IMC–MCTS  /  MICROARCHITECTURE','micro-eyebrow','start');
    text(view,1104,23,data?`${number(ucb.count)} UCB · ${number(lanes)} ADC lanes · ${number(arrays.count)} physical arrays`:'Loading hardware inventory…','micro-profile','end');
    frame(16,44,1088,76,'GLOBAL CONTROL','iteration_commit','control');
    frame(16,152,390,238,'TREE SEARCH  /  SELECTION','selection','selection');
    frame(16,420,390,230,'TREE UPDATE  /  EXPANSION + BACKPROP','expansion backpropagation','update');
    frame(444,152,660,498,'NEURAL ROLLOUT','neural','neural');
    frame(16,708,1088,212,'SHARED MEMORY','memory','memory');
    wires=svg('g',{class:'micro-wires'});units=svg('g',{class:'micro-units'});view.append(wires,units);

    block('glue',34,84,364,26,'Global FSM / request ownership','control');
    block('counter',426,84,304,26,'Iteration / budget registers','register');
    block('handshake',758,84,328,26,'Start · ready · done','register');
    wire('glue','selector','M 212 110 V 136 H 202 V 197',null,0,0,true);
    wire('glue','update','M 212 136 H 424 V 477 H 388',null,0,0,true);
    wire('glue','sequencer','M 212 136 H 770 V 193','control / status',700,130,true);

    block('selector',34,197,354,28,'Selection control / child-ID cache','control');
    const cam=block('cam',34,246,137,current?74:117,null,'memory');grid(cam,42,254,121,current?58:100,8,6);
    plate(cam,102,285,122,'Parent CAM',`${number(part('cam_macro').logical_entries)} entries`);
    const score=block('ucb',207,246,181,117,null,'compute');
    text(score,298,266,`UCB scorer × ${number(ucb.count)}`);
    miniature(score,219,280,45,29,'log');miniature(score,276,280,45,29,'÷');miniature(score,333,280,43,29,'√');
    miniature(score,219,323,157,27,'Score / result registers');
    if(current){
      const bank=block('candidates',34,332,137,44,null,'register');text(bank,102,350,'Candidate banks','micro-small');text(bank,102,367,'2 × 16 × 128 bits','micro-small');
      wire('node_router','candidates','M 264 754 V 674 H 186 V 354 H 171');wire('candidates','ucb','M 171 354 H 207');
    }
    wire('selector','cam','M 102 225 V 246');wire('cam','ucb','M 171 290 H 207','IDs',189,282);
    wire('selector','ucb','M 298 225 V 246');wire('ucb','selector','M 388 336 H 397 V 211 H 388');

    block('update',34,463,354,28,'Shared update controller','control');
    block('allocator',34,511,168,38,'Child allocator');block('choice',220,511,168,38,'Seed / choice registers','register');
    block('backprop',34,582,101,40,'Path walker','control');
    block('stats',154,575,126,54,'Visit / value','compute','alu');
    block('codec',300,582,88,40,'Q17 codec');
    wire('update','allocator','M 118 491 V 511');wire('update','choice','M 304 491 V 511');
    wire('update','backprop','M 46 491 V 562 H 84 V 582');
    wire('backprop','stats','M 135 602 H 154');wire('stats','codec','M 280 602 H 300');

    block('sequencer',470,193,608,27,'Layer / tile / row / column sequencer','control');
    const drivers=block('drivers',470,240,44,106,null,'driver');
    const driverText=text(drivers,497,293,'1-bit row drive','micro-small');driverText.setAttribute('transform','rotate(-90 497 293)');
    for(const y of [248,273,298,323])drivers.append(svg('path',{d:`M 514 ${y} h 12`,class:'micro-grid-line'}));
    for(const [i,x,w] of [[1,544,248],[2,824,248]]){
      const g=block('arrays',x,240,w,106,null,'array');g.setAttribute('aria-label',`Layer ${i} CIM arrays`);
      grid(g,x+7,247,w-14,92,16,7);
      plate(g,x+w/2,282,w-34,`Layer ${i} · ${number(layer(i))} ${layer(i)===1?'array':'arrays'}`,`${number(shape(i).rows)} × ${number(shape(i).columns)} cells / array`);
    }
    text(view,1080,174,`${number(weightBits)}-bit weights · ${number(cellBits)}-bit cells · ${current?'offset encoding':'differential slices'}`,'micro-small','end');
    wire('sequencer','drivers','M 492 220 V 240',null,0,0,true);
    wire('drivers','arrays','M 514 256 H 544');wire('drivers','arrays','M 526 256 V 228 H 814 V 256 H 824');
    wire(null,null,'M 668 346 V 364 H 808');wire(null,null,'M 948 346 V 364 H 808');
    if(current){
      block('mux',548,386,166,38,'Column mux','logic','mux');
      const sh=block('sample_hold',752,382,124,46,null,'analog');text(sh,814,402,'Sample / hold');text(sh,814,419,`${number(lanes)} shared lanes`,'micro-small');
      const adcBank=block('adc',914,376,158,58,null,'analog');text(adcBank,993,400,`ADC × ${number(lanes)}`);text(adcBank,993,419,`${number(bits)}-bit · ${number(data?.installed_memory?.adc_service_cycles ?? 13)} cycles`,'micro-small');
      wire('arrays','mux','M 808 364 H 631 V 386');wire('mux','sample_hold','M 697 405 H 752');wire('sample_hold','adc','M 876 405 H 914');
      const rb=block('readout',914,465,158,62,null,'register');text(rb,993,483,'2 × 32 × 16-bit banks','micro-small');text(rb,993,501,'128-bit bus','micro-small');text(rb,993,519,'512-bit staging','micro-small');
      const acc=block('accumulator',730,459,154,52,null,'compute','alu');text(acc,807,483,'Shift / add × 8');text(acc,807,501,'96 × 32-bit registers','micro-small');
      block('correction',534,462,158,46,'Offset correction','compute');
      wire('adc','readout','M 993 434 V 465');wire('readout','accumulator','M 914 515 H 900 V 487 H 884');wire('accumulator','correction','M 730 485 H 692');
      wire('drivers','correction','M 514 330 H 522 V 485 H 534');text(view,573,449,'input sum × 128','micro-bus-label');
      block('activation',534,547,158,42,'Scale / ReLU','compute');wire('correction','activation','M 613 508 V 547');
      block('output',754,580,164,40,'Logits / exp LUT');block('divider',956,580,112,40,'Normalize ÷','compute');
      wire('correction','output','M 692 485 H 710 V 565 H 836 V 580');wire('output','divider','M 918 600 H 956');
      wire('activation','node_router','M 613 589 V 688 H 264 V 754','hidden vector → SRAM',613,628);
      wire('divider','node_router','M 1012 620 V 688 H 264 V 754','value → tree update',985,640);
    }else{
    const hold=block('column_hold',548,382,524,28,'Optional per-column sample bank','register');
    hold.classList.toggle('uninstalled',data?.analog_readout?.profile!=='column_hold_v1');
    block('mux',548,430,166,38,'Column mux','logic','mux');
    const sh=block('sample_hold',752,426,124,46,null,'analog');
    text(sh,814,446,'Sample / hold');text(sh,814,462,`${number(lanes)} shared lanes`,'micro-small');
    const converters=block('adc',914,420,158,58,null,'analog');
    text(converters,993,437,`ADC × ${number(lanes)}`);
    for(let i=0;i<Math.min(lanes||0,4);i++)miniature(converters,924+i*36,446,30,23,i===3&&lanes>4?'…':`${number(bits)}b`);
    wire('arrays','mux','M 808 364 H 532 V 449 H 548');
    wire('arrays','column_hold','M 808 364 V 382');wire('column_hold','mux','M 808 410 V 420 H 631 V 430');
    wire('mux','sample_hold','M 697 449 H 752');wire('sample_hold','adc','M 876 449 H 914');
    const readout=block('readout',914,503,158,35,null,'register');
    text(readout,993,518,'ADC result registers','micro-small');text(readout,993,532,'32-bit readout','micro-small');
    const acc=block('accumulator',730,495,154,52,null,'compute','alu');
    text(acc,807,519,'Shift / add');text(acc,807,536,'32 × 32-bit registers','micro-small');
    const act=block('activation',534,498,158,46,null,'compute');text(act,613,517,'Scale / ReLU');text(act,613,535,'8-bit hidden values','micro-small');
    wire('adc','readout','M 993 478 V 503');wire('readout','accumulator','M 914 521 H 884');wire('accumulator','activation','M 730 521 H 692');
    block('output',754,580,164,40,'Logits / exp LUT');block('divider',956,580,112,40,'Normalize ÷','compute');
    wire('accumulator','output','M 807 547 V 580');wire('output','divider','M 918 600 H 956');
    wire('activation','node_router','M 613 544 V 688 H 264 V 754','hidden vector → SRAM',612,568);
    wire('divider','node_router','M 1012 620 V 688 H 264 V 754','value → tree update',985,640);
    }
    wire('node_router','drivers','M 264 754 V 674 H 458 V 293 H 470');
    wire('selector','node_router','M 34 211 H 24 V 674 H 264 V 754',null,0,0,false,true);
    wire('update','node_router','M 34 477 H 24 V 674 H 264 V 754',null,0,0,false,true);
    wire('backprop','node_router','M 34 602 H 24 V 674 H 264 V 754',null,0,0,false,true);
    wire('selector','child_router','M 388 211 H 414 V 698 H 914 V 754',null,0,0,false,true);
    wire('update','child_router','M 388 477 H 414 V 698 H 914 V 754',null,0,0,false,true);
    text(view,752,683,'32-bit node data / requests','micro-bus-label');
    text(view,751,702,'32-bit child data / requests','micro-bus-label');

    block('node_router',34,754,656,28,'Node bank decode / request & response registers','control');
    block('child_router',734,754,352,28,'Child memory interface','control');
    const ram=block('node_sram',34,805,656,98,null,'memory');
    text(ram,47,828,`Node SRAM · ${number(node.capacity_bytes/1024)} KiB`,'micro-label','start');
    text(ram,677,828,`${number(node.count)} × ${number(node.bank_bytes/1024)} KiB`,'micro-small','end');
    for(let i=0;i<Math.min(node.count||0,8);i++)miniature(ram,47+i*628/Math.min(node.count,8),839,628/Math.min(node.count,8)-6,20,`Bank ${i}`);
    block('path',47,871,628,23,'Reserved within node SRAM: path · board · hidden · logits / LUT','register');
    const edges=block('child_sram',734,805,352,98,null,'memory');grid(edges,743,838,334,54,18,3);
    text(edges,748,828,`Child SRAM · ${number(child.capacity_bytes/1024)} KiB`,'micro-label','start');
    plate(edges,910,860,240,`${number(child.count)} × ${number(child.bank_bytes/1024)} KiB`,'Child IDs / list links');
    wire('node_router','node_sram','M 264 782 V 805',null,0,0,false,true);wire('child_router','child_sram','M 914 782 V 805',null,0,0,false,true);
    for(const n of view.querySelectorAll('[data-from="arrays"]'))n.classList.toggle('unused-route',data?.analog_readout?.profile==='column_hold_v1'?n.dataset.to==='mux':n.dataset.to==='column_hold');
    view.querySelector('[data-from="column_hold"]')?.classList.toggle('unused-route',data?.analog_readout?.profile!=='column_hold_v1');
    el('chip').replaceChildren(view);
    el('micro-profile-note').textContent=data?`${current?'Current optimized design · '+data.architecture.profile:'Historical reference profile'} · Click a unit for details. Schematic, not a floorplan.`:'Loading the selected configuration…';
  }
  function render(next){
    const key=JSON.stringify([next?.architecture?.profile,next?.cost_model_profile,next?.cost_model_sha256,next?.component_parameters,next?.components?.map(p=>[p.id,p.count,p.rows,p.columns,p.capacity_bytes,p.bank_bytes,p.logical_entries,p.children?.filter(c=>c.id?.includes('/layer_')).map(c=>c.count)]),next?.analog_readout,next?.reference_crossbar?.cell_bits]);
    data=next;if(key===signature)return;signature=key;
    const selected=el('chip').querySelector('.selected')?.dataset.block||'glue';draw();inspect(selected);
  }
  function init(source,onInspect){blocks=source;inspect=onInspect;draw();inspect('glue');
    el('expand-chip').onclick=()=>{const large=el('chip-panel').classList.toggle('maximized');el('expand-chip').textContent=large?'Close large view':'Enlarge';};
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){el('chip-panel').classList.remove('maximized');el('expand-chip').textContent='Enlarge';}});
  }
  return {init,render};
})();
