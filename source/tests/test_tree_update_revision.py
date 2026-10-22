# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Reject cross-revision cost reuse and stale requested execution profiles.
# SPDX-License-Identifier: MIT
import unittest
from unittest.mock import patch

from core.architecture.digital_costs import digital_accounting, load_digital_profile
from core.architecture.complete_costs import complete_costs
from core.architecture.iteration_model import CompleteSimulation
from core.architecture.result_registry import configuration


class TreeUpdateRevisionTests(unittest.TestCase):
    def test_old_execution_profiles_cannot_silently_run_new_hardware(self):
        for config in ({'profile':'complete_serial_q32_v1'},
                {'profile':'complete_serial_q32_column_hold_v1','readout_profile':'column_hold_v1'},
                {'profile':'legacy_go_host_rules_q32_v1','rules':'legacy_go'}):
            with self.subTest(config=config), self.assertRaises(ValueError): configuration(config)
        self.assertEqual(configuration({})['profile'],'single_child_placement_q32_v1')
        self.assertEqual(configuration({'profile':'complete_serial_q32_v2'})['profile'],'complete_serial_q32_v2')
        self.assertEqual(configuration({'readout_profile':'column_hold_v1'})['profile'],'single_child_placement_q32_column_hold_v1')
        self.assertEqual(configuration({'profile':'complete_serial_q32_column_hold_v2','readout_profile':'column_hold_v1'})['profile'],'complete_serial_q32_column_hold_v2')

    def test_unknown_or_old_schedule_does_not_borrow_v2_area(self):
        model=CompleteSimulation(9,1)
        for revision in (None,'combinational_remainder_v1','registered_count_iterative_remainder_v2_candidate'):
            config=model.memory.config | {'tree_update_timing_profile':revision}
            ledger=digital_accounting(model.neural.profile,config)
            update=next(row for row in ledger['components'] if row['instance']=='u_upd')
            self.assertEqual(ledger['priced_instances'],5)
            self.assertIsNone(update['area_um2']); self.assertIsNone(update['timing'])
            self.assertIn('schedule differs',update['status'])

    def test_old_failed_report_remains_historical_evidence(self):
        cases=load_digital_profile()['cases']
        self.assertEqual(cases['imc_tree_update']['rtl_status'],'historical_replaced_by_v2')
        self.assertEqual(cases['imc_tree_update']['timing']['violating_setup_paths'],386)
        self.assertEqual(cases['imc_tree_update_v2']['rtl_status'],'matches_active_sources')
        self.assertEqual(cases['imc_tree_update_v2']['timing']['violating_setup_paths'],0)
        self.assertNotEqual(cases['imc_tree_update']['reports']['area.rpt'],cases['imc_tree_update_v2']['reports']['area.rpt'])

    def test_different_memory_capacities_do_not_borrow_default_tree_area(self):
        model=CompleteSimulation(9,1)
        config=model.memory.config | {'node_sram_bytes':1048576}
        ledger=digital_accounting(model.neural.profile,config)
        for row in ledger['components']:
            if row['instance'] in ('u_sel','u_upd'):
                self.assertIsNone(row['area_um2'])
                self.assertIn('NODE_BYTES/CHILD_BYTES',row['status'])

    def test_reported_failure_still_propagates_for_a_future_revision(self):
        profile=load_digital_profile(); model=CompleteSimulation(9,1)
        profile['cases']['imc_tree_update_v2']['timing'].update(critical_slack_ns=-.2,violating_setup_paths=1)
        with patch('core.architecture.digital_costs.load_digital_profile',return_value=profile):
            costs=complete_costs('cacti_22nm_lstp',{},1,model.neural.profile,model.memory.config)
        self.assertIn('imc_tree_update_v2',costs['timing_warning'])
        self.assertEqual(costs['digital']['timing_violations'][0]['violating_setup_paths'],1)


if __name__=='__main__': unittest.main()
