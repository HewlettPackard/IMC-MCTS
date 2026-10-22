# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Check spreadsheet reproduction, checkpoint mapping and host-assisted Go semantics.
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import pickle
import tempfile
import unittest

import numpy as np

from core.algorithm.evaluator import encode_board
from core.algorithm.model_catalog import load_model, model_catalog, model_record
from core.architecture.crossbar_workbook import component_estimates, reference_crossbar, workbook_source
from core.architecture.go_simulation import GoSimulation, LegacyGo, initial_state, state_record
from core.architecture.neural_mapping import NeuralMapping
from core.architecture.result_registry import ROOT, resolve_case, run_case, verify_run
from p05_studio.p00_app.placement_play import BoardPlay


class WorkbookModelGoTests(unittest.TestCase):
    def test_reference_reproduces_excel_cached_area(self):
        cells=workbook_source()['cells']['New_Architecture']; result=reference_crossbar(256)
        self.assertAlmostEqual(result['crossbar_pair_area_um2'],cells['D64']['value'],places=8)
        self.assertAlmostEqual(result['mvm_unit_area_um2'],cells['D67']['value'],places=8)
        previous=0
        for size in [32,64,128,256,512]:
            value=reference_crossbar(size)
            self.assertGreater(value['mvm_unit_area_um2'],previous); previous=value['mvm_unit_area_um2']
            self.assertEqual(value['parts_um2']['differential_cell_pair'],2*size**2*cells['C14']['value'])
        for value in [True,0,-1,1.5,4097]:
            with self.assertRaises(ValueError): reference_crossbar(value)

    def test_installed_cells_count_sign_and_slices_once(self):
        weights,_=load_model('archive_9x9_h96_centered_v1',9)
        model=NeuralMapping(*weights,9); ledger=component_estimates(model.profile,'cacti_22nm_lstp')
        cells=next(row for row in ledger['components'] if row['component']=='CIM cell arrays')
        self.assertEqual(cells['count'],sum(len(layer) for layer in model.tiles))
        self.assertEqual(cells['area_um2'],4*256*128*0.0424)
        self.assertEqual(ledger['known_area_mm2'],sum(row['area_um2'] or 0 for row in ledger['components'])/1e6)
        self.assertIsNone(ledger['whole_chip_area_mm2']); self.assertIsNone(ledger['whole_chip_energy_uj'])
        self.assertEqual(ledger['scaling_applications'],0)

    def test_packaged_weights_match_declared_original_transform(self):
        for row in model_catalog():
            if not row['available']: continue
            raw=(ROOT/row['original_snapshot']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['original_sha256'])
            original=pickle.loads(raw); weights,info=load_model(row['id'],row['board_size'])
            hidden=row['hidden_units']
            self.assertTrue(np.array_equal(weights[0][:,:hidden],(np.asarray(original['weights1'])-50)/50))
            self.assertTrue(np.array_equal(weights[1][:hidden],(np.asarray(original['weights2'])-50)/50))
            self.assertFalse(np.any(weights[0][:,hidden:])); self.assertFalse(np.any(weights[1][hidden:]))
            self.assertEqual(info['task_quality'],'not_revalidated')

    def test_white_transform_preserves_absolute_evaluator(self):
        rng=np.random.RandomState(15)
        weights,_=load_model('archive_9x9_h32_centered_v1',9)
        flipped,_=load_model('archive_9x9_h32_centered_v1',9,-1)
        normal=NeuralMapping(*weights,9); other=NeuralMapping(*flipped,9)
        for _ in range(16):
            board=rng.choice([-1,0,1],size=(9,9))
            expected=np.maximum(encode_board(board,9)@weights[0],0)@weights[1]
            actual=np.maximum(encode_board(-board,9)@flipped[0],0)@flipped[1]
            np.testing.assert_allclose(actual,expected[::-1],atol=1e-12)
            normal.forward(board); other.forward(-board)
            self.assertLessEqual(np.max(np.abs(np.array(normal.last_state['probabilities_q16'])-
                np.array(other.last_state['probabilities_q16'])[::-1])),1)

    def test_model_rejection_and_case_isolation(self):
        for identifier,size in [('missing',9),('archive_3x3_h24_centered_v1',9),('archive_9x9_turn_bit',9)]:
            with self.assertRaises(ValueError): model_record(identifier,size)
        with self.assertRaises(ValueError): resolve_case('placement_9x9_medium_v1',{'rules':'legacy_go'})
        with self.assertRaises(ValueError): resolve_case(custom={'rules':'unknown'})
        with self.assertRaises(ValueError): resolve_case(custom={'rules':'legacy_go','profile':'complete_serial_q32_v1'})

    def test_capture_suicide_ko_pass_and_scoring(self):
        game=LegacyGo(5); state=game.initial_state()
        for r,c in [(0,1),(1,0),(2,1)]: state['board'][r,c]=1
        for r,c in [(1,1),(0,2),(2,2),(1,3)]: state['board'][r,c]=-1
        original=state['board'].copy(); history=set(state['history_hashes'])
        self.assertTrue(game.is_legal(state,1,2,1)); captured=game.apply_move(state,(1,2))
        self.assertEqual(captured['board'][1,1],0); self.assertEqual(captured['captures'][1],1)
        self.assertFalse(game.is_legal(captured,1,1,-1))
        self.assertTrue(np.array_equal(state['board'],original)); self.assertEqual(state['history_hashes'],history)
        passed=game.apply_move(captured,(-1,-1)); self.assertIsNone(passed['ko_hash'])
        ended=game.apply_move(passed,(-1,-1)); self.assertTrue(game.is_terminal(ended))
        self.assertEqual(game.score_position(np.zeros((5,5),dtype=np.int8)),(0.0,6.5))
        suicide=game.initial_state()
        for r,c in [(0,1),(1,0),(2,1),(1,2)]: suicide['board'][r,c]=-1
        self.assertFalse(game.is_legal(suicide,1,1,1))

    def test_white_root_and_pass_successor_preserve_state(self):
        game=LegacyGo(3); state=game.initial_state(); state['current_player']=-1
        model=GoSimulation(board_size=3,iterations=2,go_state=state_record(state))
        self.assertEqual(model.memory._node_fields(0)['player'],-1)
        self.assertEqual(model.memory.path_depth,0)
        list(model.steps()); children=model.memory.nodes[0]['children']
        self.assertEqual(len(children),10)
        for child in children:
            expected=game.apply_move(state,model.moves[child])
            self.assertTrue(np.array_equal(model.board(child),expected['board']))
            self.assertEqual(model.memory._node_fields(child)['player'],1)
        passed=next(child for child in children if model.moves[child]==(-1,-1))
        self.assertTrue(np.array_equal(model.board(passed),model.initial_board))
        self.assertEqual(model.states[passed]['consecutive_passes'],1)

    def test_go_child_value_belongs_to_the_player_to_move(self):
        model=GoSimulation(board_size=3,iterations=2)
        list(model.steps())
        node=model.memory.nodes[model.selected]
        self.assertEqual(node['player'],-1)
        self.assertEqual(node['value'],1-model.value_q17/131072)
        self.assertEqual(sum(model.phase_cycles.values()),model.cycles)
        constrained=GoSimulation(board_size=3,iterations=2,memory_limits={'nodes':10})
        with self.assertRaises(MemoryError): list(constrained.steps())

    def test_legacy_go_result_identity_and_repeatability(self):
        config={'board_size':3,'iterations':3,'rules':'legacy_go','model_id':'archive_3x3_h24_centered_v1'}
        with tempfile.TemporaryDirectory(prefix='go_registry_',dir=ROOT) as directory:
            runs=Path(directory)/'runs'; out,a=run_case(custom=config,runs=runs); _,b=run_case(custom=config,runs=runs)
            self.assertEqual(a,b); self.assertEqual(verify_run(out),a)
            self.assertEqual(a['evaluator']['mode'],'archived_checkpoint')
            self.assertIn('host',a['publication_status']); self.assertIn('application',a)
            self.assertIn('tournament/go_compiled/engine/go_engine.py',a['identity']['source_sha256'])
            self.assertIsNone(a['metrics']['area_mm2'])

    def test_go_play_commits_rules_state_and_sums_searches(self):
        config={'board_size':3,'iterations':2,'rules':'legacy_go','model_id':'archive_3x3_h24_centered_v1'}
        with tempfile.TemporaryDirectory(prefix='go_play_',dir=ROOT) as directory:
            play=BoardPlay(config,Path(directory)/'plays'); game=LegacyGo(3); expected=game.initial_state()
            def placed(move,model):
                nonlocal expected
                action=(move['row'],move['column'])
                self.assertIn(action,game.get_legal_moves(expected))
                expected=game.apply_move(expected,action)
                self.assertEqual(move['board_after'],expected['board'].tolist())
                self.assertEqual(move['go_state'],state_record(expected))
            out,result=play.run(lambda row,model:None,placed)
            self.assertTrue(game.is_terminal(expected)); self.assertTrue(play.state()['terminal'])
            self.assertEqual(result['final_score'],list(game.score_position(expected['board'])))
            self.assertEqual(result['metrics']['completed_iterations'],2*len(play.moves))
            self.assertEqual(result['metrics']['core_cycles'],sum(row['core_cycles'] for row in play.moves))
            self.assertEqual(verify_run(out),result)


if __name__=='__main__': unittest.main()
