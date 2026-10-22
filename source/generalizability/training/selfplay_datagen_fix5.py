#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Self-Play Data Generator for 5 Underperforming Games

Generates training data using MCTS with FULL game-rule rollouts (not the
fast random-cell-fill approach used by selfplay_datagen_universal.py).

This is critical because:
  - Pente: FastMCTSEngine rollouts skip capture rules -> garbage data
  - FrozenLake/MiniGrid/ProteinFolding/Nonograms: single-player games need
    proper agent movement, not random cell fills

For single-player games, creates fresh game instances per episode (with
different seeds) to ensure puzzle diversity.

Usage:
    python selfplay_datagen_fix5.py                         # All 5 games
    python selfplay_datagen_fix5.py --games frozen_lake     # Specific game
    python selfplay_datagen_fix5.py --output_dir selfplay_data/
"""

import json
import math
import numpy as np
import random
import sys
import os
import argparse
import time
import importlib.util
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

from generalizability.games import GAME_REGISTRY, APP_BOARD_SIZES
from generalizability.games.frozen_lake import FrozenLake
from generalizability.games.minigrid import MiniGrid
from generalizability.games.nonograms import Nonograms
from generalizability.games.protein_folding import ProteinFolding

# ---------------------------------------------------------------------------
# Game configs
# ---------------------------------------------------------------------------
GAME_CONFIGS = {
    "frozen_lake":      {"iterations": 100, "max_moves":  50, "num_games": 1000, "rollout_depth": 150, "pos_rollouts": 10},
    "minigrid":         {"iterations": 100, "max_moves":  50, "num_games": 1000, "rollout_depth": 150, "pos_rollouts": 10},
    "protein_folding":  {"iterations": 100, "max_moves":  25, "num_games": 1000, "rollout_depth": 150, "pos_rollouts": 10},
    "nonograms":        {"iterations":  50, "max_moves":  81, "num_games":  500, "rollout_depth": 150, "pos_rollouts": 10},
    "pente":            {"iterations":  30, "max_moves": 250, "num_games":  100, "rollout_depth":  40, "pos_rollouts":  0},
}

ALL_GAMES = list(GAME_CONFIGS.keys())


# ---------------------------------------------------------------------------
# Coach loader (for board_to_features)
# ---------------------------------------------------------------------------
_coach_cache: Dict[str, Any] = {}


def load_coach(game_name: str):
    """Load the game's existing board-to-feature conversion."""
    if game_name in _coach_cache:
        return _coach_cache[game_name]
    coach_path = os.path.join(SCRIPT_DIR, 'games', game_name, 'coach.py')
    spec = importlib.util.spec_from_file_location(f'{game_name}_coach', coach_path)
    coach_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(coach_module)
    coach = coach_module.GameCoach()
    _coach_cache[game_name] = coach
    return coach


# ---------------------------------------------------------------------------
# MCTS with full game-rule rollouts
# ---------------------------------------------------------------------------
class MCTSNode:
    __slots__ = ('board', 'player', 'parent', 'move', 'children',
                 'untried_moves', 'visits', 'value')

    def __init__(self, board, player, parent=None, move=None):
        self.board = board
        self.player = player
        self.parent = parent
        self.move = move
        self.children: List['MCTSNode'] = []
        self.untried_moves: Optional[list] = None
        self.visits = 0
        self.value = 0.0


    def ucb1(self, c: float = 1.414) -> float:
        if self.visits == 0:
            return float('inf')
        return (self.value / self.visits) + c * math.sqrt(
            math.log(self.parent.visits) / self.visits)


def _random_rollout(game, board, player, is_two_player: bool,
                    max_depth: int) -> float:
    """Play random moves using full game rules until terminal or depth limit.

    Returns result in [0,1] from P1's perspective.
    """
    for _ in range(max_depth):
        if game.is_terminal(board):
            break
        moves = game.get_legal_moves(board, player)
        if not moves:
            break
        move = random.choice(moves)
        board = game.apply_move(board, move, player)
        player = (3 - player) if is_two_player else 1

    if game.is_terminal(board):
        return game.get_result(board, 1)
    return 0.5  # timeout -> uncertain


def estimate_position_value(game, board, player, is_two_player,
                            num_rollouts=10, max_depth=150):
    """Estimate position value by averaging quick rollouts from this state.

    Gives each position a unique, meaningful label instead of the flat
    game-level outcome.  Returns average result in [0,1] from P1's
    perspective.
    """
    if game.is_terminal(board):
        return game.get_result(board, 1)
    rollout_sum = 0.0
    for _ in range(num_rollouts):
        result = _random_rollout(game, board.copy(), player, is_two_player,
                                 max_depth)
        rollout_sum += result
    return rollout_sum / num_rollouts


def mcts_search(game, board, player, num_iterations: int,
                max_rollout: int = 150) -> Optional[tuple]:
    """Run MCTS with full game-rule rollouts and return the best move."""
    root = MCTSNode(board, player)
    is_two_player = game.num_players == 2

    for _ in range(num_iterations):
        node = root
        sim_board = board.copy()
        sim_player = player

        # Stage 1: select until this simulation can expand.
        while (node.untried_moves is not None and
               len(node.untried_moves) == 0 and
               node.children):
            node = max(node.children, key=lambda n: n.ucb1())
            sim_board = node.board
            sim_player = node.player

        # Stage 2: expand one legal move.
        if node.untried_moves is None:
            if game.is_terminal(sim_board):
                node.untried_moves = []
            else:
                node.untried_moves = list(game.get_legal_moves(sim_board, sim_player))
                random.shuffle(node.untried_moves)

        if node.untried_moves and not game.is_terminal(sim_board):
            move = node.untried_moves.pop()
            new_board = game.apply_move(sim_board, move, sim_player)
            next_player = (3 - sim_player) if is_two_player else 1
            child = MCTSNode(new_board, next_player, parent=node, move=move)
            node.children.append(child)
            node = child
            sim_board = new_board
            sim_player = next_player

        # Stage 3: roll out with the full game rules.
        result_p1 = _random_rollout(game, sim_board, sim_player,
                                    is_two_player, max_rollout)

        # Stage 4: backpropagate from P1's perspective.
        while node is not None:
            node.visits += 1
            if is_two_player:
                node.value += result_p1 if node.player == 1 else (1.0 - result_p1)
            else:
                node.value += result_p1
            node = node.parent

    # Pick most-visited child
    if not root.children:
        moves = game.get_legal_moves(board, player)
        return random.choice(moves) if moves else None
    best = max(root.children, key=lambda n: n.visits)
    return best.move


# ---------------------------------------------------------------------------
# Game instance creation (with diverse seeds)
# ---------------------------------------------------------------------------
def create_game_instance(game_name: str, episode_idx: int):
    """Create a fresh game instance, using episode_idx as seed for diversity."""
    if game_name == "frozen_lake":
        return FrozenLake(seed=episode_idx)
    elif game_name == "minigrid":
        return MiniGrid(seed=episode_idx)
    elif game_name == "nonograms":
        return Nonograms(seed=episode_idx)
    elif game_name == "protein_folding":
        # No seed parameter — diversity comes from different MCTS trajectories
        return ProteinFolding()
    elif game_name == "pente":
        # Two-player, no seed needed — diversity from self-play
        return GAME_REGISTRY["pente"]
    else:
        return GAME_REGISTRY[game_name]


# ---------------------------------------------------------------------------
# Self-play game
# ---------------------------------------------------------------------------
def play_selfplay_game(game, game_name: str, coach, config: dict):
    """Play one self-play game using MCTS with full game-rule rollouts.

    Records every board position.  When pos_rollouts > 0, each position
    is independently evaluated via quick rollouts (per-position labels).
    Otherwise all positions share the final game outcome label.

    Returns (features_list, position_values, outcome, num_moves).
    """
    board = game.initial_state()
    is_two_player = game.num_players == 2
    current_player = 1
    iterations = config["iterations"]
    max_moves = config["max_moves"]
    rollout_depth = config.get("rollout_depth", 150)
    pos_rollouts = config.get("pos_rollouts", 0)

    position_features = []
    position_values = []  # Per-position values (only when pos_rollouts > 0)

    # Stage 1: record and optionally evaluate the initial position.
    features = coach.board_to_features(board)
    features.append(1.0)  # turn indicator: P1's turn
    position_features.append(features)

    if pos_rollouts > 0:
        position_value = estimate_position_value(game, board, 1, is_two_player,
                                                 pos_rollouts, rollout_depth)
        position_values.append(position_value)

    move_count = 0
    consecutive_passes = 0

    for _ in range(max_moves):
        if game.is_terminal(board):
            break

        moves = game.get_legal_moves(board, current_player)
        if not moves:
            if is_two_player:
                consecutive_passes += 1
                if consecutive_passes >= 2:
                    break
                current_player = 3 - current_player
                continue
            else:
                break

        consecutive_passes = 0
        move = mcts_search(game, board, current_player, iterations,
                           max_rollout=rollout_depth)
        if move is None:
            break

        board = game.apply_move(board, move, current_player)
        move_count += 1

        # Stage 2: encode the position reached by this move.
        features = coach.board_to_features(board)
        features.append(1.0 if current_player == 1 else 0.0)
        position_features.append(features)

        # Stage 3: assign a rollout label when this mode is enabled.
        if pos_rollouts > 0:
            eval_player = 1 if not is_two_player else (3 - current_player)
            position_value = estimate_position_value(
                game, board, eval_player, is_two_player, pos_rollouts,
                rollout_depth
            )
            position_values.append(position_value)

        if is_two_player:
            current_player = 3 - current_player

    # Stage 4: report the final game outcome from P1's perspective.
    if game.is_terminal(board):
        outcome = game.get_result(board, 1)
    else:
        outcome = 0.5 if is_two_player else 0.0

    return position_features, position_values, outcome, move_count


# ---------------------------------------------------------------------------
# Dataset generation
# ---------------------------------------------------------------------------
def generate_game_dataset(game_name: str, num_games: int = None,
                          output_dir: str = "."):
    """Generate self-play dataset for one game."""
    config = GAME_CONFIGS[game_name]
    num_games = num_games or config["num_games"]
    board_size = APP_BOARD_SIZES[game_name]
    coach = load_coach(game_name)

    print(f"\n{'='*60}")
    print(f"SELF-PLAY (full rules): {game_name} ({board_size}x{board_size})")
    print(f"{'='*60}")
    pos_rollouts = config.get("pos_rollouts", 0)
    label_type = f"per-position ({pos_rollouts} rollouts)" if pos_rollouts > 0 else "game-level"
    print(f"  Games: {num_games}, MCTS iterations: {config['iterations']}, "
          f"Max moves: {config['max_moves']}, Labels: {label_type}")
    sys.stdout.flush()

    position_features = []
    game_outcomes = []
    stats = {"wins": 0, "losses": 0, "draws": 0}
    t0 = time.time()

    for game_idx in range(num_games):
        # Stage 1: create a fresh puzzle or self-play trajectory.
        game = create_game_instance(game_name, game_idx)

        features_list, pos_values, outcome, num_moves = play_selfplay_game(
            game, game_name, coach, config
        )

        # Stage 2: record the final outcome statistics.
        if outcome >= 0.8:
            stats["wins"] += 1
        elif outcome <= 0.2:
            stats["losses"] += 1
        else:
            stats["draws"] += 1

        # Stage 3: attach per-position labels or the game-level fallback.
        use_per_position = len(pos_values) == len(features_list)
        for position_idx, features in enumerate(features_list):
            position_features.append(features)
            if use_per_position:
                game_outcomes.append(float(pos_values[position_idx]))
            else:
                game_outcomes.append(float(outcome))

        if (game_idx + 1) % 10 == 0:
            elapsed = time.time() - t0
            rate = (game_idx + 1) / elapsed
            eta = (num_games - game_idx - 1) / rate if rate > 0 else 0
            print(f"  Game {game_idx+1}/{num_games}: {num_moves} moves, "
                  f"outcome={outcome:.2f}, positions={len(position_features)}, "
                  f"rate={rate:.1f} games/s, ETA={eta/60:.1f}min")
            sys.stdout.flush()

    elapsed = time.time() - t0

    # Stage 4: package the arrays in the universal generator's schema.
    dataset = {
        "positions": position_features,
        "game_outcomes": game_outcomes,
        "metadata": {
            "dataset_type": "selfplay_position_evaluation",
            "game": game_name,
            "board_size": board_size,
            "num_positions": len(position_features),
            "num_games": num_games,
            "mcts_iterations": config["iterations"],
            "max_moves_per_game": config["max_moves"],
            "generation_date": datetime.now().isoformat(),
            "generation_time_seconds": round(elapsed, 1),
            "feature_format": f"coach.board_to_features() + turn indicator",
            "label_format": "per-position rollout average" if pos_rollouts > 0 else "game-level outcome",
            "pos_rollouts_per_position": pos_rollouts,
            "rollout_type": "full_game_rules",
        },
        "game_stats": stats,
    }

    output_file = os.path.join(output_dir, f"selfplay_{game_name}_{num_games}games.json")
    with open(output_file, "w") as f:
        json.dump(dataset, f)

    size_mb = os.path.getsize(output_file) / (1024 * 1024)

    print(f"\n  Results for {game_name}:")
    print(f"    Total positions: {len(position_features):,}")
    print(f"    Wins:   {stats['wins']} ({stats['wins']/num_games:.1%})")
    print(f"    Losses: {stats['losses']} ({stats['losses']/num_games:.1%})")
    print(f"    Draws:  {stats['draws']} ({stats['draws']/num_games:.1%})")
    print(f"    Time: {elapsed:.1f}s ({elapsed/num_games:.2f}s/game)")
    print(f"    Saved to: {output_file} ({size_mb:.1f} MB)")
    sys.stdout.flush()

    return output_file


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Self-Play Data Generator for 5 Underperforming Games")
    parser.add_argument("--games", nargs="*", default=None,
                        help=f"Games to generate data for (default: all 5). "
                             f"Options: {', '.join(ALL_GAMES)}")
    parser.add_argument("--num_games", type=int, default=None,
                        help="Override number of games per game type")
    parser.add_argument("--output_dir", type=str, default="selfplay_data",
                        help="Output directory for JSON files (default: selfplay_data)")
    args = parser.parse_args()

    games_to_run = args.games if args.games else ALL_GAMES

    invalid = [g for g in games_to_run if g not in GAME_CONFIGS]
    if invalid:
        print(f"ERROR: Unknown games: {invalid}. Available: {', '.join(ALL_GAMES)}")
        sys.exit(1)

    # Resolve output_dir relative to script directory
    if not os.path.isabs(args.output_dir):
        output_dir = os.path.join(SCRIPT_DIR, args.output_dir)
    else:
        output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    print("SELF-PLAY DATA GENERATOR (Full Game Rules)")
    print("=" * 60)
    print(f"Games: {', '.join(games_to_run)}")
    print(f"Output directory: {output_dir}")
    sys.stdout.flush()

    output_files = []
    total_t0 = time.time()

    for game_name in games_to_run:
        output_file = generate_game_dataset(
            game_name,
            num_games=args.num_games,
            output_dir=output_dir,
        )
        output_files.append((game_name, output_file))

    total_elapsed = time.time() - total_t0

    print(f"\n{'='*60}")
    print(f"ALL DONE! Total time: {total_elapsed/60:.1f} minutes")
    print(f"Generated datasets:")
    for game_name, output_file in output_files:
        board_size = APP_BOARD_SIZES[game_name]
        print(f"  {game_name:18s} -> {output_file}")
        print(f"    Train: python train_improved.py --dataset {output_file} "
              f"--board_size {board_size} --hidden_size 32 "
              f"--output_dir {os.path.join(os.path.dirname(output_file), f'weights_{game_name}')}")


if __name__ == "__main__":
    main()
