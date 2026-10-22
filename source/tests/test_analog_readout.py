# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Finite analog retention and independent inference/timing checks.
# SPDX-License-Identifier: MIT
import csv
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

from core.algorithm.evaluator import encode_board
from core.algorithm.model_catalog import load_model
from core.architecture.analog_readout import BUFFERED, BufferedNeuralMapping, ColumnHoldBank, configure_readout, readout_activity, readout_inventory
from core.architecture.crossbar_workbook import component_estimates
from core.architecture.iteration_model import CompleteSimulation
from core.architecture.neural_mapping import NeuralMapping
from core.architecture.result_registry import ROOT, configuration, run_case, verify_run
from core.architecture.result_snapshot import freeze_repeats, verify_snapshot
from p05_studio.p00_app.placement_play import BoardPlay


class AnalogReadoutTests(unittest.TestCase):
    def test_capture_owns_continuous_samples_until_adc(self):
        bank=ColumnHoldBank(4); original=np.array([0.25,1.75,2.25,254.75])
        bank.capture(original,10); original[:]=0
        np.testing.assert_array_equal(bank.values,[0.25,1.75,2.25,254.75])
        with self.assertRaises(RuntimeError): bank.capture([1],11)
        np.testing.assert_array_equal(bank.sample(0,3,12),[0,2,2])
        with self.assertRaises(RuntimeError): bank.capture([1],13)
        np.testing.assert_array_equal(bank.sample(3,1,674),[255])
        self.assertFalse(bank.valid.any()); bank.capture([4.5],700)
        np.testing.assert_array_equal(bank.sample(0,1,702),[4])

    def test_capacity_ownership_range_and_time_guards(self):
        bank=ColumnHoldBank(3)
        with self.assertRaises(RuntimeError): bank.sample(0,1,0)
        for values in [[],[0]*4,[256],[-1],[float('nan')],[float('inf')],[[1]]]:
            with self.assertRaises(ValueError): bank.capture(values,0)
        bank.capture([1,2],10)
        with self.assertRaises(ValueError): bank.sample(0,1,9)
        with self.assertRaises(RuntimeError): bank.sample(1,2,11)
        with self.assertRaises(ValueError): bank.sample(-1,1,11)
        bank.sample(0,1,11)
        with self.assertRaises(RuntimeError): bank.sample(0,1,12)
        bank.sample(1,1,12)
        with self.assertRaises(ValueError): bank.capture([1],11)

    def test_small_and_archived_inference_matches_integer_products(self):
        rng=np.random.RandomState(17)
        for size,identifier in [(2,None),(3,'archive_3x3_h24_centered_v1'),(5,'archive_5x5_h32_centered_v1'),(9,'archive_9x9_h96_centered_v1')]:
            weights=CompleteSimulation(size,1).weights if identifier is None else load_model(identifier,size)[0]
            old=NeuralMapping(*weights,size,sram_word_cycles=2)
            new=BufferedNeuralMapping(*weights,size,sram_word_cycles=2)
            for _ in range(8):
                board=rng.choice([-1,0,1],size=(size,size))
                self.assertEqual(old.forward(board),new.forward(board)); self.assertEqual(old.last_state,new.last_state)
                np.testing.assert_array_equal(new.last_state['hidden_acc'],encode_board(board,size).astype(np.int64)@new.weight_codes[0])
                np.testing.assert_array_equal(new.last_state['logits_acc'],np.array(new.last_state['hidden_codes'])@new.weight_codes[1])
                self.assertTrue(all(not b.valid.any() for b in new.banks))

    def test_maximum_adc_and_differential_slices(self):
        weights=(np.zeros((162,96)),np.zeros((96,3)))
        model=BufferedNeuralMapping(*weights,9,sram_word_cycles=2)
        with self.assertRaises(ValueError): model.apply_buffered(np.full(162,0.5),0)
        for tile in model.tiles[0]: tile['cells'][:]=15
        # All positive and negative slices equal at the 16*15 ADC bound.
        np.testing.assert_array_equal(model.apply_buffered(np.ones(162,dtype=np.int64),0),np.zeros(96))

    def test_schedule_added_captures_and_existing_traffic(self):
        for size in [2,3,5,9]:
            model=CompleteSimulation(size,1); before=model.neural.schedule
            driven=readout_activity(model.neural); configure_readout(model,BUFFERED)
            after=model.neural.schedule; activity=readout_activity(model.neural)
            self.assertEqual(after['cycles']-before['cycles'],activity['array_read_bursts'])
            self.assertEqual(activity['array_read_bursts'],before['operations']['array_pulses'])
            self.assertEqual(activity['adc_conversions'],before['operations']['adc_conversions'])
            self.assertEqual(activity['adc_groups'],before['operations']['adc_groups'])
            self.assertEqual(activity['column_samples_captured'],activity['adc_conversions'])
            for key,count in before['operations'].items(): self.assertEqual(after['operations'][key],count)
            for a,b in zip(after['trace'],after['trace'][1:]): self.assertEqual(a['end'],b['start'])
            self.assertEqual(after['trace'][-1]['end'],after['cycles'])
            self.assertLess(activity['array_active_cycles'],driven['array_active_cycles'])
        self.assertEqual(activity['additional_capture_cycles'],81)
        self.assertEqual(activity['maximum_column_hold_ns'],1348)
        self.assertEqual(readout_inventory(model.neural.profile)['installed_analog_samples'],512)

    def test_analog_buffer_cost_and_digital_parent_are_counted_once(self):
        model=CompleteSimulation(9,1); before=component_estimates(model.neural.profile,'cacti_22nm_lstp')
        configure_readout(model,BUFFERED); after=component_estimates(model.neural.profile,'cacti_22nm_lstp')
        digital_delta=(49165.920238-48704.160224+12598.080255-12600.000255)*(22/65)**2
        hold_area=512*(85/15+2*0.35+6.398)
        self.assertAlmostEqual(after['known_area_mm2']-before['known_area_mm2'],
            (digital_delta+hold_area)*1.15/1e6,places=12)
        self.assertEqual([r['area_um2'] for r in before['components'][:3]],
            [r['area_um2'] for r in after['components'][:3]])
        row=next(x for x in after['components'] if x['component']=='Analog column holding cells')
        self.assertEqual(row['count'],512); self.assertAlmostEqual(row['area_um2'],hold_area)
        self.assertAlmostEqual(after['column_capacitor_scenario']['installed_capacitor_area_um2'],512*85/15)
        self.assertIsNone(after['whole_chip_area_mm2']); self.assertIsNone(after['whole_chip_energy_uj'])

    def test_readout_cases_have_distinct_profiles_and_reject_mismatch(self):
        old=configuration({}); new=configuration({'readout_profile':BUFFERED})
        self.assertNotEqual(old['profile'],new['profile'])
        for value in ['unknown',None,False]:
            with self.assertRaises(ValueError): configuration({'readout_profile':value})
        with self.assertRaises(ValueError): configuration({'readout_profile':BUFFERED,'profile':old['profile']})
        self.assertEqual(configuration({'rules':'legacy_go','readout_profile':BUFFERED})['profile'],'single_child_go_host_rules_q32_column_hold_v1')
        self.assertEqual(configuration({'rules':'legacy_go','readout_profile':BUFFERED,'profile':'legacy_go_host_rules_q32_column_hold_v3'})['profile'],'legacy_go_host_rules_q32_column_hold_v3')

    def test_registry_bills_capture_leakage_and_preserves_tree(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'p03_experiments') as folder:
            a,old=run_case(custom={'board_size':3,'iterations':4,'profile':'complete_serial_q32_v2'},runs=folder+'/runs')
            b,new=run_case(custom={'board_size':3,'iterations':4,'readout_profile':BUFFERED,'profile':'complete_serial_q32_column_hold_v2'},runs=folder+'/runs')
            self.assertNotEqual(old['case_id'],new['case_id'])
            self.assertEqual(old['tree_sha256'],new['tree_sha256'])
            self.assertEqual(old['node_sram_sha256'],new['node_sram_sha256'])
            self.assertEqual(old['child_sram_sha256'],new['child_sram_sha256'])
            self.assertEqual(new['metrics']['core_cycles']-old['metrics']['core_cycles'],4*new['analog_readout']['additional_capture_cycles'])
            self.assertGreater(new['costs']['sram']['energy_uj'],old['costs']['sram']['energy_uj'])
            self.assertIsNone(new['metrics']['energy_uj']); self.assertEqual(verify_run(b),new)
            self.assertEqual(new['neural']['profile']['timing_status'],'column_hold_digital_RTL_verified_ideal_interfaces')
            binding=json.loads((ROOT/'core/architecture/column_hold_controller_validation.json').read_text())
            self.assertIn(binding['evidence']['path']+'/metadata.json',new['identity']['source_sha256'])

    def test_old_snapshot_still_verifies(self):
        result=verify_snapshot(ROOT/'p04_results/p04_snapshots/run_20260909_160233Z')
        self.assertEqual(len(result['cases']),7)

    def test_buffered_play_retains_profile_and_sums_searches(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'p03_experiments') as folder:
            play=BoardPlay({'board_size':2,'iterations':2,'readout_profile':BUFFERED},folder+'/plays')
            out,result=play.run(lambda row,model:None,lambda move,model:None)
            searches=[verify_run(out/'p01_searches'/move['search_run']) for move in play.moves]
            self.assertEqual(result['metrics']['completed_moves'],4)
            self.assertEqual(result['identity']['readout_profile'],BUFFERED)
            self.assertEqual(result['metrics']['core_cycles'],sum(row['metrics']['core_cycles'] for row in searches))
            self.assertTrue(all(row['analog_readout']['profile']==BUFFERED for row in searches))
            self.assertEqual(result['publication_status'],'column_hold_candidate_not_physically_or_task_validated')
            with (out/'summary.csv').open() as stream: row=next(csv.DictReader(stream))
            self.assertEqual(row['readout_profile'],BUFFERED)

    def test_freeze_earlier_and_buffered_results_together(self):
        old=json.loads((ROOT/'p04_results/p04_snapshots/run_20260909_160233Z/manifest.json').read_text())['cases'][0]['runs']
        with tempfile.TemporaryDirectory(dir=ROOT/'p03_experiments') as folder:
            config={'board_size':3,'iterations':1,'readout_profile':BUFFERED}
            a,_=run_case(custom=config,runs=folder+'/runs'); b,_=run_case(custom=config,runs=folder+'/runs')
            out=freeze_repeats([(ROOT/old[0],ROOT/old[1]),(a,b)],snapshots=Path(folder)/'snapshots')
            self.assertEqual(len(verify_snapshot(out)['cases']),2)
            with (out/'summary.csv').open() as stream: rows=list(csv.DictReader(stream))
            self.assertEqual([row['readout_profile'] for row in rows],['sustained_drive_v1',BUFFERED])


if __name__=='__main__': unittest.main()
