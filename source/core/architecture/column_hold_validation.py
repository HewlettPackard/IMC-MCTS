# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Bind the optional buffered controller to its retained digital evidence.
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
VALIDATION=Path(__file__).with_name('column_hold_controller_validation.json')
TIMING_STATUS='column_hold_digital_RTL_verified_ideal_interfaces'


def validate_source_extension(proof):
    extension=proof.get('software_extension')
    if extension is None: return
    path=(ROOT/extension['path']).resolve()
    if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest()!=extension['sha256']:
        raise ValueError('Software reconciliation evidence identity changed')
    record=json.loads(path.read_text())
    if record['status']!='passed' or not all(record['checks'].values()):
        raise ValueError('Software reconciliation did not pass')
    for name,digest in record['validated_sources'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Software changed since reconciliation: '+name)


def validate_buffered_sources(validation=VALIDATION):
    proof=json.loads(Path(validation).read_text())
    validate_source_extension(proof)
    if proof['status']!='digital_RTL_and_generic_gates_verified_ideal_interfaces' or proof['profile']!='column_hold_v1':
        raise ValueError('Buffered controller evidence is not accepted')
    for name,digest in proof['validated_sources'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Buffered source changed since validation: '+name)
    evidence=ROOT/proof['evidence']['path']
    if hashlib.sha256((evidence/'metadata.json').read_bytes()).hexdigest()!=proof['evidence']['metadata_sha256']:
        raise ValueError('Buffered evidence identity changed')
    return proof
