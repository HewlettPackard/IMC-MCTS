#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Iterative Self-Play Training Pipeline.

Cycle: play games with current model -> collect positions -> train on them -> repeat.
Uses the C MCTS engine for fast self-play, labels positions with game outcomes.
Matches the hardware rollout unit: 163 -> 96 -> 3 (softmax).
"""

import ctypes as ct
import os
import json
import struct
import subprocess
import numpy as np
import pickle
import time
import argparse
from typing import List, Tuple

BOARD_SIZE = 9
NUM_CELLS = 81
PASS_MOVE = 81
MAX_MOVES = 200

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_PATH = os.path.join(_PROJECT_ROOT, 'engine', 'imc_mcts.so')


def load_engine():
    """Load C MCTS engine."""
    lib = ct.CDLL(LIB_PATH)
    lib.load_weights.argtypes = [ct.c_char_p]
    lib.load_weights.restype = ct.c_int
    lib.mcts_search.argtypes = [
        ct.POINTER(ct.c_int8), ct.c_int8, ct.c_int, ct.c_int,
        ct.c_uint64, ct.c_int, ct.c_double,
    ]
    lib.mcts_search.restype = ct.c_int
    lib.apply_move_c.argtypes = [
        ct.POINTER(ct.c_int8), ct.c_int, ct.c_int8, ct.POINTER(ct.c_int8)
    ]
    lib.apply_move_c.restype = ct.c_int
    return lib


def board_hash_fnv(board):
    board_hash = 14695981039346656037
    for value in board.ravel():
        board_hash ^= int(value) & 0xFF
        board_hash = (board_hash * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return board_hash


def score_position(board, komi=6.5):
    """Chinese area scoring. Returns (black_score, white_score)."""
    black_score = float(np.sum(board == 1))
    white_score = float(np.sum(board == -1))
    visited = np.zeros_like(board, dtype=bool)
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row, col] != 0 or visited[row, col]:
                continue
            region = []
            owners = set()
            stack = [(row, col)]
            while stack:
                current_row, current_col = stack.pop()
                if (current_row < 0 or current_row >= BOARD_SIZE or
                        current_col < 0 or current_col >= BOARD_SIZE):
                    continue
                if visited[current_row, current_col]:
                    continue
                if board[current_row, current_col] != 0:
                    owners.add(int(board[current_row, current_col]))
                    continue
                visited[current_row, current_col] = True
                region.append((current_row, current_col))
                for row_offset, col_offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    stack.append((current_row + row_offset,
                                  current_col + col_offset))
            if len(owners) == 1:
                owner = owners.pop()
                if owner == 1:
                    black_score += len(region)
                else:
                    white_score += len(region)
    return black_score, white_score + komi


def board_to_features(board_flat, current_player):
    """Convert flat board + player to 163 features."""
    features = []
    for cell in board_flat:
        if cell == 1:
            features.extend([1.0, 0.0])
        elif cell == -1:
            features.extend([0.0, 1.0])
        else:
            features.extend([0.0, 0.0])
    features.append(1.0 if current_player == 1 else 0.0)
    return features


def color_flip_features(features):
    """Color-flip augmentation: swap channels + flip turn bit."""
    flipped = []
    for feature_index in range(0, 162, 2):
        flipped.extend([features[feature_index + 1], features[feature_index]])
    flipped.append(1.0 - features[162])
    return flipped


def play_selfplay_game(lib, mcts_iters, exploration_c=0.7):
    """
    Play one self-play game using the C MCTS engine.
    Returns list of (features, current_player) for each position + game outcome.
    """
    board = np.zeros(NUM_CELLS, dtype=np.int8)
    new_board = (ct.c_int8 * NUM_CELLS)()
    current_player = 1
    consecutive_passes = 0
    move_count = 0
    ko_hash = 0

    positions = []  # (features, current_player) at each position

    while move_count < MAX_MOVES:
        if consecutive_passes >= 2:
            break

        # Record position BEFORE the move
        features = board_to_features(board, current_player)
        positions.append((features, current_player))

        board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
        move = lib.mcts_search(
            board_ptr, ct.c_int8(current_player),
            ct.c_int(consecutive_passes), ct.c_int(move_count),
            ct.c_uint64(ko_hash), ct.c_int(mcts_iters),
            ct.c_double(exploration_c)
        )

        if move == PASS_MOVE:
            consecutive_passes += 1
        else:
            consecutive_passes = 0
            ko_hash = board_hash_fnv(board)
            lib.apply_move_c(board_ptr, ct.c_int(move),
                             ct.c_int8(current_player), new_board)
            board = np.frombuffer(new_board, dtype=np.int8).copy()

        current_player = -current_player
        move_count += 1

    # Score the final position
    board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
    black_score, white_score = score_position(board_2d)
    if black_score > white_score:
        outcome = 1.0  # Black wins
    elif white_score > black_score:
        outcome = 0.0  # White wins
    else:
        outcome = 0.5  # Draw

    return positions, outcome, move_count


def generate_selfplay_data(lib, num_games, mcts_iters):
    """Play num_games self-play games, return features + outcomes with augmentation."""
    all_features = []
    all_outcomes = []
    stats = {'black_wins': 0, 'white_wins': 0, 'draws': 0, 'total_moves': 0}

    for game_index in range(num_games):
        positions, outcome, moves = play_selfplay_game(lib, mcts_iters)
        stats['total_moves'] += moves
        if outcome == 1.0:
            stats['black_wins'] += 1
        elif outcome == 0.0:
            stats['white_wins'] += 1
        else:
            stats['draws'] += 1

        # Label all positions with game outcome (from Black's perspective)
        for features, player in positions:
            all_features.append(features)
            all_outcomes.append(outcome)

            # Color-flip augmentation
            flipped_features = color_flip_features(features)
            all_features.append(flipped_features)
            all_outcomes.append(1.0 - outcome)

        if (game_index + 1) % 20 == 0:
            print(f"    Game {game_index+1}/{num_games}: {moves} moves, "
                  f"outcome={'B' if outcome == 1.0 else 'W' if outcome == 0.0 else 'D'}, "
                  f"positions so far: {len(all_features):,}")

    stats['avg_game_length'] = stats['total_moves'] / max(num_games, 1)
    return all_features, all_outcomes, stats


COL_LETTERS = "ABCDEFGHJKLMNOPQRST"

def move_to_gtp(move_int):
    if move_int == PASS_MOVE:
        return "pass"
    row = move_int // BOARD_SIZE
    col = move_int % BOARD_SIZE
    return f"{COL_LETTERS[col]}{BOARD_SIZE - row}"

def gtp_to_move(gtp_str):
    gtp_str = gtp_str.strip().upper()
    if gtp_str in ("PASS", "RESIGN"):
        return PASS_MOVE
    col = COL_LETTERS.index(gtp_str[0])
    row = BOARD_SIZE - int(gtp_str[1:])
    return row * BOARD_SIZE + col


class GTPProcess:
    """Lightweight GTP process wrapper."""
    def __init__(self, cmd, cwd=None):
        self.p = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True, bufsize=1, cwd=cwd)
        self._send("boardsize 9")
        self._send("clear_board")
        self._send("komi 6.5")

    def _send(self, command):
        self.p.stdin.write(command + "\n")
        self.p.stdin.flush()
        response_lines = []
        first_line = True
        while True:
            line = self.p.stdout.readline()
            if not line:
                break
            line = line.rstrip('\n\r')
            if line.strip() == '' and not first_line:
                break
            if first_line:
                first_line = False
                if line.startswith("?"):
                    return "error"
                if line.startswith("="):
                    content = line[1:].strip()
                    if content:
                        response_lines.append(content)
                    continue
            response_lines.append(line.strip())
        return "\n".join(response_lines)

    def clear(self):
        self._send("clear_board")

    def play(self, color, move):
        self._send(f"play {color} {move}")

    def genmove(self, color):
        response = self._send(f"genmove {color}")
        return response.strip().split()[0] if response.strip() else "pass"

    def stop(self):
        try:
            self._send("quit")
            self.p.terminate()
        except Exception:
            pass


def play_sparring_game(lib, gnugo, weights_path, mcts_iters, imc_is_black=True):
    """
    Play one game: IMC-MCTS vs GnuGo. Collect positions from BOTH sides.
    Returns list of (features, current_player) + outcome from Black's perspective.
    """
    gnugo.clear()
    board = np.zeros(NUM_CELLS, dtype=np.int8)
    new_board = (ct.c_int8 * NUM_CELLS)()
    current_player = 1
    consecutive_passes = 0
    move_count = 0
    ko_hash = 0
    positions = []
    resigned = False

    while move_count < MAX_MOVES:
        if consecutive_passes >= 2:
            break

        # Record position
        features = board_to_features(board, current_player)
        positions.append((features, current_player))

        is_imc = (current_player == 1 and imc_is_black) or \
                 (current_player == -1 and not imc_is_black)
        color_str = "black" if current_player == 1 else "white"

        if is_imc:
            lib.load_weights(weights_path)
            board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
            move = lib.mcts_search(
                board_ptr, ct.c_int8(current_player),
                ct.c_int(consecutive_passes), ct.c_int(move_count),
                ct.c_uint64(ko_hash), ct.c_int(mcts_iters), ct.c_double(0.7))
            gtp_move = move_to_gtp(move)
            gnugo.play(color_str, gtp_move)
        else:
            gtp_move = gnugo.genmove(color_str)
            if gtp_move.upper() == "RESIGN":
                resigned = True
                break
            move = gtp_to_move(gtp_move)

        if move == PASS_MOVE:
            consecutive_passes += 1
        else:
            consecutive_passes = 0
            ko_hash = board_hash_fnv(board)
            board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
            lib.apply_move_c(board_ptr, ct.c_int(move),
                             ct.c_int8(current_player), new_board)
            board = np.frombuffer(new_board, dtype=np.int8).copy()

        current_player = -current_player
        move_count += 1

    if resigned:
        # The side that was about to move resigned
        outcome = 1.0 if current_player == -1 else 0.0  # opponent wins
    else:
        board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
        black_score, white_score = score_position(board_2d)
        if black_score > white_score:
            outcome = 1.0
        elif white_score > black_score:
            outcome = 0.0
        else:
            outcome = 0.5

    return positions, outcome, move_count


def generate_sparring_data(lib, gnugo, weights_path, num_games, mcts_iters):
    """Play num_games vs GnuGo, return features + outcomes with augmentation."""
    all_features = []
    all_outcomes = []
    imc_wins = 0

    for game_index in range(num_games):
        imc_is_black = (game_index % 2 == 0)
        positions, outcome, moves = play_sparring_game(
            lib, gnugo, weights_path, mcts_iters, imc_is_black)

        imc_color_won = (outcome == 1.0 and imc_is_black) or \
                        (outcome == 0.0 and not imc_is_black)
        if imc_color_won:
            imc_wins += 1

        for features, player in positions:
            all_features.append(features)
            all_outcomes.append(outcome)
            flipped_features = color_flip_features(features)
            all_features.append(flipped_features)
            all_outcomes.append(1.0 - outcome)

        if (game_index + 1) % 10 == 0:
            print(f"    Sparring {game_index+1}/{num_games}: {moves} mv, "
                  f"IMC {'wins' if imc_color_won else 'loses'}, "
                  f"positions: {len(all_features):,}")

    return all_features, all_outcomes, imc_wins


def export_bin(w1, w2, filepath):
    """Export weights to C engine binary format."""
    w1_f64 = np.array(w1, dtype=np.float64)
    w2_f64 = np.array(w2, dtype=np.float64)
    with open(filepath, 'wb') as output_file:
        output_file.write(struct.pack('ii', w1_f64.shape[0], w1_f64.shape[1]))
        output_file.write(w1_f64.tobytes())
        output_file.write(struct.pack('ii', w2_f64.shape[0], w2_f64.shape[1]))
        output_file.write(w2_f64.tobytes())


class CrossbarTrainerLite:
    """Lightweight trainer for iterative self-play (3-class, hardware-compatible)."""

    INPUT_SIZE = 163
    HIDDEN_SIZE = 96
    OUTPUT_SIZE = 3

    def __init__(self, lr=0.003, label_smoothing=0.1, dropout=0.15):
        self.lr = lr
        self.label_smoothing = label_smoothing
        self.dropout = dropout
        self.beta1, self.beta2, self.eps = 0.9, 0.999, 1e-8
        self.weight_decay = 0.001
        self.t = 0

    def init_weights(self):
        """Xavier init in conductance space [0.1, 99.9]."""
        def _init(fan_in, fan_out):
            xavier_std = np.sqrt(2.0 / (fan_in + fan_out))
            weights = 50.0 + np.random.normal(
                0, xavier_std, (fan_in, fan_out)
            ) * 50.0
            return np.clip(weights, 0.1, 99.9).astype(np.float32)

        w1 = _init(self.INPUT_SIZE, self.HIDDEN_SIZE)
        w2 = _init(self.HIDDEN_SIZE, self.OUTPUT_SIZE)
        return w1, w2

    def train(self, features, outcomes, w1=None, w2=None,
              epochs=50, batch_size=256, val_split=0.15):
        """Train on self-play data. Returns best (w1, w2, val_acc)."""
        positions_array = np.array(features, dtype=np.float32)
        raw_outcomes = np.array(outcomes, dtype=np.float32)

        # Discretize outcomes to 3 classes: 0=White, 1=Draw, 2=Black
        labels = np.ones(len(raw_outcomes), dtype=int)
        labels[raw_outcomes < 0.35] = 0
        labels[raw_outcomes > 0.65] = 2

        # Split
        num_positions = len(positions_array)
        shuffled_indices = np.random.permutation(num_positions)
        num_validation = int(num_positions * val_split)
        train_indices = shuffled_indices[num_validation:]
        validation_indices = shuffled_indices[:num_validation]
        X_train = positions_array[train_indices]
        y_train = labels[train_indices]
        X_val = positions_array[validation_indices]
        y_val = labels[validation_indices]

        if w1 is None or w2 is None:
            w1, w2 = self.init_weights()

        # Adam state
        m1, v1 = np.zeros_like(w1), np.zeros_like(w1)
        m2, v2 = np.zeros_like(w2), np.zeros_like(w2)
        self.t = 0

        best_val_acc = 0.0
        best_w1, best_w2 = w1.copy(), w2.copy()

        for epoch in range(epochs):
            shuffled_train_indices = np.random.permutation(len(X_train))

            for batch_start in range(0, len(X_train), batch_size):
                batch_indices = shuffled_train_indices[
                    batch_start:batch_start + batch_size
                ]
                batch_features = X_train[batch_indices]
                batch_labels = y_train[batch_indices]
                current_batch_size = len(batch_features)

                # Forward with dropout
                w1_eff = (w1 - 50.0) / 50.0
                w2_eff = (w2 - 50.0) / 50.0
                hidden = np.maximum(0, batch_features @ w1_eff)

                if self.dropout > 0:
                    dropout_mask = (
                        np.random.random(hidden.shape) > self.dropout
                    ).astype(np.float32)
                    dropped_hidden = hidden * dropout_mask / (1.0 - self.dropout)
                else:
                    dropped_hidden = hidden
                    dropout_mask = None

                logits = dropped_hidden @ w2_eff
                logits_max = np.max(logits, axis=1, keepdims=True)
                exponentials = np.exp(logits - logits_max)
                probs = exponentials / np.sum(exponentials, axis=1, keepdims=True)

                # Label-smoothed targets
                one_hot = np.eye(self.OUTPUT_SIZE)[batch_labels]
                targets = one_hot * (1.0 - self.label_smoothing) + \
                          self.label_smoothing / self.OUTPUT_SIZE

                # Backward
                d_out = (probs - targets) / current_batch_size
                w2_grad = dropped_hidden.T @ d_out / 50.0
                d_hidden = d_out @ w2_eff.T
                if dropout_mask is not None:
                    d_hidden *= dropout_mask / (1.0 - self.dropout)
                d_hidden *= (hidden > 0)
                w1_grad = batch_features.T @ d_hidden / 50.0

                for gradient in [w1_grad, w2_grad]:
                    gradient_norm = np.linalg.norm(gradient)
                    if gradient_norm > 5.0:
                        gradient *= 5.0 / gradient_norm

                self.t += 1
                adam_parameters = [
                    (w1, w1_grad, m1, v1),
                    (w2, w2_grad, m2, v2),
                ]
                for weights, gradient, first_moment, second_moment in adam_parameters:
                    first_moment[:] = (
                        self.beta1 * first_moment +
                        (1 - self.beta1) * gradient
                    )
                    second_moment[:] = (
                        self.beta2 * second_moment +
                        (1 - self.beta2) * (gradient ** 2)
                    )
                    corrected_first_moment = first_moment / (1 - self.beta1 ** self.t)
                    corrected_second_moment = second_moment / (1 - self.beta2 ** self.t)
                    weights[:] = np.clip(
                        weights - self.lr * (
                            corrected_first_moment /
                            (np.sqrt(corrected_second_moment) + self.eps) +
                            self.weight_decay * (weights - 50.0)
                        ),
                        0.1, 99.9)

            # Validation
            w1_eff = (w1 - 50.0) / 50.0
            w2_eff = (w2 - 50.0) / 50.0
            val_h = np.maximum(0, X_val @ w1_eff)
            val_logits = val_h @ w2_eff
            val_preds = np.argmax(val_logits, axis=1)
            val_acc = np.mean(val_preds == y_val)

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                best_w1, best_w2 = w1.copy(), w2.copy()

            if epoch % 10 == 0 or epoch == epochs - 1:
                print(f"      Epoch {epoch:3d}: val_acc={val_acc:.4f} (best={best_val_acc:.4f})")

        return best_w1, best_w2, best_val_acc


def play_match(lib, weights_a, weights_b, num_games=20, iters=500):
    """Play a match between two weight files. Returns (a_wins, draws, b_wins)."""
    a_wins, b_wins = 0, 0
    for game_index in range(num_games):
        board = np.zeros(NUM_CELLS, dtype=np.int8)
        new_board = (ct.c_int8 * NUM_CELLS)()
        current_player = 1
        consecutive_passes = 0
        move_count = 0
        ko_hash = 0

        if game_index % 2 == 0:
            black_weights, white_weights = weights_a, weights_b
            a_color = 'B'
        else:
            black_weights, white_weights = weights_b, weights_a
            a_color = 'W'

        while move_count < MAX_MOVES:
            if consecutive_passes >= 2:
                break
            active_weights = black_weights if current_player == 1 else white_weights
            lib.load_weights(active_weights)
            board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
            move = lib.mcts_search(
                board_ptr, ct.c_int8(current_player),
                ct.c_int(consecutive_passes), ct.c_int(move_count),
                ct.c_uint64(ko_hash), ct.c_int(iters), ct.c_double(0.7))
            if move == PASS_MOVE:
                consecutive_passes += 1
            else:
                consecutive_passes = 0
                ko_hash = board_hash_fnv(board)
                lib.apply_move_c(board_ptr, ct.c_int(move),
                                 ct.c_int8(current_player), new_board)
                board = np.frombuffer(new_board, dtype=np.int8).copy()
            current_player = -current_player
            move_count += 1

        board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
        black_score, white_score = score_position(board_2d)
        if black_score > white_score:
            winner = 'B'
        elif white_score > black_score:
            winner = 'W'
        else:
            winner = 'D'

        if winner == a_color:
            a_wins += 1
        elif winner != 'D':
            b_wins += 1

    draws = num_games - a_wins - b_wins
    return a_wins, draws, b_wins


def eval_vs_gnugo(lib, gnugo_cmd, gnugo_level, weights_path, num_games, mcts_iters):
    """Play evaluation games vs GnuGo (no data collection). Returns win rate."""
    gnugo = GTPProcess([gnugo_cmd, "--mode", "gtp", "--level", str(gnugo_level)])
    imc_wins = 0

    for game_index in range(num_games):
        gnugo.clear()
        board = np.zeros(NUM_CELLS, dtype=np.int8)
        new_board = (ct.c_int8 * NUM_CELLS)()
        current_player = 1
        consecutive_passes = 0
        move_count = 0
        ko_hash = 0
        imc_is_black = (game_index % 2 == 0)
        resigned = False

        while move_count < MAX_MOVES:
            if consecutive_passes >= 2:
                break
            is_imc = (current_player == 1 and imc_is_black) or \
                     (current_player == -1 and not imc_is_black)
            color_str = "black" if current_player == 1 else "white"

            if is_imc:
                lib.load_weights(weights_path)
                board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
                move = lib.mcts_search(
                    board_ptr, ct.c_int8(current_player),
                    ct.c_int(consecutive_passes), ct.c_int(move_count),
                    ct.c_uint64(ko_hash), ct.c_int(mcts_iters), ct.c_double(0.7))
                gtp_move = move_to_gtp(move)
                gnugo.play(color_str, gtp_move)
            else:
                gtp_move = gnugo.genmove(color_str)
                if gtp_move.upper() == "RESIGN":
                    resigned = True
                    break
                move = gtp_to_move(gtp_move)

            if move == PASS_MOVE:
                consecutive_passes += 1
            else:
                consecutive_passes = 0
                ko_hash = board_hash_fnv(board)
                board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
                lib.apply_move_c(board_ptr, ct.c_int(move),
                                 ct.c_int8(current_player), new_board)
                board = np.frombuffer(new_board, dtype=np.int8).copy()

            current_player = -current_player
            move_count += 1

        if resigned:
            outcome = 1.0 if current_player == -1 else 0.0
        else:
            board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
            black_score, white_score = score_position(board_2d)
            outcome = 1.0 if black_score > white_score else (
                0.5 if black_score == white_score else 0.0
            )

        imc_color_won = (outcome == 1.0 and imc_is_black) or \
                        (outcome == 0.0 and not imc_is_black)
        if imc_color_won:
            imc_wins += 1

    gnugo.stop()
    return imc_wins, num_games


def main():
    parser = argparse.ArgumentParser(description="Iterative Self-Play Training")
    parser.add_argument('--iterations', type=int, default=5,
                        help='Number of self-play/train iterations')
    parser.add_argument('--games', type=int, default=200,
                        help='Self-play games per iteration')
    parser.add_argument('--mcts-iters', type=int, default=200,
                        help='MCTS iterations per move during self-play')
    parser.add_argument('--train-epochs', type=int, default=50,
                        help='Training epochs per iteration')
    parser.add_argument('--match-games', type=int, default=20,
                        help='Match games between iterations')
    parser.add_argument('--match-iters', type=int, default=500,
                        help='MCTS iterations per move during matches')
    parser.add_argument('--output', type=str, default='weights/iterative',
                        help='Output directory')
    parser.add_argument('--seed-weights', type=str, default=None,
                        help='Path to initial weights.bin (None = random init)')
    parser.add_argument('--accumulate', action='store_true',
                        help='Accumulate data across iterations (not just latest)')
    parser.add_argument('--gnugo', type=str, default=None,
                        help='Path to GnuGo binary for sparring (optional)')
    parser.add_argument('--gnugo-level', type=int, default=1,
                        help='GnuGo level for sparring (1-10)')
    parser.add_argument('--sparring-games', type=int, default=50,
                        help='Number of sparring games vs GnuGo per iteration')
    parser.add_argument('--eval-games', type=int, default=0,
                        help='Eval games vs GnuGo after each iteration (0=skip)')
    parser.add_argument('--eval-mcts-iters', type=int, default=500,
                        help='MCTS iters for GnuGo evaluation games')
    parser.add_argument('--sparring-cmd', type=str, default=None,
                        help='GTP command for sparring opponent (e.g. "pachi --nopatterns -t ~500")')
    parser.add_argument('--sparring-name', type=str, default='Opponent',
                        help='Name of the sparring opponent (for logging)')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    lib = load_engine()
    trainer = CrossbarTrainerLite()

    # Initialize weights
    if args.seed_weights:
        load_status = lib.load_weights(args.seed_weights.encode())
        if load_status != 0:
            print(f"Failed to load seed weights: {args.seed_weights}")
            return
        # Load into numpy for training
        seed_pickle_path = args.seed_weights.replace('.bin', '.pkl')
        with open(seed_pickle_path, 'rb') as seed_file:
            seed = pickle.load(seed_file)
        w1 = np.array(seed['weights1'], dtype=np.float32)
        w2 = np.array(seed['weights2'], dtype=np.float32)
        print(f"Loaded seed weights: {args.seed_weights}")
    else:
        w1, w2 = trainer.init_weights()
        # Save initial random weights so C engine can load them
        export_bin(w1, w2, os.path.join(args.output, 'iter0.bin'))
        load_status = lib.load_weights(
            os.path.join(args.output, 'iter0.bin').encode()
        )
        print(f"Initialized random weights (load={load_status})")

    all_features_accum = []
    all_outcomes_accum = []
    results_log = []

    print(f"\n{'='*70}")
    print(f"ITERATIVE SELF-PLAY TRAINING")
    # Start GnuGo if available
    gnugo = None
    if args.gnugo:
        gnugo = GTPProcess([args.gnugo, "--mode", "gtp", "--level", str(args.gnugo_level)])
        print(f"  GnuGo sparring: {args.sparring_games} games/iter @ level {args.gnugo_level}")

    # Start generic sparring opponent if provided
    sparring_opponent = None
    if args.sparring_cmd:
        sparring_cmd = args.sparring_cmd.split()
        sparring_opponent = GTPProcess(sparring_cmd)
        print(f"  {args.sparring_name} sparring: {args.sparring_games} games/iter")
        print(f"    cmd: {args.sparring_cmd}")

    print(f"  Iterations: {args.iterations}")
    print(f"  Self-play games/iter: {args.games}, MCTS iters: {args.mcts_iters}")
    print(f"  Train epochs/iter: {args.train_epochs}")
    print(f"  Match: {args.match_games} games @ {args.match_iters} iters")
    print(f"  Accumulate data: {args.accumulate}")
    print(f"{'='*70}\n")

    for iteration in range(1, args.iterations + 1):
        print(f"--- Iteration {iteration}/{args.iterations} ---")

        # Save current weights for self-play
        current_weights_path = os.path.join(args.output, f'iter{iteration-1}.bin')
        if not os.path.exists(current_weights_path):
            export_bin(w1, w2, current_weights_path)
        lib.load_weights(current_weights_path.encode())

        # Phase 1a: Self-play data generation
        print(f"  [1/3] Self-play: {args.games} games @ {args.mcts_iters} MCTS iters")
        stage_start = time.time()
        features, outcomes, stats = generate_selfplay_data(
            lib, args.games, args.mcts_iters)
        stage_end = time.time()

        print(f"    Generated {len(features):,} positions in {stage_end-stage_start:.1f}s")
        print(f"    Games: B={stats['black_wins']} D={stats['draws']} W={stats['white_wins']} "
              f"(avg {stats['avg_game_length']:.0f} moves)")

        # Phase 1b: GnuGo sparring (if available)
        if gnugo and args.sparring_games > 0:
            print(f"  [1b/3] Sparring vs GnuGo-L{args.gnugo_level}: "
                  f"{args.sparring_games} games")
            stage_start = time.time()
            sparring_features, sparring_outcomes, imc_wins = generate_sparring_data(
                lib, gnugo, current_weights_path.encode(),
                args.sparring_games, args.mcts_iters)
            stage_end = time.time()
            print(f"    Sparring: {len(sparring_features):,} positions, "
                  f"IMC won {imc_wins}/{args.sparring_games} "
                  f"({imc_wins/args.sparring_games*100:.0f}%) in {stage_end-stage_start:.1f}s")
            features.extend(sparring_features)
            outcomes.extend(sparring_outcomes)

        # Phase 1c: Generic opponent sparring (e.g. Pachi)
        if sparring_opponent and args.sparring_games > 0:
            print(f"  [1c/3] Sparring vs {args.sparring_name}: "
                  f"{args.sparring_games} games")
            stage_start = time.time()
            sparring_features, sparring_outcomes, imc_wins = generate_sparring_data(
                lib, sparring_opponent, current_weights_path.encode(),
                args.sparring_games, args.mcts_iters)
            stage_end = time.time()
            print(f"    Sparring: {len(sparring_features):,} positions, "
                  f"IMC won {imc_wins}/{args.sparring_games} "
                  f"({imc_wins/args.sparring_games*100:.0f}%) in {stage_end-stage_start:.1f}s")
            features.extend(sparring_features)
            outcomes.extend(sparring_outcomes)

        if args.accumulate:
            all_features_accum.extend(features)
            all_outcomes_accum.extend(outcomes)
            train_features = all_features_accum
            train_outcomes = all_outcomes_accum
            print(f"    Accumulated: {len(train_features):,} total positions")
        else:
            train_features = features
            train_outcomes = outcomes

        # Phase 2: Train on self-play data
        print(f"  [2/3] Training: {args.train_epochs} epochs on {len(train_features):,} positions")
        stage_start = time.time()
        w1, w2, val_acc = trainer.train(
            train_features, train_outcomes, w1, w2,
            epochs=args.train_epochs, batch_size=256)
        stage_end = time.time()
        print(f"    Best val_acc: {val_acc:.4f} ({stage_end-stage_start:.1f}s)")

        # Save iteration weights
        iter_weights_path = os.path.join(args.output, f'iter{iteration}.bin')
        export_bin(w1, w2, iter_weights_path)
        checkpoint = {
            'weights1': w1.tolist(), 'weights2': w2.tolist(),
            'val_accuracy': float(val_acc), 'iteration': iteration,
            'input_size': 163, 'hidden_size': 96, 'output_size': 3,
        }
        iteration_pickle_path = os.path.join(args.output, f'iter{iteration}.pkl')
        with open(iteration_pickle_path, 'wb') as checkpoint_file:
            pickle.dump(checkpoint, checkpoint_file)

        # Phase 3: Match against previous iteration
        iter_result = {
            'iteration': iteration,
            'val_acc': float(val_acc),
            'selfplay_positions': len(features),
            'game_stats': stats,
        }

        if iteration >= 2:
            prev_weights = os.path.join(args.output, f'iter{iteration-1}.bin').encode()
            curr_weights = iter_weights_path.encode()
            print(f"  [3/4] Match: iter{iteration} vs iter{iteration-1} "
                  f"({args.match_games} games @ {args.match_iters} iters)")
            stage_start = time.time()
            a_wins, draws, b_wins = play_match(
                lib, curr_weights, prev_weights,
                args.match_games, args.match_iters)
            stage_end = time.time()
            print(f"    Result: iter{iteration} {a_wins}-{draws}-{b_wins} iter{iteration-1} "
                  f"({a_wins/args.match_games*100:.0f}% win rate, {stage_end-stage_start:.1f}s)")
            iter_result.update({
                'match_wins': a_wins, 'match_draws': draws, 'match_losses': b_wins,
                'win_rate': a_wins / args.match_games,
            })
        else:
            print(f"  [3/4] Match: skipped (first iteration)")

        # Phase 4: Evaluate vs GnuGo (if requested)
        if args.eval_games > 0 and args.gnugo:
            print(f"  [4/4] Eval vs GnuGo-L{args.gnugo_level}: "
                  f"{args.eval_games} games @ {args.eval_mcts_iters} MCTS iters")
            stage_start = time.time()
            eval_wins, eval_total = eval_vs_gnugo(
                lib, args.gnugo, args.gnugo_level,
                iter_weights_path.encode(), args.eval_games, args.eval_mcts_iters)
            stage_end = time.time()
            eval_pct = eval_wins / eval_total * 100
            print(f"    GnuGo eval: {eval_wins}/{eval_total} ({eval_pct:.0f}%) in {stage_end-stage_start:.1f}s")
            iter_result['gnugo_eval_wins'] = eval_wins
            iter_result['gnugo_eval_total'] = eval_total
            iter_result['gnugo_eval_pct'] = eval_pct
        else:
            print(f"  [4/4] GnuGo eval: skipped")

        results_log.append(iter_result)
        print()

    # Final: match iter_last vs iter0 (random)
    print(f"{'='*70}")
    print(f"FINAL MATCH: iter{args.iterations} vs iter0 (random)")
    last_weights = os.path.join(args.output, f'iter{args.iterations}.bin').encode()
    first_weights = os.path.join(args.output, 'iter0.bin').encode()
    a_wins, draws, b_wins = play_match(
        lib, last_weights, first_weights, 40, args.match_iters)
    print(f"  iter{args.iterations} {a_wins}-{draws}-{b_wins} iter0 "
          f"({a_wins/40*100:.0f}% win rate)")

    # Save best as the canonical weights
    export_bin(w1, w2, os.path.join(args.output, 'best_model.bin'))
    with open(os.path.join(args.output, 'best_model.pkl'), 'wb') as best_model_file:
        pickle.dump(checkpoint, best_model_file)

    # Save results log
    with open(os.path.join(args.output, 'training_log.json'), 'w') as log_file:
        json.dump(results_log, log_file, indent=2)

    # Cleanup
    if gnugo:
        gnugo.stop()
    if sparring_opponent:
        sparring_opponent.stop()

    print(f"\nDone! Weights saved to {args.output}/")
    print(f"Best model: {args.output}/best_model.bin")


if __name__ == '__main__':
    main()
