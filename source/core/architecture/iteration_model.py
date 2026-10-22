# Complete serialized digital-control profile, with ideal external memories/arrays.
# SPDX-License-Identifier: MIT
from collections import Counter
import contextlib
import hashlib
import io
import math
from numbers import Integral
from types import SimpleNamespace

import numpy as np

from core.architecture.accelerator_api import Accelerator
from core.architecture.neural_mapping import NeuralMapping
from core.architecture.ucb_arithmetic import PROFILE as UCB_PROFILE, next_choice, score
from core.architecture.tree_update_timing import PROFILE as TREE_UPDATE_PROFILE, expansion_cycles
from core.architecture.block_activity import BLOCKS, phase_activity
from core.simulator.tree_memory import TreeMemory, memory_config

PROFILE='complete_serial_q32_v2'


class CompleteSimulation:
    def __init__(self, board_size=9, iterations=5000, seed=0, memory_limits=None,
                 initial_board=None, exploration=1.414, cam_entries=None,
                 weights=None, memory_factory=TreeMemory, turn_indicator=False):
        if isinstance(board_size,bool) or not isinstance(board_size,Integral) or board_size not in (2,3,5,9):
            raise ValueError('Complete core supports integer sizes 2, 3, 5 and 9')
        for name,value,limit in [('iterations',iterations,2**32),('seed',seed,2**32)]:
            if isinstance(value,bool) or not isinstance(value,Integral) or not (0 if name=='seed' else 1)<=value<limit:
                raise ValueError(name+' is outside the unsigned 32-bit range')
        if not math.isfinite(exploration) or not 0<=exploration<=8 or math.copysign(1.0,exploration)<0:
            raise ValueError('Exploration must be in [0,8], using positive zero')
        self.board_size=board_size; self.iterations=int(iterations); self.seed=int(seed)
        self.exploration=float(exploration); self.random_state=self.seed or 0x6d2b79f5
        self.completed=0; self.cycles=0; self.phase_cycles=Counter(); self.history=[]
        self.block_active_cycles=Counter(dict.fromkeys(BLOCKS,0))
        self.selected=0; self.value_q17=0; self.status='ready'
        self.initial_board=np.zeros((board_size,board_size),dtype=np.int8) if initial_board is None else np.asarray(initial_board)
        if self.initial_board.shape!=(board_size,board_size) or not np.isin(self.initial_board,[-1,0,1]).all():
            raise ValueError('Initial board must contain only -1, 0 and 1 at the configured dimensions')
        self.initial_board=self.initial_board.astype(np.int8,copy=True)
        hidden=32 if board_size in (2,3) else 96
        generated=weights is None
        if turn_indicator and generated: raise ValueError('Turn-aware inference requires an explicit trained checkpoint')
        if generated:
            rng=np.random.RandomState(self.seed)
            weights=(rng.randn(2*board_size**2,hidden)*np.sqrt(2.0/(2*board_size**2)),
                rng.randn(hidden,3)*np.sqrt(2.0/hidden))
        self.weights=[np.asarray(w,dtype=np.float64) for w in weights]
        self.neural=NeuralMapping(*self.weights,board_size,sram_word_cycles=2,turn_indicator=turn_indicator)
        if self.neural.profile['hidden_size']>128: raise ValueError('Complete core requires one row tile in layer two')
        with contextlib.redirect_stdout(io.StringIO()): base=Accelerator(board_size=board_size).base_config
        shape=SimpleNamespace(**vars(base)); shape.node_sram_kb=1536; shape.children_sram_kb=512
        shape.cam_entries=base.cam_entries if cam_entries is None else cam_entries
        if isinstance(shape.cam_entries,bool) or not isinstance(shape.cam_entries,Integral): raise ValueError('CAM entries must be an integer')
        config=memory_config(shape,memory_limits,self.neural.profile['storage_bytes'])
        config.update(sram_word_cycles=2,cam_search_cycles=3,cam_row_write_cycles=3,cam_output_cycles=3,
            ucb_cycles=225,arithmetic=UCB_PROFILE,execution_profile=PROFILE,cam_row_bits=65,cam_payload_bits=64,
            tree_update_timing_profile=TREE_UPDATE_PROFILE,
            timing_status='RTL_checked_phase_cycle_model_with_ideal_interfaces',
            timing_source='COMPLETE_CORE_SPEC.md controller equations and native 22 nm SRAM service assumptions',
            trace_timing='ordered service costs with controller gaps aggregated at phase end')
        for name in ('expand_cycles','update_cycles','rollout_cycles'): config.pop(name)
        self.memory=memory_factory(config,{})
        self.neural.bind_memory(self.memory)
        self.memory.allocate_node(0,{'visits':0,'value':0.0,'parent':-1,'children':[],
            'board':self.initial_board,'player':1})
        lut=self.neural.profile['storage']['exp_lut']
        self.memory.transfer('node_sram','write',config['neural_base']+lut['offset'],lut['bytes'])
        self.preload_operations=dict(self.memory.operations)
        self.memory.cursor=0; self.memory.operations.clear(); self.memory.phase_operations.clear()
        self.memory.phase_cycles.clear(); self.memory.transactions.clear()
        self.memory.schedule_hash=hashlib.sha256()
        self.evaluator={'mode':'random_diagnostic' if generated else 'explicit_weights_diagnostic',
            'weight_sha256':[hashlib.sha256(w.tobytes()).hexdigest() for w in self.weights],
            'coefficients':self.neural.coefficients,'input_encoding':'interleaved_black_white',
            'output_order':['white','draw','black'],'value_perspective':'black',
            'task_accuracy':'unvalidated'}
        if turn_indicator: self.evaluator['input_encoding']='interleaved_black_white_then_black_to_play'
    def _phase(self, name, action):
        self.memory.begin(name,self.completed+1,self.cycles)
        before=self.memory.operations.copy()
        duration=action()
        remainder=self.cycles+duration-self.memory.cursor
        if remainder<0: raise AssertionError('Controller schedule is shorter than its services')
        self.memory._record('controller','aggregated_control_and_compute',0,0,0,remainder)
        self.cycles+=duration; self.phase_cycles[name]+=duration
        self.block_active_cycles.update(phase_activity(name,duration,self.memory.operations-before))
        return {'phase':name,'iteration':self.completed+1,'cycles':duration,'cycle_end':self.cycles,
            'selected_node':self.selected,'path_depth':self.memory.path_depth,
            'nodes':self.memory.nodes_used,'edges':self.memory.edges_used,
            'cam_rows':sum(len(item[1]) for item in self.memory.cam.values())}

    def _select(self):
        memory=self.memory; memory.reset_path(); current=0; cycles=0
        while True:
            node=memory.read_node(current); memory.push_path(current); cycles+=24
            if not node['visits'] or not node['children_count']: break
            miss=current not in memory.cam; groups=len(memory.cam)
            evicted_before=memory.operations['cam_evicted_rows']
            children=memory.lookup_children(current,node)
            evicted_groups=groups+int(miss)-len(memory.cam)
            evicted_rows=memory.operations['cam_evicted_rows']-evicted_before
            cycles+=5+14+5*len(children)
            if miss: cycles+=22+9*len(children)+14*evicted_groups+5*evicted_rows
            best=None; best_score=float('-inf')
            for child in children:
                candidate=memory.read_node(child); memory.stage_candidate(child,candidate); cycles+=46
                if candidate['visits']==0:
                    best=child; break
                memory.compute('ucb'); cycles+=225
                value=score(node['visits'],candidate['visits'],candidate['value'],self.exploration)
                if value>best_score: best=child; best_score=value
            if best is None: raise RuntimeError('Nonempty child list has no valid candidate')
            current=best
        self.selected=current
        return cycles+2

    def _expand(self):
        memory=self.memory; node=memory.read_node(self.selected)
        if not node['visits'] or node['children_count']: return 22
        board=memory.read_board(self.selected); count=int(np.count_nonzero(board==0))
        memory.reserve_children(count)
        if count: memory.check_path_room()
        words=memory.config['board_bytes']//4
        if not count: return expansion_cycles(words,count)
        children=[]
        for position in range(board.size):
            if board.flat[position]==0:
                child_board=board.copy(); child_board.flat[position]=node['player']
                child=memory.nodes_used
                memory.transfer('node_sram','read',memory.config['working_offset'],memory.config['board_bytes'])
                memory.allocate_node(child,{'visits':0,'value':0.0,'parent':self.selected,'children':[],
                    'board':child_board,'player':-node['player']})
                children.append(child)
        memory.attach_children(self.selected,children)
        self.random_state=next_choice(self.random_state)
        self.selected=children[self.random_state%len(children)]; memory.push_path(self.selected)
        return expansion_cycles(words,count)

    def board(self, node_id):
        address=self.memory.node_address(node_id)+24
        packed=int.from_bytes(self.memory.node_sram[address:address+self.memory.config['board_bytes']],'little')
        board=np.zeros((self.board_size,self.board_size),dtype=np.int8)
        for index in range(board.size):
            cell=(packed>>(2*index))&3
            if cell==3: raise ValueError('Invalid packed board cell')
            board.flat[index]=-1 if cell==2 else cell
        return board

    def _evaluate(self):
        memory=self.memory; model=self.neural
        if model.profile.get('turn_indicator'):
            model.forward(self.board(self.selected),player=memory._node_fields(self.selected)['player'])
        else: model.forward(self.board(self.selected))
        self.value_q17=model.last_state['value_q17']
        for row in model.inference_trace(resource='node_sram'):
            if row['region']=='player': base=memory.node_address(self.selected)+20
            elif row['region']=='board': base=memory.node_address(self.selected)+24
            else: base=memory.config['neural_base']+model.profile['storage'][row['region']]['offset']
            memory.transfer('node_sram','write' if 'write' in row['operation'] else 'read',base+row['address'],row['bytes'])
        memory.count('rollout_operations')
        for name,count in model.schedule['operations'].items():
            if not name.startswith('node_sram_'): memory.count('neural_'+name,count)
        operations=model.schedule['operations']
        return model.schedule['cycles']+operations['node_sram_read_words']+operations['node_sram_write_words']+operations['adc_groups']+3+2

    def _backprop(self):
        memory=self.memory; depth=memory.path_depth
        while memory.path_depth:
            node_id=memory.pop_path(); node=memory.read_node(node_id)
            increment=self.value_q17/131072 if node['player']==1 else 1-self.value_q17/131072
            memory.update_stats(node_id,node['visits']+1,node['value']+increment)
        return 35*depth+2

    def steps(self):
        if self.status!='ready': raise RuntimeError('A simulation can run only once')
        self.status='running'
        try:
            for _ in range(self.iterations):
                phases=[]
                for name,action in [('selection',self._select),('expansion',self._expand),('neural',self._evaluate),('backpropagation',self._backprop)]:
                    row=self._phase(name,action); phases.append(row); yield row
                self.cycles+=1; self.phase_cycles['iteration_commit']+=1
                self.block_active_cycles['top_level_glue']+=1
                self.completed+=1
                row={'iteration':self.completed,'cycle_end':self.cycles,'selected_node':self.selected,
                    'value_q17':self.value_q17,'nodes':self.memory.nodes_used,'edges':self.memory.edges_used,
                    'random_state':self.random_state,'phase_cycles':{p['phase']:p['cycles'] for p in phases}}
                self.history.append(row)
                yield row | {'phase':'iteration_commit'}
            self.status='complete'
        except Exception:
            self.status='failed'
            raise
