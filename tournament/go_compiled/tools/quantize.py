# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Weight Quantization for Crossbar NN.

Quantizes full-precision conductance weights to N discrete levels,
modeling the limited programmability of RRAM/memristor devices.

Conductance range: [0.1, 99.9] nS
Quantization levels:
  2-bit:  4 levels
  4-bit: 16 levels
  8-bit: 256 levels
"""

import numpy as np
import pickle
import os


def quantize_weights(weights: np.ndarray, num_bits: int,
                     g_min: float = 0.1, g_max: float = 99.9) -> np.ndarray:
    """
    Quantize conductance weights to discrete levels.

    Uniform quantization: snap each weight to nearest level in
    np.linspace(g_min, g_max, 2^num_bits).

    Args:
        weights: Full-precision conductance matrix in [g_min, g_max]
        num_bits: Number of bits (2, 4, or 8)
        g_min: Minimum conductance (default 0.1 nS)
        g_max: Maximum conductance (default 99.9 nS)

    Returns:
        Quantized weight matrix
    """
    num_levels = 2 ** num_bits
    conductance_levels = np.linspace(g_min, g_max, num_levels)

    # Limit every device conductance to the programmable range.
    clipped_weights = np.clip(weights, g_min, g_max)

    # Snap each conductance to the nearest uniform programming level.
    level_indices = np.argmin(
        np.abs(clipped_weights[:, :, np.newaxis] - conductance_levels),
        axis=2,
    )
    quantized_weights = conductance_levels[level_indices]

    return quantized_weights


def quantize_model(input_path: str, output_path: str, num_bits: int,
                   g_min: float = 0.1, g_max: float = 99.9):
    """
    Load a full-precision model, quantize weights, and save.

    Args:
        input_path: Path to full-precision pickle file
        output_path: Path for quantized output pickle file
        num_bits: Quantization bits
        g_min: Min conductance
        g_max: Max conductance
    """
    with open(input_path, 'rb') as input_handle:
        model = pickle.load(input_handle)

    weights1 = np.array(model['weights1'])
    weights2 = np.array(model['weights2'])

    # Quantize both crossbar conductance matrices independently.
    quantized_weights1 = quantize_weights(weights1, num_bits, g_min, g_max)
    quantized_weights2 = quantize_weights(weights2, num_bits, g_min, g_max)

    # Measure conductance distortion introduced by each quantized crossbar.
    mse1 = np.mean((weights1 - quantized_weights1) ** 2)
    mse2 = np.mean((weights2 - quantized_weights2) ** 2)

    quantized_model = {
        'weights1': quantized_weights1.tolist(),
        'weights2': quantized_weights2.tolist(),
        'accuracy': model.get('accuracy', 0.0),
        'quantization': {
            'num_bits': num_bits,
            'num_levels': 2 ** num_bits,
            'g_min': g_min,
            'g_max': g_max,
            'mse_layer1': float(mse1),
            'mse_layer2': float(mse2),
        },
        'original_accuracy': model.get('accuracy', 0.0),
        'architecture': model.get('architecture', 'two_layer_memristor_crossbar'),
        'input_size': model.get('input_size', weights1.shape[0]),
        'hidden_size': model.get('hidden_size', weights1.shape[1]),
        'output_size': model.get('output_size', weights2.shape[1]),
    }

    # Preserve the existing per-bit output layout and pickle schema.
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'wb') as output_handle:
        pickle.dump(quantized_model, output_handle)

    print(f"Quantized {num_bits}-bit: {input_path} -> {output_path}")
    print(f"  Levels: {2**num_bits}, MSE layer1={mse1:.6f}, layer2={mse2:.6f}")

    return quantized_model


def quantize_all(input_path: str, output_dir: str = "weights"):
    """
    Generate all quantized variants (2-bit, 4-bit, 8-bit) from a full-precision model.

    Args:
        input_path: Path to full-precision model
        output_dir: Base output directory
    """
    for bits in [2, 4, 8]:
        bit_output_dir = os.path.join(output_dir, f"{bits}bit")
        os.makedirs(bit_output_dir, exist_ok=True)
        output_path = os.path.join(bit_output_dir, f"model_{bits}bit.pkl")
        quantize_model(input_path, output_path, bits)


def test_quantization():
    """Test quantization correctness."""
    import tempfile

    np.random.seed(42)
    w1 = np.random.uniform(0.1, 99.9, (162, 96))
    w2 = np.random.uniform(0.1, 99.9, (96, 3))

    # Test 8-bit: should be close to original
    w1_8 = quantize_weights(w1, 8)
    assert w1_8.shape == w1.shape
    assert np.all(w1_8 >= 0.1) and np.all(w1_8 <= 99.9)
    mse_8 = np.mean((w1 - w1_8) ** 2)

    # Test 4-bit: more error
    w1_4 = quantize_weights(w1, 4)
    mse_4 = np.mean((w1 - w1_4) ** 2)

    # Test 2-bit: most error
    w1_2 = quantize_weights(w1, 2)
    mse_2 = np.mean((w1 - w1_2) ** 2)

    assert mse_2 > mse_4 > mse_8, f"Expected MSE 2bit > 4bit > 8bit: {mse_2}, {mse_4}, {mse_8}"

    # Verify 2-bit only has 4 unique values
    unique_2 = np.unique(w1_2)
    assert len(unique_2) == 4, f"2-bit should have 4 levels, got {len(unique_2)}"

    # Test full pipeline
    model = {'weights1': w1.tolist(), 'weights2': w2.tolist(), 'accuracy': 0.75}
    tmp = tempfile.NamedTemporaryFile(suffix='.pkl', delete=False)
    with open(tmp.name, 'wb') as f:
        pickle.dump(model, f)

    try:
        out_path = tmp.name + '_q4.pkl'
        quantize_model(tmp.name, out_path, 4)

        with open(out_path, 'rb') as f:
            q_model = pickle.load(f)
        assert 'quantization' in q_model
        assert q_model['quantization']['num_bits'] == 4
        os.unlink(out_path)
    finally:
        os.unlink(tmp.name)

    print("Quantization tests passed!")
    print(f"  MSE: 2-bit={mse_2:.4f}, 4-bit={mse_4:.4f}, 8-bit={mse_8:.6f}")


if __name__ == "__main__":
    test_quantization()
