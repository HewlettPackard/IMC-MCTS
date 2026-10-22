# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
CrossbarEvaluator — loads per-game crossbar weights and coaches,
provides a callable eval_fn(board, player) -> float for use in MCTSEngine.

Reuses each game's coach.board_to_features() to handle game-specific encoding
(metadata row stripping, cell value mapping, etc.), matching the pattern in
src/training/evaluate_all_games.py.
"""

import os
import pickle
import random
import importlib.util
from typing import Optional

import numpy as np

# Paths relative to project root
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
_TRAINING_DIR = os.path.join(_PROJECT_ROOT, "src", "training")
_GAMES_DIR = os.path.join(_TRAINING_DIR, "games")
_SELFPLAY_DIR = os.path.join(_TRAINING_DIR, "selfplay_data")

_coach_cache = {}

# Pre-computed best weight source per game based on value-spread probing.
_BEST_SOURCE = {
    "go": "coach",             # selfplay nearly flat (std=0.02)
    "hex": "coach",            # coach H2H 33% vs selfplay 0%
    "gomoku": "selfplay",      # selfplay has wider spread
    "havannah": "coach",       # retrained with hex-only encoding
    "othello": "coach",        # coach H2H 83% vs selfplay 50%
    "connect_four": "coach",   # retrained coach; both ~50% H2H
    "pente": "selfplay",       # selfplay wider spread
    "breakthrough": "coach",   # coach H2H 50% vs selfplay 33%
    "protein_folding": "coach",  # retrained with regression
    "nonograms": "coach",      # both marginal; coach slightly better
    "frozen_lake": "coach",    # retrained; NN achieves perfect path efficiency
    "minigrid": "coach",       # retrained; NN achieves perfect path efficiency
    "minesweeper": "coach",    # only source available
}


def _load_coach(game_key: str):
    """Load the game's existing board-to-feature conversion."""
    if game_key in _coach_cache:
        return _coach_cache[game_key]
    coach_path = os.path.join(_GAMES_DIR, game_key, "coach.py")
    spec = importlib.util.spec_from_file_location(f"{game_key}_coach", coach_path)
    coach_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(coach_module)
    coach = coach_module.GameCoach()
    _coach_cache[game_key] = coach
    return coach


def _resolve_weights_path(game_key: str, weights_source: str):
    """Choose the requested weight file or the calibrated automatic source."""
    selfplay_path = os.path.join(
        _SELFPLAY_DIR, f"weights_{game_key}", "best_improved_model.pkl"
    )
    coach_path = os.path.join(
        _GAMES_DIR, game_key, "results", "best_improved_model.pkl"
    )
    if weights_source == "selfplay":
        return selfplay_path, "selfplay"
    if weights_source == "coach":
        return coach_path, "coach"
    # Auto mode uses the measured best source, then tries the other source.
    preferred_source = _BEST_SOURCE.get(game_key, "selfplay")
    preferred_path = selfplay_path if preferred_source == "selfplay" else coach_path
    fallback_path = coach_path if preferred_source == "selfplay" else selfplay_path
    fallback_source = "coach" if preferred_source == "selfplay" else "selfplay"
    if os.path.exists(preferred_path):
        return preferred_path, preferred_source
    if os.path.exists(fallback_path):
        return fallback_path, fallback_source
    raise FileNotFoundError(
        f"No trained weights found for {game_key}. "
        f"Checked:\n  {selfplay_path}\n  {coach_path}"
    )


class CrossbarEvaluator:
    """Crossbar NN position evaluator for a single game.

    Callable as eval_fn(board, player) -> float  (result in [0, 1] from P1's
    perspective), suitable for passing directly to MCTSEngine(eval_fn=...).

    Handles two training-data issues automatically:

    1. **Softmax saturation**: For classification outputs where one class
       dominates, uses a calibrated sigmoid on the logit spread instead
       of raw softmax. This preserves discriminative signal.

    2. **Label polarity**: Some weight files have class 0 = P1-wins instead
       of the expected class 2 = P1-wins. Auto-detected at init time by
       probing terminal positions, and corrected with a value flip.
    """

    def __init__(self, game_key: str,
                 weights_path: Optional[str] = None,
                 weights_source: str = "auto"):
        self.game_key = game_key
        self.coach = _load_coach(game_key)

        # Stage 1: resolve and load the conductance matrices.
        if weights_path is None:
            weights_path, weights_source = _resolve_weights_path(
                game_key, weights_source
            )

        with open(weights_path, "rb") as f:
            checkpoint = pickle.load(f)

        self.weights_source = weights_source
        self.weights_path = weights_path
        W1_conductance = np.array(checkpoint["weights1"], dtype=np.float32)
        W2_conductance = np.array(checkpoint["weights2"], dtype=np.float32)

        # Differential pair: W_eff = (G - 50) / 50.
        self.w1_eff = (W1_conductance - 50.0) / 50.0
        self.w2_eff = (W2_conductance - 50.0) / 50.0
        self._is_classification = W2_conductance.shape[1] > 1
        # Number of play-area rows the network expects (2 features per cell)
        from generalizability.games import APP_BOARD_SIZES
        self._play_rows = APP_BOARD_SIZES[game_key]

        # Stage 2: calibrate the classification logit spread.
        self._spread_lo = 0.0
        self._spread_hi = 1.0
        if self._is_classification:
            self._calibrate_spread(game_key)

        # Stage 3: detect and correct inverted label polarity.
        self._flip = False
        self._detect_polarity(game_key)

    def _calibrate_spread(self, game_key: str):
        """Probe positions to calibrate logit-spread -> [0,1] linear mapping.

        Uses linear mapping (clipped) instead of sigmoid to preserve fine
        gradations across the full spread range. This is critical for
        navigation games where most reachable positions have similar large
        spreads — sigmoid would saturate them all to ~1.0.

        Probes include both random game playouts and, for single-player
        games, positions with the agent placed at various board locations
        to sample the full spread range.
        """
        from generalizability.games import GAME_REGISTRY
        game = GAME_REGISTRY[game_key]
        rng = random.Random(42)  # fixed seed for reproducible calibration
        spreads = []

        # Strategy 1: random playouts for reachable game states.
        for _ in range(100):
            board = game.initial_state()
            player = 1
            for _ in range(rng.randint(0, 40)):
                if game.is_terminal(board):
                    break
                moves = game.get_legal_moves(board, player)
                if not moves:
                    break
                board = game.apply_move(board, rng.choice(moves), player)
                if game.num_players == 2:
                    player = 3 - player
            if not game.is_terminal(board):
                logits = self._forward(board, player)
                spreads.append(float(logits[2] - logits[0]))

        # Strategy 2: place the single-player agent at diverse locations.
        if game.num_players == 1:
            for _ in range(20):
                base_board = game.initial_state()[:self._play_rows]
                rows, cols = base_board.shape
                for row in range(rows):
                    for col in range(cols):
                        test_board = base_board.copy()
                        # Clear the existing agent, then place it on an empty cell.
                        test_board[test_board == 3] = 0
                        if test_board[row, col] == 0:
                            test_board[row, col] = 3
                            logits = self._forward(test_board, 1)
                            spreads.append(float(logits[2] - logits[0]))

        if not spreads:
            self._spread_lo = 0.0
            self._spread_hi = 1.0
            return

        spread_values = np.array(spreads)
        # Use 2nd and 98th percentile for the linear map endpoints
        self._spread_lo = float(np.percentile(spread_values, 2))
        self._spread_hi = float(np.percentile(spread_values, 98))
        if self._spread_hi - self._spread_lo < 0.1:
            self._spread_hi = self._spread_lo + 0.1

    def _detect_polarity(self, game_key: str):
        """Check if the NN assigns higher values to wins vs losses.

        If inverted, sets self._flip = True. If the signal is too weak
        to determine polarity (effect size < 0.05), sets self._weak = True
        to indicate that the NN may not be useful for this game.

        Uses a fixed seed for reproducible detection.
        """
        from generalizability.games import GAME_REGISTRY
        game = GAME_REGISTRY[game_key]
        rng = random.Random(123)  # fixed seed
        win_values, loss_values = [], []
        for _ in range(500):
            board = game.initial_state()
            player = 1
            for _ in range(500):
                if game.is_terminal(board):
                    break
                moves = game.get_legal_moves(board, player)
                if not moves:
                    break
                board = game.apply_move(board, rng.choice(moves), player)
                if game.num_players == 2:
                    player = 3 - player
            if not game.is_terminal(board):
                continue
            result = game.get_result(board, 1)
            value = self._raw_eval(board, 1)
            if result >= 0.8:
                win_values.append(value)
            elif result <= 0.2:
                loss_values.append(value)
            if len(win_values) >= 30 and len(loss_values) >= 30:
                break
        self._weak = False
        if len(win_values) >= 5 and len(loss_values) >= 5:
            value_difference = np.mean(win_values) - np.mean(loss_values)
            if value_difference < -0.02:
                # Inverted — flip
                self._flip = True
            elif abs(value_difference) < 0.02:
                # Too weak to be useful
                self._weak = True

    def _forward(self, board: np.ndarray, player: int):
        """Run forward pass, return logits.

        For games with enhanced encodings (nonograms, minesweeper, protein_folding),
        passes game-specific context kwargs to board_to_features.
        """
        play_board = board[:self._play_rows]
        feature_kwargs = self._get_feature_kwargs(play_board)
        features = self.coach.board_to_features(play_board, **feature_kwargs)
        features.append(1.0 if player == 1 else 0.0)
        feature_vector = np.array(features, dtype=np.float32)
        hidden = np.maximum(0, feature_vector @ self.w1_eff)
        return hidden @ self.w2_eff

    def _get_feature_kwargs(self, board: np.ndarray) -> dict:
        """Build game-specific kwargs for board_to_features."""
        if self.game_key == "nonograms":
            from generalizability.games import GAME_REGISTRY
            game = GAME_REGISTRY[self.game_key]
            return {"row_clues": game.row_clues, "col_clues": game.col_clues}
        if self.game_key == "minesweeper":
            from generalizability.games import GAME_REGISTRY
            game = GAME_REGISTRY[self.game_key]
            return {"mine_locations": game._mine_locations}
        return {}

    def _raw_eval(self, board: np.ndarray, player: int) -> float:
        """Evaluate without polarity flip (used during calibration)."""
        logits = self._forward(board, player)
        if self._is_classification:
            spread = float(logits[2] - logits[0])
            # Linear map: spread in [lo, hi] -> [0.02, 0.98], clipped
            normalized_spread = (
                (spread - self._spread_lo) /
                (self._spread_hi - self._spread_lo)
            )
            return float(np.clip(normalized_spread * 0.96 + 0.02, 0.02, 0.98))
        else:
            logit = float(logits[0])
            return 1.0 / (1.0 + np.exp(-np.clip(logit, -20, 20)))

    def __call__(self, board: np.ndarray, player: int) -> float:
        """Evaluate board position. Returns value in [0, 1] from P1's perspective."""
        value = self._raw_eval(board, player)
        if self._flip:
            value = 1.0 - value
        return float(value)


def make_evaluator(game_key: str,
                   weights_source: str = "auto",
                   allow_weak: bool = False) -> Optional[CrossbarEvaluator]:
    """Factory: create a CrossbarEvaluator for the given game.

    Returns None if the evaluator's signal is too weak to guide MCTS
    (unless allow_weak=True).
    """
    evaluator = CrossbarEvaluator(game_key, weights_source=weights_source)
    if evaluator._weak and not allow_weak:
        return None
    return evaluator
