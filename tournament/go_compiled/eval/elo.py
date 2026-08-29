# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
ELO Rating Calculator.

Standard ELO formula with K=32, initial rating 1500.
"""

import math
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PlayerRating:
    """Track ELO rating for a player/configuration."""

    player_id: str
    initial_rating: float = 1500.0
    current_rating: float = 1500.0
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    rating_history: List[Tuple[int, float]] = field(default_factory=list)

    def __post_init__(self):
        self.current_rating = self.initial_rating
        self.rating_history = [(0, self.initial_rating)]

    def record_game(self, result: float, new_rating: float):
        self.games_played += 1
        if result == 1.0:
            self.wins += 1
        elif result == 0.0:
            self.losses += 1
        else:
            self.draws += 1
        self.current_rating = new_rating
        self.rating_history.append((self.games_played, new_rating))

    def win_rate(self) -> float:
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played

    def score(self) -> float:
        return self.wins + 0.5 * self.draws


class ELOCalculator:
    """ELO rating system for tournament play."""

    def __init__(self, k_factor: float = 32.0, initial_rating: float = 1500.0):
        self.k_factor = k_factor
        self.initial_rating = initial_rating
        self.players: Dict[str, PlayerRating] = {}

    def add_player(self, player_id: str):
        if player_id not in self.players:
            self.players[player_id] = PlayerRating(
                player_id=player_id,
                initial_rating=self.initial_rating
            )

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / 400.0))

    def update_ratings(self, player_a: str, player_b: str, result_a: float):
        """Update ratings. result_a: 1.0=A wins, 0.5=draw, 0.0=B wins."""
        self.add_player(player_a)
        self.add_player(player_b)

        rating_a = self.players[player_a]
        rating_b = self.players[player_b]

        # E_A = 1 / (1 + 10^((R_B - R_A) / 400)).
        expected_a = self.expected_score(rating_a.current_rating, rating_b.current_rating)
        expected_b = self.expected_score(rating_b.current_rating, rating_a.current_rating)

        # R_new = R_old + K * (actual - expected).
        new_rating_a = rating_a.current_rating + self.k_factor * (result_a - expected_a)
        new_rating_b = rating_b.current_rating + self.k_factor * ((1.0 - result_a) - expected_b)

        rating_a.record_game(result_a, new_rating_a)
        rating_b.record_game(1.0 - result_a, new_rating_b)

    def get_rankings(self) -> List[Tuple[str, float, PlayerRating]]:
        return sorted(
            [
                (player_id, player_rating.current_rating, player_rating)
                for player_id, player_rating in self.players.items()
            ],
            key=lambda ranking_entry: ranking_entry[1],
            reverse=True
        )

    def print_rankings(self):
        rankings = self.get_rankings()
        print(f"{'Rank':<6}{'Player':<30}{'Rating':<8}{'Games':<7}{'W/L/D':<12}{'Win%':<7}")
        print("-" * 70)
        for rank, (player_id, rating, player_rating) in enumerate(rankings, 1):
            win_loss_draw = (
                f"{player_rating.wins}/{player_rating.losses}/{player_rating.draws}"
            )
            print(f"{rank:<6}{player_id:<30}{rating:<8.1f}{player_rating.games_played:<7}{win_loss_draw:<12}{player_rating.win_rate()*100:<7.1f}")

    def export_results(self) -> dict:
        return {
            'timestamp': datetime.now().isoformat(),
            'k_factor': self.k_factor,
            'rankings': [
                {
                    'rank': rank,
                    'player_id': player_id,
                    'rating': rating,
                    'games_played': player_rating.games_played,
                    'wins': player_rating.wins,
                    'losses': player_rating.losses,
                    'draws': player_rating.draws,
                    'win_rate': player_rating.win_rate(),
                    'rating_history': player_rating.rating_history,
                }
                for rank, (player_id, rating, player_rating)
                in enumerate(self.get_rankings(), 1)
            ]
        }
