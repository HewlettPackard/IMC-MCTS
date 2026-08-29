#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Prepare training data for the 162->96->3 crossbar NN.

Takes existing 163-feature data (with turn bit) and:
1. Drops the turn bit (feature 162) -> 162 features
2. Applies color-flip augmentation (doubles dataset)
3. Generates additional self-play positions to reach target count
4. Saves as JSON compatible with train.py
"""

import json
import os
import sys
import numpy as np
from datetime import datetime

# Add case_study_go to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SELFPLAY_DATA


def load_existing_data(path: str):
    """Load existing 163-feature dataset."""
    print(f"Loading: {path}")
    with open(path) as input_handle:
        dataset = json.load(input_handle)

    positions = np.array(dataset['positions'], dtype=np.float32)
    outcomes = np.array(dataset['game_outcomes'], dtype=np.float32)

    print(f"  Shape: {positions.shape}, Outcomes: {len(outcomes)}")
    return positions, outcomes


def drop_turn_bit(positions: np.ndarray) -> np.ndarray:
    """Drop the last column (turn bit) from 163-feature data -> 162 features."""
    if positions.shape[1] == 163:
        print(f"  Dropping turn bit: {positions.shape[1]} -> 162")
        return positions[:, :162]
    elif positions.shape[1] == 162:
        print(f"  Already 162 features, no change needed")
        return positions
    else:
        raise ValueError(f"Unexpected feature dim: {positions.shape[1]}")


def color_flip_augmentation(positions: np.ndarray, outcomes: np.ndarray):
    """
    Color-flip augmentation: swap black/white channels, invert labels.

    For 2-channel encoding: swap features at indices (2i, 2i+1) for each cell.
    Outcome 0.0 (White) -> 1.0 (Black), 1.0 -> 0.0, 0.5 -> 0.5
    """
    print(f"  Applying color-flip augmentation...")
    num_positions, num_features = positions.shape
    assert num_features == 162, f"Expected 162 features, got {num_features}"

    flipped_positions = np.zeros_like(positions)
    for feature_index in range(0, num_features, 2):
        flipped_positions[:, feature_index] = positions[:, feature_index + 1]
        flipped_positions[:, feature_index + 1] = positions[:, feature_index]

    flipped_outcomes = 1.0 - outcomes  # Invert labels

    # Combine
    all_positions = np.vstack([positions, flipped_positions])
    all_outcomes = np.concatenate([outcomes, flipped_outcomes])

    print(f"  Augmented: {num_positions} -> {len(all_positions)} positions")
    return all_positions, all_outcomes


def generate_selfplay_positions(target_count: int, board_size: int = 9) -> tuple:
    """
    Generate additional positions via MCTS self-play with random rollouts.

    Uses the Go engine with random MCTS to play games and collect positions
    with outcome labels based on game result.
    """
    from engine.go_engine import GoEngine
    from engine.mcts_engine import MCTSEngine

    go_engine = GoEngine(board_size)
    mcts_engine = MCTSEngine(go_engine, simulator=None, iterations=100)

    positions = []
    outcomes = []
    games_played = 0

    print(f"  Generating {target_count} positions via self-play...")

    while len(positions) < target_count:
        state = go_engine.initial_state()
        game_positions = []

        # Play a game
        while not go_engine.is_terminal(state) and state['move_count'] < 162:
            # Record position
            features = go_engine.board_to_features(state['board'])
            game_positions.append(features)

            # Make a move
            move = mcts_engine.search(state)
            state = go_engine.apply_move(state, move)

        # Get result
        result = go_engine.get_result_black(state)
        # Discretize: <0.35 -> 0.0 (White), >0.65 -> 1.0 (Black), else 0.5
        if result > 0.65:
            label = 1.0
        elif result < 0.35:
            label = 0.0
        else:
            label = 0.5

        # Add all positions from this game
        for features in game_positions:
            if len(positions) >= target_count:
                break
            positions.append(features.tolist())
            outcomes.append(label)

        games_played += 1
        if games_played % 50 == 0:
            print(f"    Games: {games_played}, Positions: {len(positions)}/{target_count}")

    print(f"  Generated {len(positions)} positions from {games_played} games")
    return np.array(positions, dtype=np.float32), np.array(outcomes, dtype=np.float32)


def prepare_dataset(
    source_path: str,
    output_path: str = "training_data_162.json",
    target_positions: int = 200000,
    augment: bool = True,
    generate_extra: bool = True,
):
    """
    Full data preparation pipeline.

    1. Load existing data, drop turn bit
    2. Color-flip augmentation (2x)
    3. Generate additional self-play data if needed
    4. Shuffle and save
    """
    print("=" * 60)
    print("PREPARING TRAINING DATA")
    print("=" * 60)

    # Step 1: Load and drop turn bit
    positions, outcomes = load_existing_data(source_path)
    positions = drop_turn_bit(positions)

    # Step 2: Color-flip augmentation
    if augment:
        positions, outcomes = color_flip_augmentation(positions, outcomes)

    current_count = len(positions)
    print(f"\nAfter augmentation: {current_count} positions")

    # Step 3: Generate extra self-play data if needed
    if generate_extra and current_count < target_positions:
        extra_needed = target_positions - current_count
        print(f"\nNeed {extra_needed} more positions to reach {target_positions}")
        extra_positions, extra_outcomes = generate_selfplay_positions(extra_needed)

        # Also augment the extra data
        if augment and len(extra_positions) > 0:
            extra_positions, extra_outcomes = color_flip_augmentation(
                extra_positions,
                extra_outcomes
            )

        positions = np.vstack([positions, extra_positions[:extra_needed]])
        outcomes = np.concatenate([outcomes, extra_outcomes[:extra_needed]])

    # Truncate to target
    if len(positions) > target_positions:
        selected_indices = np.random.permutation(len(positions))[:target_positions]
        positions = positions[selected_indices]
        outcomes = outcomes[selected_indices]

    # Step 4: Shuffle
    shuffle_idx = np.random.permutation(len(positions))
    positions = positions[shuffle_idx]
    outcomes = outcomes[shuffle_idx]

    # Stats
    print(f"\nFinal dataset:")
    print(f"  Positions: {len(positions)}")
    print(f"  Feature dim: {positions.shape[1]}")
    print(f"  White wins: {np.sum(outcomes == 0.0):,} ({np.mean(outcomes == 0.0):.1%})")
    print(f"  Draws: {np.sum(outcomes == 0.5):,} ({np.mean(outcomes == 0.5):.1%})")
    print(f"  Black wins: {np.sum(outcomes == 1.0):,} ({np.mean(outcomes == 1.0):.1%})")

    # Save
    dataset = {
        'positions': positions.tolist(),
        'game_outcomes': outcomes.tolist(),
        'metadata': {
            'board_size': 9,
            'feature_size': 162,
            'turn_bit': False,
            'color_flip_augmentation': augment,
            'source': source_path,
            'total_positions': len(positions),
            'generation_date': datetime.now().isoformat(),
        }
    }

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w') as output_handle:
        json.dump(dataset, output_handle)

    print(f"\nSaved to: {output_path}")
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"File size: {file_size_mb:.1f} MB")

    return dataset


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Prepare training data")
    parser.add_argument('--source', type=str,
                        default=SELFPLAY_DATA,
                        help='Source dataset path')
    parser.add_argument('--output', type=str,
                        default='training_data_162.json',
                        help='Output path')
    parser.add_argument('--target', type=int, default=200000,
                        help='Target number of positions')
    parser.add_argument('--no-augment', action='store_true',
                        help='Skip color-flip augmentation')
    parser.add_argument('--no-selfplay', action='store_true',
                        help='Skip self-play generation (use only existing data)')
    args = parser.parse_args()

    prepare_dataset(
        source_path=args.source,
        output_path=args.output,
        target_positions=args.target,
        augment=not args.no_augment,
        generate_extra=not args.no_selfplay,
    )
