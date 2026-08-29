#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Tournament Runner - Crossbar Accuracy vs ELO Study

Runs a complete round-robin tournament between 4 Accelerator configurations
with different crossbar NN accuracy levels (82%, 75%, 65%, 55%).

Each matchup is played N times with colors swapped for fairness.
ELO ratings are calculated and tracked throughout the tournament.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import List, Dict
import time

from tournament.engines.config_loader import get_tournament_configs
from tournament.engines.game_controller import GameController, GameRecord
from tournament.engines.elo_calculator import ELOCalculator


class TournamentRunner:
    """
    Manages a complete round-robin tournament.
    """

    def __init__(
        self,
        board_size: int = 9,
        games_per_matchup: int = 50,
        iterations_per_move: int = 5000,
        max_moves: int = 60,
        output_dir: str = "tournament_results",
        verbose: bool = True,
        num_players: int = 4
    ):
        """
        Initialize tournament runner.

        Args:
            board_size: Board size (default: 9 for 9x9)
            games_per_matchup: Number of games per matchup (default: 50)
            iterations_per_move: MCTS iterations per move (default: 5000)
            max_moves: Maximum moves per game (default: 60)
            output_dir: Directory for results (default: tournament_results)
            verbose: Print progress (default: True)
            num_players: Number of players (default: 4, can use 10)
        """
        self.board_size = board_size
        self.games_per_matchup = games_per_matchup
        self.iterations_per_move = iterations_per_move
        self.max_moves = max_moves
        self.output_dir = output_dir
        self.verbose = verbose
        self.num_players = num_players

        # Prepare one directory for checkpoints and final results.
        os.makedirs(output_dir, exist_ok=True)

        # Load the requested crossbar tiers and baseline modes.
        self.configs = get_tournament_configs(board_size, num_players=num_players)

        # Register every tournament player at the same starting ELO.
        self.elo = ELOCalculator(k_factor=32, initial_rating=1500)
        for config in self.configs:
            self.elo.add_player(config.name)

        # Use one controller with a fixed search and move budget.
        self.controller = GameController(
            board_size=board_size,
            iterations_per_move=iterations_per_move,
            max_moves=max_moves,
            verbose=False  # Silence individual game output
        )

        # Keep complete game records and per-matchup aggregates in memory.
        self.all_games: List[GameRecord] = []
        self.matchup_results: Dict[tuple, dict] = {}

        # Initialize progress accounting before the first matchup.
        self.start_time = None
        self.total_games = 0

    def run_tournament(self):
        """
        Run complete round-robin tournament.

        Each pair of configurations plays games_per_matchup games,
        with colors swapped for fairness (half as black, half as white).
        """
        print("=" * 80)
        print("CROSSBAR ACCURACY vs ELO TOURNAMENT")
        print("=" * 80)
        print()
        print(f"Board size: {self.board_size}x{self.board_size}")
        print(f"Games per matchup: {self.games_per_matchup}")
        print(f"Iterations per move: {self.iterations_per_move}")
        print(f"Max moves per game: {self.max_moves}")
        print()
        print("Configurations:")
        for config_index, config in enumerate(self.configs):
            print(f"  {config_index+1}. {config.name}: {config.accuracy:.2%}")
        print()

        # Calculate the complete upper-triangle round-robin schedule.
        num_matchups = len(self.configs) * (len(self.configs) - 1) // 2
        self.total_games = num_matchups * self.games_per_matchup

        print(f"Total matchups: {num_matchups}")
        print(f"Total games: {self.total_games}")
        print()
        print("=" * 80)
        print()

        self.start_time = time.time()
        games_played = 0

        # Run each unordered player pair exactly once as a matchup.
        for config1_index, config1 in enumerate(self.configs):
            for config2_index, config2 in enumerate(self.configs):
                if config1_index >= config2_index:  # Skip diagonal and lower triangle
                    continue

                matchup_key = (config1.name, config2.name)
                self.matchup_results[matchup_key] = {
                    'config1_wins': 0,
                    'config2_wins': 0,
                    'draws': 0,
                    'games': []
                }

                print(f"\n{'='*80}")
                print(f"Matchup: {config1.name} vs {config2.name}")
                print(f"{'='*80}")

                # Alternate colors across the fixed games-per-matchup budget.
                for game_num in range(self.games_per_matchup):
                    # Config 1 is Black on even games and White on odd games.
                    if game_num % 2 == 0:
                        black_config = config1
                        white_config = config2
                    else:
                        black_config = config2
                        white_config = config1

                    game_id = games_played + 1

                    if self.verbose:
                        print(f"\nGame {game_num+1}/{self.games_per_matchup} "
                              f"(#{game_id}/{self.total_games}): "
                              f"{black_config.name} (B) vs {white_config.name} (W)")

                    # Retry only Pachi protocol failures, up to the existing limit.
                    max_retries = 3 if "pachi" in (black_config.player_type, white_config.player_type) else 1
                    for retry_index in range(max_retries):
                        try:
                            game_start_time = time.time()
                            record = self.controller.play_game(
                                black_config=black_config,
                                white_config=white_config,
                                game_id=game_id
                            )
                            elapsed = time.time() - game_start_time
                            break  # Success!
                        except RuntimeError as e:
                            if "Pachi error" in str(e) and retry_index < max_retries - 1:
                                if self.verbose:
                                    print(f"  Pachi error, retrying ({retry_index+1}/{max_retries-1})...")
                                continue
                            else:
                                raise  # Give up after max_retries or if not a Pachi error

                    if self.verbose:
                        print(f"  Result: {record.winner} wins (score: {record.final_score:.2f})")
                        print(f"  Time: {elapsed:.1f}s")

                    # Convert the color result to Black's ELO score.
                    if record.winner == "Black":
                        result_black = 1.0
                    elif record.winner == "White":
                        result_black = 0.0
                    else:  # Draw
                        result_black = 0.5

                    self.elo.update_ratings(
                        black_config.name,
                        white_config.name,
                        result_black
                    )

                    # Preserve the existing matchup winner accounting.
                    if record.winner == config1.name:
                        self.matchup_results[matchup_key]['config1_wins'] += 1
                    elif record.winner == config2.name:
                        self.matchup_results[matchup_key]['config2_wins'] += 1
                    else:  # Draw
                        self.matchup_results[matchup_key]['draws'] += 1

                    self.matchup_results[matchup_key]['games'].append(record.to_dict())
                    self.all_games.append(record)
                    games_played += 1

                    # Report timing and current ELO every ten games.
                    if games_played % 10 == 0:
                        elapsed_total = time.time() - self.start_time
                        avg_time_per_game = elapsed_total / games_played
                        remaining_games = self.total_games - games_played
                        eta = avg_time_per_game * remaining_games

                        print(f"\n--- Progress: {games_played}/{self.total_games} games "
                              f"({100*games_played/self.total_games:.1f}%) ---")
                        print(f"    Elapsed: {elapsed_total/3600:.2f}h")
                        print(f"    ETA: {eta/3600:.2f}h")
                        self._print_current_rankings()

                    # Persist a recovery checkpoint every 25 games.
                    if games_played % 25 == 0:
                        self._save_checkpoint(games_played)

                # Print the aggregate result for this player pair.
                results = self.matchup_results[matchup_key]
                print(f"\nMatchup Summary:")
                print(f"  {config1.name}: {results['config1_wins']} wins")
                print(f"  {config2.name}: {results['config2_wins']} wins")
                print(f"  Draws: {results['draws']}")

        # Finalize tournament timing, rankings, and result files.
        print()
        print("=" * 80)
        print("TOURNAMENT COMPLETE!")
        print("=" * 80)
        print()

        elapsed_total = time.time() - self.start_time
        print(f"Total time: {elapsed_total/3600:.2f} hours")
        print(f"Average time per game: {elapsed_total/self.total_games:.1f}s")
        print()

        self._print_final_results()
        self._save_results()

    def _print_current_rankings(self):
        """Print current ELO rankings."""
        print()
        rankings = self.elo.get_rankings()
        print("    Current ELO Rankings:")
        for rank, (player_id, rating, player) in enumerate(rankings, 1):
            print(f"      {rank}. {player_id:<30} Rating: {rating:.1f} "
                  f"(W/L/D: {player.wins}/{player.losses}/{player.draws})")
        print()

    def _print_final_results(self):
        """Print final tournament results."""
        print("FINAL ELO RANKINGS")
        print("=" * 80)
        self.elo.print_rankings()
        print()

        print("MATCHUP RESULTS")
        print("=" * 80)
        for (config1, config2), results in self.matchup_results.items():
            print(f"{config1} vs {config2}:")
            print(f"  {config1}: {results['config1_wins']} wins")
            print(f"  {config2}: {results['config2_wins']} wins")
            print(f"  Draws: {results['draws']}")
            win_rate = results['config1_wins'] / self.games_per_matchup * 100
            print(f"  {config1} win rate: {win_rate:.1f}%")
            print()

    def _save_checkpoint(self, games_played: int):
        """Save tournament checkpoint."""
        checkpoint_file = os.path.join(
            self.output_dir,
            f"checkpoint_{games_played}_games.json"
        )

        checkpoint_data = {
            'timestamp': datetime.now().isoformat(),
            'games_played': games_played,
            'total_games': self.total_games,
            'elo_ratings': self.elo.export_results(),
            'matchup_results': {
                f"{k[0]}_vs_{k[1]}": v
                for k, v in self.matchup_results.items()
            }
        }

        with open(checkpoint_file, 'w') as checkpoint_handle:
            json.dump(checkpoint_data, checkpoint_handle, indent=2)

        if self.verbose:
            print(f"    Checkpoint saved: {checkpoint_file}")

    def _save_results(self):
        """Save final tournament results."""
        # Save the complete tournament configuration, ratings, and games.
        results_file = os.path.join(self.output_dir, "tournament_results.json")

        results_data = {
            'timestamp': datetime.now().isoformat(),
            'configuration': {
                'board_size': self.board_size,
                'games_per_matchup': self.games_per_matchup,
                'iterations_per_move': self.iterations_per_move,
                'max_moves': self.max_moves,
                'total_games': self.total_games
            },
            'configurations': [
                {
                    'name': config.name,
                    'accuracy': config.accuracy,
                    'player_type': config.player_type,
                    'weights_file': os.path.basename(config.weights_file) if config.weights_file else None
                }
                for config in self.configs
            ],
            'elo_ratings': self.elo.export_results(),
            'matchup_results': {
                f"{k[0]}_vs_{k[1]}": {
                    'config1_wins': v['config1_wins'],
                    'config2_wins': v['config2_wins'],
                    'draws': v['draws'],
                    'games': v['games']
                }
                for k, v in self.matchup_results.items()
            },
            'all_games': [game.to_dict() for game in self.all_games]
        }

        with open(results_file, 'w') as results_handle:
            json.dump(results_data, results_handle, indent=2)

        print(f"Results saved to: {results_file}")

        # Save a compact ELO-only artifact for downstream plotting.
        elo_file = os.path.join(self.output_dir, "elo_ratings.json")
        with open(elo_file, 'w') as elo_handle:
            json.dump(self.elo.export_results(), elo_handle, indent=2)

        print(f"ELO ratings saved to: {elo_file}")


def main():
    """Run tournament from command line."""
    parser = argparse.ArgumentParser(
        description='Run Crossbar Accuracy vs ELO Tournament',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test (5 games per matchup, 500 iterations)
  python tournament_runner.py --games 5 --iterations 500

  # Full tournament (50 games per matchup, 5000 iterations)
  python tournament_runner.py --games 50 --iterations 5000

  # Overnight run with checkpoints
  python tournament_runner.py --games 100 --iterations 5000 --output results_100games
        """
    )

    parser.add_argument('--board-size', type=int, default=9,
                        help='Board size (default: 9 for 9x9)')
    parser.add_argument('--games', type=int, default=50,
                        help='Games per matchup (default: 50)')
    parser.add_argument('--iterations', type=int, default=5000,
                        help='MCTS iterations per move (default: 5000)')
    parser.add_argument('--max-moves', type=int, default=60,
                        help='Maximum moves per game (default: 60)')
    parser.add_argument('--players', type=str, default='4',
                        help='Number of players (default: 4, options: 4, 10, 7plus3)')
    parser.add_argument('--output', type=str, default='tournament_results',
                        help='Output directory (default: tournament_results)')
    parser.add_argument('--quiet', action='store_true',
                        help='Suppress verbose output')

    args = parser.parse_args()

    # Preserve numeric player counts while allowing named experiment modes.
    if args.players.isdigit():
        num_players = int(args.players)
    else:
        num_players = args.players  # Keep as string (e.g., "7plus3")

    # Build the requested tournament experiment.
    tournament = TournamentRunner(
        board_size=args.board_size,
        games_per_matchup=args.games,
        iterations_per_move=args.iterations,
        max_moves=args.max_moves,
        output_dir=args.output,
        verbose=not args.quiet,
        num_players=num_players
    )

    # Run the tournament and preserve partial results on interruption.
    try:
        tournament.run_tournament()
    except KeyboardInterrupt:
        print("\n\nTournament interrupted by user!")
        print("Saving current results...")
        tournament._save_results()
        sys.exit(1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
