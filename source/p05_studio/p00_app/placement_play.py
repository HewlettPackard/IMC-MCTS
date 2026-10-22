# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Commit one chosen child per search, preserving each search's own evidence.
# SPDX-License-Identifier: MIT
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
from pathlib import Path
import tarfile

import numpy as np

from core.algorithm.model_catalog import model_record
from core.architecture.complete_costs import complete_costs
from core.architecture import studio_current as current
from core.architecture.block_activity import BLOCKS, activity_record
from core.architecture.block_power import write_power_csv
from core.architecture.component_inventory import write_component_csv
from core.architecture.cost_ledger import ledger_fields
from core.architecture.digital_costs import digital_timing_fields
from core.architecture.analog_readout import BUFFERED, DRIVEN
from core.architecture.go_simulation import LegacyGo, initial_state, state_record
from core.architecture.result_registry import ROOT, RunCancelled, configuration, new_run, run_case, write_json
from core.architecture.run_identity import json_sha256

PROFILE='placement_play_relative_player_v1'
SESSION_PROFILE='studio_turns_v3'


class BoardPlay:
    def __init__(self, config, runs, options=None):
        self.config=configuration(config); self.runs=Path(runs)
        self.options=None if options is None else {key:options.get(key,default) for key,default in [('opponent','self'),('opponent_config',{}),('architecture_side','black')]}
        self.opponent=(options or {}).get('opponent','self')
        self.opponent_config=(options or {}).get('opponent_config',{})
        self.architecture_side=(options or {}).get('architecture_side','black')
        if self.architecture_side not in ('black','white'): raise ValueError('Architecture side must be black or white')
        self.architecture_player=1 if self.architecture_side=='black' else -1
        self.completed_iterations=0
        self.termination=None
        self.board=np.asarray(self.config['initial_board'])
        size=self.config['board_size']
        if self.opponent=='engine':
            own=model_record(self.config.get('model_id','random_diagnostic'),size)
            other=model_record(self.opponent_config.get('model_id',self.config.get('model_id','random_diagnostic')),size)
            if bool(own and own.get('turn_indicator'))!=bool(other and other.get('turn_indicator')):
                raise ValueError('Opponent model must use the same board/turn input layout')
        if self.board.shape!=(size,size) or not np.isin(self.board,[-1,0,1]).all():
            raise ValueError('Initial board must contain only -1, 0 and 1 at the configured dimensions')
        self.board=self.board.astype(np.int8,copy=True)
        if type(self.config['iterations']) is not int or self.config['iterations']<2:
            raise ValueError('Playing moves needs at least two search iterations per move')
        self.game=LegacyGo(size) if self.config.get('rules')=='legacy_go' else None
        self.game_state=None if self.game is None else initial_state(self.game,self.board,self.config.get('go_state'))
        if self.game is not None and self.game.is_terminal(self.game_state): raise ValueError('The Go game is already terminal')
        self.target=int(np.count_nonzero(self.board==0)) if self.game is None else self.game._max_moves-self.game_state['move_count']
        if not self.target: raise ValueError('The board is already full. Clear a cell or choose a new initial board.')
        self.player=1 if self.game is None else self.game_state['current_player']; self.search_player=1; self.current_move=1; self.moves=[]; self.model=None; self.out=None
        self.cycles=0; self.operations=Counter(); self.phase_cycles=Counter()
        self.reporting_basis={'parents':[],'completed':0}
        blocks=tuple(k for k in BLOCKS if k!='u_ucb')+current.LANES if current.is_current(self.config) else BLOCKS
        self.block_active_cycles=Counter(dict.fromkeys(blocks,0))

    def state(self):
        return {'profile':PROFILE if self.game is None else 'legacy_go_play_v2',
            'rules':'placement' if self.game is None else 'legacy_go',
            'terminal':len(self.moves)==self.target if self.game is None else self.game.is_terminal(self.game_state),
            'captures':None if self.game is None else state_record(self.game_state)['captures'],
            'score':None if self.game is None else list(self.game.score_position(self.board)),'run':None if self.out is None else self.out.name,
            'board':self.board.tolist(),'completed_moves':len(self.moves),'total_moves':self.target,
            'player_to_move':self.player,'search_player':self.search_player,'current_move':self.current_move,
            'architecture_side':self.architecture_side,
            'moves':[dict(row) for row in self.moves],'core_cycles':self.cycles,
            'iterations_per_move':self.config['iterations']}

    def validate_human(self, move):
        if not isinstance(move,list) or len(move)!=2 or any(type(n) is not int for n in move):
            raise ValueError('Choose a board intersection or Pass')
        row,column=move
        if self.game is not None:
            if move!=[-1,-1] and not self.game.is_legal(self.game_state,row,column,self.player):
                raise ValueError('That move is not legal')
        elif not (0<=row<len(self.board) and 0<=column<len(self.board) and self.board[row,column]==0):
            raise ValueError('Choose an empty intersection')

    def human_turn(self, move, turn):
        self.validate_human(move)
        before=self.board.copy(); row,column=move
        if self.game is None:
            self.board=self.board.copy(); self.board[row,column]=self.player
        else:
            self.game_state=self.game.apply_move(self.game_state,(row,column))
            self.board=self.game_state['board'].copy()
        result={'move':turn+1,'player':self.player,'actor':'human','row':row,'column':column,
            'node':None,'visits':None,'core_cycles':0,'core_latency_us':0,'sram_energy_uj':0,
            'result_sha256':None,'execution_sha256':None,'board_before':before.tolist(),
            'board_after':self.board.tolist(),'search_run':None,'search_iterations':0}
        if self.game is not None:
            result.update(pass_move=row==-1,captures=state_record(self.game_state)['captures'],go_state=state_record(self.game_state))
        self.player=-self.player
        return result

    def run(self, on_search, on_move, on_turn=None):
        self.out=new_run(self.runs)
        metadata={'schema_version':1,'status':'running','profile':PROFILE if self.game is None else 'legacy_go_play_v2','completed_moves':0,'architecture_profile':self.config['profile'],
            'started_utc':datetime.now(timezone.utc).isoformat(),'benchmarks_executed':False}
        write_json(self.out/'metadata.json',metadata); write_json(self.out/'requested.json',self.config)
        if self.options is not None: write_json(self.out/'session.json',self.options)
        sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob('*.py'))}
        write_json(self.out/'source_sha256.json',sources)
        with tarfile.open(self.out/'source_snapshot.tar.gz','w:gz') as archive:
            for name in sources: archive.add(ROOT/name,arcname=name,recursive=False)
        deterministic_moves=[]
        try:
            for turn in range(self.target):
                if self.game is not None and self.game.is_terminal(self.game_state): break
                self.current_move=turn+1
                human=on_turn(self) if on_turn is not None else None
                if human=='finish': break
                if human is not None:
                    move=self.human_turn(human,turn)
                    self.moves.append(move); deterministic_moves.append(move)
                    write_json(self.out/'moves.json',self.moves)
                    metadata['completed_moves']=len(self.moves); write_json(self.out/'metadata.json',metadata)
                    on_move(move,self.model)
                    continue
                self.search_player=self.player if self.game is None else 1
                turn_config=self.config
                if self.options is not None and self.opponent=='engine' and self.player!=self.architecture_player:
                    turn_config=self.config | self.opponent_config
                    # The opponent may use a different input encoding/controller profile.
                    turn_config=configuration({k:v for k,v in turn_config.items() if k!='profile' or current.is_current(self.config)})
                if self.game is None:
                    request=turn_config | {'initial_board':(self.board*self.player).tolist()}
                    if turn_config.get('model_id','random_diagnostic')!='random_diagnostic': request['model_perspective']=self.player
                else:
                    request=turn_config | {'initial_board':self.board.tolist(),'go_state':state_record(self.game_state)}

                def observe(row, model):
                    self.model=model
                    on_search(row,model)

                out,result=run_case(custom=request,runs=self.out/'p01_searches',on_event=observe)
                self.model_estimates=result['component_estimates']
                tree=self.model.memory.nodes
                if not tree[0]['children']:
                    raise MemoryError('Memory limit reached before a root move was evaluated; no move was placed')
                chosen=max(tree[0]['children'],key=lambda n:(tree[n]['visits'],-n))
                if tree[chosen]['visits']<=0: raise RuntimeError('Search did not evaluate any root child')
                after=self.model.board(chosen)*self.search_player
                if self.game is None:
                    changed=np.argwhere(after!=self.board)
                    if len(changed)!=1: raise RuntimeError('Chosen child must place exactly one piece')
                    row,column=map(int,changed[0])
                    if self.board[row,column]!=0 or after[row,column]!=self.player:
                        raise RuntimeError('Chosen child does not preserve legal empty-cell placement')
                else:
                    row,column=self.model.moves[chosen]
                    expected=self.game.apply_move(self.game_state,(row,column))
                    if not np.array_equal(after,expected['board']): raise RuntimeError('Chosen child differs from legacy Go successor')
                    self.game_state=expected
                move={'move':turn+1,'player':self.player,'row':row,'column':column,'node':chosen,
                    'visits':tree[chosen]['visits'],'core_cycles':result['metrics']['core_cycles'],
                    'core_latency_us':result['metrics']['core_latency_us'],
                    'sram_energy_uj':result['costs']['sram']['energy_uj'],
                    'result_sha256':json_sha256(result),'execution_sha256':result['identity']['execution_sha256'],
                    'board_before':self.board.tolist(),'board_after':after.tolist()}
                if self.game is not None:
                    move.update(pass_move=row==-1,captures=state_record(self.game_state)['captures'],go_state=state_record(self.game_state))
                if self.options is not None:
                    move.update(actor='opponent' if self.opponent=='engine' and self.player!=self.architecture_player else 'architecture',
                        search_iterations=turn_config['iterations'],model_id=turn_config.get('model_id','random_diagnostic'),seed=turn_config['seed'])
                if (current.is_current(self.config) or self.config['profile'].startswith('single_child_')):
                    move.update(search_iterations=self.model.completed,requested_iterations=turn_config['iterations'],
                        search_status=result['status'],termination=result.get('termination'))
                deterministic_moves.append(move)
                self.moves.append(move | {'search_run':out.name})
                self.board=after; self.player=-self.player
                self.cycles+=self.model.cycles
                self.operations.update(self.model.memory.operations); self.phase_cycles.update(self.model.phase_cycles)
                self.block_active_cycles.update(self.model.block_active_cycles)
                self.completed_iterations+=self.model.completed
                if current.is_current(self.config): self.reporting_basis=current.combine(self.reporting_basis,current.capture(self.model))
                write_json(self.out/'moves.json',self.moves)
                metadata['completed_moves']=len(self.moves); write_json(self.out/'metadata.json',metadata)
                self.termination=result.get('termination')
                on_move(self.moves[-1],self.model)
                if self.termination is not None: break
            if self.model is None: raise RunCancelled('Session ended before its first architecture search')
            if any(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest for name,digest in sources.items()):
                raise RuntimeError('Placement session source changed during execution')
            identity={'profile':PROFILE if self.game is None else 'legacy_go_play_v2','configuration_sha256':json_sha256(self.config),'source_sha256':sources,
                'search_execution_sha256':[row['execution_sha256'] for row in deterministic_moves],
                'decision_policy':'most_visited_root_child_then_first_row_major',
                'player_transform':'For each turn, multiply absolute board cells by the player sign; the unchanged core sees its mover as black',
                'initial_player':1,'tree_reuse':False,'weights':'Configured evaluator and any color transform retained in every underlying search'}
            if self.game is not None:
                identity['player_transform']='Absolute Black/White board channels; current player preserved in host Go state'
                identity['decision_policy']='most_visited_legal_root_child_then_row_major_then_pass'
                identity['initial_player']=self.config.get('go_state',{}).get('current_player',1)
            if self.options is not None:
                identity.update(session_profile=SESSION_PROFILE,opponent=self.opponent,opponent_configuration=self.opponent_config,
                    architecture_side=self.architecture_side,
                    search_execution_sha256=[row['execution_sha256'] for row in deterministic_moves if row['execution_sha256']])
            if self.config.get('readout_profile')==BUFFERED:
                identity['readout_profile']=BUFFERED
                identity['validation_scope']='Buffered digital core checked in RTL and generic gates with ideal interfaces; host move orchestration, analog accuracy and physical timing excluded'
                if self.game is not None: identity['validation_scope']+='; host Go rules and interfaces excluded'
            if self.model.neural.profile.get('turn_indicator'):
                identity['player_transform']='Absolute Black/White channels plus Black-to-play bit from the node player word'
                identity['validation_scope']='163-input component schedule checked in software; turn-aware control is outside retained RTL/synthesis evidence. Host Go rules and interfaces excluded.'
            if (current.is_current(self.config) or self.config['profile'].startswith('single_child_')):
                identity.update(expansion_policy=self.model.memory.config['policy'],
                    decision_policy='most_visited_root_child_then_first_allocated',
                    validation_scope='Single-child functional and packed-memory service model; incremental control RTL, physical timing and host rules remain unvalidated')
            latest=current.is_current(self.config)
            prepared=current.prepare(self.model) if latest else None
            if latest: identity.update(architecture=current.effective_architecture(prepared),validation_scope=current.datapath_spec()['timing_status'])
            identity['execution_sha256']=json_sha256(identity)
            result={'schema_version':1,'kind':'placement_play','status':'complete','publication_status':'diagnostic_not_task_validated',
                'identity':identity,'metrics':{'core_cycles':self.cycles,'core_latency_us':self.cycles/500,
                    'completed_iterations':self.completed_iterations,'completed_moves':len(self.moves),
                    'area_mm2':None,'power_mw':None,'energy_uj':None},
                'costs':current.costs(self.operations,self.cycles,self.block_active_cycles,self.reporting_basis,prepared) if latest else complete_costs(self.config['memory_profile'],self.operations,self.cycles,
                    self.model.neural.profile,self.model.memory.config,self.phase_cycles,self.block_active_cycles),
                'block_activity':current.activity(self.block_active_cycles,self.cycles) if latest else activity_record(dict(self.block_active_cycles),self.cycles),
                'phase_cycles':dict(self.phase_cycles),'operations':dict(self.operations),
                'moves':deterministic_moves,'final_board':self.board.tolist(),
                'boundary':'Sum of completed per-move preloaded core searches on one reused chip. Host choice/board commit, reset/preload and display pacing excluded.',
                'rules':'Alternating empty-cell placement only; no captures, ko, passing, scoring or trained game strength'}
            result['component_estimates']=self.model_estimates
            write_power_csv(self.out/'block_power.csv',result['costs']['block_power'])
            write_component_csv(self.out/'components.csv',result['costs']['ledger'])
            if self.game is not None:
                result.update(kind='legacy_go_play',publication_status='host_assisted_go_not_task_validated',
                    rules='Legacy Go: captures, suicide prevention, simple ko, passing, Chinese area scoring, komi 6.5',
                    final_state=state_record(self.game_state),final_score=list(self.game.score_position(self.board)),
                    boundary='Sum of mapped component work. Host Go rules, metadata, interfaces and display pacing excluded.')
                result['costs']['boundary']=result['boundary']
                result['costs']['timing']='Component schedule estimate; integrated Go RTL and physical timing unvalidated'
            if self.config.get('readout_profile')==BUFFERED:
                result['publication_status']='column_hold_candidate_not_physically_or_task_validated'
                result['costs']['timing']='Buffered digital schedule checked in RTL with ideal interfaces; physical timing, analog retention and host orchestration excluded'
                if self.game is not None: result['costs']['timing']+='; host Go processing and interfaces excluded'
            if self.model.neural.profile.get('turn_indicator'):
                result['costs']['timing']='163-input component schedule at assumed 500 MHz; turn-aware digital control and physical timing unvalidated'
            if self.options is not None:
                result.update(session_profile=SESSION_PROFILE,session=self.options,terminal=self.state()['terminal'],
                    cost_scope='All simulated engine searches on one reused chip; human input and thinking time excluded',
                    player_totals={str(player):{'core_cycles':sum(m['core_cycles'] for m in self.moves if m['player']==player),
                        'sram_energy_uj':sum(m['sram_energy_uj'] for m in self.moves if m['player']==player)} for player in (1,-1)})
            if (current.is_current(self.config) or self.config['profile'].startswith('single_child_')):
                result.update(status='memory_limited' if self.termination else 'complete',termination=self.termination,
                    expansion_policy=self.model.memory.config['policy'])
                result['costs']['timing']='Single-child architectural service estimate; incremental controller and physical timing unvalidated'
            if latest:
                result['costs']['timing']=current.datapath_spec()['timing_status']
                result['architecture']=current.effective_architecture(prepared)
                result['reporting_basis']=self.reporting_basis
            write_json(self.out/'component_estimates.json',result['component_estimates'])
            write_json(self.out/'result.json',result)
            fields=['move','player','row','column','node','visits','core_cycles','core_latency_us','sram_energy_uj','search_run','result_sha256']
            if self.options is not None: fields+=['actor','search_iterations','model_id','seed']
            if (current.is_current(self.config) or self.config['profile'].startswith('single_child_')):
                fields+=[key for key in ('search_iterations','requested_iterations','search_status') if key not in fields]
            with (self.out/'moves.csv').open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=fields); writer.writeheader()
                writer.writerows({key:move.get(key) for key in fields} for move in self.moves)
            summary={'profile':identity['profile'],'completed_moves':len(self.moves),'iterations_per_move':self.config['iterations'],
                'execution_profile':self.config['profile'],'tree_update_timing_profile':self.model.memory.config['tree_update_timing_profile'],
                'digital_source_commit':result['costs']['digital']['source_commit'],
                'readout_profile':self.config.get('readout_profile',DRIVEN),
                'core_cycles':self.cycles,'core_latency_us':self.cycles/500,
                'sram_energy_uj':result['costs']['sram']['energy_uj'],'sram_area_mm2':result['costs']['sram']['area_mm2'],
                'sram_average_power_mw':result['costs']['sram']['average_power_mw'],
                'digital_area_22nm_estimate_mm2':result['costs']['digital']['known_area_mm2'],
                'digital_area_65nm_subtotal_um2':result['costs']['digital']['known_native_65nm_area_um2'],
                'digital_priced_instances':result['costs']['digital']['priced_instances'],
                'digital_profile_sha256':result['costs']['digital']['profile_sha256'],
                'known_area_mm2':result['component_estimates']['known_area_mm2'],
                'whole_chip_area_mm2':None,'whole_chip_energy_uj':None,'whole_chip_power_mw':None}
            summary.update(digital_timing_fields(result['costs']['digital']))
            summary.update(ledger_fields(result['costs']))
            if self.options is not None: summary.update(session_profile=SESSION_PROFILE,architecture_side=self.architecture_side,opponent=self.opponent)
            if (current.is_current(self.config) or self.config['profile'].startswith('single_child_')):
                summary.update(status=result['status'],completed_iterations=self.completed_iterations,
                    expansion_policy=self.model.memory.config['policy'],termination_reason='' if not self.termination else self.termination['resource'])
            with (self.out/'summary.csv').open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(summary)); writer.writeheader(); writer.writerow(summary)
            metadata.update(status=result['status'],finished_utc=datetime.now(timezone.utc).isoformat(),result_sha256=json_sha256(result))
            write_json(self.out/'metadata.json',metadata)
            paths=sorted(p for p in self.out.rglob('*') if p.is_file())
            (self.out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(self.out))+'\n' for p in paths))
            return self.out,result
        except Exception as error:
            metadata.update(status='cancelled' if isinstance(error,RunCancelled) else 'failed',
                error=type(error).__name__+': '+str(error),completed_moves=len(self.moves),finished_utc=datetime.now(timezone.utc).isoformat())
            write_json(self.out/'metadata.json',metadata)
            raise
