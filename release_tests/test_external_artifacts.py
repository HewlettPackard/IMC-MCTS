# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from imc_mcts_release.artifacts import install_archive, overlay_artifacts, verify_store


class ArtifactTests(unittest.TestCase):
    def fixture(self, root, members=None):
        raw = b"external numerical input"
        manifest = {"files": [{"path": "data/value.bin", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}]}
        archive = root / "inputs.tar.gz"
        members = [("data/value.bin", raw, "file")] if members is None else members
        with tarfile.open(archive, "w:gz") as stream:
            for name, blob, kind in members:
                member = tarfile.TarInfo(name)
                if kind == "link":
                    member.type = tarfile.SYMTYPE
                    member.linkname = "../../outside"
                    stream.addfile(member)
                else:
                    member.size = len(blob)
                    stream.addfile(member, io.BytesIO(blob))
        return archive, manifest, raw

    def test_valid_packet_and_overlay_copy_only_declared_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive, manifest, raw = self.fixture(root)
            store = install_archive(archive, root / "store", manifest)
            (store / "unlisted.txt").write_text("not an input")
            runtime = root / "runtime"
            runtime.mkdir()
            self.assertEqual(overlay_artifacts(store, runtime, manifest), 1)
            self.assertEqual((runtime / "data/value.bin").read_bytes(), raw)
            self.assertFalse((runtime / "unlisted.txt").exists())

    def test_corrupt_packet_rejected_before_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive, manifest, raw = self.fixture(root)
            manifest["files"][0]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "integrity"):
                install_archive(archive, root / "new", manifest)
            self.assertFalse((root / "new").exists())

    def test_traversal_links_extra_and_duplicate_members_rejected(self):
        for name, kind in [("../outside", "file"), ("/absolute", "file"), ("data/value.bin", "link"), ("unexpected", "file")]:
            with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                archive, manifest, raw = self.fixture(root, [(name, b"", kind)])
                with self.assertRaises(ValueError):
                    install_archive(archive, root / "new", manifest)
                self.assertFalse((root / "new").exists())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive, manifest, raw = self.fixture(root)
            archive, manifest, raw = self.fixture(root, [("data/value.bin", raw, "file")] * 2)
            with self.assertRaisesRegex(ValueError, "Unexpected"):
                install_archive(archive, root / "new", manifest)

    def test_incomplete_packet_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive, manifest, raw = self.fixture(root, [])
            with self.assertRaisesRegex(ValueError, "incomplete"):
                install_archive(archive, root / "new", manifest)

    def test_existing_store_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive, manifest, raw = self.fixture(root)
            output = root / "existing"
            output.mkdir()
            (output / "keep").write_text("keep")
            with self.assertRaises(FileExistsError):
                install_archive(archive, output, manifest)
            self.assertEqual((output / "keep").read_text(), "keep")

    def test_changed_store_and_outside_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive, manifest, raw = self.fixture(root)
            store = install_archive(archive, root / "store", manifest)
            target = store / "data/value.bin"
            target.write_text("changed")
            with self.assertRaisesRegex(ValueError, "integrity"):
                verify_store(store, manifest)
            target.unlink()
            target.symlink_to(archive)
            with self.assertRaisesRegex(ValueError, "escapes"):
                verify_store(store, manifest)

    def test_overlay_refuses_changed_existing_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive, manifest, raw = self.fixture(root)
            store = install_archive(archive, root / "store", manifest)
            runtime = root / "runtime"
            (runtime / "data").mkdir(parents=True)
            (runtime / "data/value.bin").write_text("keep existing")
            with self.assertRaisesRegex(ValueError, "overwrite"):
                overlay_artifacts(store, runtime, manifest)
            self.assertEqual((runtime / "data/value.bin").read_text(), "keep existing")


if __name__ == "__main__":
    unittest.main()
