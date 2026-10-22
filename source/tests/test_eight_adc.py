# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Numeric column replay, service scheduling, fixed-memory search and cost ownership.
# SPDX-License-Identifier: MIT
from collections import Counter
from copy import deepcopy
import unittest

import numpy as np

from core.algorithm.model_catalog import load_model
from core.architecture.analog_readout import configure_readout
from core.architecture.component_inventory import inventory_rows
from core.architecture.eight_adc import EightADCSimulation,EightADCGoSimulation
from core.architecture.eight_adc_costs import eight_adc_costs,prepare_eight_adc_costs
from core.architecture.parallel_selection import FourLaneSimulation,FourLaneGoSimulation,LANES
from core.architecture.parallel_selection_costs import parallel_costs
from p03_experiments.p70_eight_adc.group_reference import replay_layer


def models(iterations=100,model_id='go_strong_v1'):
    weights,entry=load_model(model_id,9)
    a=FourLaneGoSimulation(9,iterations,weights=weights,turn_indicator=entry['turn_indicator'])
    configure_readout(a,'sustained_drive_v1')
    b=EightADCGoSimulation(9,iterations,weights=weights,turn_indicator=entry['turn_indicator'])
    return a,b


class EightADCTests(unittest.TestCase):
    def test_lane_word_replay_matches_signed_products_and_tails(self):
        rng=np.random.RandomState(7)
        for rows,outputs,bits in ((163,96,1),(96,3,8),(17,35,8),(16,2,8)):
            x=rng.randint(0,1<<bits,size=rows); w=rng.randint(-127,128,size=(rows,outputs))
            expected=[sum(int(x[r])*int(w[r,c]) for r in range(rows)) for c in range(outputs)]
            for lanes in (3,8):
                result,counts,groups=replay_layer(x,w,bits,lanes)
                self.assertEqual(result,expected)
                self.assertEqual(counts['adc_conversions'],counts['shift_adds'])
                self.assertTrue(all(g['bus_words']==(g['valid_lanes']+3)//4 for g in groups))
                if lanes==8 and outputs==3:
                    self.assertEqual({g['valid_lanes'] for g in groups},{4,8})
                if lanes==8 and outputs==2:
                    self.assertEqual({g['valid_lanes'] for g in groups},{8})

    def test_trained_neural_intermediates_match_independent_group_replay(self):
        rng=np.random.RandomState(11)
        for model_id in ('go_strong_v1','go_weak_v1'):
            _,model=models(1,model_id); neural=model.neural
            for player in (-1,1):
                board=rng.choice([-1,0,1],size=(9,9)); neural.forward(board,player=player)
                hidden,first,_=replay_layer(neural.features(board,player),neural.weight_codes[0],1)
                logits,second,_=replay_layer(neural.last_state['hidden_codes'],neural.weight_codes[1],8)
                self.assertEqual(hidden,neural.last_state['hidden_acc'])
                self.assertEqual(logits,neural.last_state['logits_acc'])
                for key,value in (Counter(first)+Counter(second)).items():
                    self.assertEqual(value,neural.schedule['operations'][key],key)

    def test_schedule_charges_eight_lanes_two_words_and_serial_accumulation(self):
        serial,model=models(1); trace=model.neural.schedule['trace']
        operations=model.neural.schedule['operations']
        self.assertEqual(operations['adc_groups'],33*16+48*2)
        self.assertEqual(operations['adc_conversions'],33*128+48*12)
        self.assertEqual(operations['readout_words'],33*32+48*3)
        self.assertEqual(operations['shift_adds'],4800)
        cursor=0
        for row in trace:
            self.assertEqual(row['start'],cursor); cursor=row['end']
            if row['operation']=='adc_groups':
                self.assertEqual(row['end']-row['start'],9)
                self.assertIn(row['conversions'],(4,8))
            if row['operation']=='readout_words': self.assertEqual(row['end']-row['start'],row['count'])
            if row['operation']=='shift_adds': self.assertEqual(row['end']-row['start'],row['count'])
        self.assertEqual(cursor,model.neural.schedule['cycles'])
        for m in (serial,model): list(m.steps())
        self.assertEqual(serial.phase_cycles['neural'],26626)
        self.assertEqual(model.phase_cycles['neural'],14371)
        self.assertEqual(serial.cycles-model.cycles,12255)
        self.assertEqual(model.neural.schedule['resources']['adc_register_bits'],64)
        self.assertEqual(model.neural.schedule['resources']['shift_add_lanes'],1)
        self.assertEqual(model.neural.profile['readout_activity']['adc_groups'],624)

    def test_every_search_phase_preserves_neural_state_tree_and_sram(self):
        for a,b in (models(100),models(100,'go_weak_v1'),
                    (FourLaneSimulation(2,60,seed=3),EightADCSimulation(2,60,seed=3))):
            for old,new in zip(a.steps(),b.steps()):
                for key in ('phase','iteration','selected_node','nodes','edges'): self.assertEqual(old[key],new[key])
                if old['phase']=='neural': self.assertEqual(a.neural.last_state,b.neural.last_state)
                if old['phase']=='iteration_commit':
                    self.assertEqual(a.value_q17,b.value_q17); self.assertEqual(a.random_state,b.random_state)
            self.assertEqual(a.completed,a.iterations); self.assertEqual(b.completed,b.iterations)
            self.assertEqual(a.memory.node_sram,b.memory.node_sram)
            self.assertEqual(a.memory.child_sram,b.memory.child_sram)
            self.assertEqual(a.batch_counts,b.batch_counts)
            for lane in LANES: self.assertEqual(a.block_active_cycles[lane],b.block_active_cycles[lane])
            self.assertEqual(len(b.memory.node_sram)+len(b.memory.child_sram),2*1024*1024)
            for phase in a.phase_cycles:
                if phase!='neural': self.assertEqual(a.phase_cycles[phase],b.phase_cycles[phase])

    def test_capacity_failure_matches_four_lane_reference(self):
        for cls in (FourLaneSimulation,EightADCSimulation):
            model=cls(2,50,memory_limits={'nodes':3}); list(model.steps())
            self.assertEqual(model.status,'memory_limited'); self.assertEqual(model.completed,3)

    def test_costs_price_all_analog_lanes_and_changed_controller(self):
        a,b=models(10)
        for m in (a,b): list(m.steps())
        old=parallel_costs(a)['ledger']; prepared=prepare_eight_adc_costs(b); before=deepcopy(prepared)
        costs=eight_adc_costs(b,prepared=prepared); ledger=costs['ledger']
        self.assertEqual(prepared,before)
        self.assertEqual(costs,eight_adc_costs(b,prepared=prepared))
        rows={r['id']:r for r in ledger['components']}; previous={r['id']:r for r in old['components']}
        self.assertEqual(ledger['missing_area'],[]); self.assertEqual(ledger['missing_energy'],[])
        self.assertIsNone(ledger['whole_chip_area_mm2'])
        for name in ('adc_lanes','sample_hold'):
            self.assertEqual(rows[name]['count'],8)
            self.assertAlmostEqual(rows[name]['area_um2']/previous[name]['area_um2'],8/3)
            self.assertAlmostEqual(rows[name]['dynamic_energy_uj'],previous[name]['dynamic_energy_uj'])
            self.assertAlmostEqual(rows[name]['cost_model']['standby_mw'],previous[name]['cost_model']['standby_mw']*8/3)
            if name=='adc_lanes':self.assertGreater(rows[name]['cost_model']['standby_mw'],0)
        self.assertEqual(rows['analog_mux']['count'],previous['analog_mux']['count'])
        self.assertAlmostEqual(rows['u_nn']['area_um2']/previous['u_nn']['area_um2'],1.5/1.25)
        self.assertEqual(rows['u_nn']['adc_register_bits'],64)
        for lane in LANES: self.assertEqual(rows[lane]['area_um2'],previous[lane]['area_um2'])
        self.assertAlmostEqual(ledger['known_area_mm2']*1e6,sum(r['area_um2'] or 0 for r in rows.values()))
        self.assertAlmostEqual(ledger['known_energy_uj'],sum(r['energy_uj'] or 0 for r in rows.values()))
        self.assertAlmostEqual(ledger['known_average_power_mw'],ledger['known_energy_uj']*500000/b.cycles)
        inventory=inventory_rows(ledger['components'])
        self.assertEqual(len(inventory),len({r['id'] for r in inventory}))
        results=[eight_adc_costs(b,neural_multiplier=n,prepared=prepared)['ledger'] for n in (1.25,1.5,2.)]
        self.assertLess(results[0]['known_energy_uj'],results[1]['known_energy_uj'])
        self.assertLess(results[1]['known_energy_uj'],results[2]['known_energy_uj'])
        self.assertEqual(len({r['sha256'] for r in results}),3)
        self.assertEqual(prepared,before)
        bad=deepcopy(prepared); bad['configuration']=None
        with self.assertRaises(ValueError): eight_adc_costs(b,prepared=bad)

    def test_unreviewed_size_does_not_claim_neural_cost(self):
        for size in (2,9):
            model=EightADCSimulation(size,1); list(model.steps())
            ledger=eight_adc_costs(model)['ledger']
            row=next(r for r in ledger['components'] if r['id']=='u_nn')
            self.assertIsNone(row['area_um2']); self.assertIsNone(row['energy_uj'])
            self.assertIn(row['component'],ledger['missing_area'])
            self.assertIn(row['component'],ledger['missing_energy'])


if __name__=='__main__': unittest.main()
