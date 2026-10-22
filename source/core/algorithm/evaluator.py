import copy
import hashlib
from pathlib import Path
import pickle
import re

import numpy as np


SPEC_FIELDS = {
    'schema_version', 'checkpoint_sha256', 'board_size',
    'input_size', 'hidden_size', 'output_size', 'input_encoding',
    'turn_indicator', 'weight_transform', 'output_order',
    'value_perspective', 'arithmetic_dtype',
}


def load_evaluator_checkpoint(weights_file, evaluator_spec, board_size, hidden_size=None):
    if not isinstance(evaluator_spec, dict):
        raise ValueError('An explicit evaluator_spec dictionary is required to load weights')
    spec = copy.deepcopy(evaluator_spec)
    missing = SPEC_FIELDS - spec.keys()
    extra = spec.keys() - SPEC_FIELDS
    if missing or extra:
        raise ValueError(f'evaluator_spec fields: missing {sorted(missing)}, unknown {sorted(extra)}')
    if type(spec['schema_version']) is not int or spec['schema_version'] != 1:
        raise ValueError('Unsupported evaluator_spec schema_version; expected 1')
    for key in ('board_size', 'input_size', 'hidden_size', 'output_size'):
        if type(spec[key]) is not int or spec[key] <= 0:
            raise ValueError(f'evaluator_spec {key} must be a positive integer')
    if spec['board_size'] != board_size:
        raise ValueError(f"Board mismatch: expected {board_size}, specification has {spec['board_size']}")
    if spec['input_encoding'] != 'interleaved_black_white':
        raise ValueError('Unsupported input_encoding; this evaluator requires interleaved_black_white')
    if spec['turn_indicator'] is not False:
        raise ValueError('Unsupported turn_indicator; this evaluator has no turn input')
    if spec['input_size'] != 2 * board_size ** 2:
        raise ValueError(f'input_size must be {2 * board_size ** 2} for this board and encoding')
    if hidden_size is not None and spec['hidden_size'] != hidden_size:
        raise ValueError(f"hidden_size mismatch: component expects {hidden_size}, specification has {spec['hidden_size']}")
    if spec['output_size'] != 3 or spec['output_order'] != ['white', 'draw', 'black']:
        raise ValueError('output_size/output_order must describe [white, draw, black]')
    if spec['value_perspective'] != 'black':
        raise ValueError('Unsupported value_perspective; this evaluator returns a Black value in [0, 1]')
    if spec['arithmetic_dtype'] != 'float64':
        raise ValueError('Unsupported arithmetic_dtype; this Python evaluator uses float64')
    if spec['weight_transform'] not in ('identity', 'centered_50'):
        raise ValueError('weight_transform must be identity or centered_50')
    digest = spec['checkpoint_sha256']
    if not isinstance(digest, str) or re.fullmatch('[0-9a-f]{64}', digest) is None:
        raise ValueError('checkpoint_sha256 must be 64 lowercase hexadecimal characters')

    # Read once: validate the same bytes that will be decoded. Only use trusted
    # local pickle artifacts; a hash pins identity, not the safety of pickle.
    path = Path(weights_file)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f'checkpoint_sha256 mismatch for {path}')
    model = pickle.loads(raw)
    if not isinstance(model, dict):
        raise ValueError('Checkpoint must contain a dictionary with weights1 and weights2')
    for key in ('board_size', 'input_size', 'hidden_size', 'output_size'):
        if key in model and (
            not isinstance(model[key], (int, np.integer))
            or isinstance(model[key], (bool, np.bool_))
            or model[key] != spec[key]
        ):
            raise ValueError(f'Checkpoint metadata {key} contradicts evaluator_spec')
    for key in ('input_encoding', 'turn_indicator', 'weight_transform',
                'output_order', 'value_perspective', 'arithmetic_dtype'):
        if key in model and model[key] != spec[key]:
            raise ValueError(f'Checkpoint metadata {key} contradicts evaluator_spec')
    expected_shapes = [
        (spec['input_size'], spec['hidden_size']),
        (spec['hidden_size'], spec['output_size']),
    ]
    weights = []
    for name, shape in zip(('weights1', 'weights2'), expected_shapes):
        if name not in model:
            raise ValueError(f'Checkpoint is missing {name}')
        values = np.asarray(model[name])
        if values.shape != shape:
            raise ValueError(f'{name} shape mismatch: expected {shape}, got {values.shape}')
        if values.dtype.kind not in 'fiu':
            raise ValueError(f'{name} must contain real numeric values')
        values = values.astype(np.float64)
        if not np.isfinite(values).all():
            raise ValueError(f'{name} contains non-finite values')
        if spec['weight_transform'] == 'centered_50' and ((values < 0) | (values > 100)).any():
            raise ValueError(f'{name} must contain conductances in [0, 100] for centered_50')
        weights.append(values)
    info = {
        'mode': 'checkpoint', 'spec': spec, 'checkpoint_path': str(path.resolve()),
        'saved_accuracy_unverified': model.get('accuracy'),
    }
    return weights[0], weights[1], info


def effective_weights(weights, transform):
    if transform == 'identity':
        return weights
    if transform == 'centered_50':
        return (weights - 50.0) / 50.0
    raise ValueError(f'Unsupported weight_transform: {transform}')


def encode_board(board, board_size):
    board = np.asarray(board)
    if board.shape != (board_size, board_size):
        raise ValueError(f'Expected a {board_size}x{board_size} board, got {board.shape}')
    if not np.isin(board, (-1, 0, 1)).all():
        raise ValueError('Board cells must be -1 (White), 0 (empty), or 1 (Black)')
    return np.stack((board == 1, board == -1), axis=-1).flatten().astype(np.float64)
