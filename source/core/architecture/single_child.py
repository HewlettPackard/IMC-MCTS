# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Incremental expansion with a root-only first evaluation and finite SRAM.
# SPDX-License-Identifier: MIT
from types import SimpleNamespace

from core.architecture.go_simulation import GoSimulation
from core.architecture.iteration_model import CompleteSimulation
from core.architecture.ucb_arithmetic import next_choice, score
from core.simulator.incremental_memory import IncrementalMemory, POLICY, TIMING, incremental_config
from core.simulator.tree_memory import NO_NODE, memory_config
from py_sst_cpp.components.board_config import BoardSize, get_board_config

PROFILE='single_child_placement_q32_v1'
GO_PROFILE='single_child_go_host_rules_q32_v1'
TURN_PROFILE='single_child_go_turn_input_host_rules_q32_v1'


def preview_memory(profile):
    shape=SimpleNamespace(**vars(get_board_config(BoardSize(profile['board_size']))))
    shape.node_sram_kb=1536; shape.children_sram_kb=512
    return incremental_config(memory_config(shape,neural_scratch_bytes=profile['storage_bytes']))


class SingleChildPolicy:
    def __init__(self, *args, **kwargs):
        super().__init__(*args,memory_factory=IncrementalMemory,**kwargs)
        for key,field in [('nodes','node_capacity'),('edges','edge_capacity')]:
            requested=(kwargs.get('memory_limits') or {}).get(key)
            if requested is not None and requested!=self.memory.config[field]:
                raise ValueError(key+' quota exceeds single-child physical capacity')
        go=isinstance(self,GoSimulation)
        profile=GO_PROFILE if go else PROFILE
        if go and self.neural.profile.get('turn_indicator'): profile=TURN_PROFILE
        if go and self.memory.config['cam_entries']<self.board_size**2+1:
            raise ValueError('Go CAM must hold legal moves including pass')
        depth_bound=(self.game._max_moves-self.states[0]['move_count']+1 if go
            else int((self.initial_board==0).sum())+1)
        self.memory.config.update(execution_profile=profile,policy=POLICY,
            path_depth_bound=depth_bound,
            tree_update_timing_profile=TIMING,timing_status='architectural_service_estimate_not_RTL_validated',
            timing_source='SINGLE_CHILD_SPEC.md; new selection/expansion and memory control are not covered by prior RTL')
        self.termination=None

    def _actions(self, node_id):
        board=self.memory.read_board(node_id)
        if isinstance(self,GoSimulation):
            state=self.states[node_id]
            moves=[] if self.game.is_terminal(state) else self.game.get_legal_moves(state)
            actions=[self.board_size**2 if move==(-1,-1) else move[0]*self.board_size+move[1] for move in moves]
            self.memory.control('latch_host_legal_mask')
        else:
            actions=[i for i,cell in enumerate(board.flat) if cell==0]
            self.memory.control('scan_empty_positions',board.size)
        return self.memory.initialize_actions(node_id,actions)

    def _select(self):
        memory=self.memory; memory.reset_path(); current=0
        memory.control('selection_start',2)
        while True:
            node=memory.read_node(current); memory.push_path(current)
            memory.control('decode_node_and_branch',3)
            if not node['visits']: break
            remaining=memory.remaining(current)
            if remaining==NO_NODE: remaining=self._actions(current)
            memory.control('check_remaining_actions')
            if remaining or not node['children_count']: break
            children=memory.lookup_children(current,node)
            best=None; best_score=float('-inf')
            for child in children:
                candidate=memory.read_node(child); memory.stage_candidate(child,candidate)
                memory.control('candidate_control',4)
                if not candidate['visits']: best=child; break
                memory.compute('ucb')
                value=score(node['visits'],candidate['visits'],candidate['value'],self.exploration)
                if value>best_score: best=child; best_score=value
            if best is None: raise RuntimeError('No valid child in a nonempty list')
            current=best
        self.selected=current
        return memory.cursor-self.cycles

    def _expand(self):
        memory=self.memory; parent=self.selected; node=memory.read_node(parent)
        memory.control('expansion_start',2)
        if not node['visits']: return memory.cursor-self.cycles
        remaining=memory.remaining(parent)
        if remaining==NO_NODE: remaining=self._actions(parent)
        if not remaining: return memory.cursor-self.cycles
        memory.reserve_children(1); memory.check_path_room()
        mask=memory.action_mask(parent)
        actions=[i for i in range(memory.config['action_slots']) if mask&(1<<i)]
        if remaining!=len(actions): raise RuntimeError('Remaining-action count disagrees with bitmap')
        memory.control('scan_action_bitmap',memory.config['action_slots'])
        random=next_choice(self.random_state); action=actions[random%remaining]
        memory.control('xorshift_and_remainder',35)
        board=memory.read_board(parent)
        if isinstance(self,GoSimulation):
            move=(-1,-1) if action==self.board_size**2 else divmod(action,self.board_size)
            after=self.game.apply_move(self.states[parent],move); board=after['board']
        else: board.flat[action]=node['player']
        memory.control('apply_selected_move')
        child=memory.nodes_used
        memory.allocate_node(child,{'visits':0,'value':0.0,'parent':parent,
            'children':[],'board':board,'player':-node['player']})
        memory.append_child(parent,child)
        memory.consume_action(parent,action,remaining,mask)
        if isinstance(self,GoSimulation): self.states[child]=after; self.moves[child]=move
        self.random_state=random; self.selected=child; memory.push_path(child)
        return memory.cursor-self.cycles

    def steps(self):
        if self.status!='ready': raise RuntimeError('A simulation can run only once')
        self.status='running'
        try:
            for _ in range(self.iterations):
                phases=[]
                for name,action in [('selection',self._select),('expansion',self._expand),
                        ('neural',self._evaluate),('backpropagation',self._backprop)]:
                    row=self._phase(name,action); phases.append(row); yield row
                # One commit plus three registered allocation-budget comparisons.
                self.memory.begin('iteration_commit',self.completed+1,self.cycles)
                self.memory.control('commit_and_budget_check',4)
                self.cycles+=4; self.phase_cycles['iteration_commit']+=4
                self.block_active_cycles['top_level_glue']+=4; self.completed+=1
                row={'iteration':self.completed,'cycle_end':self.cycles,'selected_node':self.selected,
                    'value_q17':self.value_q17,'nodes':self.memory.nodes_used,'edges':self.memory.edges_used,
                    'random_state':self.random_state,'phase_cycles':{p['phase']:p['cycles'] for p in phases}}
                self.history.append(row)
                reason=self.memory.budget_reason() if self.completed<self.iterations else None
                if reason:
                    self.status='memory_limited'
                    self.termination=reason | {'reason':'memory_limit','requested_iterations':self.iterations,
                        'completed_iterations':self.completed,'boundary':'last_completed_iteration'}
                elif self.completed==self.iterations: self.status='complete'
                yield row | {'phase':'iteration_commit','cycles':4}
                if reason: return
        except Exception:
            self.status='failed'
            raise


class SingleChildSimulation(SingleChildPolicy,CompleteSimulation):
    pass


class SingleChildGoSimulation(SingleChildPolicy,GoSimulation):
    def application_record(self):
        result=super().application_record()
        result.update(profile=self.memory.config['execution_profile'],expansion_policy=POLICY,
            validation='Single-child functional Go adapter; incremental controller and Go rules have no integrated RTL proof')
        return result
