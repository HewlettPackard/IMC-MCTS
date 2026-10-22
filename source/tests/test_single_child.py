# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
# Incremental search must agree with a list-based policy oracle and packed SRAM.
import struct
import tempfile
from pathlib import Path
import unittest

import numpy as np

from core.architecture.go_simulation import LegacyGo, state_record
from core.architecture.neural_mapping import NeuralMapping
from core.architecture.single_child import SingleChildSimulation, SingleChildGoSimulation
from core.architecture.ucb_arithmetic import score
from core.architecture.result_registry import ROOT, configuration, run_case, verify_run
from core.architecture.result_snapshot import freeze_repeats
from core.architecture.complete_costs import complete_costs
from core.simulator.tree_memory import NO_NODE
from p03_experiments.p61_single_child.reference import Reference


def compare_reference(test, model):
    mapper=NeuralMapping(*model.weights,model.board_size,
        turn_indicator=model.neural.profile.get('turn_indicator',False))
    def evaluate(board,player):
        mapper.forward(board,player=player) if mapper.profile.get('turn_indicator') else mapper.forward(board)
        return mapper.last_state['value_q17']
    game=getattr(model,'game',None)
    ref=Reference(model.initial_board,evaluate,model.seed,model.exploration,game,
        None if game is None else model.states[0])
    previous=1
    for event in model.steps():
        if event['phase']!='iteration_commit': continue
        expected=ref.step()
        test.assertEqual(model.selected,expected['selected'])
        test.assertEqual(model.value_q17,expected['value_q17'])
        test.assertEqual(model.random_state,expected['random_state'])
        test.assertEqual(model.memory.nodes_used,expected['nodes'])
        test.assertLessEqual(model.memory.nodes_used-previous,1)
        previous=model.memory.nodes_used
    for n,expected in enumerate(ref.nodes):
        actual=model.memory.nodes[n]
        for key in ('visits','value','parent','children','player'): test.assertEqual(actual[key],expected[key],(n,key))
        np.testing.assert_array_equal(model.board(n),expected['board'])
    test.assertEqual(model.memory.nodes[0]['visits'],model.completed)
    test.assertEqual(sum(model.phase_cycles.values()),model.cycles)
    test.assertEqual(model.memory.path_depth,0)
    test.assertEqual(model.memory.cursor,model.cycles)
    return ref


class SingleChildTests(unittest.TestCase):
    def test_studio_refreshes_cost_context_between_same_weight_searches(self):
        from p05_studio.p00_app.server import Job
        config=configuration({'board_size':2,'iterations':2})
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            job=Job(config,'test',False,Path(folder)/'runs',options={'speed':100})
            for i,board in enumerate(([[0,0],[0,0]],[[1,0],[0,0]])):
                model=SingleChildSimulation(2,2,initial_board=board)
                job.observe({'phase':'ready','iteration':0,'cycle_end':0,'run':str(i)},model)
                for event in model.steps(): job.observe(event|{'run':str(i)},model)
                expected=complete_costs(config['memory_profile'],model.memory.operations,model.cycles,
                    model.neural.profile,model.memory.config,model.phase_cycles,model.block_active_cycles)
                self.assertEqual(job.payload()['live_costs'],expected)

    def test_partial_budget_is_saved_but_not_promoted(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            runs=Path(folder)/'runs'
            pairs=[run_case(custom={'board_size':2,'iterations':50,'memory_limits':{'nodes':3}},runs=runs) for _ in range(2)]
            self.assertEqual(pairs[0][1],pairs[1][1])
            self.assertEqual(verify_run(pairs[0][0])['status'],'memory_limited')
            self.assertEqual(pairs[0][1]['metrics']['completed_iterations'],3)
            self.assertEqual(pairs[0][1]['metrics']['requested_iterations'],50)
            self.assertFalse((runs.parent/'index.json').exists())
            with self.assertRaises(ValueError): freeze_repeats([(pairs[0][0],pairs[1][0])],Path(folder)/'snapshots')

    def test_both_readouts_keep_new_policy_and_honest_coverage(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            a,driven=run_case(custom={'board_size':2,'iterations':5},runs=Path(folder)/'runs')
            b,held=run_case(custom={'board_size':2,'iterations':5,'readout_profile':'column_hold_v1'},runs=Path(folder)/'runs')
            self.assertEqual(driven['tree_sha256'],held['tree_sha256'])
            self.assertEqual(held['metrics']['core_cycles']-driven['metrics']['core_cycles'],5*held['analog_readout']['additional_capture_cycles'])
            for result in (driven,held):
                self.assertEqual(result['memory']['nodes_used'],5)
                self.assertEqual(result['neural']['profile']['timing_status'],'single_child_architectural_services_not_RTL_validated')
                rows={row['id']:row for row in result['costs']['ledger']['components']}
                for parent in ('u_sel','u_upd','top_level_glue'):
                    self.assertIsNone(rows[parent]['area_um2']);self.assertIsNone(rows[parent]['energy_uj'])

    def test_root_only_then_one_child_on_each_revisit(self):
        model=SingleChildSimulation(2,5)
        counts=[]
        for event in model.steps():
            if event['phase']=='iteration_commit': counts.append((model.memory.nodes_used,len(model.memory.nodes[0]['children'])))
        self.assertEqual(counts,[(1,0),(2,1),(3,2),(4,3),(5,4)])
        self.assertEqual(sum(model.memory.nodes[n]['visits'] for n in model.memory.nodes[0]['children']),4)

    def test_placement_matches_independent_policy(self):
        for size,iterations in [(2,30),(3,45),(5,50),(9,100)]:
            for seed in (0,7):
                with self.subTest(size=size,seed=seed):
                    compare_reference(self,SingleChildSimulation(size,iterations,seed=seed))

    def test_go_matches_reference_for_both_players_and_passes(self):
        for player in (1,-1):
            for seed in (0,13):
                state=LegacyGo(3).initial_state(); state['current_player']=player
                state['consecutive_passes']=1; state['move_count']=1
                model=SingleChildGoSimulation(3,50,seed=seed,go_state=state_record(state))
                compare_reference(self,model)
                root=model.memory.nodes[0]
                moves=[model.moves[n] for n in root['children']]
                self.assertEqual(len(set(moves)),10)
                self.assertIn((-1,-1),moves)
                self.assertGreater(model.terminal_evaluations,0)

    def test_terminal_placement_reuses_nodes_without_duplicates(self):
        model=SingleChildSimulation(2,100,initial_board=[[1,-1],[1,0]])
        compare_reference(self,model)
        self.assertEqual(model.status,'complete')
        self.assertEqual(model.memory.nodes_used,2)
        self.assertEqual(model.memory.nodes[1]['visits'],99)

    def test_full_natural_path_does_not_stop_terminal_revisits(self):
        model=SingleChildSimulation(2,100)
        compare_reference(self,model)
        self.assertEqual(model.memory.path_high_water,5)
        self.assertEqual(model.memory.config['path_entries'],5)
        self.assertEqual(model.status,'complete')
        self.assertEqual(model.completed,100)

    def test_capacity_stops_after_a_complete_iteration(self):
        for limits,completed,resource in [({'nodes':3},3,'nodes'),({'edges':2},3,'edges'),({'path_entries':1},1,'path')]:
            with self.subTest(limits=limits):
                model=SingleChildSimulation(2,50,memory_limits=limits)
                compare_reference(self,model)
                self.assertEqual(model.status,'memory_limited')
                self.assertEqual(model.completed,completed)
                self.assertEqual(model.termination['resource'],resource)
                self.assertEqual(model.termination['requested_iterations'],50)
                self.assertEqual(len(model.history),completed)
                self.assertEqual(model.phase_cycles['iteration_commit'],4*completed)
        model=SingleChildSimulation(2,3,memory_limits={'nodes':3})
        compare_reference(self,model)
        self.assertEqual(model.status,'complete')
        self.assertIsNone(model.termination)

    def test_failed_preflight_does_not_consume_move_or_randomness(self):
        model=SingleChildSimulation(2,2,memory_limits={'nodes':1})
        model.memory.update_stats(0,1,.5)
        model.cycles=model.memory.cursor
        model._phase('selection',model._select)
        before=bytes(model.memory.node_sram),bytes(model.memory.child_sram),model.random_state
        model.memory.begin('expansion',1,model.cycles)
        with self.assertRaises(MemoryError): model._expand()
        self.assertEqual(before,(bytes(model.memory.node_sram),bytes(model.memory.child_sram),model.random_state))
        self.assertEqual(model.memory.nodes_used,1)

    def test_packed_links_actions_and_traffic_are_complete(self):
        model=SingleChildGoSimulation(3,35); memory=model.memory; memory.capture_trace=True
        compare_reference(self,model)
        self.assertEqual(len(memory.node_sram),1536*1024)
        self.assertEqual(len(memory.child_sram),512*1024)
        self.assertEqual(memory.summary()['child_bytes_used'],8*memory.edges_used)
        for n,node in memory.nodes.items():
            fields=memory._node_fields(n); edge=fields['children_start']; children=[]
            for _ in range(fields['children_count']):
                child,edge=struct.unpack_from('<II',memory.child_sram,edge*8); children.append(child)
            self.assertEqual(edge,NO_NODE)
            self.assertEqual(children,node['children'])
            address=memory.action_address(n)
            remaining,tail=struct.unpack_from('<II',memory.node_sram,address)
            mask=int.from_bytes(memory.node_sram[address+8:address+8+memory.config['action_mask_bytes']],'little')
            if remaining!=NO_NODE:
                legal=[] if model.game.is_terminal(model.states[n]) else model.game.get_legal_moves(model.states[n])
                used=[model.moves[c] for c in children]
                expected=[m for m in legal if m not in used]
                self.assertEqual(remaining,len(expected)); self.assertEqual(remaining,mask.bit_count())
                self.assertEqual(mask,sum(1<<(9 if m==(-1,-1) else m[0]*3+m[1]) for m in expected))
            if children: self.assertEqual(struct.unpack_from('<I',memory.child_sram,tail*8)[0],children[-1])
        for resource in ('node_sram','child_sram'):
            capacity=memory.config[resource+'_bytes']
            for operation in ('read','write'):
                rows=[row for row in memory.transactions if row['resource']==resource and row['operation']==operation]
                self.assertEqual(sum(row['words'] for row in rows),memory.operations[resource+'_'+operation+'_words'])
                self.assertTrue(all(0<=r['address']<r['address']+r['bytes']<=capacity for r in rows))

    def test_append_invalidates_cached_partial_parent(self):
        model=SingleChildSimulation(2,2); list(model.steps()); memory=model.memory
        parent=memory._node_fields(0)
        self.assertEqual(memory.lookup_children(0,parent),[1])
        board=model.board(0); board.flat[0]=1
        memory.allocate_node(2,{'visits':0,'value':0.0,'parent':0,'children':[],'board':board,'player':-1})
        memory.append_child(0,2)
        self.assertNotIn(0,memory.cam)
        self.assertEqual(memory.lookup_children(0),[1,2])
        self.assertEqual(memory.operations['cam_growth_flushes'],1)
        self.assertGreater(memory.operations['cam_evicted_rows'],0)

    def test_remaining_bitmap_overhead_reduces_physical_capacity(self):
        model=SingleChildSimulation(9,1); config=model.memory.config
        self.assertEqual(config['node_stride'],68)
        self.assertEqual(config['action_mask_bytes'],12)
        self.assertEqual(config['child_record_bytes'],8)
        self.assertEqual(config['node_capacity'],(1536*1024-config['node_base'])//68)
        self.assertEqual(config['edge_capacity'],512*1024//8)
        with self.assertRaises(ValueError): SingleChildSimulation(9,1,memory_limits={'nodes':30000})
        old_capacity=(1536*1024-config['node_base'])//48
        with self.assertRaises(ValueError): SingleChildSimulation(9,1,memory_limits={'nodes':old_capacity})
        with self.assertRaises(ValueError): SingleChildSimulation(9,1,memory_limits={'edges':131072})

    def test_selection_value_remains_parent_relative(self):
        for player in (1,-1):
            state=LegacyGo(2).initial_state(); state['current_player']=player
            model=SingleChildGoSimulation(2,6,go_state=state_record(state))
            list(model.steps()); memory=model.memory
            children=memory.nodes[0]['children']
            for i,child in enumerate(children): memory.update_stats(child,1,i/(len(children)-1))
            expected=max(children,key=lambda c:score(memory.nodes[0]['visits'],1,memory.nodes[c]['value'],model.exploration))
            model.cycles=memory.cursor
            model._phase('selection',model._select)
            self.assertEqual(model.selected,expected)


if __name__=='__main__': unittest.main()
