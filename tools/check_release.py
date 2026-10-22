#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
"""Offline public-release file, license and credential-signature checks."""
import bz2
import gzip
import io
import json
import lzma
from pathlib import Path, PurePosixPath
import pickletools
import re
import stat
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ['CITATION.cff', 'REPRODUCIBILITY.md', 'pyproject.toml', 'Makefile', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md', 'SECURITY.md', '.gitignore', '.github/workflows/ci.yml', '.github/workflows/secret-scan.yml', 'SBOM.cdx.json', 'SBOM_SCOPE.md']
CODE = {'.py', '.cpp', '.c', '.h', '.tcl', '.sh', '.sv', '.v', '.js', '.css', '.html'}
IGNORE = {'.git', '.venv', 'venv', 'build', 'dist', 'outputs', 'runs', '__pycache__'}
SIGNATURES = [r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', r'gh[pousr]_[A-Za-z0-9]{30,}', r'github_pat_[A-Za-z0-9_]{50,}', r'AKIA[0-9A-Z]{16}', r'sk-(?:proj-)?[A-Za-z0-9_-]{30,}']


# No trained-model payloads are shipped, even when absent from the input manifest.
# Text provenance may name these formats; only actual payload files are rejected.
WEIGHT_SUFFIXES = frozenset({
    '.bin', '.pkl', '.pickle', '.npz', '.npy', '.pt', '.pth', '.ckpt',
    '.checkpoint', '.onnx', '.safetensors', '.h5', '.hdf5', '.hdf', '.keras',
    '.weights', '.weight', '.params', '.caffemodel', '.t7', '.tflite', '.pb',
    '.pbtxt', '.mlmodel', '.mlpackage', '.joblib', '.model', '.msgpack',
    '.ubj', '.bst', '.cbm', '.rds', '.rda', '.rdata', '.paddle', '.pdparams',
    '.pdopt', '.pdmodel', '.tensor', '.tensors', '.index',
})
COMPRESSION_SUFFIXES = {'.gz', '.bz2', '.xz', '.lzma', '.tar'}
ARCHIVE_SUFFIXES = {'.zip', '.whl', '.tar', '.tgz', '.gz', '.tbz', '.tbz2', '.bz2', '.txz', '.xz', '.lzma', '.7z', '.rar'}
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_DEPTH = 6


def weight_filename(name):
    """Recognize common checkpoint formats without depending on a declared list."""
    leaf = PurePosixPath(name.replace('\\', '/')).name.lower()
    while PurePosixPath(leaf).suffix in COMPRESSION_SUFFIXES:
        leaf = leaf.rsplit('.', 1)[0]
    return (PurePosixPath(leaf).suffix in WEIGHT_SUFFIXES
            or leaf == 'checkpoint'
            or re.search(r'\.(?:ckpt|checkpoint)(?:[.-].*)?$', leaf) is not None
            or re.search(r'\.data-\d+-of-\d+$', leaf) is not None)


def _weight_signature(payload):
    if payload.startswith(b'\x93NUMPY'):
        return 'NumPy array'
    if len(payload) > 1 and payload[0] == 0x80 and 2 <= payload[1] <= 6:
        return 'binary pickle'
    if payload.startswith((b'c', b'(', b']', b'}', b'P')) and payload.endswith(b'.'):
        # pickletools reads opcodes only; it does not import globals or execute REDUCE.
        try:
            stream = io.BytesIO(payload)
            for index, (opcode, _, _) in enumerate(pickletools.genops(stream)):
                if index > 10000:
                    return 'text pickle beyond opcode inspection limit'
                if opcode.name == 'STOP' and stream.tell() == len(payload):
                    return 'text pickle'
        except (ValueError, EOFError, UnicodeError):
            pass
    if any(payload[offset:offset + 8] == b'\x89HDF\r\n\x1a\n' for offset in [0, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]):
        return 'HDF5 array'
    if len(payload) >= 10:
        header_bytes = int.from_bytes(payload[:8], 'little')
        if 2 <= header_bytes <= min(len(payload) - 8, 1024 * 1024):
            try:
                header = json.loads(payload[8:8 + header_bytes])
            except (UnicodeError, ValueError):
                header = None
            if isinstance(header, dict) and any(isinstance(v, dict) and {'dtype', 'shape', 'data_offsets'} <= v.keys() for v in header.values()):
                return 'safetensors array'
    return None


def model_payload_findings(name, payload, depth=0, budget=None):
    """Inspect bytes and nested containers in memory; never extract or unpickle."""
    if weight_filename(name):
        return ['Raw model/array format in public tree: ' + name]
    signature = _weight_signature(payload)
    if signature:
        return ['Raw model/array signature (' + signature + ') in public tree: ' + name]
    if depth > MAX_ARCHIVE_DEPTH:
        return ['Archive nesting limit exceeded; cannot establish model absence: ' + name]
    if len(payload) > MAX_MEMBER_BYTES:
        return ['Payload inspection size limit exceeded: ' + name]
    budget = [MAX_ARCHIVE_BYTES] if budget is None else budget
    errors = []

    def inspect(member, data):
        budget[0] -= len(data)
        if budget[0] < 0:
            errors.append('Archive inspection byte budget exceeded: ' + name)
        else:
            errors.extend(model_payload_findings(name + '::' + member, data, depth + 1, budget))

    def safe_member(member):
        p = PurePosixPath(member.replace('\\', '/'))
        return not p.is_absolute() and '..' not in p.parts

    suffix = PurePosixPath(name).suffix.lower()
    try:
        stream = io.BytesIO(payload)
        if zipfile.is_zipfile(stream):
            with zipfile.ZipFile(stream) as archive:
                for row in archive.infolist():
                    if row.is_dir():
                        continue
                    if not safe_member(row.filename) or stat.S_ISLNK(row.external_attr >> 16):
                        errors.append('Unsafe archive member: ' + name + '::' + row.filename)
                    elif row.file_size > MAX_MEMBER_BYTES or row.file_size > budget[0]:
                        errors.append('Archive member exceeds inspection limit: ' + name + '::' + row.filename)
                    else:
                        with archive.open(row) as data:
                            inspect(row.filename, data.read(MAX_MEMBER_BYTES + 1))
            return errors
        # is_zipfile probes the stream tail even for non-ZIP inputs.
        stream.seek(0)
        if suffix == '.tar' or payload[257:262] == b'ustar':
            with tarfile.open(fileobj=stream, mode='r:') as archive:
                for row in archive:
                    if row.isdir():
                        continue
                    if not row.isfile() or not safe_member(row.name):
                        errors.append('Unsafe archive member: ' + name + '::' + row.name)
                    elif row.size > MAX_MEMBER_BYTES or row.size > budget[0]:
                        errors.append('Archive member exceeds inspection limit: ' + name + '::' + row.name)
                    else:
                        with archive.extractfile(row) as data:
                            inspect(row.name, data.read(MAX_MEMBER_BYTES + 1))
            return errors
        compressed = None
        if payload.startswith(b'\x1f\x8b') or suffix in {'.gz', '.tgz'}:
            compressed = gzip.GzipFile(fileobj=stream)
        elif payload.startswith(b'BZh') or suffix in {'.bz2', '.tbz', '.tbz2'}:
            compressed = bz2.BZ2File(stream)
        elif payload.startswith(b'\xfd7zXZ\x00') or suffix in {'.xz', '.txz', '.lzma'}:
            compressed = lzma.LZMAFile(stream)
        if compressed is not None:
            member = PurePosixPath(name).name.rsplit('.', 1)[0]
            if suffix in {'.tgz', '.tbz', '.tbz2', '.txz'}:
                member += '.tar'
            with compressed:
                inspect(member, compressed.read(MAX_MEMBER_BYTES + 1))
            return errors
        if suffix in ARCHIVE_SUFFIXES or payload.startswith((b'7z\xbc\xaf\x27\x1c', b'Rar!')):
            return ['Uninspectable archive; cannot establish model absence: ' + name]
        # Retain ordinary scientific figures while rejecting undeclared opaque blobs.
        if payload.startswith((b'%PDF-', b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a', b'RIFF')):
            return []
        try:
            text = payload.decode('utf-8')
        except UnicodeError:
            return ['Unrecognized binary payload in public tree: ' + name]
        if any(ord(c) < 32 and c not in '\t\r\n\f' for c in text):
            return ['Unrecognized binary/control payload in public tree: ' + name]
        return []
    except (OSError, EOFError, ValueError, RuntimeError, tarfile.TarError, zipfile.BadZipFile, NotImplementedError):
        return ['Unreadable archive; cannot establish model absence: ' + name]


def main():
    errors = []
    notices = []
    for name in REQUIRED:
        if not (ROOT / name).is_file():
            errors.append('Missing required file: ' + name)
    exception_record = json.loads((ROOT / 'LICENSE_EXCEPTIONS.json').read_text())
    exceptions = exception_record['exceptions']
    artifacts = json.loads((ROOT / 'source/imc_mcts_release/external_artifacts.json').read_text())['files']
    for row in artifacts:
        if (ROOT / 'source' / row['path']).exists():
            errors.append('Unapproved artifact present in public tree: ' + row['path'])
    count = 0
    for path in sorted(ROOT.rglob('*')):
        parts = set(path.relative_to(ROOT).parts)
        if parts & {'.git', '.venv', 'venv', '__pycache__'}:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink():
            errors.append('Symlink in release tree: ' + relative)
            continue
        if not path.is_file():
            continue
        errors.extend(model_payload_findings(relative, path.read_bytes()))
        if parts & IGNORE:
            continue
        if path.name in ['AGENTS.md', 'CLAUDE.md'] or set(path.relative_to(ROOT).parts) & {'.claude', '.codex'}:
            errors.append('Assistant-specific file in release tree: ' + relative)
        if path.suffix.lower() == '.xlsx' or path.name == 'historical_test_fixtures.tar.gz':
            errors.append('Supplied input in public tree: ' + relative)
        try:
            text = path.read_text()
        except UnicodeError:
            continue
        count += 1
        if re.search('Reason' + 'Core', text, re.I):
            errors.append('Internal codename in public text: ' + relative)
        for pattern in SIGNATURES:
            if re.search(pattern, text):
                errors.append('Credential signature in ' + relative + ' (value redacted)')
        if path.suffix in CODE:
            sidecar = Path(str(path) + '.license')
            license_text = text + ('\n' + sidecar.read_text() if sidecar.is_file() else '')
            if 'SPDX-License-Identifier:' not in license_text:
                errors.append('Missing SPDX identifier: ' + relative)
            if 'SPDX-FileCopyrightText:' not in license_text:
                if relative in exceptions:
                    notices.append('Existing attribution context: ' + relative)
                else:
                    errors.append('Missing copyright identifier: ' + relative)
    result = {'status': 'PASS' if not errors else 'FAIL', 'public_text_files_checked': count, 'excluded_external_inputs': len(artifacts), 'errors': errors, 'approval_notices': [] if exception_record.get('new_approval_required_by_this_record') is False else notices, 'attribution_notices': notices, 'raw_weight_suffixes_rejected': sorted(WEIGHT_SUFFIXES), 'scope': 'Offline no-model policy inspects common weight formats, raw array signatures, opaque binaries and bounded nested archives without deserializing. Bounded credential signatures and gitleaks are separate checks. Hosted CI and external approvals are not established.'}
    print(json.dumps(result, indent=2))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
