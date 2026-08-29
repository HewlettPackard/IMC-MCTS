#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Tournament using Hardware Functional Model.

Each player uses the ACTUAL hardware logic:
- Selection Unit (UCB1)
- Expansion Unit
- Rollout Unit (Crossbar NN with trained weights)
- Backprop Unit

This tests what the real hardware would do!
"""

import numpy as np
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulator'))

from core.architecture.hardware_functional_model import MCTSHardwareFunctional
from tournament.engines.go_rules import GoRules


class HardwareFunctionalPlayer:
    """Player using hardware functional model with trained crossbar NN."""

    def __init__(self, name: str, weights_file: str, board_size: int = 9,
                 iterations: int = 200):
        self.name = name
        self.board_size = board_size
        self.iterations = iterations
        self.weights_file = weights_file

        # Build the hardware MCTS state for this player.
        print(f"Initializing {name}...")
        self.mcts = MCTSHardwareFunctional(board_size, weights_file)
        self.go_rules = GoRules(board_size)

    def select_move(self, board: np.ndarray, player: int):
        """Select best move using hardware MCTS."""
        self.mcts.reset(board)

        # Set the root perspective before running the search.
        self.mcts.tree[self.mcts.root_id]['player'] = player

        # Run the requested number of hardware MCTS iterations.
        for _ in range(self.iterations):
            self.mcts.run_iteration()

        # Read the most visited child from the completed search tree.
        root_node = self.mcts.tree[self.mcts.root_id]
        if not root_node['children']:
            return None

        best_move = max(
            root_node['children'].keys(),
            key=lambda move: self.mcts.tree[root_node['children'][move]]['visits']
        )

        return best_move


class PachiPlayer:
    """Pachi external player for comparison."""

    def __init__(self, board_size: int = 9, pachi_path: str = None):
        self.name = "Pachi"
        self.board_size = board_size

        if pachi_path is None:
            pachi_path = os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'pachi', 'pachi')

        self.process = subprocess.Popen(
            [pachi_path, "threads=1", "max_tree_size=128"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
            bufsize=1
        )

        self._cmd(f"boardsize {board_size}")
        self._cmd("clear_board")
        self._cmd("komi 5.5")
        print(f"Initialized Pachi player")

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

    def sync_board(self, board: np.ndarray, last_move=None, last_player=None):
        """Sync board state with Pachi."""
        self._cmd("clear_board")

        # Rebuild the complete board through the GTP interface.
        for row in range(self.board_size):
            for col in range(self.board_size):
                if board[row, col] == 1:  # Black
                    col_letter = "ABCDEFGHJKLMNOPQRST"[col]
                    row_num = self.board_size - row
                    self._cmd(f"play black {col_letter}{row_num}")
                elif board[row, col] == -1:  # White
                    col_letter = "ABCDEFGHJKLMNOPQRST"[col]
                    row_num = self.board_size - row
                    self._cmd(f"play white {col_letter}{row_num}")

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


def play_game(black_player, white_player, board_size: int = 9, max_moves: int = 60):
    """Play a game between two players."""
    board = np.zeros((board_size, board_size), dtype=int)
    go_rules = GoRules(board_size)
    current_player = 1  # Black first

    moves_played = 0
    passes = 0

    for move_number in range(max_moves):
        active_player = black_player if current_player == 1 else white_player

        try:
            move = active_player.select_move(board.copy(), current_player)
        except Exception as e:
            print(f"  Error from {active_player.name}: {e}")
            move = None

        if move is None:
            passes += 1
            if passes >= 2:
                break
        else:
            passes = 0
            row, col = move
            if board[row, col] == 0:
                board[row, col] = current_player
                moves_played += 1

        current_player = -current_player

    # Score the final stones with 5.5 komi for White.
    black_score = np.sum(board == 1)
    white_score = np.sum(board == -1) + 5.5  # Komi

    if black_score > white_score:
        winner = "Black"
    elif white_score > black_score:
        winner = "White"
    else:
        winner = "Draw"

    return winner, black_score, white_score, moves_played


def run_tournament():
    """Run tournament with hardware functional model."""
    print("=" * 70)
    print("TOURNAMENT WITH HARDWARE FUNCTIONAL MODEL")
    print("=" * 70)
    print()
    print("Each IMC-MCTS player uses the REAL hardware logic:")
    print("  Selection → Expansion → Rollout (Crossbar NN) → Backprop")
    print()

    board_size = 9
    weights_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'pachi_training_data', 'weights_9x9_7k_v2')

    # Build the tournament field.
    players = [
        PachiPlayer(board_size),
        HardwareFunctionalPlayer(
            "HW-MCTS@78%",
            os.path.join(weights_dir, "best_improved_model.pkl"),
            board_size,
            iterations=200
        ),
        HardwareFunctionalPlayer(
            "HW-MCTS@70%",
            os.path.join(weights_dir, "model_at_70.01percent.pkl"),
            board_size,
            iterations=200
        ),
    ]

    print()
    print("=" * 70)
    print("Starting games...")
    print("=" * 70)

    results = {player.name: {"wins": 0, "losses": 0} for player in players}
    games_per_matchup = 2

    game_number = 0
    for player1_index, player1 in enumerate(players):
        for player2_index, player2 in enumerate(players):
            if player1_index >= player2_index:
                continue

            for game_index in range(games_per_matchup):
                game_number += 1

                if game_index % 2 == 0:
                    black_player, white_player = player1, player2
                else:
                    black_player, white_player = player2, player1

                print(
                    f"\nGame {game_number}: {black_player.name}(B) vs {white_player.name}(W)...",
                    end=" ",
                    flush=True
                )

                winner, black_score, white_score, moves_played = play_game(
                    black_player,
                    white_player,
                    board_size
                )
                print(
                    f"{winner} wins "
                    f"({black_score:.0f}-{white_score:.1f}, {moves_played} moves)"
                )

                if winner == "Black":
                    results[black_player.name]["wins"] += 1
                    results[white_player.name]["losses"] += 1
                elif winner == "White":
                    results[white_player.name]["wins"] += 1
                    results[black_player.name]["losses"] += 1

    # Close Pachi
    players[0].close()

    # Rank players by total wins.
    print()
    print("=" * 70)
    print("TOURNAMENT RESULTS")
    print("=" * 70)

    standings = sorted(
        results.items(),
        key=lambda player_result: player_result[1]["wins"],
        reverse=True
    )
    for rank, (name, record) in enumerate(standings, 1):
        total_games = record["wins"] + record["losses"]
        win_rate = record["wins"] / total_games * 100 if total_games > 0 else 0
        print(
            f"  {rank}. {name}: "
            f"{record['wins']}W-{record['losses']}L ({win_rate:.0f}%)"
        )

    print()
    print("=" * 70)


if __name__ == "__main__":
    run_tournament()
