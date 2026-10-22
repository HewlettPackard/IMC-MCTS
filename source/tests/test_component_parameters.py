# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import unittest
from core.architecture.component_parameters import validate_parameters,parameter_sources
from core.architecture import studio_current as c
from core.architecture.parallel_datapath import SizedParallelDatapathGoSimulation


class ComponentParameterTests(unittest.TestCase):
    def test_reject_unknown_invalid_and_noninteger_timings(self):
        cases=[{'unknown':{}},{'adc_lanes':{'unknown':1}},{'adc_lanes':{'energy_pj':True}},
            {'adc_lanes':{'energy_pj':-1}},{'adc_lanes':{'energy_pj':float('nan')}},
            {'adc_lanes':{'energy_pj':float('inf')}},{'adc_lanes':{'service_cycles':13.5}},
            {'physical_overhead':{'area_fraction':2}}]
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):validate_parameters(value)

    def test_defaults_sources_are_immutable(self):
        m=SizedParallelDatapathGoSimulation(9,3);p=c.prepare(m)
        original=p['sources']['power']['cases']['imc_ucb_score']['powers_mw'].copy()
        changed=parameter_sources(p['sources'],{'u_ucb':{'active_dynamic_mw':100}})
        self.assertEqual(p['sources']['power']['cases']['imc_ucb_score']['powers_mw'],original)
        self.assertEqual(changed['power']['cases']['imc_ucb_score']['powers_mw'],original)
        self.assertEqual(changed['connected_parameter_overrides']['u_ucb']['active_dynamic_mw'],100)

    def test_adc_event_energy_area_and_overhead(self):
        m=SizedParallelDatapathGoSimulation(9,3,component_parameters={'adc_lanes':{'energy_pj':100,'area_um2':3200000}})
        p=c.prepare(m)
        for _ in m.steps():pass
        report=c.price(m.memory.operations,m.cycles,m.block_active_cycles,c.capture(m),p)
        rows={r['id']:r for r in report['components']}
        self.assertEqual(rows['adc_lanes']['area_um2'],3200000)
        self.assertAlmostEqual(rows['adc_lanes']['dynamic_energy_uj'],m.memory.operations['neural_adc_conversions']*100/1e6)
        self.assertAlmostEqual(rows['physical_overhead']['area_um2'],.15*sum(r['area_um2'] for key,r in rows.items() if key!='physical_overhead'))
        self.assertAlmostEqual(report['core_energy_uj'],report['core_average_power_mw']*report['latency_ms'])

    def test_timing_changes_schedule_but_preserves_search(self):
        a=SizedParallelDatapathGoSimulation(9,20,seed=7)
        b=SizedParallelDatapathGoSimulation(9,20,seed=7,component_parameters={'adc_lanes':{'service_cycles':26},'cam_macro':{'service_cycles':6}})
        for _ in a.steps():pass
        for _ in b.steps():pass
        self.assertGreater(b.cycles,a.cycles)
        self.assertEqual(a.neural.last_state,b.neural.last_state)
        self.assertEqual(a.memory.node_sram,b.memory.node_sram)
        self.assertEqual(a.memory.child_sram,b.memory.child_sram)

    def test_all_catalog_defaults_reproduce_costs(self):
        a=SizedParallelDatapathGoSimulation(9,20,seed=7);p=c.prepare(a)
        for _ in a.steps():pass
        base=c.price(a.memory.operations,a.cycles,a.block_active_cycles,c.capture(a),p)
        params={g['id']:{f['key']:f['default'] for f in g['fields']} for g in c.parameter_catalog(p,base)['groups']}
        b=SizedParallelDatapathGoSimulation(9,20,seed=7,component_parameters=params);q=c.prepare(b)
        for _ in b.steps():pass
        custom=c.price(b.memory.operations,b.cycles,b.block_active_cycles,c.capture(b),q)
        self.assertEqual(a.cycles,b.cycles)
        for old,new in zip(base['components'],custom['components']):
            for metric in ('area_um2','energy_uj','dynamic_energy_uj','standby_energy_uj'):
                self.assertAlmostEqual(old[metric],new[metric],places=8)

    def test_ucb_service_and_individual_memory_units(self):
        params={'u_ucb':{'service_cycles':300},'node_sram':{'read_energy_pj':100,'write_energy_pj':200,'standby_mw':4},
            'cam_macro':{'search_energy_pj':300,'read_energy_pj':400,'write_energy_pj':500}}
        a=SizedParallelDatapathGoSimulation(9,110,seed=4)
        b=SizedParallelDatapathGoSimulation(9,110,seed=4,component_parameters=params)
        for _ in a.steps():pass
        for _ in b.steps():pass
        self.assertGreater(b.cycles,a.cycles);self.assertEqual(a.memory.node_sram,b.memory.node_sram)
        result=c.costs(b.memory.operations,b.cycles,b.block_active_cycles,c.capture(b),c.prepare(b))
        rows={r['id']:r for r in result['estimate']['components']};ops=b.memory.operations
        self.assertAlmostEqual(rows['node_sram']['dynamic_energy_uj'],(100*ops['node_sram_read_words']+200*ops['node_sram_write_words'])/1e6)
        self.assertAlmostEqual(rows['node_sram']['standby_energy_uj'],4*b.cycles/500000)
        self.assertAlmostEqual(rows['cam_macro']['dynamic_energy_uj'],(300*ops['cam_searches']+400*ops['cam_output_ids']+500*(ops['cam_filled_rows']+ops['cam_evicted_rows']))/1e6)
        self.assertAlmostEqual(result['sram']['pools']['node_sram']['dynamic_energy_nj'],rows['node_sram']['dynamic_energy_uj']*1000)
        self.assertEqual(sum(r['details']['scores'] for r in result['estimate']['components'] if r['id'].startswith('u_ucb_')),ops['ucb_operations'])

    def test_saved_parameters_identity_and_historical_rejection(self):
        from core.architecture.result_registry import ROOT,configuration,run_case,verify_run
        from pathlib import Path
        import tempfile
        parameters={'adc_lanes':{'energy_pj':100,'service_cycles':26}}
        with self.assertRaises(ValueError):configuration({'board_size':2,'component_parameters':parameters})
        with tempfile.TemporaryDirectory(dir=ROOT/'p03_experiments/p104_simulator_campaign') as folder:
            out,result=run_case(custom=c.current_architecture()['default_configuration'] | {'iterations':3,'component_parameters':parameters},runs=Path(folder))
            saved=verify_run(out)
            self.assertEqual(saved['identity']['configuration']['requested']['component_parameters'],parameters)
            self.assertEqual(saved['costs']['ledger']['component_parameters'],parameters)
            self.assertEqual(saved['architecture']['adc_service_cycles'],26)
            self.assertEqual(saved['publication_status'],'custom_parameter_scenario_not_physically_validated')

if __name__=='__main__':unittest.main()
