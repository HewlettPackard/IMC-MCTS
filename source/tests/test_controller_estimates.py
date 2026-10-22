# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Report-proxy admission, source arithmetic, identity and unchanged physical memory.
# SPDX-License-Identifier: MIT
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.algorithm.model_catalog import load_model
from core.architecture.analog_readout import configure_readout
from core.architecture.complete_costs import complete_costs, prepare_costs
from core.architecture.controller_estimates import ASSUMPTIONS, estimate_policy
from core.architecture.digital_costs import digital_accounting, load_digital_profile
from core.architecture.single_child import SingleChildGoSimulation, SingleChildSimulation


def model_for(model_id='go_strong_v1', readout='sustained_drive_v1'):
    weights, record=load_model(model_id,9)
    model=SingleChildGoSimulation(board_size=9,iterations=3,weights=weights,
        turn_indicator=bool(record.get('turn_indicator')))
    configure_readout(model,readout)
    return model


class ControllerEstimateTests(unittest.TestCase):
    def test_four_proxies_complete_reviewed_go_geometry(self):
        for name in ('go_strong_v1','go_weak_v1'):
            for mode in ('sustained_drive_v1','column_hold_v1'):
                with self.subTest(name=name,mode=mode):
                    model=model_for(name,mode); list(model.steps())
                    costs=complete_costs('cacti_22nm_lstp',model.memory.operations,model.cycles,
                        model.neural.profile,model.memory.config,model.phase_cycles,model.block_active_cycles)
                    ledger=costs['ledger']
                    self.assertEqual(ledger['missing_area'],[]); self.assertEqual(ledger['missing_energy'],[])
                    self.assertEqual(set(ledger['controller_report_proxy_components']),{'u_sel','u_upd','u_nn','top_level_glue'})
                    self.assertIsNone(ledger['whole_chip_area_mm2'])
                    self.assertEqual(ledger['modeled_core_area_mm2'],ledger['known_area_mm2'])
                    self.assertEqual(len(model.memory.node_sram)+len(model.memory.child_sram),2097152)
                    catalog=load_digital_profile()['cases']
                    for row in ledger['components']:
                        if not row.get('report_proxy'): continue
                        raw=catalog[row['case']]
                        self.assertAlmostEqual(row['area_um2'],raw['area']['cell_um2']*1.25*(22/65)**2)
                        self.assertIsNone(row['native_65nm_area_um2']); self.assertIsNone(row['timing'])
                        self.assertIsNone(row['native_65nm_power']); self.assertEqual(row['includes'],[])
                        self.assertEqual(row['block_power']['status'],'controller_report_proxy_estimate')
                        p=row['block_power']; elapsed=model.cycles/500
                        expected=1.25*(raw['power']['dynamic_mw']*p['active_us']+
                            p['powers_mw']['idle_dynamic_mw']/1.25*p['idle_us'])*(22/65)*.8**2
                        self.assertAlmostEqual(p['target_22nm_dynamic_energy_nj'],expected)
                        self.assertAlmostEqual(p['target_22nm_leakage_energy_nj'],1.25*raw['power']['leakage_mw']*elapsed)

    def test_exact_neural_report_does_not_get_allowance(self):
        model=model_for('archive_9x9_h96_centered_v1')
        ledger=digital_accounting(model.neural.profile,model.memory.config)
        row=next(row for row in ledger['components'] if row['instance']=='u_nn')
        self.assertNotIn('report_proxy',row)
        self.assertIsNotNone(row['native_65nm_area_um2'])
        self.assertEqual(len(ledger['report_proxy_instances']),3)

    def test_unreviewed_geometry_stays_missing(self):
        model=model_for()
        changes=[({'hidden_size':32},{}),({'adc_lanes':6},{}),({'input_size':164},{}),
            ({},{'cam_entries':512}),({},{'node_sram_bytes':2097152}),
            ({},{'tree_update_timing_profile':'other'}),({},{'neural_bytes':20000})]
        for neural,memory in changes:
            with self.subTest(neural=neural,memory=memory):
                ledger=digital_accounting(model.neural.profile|neural,model.memory.config|memory)
                self.assertFalse(any(row.get('report_proxy') for row in ledger['components']))
        small=SingleChildSimulation(2,1)
        self.assertFalse(any(row.get('report_proxy') for row in digital_accounting(small.neural.profile,small.memory.config)['components']))

    def test_missing_source_cannot_be_filled_with_a_proxy(self):
        model=model_for(); profile=load_digital_profile(); profile['cases'].pop('imc_tree_update_v2')
        with patch('core.architecture.digital_costs.load_digital_profile',return_value=profile):
            row=next(row for row in digital_accounting(model.neural.profile,model.memory.config)['components'] if row['instance']=='u_upd')
        self.assertIsNone(row['area_um2']); self.assertNotIn('report_proxy',row)

    def test_prepared_live_and_final_costs_agree(self):
        model=model_for(); prepared=prepare_costs('cacti_22nm_lstp',model.neural.profile,model.memory.config)
        for event in model.steps():
            if event['phase']!='iteration_commit': continue
            args=('cacti_22nm_lstp',model.memory.operations,model.cycles,model.neural.profile,
                model.memory.config,model.phase_cycles,model.block_active_cycles)
            self.assertEqual(complete_costs(*args),complete_costs(*args,prepared=prepared))

    def test_allowance_change_needs_new_reviewed_policy(self):
        policy=estimate_policy(); policy['nominal_multiplier']=0
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'policy.json'; file.write_text(json.dumps(policy))
            with patch('core.architecture.controller_estimates.ASSUMPTIONS',file):
                with self.assertRaises(ValueError): estimate_policy()


if __name__=='__main__': unittest.main()
