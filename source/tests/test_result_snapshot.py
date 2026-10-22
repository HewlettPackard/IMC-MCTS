# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Guard cost reconciliation and one-row-per-configuration result freezes.
# SPDX-License-Identifier: MIT
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from core.architecture.crossbar_workbook import component_estimates, reference_crossbar, workbook_source
from core.architecture.neural_mapping import neural_profile
from core.architecture.result_registry import ROOT, run_case
from core.architecture.result_snapshot import freeze_repeats, latest_snapshot, verify_snapshot


class CostRecoveryTests(unittest.TestCase):
    def test_recovered_workbook_matches_original_project_member(self):
        source=workbook_source()
        self.assertEqual(source['identity_status'],'recovered_from_legacy_imc_mcts_archive')
        self.assertIn('HPE_Duke/src/synthesis/data/',source['recovery']['archive_member'])
        self.assertEqual(source['source_sha256'],source['recovery']['source_sha256'])

    def test_sequential_energy_uses_the_same_converter_as_area(self):
        cells=workbook_source()['cells']['New_Architecture']; v=lambda key:cells[key]['value']
        ref=reference_crossbar(256)
        expected=2*(v('O22')+v('O30')+v('O46'))+v('P31')+v('O53')
        self.assertAlmostEqual(ref['sequential_reference']['mvm_energy_pj'],expected,places=8)
        self.assertAlmostEqual(expected-v('P67'),v('O53')-v('Q53'),places=8)
        self.assertAlmostEqual(ref['sequential_reference']['average_power_mw']*v('C9'),expected,places=8)
        self.assertNotAlmostEqual(v('O47')+v('O48'),v('O46'))
        self.assertEqual(ref['crossbar_pair_area_um2'],sum(ref['parts_um2'].values()))

    def test_fixed_resources_are_distinct_from_peak_activity(self):
        ledger=component_estimates(neural_profile(9,96),'cacti_22nm_lstp')
        resources=ledger['resource_requirements']
        self.assertEqual(resources['physical_row_terminals'],1024)
        self.assertEqual(resources['physical_column_terminals'],512)
        self.assertEqual(resources['peak_active_rows'],16)
        self.assertEqual(resources['shared_adc_lanes'],3)
        self.assertEqual(resources['maximum_column_groups'],43)
        driver=next(row for row in ledger['components'] if row['component'].startswith('Binary row'))
        self.assertEqual(driver['count'],1024); self.assertGreater(driver['area_um2'],0)
        self.assertIsNone(ledger['whole_chip_area_mm2'])


class ResultSnapshotTests(unittest.TestCase):
    def test_repeat_freeze_rejects_ambiguity_and_detects_drift(self):
        with tempfile.TemporaryDirectory(prefix='snapshot_',dir=ROOT) as directory:
            base=Path(directory); runs=base/'p01_runs'; snapshots=base/'p04_snapshots'
            first,_=run_case(custom={'board_size':2,'iterations':2},runs=runs)
            repeat,_=run_case(custom={'board_size':2,'iterations':2},runs=runs)
            self.assertIsNone(latest_snapshot(snapshots))
            with self.assertRaises(ValueError): freeze_repeats([(first,first)],snapshots)
            with self.assertRaises(ValueError): freeze_repeats([(first,repeat),(first,repeat)],snapshots)
            out=freeze_repeats([(first,repeat)],snapshots)
            manifest=verify_snapshot(out)
            self.assertFalse(manifest['publication_ready'])
            self.assertEqual(latest_snapshot(snapshots),manifest)
            with (out/'summary.csv').open(newline='') as stream: row=list(csv.DictReader(stream))[0]
            self.assertEqual(row['whole_chip_energy_uj'],'')
            self.assertEqual(row['rules'],'placement')
            changed,_=run_case(custom={'board_size':2,'iterations':3},runs=runs)
            with self.assertRaises(ValueError): freeze_repeats([(first,changed)],snapshots)
            self.assertEqual(verify_snapshot(out),manifest)
            data=(out/'summary.csv').read_bytes()
            (out/'summary.csv').write_bytes(data.replace(b',placement,',b',wrong_rules,'))
            with self.assertRaises(ValueError): verify_snapshot(out)
            checks=out/'SHA256SUMS'
            checks.write_text(''.join(hashlib.sha256((out/name).read_bytes()).hexdigest()+'  '+name+'\n'
                for name in ['manifest.json','summary.csv']))
            with self.assertRaisesRegex(ValueError,'CSV'): verify_snapshot(out)


if __name__=='__main__': unittest.main()
