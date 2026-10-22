# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Report units, installed module ownership and scenario provenance.
# SPDX-License-Identifier: MIT
import csv
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from core.architecture.analog_readout import BUFFERED, configure_readout
from core.architecture.complete_costs import complete_costs
from core.architecture.crossbar_workbook import component_estimates
from core.architecture.digital_costs import ROOT, CHARACTERIZATION, build_characterization, digital_accounting, digital_timing_fields, load_digital_profile
from core.architecture.iteration_model import CompleteSimulation
from core.architecture.result_registry import run_case, verify_run
from core.architecture.result_snapshot import summary_row


class DigitalCostTests(unittest.TestCase):
    def test_native_report_units_warnings_and_parameters(self):
        profile=load_digital_profile(); cases=profile['cases']
        self.assertEqual(len(cases),18); self.assertEqual(profile['missing_cases'],[])
        neural=cases['imc_buffered_neural_sequencer']
        self.assertEqual(neural['area']['cell_um2'],49165.920238)
        self.assertEqual(neural['power']['dynamic_mw'],6.0119)
        self.assertAlmostEqual(neural['power']['leakage_mw'],.1400118)
        self.assertAlmostEqual(cases['imc_column_hold_control']['power']['dynamic_mw'],.071547)
        self.assertEqual(neural['parameters'],{'INPUTS':162,'HIDDEN':96,'ADDR_W':21,'SRAM_BYTES':1572864})
        self.assertEqual(neural['checks']['max_capacitance_violations'],1)
        self.assertEqual(cases['imc_cached_selector']['checks']['max_capacitance_violations'],5)
        self.assertIn('PWR-414',neural['checks']['warning_codes'])
        self.assertEqual(cases['imc_fixed_scale']['timing']['constraint_kind'],'input-to-output max delay')
        self.assertTrue(all(c['timing']['violating_setup_paths']==0 for name,c in cases.items() if name!='imc_tree_update'))
        update=cases['imc_tree_update_v2']
        self.assertEqual(update['area']['cell_um2'],35855.520030)
        self.assertEqual(update['power']['dynamic_mw'],4.3517)
        self.assertAlmostEqual(update['power']['leakage_mw'],.1201442)
        self.assertEqual(update['timing']['critical_slack_ns'],0)
        self.assertEqual(update['timing']['violating_setup_paths'],0)
        self.assertEqual(update['checks']['max_capacitance_violations'],0)
        self.assertTrue(all(c['power']['workload_energy_uj'] is None for c in cases.values()))

    def test_installed_parents_include_children_and_share_update(self):
        model=CompleteSimulation(9,1)
        ledger=digital_accounting(model.neural.profile,model.memory.config)
        self.assertEqual(ledger['priced_instances'],7)
        expected=99926.880144+90935.040461+48704.160224+2308.320027+1779.360027+35855.520030+12600.000255
        self.assertAlmostEqual(ledger['known_native_65nm_area_um2'],expected)
        self.assertAlmostEqual(ledger['known_area_mm2'],expected*(22/65)**2/1e6)
        rows={r['instance']:r for r in ledger['components']}
        self.assertEqual(len(rows),7)
        self.assertEqual(rows['u_upd']['owner_phases'],['expansion','backpropagation'])
        self.assertAlmostEqual(rows['u_upd']['area_um2'],35855.520030*(22/65)**2)
        self.assertEqual({r['instance']:r['inclusive_area_um2'] for r in rows['u_upd']['includes']},{'u_choice':1198.08,'u_codec':5514.72})
        self.assertAlmostEqual(rows['top_level_glue']['area_um2'],12600.000255*(22/65)**2)
        self.assertEqual(rows['top_level_glue']['includes'],[])
        self.assertEqual(digital_timing_fields(ledger)['digital_65nm_setup_violating_paths'],0)
        self.assertEqual(digital_timing_fields(ledger)['digital_65nm_timing_failed_modules'],'')
        self.assertEqual({x['design'] for x in rows['u_nn']['includes']},
            {'imc_shift_accumulator','imc_fixed_scale','imc_round_divider'})
        configure_readout(model,BUFFERED)
        buffered=digital_accounting(model.neural.profile,model.memory.config)
        delta=buffered['known_native_65nm_area_um2']-ledger['known_native_65nm_area_um2']
        self.assertAlmostEqual(delta,461.760014-1.92)
        self.assertNotAlmostEqual(delta,599.520003)  # Standalone holding control cannot be added to the parent.
        self.assertEqual(buffered['priced_instances'],7)
        parent=next(r for r in buffered['components'] if r['instance']=='u_nn')
        self.assertIn('u_column_hold',[child['instance'] for child in parent['includes']])

    def test_mismatched_sizes_and_precision_do_not_borrow_9x9_costs(self):
        model=CompleteSimulation(5,1)
        ledger=digital_accounting(model.neural.profile,model.memory.config)
        self.assertEqual(ledger['priced_instances'],3)
        for instance in ('u_sel','u_nn','u_upd'):
            self.assertIsNone(next(r for r in ledger['components'] if r['instance']==instance)['area_um2'])
        self.assertEqual(ledger['timing_violations'],[])
        self.assertEqual(digital_timing_fields(ledger)['digital_65nm_timing_status'],'no_reported_failure_in_priced_modules')
        model=CompleteSimulation(9,1,cam_entries=512)
        ledger=digital_accounting(model.neural.profile,model.memory.config)
        self.assertEqual(ledger['priced_instances'],4)
        changed=digital_accounting(model.neural.profile | {'adc_lanes':6},model.memory.config)
        self.assertEqual(changed['priced_instances'],3)
        with self.assertRaises(ValueError): digital_accounting(model.neural.profile,{'node_sram_bytes':524289})

    def test_absent_report_stays_unpriced_and_cannot_claim_timing_success(self):
        profile=load_digital_profile(); profile['cases'].pop('imc_tree_update_v2')
        with patch('core.architecture.digital_costs.load_digital_profile',return_value=profile):
            ledger=digital_accounting(CompleteSimulation(9,1).neural.profile)
        update=next(r for r in ledger['components'] if r['instance']=='u_upd')
        self.assertEqual(update['status'],'Missing module report')
        self.assertIsNone(update['area_um2']); self.assertIsNone(update['timing'])
        self.assertEqual(ledger['priced_instances'],6)
        self.assertEqual(digital_timing_fields(ledger)['digital_65nm_timing_status'],'no_reported_failure_in_priced_modules')
        self.assertIsNone(digital_timing_fields(None)['digital_65nm_timing_status'])

    def test_workload_does_not_replicate_hardware_or_import_vectorless_energy(self):
        model=CompleteSimulation(9,3); before=component_estimates(model.neural.profile,'cacti_22nm_lstp',model.memory.config)
        list(model.steps())
        costs=complete_costs('cacti_22nm_lstp',model.memory.operations,model.cycles,
            model.neural.profile,model.memory.config,model.phase_cycles)
        baseline=complete_costs('cacti_22nm_lstp',model.memory.operations,model.cycles)
        self.assertEqual(costs['sram'],baseline['sram'])
        digital=costs['digital']; self.assertEqual(digital['known_area_mm2'],before['digital']['known_area_mm2'])
        self.assertIsNone(digital['energy_uj']); self.assertIsNone(digital['power_mw'])
        self.assertIsNone(costs['whole_chip']['energy_uj'])
        self.assertEqual(costs['coverage'][0]['scaling_applications'],0)
        self.assertEqual(digital['power_conversion']['applications'],0)
        self.assertIsNone(costs['timing_warning'])
        memory_and_cells=sum(row['area_um2'] for row in before['components'] if row['id'] in ('node_sram','child_sram','cim_arrays'))/1e6
        self.assertAlmostEqual(memory_and_cells,1.6626054528)
        rows={r['instance']:r for r in digital['components']}
        self.assertEqual(rows['u_ucb']['requests'],model.memory.operations['ucb_operations'])
        self.assertEqual(rows['u_upd']['owner_phase_cycles'],model.phase_cycles['expansion']+model.phase_cycles['backpropagation'])
        self.assertEqual(rows['u_node_router']['word_requests']['read'],model.memory.operations['node_sram_read_words'])

    def test_changed_catalog_or_report_is_rejected(self):
        profile=load_digital_profile()
        with tempfile.TemporaryDirectory(dir=ROOT/'p03_experiments') as directory:
            base=Path(directory); candidate=base/'catalog.json'
            changed=json.loads(CHARACTERIZATION.read_text()); changed['cases']['imc_ucb_score']['area']['cell_um2']+=1
            candidate.write_text(json.dumps(changed))
            with patch('core.architecture.digital_costs.CHARACTERIZATION',candidate):
                with self.assertRaisesRegex(ValueError,'differs'): load_digital_profile()
            source=ROOT/profile['source_import']; copied=base/'source'
            for name in profile['source_files']:
                path=ROOT/name
                if not path.is_relative_to(source): continue
                target=copied/path.relative_to(source); target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,target)
            build_characterization(copied,verify_all=False)
            area=copied/'results/imc_ucb_score/area.rpt'
            area.write_text(area.read_text().replace('90935.040461','1.000000'))
            with self.assertRaisesRegex(ValueError,'hash mismatch'): build_characterization(copied,verify_all=False)

    def test_glue_report_scope_units_and_constraint_warnings(self):
        profile=load_digital_profile()
        for name,area,aliases in [('imc_iteration_glue',12600.000255,2166),('imc_buffered_iteration_glue',12598.080255,2179)]:
            with self.subTest(top=name):
                record=profile['cases'][name]
                self.assertEqual(record['design'],name)
                self.assertEqual(record['area']['cell_um2'],area)
                self.assertEqual(record['hierarchy'],[])
                self.assertEqual(record['timing']['violating_setup_paths'],0)
                self.assertEqual(record['checks']['constraint_violation_counts'],
                    {'max_capacitance':2,'max_leakage_power':1,'multiport_net':aliases})
                self.assertIn('LINT-31',record['checks']['warning_codes'])
                self.assertIsNone(record['power']['target_22nm_power_mw'])
                self.assertIsNone(record['power']['workload_energy_uj'])
                self.assertIn('units.rpt',record['reports'])

    def test_glue_cost_rejects_incompatible_interfaces_and_memory(self):
        model=CompleteSimulation(9,1)
        for neural,memory in [
            (model.neural.profile | {'adc_lanes':6},model.memory.config),
            (model.neural.profile | {'hidden_size':32},model.memory.config),
            (model.neural.profile,model.memory.config | {'cam_entries':512}),
            (model.neural.profile,model.memory.config | {'node_sram_bytes':1048576}),
            (model.neural.profile,model.memory.config | {'neural_bytes':16000}),
            (model.neural.profile,model.memory.config | {'tree_update_timing_profile':'old'})]:
            row=next(r for r in digital_accounting(neural,memory)['components'] if r['instance']=='top_level_glue')
            self.assertIsNone(row['area_um2'])
            self.assertIsNone(row['native_65nm_power'])
            self.assertEqual(row['scaling_applications'],0)

    def test_missing_glue_report_does_not_borrow_other_readout(self):
        profile=load_digital_profile(); profile['cases'].pop('imc_iteration_glue')
        model=CompleteSimulation(9,1)
        with patch('core.architecture.digital_costs.load_digital_profile',return_value=profile):
            ledger=digital_accounting(model.neural.profile,model.memory.config)
        row=next(r for r in ledger['components'] if r['instance']=='top_level_glue')
        self.assertEqual(row['status'],'Missing module report')
        self.assertIsNone(row['area_um2'])
        self.assertEqual(ledger['priced_instances'],6)

    def test_glue_area_is_installed_once_but_its_energy_stays_missing(self):
        model=CompleteSimulation(9,2); list(model.steps())
        result=complete_costs('cacti_22nm_lstp',model.memory.operations,model.cycles,
            model.neural.profile,model.memory.config,model.phase_cycles)
        rows=[r for r in result['ledger']['components'] if r['id']=='top_level_glue']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['count'],1)
        self.assertEqual(rows[0]['scaling_applications'],1)
        self.assertIsNone(rows[0]['energy_uj'])
        self.assertNotIn(rows[0]['component'],result['ledger']['missing_area'])
        self.assertIn(rows[0]['component'],result['ledger']['missing_energy'])

    def test_run_and_csv_pin_report_identity_and_remain_repeatable(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'p03_experiments') as directory:
            first,a=run_case(custom={'board_size':9,'iterations':2},runs=Path(directory)/'runs')
            second,b=run_case(custom={'board_size':9,'iterations':2},runs=Path(directory)/'runs')
            self.assertEqual(a,b); self.assertEqual(a,verify_run(first)); self.assertEqual(b,verify_run(second))
            self.assertIn('core/architecture/digital_characterization.json',a['identity']['source_sha256'])
            report=next(name for name in a['identity']['source_sha256'] if name.endswith('/imc_ucb_score/area.rpt'))
            with tarfile.open(first/'source_snapshot.tar.gz') as archive:
                self.assertEqual(archive.extractfile(report).read(),(ROOT/report).read_bytes())
            with (first/'summary.csv').open() as stream: row=next(csv.DictReader(stream))
            self.assertEqual(float(row['digital_area_22nm_estimate_mm2']),a['costs']['digital']['known_area_mm2'])
            self.assertEqual(row['whole_chip_power_mw'],'')
            self.assertEqual(row['digital_65nm_setup_violating_paths'],'0')
            self.assertEqual(row['digital_65nm_timing_failed_modules'],'')
            self.assertEqual(row['digital_65nm_timing_status'],'no_reported_failure_in_priced_modules')
            self.assertNotIn('digital_priced_instances',summary_row(first,a,include_readout=True,include_digital=False,include_timing=False))
            self.assertNotIn('digital_65nm_timing_status',summary_row(first,a,include_readout=True,include_digital=True,include_timing=False))


if __name__=='__main__': unittest.main()
