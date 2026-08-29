#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Go Case Study - Tournament Runner.

Main entry point for running round-robin tournaments between:
  - IMC-MCTS-8bit (behavioral sim with 8-bit quantized weights)
  - IMC-MCTS-4bit (behavioral sim with 4-bit quantized weights)
  - IMC-MCTS-2bit (behavioral sim with 2-bit quantized weights)
  - MCTS-Rollout  (random rollout baseline, same iterations)
  - External engines: GnuGo-L1, GnuGo-L10, Pachi-10p, Pachi-100p, KataGo-100v

Configuration: 9x9 Go, 6.5 komi, 2000 MCTS iterations, 50 games/matchup
"""

import argparse
import json
import os
import sys
import time
import random
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.go_engine import GoEngine
from engine.behavioral_sim import BehavioralSimulator
from engine.mcts_engine import MCTSEngine
from eval.tournament import GameController, GameRecord
from engine.gtp_player import GTPPlayer, create_gtp_player
from eval.elo import ELOCalculator
from eval.sgg_metric import compute_sgg, print_sgg_table
from tools.quantize import quantize_all
from paths import GNUGO_BIN, PACHI_BIN


# ======================================================================
# Player Wrappers
# ======================================================================

class MCTSNNPlayer:
    """MCTS player using behavioral RTL simulator for evaluation."""

    def __init__(self, go_engine: GoEngine, weights_file: str,
                 iterations: int = 2000, noise_std: float = 0.0,
                 adc_bits: int = 0):
        simulator = BehavioralSimulator(
            weights_file,
            go_engine.board_size,
            adc_bits=adc_bits,
            conductance_noise_std=noise_std
        )
        self.mcts = MCTSEngine(
            go_engine,
            simulator=simulator,
            iterations=iterations
        )
        self.go = go_engine

    def select_move(self, board: np.ndarray):
        state = self.go.initial_state()
        state['board'] = board.copy()
        # Infer current player from stone count
        black_stones = np.sum(board == 1)
        white_stones = np.sum(board == -1)
        state['current_player'] = 1 if black_stones <= white_stones else -1
        return self.mcts.search(state)


class MCTSRolloutPlayer:
    """MCTS player with random rollout (no NN)."""

    def __init__(self, go_engine: GoEngine, iterations: int = 2000):
        self.mcts = MCTSEngine(go_engine, simulator=None, iterations=iterations)
        self.go = go_engine

    def select_move(self, board: np.ndarray):
        state = self.go.initial_state()
        state['board'] = board.copy()
        black_stones = np.sum(board == 1)
        white_stones = np.sum(board == -1)
        state['current_player'] = 1 if black_stones <= white_stones else -1
        return self.mcts.search(state)


# ======================================================================
# Tournament Configuration
# ======================================================================

def load_config(config_path: str) -> dict:
    """Load tournament configuration from JSON."""
    with open(config_path, 'r') as config_handle:
        return json.load(config_handle)


def get_default_config() -> dict:
    """Default tournament configuration."""
    return {
        "board_size": 9,
        "komi": 6.5,
        "mcts_iterations": 2000,
        "games_per_matchup": 50,
        "max_moves_per_game": 162,
        "players": {
            "IMC-MCTS-8bit": {
                "type": "mcts_nn",
                "weights": "weights/8bit/model_8bit.pkl",
                "noise_std": 0.0,
                "adc_bits": 0,
            },
            "IMC-MCTS-4bit": {
                "type": "mcts_nn",
                "weights": "weights/4bit/model_4bit.pkl",
                "noise_std": 0.0,
                "adc_bits": 0,
            },
            "IMC-MCTS-2bit": {
                "type": "mcts_nn",
                "weights": "weights/2bit/model_2bit.pkl",
                "noise_std": 0.0,
                "adc_bits": 0,
            },
            "MCTS-Rollout": {
                "type": "mcts_rollout",
            },
        },
        "external_players": {
            "GnuGo-L1": {
                "engine": "gnugo",
                "gnugo_path": GNUGO_BIN,
                "level": 1,
            },
            "GnuGo-L10": {
                "engine": "gnugo",
                "gnugo_path": GNUGO_BIN,
                "level": 10,
            },
            "Pachi-5s": {
                "engine": "pachi",
                "pachi_path": PACHI_BIN,
                "time_per_move": 5,
            },
            "Pachi-1s": {
                "engine": "pachi",
                "pachi_path": PACHI_BIN,
                "time_per_move": 1,
            },
        },
    }


# ======================================================================
# Tournament Runner
# ======================================================================

class TournamentRunner:
    """Run round-robin tournament between all configurations."""

    def __init__(self, config: dict, output_dir: str = "results",
                 include_external: bool = False, verbose: bool = True):
        self.config = config
        self.output_dir = output_dir
        self.include_external = include_external
        self.verbose = verbose

        self.board_size = config.get("board_size", 9)
        self.go = GoEngine(self.board_size, config.get("komi", 6.5))
        self.iterations = config.get("mcts_iterations", 2000)
        self.games_per_matchup = config.get("games_per_matchup", 50)
        self.max_moves = config.get("max_moves_per_game", 162)

        self.elo = ELOCalculator(k_factor=32, initial_rating=1500)
        self.game_controller = GameController(self.go, self.max_moves, verbose=False)

        os.makedirs(output_dir, exist_ok=True)

    def _create_player(self, name: str, player_config: dict, player_id: int):
        """Create a player from config."""
        player_type = player_config.get("type", player_config.get("engine", ""))

        if player_type == "mcts_nn":
            return MCTSNNPlayer(
                self.go,
                player_config["weights"],
                iterations=self.iterations,
                noise_std=player_config.get("noise_std", 0.0),
                adc_bits=player_config.get("adc_bits", 0),
            )
        elif player_type == "mcts_rollout":
            return MCTSRolloutPlayer(self.go, iterations=self.iterations)
        elif player_type in ("gnugo", "pachi", "katago"):
            player_arguments = {
                key: value
                for key, value in player_config.items()
                if key != "engine"
            }
            return create_gtp_player(
                player_type,
                self.board_size,
                player_id,
                **player_arguments
            )
        else:
            raise ValueError(f"Unknown player type: {player_type}")

    def run(self):
        """Run the full round-robin tournament."""
        # Build the complete tournament field.
        players = dict(self.config.get("players", {}))
        if self.include_external:
            players.update(self.config.get("external_players", {}))

        player_names = list(players.keys())
        num_players = len(player_names)
        num_matchups = num_players * (num_players - 1) // 2
        total_games = num_matchups * self.games_per_matchup

        print("=" * 70)
        print("GO CASE STUDY - IMC-MCTS TOURNAMENT")
        print("=" * 70)
        print(f"Board: {self.board_size}x{self.board_size}, Komi: {self.go.komi}")
        print(f"MCTS iterations: {self.iterations}")
        print(f"Games per matchup: {self.games_per_matchup}")
        print(f"Players: {', '.join(player_names)}")
        print(f"Total matchups: {num_matchups}, Total games: {total_games}")
        print()

        for name in player_names:
            self.elo.add_player(name)

        all_records: List[GameRecord] = []
        matchup_results: Dict[str, dict] = {}
        tournament_start_time = time.time()
        games_played = 0

        # Run every player pair with alternating colors.
        for player_a_index in range(num_players):
            for player_b_index in range(player_a_index + 1, num_players):
                name_a = player_names[player_a_index]
                name_b = player_names[player_b_index]
                matchup_key = f"{name_a}_vs_{name_b}"
                matchup_results[matchup_key] = {
                    'a_wins': 0,
                    'b_wins': 0,
                    'draws': 0
                }

                print(f"\nMatchup: {name_a} vs {name_b}")

                for game_index in range(self.games_per_matchup):
                    if game_index % 2 == 0:
                        black_name, white_name = name_a, name_b
                        black_config, white_config = players[name_a], players[name_b]
                    else:
                        black_name, white_name = name_b, name_a
                        black_config, white_config = players[name_b], players[name_a]

                    # Create fresh player state for each game.
                    try:
                        black_player = self._create_player(
                            black_name,
                            black_config,
                            1
                        )
                        white_player = self._create_player(
                            white_name,
                            white_config,
                            -1
                        )
                    except (RuntimeError, FileNotFoundError) as e:
                        print(f"  Skipping: {e}")
                        continue

                    try:
                        record = self.game_controller.play_game(
                            black_player,
                            white_player,
                            black_name,
                            white_name,
                            game_id=games_played + 1
                        )
                    except Exception as e:
                        print(f"  Game error: {e}")
                        # Clean up GTP players
                        for player in [black_player, white_player]:
                            if hasattr(player, 'cleanup'):
                                player.cleanup()
                        continue
                    finally:
                        for player in [black_player, white_player]:
                            if hasattr(player, 'cleanup'):
                                player.cleanup()

                    all_records.append(record)
                    games_played += 1

                    # Update Elo in game order.
                    self.elo.update_ratings(
                        black_name,
                        white_name,
                        record.result_black
                    )

                    # Convert the color result back to the fixed matchup names.
                    if record.winner == "Black":
                        winner_name = black_name
                    elif record.winner == "White":
                        winner_name = white_name
                    else:
                        winner_name = None

                    if winner_name == name_a:
                        matchup_results[matchup_key]['a_wins'] += 1
                    elif winner_name == name_b:
                        matchup_results[matchup_key]['b_wins'] += 1
                    else:
                        matchup_results[matchup_key]['draws'] += 1

                    if self.verbose and (games_played % 10 == 0):
                        elapsed = time.time() - tournament_start_time
                        estimated_time_remaining = (
                            elapsed / games_played * (total_games - games_played)
                        )
                        print(f"  Progress: {games_played}/{total_games} "
                              f"({100*games_played/total_games:.0f}%) "
                              f"ETA: {estimated_time_remaining/60:.1f}min")

                matchup_record = matchup_results[matchup_key]
                print(f"  {name_a}: {matchup_record['a_wins']}W, {name_b}: {matchup_record['b_wins']}W, "
                      f"Draws: {matchup_record['draws']}")

        elapsed_total = time.time() - tournament_start_time

        # Print results
        print("\n" + "=" * 70)
        print("FINAL ELO RANKINGS")
        print("=" * 70)
        self.elo.print_rankings()

        # Compute SGG for NN players vs rollout
        print("\n" + "=" * 70)
        print("SEARCH GUIDANCE GAIN (SGG)")
        print("=" * 70)

        sgg_data = {}
        rollout_name = "MCTS-Rollout"
        for name in player_names:
            if name == rollout_name:
                continue
            # Find H2H win rate vs rollout
            mkey1 = f"{name}_vs_{rollout_name}"
            mkey2 = f"{rollout_name}_vs_{name}"
            if mkey1 in matchup_results:
                matchup_record = matchup_results[mkey1]
                matchup_games = (
                    matchup_record['a_wins']
                    + matchup_record['b_wins']
                    + matchup_record['draws']
                )
                if matchup_games > 0:
                    win_rate = (
                        matchup_record['a_wins']
                        + 0.5 * matchup_record['draws']
                    ) / matchup_games
                    sgg_data[name] = win_rate
            elif mkey2 in matchup_results:
                matchup_record = matchup_results[mkey2]
                matchup_games = (
                    matchup_record['a_wins']
                    + matchup_record['b_wins']
                    + matchup_record['draws']
                )
                if matchup_games > 0:
                    win_rate = (
                        matchup_record['b_wins']
                        + 0.5 * matchup_record['draws']
                    ) / matchup_games
                    sgg_data[name] = win_rate

        if sgg_data:
            sgg_results = {}
            for name, win_rate in sgg_data.items():
                sgg_results[name] = compute_sgg(
                    win_rate,
                    0.50,
                    self.iterations
                )
            print_sgg_table(sgg_results)

        # Save results
        results = {
            'timestamp': datetime.now().isoformat(),
            'config': self.config,
            'elapsed_seconds': elapsed_total,
            'total_games': games_played,
            'elo_ratings': self.elo.export_results(),
            'matchup_results': matchup_results,
            'games': [record.to_dict() for record in all_records],
        }
        if sgg_data:
            results['sgg'] = {
                name: compute_sgg(win_rate, 0.50, self.iterations)
                for name, win_rate in sgg_data.items()
            }

        results_path = os.path.join(self.output_dir, "tournament_results.json")
        with open(results_path, 'w') as results_handle:
            json.dump(results, results_handle, indent=2)

        print(f"\nResults saved to: {results_path}")
        print(f"Total time: {elapsed_total/60:.1f} minutes")

        return results


def main():
    parser = argparse.ArgumentParser(description="Go Case Study Tournament")
    parser.add_argument('--config', type=str, default=None,
                        help='Config JSON file (default: built-in)')
    parser.add_argument('--output', type=str, default='results',
                        help='Output directory')
    parser.add_argument('--games', type=int, default=None,
                        help='Override games per matchup')
    parser.add_argument('--iterations', type=int, default=None,
                        help='Override MCTS iterations')
    parser.add_argument('--external', action='store_true',
                        help='Include external engines (KataGo, Pachi, GnuGo)')
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--quantize', type=str, default=None,
                        help='Quantize a full-precision model before running')
    args = parser.parse_args()

    # Load or create config
    if args.config:
        config = load_config(args.config)
    else:
        config = get_default_config()

    # Apply overrides
    if args.games:
        config['games_per_matchup'] = args.games
    if args.iterations:
        config['mcts_iterations'] = args.iterations

    # Optional: quantize weights
    if args.quantize:
        print(f"Quantizing weights from {args.quantize}...")
        quantize_all(args.quantize, output_dir="weights")
        # Copy full precision
        import shutil
        os.makedirs("weights/full_precision", exist_ok=True)
        shutil.copy2(args.quantize, "weights/full_precision/best_model.pkl")

    # Run tournament
    runner = TournamentRunner(
        config, output_dir=args.output,
        include_external=args.external,
        verbose=not args.quiet,
    )
    runner.run()


if __name__ == "__main__":
    main()
