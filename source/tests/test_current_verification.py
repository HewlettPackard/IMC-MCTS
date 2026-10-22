# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from core.architecture import studio_current as c
from core.architecture.result_registry import ROOT,run_case
from core.architecture.verification import audit_current_result

class CurrentVerificationTests(unittest.TestCase):
    def test_current_contract_and_corruptions(self):
        for parameters in ({},{'adc_lanes':{'energy_pj':90,'service_cycles':26}}):
            with tempfile.TemporaryDirectory(dir=ROOT/'p03_experiments/p104_simulator_campaign') as folder:
                config=c.current_architecture()['default_configuration'] | {'iterations':3}
                if parameters:config['component_parameters']=parameters
                out,result=run_case(custom=config,runs=Path(folder))
                contract={'configuration':result['identity']['configuration']['requested'],'evaluator':result['identity']['configuration']['evaluator'],'cost_sources':result['costs']['ledger']['source_identities']}
                self.assertEqual(audit_current_result(result,contract)['status'],'PASS')
                bad=deepcopy(result);bad['phase_cycles']['iteration_commit']+=1
                with self.assertRaises(ValueError):audit_current_result(bad,contract)
                bad=deepcopy(result);bad['costs']['ledger']['components'].append(bad['costs']['ledger']['components'][0])
                with self.assertRaises(ValueError):audit_current_result(bad,contract)
                bad=deepcopy(result);bad['costs']['ledger']['known_energy_uj']*=1000
                with self.assertRaises(ValueError):audit_current_result(bad,contract)
                bad=deepcopy(result);bad['costs']['ledger']['component_parameters']={'adc_lanes':{'energy_pj':99}}
                with self.assertRaises(ValueError):audit_current_result(bad,contract)

if __name__=='__main__':unittest.main()
