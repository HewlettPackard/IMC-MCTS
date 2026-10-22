# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
"""Explicit offline installation of checksum-bound optional inputs."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile


def artifact_manifest():
    return json.loads(Path(__file__).with_name("external_artifacts.json").read_text())


def relative_path(value):
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts or "\\" in value:
        raise ValueError(f"Unsafe artifact path: {value}")
    return path


def verify_store(root, manifest=None):
    manifest = artifact_manifest() if manifest is None else manifest
    if root is None:
        raise ValueError("Full simulation requires approved external inputs. Install a locally supplied packet with 'imc-mcts artifacts install --archive FILE --output NEW_STORE', then use --artifacts NEW_STORE.")
    root = Path(root).resolve()
    checked = []
    for row in manifest["files"]:
        relative = relative_path(row["path"])
        path = root.joinpath(*relative.parts)
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Artifact escapes its store: {relative}")
        try:
            raw = path.read_bytes()
        except OSError as error:
            raise ValueError(f"Missing external artifact: {relative}") from error
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError(f"External artifact integrity check failed: {relative}")
        checked.append((path, relative))
    return checked


def install_archive(archive, output, manifest=None):
    manifest = artifact_manifest() if manifest is None else manifest
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Artifact store already exists: {output}. Choose a new directory.")
    expected = {str(relative_path(row["path"])): row for row in manifest["files"]}
    if len(expected) != len(manifest["files"]):
        raise ValueError("Duplicate declared artifact path")
    payloads = {}
    # Check every member before creating the output directory. No extraction API is used.
    with tarfile.open(archive, "r:gz") as stream:
        for member in stream:
            name = str(relative_path(member.name))
            if not member.isfile() or name not in expected or name in payloads:
                raise ValueError(f"Unexpected artifact member: {name}")
            row = expected[name]
            if member.size != row["bytes"]:
                raise ValueError(f"Artifact size mismatch: {name}")
            raw = stream.extractfile(member).read(row["bytes"] + 1)
            if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError(f"Artifact integrity check failed: {name}")
            payloads[name] = raw
    if set(payloads) != set(expected):
        raise ValueError("Artifact packet is incomplete")
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads.items():
        path = output.joinpath(*relative_path(name).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (output / "ARTIFACT_RECEIPT.json").write_text(json.dumps({"status": "VERIFIED_LOCAL_INPUTS", "files": len(payloads), "redistribution_cleared": False}, indent=2) + "\n")
    return output


def overlay_artifacts(store, runtime, manifest=None):
    checked = verify_store(store, manifest)
    runtime = Path(runtime).resolve()
    for original, relative in checked:
        target = runtime.joinpath(*relative.parts)
        if target.is_symlink() or not target.resolve().is_relative_to(runtime):
            raise ValueError(f"Artifact target escapes the runtime: {relative}")
        if target.exists() and target.read_bytes() != original.read_bytes():
            raise ValueError(f"Refusing to overwrite changed runtime input: {relative}")
    for original, relative in checked:
        target = runtime.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
    return len(checked)
