# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# A displayed placement must be the chosen child of a completed real search.
# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

import numpy as np

from core.architecture.result_registry import ROOT, RunCancelled, resolve_case, verify_run
from p05_studio.p00_app.placement_play import BoardPlay
from p05_studio.p00_app.server import Job


class PlacementPlayTests(unittest.TestCase):
    def test_successive_legal_moves_and_accounting(self):
        with tempfile.TemporaryDirectory(prefix='play_check_',dir=ROOT) as directory:
            play=BoardPlay({'board_size':2,'iterations':3},Path(directory)/'sessions')
            captured=[]
            def placed(move, model):
                board=np.array(move['board_after']); previous=np.array(move['board_before'])
                self.assertEqual(np.count_nonzero(board),move['move'])
                self.assertEqual(np.count_nonzero(board!=previous),1)
                self.assertEqual(move['player'],1 if move['move']%2 else -1)
                self.assertEqual(board[move['row'],move['column']],move['player'])
                self.assertTrue(np.array_equal(model.board(move['node'])*move['player'],board))
                nodes=model.memory.nodes; best=max(nodes[0]['children'],key=lambda n:(nodes[n]['visits'],-n))
                self.assertEqual(move['node'],best); self.assertEqual(model.completed,3)
                captured.append(move)
            out,result=play.run(lambda row,model:None,placed)
            self.assertEqual(len(captured),4); self.assertEqual(np.count_nonzero(play.board),4)
            self.assertEqual(verify_run(out),result)
            searches=[verify_run(out/'p01_searches'/move['search_run']) for move in captured]
            self.assertEqual(result['metrics']['core_cycles'],sum(row['metrics']['core_cycles'] for row in searches))
            self.assertEqual(result['metrics']['completed_iterations'],12)
            self.assertEqual(sum(result['phase_cycles'].values()),result['metrics']['core_cycles'])
            for instance, activity in result['block_activity']['blocks'].items():
                self.assertEqual(activity['active_cycles'],sum(row['block_activity']['blocks'][instance]['active_cycles'] for row in searches))
                self.assertEqual(activity['active_cycles']+activity['idle_cycles'],result['metrics']['core_cycles'])
            self.assertTrue((out/'block_power.csv').is_file())
            self.assertAlmostEqual(result['costs']['sram']['energy_uj'],sum(row['costs']['sram']['energy_uj'] for row in searches),places=12)
            self.assertEqual(result['costs']['sram']['area_mm2'],searches[0]['costs']['sram']['area_mm2'])
            self.assertEqual(result['costs']['digital']['known_area_mm2'],searches[0]['costs']['digital']['known_area_mm2'])
            self.assertEqual(result['component_estimates'],searches[0]['component_estimates'])
            self.assertIsNone(result['metrics']['energy_uj'])
            for move,search in zip(captured,searches):
                normalized=np.array(move['board_before'])*move['player']
                self.assertEqual(search['identity']['configuration']['requested']['initial_board'],normalized.tolist())
            second=BoardPlay({'board_size':2,'iterations':3},Path(directory)/'repeated')
            _,repeat=second.run(lambda row,model:None,lambda move,model:None)
            self.assertEqual(result,repeat)

    def test_partial_initial_board_preserved(self):
        board=[[1,-1],[0,0]]
        with tempfile.TemporaryDirectory(prefix='play_partial_',dir=ROOT) as directory:
            play=BoardPlay({'board_size':2,'iterations':2,'initial_board':board},Path(directory)/'sessions')
            _,result=play.run(lambda row,model:None,lambda move,model:None)
            self.assertEqual(result['metrics']['completed_moves'],2)
            self.assertEqual(result['final_board'][0],board[0])
            self.assertEqual(result['moves'][0]['player'],1)

    def test_cancel_keeps_only_committed_prefix(self):
        with tempfile.TemporaryDirectory(prefix='play_cancel_',dir=ROOT) as directory:
            play=BoardPlay({'board_size':2,'iterations':2},Path(directory)/'sessions')
            def cancel(move, model):
                if move['move']==2: raise RunCancelled('cancel after two actual moves')
            with self.assertRaises(RunCancelled): play.run(lambda row,model:None,cancel)
            record=json.loads((play.out/'metadata.json').read_text())
            self.assertEqual((record['status'],record['completed_moves']),('cancelled',2))
            self.assertEqual(np.count_nonzero(play.board),2)
            self.assertFalse((play.out/'result.json').exists())

    def test_failed_search_does_not_place_a_piece(self):
        with tempfile.TemporaryDirectory(prefix='play_failure_',dir=ROOT) as directory:
            play=BoardPlay({'board_size':2,'iterations':3,'memory_limits':{'nodes':1}},Path(directory)/'sessions')
            with self.assertRaises(MemoryError): play.run(lambda row,model:None,lambda move,model:None)
            record=json.loads((play.out/'metadata.json').read_text())
            self.assertEqual((record['status'],record['completed_moves']),('failed',0))
            self.assertEqual(np.count_nonzero(play.board),0)

    def test_phase_controls_and_display_delay_do_not_charge_cycles(self):
        with tempfile.TemporaryDirectory(prefix='play_control_',dir=ROOT) as directory:
            config,identifier=resolve_case(custom={'board_size':2,'iterations':2})
            job=Job(config,identifier,True,Path(directory)/'searches','play',5000)
            worker=threading.Thread(target=job.work); worker.start()
            def wait(predicate):
                end=time.monotonic()+10
                while time.monotonic()<end:
                    payload=job.payload()
                    if predicate(payload): return payload
                    if payload['status']=='failed': self.fail(payload['error'])
                    time.sleep(.01)
                self.fail('Job did not reach the expected state')
            try:
                ready=wait(lambda row:row['status']=='paused')
                self.assertEqual(ready['snapshot']['display_cycles'],0)
                job.action('step'); step=wait(lambda row:row['snapshot']['event']['phase']=='selection')
                self.assertEqual(step['snapshot']['cycles'],26)
                self.assertEqual(step['snapshot']['play']['completed_moves'],0)
                job.action('resume'); placed=wait(lambda row:row['snapshot'].get('play',{}).get('completed_moves')==1)
                job.action('pause'); paused=wait(lambda row:row['status']=='paused')
                before=paused['snapshot']['display_cycles']; time.sleep(.1)
                self.assertEqual(job.payload()['snapshot']['display_cycles'],before)
                self.assertEqual(sum(paused['snapshot']['display_phase_cycles'].values()),before)
                job.action('step'); next_turn=wait(lambda row:row['snapshot']['play']['current_move']==2)
                self.assertEqual(next_turn['snapshot']['display_cycles'],before)
                self.assertEqual(next_turn['snapshot']['play']['completed_moves'],1)
                job.action('cancel'); wait(lambda row:row['status']=='cancelled')
            finally:
                if job.status not in ('complete','failed','cancelled'): job.action('cancel')
                worker.join(timeout=10)
            self.assertFalse(worker.is_alive())

    def test_invalid_play_inputs(self):
        for config in ({'board_size':2,'iterations':1},{'board_size':2,'initial_board':[[1,-1],[1,-1]]},
                {'board_size':2,'initial_board':[[0,.5],[0,0]]}):
            with self.assertRaises(ValueError): BoardPlay(config,ROOT/'unused_play_output')


if __name__=='__main__': unittest.main()
