#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Universal Self-Play Training Data Generator

Generates training data for ALL two-player games by playing MCTS+Rollout
games against itself, recording every board position, and labeling with
the actual game outcome.

Optimizations over the base MCTSEngine:
  - Single-child expansion (not full expansion) for lower memory/time
  - Fast rollouts: play on random empty cells, skip game-specific legality
  - Lazy untried_moves initialization

Works with: Go, Hex, Gomoku, Havannah, Othello, Connect Four, Pente, Breakthrough

Usage:
    python selfplay_datagen_universal.py                    # All games, defaults
    python selfplay_datagen_universal.py --games go hex     # Specific games
    python selfplay_datagen_universal.py --num_games 500    # Custom game count
"""

import json
import math
import numpy as np
import random
import sys
import os
import argparse
import time
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generalizability.games import GAME_REGISTRY, APP_BOARD_SIZES


# Per-game configuration: iterations scaled by board size, max_moves by game type
GAME_CONFIGS = {
    "connect_four": {"iterations": 200, "max_moves": 42,  "num_games": 500},
    "othello":      {"iterations": 150, "max_moves": 64,  "num_games": 500},
    "breakthrough": {"iterations": 150, "max_moves": 100, "num_games": 500},
    "go":           {"iterations": 150, "max_moves": 100, "num_games": 500},
    "hex":          {"iterations": 100, "max_moves": 130, "num_games": 300},
    "gomoku":       {"iterations": 100, "max_moves": 200, "num_games": 300},
    "havannah":     {"iterations": 100, "max_moves": 200, "num_games": 300},
    "pente":        {"iterations":  50, "max_moves": 250, "num_games": 200},
}

# Metadata rows beyond board_size in initial_state
METADATA_ROWS = {
    "go": 1,       # 1 extra row for pass counter
    "pente": 2,    # 2 extra rows for capture counts
}

TWO_PLAYER_GAMES = [name for name, game in GAME_REGISTRY.items() if game.num_players == 2]


class FastMCTSEngine:
    """Run memory-light MCTS for self-play data generation.

    Key differences from applications/mcts_engine.py:
      - Expands ONE child at a time (not all) -> much less memory for large boards
      - Fast rollouts: fills random empty cells, skips game-specific rules
      - Lazy initialization of untried_moves
      - Perspective-correct: values stored from P1's perspective, flipped in UCB1
    """

    def __init__(self, game, iterations=100, max_rollout_depth=100):
        self.game = game
        self.iterations = iterations
        self.max_rollout_depth = max_rollout_depth
        self.exploration_c = 1.414

    def search(self, board, player):
        """Run MCTS and return best move."""
        root = self._make_node(board, player)
        root["untried_moves"] = list(self.game.get_legal_moves(board, player))
        root["terminal"] = self.game.is_terminal(board)
        nodes = [root]

        for _ in range(self.iterations):
            # Stage 1: select a node that is terminal or can expand.
            idx = 0
            while True:
                node = nodes[idx]
                if node["terminal"]:
                    break
                # Lazy init
                if node["untried_moves"] is None:
                    node["untried_moves"] = list(
                        self.game.get_legal_moves(node["board"], node["player"]))
                    node["terminal"] = self.game.is_terminal(node["board"])
                    if node["terminal"]:
                        break
                # Has untried moves -> expand here
                if node["untried_moves"]:
                    break
                # All moves tried -> select best child via UCB1
                if not node["children"]:
                    break
                best_idx = -1
                best_score = -float("inf")
                for candidate_idx in node["children"]:
                    candidate = nodes[candidate_idx]
                    if candidate["visits"] == 0:
                        best_idx = candidate_idx
                        break
                    exploit = candidate["value"] / candidate["visits"]
                    if node["player"] == 2:
                        exploit = 1.0 - exploit
                    explore = self.exploration_c * math.sqrt(
                        math.log(node["visits"]) / candidate["visits"])
                    score = exploit + explore
                    if score > best_score:
                        best_score = score
                        best_idx = candidate_idx
                if best_idx < 0:
                    break
                idx = best_idx

            node = nodes[idx]

            # Stage 2: expand one child and remove its move in O(1).
            if not node.get("terminal", False) and node["untried_moves"]:
                move_idx = random.randrange(len(node["untried_moves"]))
                move = node["untried_moves"][move_idx]
                # O(1) swap-remove
                node["untried_moves"][move_idx] = node["untried_moves"][-1]
                node["untried_moves"].pop()

                new_board = self.game.apply_move(node["board"], move, node["player"])
                child = self._make_node(new_board, 3 - node["player"], idx, move)
                child_idx = len(nodes)
                nodes.append(child)
                node["children"].append(child_idx)
                idx = child_idx
                node = nodes[idx]

            # Stage 3: estimate the child with the fast rollout model.
            result = self._fast_rollout(node["board"], node["player"])

            # Stage 4: backpropagate from P1's perspective.
            while idx is not None:
                nodes[idx]["visits"] += 1
                nodes[idx]["value"] += result
                idx = nodes[idx]["parent"]

        # Choose most-visited child
        if not root["children"]:
            moves = self.game.get_legal_moves(board, player)
            return random.choice(moves) if moves else (0, 0)

        best = max(root["children"], key=lambda child_idx: nodes[child_idx]["visits"])
        return nodes[best]["move"]

    def _make_node(self, board, player, parent=None, move=None):
        return {
            "board": board,
            "player": player,
            "parent": parent,
            "move": move,
            "visits": 0,
            "value": 0.0,
            "children": [],
            "untried_moves": None,  # lazily initialized
            "terminal": None,
        }

    def _fast_rollout(self, board, player):
        """Fast rollout: fill random empty cells, skip game-specific rules.

        This is a rough but fast value estimate. The actual game positions
        (which become training labels) use full rules via play_selfplay_game().
        """
        play_board = board.copy()
        play_rows = self.game.board_size  # skip metadata rows

        # Collect empty cells in the play area
        empty = []
        for r in range(play_rows):
            for c in range(play_board.shape[1]):
                if play_board[r, c] == 0:
                    empty.append((r, c))

        current_player = player
        steps = min(self.max_rollout_depth, len(empty))
        for _ in range(steps):
            if not empty:
                break
            empty_idx = random.randrange(len(empty))
            r, c = empty[empty_idx]
            play_board[r, c] = current_player
            # O(1) swap-remove
            empty[empty_idx] = empty[-1]
            empty.pop()
            current_player = 3 - current_player

        # Evaluate from Player 1's perspective
        return self.game.get_result(play_board, 1)


def get_play_area(board, game_name, board_size):
    """Extract the play area from a board, slicing off metadata rows."""
    extra = METADATA_ROWS.get(game_name, 0)
    if extra > 0:
        return board[:board_size]
    return board


def board_to_features(board, game_name, board_size):
    """Convert board to feature vector compatible with train_improved.py.

    All games use 1/2 encoding:
        Player 1 -> [1.0, 0.0]
        Player 2 -> [0.0, 1.0]
        Empty    -> [0.0, 0.0]

    Plus a turn indicator (1.0 if P1's turn, 0.0 if P2's turn).
    Feature vector size = board_size^2 * 2 + 1.
    """
    play_area = get_play_area(board, game_name, board_size)

    features = []
    for cell_value in play_area.flatten():
        if cell_value == 1:     # Player 1
            features.extend([1.0, 0.0])
        elif cell_value == 2:   # Player 2
            features.extend([0.0, 1.0])
        else:             # Empty (0) or other
            features.extend([0.0, 0.0])

    # Turn indicator
    p1_count = int(np.sum(play_area == 1))
    p2_count = int(np.sum(play_area == 2))
    features.append(1.0 if p1_count <= p2_count else 0.0)

    return features


def play_selfplay_game(engine, game, game_name, board_size, max_moves):
    """Play one self-play game, recording all positions.

    Uses full game rules for move selection and application.
    The FastMCTSEngine only uses fast rollouts internally for value estimation.
    """
    board = game.initial_state()
    board_positions = [board.copy()]
    current_player = 1
    consecutive_passes = 0

    for _ in range(max_moves):
        if game.is_terminal(board):
            break

        moves = game.get_legal_moves(board, current_player)
        if not moves:
            consecutive_passes += 1
            if consecutive_passes >= 2:
                break
            current_player = 3 - current_player
            continue

        consecutive_passes = 0
        move = engine.search(board, current_player)
        board = game.apply_move(board, move, current_player)
        board_positions.append(board.copy())
        current_player = 3 - current_player

    outcome = game.get_result(board, 1)
    return board_positions, outcome, len(board_positions) - 1


def generate_game_dataset(game_name, num_games=None, iterations=None,
                          max_moves=None, output_dir="."):
    """Generate self-play dataset for one game."""
    game = GAME_REGISTRY[game_name]
    board_size = APP_BOARD_SIZES[game_name]
    config = GAME_CONFIGS[game_name]

    num_games = num_games or config["num_games"]
    iterations = iterations or config["iterations"]
    max_moves = max_moves or config["max_moves"]

    print(f"\n{'='*60}")
    print(f"SELF-PLAY: {game.name} ({board_size}x{board_size})")
    print(f"{'='*60}")
    print(f"  Games: {num_games}, MCTS iterations: {iterations}, Max moves: {max_moves}")
    sys.stdout.flush()

    engine = FastMCTSEngine(game, iterations=iterations, max_rollout_depth=max_moves)

    position_features = []
    game_outcomes = []
    stats = {"p1_wins": 0, "p2_wins": 0, "draws": 0}
    t0 = time.time()

    for game_idx in range(num_games):
        board_positions, outcome, num_moves = play_selfplay_game(
            engine, game, game_name, board_size, max_moves
        )

        # Stage 1: count the completed game's outcome.
        if outcome == 1.0:
            stats["p1_wins"] += 1
        elif outcome == 0.0:
            stats["p2_wins"] += 1
        else:
            stats["draws"] += 1

        # Stage 2: encode every visited board with the game-level label.
        for board_state in board_positions:
            features = board_to_features(board_state, game_name, board_size)
            position_features.append(features)
            game_outcomes.append(float(outcome))

        if (game_idx + 1) % 10 == 0:
            elapsed = time.time() - t0
            rate = (game_idx + 1) / elapsed
            eta = (num_games - game_idx - 1) / rate if rate > 0 else 0
            print(f"  Game {game_idx+1}/{num_games}: {num_moves} moves, "
                  f"outcome={outcome:.1f}, positions={len(position_features)}, "
                  f"rate={rate:.1f} games/s, ETA={eta/60:.1f}min")
            sys.stdout.flush()

    elapsed = time.time() - t0

    # Stage 3: package the arrays in the trainer's JSON schema.
    dataset = {
        "positions": position_features,
        "game_outcomes": game_outcomes,
        "metadata": {
            "dataset_type": "selfplay_position_evaluation",
            "game": game_name,
            "game_display_name": game.name,
            "board_size": board_size,
            "num_positions": len(position_features),
            "num_games": num_games,
            "mcts_iterations": iterations,
            "max_moves_per_game": max_moves,
            "generation_date": datetime.now().isoformat(),
            "generation_time_seconds": round(elapsed, 1),
            "player_encoding": "1=Player1, 2=Player2, 0=Empty",
            "feature_format": f"{board_size*board_size*2+1} features (2 per cell + turn indicator)",
            "label_format": "1.0=P1 wins, 0.5=Draw, 0.0=P2 wins",
        },
        "game_stats": stats,
    }

    output_file = os.path.join(output_dir, f"selfplay_{game_name}_{num_games}games.json")
    with open(output_file, "w") as f:
        json.dump(dataset, f)

    size_mb = os.path.getsize(output_file) / (1024 * 1024)

    print(f"\n  Results for {game.name}:")
    print(f"    Total positions: {len(position_features):,}")
    print(f"    P1 wins: {stats['p1_wins']} ({stats['p1_wins']/num_games:.1%})")
    print(f"    P2 wins: {stats['p2_wins']} ({stats['p2_wins']/num_games:.1%})")
    print(f"    Draws:   {stats['draws']} ({stats['draws']/num_games:.1%})")
    print(f"    Time: {elapsed:.1f}s ({elapsed/num_games:.2f}s/game)")
    print(f"    Saved to: {output_file} ({size_mb:.1f} MB)")
    sys.stdout.flush()

    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Universal Self-Play Training Data Generator")
    parser.add_argument("--games", nargs="*", default=None,
                        help=f"Games to generate data for (default: all). "
                             f"Options: {', '.join(TWO_PLAYER_GAMES)}")
    parser.add_argument("--num_games", type=int, default=None,
                        help="Override number of games per game type")
    parser.add_argument("--iterations", type=int, default=None,
                        help="Override MCTS iterations")
    parser.add_argument("--output_dir", type=str, default=".",
                        help="Output directory for JSON files")

    args = parser.parse_args()

    games_to_run = args.games if args.games else list(TWO_PLAYER_GAMES)

    invalid = [g for g in games_to_run if g not in GAME_REGISTRY]
    if invalid:
        print(f"ERROR: Unknown games: {invalid}. Available: {', '.join(TWO_PLAYER_GAMES)}")
        sys.exit(1)

    single_player = [g for g in games_to_run if GAME_REGISTRY[g].num_players != 2]
    if single_player:
        print(f"WARNING: Skipping single-player games: {single_player}")
        games_to_run = [g for g in games_to_run if GAME_REGISTRY[g].num_players == 2]

    os.makedirs(args.output_dir, exist_ok=True)

    print("UNIVERSAL SELF-PLAY TRAINING DATA GENERATOR")
    print("=" * 60)
    print(f"Games: {', '.join(games_to_run)}")
    print(f"Output directory: {args.output_dir}")
    sys.stdout.flush()

    output_files = []
    total_t0 = time.time()

    for game_name in games_to_run:
        output_file = generate_game_dataset(
            game_name,
            num_games=args.num_games,
            iterations=args.iterations,
            output_dir=args.output_dir
        )
        output_files.append((game_name, output_file))

    total_elapsed = time.time() - total_t0

    print(f"\n{'='*60}")
    print(f"ALL DONE! Total time: {total_elapsed/60:.1f} minutes")
    print(f"Generated datasets:")
    for game_name, output_file in output_files:
        board_size = APP_BOARD_SIZES[game_name]
        print(f"  {game_name:15s} -> {output_file}")
        print(f"    Train: python train_improved.py --dataset {output_file} "
              f"--board_size {board_size} --output_dir selfplay_weights_{game_name}")


if __name__ == "__main__":
    main()
