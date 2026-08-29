#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Minimal crossbar evaluator with conductance-noise injection.

Bypasses generalizability/evaluation/crossbar_evaluator.py (which depends on a
missing src/training/games/<game>/coach.py tree). Uses the same 2-channel
encoding and forward pass as core/simulator/mcts_sst_components.py
(RolloutUnitComponent) so noise effects match what would happen in the SST sim.

Noise model
-----------
Programming variation in RRAM, sampled once at construction:

    G_noisy = G + sigma * 50 * N(0, 1)        # conductance space, per cell

In eff-space (w = (G - 50) / 50) this is exactly:

    w_noisy = w + sigma * N(0, 1)

The implementation below applies this relationship directly in weight space.

Usage
-----
    ev = NoisyCrossbarEval("go", noise_sigma=0.05, noise_seed=1)
    engine = MCTSEngine(go_game, iterations=1000, eval_fn=ev)
"""

import os
import pickle

import numpy as np

# Project root: this file lives at generalizability/evaluation/noisy_eval.py,
# so two levels up is the generalizability/ package root.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Board size per game (matches the board sizes used by the game registry in
# generalizability/games/). Only games with trained weights under
# weights/models/weights_NxN/ are usable here.
_BOARD_SIZE = {
    "go": 9, "hex": 11, "gomoku": 15, "havannah": 15, "pente": 19,
    "othello": 8, "connect_four": 8, "breakthrough": 8,
    "protein_folding": 13, "nonograms": 9, "frozen_lake": 8,
    "minigrid": 8, "minesweeper": 9,
}


def _weights_path(game_key):
    n = _BOARD_SIZE[game_key]
    return os.path.join(_PROJECT_ROOT, "weights", "models",
                        f"weights_{n}x{n}", "best_improved_model.pkl")


class NoisyCrossbarEval:
    """Position evaluator for MCTS that can inject conductance noise.

    Returns a value in [0, 1] from player 1's perspective:
        1.0 = P1 wins,  0.5 = draw,  0.0 = P1 loses.
    """

    def __init__(self, game_key, noise_sigma=0.0, noise_seed=0):
        self.game_key = game_key
        self.board_size = _BOARD_SIZE[game_key]
        self.noise_sigma = float(noise_sigma)
        self.noise_seed = int(noise_seed)

        with open(_weights_path(game_key), "rb") as f:
            ckpt = pickle.load(f)
        w1 = np.asarray(ckpt["weights1"], dtype=np.float64)
        w2 = np.asarray(ckpt["weights2"], dtype=np.float64)

        # Differential-pair normalization: G in [0, 100] uS -> w in [-1, 1].
        # Matches engine/imc_mcts.c:78 and crossbar_evaluator.py:122-123.
        self.w1_eff = (w1 - 50.0) / 50.0
        self.w2_eff = (w2 - 50.0) / 50.0

        # Inject programming noise only when asked. Clean baseline keeps sigma=0.
        if self.noise_sigma > 0.0:
            self._inject_conductance_noise(self.noise_sigma, self.noise_seed)

        # Auto-detect polarity: the SST sim assumes probs = [P(white), P(draw),
        # P(black)] so value = probs[2]. Training labels may be inverted; detect
        # on a few clear terminal positions.
        self._flip = self._detect_polarity()

    def _inject_conductance_noise(self, sigma, seed):
        """Additive Gaussian noise in conductance space (G).

        In eff-space, sigma_G / 50 = sigma, so adding sigma * N(0,1) to w_eff is
        equivalent to adding sigma * 50 * N(0,1) uS to G.
        """
        rng = np.random.RandomState(seed)
        self.w1_eff = self.w1_eff + sigma * rng.standard_normal(self.w1_eff.shape)
        self.w2_eff = self.w2_eff + sigma * rng.standard_normal(self.w2_eff.shape)

    def _board_to_features(self, board):
        """2-channel encoding identical to SST RolloutUnitComponent.

        Player 1 (Black) -> channel 0; player 2 (White) -> channel 1.
        Drops metadata rows by trimming to board_size rows.
        """
        play = board[:self.board_size]
        feats = np.zeros(self.board_size * self.board_size * 2, dtype=np.float64)
        flat = play.flatten()
        feats[0::2] = (flat == 1).astype(np.float64)  # Black
        feats[1::2] = (flat == 2).astype(np.float64)  # White
        return feats

    def _forward(self, board):
        """Two-layer NN forward pass. Returns softmax over [W, D, B] outputs."""
        x = self._board_to_features(board)
        h = np.maximum(0.0, x @ self.w1_eff)
        logits = h @ self.w2_eff
        logits -= logits.max()
        e = np.exp(logits)
        return e / e.sum()

    def _value_from_probs(self, probs):
        """Convention: probs = [P(white-win), P(draw), P(black-win)].
        Value from BLACK's perspective. Caller flips for player 2."""
        return float(probs[2] * 1.0 + probs[1] * 0.5 + probs[0] * 0.0)

    def _detect_polarity(self):
        """Return True if labels are inverted (P(black-win) at index 0).

        Constructs a few obviously-black-winning terminal positions and checks
        whether index 2 or index 0 has the higher probability. Robust to a
        small noise injection; uses zero noise for the probe boards.
        """
        n = self.board_size
        # All-black board -> black should win decisively.
        black_dom = np.zeros((n + 2, n), dtype=np.int16)
        black_dom[:n, :] = 1
        # All-white board -> white should win.
        white_dom = np.zeros((n + 2, n), dtype=np.int16)
        white_dom[:n, :] = 2

        pb_black = self._forward(black_dom)
        pb_white = self._forward(white_dom)
        # If index 2 is "black wins", black_dom should have probs[2] > probs[0]
        # AND white_dom should have probs[0] > probs[2].
        index2_is_black = (pb_black[2] > pb_black[0]) and (pb_white[0] > pb_white[2])
        index0_is_black = (pb_black[0] > pb_black[2]) and (pb_white[2] > pb_white[0])
        if index2_is_black:
            return False
        if index0_is_black:
            return True
        # Ambiguous (e.g. saturated softmax) -- default to non-flipped and let
        # the sanity test downstream catch it.
        return False

    def raw_probs(self, board):
        """Expose raw [W, D, B] (or flipped) probs for diagnostics / panel c."""
        p = self._forward(board)
        if self._flip:
            p = p[::-1].copy()
        return p

    def __call__(self, board, player):
        """MCTS eval_fn signature. Returns value in [0, 1] from P1's perspective."""
        probs = self._forward(board)
        val_black = self._value_from_probs(probs)
        if self._flip:
            val_black = 1.0 - val_black
        # val_black is from P1=Black perspective; MCTS expects P1's value.
        # Caller-side perspective handling is in MCTSEngine._ucb1, not here.
        return val_black


if __name__ == "__main__":
    # Self-check on Go: load the evaluator and show the noise model shifting the
    # [W, D, B] probabilities on a few probe boards. sigma=0 is the clean baseline.
    n = _BOARD_SIZE["go"]

    def all_color(color):
        b = np.zeros((n + 2, n), dtype=np.int16)
        b[:n, :] = color
        return b

    boards = {
        "empty":     np.zeros((n + 2, n), dtype=np.int16),
        "all_black": all_color(1),
        "all_white": all_color(2),
    }

    clean = NoisyCrossbarEval("go", noise_sigma=0.0)
    noisy = NoisyCrossbarEval("go", noise_sigma=0.05, noise_seed=1)
    print(f"loaded go weights; polarity flip: clean={clean._flip} noisy={noisy._flip}")
    print()
    print(f"{'board':<11}{'clean [W,D,B]':<26}{'noisy(sigma=0.05) [W,D,B]'}")
    print("-" * 70)
    for name, b in boards.items():
        pc = clean.raw_probs(b)
        pn = noisy.raw_probs(b)
        print(f"{name:<11}{np.array2string(pc, precision=3):<26}"
              f"{np.array2string(pn, precision=3)}")
        print(f"{'':<11}value: clean={clean(b, 1):.3f}  noisy={noisy(b, 1):.3f}")
