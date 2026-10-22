#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Behavioral Demo - Play each game at LOW/MED/HIGH iteration counts.

Demonstrates that the game-agnostic MCTS engine can play all 13 applications
with no game-specific tuning. Reports win rates, game lengths, scores, and
game-specific quality metrics.

Usage:
    python applications/demo_behavioral.py --game hex --iterations 200 --num-games 5
    python applications/demo_behavioral.py --game all --num-games 10
"""

import argparse
import sys
import os
import time
import csv
from typing import Dict, List, Any

# Ensure applications package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.algorithm.game_interface import GameInterface
from generalizability.games import GAME_REGISTRY, APP_BOARD_SIZES
from core.algorithm.mcts_engine import MCTSEngine

# Software demo iteration presets (much smaller than hardware estimation presets
# to keep runtime reasonable for behavioral demonstrations)
DEMO_PRESETS = {
    "LOW": 50,
    "MED": 200,
    "HIGH": 1000,
}


def _aggregate_metrics(all_metrics: List[dict]) -> dict:
    """Average numeric metrics and take the mode of categorical metrics."""
    if not all_metrics:
        return {}
    aggregate = {}
    for key in all_metrics[0]:
        metric_values = [metrics[key] for metrics in all_metrics if key in metrics]
        if not metric_values:
            continue
        if isinstance(metric_values[0], (int, float)):
            aggregate[f"avg_{key}"] = sum(metric_values) / len(metric_values)
        else:
            # Categorical metrics report the most common value.
            from collections import Counter
            counts = Counter(metric_values)
            aggregate[f"mode_{key}"] = counts.most_common(1)[0][0]
    return aggregate


def play_games(game: GameInterface, iterations: int,
               num_games: int, eval_fn=None) -> Dict[str, Any]:
    """Play one experiment configuration and summarize its game records."""
    engine = MCTSEngine(game, iterations=iterations, eval_fn=eval_fn)
    game_records = []

    # Stage 1: play the requested number of games.
    for _ in range(num_games):
        record = engine.play_game()
        game_records.append(record)

    # Stage 2: compute game length and outcome statistics.
    game_lengths = [record["game_length"] for record in game_records]
    avg_length = sum(game_lengths) / len(game_lengths)

    if game.num_players == 2:
        wins = sum(1 for record in game_records if record["result_p1"] == 1.0)
        draws = sum(1 for record in game_records if record["result_p1"] == 0.5)
        losses = sum(1 for record in game_records if record["result_p1"] == 0.0)
        win_rate = wins / num_games
        avg_score = sum(record["result_p1"] for record in game_records) / num_games
    else:
        wins = sum(1 for record in game_records if record["result_p1"] >= 0.5)
        draws = 0
        losses = num_games - wins
        win_rate = wins / num_games
        avg_score = sum(record["result_p1"] for record in game_records) / num_games

    # Stage 3: aggregate each game's application-specific metrics.
    all_metrics = [record.get("metrics", {}) for record in game_records]
    aggregate_metrics = _aggregate_metrics(all_metrics)

    stats = {
        "game": game.name,
        "board_size": game.board_size,
        "iterations": iterations,
        "num_games": num_games,
        "win_rate": win_rate,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "avg_length": avg_length,
        "avg_score": avg_score,
    }
    stats.update(aggregate_metrics)
    return stats


def print_results_table(all_results: List[Dict[str, Any]]):
    """Print the behavioral summary and application-specific metrics."""
    has_mode = any("mode" in result for result in all_results)
    header = (
        f"{'Game':<18} {'Board':>5} {'Strength':>8} {'Iter':>6} "
        f"{'Games':>5} {'WinRate':>8} {'W/D/L':>10} {'AvgLen':>7} {'AvgScore':>8}"
    )
    if has_mode:
        header += f" {'Mode':>6}"
    sep = "-" * len(header)

    print("\n" + "=" * len(header))
    print("Accelerator Behavioral Demo Results")
    print("=" * len(header))
    print(header)
    print(sep)

    current_game = None
    for result in all_results:
        if result["game"] != current_game:
            if current_game is not None:
                print(sep)
            current_game = result["game"]
        line = (
            f"{result['game']:<18} {result['board_size']:>5} {result.get('strength', ''):>8} "
            f"{result['iterations']:>6} {result['num_games']:>5} "
            f"{result['win_rate']:>7.1%} "
            f"{result['wins']}/{result['draws']}/{result['losses']:>7} "
            f"{result['avg_length']:>7.1f} {result['avg_score']:>8.3f}"
        )
        if has_mode:
            line += f" {result.get('mode', ''):>6}"
        print(line)
    print(sep)

    # Print game-specific metrics summary
    print("\n" + "=" * 80)
    print("Game-Specific Quality Metrics")
    print("=" * 80)
    for result in all_results:
        metric_keys = [key for key in result
                       if key.startswith("avg_") or key.startswith("mode_")]
        if not metric_keys:
            continue
        strength = result.get("strength", "")
        parts = [
            f"{key}={result[key]:.3f}"
            if isinstance(result[key], float) else f"{key}={result[key]}"
            for key in metric_keys
        ]
        print(f"  {result['game']:<16} [{strength:>6}]  {', '.join(parts)}")
    print("-" * 80)


def save_results_csv(all_results: List[Dict[str, Any]], filepath: str):
    """Save results to CSV, including game-specific metric columns."""
    if not all_results:
        return
    # Keep the core experiment columns first, then append discovered metrics.
    fieldnames = []
    seen = set()
    base_keys = ["game", "board_size", "strength", "mode", "iterations", "num_games",
                 "win_rate", "wins", "draws", "losses", "avg_length", "avg_score"]
    for key in base_keys:
        fieldnames.append(key)
        seen.add(key)
    for result in all_results:
        for key in sorted(result.keys()):
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\nResults saved to: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Accelerator Behavioral Demo - Play games with MCTS"
    )
    parser.add_argument(
        "--game", type=str, default="all",
        help="Game to play (name from registry, or 'all')"
    )
    parser.add_argument(
        "--iterations", type=int, default=None,
        help="Override iteration count (skips LOW/MED/HIGH sweep)"
    )
    parser.add_argument(
        "--num-games", type=int, default=10,
        help="Number of games to play per configuration (default: 10)"
    )
    parser.add_argument(
        "--output-csv", type=str, default=None,
        help="Path to save CSV results"
    )
    parser.add_argument(
        "--nn", action="store_true",
        help="Use NN evaluation (CrossbarEvaluator) instead of random rollouts"
    )
    parser.add_argument(
        "--weights-source", type=str, default="auto",
        choices=["auto", "selfplay", "coach"],
        help="Weight source for NN evaluation (default: auto)"
    )
    args = parser.parse_args()

    # Stage 1: select the games in this experiment.
    if args.game.lower() == "all":
        games = list(GAME_REGISTRY.items())
    else:
        key = args.game.lower().replace(" ", "_")
        if key not in GAME_REGISTRY:
            print(f"Error: Unknown game '{args.game}'.")
            print(f"Available games: {', '.join(GAME_REGISTRY.keys())}")
            sys.exit(1)
        games = [(key, GAME_REGISTRY[key])]

    # Stage 2: load one crossbar evaluator per game when requested.
    evaluators = {}
    if args.nn:
        from generalizability.evaluation.crossbar_evaluator import make_evaluator
        for game_name, _game in games:
            try:
                evaluators[game_name] = make_evaluator(
                    game_name, weights_source=args.weights_source
                )
            except FileNotFoundError as e:
                print(f"  [WARNING] {e}")

    # Stage 3: choose the MCTS iteration sweep.
    if args.iterations is not None:
        levels = [("CUSTOM", args.iterations)]
    else:
        levels = [(name, iters) for name, iters in DEMO_PRESETS.items()]

    # Stage 4: choose random-rollout and crossbar-guided modes.
    modes = ["random"]
    if args.nn:
        modes.append("nn")

    experiment_results = []
    total_start = time.time()

    # Stage 5: run every game, strength, and evaluation mode.
    for game_name, game in games:
        for strength_name, iters in levels:
            for mode in modes:
                eval_fn = evaluators.get(game_name) if mode == "nn" else None
                if mode == "nn" and eval_fn is None:
                    continue  # skip NN mode if weights not found
                label = f"{strength_name}/{mode}"
                print(f"  Playing {game.name} @ {label} ({iters} iter) "
                      f"x {args.num_games} games ...", end=" ", flush=True)
                t0 = time.time()
                stats = play_games(game, iters, args.num_games, eval_fn=eval_fn)
                stats["strength"] = strength_name
                stats["mode"] = mode
                elapsed = time.time() - t0
                print(f"done ({elapsed:.1f}s)")
                experiment_results.append(stats)

    total_elapsed = time.time() - total_start
    print_results_table(experiment_results)
    print(f"\nTotal elapsed time: {total_elapsed:.1f}s")

    if args.output_csv:
        save_results_csv(experiment_results, args.output_csv)


if __name__ == "__main__":
    main()
