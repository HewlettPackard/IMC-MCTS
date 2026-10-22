# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Check displayed cycles against the model and retain bounded reconnect state.
# SPDX-License-Identifier: MIT
import copy
import unittest

from core.architecture.analog_readout import BUFFERED, DRIVEN, configure_readout
from core.architecture.iteration_model import CompleteSimulation
from p05_studio.p00_app.pipeline import Pipeline, service_intervals
from p05_studio.p00_app.visualization import activity_groups


class StudioPipelineTests(unittest.TestCase):
    def observe(self, model, key='search_one'):
        view=Pipeline(); ready={'run':key,'phase':'ready'}
        view.observe(ready,model);activity_groups(ready,model)
        for event in model.steps():
            event=event | {'run':key}
            transactions=copy.deepcopy(model.memory.transactions)
            view.observe(event,model)
            self.assertEqual(model.memory.transactions,transactions)
            activity_groups(event,model)
        return view

    def test_intervals_cover_phase_cycles_for_both_readouts(self):
        for profile in (DRIVEN,BUFFERED):
            with self.subTest(profile=profile):
                model=CompleteSimulation(3,4,17);configure_readout(model,profile)
                view=self.observe(model)
                previous=0
                for phase in view.payload()['phases']:
                    self.assertEqual(phase['start'],previous)
                    previous=phase['end'];services=phase['services']
                    if phase['phase']=='neural':
                        services=[[r,o,a+phase['start'],b+phase['start'],s]
                            for r,o,a,b,s in service_intervals(model.neural.schedule['trace'])]+services
                    cursor=phase['start']
                    for resource,operation,start,end,stage in services:
                        self.assertEqual(start,cursor);self.assertGreaterEqual(end,start)
                        self.assertLessEqual(end,phase['end']);cursor=end
                    self.assertEqual(cursor,phase['end'])
                self.assertEqual(previous,model.cycles)
                self.assertEqual(sum(p['end']-p['start'] for p in view.phases),model.cycles)
                self.assertEqual(sum(p['end']-p['start'] for p in view.phases if p['phase']=='iteration_commit'),4)
                self.assertEqual(any(r[0]=='column_hold' for r in service_intervals(model.neural.schedule['trace'])),profile==BUFFERED)

    def test_observation_preserves_the_search_and_service_hash(self):
        watched=CompleteSimulation(3,8,19);plain=CompleteSimulation(3,8,19)
        self.observe(watched);list(plain.steps())
        for name in ('cycles','history','value_q17','random_state','phase_cycles','block_active_cycles'):
            self.assertEqual(getattr(watched,name),getattr(plain,name))
        self.assertEqual(watched.memory.schedule_hash.hexdigest(),plain.memory.schedule_hash.hexdigest())
        self.assertEqual(watched.memory.operations,plain.memory.operations)
        self.assertEqual(watched.memory.node_sram,plain.memory.node_sram)
        self.assertEqual(watched.memory.child_sram,plain.memory.child_sram)

    def test_reconnect_restores_latest_window_without_unbounded_trace(self):
        model=CompleteSimulation(3,18,3);view=self.observe(model)
        data=view.payload()
        self.assertEqual(len(data['phases']),12*5)
        self.assertEqual((data['phases'][0]['iteration'],data['phases'][-1]['iteration']),(7,18))
        self.assertIsNone(view.payload(view.revision,view.key)['phases'])
        for revision,key in ((1,view.key),(view.revision+1,view.key),(view.revision,'old_search')):
            self.assertEqual(view.payload(revision,key)['phases'],data['phases'])
        self.assertTrue(all(len(p['services'])==1 for p in data['phases'] if p['phase']=='neural'))
        next_model=CompleteSimulation(2,1)
        view.observe({'run':'search_two','phase':'ready'},next_model)
        reset=view.payload(data['revision'],data['key'])
        self.assertEqual(reset['key'],'search_two');self.assertEqual(reset['phases'],[])

    def test_merging_only_preserves_contiguous_same_resource_work(self):
        raw=[
            {'resource':'adc_bank','operation':'convert','phase':'layer1','start':0,'end':2},
            {'resource':'adc_bank','operation':'convert','phase':'layer1','start':2,'end':4},
            {'resource':'adc_bank','operation':'convert','phase':'layer2','start':4,'end':6},
            {'resource':'readout_bus','operation':'read','phase':'layer2','start':6,'end':8},
            {'resource':'adc_bank','operation':'convert','phase':'layer2','start':8,'end':10},
        ]
        before=copy.deepcopy(raw);rows=service_intervals(raw)
        self.assertEqual(raw,before);self.assertEqual(len(rows),4)
        self.assertEqual(rows[0],['adc_bank','convert',0,4,'layer1'])
        self.assertEqual(sum(r[3]-r[2] for r in rows),10)


if __name__=='__main__': unittest.main()
