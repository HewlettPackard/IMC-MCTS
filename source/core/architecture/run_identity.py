# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

import contextlib
import hashlib
import io
import json
import os
import platform
import struct
from pathlib import Path

import numpy as np


def json_sha256(value):
    data = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def build_run_identity(configuration):
    root = Path(__file__).resolve().parents[2]
    sources = {}
    for package in ('core', 'py_sst_cpp'):
        for path in sorted((root / package).rglob('*.py')):
            sources[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('sram_characterization.json', 'neural_controller_timing.json'):
        data = root / 'core/architecture' / name
        sources[data.relative_to(root).as_posix()] = hashlib.sha256(data.read_bytes()).hexdigest()
    numpy_build = io.StringIO()
    with contextlib.redirect_stdout(numpy_build):
        np.show_config()
    runtime = {
        'python': platform.python_version(),
        'python_implementation': platform.python_implementation(),
        'numpy': np.__version__,
        'system': platform.system(),
        'machine': platform.machine(),
        'numpy_build': numpy_build.getvalue(),
        'thread_environment': {name: os.environ.get(name) for name in (
            'OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
            'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS')},
    }
    config_hash = json_sha256(configuration)
    source_hash = json_sha256(sources)
    execution_hash = json_sha256({
        'configuration_sha256': config_hash,
        'simulator_sha256': source_hash,
        'runtime': runtime,
    })
    return {
        'schema_version': 1,
        'configuration': configuration,
        'configuration_sha256': config_hash,
        'source_sha256': sources,
        'simulator_sha256': source_hash,
        'runtime': runtime,
        'execution_sha256': execution_hash,
    }


def tree_sha256(tree):
    # Preserve the Round 4 evidence encoding for independent before/after checks.
    digest = hashlib.sha256()
    for node_id, node in sorted(tree.items()):
        digest.update(struct.pack('!QqQd', node_id, node['parent'], node['visits'], node['value']))
        digest.update(node['board'].astype('int8').tobytes())
        digest.update(json.dumps([node['player'], node['children']]).encode())
    return digest.hexdigest()
