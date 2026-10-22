# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import csv
import json
from pathlib import Path
import tempfile
import unittest

from core.algorithm.model_catalog import load_model
from core.architecture.board_sizing import PROFILE, board_table, sized_memory
from core.architecture.sized_simulation import SizedSingleChildSimulation, SizedSingleChildGoSimulation
from core.architecture.single_child import SingleChildGoSimulation
from core.architecture.result_registry import ROOT, configuration, run_case, verify_run
from core.architecture.run_identity import tree_sha256
from core.architecture.sram_costs import load_sram_profile
from core.architecture.complete_costs import complete_costs
from core.architecture.crossbar_workbook import component_estimates
from core.architecture.analog_readout import configure_readout
from tests.test_single_child import compare_reference


class BoardSizingTests(unittest.TestCase):
    def test_s1_table_and_installed_storage(self):
        # Approved paper table is independent of runtime configuration.
        path=ROOT/'p03_experiments/p80_blue_scaling_table/p00_runs/run_20260917_162012Z/p02_data/proposed_configurations.csv'
        with path.open() as stream: approved=list(csv.DictReader(stream))
        self.assertEqual(len(approved),6)
        for row in board_table()['boards']:
            b=row['board_size']
            source=next(item for item in approved if int(item['board_size'])==b)
            for key in ('cam_entries','node_sram_kib','child_sram_kib'):
                self.assertEqual(row[key],int(source[key]))
            for tier in ('low','medium','high'):
                self.assertEqual(row['iterations'][tier],int(source[tier]))
            model=SizedSingleChildGoSimulation(b,3)
            memory=model.memory.config
            self.assertEqual(len(model.memory.node_sram),row['node_sram_kib']*1024)
            self.assertEqual(len(model.memory.child_sram),row['child_sram_kib']*1024)
            self.assertEqual(memory['cam_entries'],row['cam_entries'])
            self.assertEqual(memory['path_storage_entries'],2*b*b+1)
            self.assertEqual(memory['path_storage_entries'],model.game._max_moves+1)
            self.assertGreaterEqual(memory['node_capacity'],row['iterations']['high']+1)
            self.assertGreaterEqual(memory['edge_capacity'],row['iterations']['high'])
            self.assertEqual(row['iterations']['high'],2*row['iterations']['medium'])
            self.assertLessEqual(memory['node_base']+memory['node_capacity']*memory['node_stride'],memory['node_sram_bytes'])
            preview=sized_memory(model.neural.profile,rules='legacy_go')
            for key in ('node_base','node_stride','node_capacity','edge_capacity','path_storage_entries','neural_base'):
                self.assertEqual(memory[key],preview[key],(b,key))
            for flavor in ('hp','lstp'):
                cfg=configuration({'board_size':b,'hardware_profile':PROFILE,'memory_profile':'cacti_22nm_'+flavor})
                macro=load_sram_profile(cfg['memory_profile'])
                self.assertEqual(macro['sram_word_cycles'],memory['sram_word_cycles'])
                for pool in ('node_sram','child_sram'):
                    self.assertEqual(macro['bank_bytes']*macro['banks'][pool],memory[pool+'_bytes'])

    def test_small_go_path_regression_and_policy_oracle(self):
        model=SizedSingleChildGoSimulation(2,400)
        compare_reference(self,model)
        self.assertEqual((model.status,model.completed),('complete',400))
        self.assertGreater(model.memory.path_high_water,5)

    def test_large_board_matches_policy_oracle(self):
        for b in (13,19):
            for engine in (SizedSingleChildSimulation,SizedSingleChildGoSimulation):
                compare_reference(self,engine(b,12,seed=2))

    def test_trained_outputs_unchanged(self):
        for name in ('go_strong_v1','go_weak_v1'):
            weights,_=load_model(name,9)
            models=[engine(9,100,weights=weights,turn_indicator=True) for engine in (SingleChildGoSimulation,SizedSingleChildGoSimulation)]
            for model in models: list(model.steps())
            self.assertEqual(tree_sha256(models[0].memory.nodes),tree_sha256(models[1].memory.nodes))
            self.assertEqual(models[0].history,models[1].history)
            self.assertEqual(models[0].neural.last_state,models[1].neural.last_state)

    def test_quota_and_hardware_identity_guards(self):
        for bad in ({'cam_entries':127},{'memory_profile':'cacti_22nm_s1_b9_hp'},
                    {'profile':'single_child_placement_q32_v1'},{'hardware_profile':'typo'}):
            with self.assertRaises(ValueError): configuration({'board_size':2,'hardware_profile':PROFILE}|bad)
        for limits in ({'nodes':999999},{'edges':999999},{'path_entries':10},{'nodes':True}):
            with self.assertRaises(ValueError): SizedSingleChildGoSimulation(2,20,memory_limits=limits)
        model=SizedSingleChildGoSimulation(2,20,memory_limits={'nodes':3})
        list(model.steps())
        self.assertEqual((model.status,model.completed),('memory_limited',3))
        self.assertNotIn('hardware_profile',configuration({'board_size':2}))

    def test_run_preview_and_export_agree(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            for b,readout in ((2,'sustained_drive_v1'),(19,'column_hold_v1')):
                config={'board_size':b,'iterations':3,'rules':'legacy_go','hardware_profile':PROFILE,'readout_profile':readout}
                out,result=run_case(custom=config,runs=Path(folder)/'runs')
                self.assertEqual(result,verify_run(out))
                effective=result['identity']['configuration']
                memory=effective['memory'];neural=effective['neural_profile']
                self.assertEqual(effective['requested']['profile'],memory['execution_profile'])
                self.assertEqual(result['component_estimates'],component_estimates(neural,effective['requested']['memory_profile'],memory))
                for pool,row in result['costs']['sram']['pools'].items():
                    self.assertEqual(row['capacity_bytes'],memory[pool+'_bytes'])
                with (out/'summary.csv').open() as stream: exported=next(csv.DictReader(stream))
                self.assertEqual(int(exported['node_sram_bytes']),memory['node_sram_bytes'])
                self.assertEqual(int(exported['cam_entries']),memory['cam_entries'])
                cam=next(row for row in result['component_estimates']['components'] if row['id']=='cam_macro')
                self.assertEqual(cam['logical_entries'],memory['cam_entries'])
                self.assertIsNotNone(cam['area_um2'])


if __name__=='__main__': unittest.main()
