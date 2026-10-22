# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Live pricing reuses verified static data, never a previous workload's totals.
# SPDX-License-Identifier: MIT
from copy import deepcopy
import unittest
from unittest.mock import patch

from core.architecture.analog_readout import DRIVEN, BUFFERED, configure_readout
from core.architecture.complete_costs import complete_costs, prepare_costs
from core.architecture.iteration_model import CompleteSimulation
from core.algorithm.model_catalog import load_model


class PreparedCostsTests(unittest.TestCase):
    def test_live_costs_equal_fresh_source_accounting_for_each_phase(self):
        cases = [(2, None, DRIVEN, 'cacti_22nm_hp'), (9, None, DRIVEN, 'cacti_22nm_lstp'),
            (9, 'go_strong_v1', DRIVEN, 'cacti_22nm_lstp'), (9, 'go_weak_v1', BUFFERED, 'cacti_22nm_hp')]
        for size, identifier, mode, sram in cases:
            with self.subTest(size=size, model=identifier, mode=mode, sram=sram):
                weights, _ = load_model(identifier, size) if identifier else (None, None)
                model = CompleteSimulation(size, 2, weights=weights, turn_indicator=bool(identifier))
                configure_readout(model, mode)
                prepared = prepare_costs(sram, model.neural.profile, model.memory.config)
                before = deepcopy(prepared)
                for event in model.steps():
                    args = (sram, model.memory.operations, model.cycles, model.neural.profile,
                        model.memory.config, model.phase_cycles, model.block_active_cycles)
                    expected = complete_costs(*args)
                    with (patch('core.architecture.complete_costs.digital_accounting', side_effect=AssertionError('Reparsed digital reports')),
                         patch('core.architecture.complete_costs.component_estimates', side_effect=AssertionError('Rebuilt fixed inventory')),
                         patch('core.architecture.block_power.load_power_table', side_effect=AssertionError('Reparsed power reports'))):
                        actual = complete_costs(*args, prepared=prepared)
                    self.assertEqual(actual, expected)
                    actual['ledger']['components'][0]['children'].clear()
                    self.assertEqual(prepared, before)
                for neural, memory, flavor in [(model.neural.profile | {'adc_lanes': 1}, model.memory.config, sram),
                        (model.neural.profile, model.memory.config | {'cam_entries': 1}, sram),
                        (model.neural.profile, model.memory.config, 'cacti_22nm_lstp' if sram.endswith('hp') else 'cacti_22nm_hp')]:
                    with self.assertRaisesRegex(ValueError, 'different hardware'):
                        complete_costs(flavor, model.memory.operations, model.cycles, neural, memory,
                            model.phase_cycles, model.block_active_cycles, prepared=prepared)


if __name__ == '__main__':
    unittest.main()
