# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Explicit archived evaluator selection for the mapped architecture.
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
CATALOG=ROOT/'p04_results/p03_models/catalog.json'
PAPER_CATALOG=CATALOG.with_name('paper_catalog.json')


def model_catalog():
    return json.loads(CATALOG.read_text())['models']+json.loads(PAPER_CATALOG.read_text())['models']


def model_record(identifier, board_size):
    if identifier=='random_diagnostic': return None
    records={row['id']:row for row in model_catalog()}
    if identifier not in records: raise ValueError('Unknown evaluator model')
    record=records[identifier]
    if not record['available']: raise ValueError(record['reason'])
    if record['board_size']!=board_size: raise ValueError('Evaluator board size does not match this case')
    return record


def load_model(identifier, board_size, perspective=1):
    record=model_record(identifier,board_size)
    if record is None: return None,None
    if perspective not in (-1,1): raise ValueError('Evaluator perspective must be black or white')
    turn=record.get('turn_indicator',False)
    if turn and perspective!=1: raise ValueError('Turn-aware Go models require absolute black/white encoding')
    path=ROOT/record['file']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
        raise ValueError('Evaluator checkpoint hash mismatch')
    hidden=32 if board_size in (2,3) else 96
    with np.load(path,allow_pickle=False) as archive:
        weights=[np.asarray(archive[key],dtype=np.float64) for key in ('weights1','weights2')]
    if weights[0].shape!=(2*board_size**2+int(turn),hidden) or weights[1].shape!=(hidden,3):
        raise ValueError('Evaluator dimensions do not fit this mapped core')
    if not all(np.isfinite(w).all() for w in weights): raise ValueError('Evaluator contains nonfinite weights')
    if perspective==-1:
        weights=[weights[0].reshape(-1,2,hidden)[:,::-1,:].reshape(-1,hidden).copy(),weights[1][:,::-1].copy()]
    info=dict(record,perspective_transform='absolute_black' if perspective==1 else 'swap_input_colors_and_reverse_output_classes',
        mapping='symmetric_signed_8bit_weights_differential_4bit_cells')
    return weights,info


def model_sources(identifier, board_size):
    record=model_record(identifier,board_size)
    paths=[CATALOG,PAPER_CATALOG]
    if record is not None: paths.extend([ROOT/record['file'],ROOT/record['original_snapshot']])
    if record is not None and record.get('binary_snapshot'): paths.append(ROOT/record['binary_snapshot'])
    return paths
