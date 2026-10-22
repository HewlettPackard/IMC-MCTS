# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from core.architecture import connected_costs as connected


class ConnectedCharacterizationTests(unittest.TestCase):
    def test_native_report_values_and_disjoint_selection(self):
        data = connected.load_characterization()
        parts = connected.native_parts()
        self.assertEqual(set(parts), {'u_sel', 'u_nn', *connected.LANES})
        self.assertEqual(data['native_tops']['imc_selection_path']['area_um2'], 1538770.569904)
        self.assertEqual(parts['u_nn']['area_um2'], 104753.280035)
        self.assertEqual(parts['u_ucb_00']['area_um2'], 91260.4805)
        self.assertEqual(parts['u_ucb_15']['area_um2'], 90827.5205)
        self.assertAlmostEqual(parts['u_ucb_00']['dynamic_mw'], 3.498)
        self.assertAlmostEqual(parts['u_ucb_15']['dynamic_mw'], 3.371)
        for key in ('area_um2', 'dynamic_mw', 'leakage_mw'):
            actual = math.fsum(parts[name][key] for name in ('u_sel', *connected.LANES))
            self.assertAlmostEqual(actual, data['native_tops']['imc_selection_path'][key], places=8)
        self.assertEqual(parts['u_nn']['dynamic_mw'], 15.263)
        self.assertEqual(parts['u_nn']['leakage_mw'], .246301)
        for part in parts.values():
            self.assertEqual(part['active_dynamic_mw'], part['idle_dynamic_mw'])
            self.assertEqual(part['dynamic_mw'], part['active_dynamic_mw'])

    def test_raw_acceptance_is_preserved(self):
        metadata = connected.metadata()
        self.assertEqual(metadata['source_node_nm'], 65)
        self.assertEqual(metadata['clock_period_ns'], 2)
        self.assertEqual(metadata['current_stage_constraint_closure'], 'PASS')
        self.assertEqual(metadata['original_packet_acceptance'], 'UNVERIFIED')
        self.assertEqual(metadata['equivalence'], 'UNVERIFIED')
        self.assertEqual(metadata['power'], 'VECTORLESS_ONLY')
        self.assertEqual(metadata['missing_native_evidence'], ['imc_selection_path/driver_resize.svf'])

    def _copy_evidence(self, folder):
        for source in connected.SOURCE_FILES:
            destination = folder / source.relative_to(connected.ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        return folder / connected.CHARACTERIZATION.relative_to(connected.ROOT)

    def test_report_digest_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); catalog = self._copy_evidence(folder)
            report = folder / connected.native_parts()['u_nn']['source']
            report.write_text(report.read_text() + '\nchanged\n')
            with patch.object(connected, 'ROOT', folder), patch.object(connected, 'CHARACTERIZATION', catalog):
                with self.assertRaisesRegex(ValueError, 'evidence hash mismatch'):
                    connected.load_characterization()

    def test_catalog_value_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); catalog = self._copy_evidence(folder)
            data = json.loads(catalog.read_text()); data['parts']['u_nn']['area_um2'] += 1
            catalog.write_text(json.dumps(data))
            with patch.object(connected, 'ROOT', folder), patch.object(connected, 'CHARACTERIZATION', catalog):
                with self.assertRaisesRegex(ValueError, 'differs from native reports'):
                    connected.load_characterization()

    def test_rtl_binding_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); catalog = self._copy_evidence(folder)
            rtl = folder / 'rtl_synthesis/p08_connected_paths/p00_rtl/imc_readout_path.sv'
            rtl.write_text(rtl.read_text() + '\n// changed source\n')
            with patch.object(connected, 'ROOT', folder), patch.object(connected, 'CHARACTERIZATION', catalog):
                with self.assertRaisesRegex(ValueError, 'RTL binding hash mismatch'):
                    connected.load_characterization()


if __name__ == '__main__':
    unittest.main()
