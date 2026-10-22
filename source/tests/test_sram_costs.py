# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import contextlib
import gzip
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.architecture.accelerator_api import Accelerator
from core.architecture.sram_costs import load_sram_profile, sram_accounting
from p03_experiments.p08_cost_sources.characterize import check_cache, parse_cacti


ROOT = Path(__file__).resolve().parents[1]
PROBES = ROOT / 'p03_experiments/p08_cost_sources/p00_runs/run_20260909_023818Z/p02_probes'


class SRAMCostsTests(unittest.TestCase):
    def raw(self, name='macro_512k_lstp22'):
        path = PROBES / name
        return gzip.decompress((path/'stdout.txt.gz').read_bytes()).decode(), (path/'memory.cfg.out').read_text()

    def test_parser_matches_independent_dimensions_and_units(self):
        text, csv = self.raw()
        parsed = parse_cacti(text, csv)
        self.assertAlmostEqual(parsed['area_mm2'], 0.83002 * 0.499099, delta=2e-6)
        self.assertEqual(parsed['read_energy_nj'], 0.0111329)
        self.assertEqual(parsed['write_energy_nj'], 0.00775607)
        self.assertAlmostEqual(parsed['leakage_mw'], 0.110278 + 0.0630806)
        self.assertEqual(parsed['capacity_bytes'], 524288)
        self.assertEqual(parsed['word_bytes'], 4)
        self.assertEqual(parsed['technology_nm'], 22)

    def test_missing_nan_and_conflicting_metrics_fail(self):
        text, csv = self.raw()
        for broken in (text.replace('Total dynamic write energy per access (nJ)', 'missing'),
                       text.replace('0.0111329', 'nan'),
                       text.replace('Technology size (nm): 22', 'Technology size (nm): 65')):
            with self.assertRaises(ValueError):
                parse_cacti(broken, csv)
        with self.assertRaises(ValueError):
            parse_cacti(text, csv + csv.splitlines()[1] + '\n')

    def test_nonbinary_decoder_shape_is_rejected(self):
        text, csv = self.raw('requested_1536k_hp22')
        with self.assertRaisesRegex(ValueError, 'power-of-two'):
            parse_cacti(text, csv)

    def test_profile_is_four_macros_without_rescaling(self):
        profile = load_sram_profile('cacti_22nm_lstp')
        self.assertEqual(profile['banks'], {'node_sram': 3, 'child_sram': 1})
        self.assertEqual(profile['macro']['technology_nm'], 22)
        self.assertEqual(profile['sram_word_cycles'], 2)
        self.assertEqual(profile['macro']['read_energy_nj'], 0.0111329)

    def test_packaged_costs_match_raw_accepted_output(self):
        for name in ('cacti_22nm_hp', 'cacti_22nm_lstp'):
            profile = load_sram_profile(name)
            path = ROOT / profile['source']['evidence']
            parsed = parse_cacti(gzip.decompress((path/'stdout.txt.gz').read_bytes()).decode(),
                                 (path/'memory.cfg.out').read_text())
            for key, value in parsed.items():
                self.assertEqual(profile['macro'][key], value)
            check_cache(path, profile['source']['cache_key'])

    def test_cached_output_corruption_or_identity_change_fails(self):
        profile = load_sram_profile('cacti_22nm_lstp')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            evidence = ROOT / profile['source']['evidence']
            for name in ('execution.json', 'memory.cfg', 'memory.cfg.out', 'stdout.txt.gz', 'stderr.txt.gz'):
                shutil.copyfile(evidence/name, path/name)
            with self.assertRaisesRegex(ValueError, 'identity'):
                check_cache(path, 'different tool or config')
            (path/'memory.cfg.out').write_text('corrupted')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                check_cache(path, profile['source']['cache_key'])

    def test_native_costs_reject_a_second_technology_conversion(self):
        path = ROOT / 'core/architecture/sram_characterization.json'
        data = json.loads(path.read_text())
        data['cacti_22nm_lstp']['scaling']['applications'] = 1
        with patch.object(Path, 'read_text', return_value=json.dumps(data)):
            with self.assertRaisesRegex(ValueError, 'scaling'):
                load_sram_profile('cacti_22nm_lstp')

    def test_energy_counts_accesses_and_all_idle_macros_once(self):
        profile = load_sram_profile('cacti_22nm_lstp')
        counts = {'node_sram_read_words': 10, 'node_sram_write_words': 4,
                  'child_sram_read_words': 2, 'child_sram_write_words': 1}
        cost = sram_accounting(profile, counts, 1000)
        self.assertAlmostEqual(cost['dynamic_energy_nj'], 12 * 0.0111329 + 5 * 0.00775607)
        self.assertAlmostEqual(cost['leakage_energy_nj'], 4 * (0.110278 + 0.0630806) * 2)
        self.assertAlmostEqual(cost['area_mm2'], 4 * 0.414262)
        self.assertEqual(cost['status'], 'partial_sram_tool_estimate')

    def test_new_profile_changes_timing_without_changing_computation(self):
        with contextlib.redirect_stdout(io.StringIO()):
            old = Accelerator(board_size=9, iterations=2, neural_mode='mapped').analyze('simulate')
            new = Accelerator(board_size=9, iterations=2, neural_mode='mapped',
                memory_profile='cacti_22nm_lstp', capture_memory_trace=True).analyze('simulate')
        words = sum(count for name, count in old.simulation['memory']['operations'].items()
                    if name.endswith(('_read_words', '_write_words')))
        self.assertEqual(new.simulation['cycles'], old.simulation['cycles'] + words)
        self.assertEqual(old.simulation['tree_sha256'], new.simulation['tree_sha256'])
        self.assertEqual(new.simulation['neural']['cycles'], 24814 + 96)
        self.assertIsNone(new.energy_uj)
        self.assertIsNone(new.area_mm2)
        self.assertGreater(new.accounting['sram']['energy_uj'], 0)
        self.assertNotEqual(old.run_identity['configuration_sha256'], new.run_identity['configuration_sha256'])
        self.assertEqual(new.simulation['memory']['config']['sram_banks'], {'node_sram': 3, 'child_sram': 1})
        self.assertIn('core/architecture/sram_characterization.json', new.run_identity['source_sha256'])

    def test_unsupported_profile_combinations_fail(self):
        for settings in ({'memory_profile': 'unknown'},
                         {'memory_profile': 'cacti_22nm_lstp', 'board_size': 3},
                         {'memory_profile': 'cacti_22nm_lstp'}):
            with self.assertRaises(ValueError):
                Accelerator(**settings).analyze('simulate')


if __name__ == '__main__':
    unittest.main()
