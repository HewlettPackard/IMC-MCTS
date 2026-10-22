# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import hashlib
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from imc_mcts_release import cli


class ReleaseCliTests(unittest.TestCase):
    def fixture(self, root, path="core/value.json"):
        target = root / "core" / "value.json"
        target.parent.mkdir()
        target.write_bytes(b'{"value": 1}\n')
        (root / "not-runtime.txt").write_text("must not be copied")
        raw = target.read_bytes()
        return {"files": [{"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}]}

    def test_run_without_inputs_fails_before_creating_output(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'new'
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                status = cli.main(['run', '--output', str(output)])
            self.assertEqual(status, 2)
            self.assertIn('approved external inputs', errors.getvalue())
            self.assertFalse(output.exists())

    def test_help_restores_argv_after_failure(self):
        old = sys.argv
        def fail():
            raise RuntimeError('help failed')
        with patch.dict(sys.modules, {'reproduce_runtime': SimpleNamespace(main=fail)}):
            with self.assertRaisesRegex(RuntimeError, 'help failed'):
                cli.run_simulator(['--help'])
        self.assertIs(sys.argv, old)

    def test_relative_output_survives_temporary_runtime_cleanup(self):
        import os
        with tempfile.TemporaryDirectory() as folder:
            previous = Path.cwd()
            os.chdir(folder)
            def copy(output):
                runtime = Path(output) / 'runtime'
                runtime.mkdir(parents=True)
                return runtime
            def child(command, **kwargs):
                output = Path(command[command.index('--output') + 1])
                self.assertTrue(output.is_absolute())
                output.mkdir(parents=True)
                (output / 'result.json').write_text('saved')
                return 0
            try:
                with patch.object(cli, 'verify_store'), patch.object(cli, 'copy_runtime', side_effect=copy), patch.object(cli, 'overlay_artifacts'), patch.object(cli.subprocess, 'call', side_effect=child):
                    self.assertEqual(cli.main(['run', '--artifacts', 'store', '--output', 'runs/hero']), 0)
                self.assertEqual(Path('runs/hero/result.json').read_text(), 'saved')
            finally:
                os.chdir(previous)

    def test_existing_workspace_is_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "existing"
            output.mkdir()
            sentinel = output / "keep.txt"
            sentinel.write_text("keep")
            with self.assertRaises(FileExistsError):
                cli.copy_runtime(output, source_root=Path(temp), manifest={"files": []})
            self.assertEqual(sentinel.read_text(), "keep")

    def test_only_listed_runtime_files_are_copied(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "installed"
            source.mkdir()
            manifest = self.fixture(source)
            runtime = cli.copy_runtime(root / "workspace", source_root=source, manifest=manifest)
            self.assertEqual((runtime / "core/value.json").read_bytes(), (source / "core/value.json").read_bytes())
            self.assertFalse((runtime / "not-runtime.txt").exists())
            self.assertEqual(len(list(runtime.rglob("*.*"))), 1)

    def test_unsafe_manifest_path_rejected_before_workspace_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self.fixture(root, path="../escape")
            output = root / "workspace"
            with self.assertRaisesRegex(ValueError, "Unsafe runtime path"):
                cli.copy_runtime(output, source_root=root, manifest=manifest)
            self.assertFalse(output.exists())

    def test_corrupted_runtime_rejected_before_workspace_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self.fixture(root)
            (root / "core/value.json").write_text("changed")
            output = root / "workspace"
            with self.assertRaisesRegex(ValueError, "integrity check failed"):
                cli.copy_runtime(output, source_root=root, manifest=manifest)
            self.assertFalse(output.exists())

    def test_missing_runtime_rejected_before_workspace_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self.fixture(root)
            (root / "core/value.json").unlink()
            output = root / "workspace"
            with self.assertRaises(FileNotFoundError):
                cli.copy_runtime(output, source_root=root, manifest=manifest)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
