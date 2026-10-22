# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Recovered tournament identities, turn semantics and mapped game integration.
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from core.algorithm.model_catalog import load_model, model_catalog, model_sources
from core.architecture.analog_readout import BufferedNeuralMapping, BUFFERED, DRIVEN, configure_readout
from core.architecture.go_simulation import GoSimulation, LegacyGo, state_record, TURN_PROFILE
from core.architecture.neural_mapping import NeuralMapping
from core.architecture.result_registry import ROOT, configuration, run_case, verify_run
from p05_studio.p00_app.placement_play import BoardPlay

MODELS=('go_strong_v1','go_weak_v1')


class PaperModelTests(unittest.TestCase):
    def test_ten_paper_roles_and_two_distinct_checkpoints(self):
        rows=[row for row in model_catalog() if row.get('paper_model')]
        self.assertEqual([row['label'] for row in rows],['Go-strong','Go-weak','Connect Four',
            'Othello','Hex','Go','FrozenLake','MiniGrid','HP Protein Fold','Minesweeper'])
        self.assertEqual([row['id'] for row in rows if row['available']],list(MODELS))
        self.assertEqual(len({row['sha256'] for row in rows if row['available']}),2)
        for row in rows[2:]:
            with self.subTest(model=row['id']),self.assertRaises(ValueError):
                configuration({'model_id':row['id'],'rules':'legacy_go'})

    def test_runtime_matrices_preserve_binary_and_all_turn_weights(self):
        for identifier in MODELS:
            weights,record=load_model(identifier,9); raw=(ROOT/record['binary_snapshot']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),record['binary_sha256'])
            offset=0
            for weight in weights:
                rows,cols=struct.unpack_from('<ii',raw,offset);offset+=8
                source=np.frombuffer(raw,dtype='<f8',count=rows*cols,offset=offset).reshape(rows,cols)
                offset+=8*rows*cols
                np.testing.assert_array_equal(weight,(source-50)/50)
            self.assertEqual(offset,len(raw));self.assertEqual(weights[0].shape,(163,96))
            self.assertEqual(np.count_nonzero(weights[0][-1]),96)
            self.assertIn(ROOT/record['binary_snapshot'],model_sources(identifier,9))

    def test_both_turns_match_dense_integer_mapping_and_both_readouts(self):
        boards=[np.zeros((9,9),dtype=np.int8),np.random.RandomState(29).choice([-1,0,1],size=(9,9))]
        for identifier in MODELS:
            weights,_=load_model(identifier,9)
            driven=NeuralMapping(*weights,9,turn_indicator=True,sram_word_cycles=2)
            buffered=BufferedNeuralMapping(*weights,9,turn_indicator=True,sram_word_cycles=2)
            for board in boards:
                accumulators={}
                for player in (1,-1):
                    # Independent encoding, including the same board with either side to play.
                    inputs=np.zeros(163,dtype=np.int64)
                    inputs[:162:2]=(board.ravel()==1);inputs[1:162:2]=(board.ravel()==-1)
                    inputs[-1]=int(player==1)
                    driven.forward(board,player);buffered.forward(board,player)
                    np.testing.assert_array_equal(driven.last_state['hidden_acc'],inputs@driven.weight_codes[0])
                    self.assertEqual(driven.last_state,buffered.last_state)
                    self.assertEqual(driven.last_state['hidden_saturations'],0)
                    self.assertEqual(driven.last_state['logit_saturations'],0)
                    accumulators[player]=np.array(driven.last_state['hidden_acc'])
                np.testing.assert_array_equal(accumulators[1]-accumulators[-1],driven.weight_codes[0][-1])
            for bad in (None,0,True,2):
                with self.subTest(player=bad),self.assertRaises(ValueError): driven.forward(boards[0],bad)

    def test_turn_requires_explicit_supported_encoding(self):
        weights,_=load_model(MODELS[0],9)
        with self.assertRaises(ValueError): NeuralMapping(*weights,9)
        with self.assertRaises(ValueError): load_model(MODELS[0],9,-1)
        for config in ({'model_id':MODELS[0]}, {'model_id':MODELS[0],'rules':'legacy_go','board_size':5}):
            with self.assertRaises(ValueError): configuration(config)
        config=configuration({'model_id':MODELS[0],'rules':'legacy_go'})
        self.assertEqual(config['profile'],'single_child_go_turn_input_host_rules_q32_v1')
        self.assertEqual(configuration({'model_id':MODELS[0],'rules':'legacy_go','profile':TURN_PROFILE})['profile'],TURN_PROFILE)

    def test_node_player_word_and_pass_change_the_actual_evaluation(self):
        weights,_=load_model(MODELS[0],9)
        for player in (1,-1):
            state=LegacyGo(9).initial_state();state['current_player']=player
            model=GoSimulation(board_size=9,iterations=2,weights=weights,turn_indicator=True,go_state=state_record(state))
            observed=[]
            for event in model.steps():
                if event['phase']=='neural':
                    selected=model.memory._node_fields(model.selected)['player']
                    self.assertEqual(model.neural.last_state['black_to_play'],int(selected==1))
                    observed.append(model.neural.last_state['black_to_play'])
            self.assertEqual(observed,[int(player==1),int(player==-1)])
            passed=next(n for n,move in model.moves.items() if move==(-1,-1))
            np.testing.assert_array_equal(model.board(passed),model.initial_board)
            model.memory.capture_trace=True
            model.selected=passed;model._phase('neural',model._evaluate)
            self.assertEqual(model.neural.last_state['black_to_play'],int(player==-1))
            reads=[row for row in model.neural.schedule['trace'] if row['region']=='player']
            self.assertEqual(len(reads),1);self.assertEqual(reads[0]['bytes'],4)
            transactions=model.memory.transactions
            self.assertTrue(any(row['resource']=='node_sram' and row['operation']=='read' and
                row['address']==model.memory.node_address(passed)+20 for row in transactions))

    def test_saved_runs_trace_actual_models_and_estimated_costs(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            for identifier in MODELS:
                for mode in (DRIVEN,BUFFERED):
                    config={'board_size':9,'iterations':2,'rules':'legacy_go','model_id':identifier,'readout_profile':mode}
                    out,result=run_case(custom=config,runs=Path(temporary)/'runs')
                    self.assertEqual(result,verify_run(out))
                    self.assertEqual(result['evaluator']['checkpoint']['id'],identifier)
                    self.assertEqual(result['neural']['profile']['input_size'],163)
                    self.assertEqual(result['neural']['resources']['turn_input_register_bits'],1)
                    self.assertIn('not_RTL_validated',result['neural']['profile']['timing_status'])
                    self.assertEqual(result['neural']['resources']['array_count'],4)
                    neural=next(row for row in result['costs']['digital']['components'] if row['instance']=='u_nn')
                    self.assertGreater(neural['area_um2'],0)
                    self.assertEqual(neural['report_proxy']['status'],'engineering_estimate_not_matching_synthesis')
                    self.assertEqual(neural['report_proxy']['reference_parameters']['INPUTS'],162)
                    self.assertEqual(neural['parameters_required']['INPUTS'],163)
                    self.assertIsNone(neural['native_65nm_area_um2'])
                    self.assertIsNone(neural['timing'])
                    self.assertIn('software_extension',json.loads((ROOT/'core/architecture/complete_controller_validation.json').read_text()))

    def test_engine_and_self_play_keep_model_and_side(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            for opponent in ('self','engine'):
                for side in ('black','white'):
                    options={'opponent':opponent,'architecture_side':side,
                        'opponent_config':{'model_id':MODELS[1],'iterations':2,'seed':4}}
                    play=BoardPlay({'board_size':9,'iterations':2,'rules':'legacy_go','model_id':MODELS[0]},
                        Path(temporary)/'plays',options)
                    def turn(current): return 'finish' if len(current.moves)>=2 else None
                    out,result=play.run(lambda row,model:None,lambda move,model:None,on_turn=turn)
                    self.assertEqual(result,verify_run(out))
                    self.assertEqual([m['player'] for m in play.moves],[1,-1])
                    expected=[MODELS[0],MODELS[0]] if opponent=='self' else (list(MODELS) if side=='black' else list(MODELS[::-1]))
                    self.assertEqual([m['model_id'] for m in play.moves],expected)

    def test_incompatible_opponent_is_rejected_before_creating_a_game(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            with self.assertRaisesRegex(ValueError,'same board/turn input layout'):
                BoardPlay({'board_size':9,'iterations':2,'rules':'legacy_go','model_id':MODELS[0]},
                    Path(temporary)/'plays',{'opponent':'engine','opponent_config':{'model_id':'random_diagnostic'}})


if __name__=='__main__': unittest.main()
