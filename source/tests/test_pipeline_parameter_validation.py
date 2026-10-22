# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
# Strict resource parameters before exposing user-editable timings.
import unittest
from core.architecture.parallel_datapath import column_pipeline, candidate_pipeline


class PipelineParameterValidationTests(unittest.TestCase):
    def test_noninteger_or_boolean_resources_are_rejected(self):
        for key in ('outputs','lanes','bus_bits','accumulators','adc_cycles','banks'):
            for value in (True,False,1.5,float('nan'),float('inf')):
                options={'outputs':96,key:value}
                with self.subTest(kernel='column',key=key,value=value):
                    with self.assertRaises(ValueError): column_pipeline(**options)
        for key in ('lanes','banks','busy_cycles','word_cycles'):
            for value in (True,False,1.5,float('nan'),float('inf')):
                with self.subTest(kernel='candidate',key=key,value=value):
                    with self.assertRaises(ValueError): candidate_pipeline([True]*17,**{key:value})

    def test_candidate_flags_are_boolean(self):
        for flags in ([1,1],[2],[None],[True,1]):
            with self.subTest(flags=flags):
                with self.assertRaises(ValueError): candidate_pipeline(flags)

if __name__=='__main__': unittest.main()
