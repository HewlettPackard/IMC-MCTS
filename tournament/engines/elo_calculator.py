# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
ELO Rating System for MCTS Tournament.

Implements standard ELO rating calculations used in chess and other
competitive games to track relative playing strength.
"""

import math
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PlayerRating:
    """Track ELO rating for a player/configuration."""

    player_id: str  # Unique identifier (e.g., "High Accuracy")
    initial_rating: float = 1500.0  # Standard ELO starting point
    current_rating: float = 1500.0
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    rating_history: List[Tuple[int, float]] = field(default_factory=list)  # (game_num, rating)

    def __post_init__(self):
        """Initialize rating history with starting rating."""
        self.current_rating = self.initial_rating
        self.rating_history = [(0, self.initial_rating)]

    def record_game(self, result: float, new_rating: float):
        """
        Record a game result and update rating.

        Args:
            result: 1.0 (win), 0.5 (draw), or 0.0 (loss)
            new_rating: Updated ELO rating after this game
        """
        self.games_played += 1

        if result == 1.0:
            self.wins += 1
        elif result == 0.0:
            self.losses += 1
        else:  # 0.5
            self.draws += 1

        self.current_rating = new_rating
        self.rating_history.append((self.games_played, new_rating))

    def win_rate(self) -> float:
        """Calculate win rate (wins / games)."""
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played

    def score(self) -> float:
        """Calculate total score (wins + 0.5*draws)."""
        return self.wins + 0.5 * self.draws

    def __repr__(self):
        return (f"PlayerRating({self.player_id}, "
                f"rating={self.current_rating:.1f}, "
                f"games={self.games_played}, "
                f"W/L/D={self.wins}/{self.losses}/{self.draws})")


class ELOCalculator:
    """
    ELO rating calculator for tournament play.

    Standard ELO formula:
        new_rating = old_rating + K * (actual_score - expected_score)

    Where:
        K = K-factor (higher = more volatile ratings)
        actual_score = 1 (win), 0.5 (draw), 0 (loss)
        expected_score = 1 / (1 + 10^((opponent_rating - player_rating) / 400))
    """

    def __init__(self, k_factor: float = 32.0, initial_rating: float = 1500.0):
        """
        Initialize ELO calculator.

        Args:
            k_factor: K-factor for rating changes (default: 32, typical for games)
            initial_rating: Starting rating for all players (default: 1500)
        """
        self.k_factor = k_factor
        self.initial_rating = initial_rating
        self.players: Dict[str, PlayerRating] = {}

    def add_player(self, player_id: str):
        """
        Add a new player to the rating system.

        Args:
            player_id: Unique identifier for the player
        """
        if player_id not in self.players:
            self.players[player_id] = PlayerRating(
                player_id=player_id,
                initial_rating=self.initial_rating
            )

    def get_expected_score(self, rating_a: float, rating_b: float) -> float:
        """
        Calculate expected score for player A vs player B.

        Formula: 1 / (1 + 10^((rating_b - rating_a) / 400))

        Args:
            rating_a: Current rating of player A
            rating_b: Current rating of player B

        Returns:
            Expected score for player A (between 0 and 1)
        """
        exponent = (rating_b - rating_a) / 400.0
        return 1.0 / (1.0 + math.pow(10, exponent))

    def update_ratings(self, player_a_id: str, player_b_id: str, result_a: float):
        """
        Update ratings after a game between two players.

        Args:
            player_a_id: ID of player A
            player_b_id: ID of player B
            result_a: Result from player A's perspective:
                      1.0 = A wins, 0.5 = draw, 0.0 = B wins
        """
        # Register both players before reading their current ratings.
        self.add_player(player_a_id)
        self.add_player(player_b_id)

        player_a = self.players[player_a_id]
        player_b = self.players[player_b_id]

        # Snapshot both pre-game ratings.
        rating_a = player_a.current_rating
        rating_b = player_b.current_rating

        # Compute each player's expected score from the pre-game ratings.
        expected_a = self.get_expected_score(rating_a, rating_b)
        expected_b = self.get_expected_score(rating_b, rating_a)

        # Apply new_rating = old_rating + K * (actual - expected).
        new_rating_a = rating_a + self.k_factor * (result_a - expected_a)
        new_rating_b = rating_b + self.k_factor * ((1.0 - result_a) - expected_b)

        # Record complementary outcomes for the two players.
        player_a.record_game(result_a, new_rating_a)
        player_b.record_game(1.0 - result_a, new_rating_b)

    def get_rating(self, player_id: str) -> float:
        """
        Get current rating for a player.

        Args:
            player_id: Player identifier

        Returns:
            Current ELO rating
        """
        if player_id not in self.players:
            return self.initial_rating
        return self.players[player_id].current_rating

    def get_player(self, player_id: str) -> PlayerRating:
        """
        Get full player rating object.

        Args:
            player_id: Player identifier

        Returns:
            PlayerRating object

        Raises:
            KeyError: If player doesn't exist
        """
        return self.players[player_id]

    def get_rankings(self) -> List[Tuple[str, float, PlayerRating]]:
        """
        Get players ranked by current ELO rating.

        Returns:
            List of (player_id, rating, player_object) tuples, sorted by rating descending
        """
        player_ratings = [
            (player_id, player.current_rating, player)
            for player_id, player in self.players.items()
        ]
        return sorted(player_ratings, key=lambda rating_entry: rating_entry[1], reverse=True)

    def print_rankings(self):
        """Print current rankings in human-readable format."""
        rankings = self.get_rankings()

        print("ELO Rankings")
        print("=" * 80)
        print(f"{'Rank':<6} {'Player':<30} {'Rating':<8} {'Games':<7} {'W/L/D':<12} {'Win%':<7}")
        print("-" * 80)

        for rank, (player_id, rating, player) in enumerate(rankings, 1):
            wld = f"{player.wins}/{player.losses}/{player.draws}"
            win_pct = player.win_rate() * 100

            print(f"{rank:<6} {player_id:<30} {rating:<8.1f} {player.games_played:<7} {wld:<12} {win_pct:<7.1f}")

        print("=" * 80)

    def export_results(self) -> dict:
        """
        Export tournament results as dictionary.

        Returns:
            Dictionary with player stats and rankings
        """
        rankings = self.get_rankings()

        return {
            'timestamp': datetime.now().isoformat(),
            'k_factor': self.k_factor,
            'initial_rating': self.initial_rating,
            'rankings': [
                {
                    'rank': rank,
                    'player_id': player_id,
                    'rating': rating,
                    'games_played': player.games_played,
                    'wins': player.wins,
                    'losses': player.losses,
                    'draws': player.draws,
                    'win_rate': player.win_rate(),
                    'score': player.score(),
                    'rating_history': player.rating_history
                }
                for rank, (player_id, rating, player) in enumerate(rankings, 1)
            ]
        }


def test_elo_calculator():
    """Test ELO calculator with sample games."""
    print("Testing ELO Calculator")
    print("=" * 80)
    print()

    calc = ELOCalculator(k_factor=32, initial_rating=1500)

    # Add players
    calc.add_player("High Accuracy")
    calc.add_player("Medium Accuracy")
    calc.add_player("Low Accuracy")

    print("Initial ratings:")
    calc.print_rankings()
    print()

    # Simulate some games
    games = [
        ("High Accuracy", "Medium Accuracy", 1.0),  # High wins
        ("High Accuracy", "Low Accuracy", 1.0),     # High wins
        ("Medium Accuracy", "Low Accuracy", 1.0),   # Medium wins
        ("High Accuracy", "Medium Accuracy", 1.0),  # High wins
        ("Medium Accuracy", "Low Accuracy", 0.5),   # Draw
        ("High Accuracy", "Low Accuracy", 1.0),     # High wins
    ]

    print("Simulating 6 games...")
    for i, (player_a, player_b, result) in enumerate(games, 1):
        calc.update_ratings(player_a, player_b, result)
        result_str = "wins" if result == 1.0 else "draws" if result == 0.5 else "loses"
        print(f"  Game {i}: {player_a} {result_str} vs {player_b}")

    print()
    print("Final ratings:")
    calc.print_rankings()
    print()

    # Check expected outcomes
    assert calc.get_rating("High Accuracy") > calc.get_rating("Medium Accuracy")
    assert calc.get_rating("Medium Accuracy") > calc.get_rating("Low Accuracy")

    print("✓ ELO calculator test passed!")


if __name__ == "__main__":
    test_elo_calculator()
