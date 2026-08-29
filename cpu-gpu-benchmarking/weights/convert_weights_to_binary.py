#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Convert trained neural network weights from pickle format to binary format for C++.

This script converts the .pkl weight files from the crossbar training directory
into binary files that can be easily loaded by C++/CUDA code.

Binary format:
[4 bytes: rows (int32)]
[4 bytes: cols (int32)]
[rows×cols×4 bytes: weights (float32) in row-major order]

Usage:
    python3 convert_weights_to_binary.py --source generalizability/weights/models
"""

import argparse
import pickle
import struct
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = REPO_ROOT / "generalizability" / "weights" / "models"
DEFAULT_TARGET_DIR = Path(__file__).resolve().parent


def convert_pkl_to_bin(board_size, source_dir, target_dir):
    """
    Convert pickle weights to binary format for a specific board size.

    Args:
        board_size: Size of the Go board (2, 3, 5, 9, 13, or 19)
    """
    # Source pickle file
    source_pickle_path = source_dir / f"weights_{board_size}x{board_size}" / "best_improved_model.pkl"

    if not source_pickle_path.exists():
        print(f"⚠️  Warning: {source_pickle_path} not found, skipping...")
        return False

    # Load pickle file
    print(f"Loading {source_pickle_path}...")
    with open(source_pickle_path, 'rb') as file_handle:
        model_data = pickle.load(file_handle)

    # Convert to numpy arrays if they're lists
    first_layer_weights = np.array(model_data['weights1'], dtype=np.float32)
    second_layer_weights = np.array(model_data['weights2'], dtype=np.float32)

    # Print info
    print(f"  weights1 shape: {first_layer_weights.shape} ({first_layer_weights.dtype})")
    print(f"  weights2 shape: {second_layer_weights.shape} ({second_layer_weights.dtype})")
    print(f"  accuracy: {model_data.get('accuracy', 'N/A')}")

    # Target binary files
    target_board_directory = target_dir / f"{board_size}x{board_size}"
    target_board_directory.mkdir(parents=True, exist_ok=True)
    first_layer_binary_path = target_board_directory / "weights1.bin"
    second_layer_binary_path = target_board_directory / "weights2.bin"

    # Save weights1 as binary
    with open(first_layer_binary_path, 'wb') as file_handle:
        # Write dimensions: rows, cols (4 bytes each, int32)
        file_handle.write(struct.pack(
            'ii',
            first_layer_weights.shape[0],
            first_layer_weights.shape[1]
        ))
        # Write data as float32 in row-major order
        first_layer_weights.astype(np.float32).tofile(file_handle)

    # Save weights2 as binary
    with open(second_layer_binary_path, 'wb') as file_handle:
        file_handle.write(struct.pack(
            'ii',
            second_layer_weights.shape[0],
            second_layer_weights.shape[1]
        ))
        second_layer_weights.astype(np.float32).tofile(file_handle)

    # Verify file sizes
    first_layer_file_size = first_layer_binary_path.stat().st_size
    second_layer_file_size = second_layer_binary_path.stat().st_size
    expected_first_layer_size = 8 + first_layer_weights.size * 4  # 8 bytes header + data
    expected_second_layer_size = 8 + second_layer_weights.size * 4

    print(f"✅ Saved {first_layer_binary_path} ({first_layer_file_size} bytes, expected {expected_first_layer_size})")
    print(f"✅ Saved {second_layer_binary_path} ({second_layer_file_size} bytes, expected {expected_second_layer_size})")

    return True


def main():
    """Convert all board sizes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_DIR,
                        help="Directory containing weights_NxN/best_improved_model.pkl")
    parser.add_argument("--output", type=Path, default=DEFAULT_TARGET_DIR,
                        help="Directory for board-specific binary weights")
    args = parser.parse_args()

    print("=" * 60)
    print("Converting Neural Network Weights to Binary Format")
    print("=" * 60)
    print()

    board_sizes = [2, 3, 5, 9, 13, 19]
    success_count = 0

    for board_size in board_sizes:
        print(f"\n[{board_size}×{board_size} Board]")
        if convert_pkl_to_bin(board_size, args.source, args.output):
            success_count += 1
        print()

    print("=" * 60)
    print(f"Conversion Complete: {success_count}/{len(board_sizes)} successful")
    print("=" * 60)

    # Print summary
    print("\nGenerated files:")
    for board_size in board_sizes:
        target_board_directory = args.output / f"{board_size}x{board_size}"
        if (target_board_directory / "weights1.bin").exists():
            print(f"  {board_size}x{board_size}/weights1.bin")
            print(f"  {board_size}x{board_size}/weights2.bin")


if __name__ == "__main__":
    main()
