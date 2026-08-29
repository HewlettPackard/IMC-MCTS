#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Train all board sizes with proven heuristic pipeline
Expected: 70-90% accuracy for each board size

All training outputs will be saved in results/:
  - Datasets: results/go_positions_{size}x{size}.json
  - Weights: results/weights_{size}x{size}/best_improved_model.pkl
  - Logs: results/training.log
"""

import subprocess
import os
from datetime import datetime

# Board sizes for the main results
BOARD_SIZES = [2, 3, 5, 9, 13, 19]
NUM_POSITIONS = 2000  # Reduced for faster training

# Hidden layer sizes optimized for each board size
# Balances model capacity with hardware efficiency
HIDDEN_SIZE_MAP = {
    2: 16,    # 8 inputs → 16 hidden (2× scaling for small boards)
    3: 24,    # 18 inputs → 24 hidden (1.3× scaling)
    5: 32,    # 50 inputs → 32 hidden (0.64× scaling - proven architecture)
    9: 96,    # 162 inputs → 96 hidden (0.59× scaling)
    13: 128,  # 338 inputs → 128 hidden (0.38× scaling)
    19: 192   # 722 inputs → 192 hidden (0.27× scaling)
}

RESULTS_DIR = "results"
LOG_FILE = os.path.join(RESULTS_DIR, "training.log")


def log_and_print(message):
    """Print a message and append it to the training log."""
    print(message)
    with open(LOG_FILE, "a") as f:
        f.write(message + "\n")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    log_and_print("=" * 70)
    log_and_print("PROVEN PIPELINE: Go Position Evaluation")
    log_and_print("=" * 70)
    log_and_print("Method: Heuristic-based dataset generation")
    log_and_print("Architecture: Two-layer memristor crossbar (Input → Hidden → Output)")
    log_and_print(f"Board sizes: {', '.join([f'{b}×{b}' for b in BOARD_SIZES])}")
    log_and_print("")
    log_and_print("Crossbar dimensions per board size:")
    for bs in BOARD_SIZES:
        input_sz = bs * bs * 2
        hidden_sz = HIDDEN_SIZE_MAP[bs]
        total_mem = input_sz * hidden_sz + hidden_sz * 3
        log_and_print(f"   {bs}×{bs}: {input_sz} → {hidden_sz} → 3 ({total_mem:,} memristors)")
    log_and_print("")
    log_and_print(f"Output directory: {RESULTS_DIR}/")
    log_and_print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_and_print("")

    results = {}

    for board_size in BOARD_SIZES:
        log_and_print("")
        log_and_print("=" * 70)
        log_and_print(f"BOARD SIZE: {board_size}×{board_size}")
        log_and_print("=" * 70)

        dataset = os.path.join(RESULTS_DIR, f"go_positions_{board_size}x{board_size}.json")
        output_dir = os.path.join(RESULTS_DIR, f"weights_{board_size}x{board_size}")

        # Step 1: Generate dataset
        log_and_print("")
        log_and_print(f"Step 1/2: Generating {NUM_POSITIONS:,} positions...")
        ret = subprocess.run([
            "python3", "datagen.py",
            "--num_positions", str(NUM_POSITIONS),
            "--board_size", str(board_size),
            "--output", dataset
        ])

        if ret.returncode != 0:
            log_and_print(f"ERROR: Dataset generation failed for {board_size}×{board_size}")
            results[board_size] = "FAILED (datagen)"
            continue

        # Step 2: Train
        hidden_size = HIDDEN_SIZE_MAP[board_size]
        input_size = board_size * board_size * 2
        log_and_print("")
        log_and_print(f"Step 2/2: Training two-layer crossbar...")
        log_and_print(f"   Architecture: {input_size} → {hidden_size} → 3")
        log_and_print(f"   Crossbar 1: {input_size}×{hidden_size} ({input_size * hidden_size:,} memristors)")
        log_and_print(f"   Crossbar 2: {hidden_size}×3 ({hidden_size * 3:,} memristors)")
        log_and_print(f"   Total: {input_size * hidden_size + hidden_size * 3:,} memristors")
        ret = subprocess.run([
            "python3", "train_improved.py",
            "--dataset", dataset,
            "--board_size", str(board_size),
            "--epochs", "2000",
            "--learning_rate", "0.003",
            "--hidden_size", str(hidden_size),
            "--output_dir", output_dir,
            "--patience", "200",
            "--batch_size", "256"
        ])

        if ret.returncode != 0:
            log_and_print(f"ERROR: Training failed for {board_size}×{board_size}")
            results[board_size] = "FAILED (training)"
            continue

        # Check if best model exists
        best_model = os.path.join(output_dir, "best_improved_model.pkl")
        if os.path.exists(best_model):
            results[board_size] = "SUCCESS"
            log_and_print("")
            log_and_print(f"{board_size}×{board_size} COMPLETE!")
            log_and_print(f"   Dataset: {dataset}")
            log_and_print(f"   Weights: {output_dir}/")
        else:
            results[board_size] = "FAILED (no model)"

    log_and_print("")
    log_and_print("=" * 70)
    log_and_print("ALL BOARD SIZES COMPLETE!")
    log_and_print("=" * 70)
    log_and_print("")
    log_and_print("Training results:")
    for board_size, status in results.items():
        icon = "[OK]" if status == "SUCCESS" else "[FAIL]"
        log_and_print(f"  {icon} {board_size}×{board_size}: {status}")
    log_and_print("")
    log_and_print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_and_print("")
    log_and_print("All files saved in: results/")
    log_and_print("")


if __name__ == "__main__":
    main()
