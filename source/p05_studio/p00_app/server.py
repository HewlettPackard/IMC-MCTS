# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Local interactive execution on the same complete simulator and result registry.
# SPDX-License-Identifier: MIT
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')

import hashlib
import argparse
import base64
import csv
import gzip
from collections import deque
from copy import deepcopy
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit, parse_qs
import uuid

from core.architecture.complete_costs import complete_costs, prepare_costs
from core.architecture import studio_current as current_arch
from core.architecture.cost_ledger import scaling_policy
from core.algorithm.model_catalog import model_catalog, model_record
from core.architecture.crossbar_workbook import component_estimates, reference_crossbar
from core.architecture.neural_mapping import neural_profile
from core.architecture.iteration_model import PROFILE
from core.architecture.single_child import PROFILE as SINGLE_PROFILE, preview_memory
from core.architecture.board_sizing import PROFILE as SIZED_HARDWARE, board_table, sized_memory, memory_profile_name
from core.architecture.analog_readout import DRIVEN, readout_spec
from core.architecture.result_registry import RUNS, ROOT, RunCancelled, catalog, current_index, resolve_case, run_case, verify_run
from core.architecture.result_snapshot import latest_snapshot, verify_snapshot
from p05_studio.p00_app.placement_play import BoardPlay
from p05_studio.p00_app.visualization import Visualization, activity_groups
from p05_studio.p00_app.pipeline import Pipeline, service_intervals

STATIC=Path(__file__).resolve().parents[1]/'p01_static'


def saved_cost_identity(out):
    # Enrich the response from the saved ledger without rewriting old indexes.
    try:
        ledger=json.loads((Path(out)/'result.json').read_text()).get('costs',{}).get('ledger',{})
    except (OSError,json.JSONDecodeError):
        ledger={}
    return {'cost_model_profile':ledger.get('profile'),'cost_model_sha256':ledger.get('sha256')}


class Job:
    def __init__(self, config, identifier, paused, runs, execution='search', move_delay_ms=600, options=None):
        self.id=uuid.uuid4().hex[:12]; self.config=config; self.identifier=identifier; self.runs=runs
        self.condition=threading.Condition(); self.paused=paused; self.permits=0; self.cancelled=False
        self.status='queued'; self.sequence=0; self.events=deque(maxlen=2000)
        self.snapshot={}; self.program=None; self.programs={}; self.result=None; self.run=None; self.error=None
        self.execution=execution; self.move_delay_ms=move_delay_ms
        self.options=options
        self.speed=(options or {}).get('speed',85)
        self.move_quota=None if (options or {}).get('play_until','end')=='end' else 1
        self.human_input=None; self.finished=False
        self.visual=Visualization()
        self.pipeline=Pipeline()
        self.activity_cache={}
        self.cost_context=None
        self.play=None if execution=='search' else BoardPlay(config,Path(runs).parent/'p02_plays',options)

    def hold(self, delay=0):
        end=time.monotonic()+delay
        while True:
            if self.cancelled: raise RunCancelled('Cancelled in the studio')
            self.status='paused' if self.paused else 'running'
            if self.paused:
                if self.permits:
                    self.permits-=1; return
                self.condition.wait(timeout=.25)
            else:
                remaining=end-time.monotonic()
                if remaining<=0: return
                self.condition.wait(timeout=remaining)

    def observe(self, event, model):
        with self.condition:
            if self.cancelled: raise RunCancelled('Cancelled in the studio')
            self.run=event['run'] if self.play is None else self.play.out.name
            latest=current_arch.is_current(self.config)
            configuration_key=model.memory.config['execution_profile']+':'+':'.join(model.evaluator['weight_sha256'])+':'+hashlib.sha256(json.dumps(getattr(model,'component_parameters',{}),sort_keys=True).encode()).hexdigest()
            if latest: configuration_key+=':'+current_arch.COST_PROFILE
            refresh_costs=self.program is None or self.program.get('configuration_key')!=configuration_key or event['phase']=='ready'
            if refresh_costs:
                self.cost_context=current_arch.prepare(model) if latest else prepare_costs(self.config['memory_profile'],model.neural.profile,model.memory.config)
            program_key=configuration_key
            if latest: program_key+=':'+current_arch.cost_identity(self.cost_context['source_sha256'],self.cost_context['component_parameters'])
            if self.program is None or self.program['key']!=program_key:
                arrays=[]
                for layer,tiles in enumerate(model.neural.tiles):
                    for tile in tiles:
                        cells=tile['cells'].astype('u1')
                        arrays.append({'layer':layer+1,'rows':cells.shape[0],'columns':cells.shape[1],
                            'row_start':tile['row_start'],'output_start':tile['output_start'],
                            'cells':base64.b64encode(cells.tobytes()).decode()})
                self.program={'key':program_key,'configuration_key':configuration_key,'arrays':arrays,'profile':model.neural.profile,'coefficients':model.neural.coefficients,
                    'evaluator':model.evaluator,'component_estimates':current_arch.inventory(self.cost_context) if latest else component_estimates(model.neural.profile,self.config['memory_profile'],model.memory.config)}
                self.program['pipeline']={'cycles':model.neural.schedule['cycles'],
                    'services':service_intervals(model.neural.schedule['trace'])}
                self.programs[program_key]=self.program
            root=model.memory.nodes[0]
            children=[]
            for n in root['children']:
                node=model.memory.nodes[n]
                children.append({'id':n,'visits':node['visits'],'black_value':None if not node['visits'] else (node['value']/node['visits'] if node['player']==1 else 1-node['value']/node['visits']),
                    'position':next((i for i,(a,b) in enumerate(zip(model.initial_board.flat,node['board'].flat)) if a!=b),None)})
            self.sequence+=1
            row=event | {'seq':self.sequence}
            self.events.append(row)
            self.snapshot={'event':row,'program_key':program_key,'board':model.board(model.selected).tolist(),'completed':model.completed,
                'budget':model.iterations,'cycles':model.cycles,'nodes':model.memory.nodes_used,'edges':model.memory.edges_used,
                'memory':model.memory.config,'operations':dict(model.memory.operations),'phase_cycles':dict(model.phase_cycles),
                'block_active_cycles':dict(model.block_active_cycles),
                'cam_rows':sum(len(item[1]) for item in model.memory.cam.values()),'root_children':children,
                'cache_groups':[{'parent':parent,'rows':len(rows),'first_row':rows[0]} for parent,(_,rows,_) in list(model.memory.cam.items())[-16:]],
                'neural':model.neural.last_state,'selected_node':model.selected,'path_depth':model.memory.path_depth,
                'value_q17':model.value_q17,'run':self.run}
            if latest: self.snapshot['reporting_basis']=current_arch.capture(model)
            if hasattr(model,'termination'): self.snapshot['termination']=model.termination
            self.status='paused' if self.paused else 'running'
            if self.play is not None:
                self.snapshot.update(play=self.play.state(),run=self.run,
                    board=(model.board(model.selected)*self.play.search_player).tolist(),
                    display_cycles=self.play.cycles+model.cycles,
                    display_operations=dict(self.play.operations+model.memory.operations),
                    display_phase_cycles=dict(self.play.phase_cycles+model.phase_cycles),
                    display_block_active_cycles={key:self.play.block_active_cycles[key]+value for key,value in model.block_active_cycles.items()})
                if latest: self.snapshot['display_reporting_basis']=current_arch.combine(self.play.reporting_basis,current_arch.capture(model))
                if self.play.search_player==-1:
                    self.snapshot['display_black_value_q17']=131072-model.value_q17
                    if model.neural.last_state:
                        self.snapshot['display_probabilities_q16']=list(reversed(model.neural.last_state['probabilities_q16']))
                    for child in children:
                        if child['black_value'] is not None: child['black_value']=1-child['black_value']
            if self.options is not None:
                self.pipeline.observe(event,model)
                self.visual.observe(event,model,1 if self.play is None else self.play.search_player)
                groups=activity_groups(event,model,self.activity_cache)
                self.snapshot.update(activity=groups,activity_index=-1)
            if event['phase']=='iteration_commit' and (model.completed==model.iterations or model.status=='memory_limited'): return
            self.present() if self.options is not None else self.hold()

    def present(self, move=False):
        groups=self.snapshot.get('activity',[])
        indices=range(len(groups)) if self.speed<60 and groups and not move else [-1]
        for index in indices:
            self.snapshot['activity_index']=index
            self.sequence+=1
            self.snapshot['event']=self.snapshot['event'] | {'seq':self.sequence}
            # Recalculate elapsed display time when the speed slider changes.
            started=time.monotonic()
            while True:
                if self.cancelled: raise RunCancelled('Cancelled in the studio')
                if self.paused:
                    self.hold(); break
                self.status='running'
                delay=(1-self.speed/100)**2*(1.0 if move else .7)
                remaining=delay-(time.monotonic()-started)
                if remaining<=0: break
                self.condition.wait(timeout=min(remaining,.1))

    def turn(self, play):
        with self.condition:
            human=play.opponent=='human' and play.player!=play.architecture_player
            self.run=play.out.name
            while True:
                if self.cancelled: raise RunCancelled('Cancelled in the studio')
                if self.finished: return 'finish'
                if self.paused and (self.snapshot.get('event') or human):
                    self.hold()
                if human or self.move_quota==0:
                    self.snapshot.update(play=play.state(),run=self.run)
                    self.status='awaiting_human' if human else 'awaiting_move'
                    if human and self.human_input is not None:
                        move=self.human_input; self.human_input=None
                        self.status='running'; return move
                    if not human and self.move_quota!=0: return None
                    self.condition.wait(timeout=.1)
                    continue
                self.status='running'; return None

    def placed(self, move, model):
        with self.condition:
            self.sequence+=1
            event={'phase':'move_commit','iteration':0 if model is None else model.completed,'move':move['move'],
                'cycle_end':self.play.cycles,'run':self.run,'seq':self.sequence}
            self.events.append(event)
            self.snapshot.update(event=event,play=self.play.state(),display_cycles=self.play.cycles,
                display_operations=dict(self.play.operations),display_phase_cycles=dict(self.play.phase_cycles),
                display_block_active_cycles=dict(self.play.block_active_cycles))
            if current_arch.is_current(self.config): self.snapshot['display_reporting_basis']=self.play.reporting_basis
            if self.options is not None:
                self.snapshot.update(activity=[],activity_index=-1)
                if move.get('actor')!='human' and self.move_quota is not None:
                    self.move_quota=max(0,self.move_quota-1)
                if len(self.play.moves)<self.play.target and self.play.termination is None: self.present(move=True)
                return
            if len(self.play.moves)==self.play.target: return
            self.hold(self.move_delay_ms/1000)

    def work(self):
        try:
            if self.play is not None:
                out,result=self.play.run(self.observe,self.placed,self.turn if self.options is not None else None)
            else:
                named=any(row['id']==self.identifier for row in catalog()['cases'])
                out,result=run_case(case_id=self.identifier if named else None,custom=None if named else self.config,
                    runs=self.runs,on_event=self.observe)
            with self.condition:
                self.result=result; self.run=out.name; self.status=result['status']
        except Exception as error:
            with self.condition:
                self.error=str(error); self.status='cancelled' if isinstance(error,RunCancelled) else 'failed'

    def action(self, action, value=None):
        with self.condition:
            if action=='speed':
                if type(value) is not int or not 0<=value<=100: raise ValueError('Speed must be between 0 and 100')
                self.speed=value; self.condition.notify_all(); return
            if self.status in ('complete','memory_limited','failed','cancelled'): raise ValueError('This job has finished')
            if action=='pause': self.paused=True
            elif action=='resume': self.paused=False; self.permits=0
            elif action=='step': self.paused=True; self.permits+=1
            elif action=='cancel': self.cancelled=True; self.status='cancelling'
            elif action=='human_move':
                if self.status!='awaiting_human' or self.human_input is not None: raise ValueError('It is not your turn')
                self.play.validate_human(value); self.human_input=value
            elif action in ('one','until_end'):
                if self.play is None: raise ValueError('This is a single-position search')
                self.move_quota=1 if action=='one' else None; self.paused=False
            elif action=='finish':
                if self.status not in ('awaiting_move','awaiting_human'): raise ValueError('Pause between moves before ending the session')
                self.finished=True; self.paused=False
            else: raise ValueError('Unknown execution action')
            self.condition.notify_all()

    def payload(self, after=0, tree_after=0, tree_key=None, pipeline_after=0, pipeline_key=None):
        with self.condition:
            snapshot=deepcopy(self.snapshot)
            result={'id':self.id,'case_id':self.identifier,'status':self.status,'run':self.run,'error':self.error,
                'configuration':self.config,
                'execution':self.execution,'move_delay_ms':self.move_delay_ms,
                'studio_options':self.options,'speed':self.speed,
                'export_base':('/api/plays/' if self.play is not None else '/api/runs/')+str(self.run),
                'sequence':self.sequence,'snapshot':snapshot,'events':[r for r in self.events if r['seq']>after][-200:],
                'result':None if self.result is None else {'metrics':self.result['metrics'],'costs':self.result['costs'],
                    'tree_sha256':self.result.get('tree_sha256'),'execution_sha256':self.result['identity']['execution_sha256'],
                    'component_estimates':self.result.get('component_estimates')}}
            if result['result'] is not None:
                result['result'].update(status=self.result['status'],termination=self.result.get('termination'),
                    expansion_policy=self.result.get('expansion_policy'))
            if self.options is not None:
                result['tree']=self.visual.payload(tree_after,tree_key)
                result['pipeline']=self.pipeline.payload(pipeline_after,pipeline_key)
            cycles=snapshot.get('display_cycles',snapshot.get('cycles',0))
            prepared=self.cost_context
            if cycles>0:
                cost_inputs=(self.config['memory_profile'],
                    snapshot.get('display_operations',snapshot['operations']),cycles,
                    deepcopy(self.program['profile']),snapshot['memory'],
                    snapshot.get('display_phase_cycles',snapshot['phase_cycles']),
                    snapshot.get('display_block_active_cycles',snapshot['block_active_cycles']))
        # Source checks and PPA calculation can be slow. They use this frame's
        # captured inputs without holding up search progress or execution controls.
        if cycles>0:
            result['live_costs']=current_arch.costs(cost_inputs[1],cycles,cost_inputs[6],
                snapshot.get('display_reporting_basis',snapshot.get('reporting_basis')),prepared) if current_arch.is_current(self.config) else complete_costs(*cost_inputs,prepared=prepared)
        return result


class Studio:
    def __init__(self, runs=RUNS):
        self.jobs={}; self.lock=threading.Lock(); self.runs=Path(runs)

    def create(self, body, owner=""):
        if not isinstance(body,dict) or set(body)-{'case_id','configuration','mode','execution','move_delay_ms','studio_options'}: raise ValueError('Unknown job fields')
        if body.get('mode','live') not in ('live','paused'): raise ValueError('Mode must be live or paused')
        execution=body.get('execution','search'); delay=body.get('move_delay_ms',600)
        if execution not in ('search','play'): raise ValueError('Unknown execution mode')
        if type(delay) is not int or not 0<=delay<=5000: raise ValueError('Move display delay must be between 0 and 5,000 ms')
        request=body.get('configuration')
        if not body.get('case_id') and (request is None or isinstance(request,dict) and not request.get('profile') and not request.get('hardware_profile')):
            request=current_arch.current_architecture()['default_configuration'] | (request or {})
        config,identifier=resolve_case(body.get('case_id'),request)
        options=body.get('studio_options')
        if options is not None:
            if not isinstance(options,dict) or set(options)-{'speed','play_until','opponent','opponent_config','architecture_side'}: raise ValueError('Unknown studio options')
            options={'speed':85,'play_until':'end','opponent':'self','opponent_config':{},'architecture_side':'black'} | options
            if type(options['speed']) is not int or not 0<=options['speed']<=100: raise ValueError('Invalid animation speed')
            if options['play_until'] not in ('one','end') or options['opponent'] not in ('self','human','engine'): raise ValueError('Invalid play options')
            if options['architecture_side'] not in ('black','white'): raise ValueError('Architecture side must be black or white')
            opponent=options['opponent_config']
            if not isinstance(opponent,dict) or set(opponent)-{'iterations','seed','model_id'}: raise ValueError('Unknown opponent settings')
            resolved,_=resolve_case(custom=config | opponent)
            if type(resolved['iterations']) is not int or not (1 if execution=='search' else 2)<=resolved['iterations']<=50000: raise ValueError('Invalid iteration budget')
            if type(resolved['seed']) is not int or not 0<=resolved['seed']<2**32: raise ValueError('Invalid opponent seed')
        if type(config['iterations']) is not int or not 1<=config['iterations']<=50000:
            raise ValueError('Studio iteration budget must be between 1 and 50,000')
        with self.lock:
            if any(job.status not in ('complete','memory_limited','failed','cancelled') for job in self.jobs.values()):
                raise ValueError('A job is active. Finish or cancel it before starting another.')
            if len(self.jobs)>=8: self.jobs.pop(next(iter(self.jobs)))
            job=Job(config,identifier,body.get('mode')=='paused',self.runs,execution,delay,options); job.owner=owner; self.jobs[job.id]=job
            threading.Thread(target=job.work,daemon=True,name='imc-'+job.id).start()
            return job


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        if self.path.startswith('/api/jobs/') and self.command=='GET': return
        super().log_message(format,*args)

    def send_data(self, status, data, content_type='application/json; charset=utf-8', download=None):
        if not isinstance(data,bytes): data=json.dumps(data,allow_nan=False).encode()
        self.send_response(status); self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if download: self.send_header('Content-Disposition','attachment; filename="'+download+'"')
        self.end_headers()
        try: self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError): pass

    def client_id(self):
        value=self.headers.get("X-Studio-Client","")
        if value and not re.fullmatch(r"[a-f0-9]{32}",value): raise ValueError("Invalid studio client identifier")
        return value

    def owned_job(self,identifier):
        job=self.server.studio.jobs.get(identifier)
        return job if job is not None and getattr(job,"owner","")==self.client_id() else None

    def do_GET(self):
        try:
            url=urlsplit(self.path); path=url.path; query=parse_qs(url.query); studio=self.server.studio
            if path=='/favicon.ico': return self.send_data(204,b'','image/x-icon')
            if path in ('/','/app.js','/style.css','/visuals.js'):
                file=STATIC/('index.html' if path=='/' else path[1:])
                return self.send_data(200,file.read_bytes(),mimetypes.guess_type(file)[0] or 'application/octet-stream')
            if path=='/api/health': return self.send_data(200,{'status':'ok','service':'IMC-MCTS Studio','profile':current_arch.PROFILE,
                'cost_model_profile':current_arch.preview('go_strong_v1')['peripheral_model']['profile'],
                'cost_model_sha256':current_arch.cost_identity(),'connected_synthesis':current_arch.connected_metadata(),
                'scaling_policy_profile':scaling_policy()['profile'],'loopback_only':True})
            if path=='/api/architecture': return self.send_data(200,current_arch.current_architecture())
            if path=='/api/catalog': return self.send_data(200,catalog())
            if path=='/api/models': return self.send_data(200,{'models':model_catalog()})
            if path=='/api/board-hardware': return self.send_data(200,board_table())
            if path=='/api/crossbar': return self.send_data(200,reference_crossbar(int(query.get('size',['256'])[0])))
            if path=='/api/components':
                if query.get('architecture',[''])[0]==current_arch.PROFILE:
                    config=current_arch.current_architecture()['default_configuration'] | {'board_size':int(query.get('board',['9'])[0]),'model_id':query.get('model',['go_strong_v1'])[0],
                        'readout_profile':query.get('readout',[DRIVEN])[0],'memory_profile':query.get('memory',['cacti_22nm_lstp'])[0]}
                    current_arch.validate_current(config)
                    return self.send_data(200,current_arch.preview(config['model_id'],config['board_size']))
                size=int(query.get('board',['9'])[0])
                sized=query.get('hardware',[''])[0]==SIZED_HARDWARE
                if size not in ((2,3,5,9,13,19) if sized else (2,3,5,9)): raise ValueError('Unsupported board size')
                record=model_record(query.get('model',['random_diagnostic'])[0],size)
                profile=neural_profile(size,32 if size in (2,3) else 96,sram_word_cycles=2,
                    turn_indicator=bool(record and record.get('turn_indicator')))
                profile['readout']=readout_spec(query.get('readout',[DRIVEN])[0])
                memory=None if query.get('expansion',['single'])[0]=='legacy' else preview_memory(profile)
                name=query.get('memory',['cacti_22nm_lstp'])[0]
                if sized:
                    memory=sized_memory(profile,rules=query.get('rules',['placement'])[0])
                    name=memory_profile_name(size,name)
                data=component_estimates(profile,name,memory)
                if sized: data['installed_memory']=memory
                return self.send_data(200,data)
            if path=='/api/runs':
                data=deepcopy(current_index(studio.runs))
                for row in data['cases'].values(): row.update(saved_cost_identity(studio.runs/row['run']))
                return self.send_data(200,data)
            if path=='/api/snapshot':
                snapshot=latest_snapshot(studio.runs.parent/'p04_snapshots')
                rows=[]
                if snapshot:
                    with (studio.runs.parent/'p04_snapshots'/snapshot['id']/'summary.csv').open(newline='') as stream:
                        rows=list(csv.DictReader(stream))
                return self.send_data(200,{'snapshot':snapshot,'rows':rows})
            snapshot=re.fullmatch(r'/api/snapshots/(run_\d{8}_\d{6}Z)/(summary.csv|manifest.json|SHA256SUMS)',path)
            if snapshot:
                out=studio.runs.parent/'p04_snapshots'/snapshot[1]; verify_snapshot(out)
                file=out/snapshot[2]
                return self.send_data(200,file.read_bytes(),mimetypes.guess_type(file)[0] or 'application/octet-stream',file.name)
            if path=='/api/plays':
                rows=[]
                for out in sorted((studio.runs.parent/'p02_plays').glob('run_*'),reverse=True):
                    if not (out/'SHA256SUMS').is_file(): continue
                    record=json.loads((out/'metadata.json').read_text())
                    if record['status'] in ('complete','memory_limited'): rows.append({'run':out.name,'moves':record['completed_moves'],'status':record['status'],'architecture_profile':record.get('architecture_profile')} | saved_cost_identity(out))
                    if len(rows)==10: break
                return self.send_data(200,{'sessions':rows})
            if path=='/api/session':
                with studio.lock: job=next((j for j in reversed(studio.jobs.values()) if getattr(j,"owner","")==self.client_id()),None)
                return self.send_data(200,{'job':None if job is None else job.payload()})
            saved_tree=re.fullmatch(r'/api/jobs/([a-f0-9]{12})/tree/(\d+)',path)
            if saved_tree:
                job=self.owned_job(saved_tree[1])
                if job is None or job.play is None: raise ValueError('No game tree is available')
                moves=[row for row in job.play.moves if row['move']==int(saved_tree[2]) and row.get('search_run')]
                if not moves: raise ValueError('That move has no completed search tree')
                move=moves[0]; out=job.play.out/'p01_searches'/move['search_run']; verify_run(out)
                with gzip.open(out/'tree.json.gz','rt') as stream: tree=json.load(stream)
                perspective=1 if job.config.get('rules')=='legacy_go' else move['player']
                rows=[]
                for name,node in tree.items():
                    rows.append({'id':int(name),'parent':node['parent'],'children':len(node['children']),
                        'visits':node['visits'],'value_sum':node['value'],'player':node['player']*perspective,
                        'board':[[value*perspective for value in row] for row in node['board']]})
                route=[]; current=move['node']
                while current>=0:
                    route.append(current); current=tree[str(current)]['parent']
                return self.send_data(200,{'move':move['move'],'nodes':rows,'path':list(reversed(route))})
            match=re.fullmatch(r'/api/jobs/([a-f0-9]{12})(/program)?',path)
            if match:
                job=self.owned_job(match[1])
                if job is None: return self.send_data(404,{'error':'Unknown job'})
                if match[2]: return self.send_data(200,job.programs.get(query['key'][0]) if 'key' in query else job.program)
                return self.send_data(200,job.payload(int(query.get('after',['0'])[0]),
                    int(query.get('tree_after',['0'])[0]),query.get('tree_key',[None])[0],
                    int(query.get('pipeline_after',['0'])[0]),query.get('pipeline_key',[None])[0]))
            match=re.fullmatch(r'/api/runs/(run_\d{8}_\d{6}Z)/([a-zA-Z0-9_.]+)',path)
            allowed={'result.json','summary.csv','block_power.csv','components.csv','iterations.csv','phases.jsonl','tree.json.gz','identity.json','weights.npz','source_snapshot.tar.gz','SHA256SUMS','metadata.json','component_estimates.json'}
            if match and match[2] in allowed:
                out=studio.runs/match[1]; verify_run(out)
                file=out/match[2]
                return self.send_data(200,file.read_bytes(),mimetypes.guess_type(file)[0] or 'application/octet-stream',file.name if 'download' in query else None)
            play=re.fullmatch(r'/api/plays/(run_\d{8}_\d{6}Z)(?:/searches/(run_\d{8}_\d{6}Z))?/([a-zA-Z0-9_.]+)',path)
            if play and play[3] in allowed | {'moves.json','moves.csv'}:
                out=studio.runs.parent/'p02_plays'/play[1]
                if play[2]: out=out/'p01_searches'/play[2]
                verify_run(out); file=out/play[3]
                return self.send_data(200,file.read_bytes(),mimetypes.guess_type(file)[0] or 'application/octet-stream',file.name if 'download' in query else None)
            self.send_data(404,{'error':'Not found'})
        except (ValueError,TypeError,KeyError) as error: self.send_data(400,{'error':str(error)})
        except FileNotFoundError: self.send_data(404,{'error':'Saved artifact not found'})

    def do_POST(self):
        origin=self.headers.get('Origin')
        port=self.server.server_address[1]
        if origin and origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
            return self.send_data(403,{'error':'Local studio origin required'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            return self.send_data(415,{'error':'Use application/json'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=65536: raise ValueError('Invalid request size')
            body=json.loads(self.rfile.read(length))
            path=urlsplit(self.path).path
            if path=='/api/component-preview':
                if not isinstance(body,dict) or set(body)-{'board_size','model_id','component_parameters'}: raise ValueError('Unknown component preview fields')
                config=current_arch.current_architecture()['default_configuration'] | body
                current_arch.validate_current(config)
                return self.send_data(200,current_arch.custom_preview(config['model_id'],config['board_size'],config.get('component_parameters',{})))
            if path=='/api/jobs': return self.send_data(202,self.server.studio.create(body,self.client_id()).payload())
            match=re.fullmatch(r'/api/jobs/([a-f0-9]{12})/actions',path)
            if match:
                job=self.owned_job(match[1])
                if job is None: return self.send_data(404,{'error':'Unknown job'})
                if not isinstance(body,dict) or 'action' not in body or set(body)-{'action','value'}: raise ValueError('Expected an action and optional value')
                job.action(body['action'],body.get('value')); return self.send_data(200,job.payload())
            self.send_data(404,{'error':'Not found'})
        except (ValueError,TypeError,KeyError) as error: self.send_data(400,{'error':str(error)})


def serve(port=4781, runs=RUNS):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler); server.studio=Studio(runs)
    print(f'IMC-MCTS Studio: http://127.0.0.1:{server.server_address[1]}',flush=True)
    server.serve_forever(poll_interval=0.25)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=4781)
    args=parser.parse_args(); serve(args.port)
