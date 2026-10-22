# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
# End-to-end current-profile, accounting and historical-isolation checks.
import json
from pathlib import Path
import tempfile
import unittest
from collections import Counter

from core.algorithm.model_catalog import load_model
from core.architecture import studio_current as c
from core.architecture.result_registry import configuration,ROOT,run_case,verify_run
from core.architecture.ucb_overlap import OverlappedUCBGoSimulation
from core.architecture.parallel_datapath_costs import parallel_datapath_costs
from p03_experiments.p79_scalability.costs import estimate
from p03_experiments.p84_parallel_datapath.run import result as experiment_result
from p05_studio.p00_app.server import Job
from p05_studio.p00_app.placement_play import BoardPlay
from p05_studio.p00_app.pipeline import Pipeline
from p05_studio.p00_app.visualization import activity_groups,RESOURCES

CONFIG=c.current_architecture()['default_configuration']

class CurrentStudioTests(unittest.TestCase):
    def test_contract_and_reject_unsupported(self):
        config=configuration(CONFIG)
        self.assertEqual(config['profile'],c.PROFILE)
        for override in ({'board_size':13},{'readout_profile':'column_hold_v1'},
                         {'hardware_profile':'unknown'},{'memory_profile':'cacti_22nm_hp'}):
            with self.assertRaises(ValueError):configuration(CONFIG|override)
        old=configuration({'board_size':2})
        self.assertFalse(c.is_current(old))
        data=c.preview('go_strong_v1'); parts={r['id']:r for r in data['components']}
        self.assertEqual([parts[x]['count'] for x in ('u_ucb','adc_lanes','cim_arrays')],[16,32,2])
        self.assertEqual([(r['rows'],r['columns']) for r in parts['cim_arrays']['children']],[(163,96),(96,3)])
        self.assertAlmostEqual(sum(r['area_um2'] for r in parts.values())/1e6,data['known_area_mm2'])

    def test_live_phase_costs_and_reference_work(self):
        for model_id in ('go_strong_v1','go_weak_v1'):
            weights,_=load_model(model_id,9)
            model=c.ParallelDatapathGoSimulation(9,110,weights=weights,turn_indicator=True)
            prepared=c.prepare(model);pipeline=Pipeline();cache={}
            event={'phase':'ready','iteration':0,'cycle_end':0,'run':'check'}
            pipeline.observe(event,model);activity_groups(event,model,cache)
            for event in model.steps():
                event=event|{'run':'check'};pipeline.observe(event,model)
                groups=activity_groups(event,model,cache)
                if event['iteration'] in (1,110):
                    costs=c.costs(model.memory.operations,model.cycles,model.block_active_cycles,c.capture(model),prepared)
                    ledger=costs['ledger']
                    self.assertAlmostEqual(ledger['known_energy_uj'],ledger['known_average_power_mw']*model.cycles/500000)
                if event['phase']=='neural':
                    self.assertTrue(all(g['resource'] in RESOURCES for g in groups))
            reference=OverlappedUCBGoSimulation(9,110,weights=weights,turn_indicator=True)
            for _ in reference.steps():pass
            expected=parallel_datapath_costs(experiment_result(model,model_id),experiment_result(reference,model_id),
                estimate(reference,prepared['sources'],prepared['published']),prepared['sources'],prepared['published'])
            self.assertAlmostEqual(costs['ledger']['known_energy_uj'],expected['core_energy_uj'],places=10)
            names={r[0] for phase in pipeline.phases for r in phase['services']}
            self.assertIn('ucb_bank',names);self.assertIn('selection_loader',names)
            self.assertNotIn('parallel_selection',names)
            both=c.combine(c.capture(model),c.capture(model))
            double=c.costs(Counter(model.memory.operations)+model.memory.operations,2*model.cycles,
                Counter(model.block_active_cycles)+model.block_active_cycles,both,prepared)
            self.assertAlmostEqual(double['ledger']['known_energy_uj'],2*expected['core_energy_uj'])
            self.assertEqual(double['ledger']['known_area_mm2'],costs['ledger']['known_area_mm2'])

    def test_saved_job_and_two_move_session(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'p03_experiments/p91_studio_latest_architecture') as folder:
            config=configuration(CONFIG|{'iterations':4})
            job=Job(config,'current-check',False,Path(folder)/'p01_runs',options={'speed':100})
            job.work();self.assertIsNone(job.error)
            self.assertEqual(job.status,'complete')
            payload=job.payload(); saved=verify_run(Path(folder)/'p01_runs'/job.run)
            self.assertEqual(payload['live_costs']['ledger'],saved['costs']['ledger'])
            self.assertEqual(saved['identity']['configuration']['memory']['execution_profile'],c.PROFILE)
            self.assertEqual(saved['neural']['cycles_per_inference'],2666)
            self.assertEqual(saved['architecture']['readout_bus_bits'],128)
            self.assertIn('core/architecture/parallel_datapath.json',saved['identity']['source_sha256'])
            play=BoardPlay(config,Path(folder)/'p02_plays',{'opponent':'engine','opponent_config':{'model_id':'go_weak_v1'},'architecture_side':'black'})
            out,game=play.run(lambda *args:None,lambda *args:None,lambda p:'finish' if len(p.moves)==2 else None)
            self.assertEqual(len(game['moves']),2)
            energy=0
            for move in play.moves:
                search=verify_run(out/'p01_searches'/move['search_run'])
                self.assertEqual(search['architecture']['profile'],c.PROFILE)
                energy+=search['costs']['ledger']['known_energy_uj']
            self.assertAlmostEqual(energy,game['costs']['ledger']['known_energy_uj'])
            verify_run(out)

if __name__=='__main__':unittest.main()
