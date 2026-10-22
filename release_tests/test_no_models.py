# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
"""No model checkpoints or array payloads may enter the public release."""
import bz2
import contextlib
import gzip
import importlib.util
import io
import json
import lzma
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_policy', ROOT / 'tools/check_release.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def zip_bytes(name, data):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr(name, data)
    return output.getvalue()


def tar_bytes(name, data):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as archive:
        member = tarfile.TarInfo(name)
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


class NoModelsTests(unittest.TestCase):
    def test_undeclared_common_checkpoint_formats_are_rejected(self):
        # No artifact manifest participates in this check.
        for suffix in ['pkl', 'pickle', 'bin', 'npz', 'npy', 'pt', 'pth', 'ckpt',
                       'onnx', 'safetensors', 'h5', 'hdf5', 'keras', 'weights',
                       'joblib', 'tflite', 'pb', 'caffemodel', 'model', 'msgpack']:
            for name in ['unlisted.' + suffix, 'unlisted.' + suffix.upper()]:
                with self.subTest(name=name):
                    self.assertTrue(policy.model_payload_findings(name, b'not deserialized'))
        for name in ['net.pth.tar', 'net.ckpt-500.index', 'net.data-00000-of-00002', 'checkpoint']:
            with self.subTest(name=name):
                self.assertTrue(policy.model_payload_findings(name, b'not deserialized'))

    def test_renamed_binary_arrays_and_pickles_are_rejected_without_loading(self):
        header = json.dumps({'layer': {'dtype': 'F32', 'shape': [1], 'data_offsets': [0, 4]}}).encode()
        payloads = [b'\x93NUMPY\x01\x00', b'\x80\x05N.', b'(dp0\n.', b'cnumpy\narray\n.', b'\x89HDF\r\n\x1a\n', len(header).to_bytes(8, 'little') + header + b'\x00' * 4, b'\x00\xffopaque']
        for payload in payloads:
            with self.subTest(prefix=repr(payload[:8])):
                self.assertTrue(policy.model_payload_findings('renamed.blob', payload))

    def test_nested_fixture_archives_cannot_hide_weights(self):
        payload = tar_bytes('fixtures/inner.zip', zip_bytes('weights/unlisted.PKL', b'not loaded'))
        for compressed, suffix in [(gzip.compress(payload), 'tar.gz'), (bz2.compress(payload), 'tar.bz2'), (lzma.compress(payload), 'tar.xz')]:
            with self.subTest(suffix=suffix):
                findings = policy.model_payload_findings('renamed-fixtures.' + suffix, compressed)
                self.assertTrue(findings)
                self.assertTrue(any('unlisted.PKL' in row for row in findings), findings)
        self.assertTrue(policy.model_payload_findings('arbitrary.data', zip_bytes('arrays/disguised', b'\x93NUMPY\x01\x00')))

    def test_corrupt_unsupported_or_over_limit_archives_fail_closed(self):
        for name, data in [('fixtures.tar.gz', b'broken'), ('fixtures.zip', b'broken'), ('fixtures.7z', b'7z\xbc\xaf\x27\x1c')]:
            with self.subTest(name=name):
                self.assertTrue(policy.model_payload_findings(name, data))
        nested = b'plain text'
        for _ in range(policy.MAX_ARCHIVE_DEPTH + 2):
            nested = zip_bytes('next.zip', nested)
        self.assertTrue(policy.model_payload_findings('outer.zip', nested))
        with patch.object(policy, 'MAX_MEMBER_BYTES', 4):
            self.assertTrue(policy.model_payload_findings('large.data', b'more than four'))
        self.assertTrue(policy.model_payload_findings('limited.zip', zip_bytes('text.txt', b'long text'), budget=[2]))

    def test_archive_paths_and_links_cannot_bypass_inspection(self):
        self.assertTrue(policy.model_payload_findings('fixture.zip', zip_bytes('../outside.txt', b'plain')))
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode='w') as archive:
            member = tarfile.TarInfo('alias')
            member.type = tarfile.SYMTYPE
            member.linkname = 'outside.pkl'
            archive.addfile(member)
        self.assertTrue(policy.model_payload_findings('fixture.tar', output.getvalue()))

    def test_text_metadata_and_compressed_cacti_logs_remain_public(self):
        text = b'CACTI report\nArea (mm^2): 0.123\n'
        for name, data in [('report.txt', text), ('report.txt.gz', gzip.compress(text)), ('metadata.json', b'{"checkpoint_path":"not-shipped.pkl","energy_mJ":3.7}'), ('values.csv', b'iterations,energy_mJ\n5000,3.7\n'), ('figure.pdf', b'%PDF-1.4\npublic scientific figure')]:
            with self.subTest(name=name):
                self.assertEqual(policy.model_payload_findings(name, data), [])

    def test_packaging_excludes_weight_formats_independently_of_manifest(self):
        import tomllib
        project = tomllib.loads((ROOT / 'pyproject.toml').read_text())
        excluded = project['tool']['setuptools']['exclude-package-data']['*']
        manifest = (ROOT / 'MANIFEST.in').read_text()
        ignored = (ROOT / '.gitignore').read_text().splitlines()
        for suffix in policy.WEIGHT_SUFFIXES:
            with self.subTest(suffix=suffix):
                self.assertIn('*' + suffix, excluded)
                self.assertIn('global-exclude *' + suffix, manifest)
                self.assertIn('*' + suffix, ignored)

    def test_policy_main_rejects_undeclared_models_in_generated_output_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in policy.REQUIRED:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('public metadata\n')
            (root / 'LICENSE_EXCEPTIONS.json').write_text('{"exceptions":{},"new_approval_required_by_this_record":false}')
            manifest = root / 'source/imc_mcts_release/external_artifacts.json'
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{"files":[]}')
            hidden = root / 'outputs/undeclared.bin'
            hidden.parent.mkdir()
            hidden.write_bytes(b'not deserialized')
            output = io.StringIO()
            with patch.object(policy, 'ROOT', root), contextlib.redirect_stdout(output):
                self.assertEqual(policy.main(), 1)
            report = json.loads(output.getvalue())
            self.assertTrue(any('outputs/undeclared.bin' in row for row in report['errors']))

    def test_complete_public_tree_contains_no_model_payloads(self):
        # Includes unlisted/ignored output paths, rather than only the 34 inputs.
        for path in ROOT.rglob('*'):
            parts = set(path.relative_to(ROOT).parts)
            if path.is_file() and not parts & {'.git', '.venv', 'venv', '__pycache__', '*.egg-info'}:
                findings = policy.model_payload_findings(path.relative_to(ROOT).as_posix(), path.read_bytes())
                self.assertEqual(findings, [], findings)


if __name__ == '__main__':
    unittest.main()
