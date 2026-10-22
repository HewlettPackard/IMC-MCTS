# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Board-sized initialization reuses the reference arithmetic and execution methods.
# SPDX-License-Identifier: MIT
from collections import Counter
import hashlib
import math
from numbers import Integral

import numpy as np

from core.architecture.neural_mapping import NeuralMapping
from core.architecture.ucb_arithmetic import PROFILE as UCB_PROFILE, next_choice, score
from core.architecture.tree_update_timing import PROFILE as TREE_UPDATE_PROFILE, expansion_cycles
from core.architecture.block_activity import BLOCKS, phase_activity
from core.simulator.tree_memory import TreeMemory, memory_config

from core.architecture.iteration_model import CompleteSimulation, PROFILE
from core.architecture.go_simulation import GoSimulation
from core.architecture.single_child import SingleChildPolicy
from core.architecture.board_sizing import PROFILE as HARDWARE_PROFILE, board_hardware, sized_memory


class SizedInitialization(CompleteSimulation):
    def __init__(self, board_size=9, iterations=5000, seed=0, memory_limits=None,
                 initial_board=None, exploration=1.414, cam_entries=None,
                 weights=None, memory_factory=TreeMemory, turn_indicator=False):
        if isinstance(board_size,bool) or not isinstance(board_size,Integral) or board_size not in (2,3,5,9,13,19):
            raise ValueError('Board-sized core supports integer sizes 2, 3, 5, 9, 13 and 19')
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
        shape=board_hardware(board_size)
        if cam_entries is not None and (type(cam_entries) is not int or cam_entries!=shape['cam_entries']):
            raise ValueError('CAM override conflicts with the selected board hardware')
        config=sized_memory(self.neural.profile,memory_limits,
            'legacy_go' if isinstance(self,GoSimulation) else 'placement',incremental=False)
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


class SizedProfile:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.memory.config['execution_profile'] += '_board_sized_s1_v1'
        self.memory.config['hardware_profile'] = HARDWARE_PROFILE


class SizedSingleChildSimulation(SizedProfile, SingleChildPolicy, SizedInitialization):
    pass


class SizedGoBase(GoSimulation, SizedInitialization):
    pass


class SizedSingleChildGoSimulation(SizedProfile, SingleChildPolicy, SizedGoBase):
    pass
