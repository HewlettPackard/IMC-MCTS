# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Four-lane selection preserves search semantics and prices every physical lane.
# SPDX-License-Identifier: MIT
from copy import deepcopy
import unittest

import numpy as np

from core.algorithm.model_catalog import load_model
from core.architecture.analog_readout import configure_readout
from core.architecture.complete_costs import complete_costs, prepare_costs
from core.architecture.component_inventory import inventory_rows
from core.architecture.parallel_selection import FourLaneSimulation, FourLaneGoSimulation, LANES
from core.architecture.parallel_selection_costs import parallel_costs
from core.architecture.single_child import SingleChildSimulation, SingleChildGoSimulation


def pair(test, serial_class=SingleChildSimulation, parallel_class=FourLaneSimulation, **kwargs):
    serial=serial_class(**kwargs); parallel=parallel_class(**kwargs)
    for model in (serial,parallel): list(model.steps())
    test.assertEqual(serial.completed,parallel.completed)
    test.assertEqual(serial.status,parallel.status)
    test.assertEqual(serial.termination,parallel.termination)
    for a,b in zip(serial.history,parallel.history):
        for key in ('iteration','selected_node','value_q17','nodes','edges','random_state'):
            test.assertEqual(a[key],b[key],(a['iteration'],key))
    test.assertEqual(serial.memory.nodes_used,parallel.memory.nodes_used)
    for n in range(serial.memory.nodes_used):
        for key in ('visits','value','parent','children','player'):
            test.assertEqual(serial.memory.nodes[n][key],parallel.memory.nodes[n][key],(n,key))
        np.testing.assert_array_equal(serial.board(n),parallel.board(n))
    offset=serial.memory.config['stats_offset']
    test.assertEqual(serial.memory.node_sram[:offset],parallel.memory.node_sram[:offset])
    test.assertEqual(serial.memory.node_sram[offset+16:],parallel.memory.node_sram[offset+16:])
    test.assertEqual(serial.memory.child_sram,parallel.memory.child_sram)
    test.assertEqual(len(parallel.memory.node_sram)+len(parallel.memory.child_sram),2*1024*1024)
    old=serial.memory.operations; new=parallel.memory.operations
    for op in set(old)|set(new):
        if op in ('node_sram_read_words','node_sram_write_words'):
            test.assertEqual(old[op]-new[op],4*old['candidate_checks'])
        elif op!='ucb_batches': test.assertEqual(old[op],new[op],op)
    test.assertEqual(sum(n*count for n,count in parallel.batch_counts.items()),new['ucb_operations'])
    test.assertEqual(sum(parallel.block_active_cycles[lane] for lane in LANES),223*old['ucb_operations'])
    saved=24*old['candidate_checks']+225*old['ucb_operations']-sum((225+n)*count for n,count in parallel.batch_counts.items())
    test.assertEqual(serial.cycles-parallel.cycles,saved)
    for phase in serial.phase_cycles:
        test.assertEqual(serial.phase_cycles[phase]-parallel.phase_cycles[phase],saved if phase=='selection' else 0)
    test.assertEqual(parallel.memory.cursor,parallel.cycles)
    parallel.activity_record()
    return serial,parallel


def go_model(cls, iterations=100):
    weights,entry=load_model('go_strong_v1',9)
    model=cls(9,iterations,seed=0,exploration=1.414,weights=weights,turn_indicator=entry['turn_indicator'])
    configure_readout(model,'sustained_drive_v1')
    list(model.steps())
    return model


class ParallelSelectionTests(unittest.TestCase):
    def test_search_equivalence_and_exact_cycle_and_traffic_savings(self):
        for seed in (0,1,17):
            with self.subTest(seed=seed):
                _,parallel=pair(self,board_size=2,iterations=100,seed=seed)
                self.assertEqual(set(parallel.batch_counts),{1,2,3,4})

    def test_go_search_equivalence(self):
        for seed in (0,3):
            with self.subTest(seed=seed):
                pair(self,SingleChildGoSimulation,FourLaneGoSimulation,board_size=3,iterations=75,seed=seed)

    def test_capacity_boundaries_do_not_change(self):
        for limits in ({'nodes':3},{'edges':2},{'path_entries':1}):
            with self.subTest(limits=limits):
                pair(self,board_size=2,iterations=50,memory_limits=limits)

    def test_tie_order_and_first_unvisited_keep_reference_scoring_work(self):
        models=[cls(2,5) for cls in (SingleChildSimulation,FourLaneSimulation)]
        for model in models:
            list(model.steps())
            # Root has four children. With equal visits/value, child zero wins a tie.
            for child in range(1,5): model.memory.update_stats(child,1,.5)
            model.exploration=0; model.cycles=model.memory.cursor
            model._phase('selection',model._select)
        self.assertEqual([m.selected for m in models],[1,1])
        for model in models:
            while model.memory.path_depth: model.memory.pop_path()
            model.memory.update_stats(3,0,0)
            model.cycles=model.memory.cursor
            before=model.memory.operations['ucb_operations']
            model._phase('selection',model._select)
            self.assertEqual(model.selected,3)
            self.assertEqual(model.memory.operations['ucb_operations']-before,2)

    def test_three_adc_rollout_and_single_port_are_preserved(self):
        serial,parallel=pair(self,board_size=2,iterations=30)
        self.assertEqual(serial.neural.profile,parallel.neural.profile)
        self.assertEqual(parallel.neural.profile['adc_lanes'],3)
        self.assertEqual(parallel.memory.config['node_ports'],1)
        self.assertEqual(parallel.memory.config['child_ports'],1)
        self.assertEqual(serial.memory.config['ucb_lanes'],1)
        self.assertEqual(parallel.memory.config['ucb_lanes'],4)

    def test_costs_count_four_units_and_do_not_mutate_source_cache(self):
        serial=go_model(SingleChildGoSimulation); parallel=go_model(FourLaneGoSimulation)
        prepared=prepare_costs('cacti_22nm_lstp',parallel.neural.profile,parallel.serial_memory_config)
        before=deepcopy(prepared)
        base=complete_costs('cacti_22nm_lstp',serial.memory.operations,serial.cycles,serial.neural.profile,
            serial.memory.config,serial.phase_cycles,serial.block_active_cycles)
        costs=parallel_costs(parallel,prepared=prepared); ledger=costs['ledger']
        self.assertEqual(prepared,before)
        self.assertEqual(costs,parallel_costs(parallel,prepared=prepared))
        unit=next(row for row in base['ledger']['components'] if row['id']=='u_ucb')
        rows={row['id']:row for row in ledger['components']}
        self.assertNotIn('u_ucb',rows)
        self.assertEqual(ledger['missing_area'],[]); self.assertEqual(ledger['missing_energy'],[])
        self.assertIsNone(ledger['whole_chip_area_mm2'])
        self.assertAlmostEqual(ledger['known_area_mm2']-base['ledger']['known_area_mm2'],3*unit['area_um2']*1.15/1e6)
        self.assertAlmostEqual(ledger['known_area_mm2']*1e6,sum(row['area_um2'] or 0 for row in rows.values()))
        self.assertAlmostEqual(ledger['known_energy_uj'],sum(row['energy_uj'] or 0 for row in rows.values()))
        for lane in LANES:
            row=rows[lane]; power=row['block_power']; coefficients=power['powers_mw']
            self.assertAlmostEqual(row['area_um2'],unit['area_um2'])
            self.assertEqual(power['active_cycles'],parallel.block_active_cycles[lane])
            self.assertEqual(power['active_cycles']+power['idle_cycles'],parallel.cycles)
            dynamic=(power['active_us']*coefficients['active_dynamic_mw']+power['idle_us']*coefficients['idle_dynamic_mw'])*(22/65)*.8**2
            leakage=parallel.cycles/500*coefficients['leakage_mw']
            self.assertAlmostEqual(row['energy_uj']*1000,dynamic+leakage)
            self.assertTrue(all(child['included_in'].startswith(lane) for child in inventory_rows(row['children'])))
        all_rows=inventory_rows(ledger['components'])
        self.assertEqual(len(all_rows),len({row['id'] for row in all_rows}))
        self.assertTrue(any(row['component']=='Four-candidate register buffer' for row in all_rows))
        self.assertNotEqual(ledger['sha256'],base['ledger']['sha256'])

    def test_controller_allowance_sensitivity_is_explicit(self):
        model=go_model(FourLaneGoSimulation,3)
        prepared=prepare_costs('cacti_22nm_lstp',model.neural.profile,model.serial_memory_config)
        before=deepcopy(prepared)
        results=[parallel_costs(model,selector_multiplier=n,prepared=prepared)['ledger'] for n in (1.,1.25,2.)]
        for key in ('known_area_mm2','known_energy_uj'):
            self.assertLess(results[0][key],results[1][key]); self.assertLess(results[1][key],results[2][key])
        self.assertEqual(len({r['sha256'] for r in results}),3)
        self.assertEqual(prepared,before)
        with self.assertRaises(ValueError): parallel_costs(model,selector_multiplier=0,prepared=prepared)
        bad=deepcopy(prepared); bad['configuration']=None
        with self.assertRaises(ValueError): parallel_costs(model,prepared=bad)
        with self.assertRaises(ValueError):
            complete_costs('cacti_22nm_lstp',model.memory.operations,model.cycles,model.neural.profile,
                model.memory.config,model.phase_cycles,model.block_active_cycles)

    def test_small_geometry_keeps_unestimated_controllers_missing(self):
        model=FourLaneSimulation(2,8); list(model.steps())
        ledger=parallel_costs(model)['ledger']
        selector=next(row for row in ledger['components'] if row['id']=='u_sel')
        self.assertIn(selector['component'],ledger['missing_area'])
        self.assertIn(selector['component'],ledger['missing_energy'])


if __name__=='__main__': unittest.main()
