#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Tournament: 24 Games (4 players × 6 matchups × 4 games each)

Players:
1. Pachi (strong baseline, ~1900 ELO on 19x19)
2. MCTS-NN-50% (crossbar at 50% accuracy)
3. MCTS-NN-65% (crossbar at 65% accuracy)
4. MCTS-NN-78% (crossbar at 78% accuracy - best model)

Run with: python3 run_tournament_24games.py
"""

import numpy as np
import subprocess
import sys
import os
import json
import time
from datetime import datetime
from tqdm import tqdm


class NumpyEncoder(json.JSONEncoder):
    """Handle numpy types for JSON serialization."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

sys.path.insert(0, os.path.dirname(__file__))

from tournament.engines.mcts_player import SimplifiedMCTSPlayer
from tournament.engines.go_rules import GoRules


# =============================================================================
# CONFIGURATION
# =============================================================================

BOARD_SIZE = 9
GAMES_PER_MATCHUP = 4  # 6 matchups × 4 = 24 games total
ITERATIONS_PER_MOVE = 100  # Reduced from 200 for faster games
MAX_MOVES_PER_GAME = 81  # 9x9 board

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
WEIGHTS_DIR = os.path.join(_REPO_ROOT, 'data', 'pachi_training_data', 'weights_9x9_7k_v2')
PACHI_PATH = os.path.join(_REPO_ROOT, 'tools', 'pachi', 'pachi')

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'tournament_24games')


# =============================================================================
# PACHI PLAYER
# =============================================================================

class PachiPlayer:
    """Pachi GTP player."""

    def __init__(self, board_size: int = 9):
        self.name = "Pachi"
        self.board_size = board_size
        self.accuracy = None  # N/A for Pachi

        self.process = subprocess.Popen(
            [PACHI_PATH, "threads=1", "max_tree_size=256"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
            bufsize=1
        )

        self._cmd(f"boardsize {board_size}")
        self._cmd("clear_board")
        self._cmd("komi 6.5")

    def _cmd(self, command: str) -> str:
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

        response_text = ""
        while True:
            line = self.process.stdout.readline()
            if line == "\n" or line == "":
                break
            if line.startswith("="):
                response_text = line[1:].strip()
            elif line.startswith("?"):
                break
        return response_text

    def sync_board(self, board: np.ndarray):
        """Sync board state with Pachi."""
        self._cmd("clear_board")

        for row in range(self.board_size):
            for col in range(self.board_size):
                if board[row, col] != 0:
                    col_letter = "ABCDEFGHJKLMNOPQRST"[col]
                    row_num = self.board_size - row
                    color = "black" if board[row, col] == 1 else "white"
                    self._cmd(f"play {color} {col_letter}{row_num}")

    def select_move(self, board: np.ndarray, player: int):
        """Get move from Pachi."""
        self.sync_board(board)

        color = "black" if player == 1 else "white"
        response = self._cmd(f"genmove {color}")

        if not response or response.upper() in ["PASS", "RESIGN"]:
            return None

        try:
            col = "ABCDEFGHJKLMNOPQRST".index(response[0].upper())
            row = self.board_size - int(response[1:])
            return (row, col)
        except:
            return None

    def close(self):
        try:
            self._cmd("quit")
            self.process.terminate()
        except:
            pass


# =============================================================================
# NN PLAYER WRAPPER
# =============================================================================

class NNPlayer:
    """Wrapper for MCTS-NN player."""

    def __init__(self, name: str, weights_file: str, board_size: int = 9):
        self.name = name
        self.board_size = board_size
        self.weights_file = weights_file

        self.mcts = SimplifiedMCTSPlayer(
            board_size=board_size,
            weights_file=weights_file,
            iterations=ITERATIONS_PER_MOVE,
            player_id=1
        )
        self.accuracy = self.mcts.accuracy
        self.go_rules = GoRules(board_size)

    def select_move(self, board: np.ndarray, player: int):
        """Select move using MCTS with crossbar NN."""
        self.mcts.player_id = player
        move = self.mcts.select_move(board)
        if move == (-1, -1):
            return None
        return move


# =============================================================================
# GAME PLAY
# =============================================================================

def play_game(black_player, white_player, game_id: int) -> dict:
    """Play a single game and return results."""
    board = np.zeros((BOARD_SIZE, BOARD_SIZE), dtype=int)
    go_rules = GoRules(BOARD_SIZE)

    current_player = 1  # Black first
    moves_played = 0
    consecutive_passes = 0
    move_history = []

    # Alternate players until the move limit or two consecutive passes.
    for move_number in range(MAX_MOVES_PER_GAME):
        active_player = black_player if current_player == 1 else white_player

        try:
            move = active_player.select_move(board.copy(), current_player)
        except Exception as e:
            move = None

        if move is None:
            consecutive_passes += 1
            move_history.append({"player": current_player, "move": "pass"})
            if consecutive_passes >= 2:
                break
        else:
            consecutive_passes = 0
            row, col = move

            if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE and board[row, col] == 0:
                legal, captured = go_rules.apply_move(board, row, col, current_player)
                if legal:
                    moves_played += 1
                    move_history.append({
                        "player": current_player,
                        "move": f"{row},{col}",
                        "captured": captured
                    })

        current_player = -current_player

    # Count occupied intersections first.
    black_area = np.sum(board == 1)
    white_area = np.sum(board == -1)

    # Add each empty point whose occupied neighbors have one color.
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row, col] == 0:
                neighbor_colors = []
                for row_offset, col_offset in [(-1,0), (1,0), (0,-1), (0,1)]:
                    neighbor_row = row + row_offset
                    neighbor_col = col + col_offset
                    if 0 <= neighbor_row < BOARD_SIZE and 0 <= neighbor_col < BOARD_SIZE:
                        if board[neighbor_row, neighbor_col] != 0:
                            neighbor_colors.append(board[neighbor_row, neighbor_col])

                if neighbor_colors and all(color == 1 for color in neighbor_colors):
                    black_area += 1
                elif neighbor_colors and all(color == -1 for color in neighbor_colors):
                    white_area += 1

    komi = 6.5
    black_score = black_area
    white_score = white_area + komi

    if black_score > white_score:
        winner = "Black"
        winner_name = black_player.name
    elif white_score > black_score:
        winner = "White"
        winner_name = white_player.name
    else:
        winner = "Draw"
        winner_name = None

    return {
        "game_id": game_id,
        "black_player": black_player.name,
        "white_player": white_player.name,
        "black_accuracy": getattr(black_player, 'accuracy', None),
        "white_accuracy": getattr(white_player, 'accuracy', None),
        "winner": winner,
        "winner_name": winner_name,
        "black_score": black_score,
        "white_score": white_score,
        "moves_played": moves_played,
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# ELO CALCULATION
# =============================================================================

def calculate_elo(results: list, players: list, k_factor: int = 32) -> dict:
    """Calculate ELO ratings from game results."""
    ratings = {player.name: 1500.0 for player in players}
    history = {player.name: [(0, 1500.0)] for player in players}

    game_number = 0
    for result in results:
        game_number += 1
        black_name = result["black_player"]
        white_name = result["white_player"]

        # E_black = 1 / (1 + 10^((R_white - R_black) / 400)).
        black_rating = ratings[black_name]
        white_rating = ratings[white_name]

        expected_black = 1.0 / (1.0 + 10**((white_rating - black_rating) / 400))
        expected_white = 1.0 - expected_black

        # Convert the game result into the actual Elo scores.
        if result["winner"] == "Black":
            actual_black, actual_white = 1.0, 0.0
        elif result["winner"] == "White":
            actual_black, actual_white = 0.0, 1.0
        else:
            actual_black, actual_white = 0.5, 0.5

        # R_new = R_old + K(S - E).
        ratings[black_name] += k_factor * (actual_black - expected_black)
        ratings[white_name] += k_factor * (actual_white - expected_white)

        history[black_name].append((game_number, ratings[black_name]))
        history[white_name].append((game_number, ratings[white_name]))

    # Summarize each player's complete tournament record.
    stats = {}
    for name in ratings:
        games = [
            result for result in results
            if result["black_player"] == name or result["white_player"] == name
        ]
        wins = len([result for result in games if result["winner_name"] == name])
        losses = len([
            result for result in games
            if result["winner_name"] is not None and result["winner_name"] != name
        ])
        draws = len([result for result in games if result["winner"] == "Draw"])

        stats[name] = {
            "rating": ratings[name],
            "games": len(games),
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": wins / len(games) if games else 0,
            "history": history[name]
        }

    return stats


# =============================================================================
# MAIN TOURNAMENT
# =============================================================================

def main():
    print("=" * 70)
    print("TOURNAMENT: 24 GAMES")
    print("=" * 70)
    print(f"Board Size: {BOARD_SIZE}x{BOARD_SIZE}")
    print(f"Games per matchup: {GAMES_PER_MATCHUP}")
    print(f"MCTS iterations: {ITERATIONS_PER_MOVE}")
    print()

    # Prepare the output directory.
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Initialize Pachi and the three crossbar checkpoints.
    print("Initializing players...")
    print("-" * 40)

    players = []

    print("Loading Pachi...")
    pachi = PachiPlayer(BOARD_SIZE)
    players.append(pachi)
    print(f"  {pachi.name}: Ready")

    nn_configurations = [
        ("MCTS-NN-50%", "model_at_50.01percent.pkl"),
        ("MCTS-NN-65%", "model_at_65.04percent.pkl"),
        ("MCTS-NN-78%", "best_improved_model.pkl"),
    ]

    for name, weights_file in nn_configurations:
        print(f"Loading {name}...")
        weights_path = os.path.join(WEIGHTS_DIR, weights_file)
        player = NNPlayer(name, weights_path, BOARD_SIZE)
        players.append(player)
        print(f"  {player.name}: {player.accuracy:.1%} accuracy")

    print()
    print(f"Total players: {len(players)}")

    # Build every player pair with alternating colors.
    matchups = []
    for player1_index in range(len(players)):
        for player2_index in range(player1_index + 1, len(players)):
            for game_index in range(GAMES_PER_MATCHUP):
                if game_index % 2 == 0:
                    matchups.append((players[player1_index], players[player2_index]))
                else:
                    matchups.append((players[player2_index], players[player1_index]))

    total_games = len(matchups)
    print(f"Total games to play: {total_games}")
    print()

    # Play the full tournament in matchup order.
    print("=" * 70)
    print("RUNNING TOURNAMENT")
    print("=" * 70)

    results = []

    with tqdm(total=total_games, desc="Tournament", unit="game") as progress_bar:
        for game_id, (black_player, white_player) in enumerate(matchups, 1):
            progress_bar.set_postfix_str(
                f"{black_player.name}(B) vs {white_player.name}(W)"
            )

            result = play_game(black_player, white_player, game_id)
            results.append(result)

            winner_str = f"{result['winner']} wins" if result['winner'] != "Draw" else "Draw"
            progress_bar.set_postfix_str(
                f"{black_player.name} vs {white_player.name}: {winner_str}"
            )
            progress_bar.update(1)

    # Close Pachi
    pachi.close()

    # Calculate and print the final Elo table.
    print()
    print("=" * 70)
    print("CALCULATING ELO RATINGS")
    print("=" * 70)

    elo_stats = calculate_elo(results, players)

    rankings = sorted(
        elo_stats.items(),
        key=lambda player_stats: player_stats[1]["rating"],
        reverse=True
    )

    print()
    print(f"{'Rank':<6}{'Player':<20}{'ELO':<10}{'W/L/D':<12}{'Win Rate':<10}")
    print("-" * 58)

    for rank, (name, stats) in enumerate(rankings, 1):
        wld = f"{stats['wins']}/{stats['losses']}/{stats['draws']}"
        print(f"{rank:<6}{name:<20}{stats['rating']:<10.0f}{wld:<12}{stats['win_rate']:<10.1%}")

    # Save the complete configuration, game records, and rankings.
    output = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "board_size": BOARD_SIZE,
            "games_per_matchup": GAMES_PER_MATCHUP,
            "iterations_per_move": ITERATIONS_PER_MOVE,
            "total_games": total_games
        },
        "players": [
            {"name": player.name, "accuracy": getattr(player, 'accuracy', None)}
            for player in players
        ],
        "results": results,
        "elo_rankings": [
            {
                "rank": rank,
                "name": name,
                "rating": stats["rating"],
                "games": stats["games"],
                "wins": stats["wins"],
                "losses": stats["losses"],
                "draws": stats["draws"],
                "win_rate": stats["win_rate"]
            }
            for rank, (name, stats) in enumerate(rankings, 1)
        ]
    }

    output_file = os.path.join(OUTPUT_DIR, "tournament_results.json")
    with open(output_file, 'w') as output_handle:
        json.dump(output, output_handle, indent=2, cls=NumpyEncoder)

    print()
    print(f"Results saved to: {output_file}")
    print()
    print("=" * 70)
    print("TOURNAMENT COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
