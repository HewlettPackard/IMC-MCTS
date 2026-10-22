#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Dataset Validation Script -- run before training to catch encoding issues.

Checks:
  1. Feature dimension matches metadata expectation
  2. No dead channels (all-zero or all-one features)
  3. Label balance (not too skewed)
  4. New feature channels carry discriminative signal
  5. Feature values are in valid range [0, 1]
  6. Consistency: all positions have same feature length

Usage:
    python validate_datasets.py                          # Validate all 5 modified games
    python validate_datasets.py --games hex havannah     # Validate specific games
    python validate_datasets.py --generate               # Generate + validate
"""

import os
import sys
import json
import argparse
import subprocess
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GAMES_DIR = os.path.join(SCRIPT_DIR, 'games')

# Games with modified encodings and their expected feature sizes
MODIFIED_GAMES = {
    'havannah':        {'old': 451, 'new_min': 500},  # 169*4 + 1 = 677
    'hex':             {'old': 243, 'new_min': 400},   # 121*4 + 1 = 485
    'nonograms':       {'old': 163, 'new_min': 230},   # 162 + 72 + 1 = 235
    'minesweeper':     {'old': 163, 'new_min': 240},   # 81*3 + 1 = 244
    'protein_folding': {'old': 339, 'new_min': 340},   # 338 + 5 + 1 = 344
}


def validate_dataset(game_name, dataset_path):
    """Validate a single game's dataset. Returns dict with pass/fail and details."""
    result = {'game': game_name, 'path': dataset_path, 'checks': [], 'passed': True}

    if not os.path.exists(dataset_path):
        result['checks'].append(('EXISTS', False, f'Dataset not found: {dataset_path}'))
        result['passed'] = False
        return result
    result['checks'].append(('EXISTS', True, 'Dataset file found'))

    with open(dataset_path, 'r') as f:
        dataset = json.load(f)

    positions = dataset['positions']
    outcomes = dataset['game_outcomes']
    metadata = dataset.get('metadata', {})
    n_pos = len(positions)
    result['n_positions'] = n_pos

    # Check 1: Non-empty
    if n_pos == 0:
        result['checks'].append(('NON_EMPTY', False, 'Dataset is empty'))
        result['passed'] = False
        return result
    result['checks'].append(('NON_EMPTY', True, f'{n_pos:,} positions'))

    # Check 2: Consistent feature dimensions
    feat_lens = set(len(p) for p in positions)
    if len(feat_lens) != 1:
        result['checks'].append(('CONSISTENT_DIM', False,
                                 f'Inconsistent feature lengths: {feat_lens}'))
        result['passed'] = False
    else:
        feat_dim = feat_lens.pop()
        result['feat_dim'] = feat_dim
        result['checks'].append(('CONSISTENT_DIM', True, f'Feature dim = {feat_dim}'))

        # Check 2b: Feature dim matches metadata
        expected = metadata.get('feature_vector_size')
        if expected and feat_dim != expected:
            result['checks'].append(('DIM_METADATA', False,
                                     f'Feature dim {feat_dim} != metadata {expected}'))
            result['passed'] = False
        elif expected:
            result['checks'].append(('DIM_METADATA', True,
                                     f'Matches metadata ({expected})'))

        # Check 2c: New encoding detected
        info = MODIFIED_GAMES.get(game_name)
        if info:
            if feat_dim <= info['old']:
                result['checks'].append(('NEW_ENCODING', False,
                                         f'Still using OLD encoding ({feat_dim} <= {info["old"]}). '
                                         f'Expected >= {info["new_min"]}'))
                result['passed'] = False
            else:
                result['checks'].append(('NEW_ENCODING', True,
                                         f'New encoding active ({feat_dim} > {info["old"]})'))

    # Convert to numpy for analysis (sample if large)
    sample_size = min(n_pos, 5000)
    indices = np.random.choice(n_pos, size=sample_size, replace=False)
    X = np.array([positions[i] for i in indices], dtype=np.float32)
    Y = np.array([outcomes[i] for i in indices])

    # Check 3: Feature value range
    f_min, f_max = X.min(), X.max()
    if f_min < -0.01 or f_max > 1.01:
        result['checks'].append(('VALUE_RANGE', False,
                                 f'Features out of [0,1]: min={f_min:.4f}, max={f_max:.4f}'))
        result['passed'] = False
    else:
        result['checks'].append(('VALUE_RANGE', True,
                                 f'All features in [0, 1] (min={f_min:.4f}, max={f_max:.4f})'))

    # Check 4: Dead features (all-zero or all-constant across sample)
    feat_std = X.std(axis=0)
    dead_features = np.sum(feat_std < 1e-8)
    dead_pct = dead_features / X.shape[1] * 100
    if dead_pct > 50:
        result['checks'].append(('DEAD_FEATURES', False,
                                 f'{dead_features}/{X.shape[1]} features are dead '
                                 f'({dead_pct:.1f}%)'))
        result['passed'] = False
    else:
        result['checks'].append(('DEAD_FEATURES', True,
                                 f'{dead_features}/{X.shape[1]} dead features '
                                 f'({dead_pct:.1f}%) -- OK'))

    # Check 4b: New channels specifically (skip base board features)
    info = MODIFIED_GAMES.get(game_name)
    if info and X.shape[1] > info['old']:
        # The new features start after the old-format features
        # For most games, base board features are board_size^2 * 2
        # New features are the extra columns
        new_start = info['old'] - 1  # -1 for turn indicator at end of old format
        new_feats = X[:, new_start:-1]  # exclude final turn indicator
        if new_feats.shape[1] > 0:
            new_std = new_feats.std(axis=0)
            new_dead = np.sum(new_std < 1e-8)
            new_active = new_feats.shape[1] - new_dead
            if new_active == 0:
                result['checks'].append(('NEW_CHANNEL_SIGNAL', False,
                                         'ALL new feature channels are dead (no signal)!'))
                result['passed'] = False
            else:
                new_mean = new_feats.mean(axis=0)
                result['checks'].append(('NEW_CHANNEL_SIGNAL', True,
                                         f'{new_active}/{new_feats.shape[1]} new channels active, '
                                         f'mean range [{new_mean.min():.3f}, {new_mean.max():.3f}]'))

    # Check 5: Label balance
    unique_labels, counts = np.unique(Y.round(2), return_counts=True)
    label_dist = dict(zip(unique_labels, counts))
    most_common_pct = max(counts) / len(Y) * 100
    if most_common_pct > 90:
        result['checks'].append(('LABEL_BALANCE', False,
                                 f'Severely imbalanced: {label_dist} '
                                 f'(most common = {most_common_pct:.1f}%)'))
        result['passed'] = False
    elif most_common_pct > 70:
        result['checks'].append(('LABEL_BALANCE', True,
                                 f'Somewhat skewed but OK: {label_dist} '
                                 f'(most common = {most_common_pct:.1f}%)'))
    else:
        result['checks'].append(('LABEL_BALANCE', True,
                                 f'Well balanced: {label_dist}'))

    # Check 6: Discriminative signal — do features correlate with labels?
    if len(unique_labels) >= 2:
        # Simple check: feature means differ between label groups
        groups = {}
        for label in unique_labels:
            mask = Y.round(2) == label
            if mask.sum() >= 10:
                groups[label] = X[mask].mean(axis=0)
        if len(groups) >= 2:
            labels = sorted(groups.keys())
            diff = np.abs(groups[labels[-1]] - groups[labels[0]])
            significant_diff = np.sum(diff > 0.01)
            result['checks'].append(('DISCRIMINATIVE', True,
                                     f'{significant_diff}/{X.shape[1]} features differ '
                                     f'between label groups'))

    return result


def print_validation_report(results):
    """Print a formatted validation report."""
    all_passed = True
    print("\n" + "=" * 70)
    print("  DATASET VALIDATION REPORT")
    print("=" * 70)

    for r in results:
        status = "PASS" if r['passed'] else "FAIL"
        print(f"\n  {r['game'].upper()} [{status}]")
        if 'feat_dim' in r:
            print(f"    Feature dim: {r['feat_dim']}, Positions: {r.get('n_positions', '?')}")
        for check_name, passed, detail in r['checks']:
            icon = "  OK" if passed else "FAIL"
            print(f"    [{icon}] {check_name}: {detail}")
        if not r['passed']:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("  ALL DATASETS PASSED VALIDATION")
    else:
        failed = [r['game'] for r in results if not r['passed']]
        print(f"  FAILED: {', '.join(failed)}")
    print("=" * 70 + "\n")
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Validate training datasets")
    parser.add_argument('--games', nargs='+', default=None,
                        help='Games to validate (default: all modified games)')
    parser.add_argument('--generate', action='store_true',
                        help='Generate datasets before validating')
    parser.add_argument('--num_positions', type=int, default=1000,
                        help='Positions to generate for validation (default: 1000)')
    args = parser.parse_args()

    games = args.games or list(MODIFIED_GAMES.keys())

    if args.generate:
        print("Generating validation datasets...")
        for game in games:
            datagen_script = os.path.join(GAMES_DIR, game, 'datagen.py')
            output_path = os.path.join(GAMES_DIR, game, 'results',
                                       'validation_dataset.json')
            if not os.path.exists(datagen_script):
                print(f"  SKIP {game}: no datagen.py")
                continue
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            print(f"  Generating {game} ({args.num_positions} positions)...")
            cmd = [sys.executable, datagen_script,
                   '--num_positions', str(args.num_positions),
                   '--output', output_path]
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    cwd=os.path.join(GAMES_DIR, game))
            if result.returncode != 0:
                print(f"    ERROR: {result.stderr[:300]}")
            else:
                print(f"    OK -> {output_path}")

    # Validate
    results = []
    for game in games:
        # Check validation dataset first, then training dataset
        val_path = os.path.join(GAMES_DIR, game, 'results',
                                'validation_dataset.json')
        train_path = os.path.join(GAMES_DIR, game, 'results', 'dataset.json')
        dataset_path = val_path if os.path.exists(val_path) else train_path
        results.append(validate_dataset(game, dataset_path))

    all_passed = print_validation_report(results)
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
