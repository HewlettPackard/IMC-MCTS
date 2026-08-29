# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Game Controller for Tournament Play.

Manages full games between two MCTS players using the training heuristic
for evaluation.
"""

import numpy as np
from typing import Tuple, Optional, List
from dataclasses import dataclass
from datetime import datetime

from tournament.engines.heuristic_eval import HeuristicEvaluator
from tournament.engines.mcts_player import SimplifiedMCTSPlayer
from tournament.engines.random_player import RandomPlayer
from tournament.engines.greedy_player import GreedyPlayer
from tournament.engines.pachi_player import PachiPlayer
from tournament.engines.katago_player import KataGoPlayer
from tournament.engines.mcts_rollout_player import MCTSRolloutPlayer
from tournament.engines.config_loader import AcceleratorConfig
from tournament.engines.go_rules import GoRules


@dataclass
class GameRecord:
    """Record of a completed game."""

    game_id: int
    black_config: AcceleratorConfig
    white_config: AcceleratorConfig
    winner: str  # "Black", "White", or "Draw"
    outcome_value: float  # 1.0, 0.5, or 0.0
    total_moves: int
    final_score: float  # From heuristic evaluation
    score_details: dict  # Breakdown of material/territory/liberties
    timestamp: str
    move_history: List[Tuple[int, int]]  # List of (row, col) moves

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return {
            'game_id': self.game_id,
            'black_player': self.black_config.name,
            'black_accuracy': self.black_config.accuracy,
            'white_player': self.white_config.name,
            'white_accuracy': self.white_config.accuracy,
            'winner': self.winner,
            'outcome_value': self.outcome_value,
            'total_moves': self.total_moves,
            'final_score': self.final_score,
            'score_details': self.score_details,
            'timestamp': self.timestamp,
            'move_count': len(self.move_history)
        }


class GameController:
    """
    Controller for playing a game between two MCTS configurations.

    Uses the training heuristic (material + 0.5*territory + 0.1*liberties)
    to evaluate final positions.
    """

    def __init__(
        self,
        board_size: int = 9,
        iterations_per_move: int = 5000,
        max_moves: int = 60,  # Stop before board fills (9x9 = 81 positions)
        verbose: bool = True
    ):
        """
        Initialize game controller.

        Args:
            board_size: Size of board (default: 9 for 9x9)
            iterations_per_move: MCTS iterations per move (default: 5000)
            max_moves: Maximum moves before evaluating position (default: 60)
                       This prevents board from filling completely, leaving
                       territory and liberties to evaluate
            verbose: Print game progress
        """
        self.board_size = board_size
        self.iterations_per_move = iterations_per_move
        self.max_moves = max_moves
        self.verbose = verbose

        # Use the training evaluator and the tournament's Go legality model.
        self.evaluator = HeuristicEvaluator(board_size)
        self.go_rules = GoRules(board_size)

        # Keep the active board and move trace visible on the controller.
        self.board: Optional[np.ndarray] = None
        self.move_history: List[Tuple[int, int]] = []

    def _create_player(self, config: AcceleratorConfig, player_id: int):
        """
        Create a player based on configuration type.

        Args:
            config: Player configuration
            player_id: 1 for Black, -1 for White

        Returns:
            Player instance (SimplifiedMCTSPlayer, RandomPlayer, GreedyPlayer, or PachiPlayer)
        """
        if config.player_type == "mcts_nn":
            return SimplifiedMCTSPlayer(
                board_size=self.board_size,
                weights_file=config.weights_file,
                iterations=self.iterations_per_move,
                player_id=player_id,
                accuracy=config.accuracy
            )
        elif config.player_type == "random":
            return RandomPlayer(
                board_size=self.board_size,
                player_id=player_id
            )
        elif config.player_type == "greedy":
            return GreedyPlayer(
                board_size=self.board_size,
                player_id=player_id
            )
        elif config.player_type == "pachi":
            return PachiPlayer(
                board_size=self.board_size,
                iterations=self.iterations_per_move,
                player_id=player_id
            )
        elif config.player_type == "katago_1k":
            return KataGoPlayer(
                board_size=self.board_size,
                iterations=1000,  # 1k playouts
                player_id=player_id
            )
        elif config.player_type == "katago_5k":
            return KataGoPlayer(
                board_size=self.board_size,
                iterations=5000,  # 5k playouts (same as MCTS players)
                player_id=player_id
            )
        elif config.player_type == "mcts_rollout":
            return MCTSRolloutPlayer(
                board_size=self.board_size,
                iterations=self.iterations_per_move,
                player_id=player_id
            )
        else:
            raise ValueError(f"Unknown player type: {config.player_type}")

    def play_game(
        self,
        black_config: AcceleratorConfig,
        white_config: AcceleratorConfig,
        game_id: int = 0
    ) -> GameRecord:
        """
        Play a complete game between two configurations.

        Args:
            black_config: Configuration for Black player
            white_config: Configuration for White player
            game_id: Unique game identifier

        Returns:
            GameRecord with complete game information
        """
        if self.verbose:
            print(f"\n{'='*80}")
            print(f"Game #{game_id}: {black_config.name} (Black) vs {white_config.name} (White)")
            print(f"{'='*80}")

        # Stage 1: initialize an empty board and fresh move trace.
        self.board = np.zeros((self.board_size, self.board_size), dtype=int)
        self.move_history = []

        # Stage 2: instantiate Black and White from their explicit modes.
        black_player = self._create_player(black_config, player_id=1)
        white_player = self._create_player(white_config, player_id=-1)

        # Stage 3: alternate legal moves until the board or move budget ends.
        current_player = black_player
        current_player_name = "Black"
        move_count = 0

        while move_count < self.max_moves:
            # Stop when no empty board point remains.
            if not self._has_valid_moves():
                if self.verbose:
                    print(f"Board full after {move_count} moves")
                break

            # Retain the explicit move-budget guard inside the loop.
            if move_count >= self.max_moves:
                if self.verbose:
                    print(f"Reached maximum moves ({self.max_moves}), evaluating position...")
                break

            # Ask the active player for one move on the current board.
            move = current_player.select_move(self.board)

            if move == (-1, -1):
                if self.verbose:
                    print(f"{current_player_name} has no valid moves")
                break

            # Apply occupancy, suicide, and capture rules to the shared board.
            row, col = move
            legal, captured = self.go_rules.apply_move(
                self.board, row, col, current_player.player_id
            )

            if not legal:
                print(f"ERROR: {current_player_name} tried illegal move {move}!")
                print(f"  Reason: Position occupied or suicide move")
                break

            self.move_history.append(move)
            move_count += 1

            if captured > 0 and self.verbose:
                print(f"  {current_player_name} captured {captured} stone(s) with move {move}")

            # Synchronize external GTP engines with the opponent's move.
            opponent_player = white_player if current_player == black_player else black_player
            if hasattr(opponent_player, 'update_with_move'):
                opponent_player.update_with_move(move, current_player.player_id)

            if self.verbose and move_count % 10 == 0:
                print(f"Move {move_count}: {current_player_name} plays {move}")

            # Alternate the active color for the next turn.
            if current_player == black_player:
                current_player = white_player
                current_player_name = "White"
            else:
                current_player = black_player
                current_player_name = "Black"

        # Stage 4: score the final board with the training heuristic.
        outcome, score_details = self.evaluator.evaluate_position(self.board)
        winner = self.evaluator.get_winner_string(outcome)

        if self.verbose:
            print(f"\n{'-'*80}")
            print(f"Game Over after {move_count} moves")
            print(self.evaluator.format_evaluation(outcome, score_details))
            print(f"{'-'*80}\n")

        # Stage 5: freeze the game result for tournament aggregation.
        game_record = GameRecord(
            game_id=game_id,
            black_config=black_config,
            white_config=white_config,
            winner=winner,
            outcome_value=outcome,
            total_moves=move_count,
            final_score=score_details['total_score'],
            score_details=score_details,
            timestamp=datetime.now().isoformat(),
            move_history=self.move_history.copy()
        )

        return game_record

    def _has_valid_moves(self) -> bool:
        """Check if board has any empty positions."""
        return np.any(self.board == 0)

    def print_board(self):
        """Print current board state."""
        if self.board is None:
            print("No active game")
            return

        print()
        for row in self.board:
            print(" ".join([
                'B' if x == 1 else 'W' if x == -1 else '.'
                for x in row
            ]))
        print()


def test_game_controller():
    """Test game controller with two players."""
    print("Testing Game Controller")
    print("=" * 80)

    from tournament.engines.config_loader import get_tournament_configs

    # Get configurations
    configs = get_tournament_configs(board_size=9)  # Use 9x9

    # Play a test game (use first two configs)
    controller = GameController(
        board_size=9,
        iterations_per_move=50,  # Very low for quick testing
        verbose=True
    )

    record = controller.play_game(
        black_config=configs[0],
        white_config=configs[1],
        game_id=1
    )

    print("\nGame Record:")
    print(f"  Winner: {record.winner}")
    print(f"  Total Moves: {record.total_moves}")
    print(f"  Final Score: {record.final_score:.2f}")
    print(f"  Material: {record.score_details['material_diff']}")
    print(f"  Territory: {record.score_details['territory_diff']}")
    print(f"  Liberties: {record.score_details['liberty_diff']}")

    print("\n✓ Game controller test passed!")


if __name__ == "__main__":
    test_game_controller()
