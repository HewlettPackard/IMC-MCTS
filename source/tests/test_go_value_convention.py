# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import math
from collections import Counter
from pathlib import Path
import tempfile
import unittest

from core.architecture.go_simulation import GoSimulation, LegacyGo, state_record
from core.architecture.result_registry import ROOT, configuration
from p05_studio.p00_app.placement_play import BoardPlay
from p05_studio.p00_app.server import Job


def two_choices(player, outcomes, visits=(1,1), exploration=0):
    state=LegacyGo(3).initial_state(); state['current_player']=player
    model=GoSimulation(board_size=3,iterations=1,exploration=exploration,go_state=state_record(state))
    memory=model.memory
    for child in (1,2):
        board=model.initial_board.copy(); board.flat[child-1]=player
        memory.allocate_node(child,{'visits':0,'value':0.0,'parent':0,'children':[],
            'board':board,'player':-player})
    memory.attach_children(0,[1,2])
    for child,(outcome,count) in enumerate(zip(outcomes,visits),1):
        for _ in range(count):
            memory.reset_path(); memory.push_path(0); memory.push_path(child)
            model.value_q17=round(outcome*131072)
            model._backprop()
    return model


class GoValueConventionTests(unittest.TestCase):
    def test_parent_prefers_its_own_win_for_both_colors_and_orders(self):
        for player in (1,-1):
            for outcomes in ([1,0],[0,1]):
                for exploration in (0,1.414):
                    with self.subTest(player=player,outcomes=outcomes,exploration=exploration):
                        model=two_choices(player,outcomes,exploration=exploration)
                        model._select()
                        self.assertEqual(model.selected,outcomes.index(1 if player==1 else 0)+1)

    def test_unequal_visits_and_draws_match_independent_parent_ucb(self):
        for player in (1,-1):
            for outcomes,visits in [([.25,.75],[1,12]),([.5,1],[8,2]),([0,.5],[3,9])]:
                for exploration in (0,1.414):
                    with self.subTest(player=player,outcomes=outcomes,visits=visits,exploration=exploration):
                        model=two_choices(player,outcomes,visits,exploration)
                        scores=[(value if player==1 else 1-value)+exploration*math.sqrt(math.log(sum(visits))/count)
                            for value,count in zip(outcomes,visits)]
                        expected=max(range(2),key=lambda i:scores[i])+1
                        model._select()
                        self.assertEqual(model.selected,expected)

    def test_unvisited_and_first_tie_priority_are_preserved(self):
        for player in (1,-1):
            for visits,expected in [([0,3],1),([3,0],2),([1,1],1)]:
                model=two_choices(player,[.5,.5],visits,1.414)
                model._select()
                self.assertEqual(model.selected,expected)

    def test_each_stored_value_belongs_to_the_player_to_move(self):
        for player in (1,-1):
            model=two_choices(player,[1,0],visits=(2,3))
            root=model.memory.read_node(0)
            self.assertEqual(root['visits'],5)
            self.assertEqual(root['value'],2 if player==1 else 3)
            for child,outcome in [(1,1),(2,0)]:
                node=model.memory.read_node(child)
                expected=outcome if node['player']==1 else 1-outcome
                self.assertEqual(node['value']/node['visits'],expected)

    def test_terminal_pass_value_reaches_both_players_correctly(self):
        for player in (1,-1):
            state=LegacyGo(3).initial_state(); state.update(current_player=player,consecutive_passes=1,move_count=1)
            model=GoSimulation(board_size=3,iterations=2,go_state=state_record(state))
            model.memory.update_stats(0,1,.5)
            model._expand()
            terminal=next(n for n,move in model.moves.items() if move==(-1,-1))
            model.selected=terminal
            self.assertTrue(model.game.is_terminal(model.states[terminal]))
            model._evaluate()
            outcome=model.game.get_result_black(model.states[terminal])
            self.assertEqual(model.value_q17,round(outcome*131072))
            while model.memory.path_depth: model.memory.pop_path()
            model.memory.reset_path();model.memory.push_path(0);model.memory.push_path(terminal)
            model._backprop()
            child=model.memory.read_node(terminal)
            self.assertEqual(child['value'],outcome if child['player']==1 else 1-outcome)

    def test_studio_root_children_keep_absolute_black_values(self):
        for player in (1,-1):
            model=two_choices(player,[1,0]);model._select();model.completed=1
            state=LegacyGo(3).initial_state();state['current_player']=player
            config=configuration({'board_size':3,'iterations':1,'rules':'legacy_go','go_state':state_record(state)})
            with tempfile.TemporaryDirectory(dir=ROOT) as folder:
                job=Job(config,'test',False,Path(folder)/'runs')
                job.observe({'run':'value_convention','phase':'iteration_commit','iteration':1},model)
                self.assertEqual([n['black_value'] for n in job.snapshot['root_children']],[1,0])

    def test_fixed_go_identity_names_the_value_convention(self):
        model=GoSimulation(board_size=3,iterations=1)
        self.assertEqual(configuration({'rules':'legacy_go'})['profile'],'single_child_go_host_rules_q32_v1')
        self.assertEqual(configuration({'rules':'legacy_go','profile':'legacy_go_host_rules_q32_v3'})['profile'],'legacy_go_host_rules_q32_v3')
        self.assertEqual(model.application_record()['node_value_perspective'],'player_to_move')

    def test_complete_search_values_and_committed_moves_for_both_colors(self):
        for player in (1,-1):
            state=LegacyGo(3).initial_state();state['current_player']=player
            config={'board_size':3,'iterations':32,'rules':'legacy_go',
                'model_id':'archive_3x3_h24_centered_v1','go_state':state_record(state)}
            with tempfile.TemporaryDirectory(dir=ROOT) as folder:
                play=BoardPlay(config,Path(folder)/'plays')
                observed=[]

                def committed(move,model):
                    tree=model.memory.nodes;visits=Counter();values=Counter()
                    for event in model.history:
                        node=event['selected_node']
                        while node != -1:
                            visits[node]+=1
                            values[node]+=event['value_q17'] if tree[node]['player']==1 else 131072-event['value_q17']
                            node=tree[node]['parent']
                    for node,record in tree.items():
                        self.assertEqual(record['visits'],visits[node])
                        self.assertEqual(record['value'],values[node]/131072)
                    chosen=max(tree[0]['children'],key=lambda n:(visits[n],-n))
                    self.assertEqual(move['node'],chosen)
                    self.assertEqual(move['board_after'],model.states[chosen]['board'].tolist())
                    self.assertEqual(move['go_state'],state_record(model.states[chosen]))
                    self.assertEqual(move['player'],model.states[0]['current_player'])
                    self.assertEqual(sum(model.phase_cycles.values()),move['core_cycles'])
                    observed.append(move)

                _,result=play.run(lambda row,model:None,committed,
                    lambda current:'finish' if len(current.moves)==2 else None)
                self.assertEqual([move['player'] for move in observed],[player,-player])
                self.assertEqual(result['metrics']['completed_iterations'],64)
                self.assertEqual(result['identity']['profile'],'legacy_go_play_v2')


if __name__=='__main__': unittest.main()
