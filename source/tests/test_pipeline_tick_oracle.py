# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
# Schedules checked against an independently clock-stepped queue model.
import unittest
from core.architecture.parallel_datapath import column_pipeline,candidate_pipeline
from p03_experiments.p104_simulator_campaign.oracles import pipeline_ticks


class PipelineTickOracleTests(unittest.TestCase):
    def test_readout_timing_action_counts_and_backpressure(self):
        for outputs in (1,3,31,32,33,96,129):
            for adc in (1,13,41):
                for banks in (1,2,3):
                    for bus,accum in ((16,1),(128,8)):
                        counts=[min(32,outputs-i) for i in range(0,outputs,32)]
                        production=[adc+3 for _ in counts]
                        consumption=[(n+bus//16-1)//(bus//16)+(n+accum-1)//accum for n in counts]
                        expected=pipeline_ticks(production,consumption,banks)
                        actual=column_pipeline(outputs,adc_cycles=adc,banks=banks,bus_bits=bus,accumulators=accum)
                        with self.subTest(outputs=outputs,adc=adc,banks=banks,bus=bus):
                            self.assertEqual(actual['cycles'],expected)
                            self.assertEqual(sum(r['conversions'] for r in actual['trace'] if r['resource']=='adc_bank'),outputs)
                            self.assertEqual(sum(g['count'] for g in actual['groups']),outputs)

    def test_candidate_timing_against_clock_steps(self):
        for count in (1,15,16,17,32,33,65):
            for busy in (1,169,500):
                for words in (1,2,5):
                    for banks in (1,2):
                        for unvisited in (False,True):
                            flags=[True]*count
                            if unvisited:flags[-1]=False
                            groups=[flags[i:i+16] for i in range(0,count,16)]
                            production=[len(g)*(6*(1+words)+4) for g in groups]
                            consumption=[busy+2+sum(g) if any(g) else 0 for g in groups]
                            expected=pipeline_ticks(production,consumption,banks)
                            actual=candidate_pipeline(flags,busy_cycles=busy,word_cycles=words,banks=banks)
                            with self.subTest(count=count,busy=busy,words=words,banks=banks,unvisited=unvisited):
                                self.assertEqual(actual['cycles'],expected)
                                self.assertEqual(sum(g['valid_lanes'] for g in actual['groups']),sum(flags))

if __name__=='__main__':unittest.main()
