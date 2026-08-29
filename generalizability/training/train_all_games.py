#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Train crossbar NNs for all 13 Accelerator games.

Pipeline per game:
  1. Generate dataset using game-specific coach + datagen
  2. Train 2-layer memristor crossbar NN
  3. Save weights to game's results/ directory

Usage:
  python train_all_games.py                    # Train all games
  python train_all_games.py --games go hex     # Train specific games
  python train_all_games.py --num_positions 10000  # Smaller dataset
"""

import os
import sys
import argparse
import subprocess

# Game configurations: name -> (board_size, hidden_size, module_name)
GAME_CONFIGS = {
    'go':               (9,  96,  'go'),
    'hex':              (11, 96,  'hex'),
    'gomoku':           (15, 128, 'gomoku'),
    'havannah':         (15, 128, 'havannah'),
    'othello':          (8,  96,  'othello'),
    'connect_four':     (8,  96,  'connect_four'),
    'pente':            (19, 192, 'pente'),
    'breakthrough':     (8,  96,  'breakthrough'),
    'protein_folding':  (13, 128, 'protein_folding'),
    'nonograms':        (9,  96,  'nonograms'),
    'frozen_lake':      (8,  96,  'frozen_lake'),
    'minigrid':         (8,  96,  'minigrid'),
    'minesweeper':      (9,  96,  'minesweeper'),
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GAMES_DIR = os.path.join(SCRIPT_DIR, 'games')
TRAINER = os.path.join(SCRIPT_DIR, 'train_improved.py')


def train_game(game_name, board_size, hidden_size, num_positions=50000,
               epochs=2000, patience=200, batch_size=256):
    """Run the full training pipeline for one game."""

    game_dir = os.path.join(GAMES_DIR, game_name)
    results_dir = os.path.join(game_dir, 'results')
    os.makedirs(results_dir, exist_ok=True)

    dataset_path = os.path.join(results_dir, 'dataset.json')
    datagen_script = os.path.join(game_dir, 'datagen.py')

    print(f"\n{'='*60}")
    print(f"  TRAINING: {game_name.upper()} ({board_size}x{board_size})")
    print(f"{'='*60}")

    # Step 1: Generate dataset
    if not os.path.exists(dataset_path):
        print(f"\n[1/2] Generating dataset ({num_positions} positions)...")
        if os.path.exists(datagen_script):
            cmd = [
                sys.executable, datagen_script,
                '--num_positions', str(num_positions),
                '--output', dataset_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True,
                                     cwd=game_dir)
            if result.returncode != 0:
                print(f"  ERROR in datagen: {result.stderr[:500]}")
                return None
            print(f"  Dataset saved: {dataset_path}")
        else:
            print(f"  ERROR: No datagen.py found at {datagen_script}")
            return None
    else:
        print(f"\n[1/2] Dataset exists: {dataset_path}")

    # Step 2: Train crossbar NN
    print(f"\n[2/2] Training crossbar NN...")
    cmd = [
        sys.executable, TRAINER,
        '--dataset', dataset_path,
        '--board_size', str(board_size),
        '--hidden_size', str(hidden_size),
        '--output_dir', results_dir,
        '--epochs', str(epochs),
        '--patience', str(patience),
        '--batch_size', str(batch_size),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR in training: {result.stderr[:500]}")
        return None

    # Extract final accuracy from output
    for line in result.stdout.split('\n'):
        if 'Final accuracy' in line:
            print(f"  {line.strip()}")

    print(f"  Weights saved: {results_dir}/best_improved_model.pkl")
    return results_dir


def main():
    parser = argparse.ArgumentParser(description="Train crossbar NNs for all games")
    parser.add_argument('--games', nargs='+', default=None,
                        choices=list(GAME_CONFIGS.keys()),
                        help='Specific games to train (default: all)')
    parser.add_argument('--num_positions', type=int, default=50000,
                        help='Positions per dataset (default: 50000)')
    parser.add_argument('--epochs', type=int, default=2000,
                        help='Max training epochs (default: 2000)')
    parser.add_argument('--patience', type=int, default=200,
                        help='Early stopping patience (default: 200)')
    parser.add_argument('--batch_size', type=int, default=256,
                        help='Batch size (default: 256)')
    parser.add_argument('--skip_existing', action='store_true',
                        help='Skip games that already have trained weights')

    args = parser.parse_args()
    games = args.games or list(GAME_CONFIGS.keys())

    print(f"Accelerator: Train All Games")
    print(f"Games: {', '.join(games)}")
    print(f"Positions per game: {args.num_positions}")
    print(f"Max epochs: {args.epochs}")

    results = {}
    for game_name in games:
        board_size, hidden_size, _ = GAME_CONFIGS[game_name]

        if args.skip_existing:
            weights_path = os.path.join(GAMES_DIR, game_name, 'results',
                                        'best_improved_model.pkl')
            if os.path.exists(weights_path):
                print(f"\nSkipping {game_name} (weights exist)")
                continue

        result = train_game(
            game_name, board_size, hidden_size,
            num_positions=args.num_positions,
            epochs=args.epochs,
            patience=args.patience,
            batch_size=args.batch_size,
        )
        results[game_name] = result

    # Summary
    print(f"\n{'='*60}")
    print(f"  TRAINING SUMMARY")
    print(f"{'='*60}")
    for game_name in games:
        status = "OK" if results.get(game_name) else "SKIP/FAIL"
        board_size, hidden_size, _ = GAME_CONFIGS[game_name]
        print(f"  {game_name:20s} {board_size:2d}x{board_size:<2d}  hidden={hidden_size:3d}  [{status}]")


if __name__ == "__main__":
    main()
