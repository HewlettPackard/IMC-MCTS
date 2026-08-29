# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Tournament Game Controller.

Manages individual games between two players using full Go rules.
"""

import numpy as np
import os
import sys
from typing import Tuple, List, Optional
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.go_engine import GoEngine


@dataclass
class GameRecord:
    """Record of a completed game."""
    game_id: int
    black_name: str
    white_name: str
    winner: str          # "Black", "White", or "Draw"
    result_black: float  # 1.0, 0.5, or 0.0
    total_moves: int
    black_score: float
    white_score: float
    move_history: List[Tuple[int, int]]
    timestamp: str

    def to_dict(self) -> dict:
        return {
            'game_id': self.game_id,
            'black': self.black_name,
            'white': self.white_name,
            'winner': self.winner,
            'result_black': self.result_black,
            'total_moves': self.total_moves,
            'black_score': self.black_score,
            'white_score': self.white_score,
            'timestamp': self.timestamp,
        }


class GameController:
    """Play a game between two players using full Go rules."""

    def __init__(self, go_engine: GoEngine, max_moves: int = 162,
                 verbose: bool = False):
        self.go = go_engine
        self.max_moves = max_moves
        self.verbose = verbose

    def play_game(self, black_player, white_player,
                  black_name: str, white_name: str,
                  game_id: int = 0) -> GameRecord:
        """
        Play a complete game.

        Players must implement:
          - select_move(board: np.ndarray) -> (row, col)
          - update_with_move(move, player_id) [optional, for GTP engines]

        Args:
            black_player: Player object for Black (player_id=1)
            white_player: Player object for White (player_id=-1)
            black_name: Display name for Black
            white_name: Display name for White
            game_id: Game identifier

        Returns:
            GameRecord
        """
        state = self.go.initial_state()
        move_history = []
        players = {1: black_player, -1: white_player}
        names = {1: black_name, -1: white_name}

        while not self.go.is_terminal(state) and state['move_count'] < self.max_moves:
            current_player = state['current_player']
            active_player = players[current_player]

            # Ask the active player for a move on the current board.
            move = active_player.select_move(state['board'])

            # Convert out-of-range or illegal moves to a pass.
            if move != (-1, -1):
                row, col = move
                if not (0 <= row < self.go.board_size and 0 <= col < self.go.board_size):
                    move = (-1, -1)  # Invalid -> pass
                elif not self.go.is_legal(state, row, col, current_player):
                    if self.verbose:
                        print(f"  Illegal move {move} by {names[current_player]}, treating as pass")
                    move = (-1, -1)

            # Advance the shared Go state and save the move history.
            state = self.go.apply_move(state, move)
            move_history.append(move)

            # Keep an external opponent synchronized with the applied move.
            opponent = players[-current_player]
            if hasattr(opponent, 'update_with_move'):
                opponent.update_with_move(move, current_player)

            if self.verbose and state['move_count'] % 20 == 0:
                print(f"  Move {state['move_count']}: {names[current_player]} plays {move}")

        # Score the final board and convert it to Black's result.
        black_score, white_score = self.go.score_position(state['board'])

        if black_score > white_score:
            winner = "Black"
            result_black = 1.0
        elif white_score > black_score:
            winner = "White"
            result_black = 0.0
        else:
            winner = "Draw"
            result_black = 0.5

        if self.verbose:
            print(f"  Result: {winner} (B={black_score:.1f}, W={white_score:.1f})")

        return GameRecord(
            game_id=game_id,
            black_name=black_name,
            white_name=white_name,
            winner=winner,
            result_black=result_black,
            total_moves=state['move_count'],
            black_score=black_score,
            white_score=white_score,
            move_history=move_history,
            timestamp=datetime.now().isoformat(),
        )
