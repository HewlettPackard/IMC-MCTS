# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Apply the same installed-memory table to the preserved optimized figure harness.
# SPDX-License-Identifier: MIT
from copy import deepcopy
import hashlib,json,time
from pathlib import Path
from core.algorithm.model_catalog import load_model
from core.architecture.board_sizing import PROFILE,board_table,sized_memory
from core.architecture.run_identity import tree_sha256
from core.simulator.incremental_memory import IncrementalMemory
from p03_experiments.p79_scalability.model import DiagnosticSearch


class SizedOptimizedSearch(DiagnosticSearch):
    def __init__(self, board, iterations, seed=0, weights=None):
        super().__init__(board,iterations,seed,weights)
        previous=deepcopy(self.memory.config)
        layout=sized_memory(self.neural.profile,rules='legacy_go',incremental=False)
        # Construct the physical single-port memories first; the UCB batch owns
        # its four independent arithmetic lanes, without adding memory ports.
        config=previous|layout
        for key in ('expand_cycles','update_cycles','rollout_cycles'):config.pop(key,None)
        self.memory=IncrementalMemory(config,{})
        self.neural.bind_memory(self.memory)
        self.memory.allocate_node(0,{'visits':0,'value':0.0,'parent':-1,'children':[],
            'board':self.initial_board,'player':1})
        lut=self.neural.profile['storage']['exp_lut']
        self.memory.transfer('node_sram','write',config['neural_base']+lut['offset'],lut['bytes'])
        self.preload_operations=dict(self.memory.operations)
        self.memory.cursor=0;self.memory.operations.clear();self.memory.phase_operations.clear()
        self.memory.phase_cycles.clear();self.memory.transactions.clear();self.memory.schedule_hash=hashlib.sha256()
        self.memory.config.update(ucb_lanes=4,execution_profile=previous['execution_profile']+'_'+PROFILE,
            path_depth_bound=self.game._max_moves+1,timing_status='Board-sized optimized architectural services; not physical closure')


if __name__=='__main__':
    root=Path.cwd();out=root/json.loads((Path(__file__).parent/'latest.json').read_text())['run']
    checks=[]
    for name in ('go_strong_v1','go_weak_v1'):
        weights,_=load_model(name,9)
        models=[engine(9,100,weights=weights) for engine in (DiagnosticSearch,SizedOptimizedSearch)]
        for model in models:list(model.steps())
        a,b=models
        assert a.history==b.history
        assert a.neural.last_state==b.neural.last_state
        assert tree_sha256(a.memory.nodes)==tree_sha256(b.memory.nodes)
        assert a.memory.operations==b.memory.operations
        checks.append({'model':name,'iterations':100,'identical_tree_outputs_cycles_and_traffic':True})
    rows=[]
    for shape in board_table()['boards']:
        board=shape['board_size'];budget=shape['iterations']['high'];start=time.monotonic()
        model=SizedOptimizedSearch(board,budget)
        for event in model.steps():pass
        assert model.status=='complete' and model.completed==budget,(board,model.status,model.termination)
        assert model.memory.nodes[0]['visits']==budget
        assert model.memory.nodes_used<=model.memory.config['node_capacity']
        assert model.memory.path_high_water<=model.memory.config['path_storage_entries']
        assert sum(model.phase_cycles.values())==model.cycles
        rows.append({'board_size':board,'iterations':budget,'completed':model.completed,'status':model.status,
            'memory':model.memory.config,'nodes':model.memory.nodes_used,'edges':model.memory.edges_used,
            'path_high_water':model.memory.path_high_water,'cycles':model.cycles,'phase_cycles':dict(model.phase_cycles),
            'neural_profile':model.neural.profile,'tree_sha256':tree_sha256(model.memory.nodes),'wall_seconds':time.monotonic()-start})
        (out/'optimized_high_budget_results.json').write_text(json.dumps({'prefix_checks':checks,'rows':rows},indent=2)+'\n')
        print(board,'PASS',budget,'nodes',model.memory.nodes_used,'path',model.memory.path_high_water,flush=True)
    print('PASS: same table for all six optimized figure configurations',flush=True)
