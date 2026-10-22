# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# The display must preserve the actual tree, game state and modeled costs.
# SPDX-License-Identifier: MIT
import gzip
import csv
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from core.architecture.result_registry import ROOT, resolve_case, run_case, verify_run
from p05_studio.p00_app.server import Job, Studio
from p05_studio.p00_app.visualization import Visualization
from p05_studio.p00_app.placement_play import BoardPlay


class StudioViewsTests(unittest.TestCase):
    def wait(self, job, predicate, timeout=30):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            row=job.payload()
            if row['status']=='failed': self.fail(row['error'])
            if predicate(row): return row
            time.sleep(.005)
        self.fail('Studio did not reach the expected state: '+job.status)

    def start(self, folder, options, paused=False, execution='play', config=None):
        config,identifier=resolve_case(custom=config or {'board_size':2,'iterations':3})
        job=Job(config,identifier,paused,folder,execution,0,options)
        worker=threading.Thread(target=job.work,daemon=True); worker.start()
        self.addCleanup(lambda: job.action('cancel') if job.status not in ('complete','failed','cancelled') else None)
        return job,worker

    def test_display_matches_headless_search_and_tree(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            folder=Path(folder)
            config={'board_size':3,'iterations':8,'seed':17}
            _,reference=run_case(custom=config,runs=folder/'reference')
            job,worker=self.start(folder/'watched',{'speed':100},execution='search',config=config)
            self.wait(job,lambda row:row['status']=='complete');worker.join(5)
            self.assertEqual(job.result,reference)
            self.assertEqual(sum(n['visits'] for n in job.visual.nodes.values()),
                sum(n['visits'] for n in json.loads(gzip.open(folder/'watched'/job.run/'tree.json.gz','rt').read()).values()))
            tree=json.loads(gzip.open(folder/'watched'/job.run/'tree.json.gz','rt').read())
            for node_id,node in job.visual.nodes.items():
                actual=tree[str(node_id)]
                self.assertEqual((node['board'],node['visits'],node['value_sum'],node['children']),
                    (actual['board'],actual['visits'],actual['value'],len(actual['children'])))
            self.assertNotIn('transactions',job.result['memory'])

    def test_detailed_stepping_and_speed_do_not_change_results(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            folder=Path(folder);config={'board_size':2,'iterations':2}
            job,worker=self.start(folder/'stepped',{'speed':40},paused=True,execution='search',config=config)
            self.wait(job,lambda row:row['status']=='paused')
            groups=set(); previous=-1
            end=time.monotonic()+30
            while job.status!='complete' and time.monotonic()<end:
                row=job.payload()
                if row['status']=='failed': self.fail(row['error'])
                if row['sequence']!=previous and row['status']=='paused':
                    previous=row['sequence']
                    for group in row['snapshot'].get('activity',[]): groups.add(group['resource'])
                    job.action('step')
                time.sleep(.002)
            self.assertEqual(job.status,'complete');worker.join(5)
            self.assertTrue({'array','adc_bank','node_sram','divider'}<=groups)
            _,reference=run_case(custom=config,runs=folder/'reference')
            self.assertEqual(job.result,reference)

    def test_one_move_waits_and_continues_same_game(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            job,worker=self.start(Path(folder)/'searches',{'speed':100,'play_until':'one','opponent':'self'})
            first=self.wait(job,lambda r:r['status']=='awaiting_move')
            board=first['snapshot']['play']['board']; cycles=first['snapshot']['display_cycles']
            time.sleep(.03)
            self.assertEqual(job.payload()['snapshot']['play']['board'],board)
            self.assertEqual(len(job.play.moves),1)
            job.action('one');self.wait(job,lambda r:r['status']=='awaiting_move' and r['snapshot']['play']['completed_moves']==2)
            self.assertEqual(job.play.moves[1]['board_before'],board)
            self.assertGreater(job.play.cycles,cycles)
            job.action('until_end');self.wait(job,lambda r:r['status']=='complete');worker.join(5)
            self.assertEqual(len(job.play.moves),4)
            result=verify_run(job.play.out)
            self.assertEqual(result['metrics']['completed_iterations'],12)
            self.assertTrue(result['terminal'])

    def test_paused_game_starts_with_a_ready_tree(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            job,worker=self.start(Path(folder)/'searches',{'speed':100,'play_until':'one'},paused=True)
            ready=self.wait(job,lambda r:r['status']=='paused')
            self.assertEqual(ready['snapshot']['event']['phase'],'ready')
            self.assertEqual(ready['tree']['total'],1)
            job.action('step')
            phase=self.wait(job,lambda r:r['snapshot'].get('event',{}).get('phase')=='selection')
            self.assertEqual(phase['snapshot']['cycles'],26)
            job.action('cancel');worker.join(5)

    def test_human_input_invalid_moves_and_no_human_cost(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            job,worker=self.start(Path(folder)/'searches',{'speed':100,'play_until':'end','opponent':'human'})
            self.wait(job,lambda r:r['status']=='awaiting_human')
            before=job.play.board.copy();cycles=job.play.cycles
            occupied=next([r,c] for r in range(2) for c in range(2) if before[r,c])
            with self.assertRaises(ValueError): job.action('human_move',occupied)
            self.assertEqual(job.play.board.tolist(),before.tolist())
            empty=next([r,c] for r in range(2) for c in range(2) if not before[r,c])
            job.action('human_move',empty)
            self.wait(job,lambda r:r['status']=='awaiting_human' and len(job.play.moves)==3)
            human=job.play.moves[1]
            self.assertEqual((human['actor'],human['core_cycles'],human['search_run']),('human',0,None))
            last=next([r,c] for r in range(2) for c in range(2) if not job.play.board[r,c])
            job.action('human_move',last);self.wait(job,lambda r:r['status']=='complete');worker.join(5)
            self.assertEqual(job.result['metrics']['completed_iterations'],6)
            self.assertEqual(job.result['player_totals']['-1']['core_cycles'],0)
            self.assertGreater(job.result['metrics']['core_cycles'],cycles)

    def test_go_pass_keeps_metadata_and_finish_saves_prefix(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            job,worker=self.start(Path(folder)/'searches',{'speed':100,'play_until':'one','opponent':'human'},
                config={'board_size':3,'iterations':2,'rules':'legacy_go'})
            self.wait(job,lambda r:r['status']=='awaiting_human')
            job.action('human_move',[-1,-1]);self.wait(job,lambda r:r['status']=='awaiting_move')
            self.assertTrue(job.play.moves[-1]['pass_move'])
            self.assertEqual(job.play.game_state['current_player'],1)
            self.assertEqual(job.play.game_state['consecutive_passes'],1)
            job.action('finish');self.wait(job,lambda r:r['status']=='complete');worker.join(5)
            result=verify_run(job.play.out)
            self.assertFalse(result['terminal']);self.assertEqual(result['final_state']['move_count'],2)
            self.assertEqual(result['metrics']['completed_iterations'],2)

    def test_opponent_settings_are_used_and_costs_sum_searches(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            job,worker=self.start(Path(folder)/'searches',{'speed':100,'play_until':'end','opponent':'engine',
                'opponent_config':{'iterations':5,'seed':83,'model_id':'random_diagnostic'}})
            self.wait(job,lambda r:r['status']=='complete');worker.join(5)
            self.assertEqual([row['search_iterations'] for row in job.play.moves],[3,5,3,5])
            self.assertEqual([row['seed'] for row in job.play.moves],[0,83,0,83])
            self.assertEqual(job.result['metrics']['completed_iterations'],16)
            searches=[verify_run(job.play.out/'p01_searches'/m['search_run']) for m in job.play.moves]
            self.assertEqual(job.result['metrics']['core_cycles'],sum(r['metrics']['core_cycles'] for r in searches))
            self.assertAlmostEqual(job.result['costs']['sram']['energy_uj'],sum(r['costs']['sram']['energy_uj'] for r in searches),places=12)

    def test_tree_resynchronizes_after_lost_delta_history(self):
        from core.architecture.iteration_model import CompleteSimulation
        model=CompleteSimulation(board_size=3,iterations=35)
        view=Visualization();key='run_test';view.observe({'run':key,'phase':'ready'},model)
        for event in model.steps(): view.observe(event|{'run':key},model)
        payload=view.payload(1,key)
        self.assertTrue(payload['reset']);self.assertEqual(len(payload['nodes']),model.memory.nodes_used)
        self.assertEqual(view.payload(view.revision,key)['nodes'],[])
        self.assertTrue(view.payload(view.revision,'older_move')['reset'])

    def test_white_architecture_waits_for_black_human_opening(self):
        for rules,size in (('placement',2),('legacy_go',3)):
            with self.subTest(rules=rules), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                job,worker=self.start(Path(folder)/'searches',{'speed':100,'play_until':'one',
                    'opponent':'human','architecture_side':'white'},
                    config={'board_size':size,'iterations':3,'rules':rules})
                try:
                    ready=self.wait(job,lambda r:r['status']=='awaiting_human')
                    self.assertEqual(job.play.moves,[])
                    self.assertEqual(ready['snapshot']['play']['player_to_move'],1)
                    self.assertEqual(ready['snapshot']['play']['architecture_side'],'white')
                    self.assertEqual(job.play.cycles,0);self.assertIsNone(job.program)
                    self.assertEqual(ready['run'],job.play.out.name)
                    job.action('human_move',[0,0])
                    self.wait(job,lambda r:r['status']=='awaiting_human' and len(job.play.moves)==2)
                    self.assertEqual([(m['player'],m['actor']) for m in job.play.moves],[(1,'human'),(-1,'architecture')])
                    self.assertEqual(job.play.moves[0]['core_cycles'],0)
                    job.action('finish');self.wait(job,lambda r:r['status']=='complete');worker.join(5)
                    result=verify_run(job.play.out)
                    self.assertEqual(result['identity']['architecture_side'],'white')
                    self.assertEqual(result['session_profile'],'studio_turns_v3')
                    self.assertEqual(result['player_totals']['1']['core_cycles'],0)
                    self.assertEqual(result['metrics']['completed_iterations'],3)
                    search=verify_run(job.play.out/'p01_searches'/job.play.moves[1]['search_run'])
                    self.assertEqual(result['costs']['ledger'],search['costs']['ledger'])
                    with (job.play.out/'summary.csv').open() as stream:
                        self.assertEqual(next(csv.DictReader(stream))['architecture_side'],'white')
                    with (job.play.out/'moves.csv').open() as stream:
                        self.assertEqual([row['actor'] for row in csv.DictReader(stream)],['human','architecture'])
                finally:
                    if job.status not in ('complete','failed','cancelled'): job.action('cancel')
                    worker.join(5)

    def test_white_architecture_uses_opponent_settings_for_black(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            job,worker=self.start(Path(folder)/'searches',{'speed':100,'play_until':'one',
                'opponent':'engine','architecture_side':'white',
                'opponent_config':{'iterations':5,'seed':83,'model_id':'random_diagnostic'}})
            try:
                self.wait(job,lambda r:r['status']=='awaiting_move')
                self.assertEqual([(m['player'],m['actor'],m['search_iterations'],m['seed']) for m in job.play.moves],[(1,'opponent',5,83)])
                job.action('one')
                self.wait(job,lambda r:r['status']=='awaiting_move' and len(job.play.moves)==2)
                second=job.play.moves[1]
                self.assertEqual((second['player'],second['actor'],second['search_iterations'],second['seed']),(-1,'architecture',3,0))
                job.action('finish');self.wait(job,lambda r:r['status']=='complete');worker.join(5)
                result=verify_run(job.play.out)
                self.assertEqual(result['session']['architecture_side'],'white')
                self.assertEqual(result['metrics']['completed_iterations'],8)
                searches=[verify_run(job.play.out/'p01_searches'/m['search_run']) for m in job.play.moves]
                self.assertAlmostEqual(result['costs']['ledger']['known_energy_uj'],sum(r['costs']['ledger']['known_energy_uj'] for r in searches))
            finally:
                if job.status not in ('complete','failed','cancelled'): job.action('cancel')
                worker.join(5)

    def test_self_play_uses_both_colors_with_a_saved_side(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            play=BoardPlay({'board_size':2,'iterations':3},Path(folder)/'sessions',
                {'opponent':'self','architecture_side':'white'})
            _,result=play.run(lambda row,model:None,lambda move,model:None)
            self.assertEqual([m['player'] for m in result['moves']],[1,-1,1,-1])
            self.assertTrue(all(m['actor']=='architecture' for m in result['moves']))
            self.assertEqual(result['metrics']['completed_iterations'],12)

    def test_bad_settings_rejected_before_starting(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            studio=Studio(Path(folder)/'searches')
            for options in ({'speed':True},{'opponent':'external'},{'opponent_config':{'board_size':9}},
                {'opponent_config':{'iterations':0}},{'opponent_config':{'seed':-1}},
                {'architecture_side':None},{'architecture_side':True},{'architecture_side':1},
                {'architecture_side':'red'},{'architecture_side':['white']}):
                with self.assertRaises(ValueError): studio.create({'configuration':{'board_size':2,'iterations':2},'execution':'play','studio_options':options})
            self.assertFalse(studio.jobs)


if __name__=='__main__': unittest.main()
