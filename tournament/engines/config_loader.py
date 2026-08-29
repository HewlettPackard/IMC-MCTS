# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Configuration loader for different NN accuracy levels.

This module handles loading the correct neural network weights for each
accuracy tier in the tournament.
"""

import os
from typing import List
from dataclasses import dataclass


@dataclass
class AcceleratorConfig:
    """Configuration for an IMC-MCTS instance with specific NN accuracy."""

    name: str  # Human-readable name (e.g., "High Accuracy")
    accuracy: float  # Target accuracy (e.g., 0.8195)
    weights_file: str  # Path to weights pickle file (None for baseline players)
    board_size: int  # Board size (e.g., 9)
    player_type: str = "mcts_nn"  # Player type: "mcts_nn", "random", "greedy", "pachi"

    def __repr__(self):
        return f"AcceleratorConfig({self.name}, {self.accuracy:.2%}, type={self.player_type}, board_size={self.board_size})"


def get_tournament_configs(board_size: int = 9, base_dir: str = None, num_players: int = 4) -> List[AcceleratorConfig]:
    """
    Get tournament configurations for different accuracy levels.

    Args:
        board_size: Board size (default: 9 for 9x9)
        base_dir: Base directory for IMC_MCTS_main (auto-detected if None)
        num_players: Number of players/configurations (default: 4, can use 10, or "7plus3")

    Returns:
        List of AcceleratorConfig objects with different accuracy levels

    Raises:
        FileNotFoundError: If weights files don't exist
    """
    # Resolve the repository root when the caller does not provide one.
    if base_dir is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(os.path.dirname(current_dir))

    # Use the board-specific training checkpoint directory.
    weights_dir = os.path.join(
        base_dir,
        'src', 'training',
        'results',
        f'weights_{board_size}x{board_size}'
    )

    if not os.path.exists(weights_dir):
        raise FileNotFoundError(
            f"Weights directory not found: {weights_dir}\n"
            f"Please ensure neural networks have been trained for {board_size}x{board_size}"
        )

    if num_players == 4:
        # Original four crossbar-accuracy tiers.
        configs = [
            AcceleratorConfig(
                name="High Accuracy",
                accuracy=0.8195,
                weights_file=os.path.join(weights_dir, 'best_improved_model.pkl'),
                board_size=board_size
            ),
            AcceleratorConfig(
                name="Medium-High Accuracy",
                accuracy=0.7600,
                weights_file=os.path.join(weights_dir, 'model_at_76.00percent.pkl'),
                board_size=board_size
            ),
            AcceleratorConfig(
                name="Medium Accuracy",
                accuracy=0.6400,
                weights_file=os.path.join(weights_dir, 'model_at_64.00percent.pkl'),
                board_size=board_size
            ),
            AcceleratorConfig(
                name="Low Accuracy",
                accuracy=0.5600,
                weights_file=os.path.join(weights_dir, 'model_at_56.00percent.pkl'),
                board_size=board_size
            ),
        ]
    elif num_players == 10:
        # Ten approximately even accuracy tiers from 50% to 82%.
        configs = [
            AcceleratorConfig(
                name="MCTS-NN-82%",
                accuracy=0.8195,
                weights_file=os.path.join(weights_dir, 'best_improved_model.pkl'),
                board_size=board_size
            ),
            AcceleratorConfig(
                name="MCTS-NN-78%",
                accuracy=0.7800,
                weights_file=os.path.join(weights_dir, 'model_at_78.00percent.pkl'),
                board_size=board_size
            ),
            AcceleratorConfig(
                name="MCTS-NN-74%",
                accuracy=0.7400,
                weights_file=os.path.join(weights_dir, 'model_at_74.00percent.pkl'),
                board_size=board_size
            ),
            AcceleratorConfig(
                name="MCTS-NN-70%",
                accuracy=0.7002,
                weights_file=os.path.join(weights_dir, 'model_at_70.02percent.pkl'),
                board_size=board_size
            ),
            AcceleratorConfig(
                name="MCTS-NN-66%",
                accuracy=0.6600,
                weights_file=os.path.join(weights_dir, 'model_at_66.00percent.pkl'),
                board_size=board_size
            ),
            AcceleratorConfig(
                name="MCTS-NN-62%",
                accuracy=0.6206,
                weights_file=os.path.join(weights_dir, 'model_at_62.06percent.pkl'),
                board_size=board_size
            ),
            AcceleratorConfig(
                name="MCTS-NN-58%",
                accuracy=0.5820,
                weights_file=os.path.join(weights_dir, 'model_at_58.20percent.pkl'),
                board_size=board_size
            ),
            AcceleratorConfig(
                name="MCTS-NN-54%",
                accuracy=0.5435,
                weights_file=os.path.join(weights_dir, 'model_at_54.35percent.pkl'),
                board_size=board_size
            ),
            AcceleratorConfig(
                name="MCTS-NN-52%",
                accuracy=0.5215,
                weights_file=os.path.join(weights_dir, 'model_at_52.15percent.pkl'),
                board_size=board_size
            ),
            AcceleratorConfig(
                name="MCTS-NN-50%",
                accuracy=0.5020,
                weights_file=os.path.join(weights_dir, 'model_at_50.20percent.pkl'),
                board_size=board_size
            ),
        ]
    elif num_players == "5plus3":
        # 5 NN players + 3 baselines = 8 total (WITH KATAGO!)
        # NN players: 82%, 74%, 66%, 54%, 50%
        # Baselines: Random, KataGo-1k, KataGo-5k
        configs = [
            # NN-based players (5)
            AcceleratorConfig(
                name="MCTS-NN-82%",
                accuracy=0.8195,
                weights_file=os.path.join(weights_dir, 'best_improved_model.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-74%",
                accuracy=0.7400,
                weights_file=os.path.join(weights_dir, 'model_at_74.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-66%",
                accuracy=0.6600,
                weights_file=os.path.join(weights_dir, 'model_at_66.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-54%",
                accuracy=0.5435,
                weights_file=os.path.join(weights_dir, 'model_at_54.35percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-50%",
                accuracy=0.5020,
                weights_file=os.path.join(weights_dir, 'model_at_50.20percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            # Baseline players (3)
            AcceleratorConfig(
                name="Random",
                accuracy=0.0,
                weights_file=None,
                board_size=board_size,
                player_type="random"
            ),
            AcceleratorConfig(
                name="KataGo-1k",
                accuracy=0.90,  # Strong baseline, 1000 playouts
                weights_file=None,
                board_size=board_size,
                player_type="katago_1k"
            ),
            AcceleratorConfig(
                name="KataGo-5k",
                accuracy=0.95,  # Very strong baseline, 5000 playouts
                weights_file=None,
                board_size=board_size,
                player_type="katago_5k"
            ),
        ]
    elif num_players == "3plus1_proper_pachi":
        # 3 NN players (PROPER GO RULES) + 1 Pachi = 4 total (QUICK TEST)
        # NN players: 82%, 70%, 58%
        # Baseline: Pachi (real Go engine)
        # Uses crossbar_training_proper weights with captures, suicide detection, etc.

        proper_weights_dir = os.path.join(
            base_dir,
            'src', 'training',
            'results',
            f'weights_{board_size}x{board_size}'
        )

        configs = [
            # NN-based players with PROPER Go rules (3)
            AcceleratorConfig(
                name="MCTS-NN-82%",
                accuracy=0.8200,
                weights_file=os.path.join(proper_weights_dir, 'model_at_82.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-70%",
                accuracy=0.7002,
                weights_file=os.path.join(proper_weights_dir, 'model_at_70.02percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-58%",
                accuracy=0.5820,
                weights_file=os.path.join(proper_weights_dir, 'model_at_58.20percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            # Baseline player (1 - Pachi)
            AcceleratorConfig(
                name="Pachi",
                accuracy=0.75,
                weights_file=None,
                board_size=board_size,
                player_type="pachi"
            ),
        ]
    elif num_players == "5plus1_proper_pachi":
        # 6 NN players (PROPER GO RULES) + 1 Pachi = 7 total (QUICK TEST)
        # NN players: 82%, 76%, 70%, 64%, 58%, 50%
        # Baseline: Pachi (real Go engine)
        # Uses crossbar_training_proper weights with captures, suicide detection, etc.

        proper_weights_dir = os.path.join(
            base_dir,
            'src', 'training',
            'results',
            f'weights_{board_size}x{board_size}'
        )

        configs = [
            # NN-based players with PROPER Go rules (6)
            AcceleratorConfig(
                name="MCTS-NN-82%",
                accuracy=0.8200,
                weights_file=os.path.join(proper_weights_dir, 'model_at_82.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-76%",
                accuracy=0.7600,
                weights_file=os.path.join(proper_weights_dir, 'model_at_76.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-70%",
                accuracy=0.7002,
                weights_file=os.path.join(proper_weights_dir, 'model_at_70.02percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-64%",
                accuracy=0.6400,
                weights_file=os.path.join(proper_weights_dir, 'model_at_64.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-58%",
                accuracy=0.5820,
                weights_file=os.path.join(proper_weights_dir, 'model_at_58.20percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-50%",
                accuracy=0.5020,
                weights_file=os.path.join(proper_weights_dir, 'model_at_50.20percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            # Baseline player (1 - Pachi)
            AcceleratorConfig(
                name="Pachi",
                accuracy=0.75,
                weights_file=None,
                board_size=board_size,
                player_type="pachi"
            ),
        ]
    elif num_players == "5plus3_proper":
        # 5 NN players (PROPER GO RULES) + 3 baselines = 8 total
        # NN players: 82%, 76%, 70%, 64%, 58%, 50%
        # Baselines: Random, KataGo-1k (weak), KataGo-5k (strong)
        # Uses crossbar_training_proper weights with captures, suicide detection, etc.

        proper_weights_dir = os.path.join(
            base_dir,
            'src', 'training',
            'results',
            f'weights_{board_size}x{board_size}'
        )

        configs = [
            # NN-based players with PROPER Go rules (5)
            AcceleratorConfig(
                name="MCTS-NN-82%",
                accuracy=0.8200,
                weights_file=os.path.join(proper_weights_dir, 'model_at_82.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-76%",
                accuracy=0.7600,
                weights_file=os.path.join(proper_weights_dir, 'model_at_76.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-70%",
                accuracy=0.7002,
                weights_file=os.path.join(proper_weights_dir, 'model_at_70.02percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-64%",
                accuracy=0.6400,
                weights_file=os.path.join(proper_weights_dir, 'model_at_64.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-58%",
                accuracy=0.5820,
                weights_file=os.path.join(proper_weights_dir, 'model_at_58.20percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-50%",
                accuracy=0.5020,
                weights_file=os.path.join(proper_weights_dir, 'model_at_50.20percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            # Baseline players (3 - Random + 2 KataGo levels)
            AcceleratorConfig(
                name="Random",
                accuracy=0.0,
                weights_file=None,
                board_size=board_size,
                player_type="random"
            ),
            AcceleratorConfig(
                name="KataGo-1k",
                accuracy=0.85,  # Weaker KataGo (1000 playouts)
                weights_file=None,
                board_size=board_size,
                player_type="katago_1k"
            ),
            AcceleratorConfig(
                name="KataGo-5k",
                accuracy=0.95,  # Stronger KataGo (5000 playouts)
                weights_file=None,
                board_size=board_size,
                player_type="katago_5k"
            ),
        ]
    elif num_players == "5plus1":
        # 5 NN players + 1 baseline = 6 total (FAST AND RELIABLE!)
        # NN players: 82%, 74%, 66%, 54%, 50%
        # Baseline: Random ONLY (no KataGo due to rule incompatibility)
        configs = [
            # NN-based players (5)
            AcceleratorConfig(
                name="MCTS-NN-82%",
                accuracy=0.8195,
                weights_file=os.path.join(weights_dir, 'best_improved_model.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-74%",
                accuracy=0.7400,
                weights_file=os.path.join(weights_dir, 'model_at_74.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-66%",
                accuracy=0.6600,
                weights_file=os.path.join(weights_dir, 'model_at_66.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-54%",
                accuracy=0.5435,
                weights_file=os.path.join(weights_dir, 'model_at_54.35percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-50%",
                accuracy=0.5020,
                weights_file=os.path.join(weights_dir, 'model_at_50.20percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            # Baseline player (1 - Random only!)
            AcceleratorConfig(
                name="Random",
                accuracy=0.0,
                weights_file=None,
                board_size=board_size,
                player_type="random"
            ),
        ]
    elif num_players == "5plus2":
        # 5 NN players + 2 baselines = 7 total (NO PACHI - FAST AND RELIABLE!)
        # NN players: 82%, 74%, 66%, 54%, 50%
        # Baselines: Random, Greedy
        configs = [
            # NN-based players (5)
            AcceleratorConfig(
                name="MCTS-NN-82%",
                accuracy=0.8195,
                weights_file=os.path.join(weights_dir, 'best_improved_model.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-74%",
                accuracy=0.7400,
                weights_file=os.path.join(weights_dir, 'model_at_74.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-66%",
                accuracy=0.6600,
                weights_file=os.path.join(weights_dir, 'model_at_66.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-54%",
                accuracy=0.5435,
                weights_file=os.path.join(weights_dir, 'model_at_54.35percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-50%",
                accuracy=0.5020,
                weights_file=os.path.join(weights_dir, 'model_at_50.20percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            # Baseline players (2 - NO PACHI!)
            AcceleratorConfig(
                name="Random",
                accuracy=0.0,
                weights_file=None,
                board_size=board_size,
                player_type="random"
            ),
            AcceleratorConfig(
                name="Greedy-Heuristic",
                accuracy=0.5,
                weights_file=None,
                board_size=board_size,
                player_type="greedy"
            ),
        ]
    elif num_players == "7plus3" or num_players == 10.1:  # 10.1 is a hack for backwards compat
        # 7 NN players + 3 baselines = 10 total
        # NN players: 82%, 74%, 70%, 66%, 62%, 54%, 50%
        # Baselines: Random, Greedy, Pachi
        configs = [
            # NN-based players (7)
            AcceleratorConfig(
                name="MCTS-NN-82%",
                accuracy=0.8195,
                weights_file=os.path.join(weights_dir, 'best_improved_model.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-74%",
                accuracy=0.7400,
                weights_file=os.path.join(weights_dir, 'model_at_74.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-70%",
                accuracy=0.7002,
                weights_file=os.path.join(weights_dir, 'model_at_70.02percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-66%",
                accuracy=0.6600,
                weights_file=os.path.join(weights_dir, 'model_at_66.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-62%",
                accuracy=0.6206,
                weights_file=os.path.join(weights_dir, 'model_at_62.06percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-54%",
                accuracy=0.5435,
                weights_file=os.path.join(weights_dir, 'model_at_54.35percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-50%",
                accuracy=0.5020,
                weights_file=os.path.join(weights_dir, 'model_at_50.20percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            # Baseline players (3)
            AcceleratorConfig(
                name="Random",
                accuracy=0.0,  # Worst possible
                weights_file=None,
                board_size=board_size,
                player_type="random"
            ),
            AcceleratorConfig(
                name="Greedy-Heuristic",
                accuracy=0.5,  # Estimated (between random and 50% NN)
                weights_file=None,
                board_size=board_size,
                player_type="greedy"
            ),
            AcceleratorConfig(
                name="Pachi",
                accuracy=0.85,  # Estimated (stronger than 82% NN)
                weights_file=None,
                board_size=board_size,
                player_type="pachi"
            ),
        ]
    elif num_players == "5plus2_rollout":
        # 5 NN players + MCTS-Rollout baseline + Random baseline = 7 total
        # THE KEY COMPARISON: MCTS+NN vs MCTS+Rollout at same iterations
        configs = [
            AcceleratorConfig(
                name="MCTS-NN-82%",
                accuracy=0.8195,
                weights_file=os.path.join(weights_dir, 'best_improved_model.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-74%",
                accuracy=0.7400,
                weights_file=os.path.join(weights_dir, 'model_at_74.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-66%",
                accuracy=0.6600,
                weights_file=os.path.join(weights_dir, 'model_at_66.00percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-54%",
                accuracy=0.5435,
                weights_file=os.path.join(weights_dir, 'model_at_54.35percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            AcceleratorConfig(
                name="MCTS-NN-50%",
                accuracy=0.5020,
                weights_file=os.path.join(weights_dir, 'model_at_50.20percent.pkl'),
                board_size=board_size,
                player_type="mcts_nn"
            ),
            # MCTS with random rollouts (same iterations as NN players)
            AcceleratorConfig(
                name="MCTS-Rollout",
                accuracy=0.0,
                weights_file=None,
                board_size=board_size,
                player_type="mcts_rollout"
            ),
            # Pure random baseline
            AcceleratorConfig(
                name="Random",
                accuracy=0.0,
                weights_file=None,
                board_size=board_size,
                player_type="random"
            ),
        ]
    else:
        raise ValueError(f"num_players must be 4, 10, '5plus2', '5plus3', '7plus3', or '5plus2_rollout', got {num_players}")

    # Verify every NN checkpoint while skipping weight-free baselines.
    missing_files = []
    for config in configs:
        if config.weights_file is not None and not os.path.exists(config.weights_file):
            missing_files.append(config.weights_file)

    if missing_files:
        print(f"WARNING: Some weight files not found:")
        for missing_file in missing_files:
            print(f"  - {missing_file}")
        print()
        print("Available files in weights directory:")
        if os.path.exists(weights_dir):
            for available_file in sorted(os.listdir(weights_dir)):
                if available_file.endswith('.pkl'):
                    print(f"  - {available_file}")
        raise FileNotFoundError(f"Missing {len(missing_files)} weight files")

    return configs


def get_config_by_name(name: str, board_size: int = 9) -> AcceleratorConfig:
    """
    Get a specific configuration by name.

    Args:
        name: Name matching one of: "High Accuracy", "Medium-High Accuracy",
              "Medium Accuracy", "Low Accuracy"
        board_size: Board size (default: 9)

    Returns:
        AcceleratorConfig for that accuracy level

    Raises:
        ValueError: If name doesn't match any configuration
    """
    configs = get_tournament_configs(board_size)

    for config in configs:
        if config.name == name:
            return config

    valid_names = [config.name for config in configs]
    raise ValueError(
        f"Unknown config name: {name}\n"
        f"Valid names: {valid_names}"
    )


def get_config_by_accuracy(accuracy: float, board_size: int = 9) -> AcceleratorConfig:
    """
    Get configuration closest to target accuracy.

    Args:
        accuracy: Target accuracy (e.g., 0.75 for 75%)
        board_size: Board size (default: 9)

    Returns:
        AcceleratorConfig with closest accuracy
    """
    configs = get_tournament_configs(board_size)

    # Select the checkpoint with minimum absolute accuracy error.
    closest = min(configs, key=lambda config: abs(config.accuracy - accuracy))

    return closest


def print_tournament_configs(board_size: int = 9):
    """
    Print summary of tournament configurations.

    Args:
        board_size: Board size (default: 9)
    """
    try:
        configs = get_tournament_configs(board_size)

        print(f"Tournament Configurations for {board_size}x{board_size} Board")
        print("=" * 80)
        print()

        for config_index, config in enumerate(configs, 1):
            print(f"{config_index}. {config.name}")
            print(f"   Accuracy: {config.accuracy:.2%}")
            print(f"   Weights: {os.path.basename(config.weights_file)}")
            print(f"   Full path: {config.weights_file}")
            print(f"   Exists: {'✓' if os.path.exists(config.weights_file) else '✗'}")
            print()

        print(f"Total configurations: {len(configs)}")
        print(f"Tournament matchups: {len(configs) * (len(configs) - 1) // 2}")
        print()

    except FileNotFoundError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import sys

    # Test configuration loading
    board_size = int(sys.argv[1]) if len(sys.argv) > 1 else 9

    print_tournament_configs(board_size)
