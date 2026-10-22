# Legacy Go supplies legal successor states to the mapped search components.
# SPDX-License-Identifier: MIT
import struct

import numpy as np

from core.architecture.iteration_model import CompleteSimulation
from core.architecture.ucb_arithmetic import next_choice
from core.architecture.tree_update_timing import expansion_cycles
from core.simulator.tree_memory import TreeMemory
from tournament.go_compiled.engine.go_engine import GoEngine

PROFILE='legacy_go_host_rules_q32_v3'
TURN_PROFILE='legacy_go_turn_input_host_rules_q32_v1'
RULES_SOURCE='tournament/go_compiled/engine/go_engine.py'


class LegacyGo(GoEngine):
    def __init__(self, board_size):
        super().__init__(board_size=board_size,komi=6.5)
        self._use_c=False

    def apply_move(self, state, move, lightweight=False):
        # The legacy lightweight path aliases the caller's history set.
        result=super().apply_move(state,move,lightweight=False)
        if move==(-1,-1): result['ko_hash']=None
        return result

    def is_legal(self, state, r, c, player):
        if not (0<=r<self.board_size and 0<=c<self.board_size): return False
        if not super().is_legal(state,r,c,player): return False
        if state['ko_hash'] is not None:
            candidate=state['board'].copy(); candidate[r,c]=player
            self._capture_dead_groups(candidate,-player)
            if self._board_hash(candidate)==state['ko_hash']: return False
        return True


def state_record(state):
    return {'current_player':state['current_player'],'ko_hash':state['ko_hash'],
        'consecutive_passes':state['consecutive_passes'],'move_count':state['move_count'],
        'captures':{str(k):int(v) for k,v in state['captures'].items()}}


def initial_state(engine, board, record=None):
    state=engine.initial_state(); state['board']=np.asarray(board,dtype=np.int8).copy()
    if record is not None:
        if not isinstance(record,dict) or set(record)!=set(state_record(state)):
            raise ValueError('Go state must declare player, ko, pass count, move count and captures')
        if type(record['current_player']) is not int or record['current_player'] not in (-1,1):
            raise ValueError('Invalid Go player')
        for key,limit in [('consecutive_passes',2),('move_count',engine._max_moves)]:
            if type(record[key]) is not int or not 0<=record[key]<=limit: raise ValueError('Invalid Go '+key)
        ko=record['ko_hash']
        if ko is not None and (type(ko) is not int or not 0<=ko<2**63): raise ValueError('Invalid Go ko hash')
        if not isinstance(record['captures'],dict) or set(record['captures'])!={'1','-1'}:
            raise ValueError('Invalid Go captures')
        if any(type(v) is not int or v<0 for v in record['captures'].values()): raise ValueError('Invalid Go captures')
        state.update(record); state['captures']={int(k):v for k,v in record['captures'].items()}
    return state


class GoMemory(TreeMemory):
    def reserve_children(self, count):
        if not 0<=count<=self.config['board_size']**2+1: raise ValueError('Invalid Go child count')
        if self.nodes_used+count>self.config['node_capacity']: raise MemoryError('Go node capacity exceeded')
        if self.edges_used+count>self.config['edge_capacity']: raise MemoryError('Go child-pointer capacity exceeded')
        if count>self.config['cam_entries']: raise MemoryError('Go child list including pass exceeds CAM capacity')


class GoSimulation(CompleteSimulation):
    def __init__(self, *args, go_state=None, memory_factory=GoMemory, **kwargs):
        super().__init__(*args,memory_factory=memory_factory,**kwargs)
        self.game=LegacyGo(self.board_size)
        state=initial_state(self.game,self.initial_board,go_state)
        if self.game.is_terminal(state): raise ValueError('The initial Go position is already terminal')
        self.states={0:state}; self.moves={}; self.terminal_evaluations=0
        player=state['current_player']; self.memory.nodes[0]['player']=player
        struct.pack_into('<H',self.memory.node_sram,self.memory.node_address(0)+22,int(player==-1))
        self.memory.config.update(execution_profile=PROFILE,timing_status='host_assisted_component_schedule_not_complete_Go_RTL',
            policy='expand_all_legal_Go_successors_including_pass',
            node_value_perspective='player_to_move',
            host_rules='Legacy captures, suicide, simple ko, passes and Chinese area scoring with 6.5 komi',
            host_state='Ko/pass/capture/move metadata and legal successor computation are outside modeled chip storage and timing')
        self.workload='legacy_go_captures_ko_pass_chinese_area_v1'
        if self.neural.profile.get('turn_indicator'):
            self.memory.config.update(execution_profile=TURN_PROFILE,
                timing_status='turn_input_host_assisted_component_schedule_not_Go_RTL')

    def _expand(self):
        memory=self.memory; node=memory.read_node(self.selected); state=self.states[self.selected]
        if not node['visits'] or node['children_count'] or self.game.is_terminal(state): return 22
        memory.read_board(self.selected)
        moves=self.game.get_legal_moves(state); count=len(moves)
        memory.reserve_children(count); memory.check_path_room()
        words=memory.config['board_bytes']//4; children=[]
        for move in moves:
            after=self.game.apply_move(state,move); child=memory.nodes_used
            memory.transfer('node_sram','read',memory.config['working_offset'],memory.config['board_bytes'])
            memory.allocate_node(child,{'visits':0,'value':0.0,'parent':self.selected,'children':[],
                'board':after['board'],'player':after['current_player']})
            self.states[child]=after; self.moves[child]=move; children.append(child)
        memory.attach_children(self.selected,children)
        self.random_state=next_choice(self.random_state)
        self.selected=children[self.random_state%count]; memory.push_path(self.selected)
        return expansion_cycles(words,count)

    def _evaluate(self):
        cycles=super()._evaluate()
        if self.game.is_terminal(self.states[self.selected]):
            self.value_q17=int(self.game.get_result_black(self.states[self.selected])*131072)
            self.terminal_evaluations+=1
        return cycles

    def application_record(self):
        return {'rules':self.workload,'profile':TURN_PROFILE if self.neural.profile.get('turn_indicator') else PROFILE,'komi':self.game.komi,
            'initial_state':state_record(self.states[0]),'terminal_evaluations':self.terminal_evaluations,
            'node_states':{str(n):state_record(state) for n,state in self.states.items()},
            'node_moves':{str(n):list(move) for n,move in self.moves.items()},
            'node_value_perspective':'player_to_move',
            'selection_value':'player_to_move_value; UCB complements the child mean for the selecting parent',
            'terminal_policy':'Evaluator still executes; host-scored terminal result replaces its value for backpropagation',
            'validation':'Functional Go adapter; no integrated Go-rule RTL or physical latency validation',
            'unbilled':['host legality/capture/ko/scoring computation','host metadata storage and successor delivery','host terminal-value override']}
