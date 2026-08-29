#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Train on mixed data: KataGo supervised + self-play.
Goal: combine KataGo's generalizable position knowledge with self-play's
tactical understanding to beat GnuGo.
"""

import ctypes as ct
import os
import json
import struct
import numpy as np
import pickle
import time
import subprocess
import sys

BOARD_SIZE = 9
NUM_CELLS = 81
PASS_MOVE = 81
MAX_MOVES = 200

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
from paths import GNUGO_BIN

LIB_PATH = os.path.join(_PROJECT_ROOT, 'engine', 'imc_mcts.so')


def load_engine():
    lib = ct.CDLL(LIB_PATH)
    lib.load_weights.argtypes = [ct.c_char_p]
    lib.load_weights.restype = ct.c_int
    lib.mcts_search.argtypes = [
        ct.POINTER(ct.c_int8), ct.c_int8, ct.c_int, ct.c_int,
        ct.c_uint64, ct.c_int, ct.c_double,
    ]
    lib.mcts_search.restype = ct.c_int
    lib.apply_move_c.argtypes = [ct.POINTER(ct.c_int8), ct.c_int, ct.c_int8, ct.POINTER(ct.c_int8)]
    lib.apply_move_c.restype = ct.c_int
    return lib


def board_hash_fnv(board):
    board_hash = 14695981039346656037
    for value in board.ravel():
        board_hash ^= int(value) & 0xFF
        board_hash = (board_hash * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return board_hash


def score_position(board, komi=6.5):
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
    flipped = []
    for feature_index in range(0, 162, 2):
        flipped.extend([
            features[feature_index + 1],
            features[feature_index]
        ])
    flipped.append(1.0 - features[162])
    return flipped


# ── Self-play data generation ──

def generate_selfplay_data(lib, weights_path, num_games, mcts_iters):
    """Play self-play games and collect training data."""
    lib.load_weights(weights_path)
    all_features = []
    all_outcomes = []

    for game_index in range(num_games):
        board = np.zeros(NUM_CELLS, dtype=np.int8)
        new_board = (ct.c_int8 * NUM_CELLS)()
        current_player = 1
        consecutive_passes, move_count, ko_hash = 0, 0, 0
        positions = []

        while move_count < MAX_MOVES and consecutive_passes < 2:
            features = board_to_features(board, current_player)
            positions.append((features, current_player))

            board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
            move = lib.mcts_search(
                board_ptr, ct.c_int8(current_player),
                ct.c_int(consecutive_passes), ct.c_int(move_count),
                ct.c_uint64(ko_hash), ct.c_int(mcts_iters), ct.c_double(0.7)
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

        board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
        black_score, white_score = score_position(board_2d)
        if black_score > white_score:
            outcome = 1.0
        elif white_score > black_score:
            outcome = 0.0
        else:
            outcome = 0.5

        for features, player in positions:
            all_features.append(features)
            all_outcomes.append(outcome)
            # Color-flip augmentation
            flipped_features = color_flip_features(features)
            all_features.append(flipped_features)
            all_outcomes.append(1.0 - outcome)

        if (game_index + 1) % 20 == 0:
            print(f"    Self-play game {game_index+1}/{num_games}")

    return all_features, all_outcomes


# ── GnuGo sparring data generation ──

COL_LETTERS = "ABCDEFGHJKLMNOPQRST"

def move_to_gtp(m):
    if m == PASS_MOVE:
        return "pass"
    return f"{COL_LETTERS[m % BOARD_SIZE]}{BOARD_SIZE - m // BOARD_SIZE}"

def gtp_to_move(s):
    s = s.strip().upper()
    if s in ("PASS", "RESIGN"):
        return PASS_MOVE
    return (BOARD_SIZE - int(s[1:])) * BOARD_SIZE + COL_LETTERS.index(s[0])


class GnuGoProcess:
    def __init__(self, level=10):
        self.proc = subprocess.Popen(
            [GNUGO_BIN, "--mode", "gtp", "--level", str(level)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True, bufsize=1)
        self._send("boardsize 9")
        self._send("clear_board")
        self._send("komi 6.5")

    def _send(self, cmd):
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()
        response_lines = []
        first_line = True
        while True:
            line = self.proc.stdout.readline()
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

    def new_game(self):
        self._send("clear_board")

    def play(self, color, move):
        self._send(f"play {color} {move}")

    def genmove(self, color):
        response = self._send(f"genmove {color}")
        return response.strip().split()[0] if response.strip() else "pass"

    def stop(self):
        try:
            self._send("quit")
            self.proc.terminate()
        except:
            pass


def generate_gnugo_sparring_data(lib, weights_path, num_games, mcts_iters, gnugo_level=1):
    """Play games vs GnuGo and collect training data from IMC's positions."""
    gnugo = GnuGoProcess(level=gnugo_level)
    all_features = []
    all_outcomes = []
    wins = 0

    for game_index in range(num_games):
        gnugo.new_game()
        lib.load_weights(weights_path)
        board = np.zeros(NUM_CELLS, dtype=np.int8)
        new_board = (ct.c_int8 * NUM_CELLS)()
        consecutive_passes = 0
        move_count = 0
        ko_hash = 0
        imc_is_black = (game_index % 2 == 0)
        positions = []  # Only IMC's positions
        resigned = False

        while move_count < MAX_MOVES and consecutive_passes < 2:
            black_turn = (move_count % 2 == 0)
            imc_turn = (black_turn == imc_is_black)
            color = "black" if black_turn else "white"
            current_player = 1 if black_turn else -1

            if imc_turn:
                # Record IMC's position
                features = board_to_features(board, current_player)
                positions.append((features, current_player))

                board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
                move = lib.mcts_search(
                    board_ptr, ct.c_int8(current_player),
                    ct.c_int(consecutive_passes), ct.c_int(move_count),
                    ct.c_uint64(ko_hash), ct.c_int(mcts_iters),
                    ct.c_double(0.7)
                )
                gtp_move = move_to_gtp(move)
                gnugo.play(color, gtp_move)
            else:
                gtp_move = gnugo.genmove(color)
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
                lib.apply_move_c(
                    board_ptr, ct.c_int(move),
                    ct.c_int8(current_player), new_board
                )
                board = np.frombuffer(new_board, dtype=np.int8).copy()
            move_count += 1

        # Determine outcome from Black's perspective
        if resigned:
            outcome = 1.0  # GnuGo resigned, IMC wins
            wins += 1
        else:
            board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
            black_score, white_score = score_position(board_2d)
            if black_score > white_score:
                outcome = 1.0
            elif white_score > black_score:
                outcome = 0.0
            else:
                outcome = 0.5
            if ((imc_is_black and black_score > white_score) or
                    (not imc_is_black and white_score > black_score)):
                wins += 1

        # Add positions with game outcome
        for features, player in positions:
            all_features.append(features)
            all_outcomes.append(outcome)
            flipped_features = color_flip_features(features)
            all_features.append(flipped_features)
            all_outcomes.append(1.0 - outcome)

        if (game_index + 1) % 10 == 0:
            print(f"    GnuGo sparring {game_index+1}/{num_games} (wins: {wins})")

    gnugo.stop()
    print(f"    GnuGo sparring done: {wins}/{num_games} wins ({wins/num_games*100:.0f}%)")
    return all_features, all_outcomes


# ── Training ──

class CrossbarTrainer:
    def __init__(self, input_size=163, hidden_size=96, output_size=3, lr=0.003):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.lr = lr
        self.beta1, self.beta2, self.eps = 0.9, 0.999, 1e-8
        self.weight_decay = 0.001
        self.t = 0

    def init_weights(self, fin, fout):
        xavier_std = np.sqrt(2.0 / (fin + fout))
        weights = 50.0 + np.random.normal(0, xavier_std, (fin, fout)) * 50.0
        return np.clip(weights, 0.1, 99.9).astype(np.float32)

    def forward(self, x, w):
        return np.dot(x, (w - 50.0) / 50.0)

    @staticmethod
    def relu(x):
        return np.maximum(0, x)

    @staticmethod
    def relu_d(x):
        return (x > 0).astype(np.float32)

    @staticmethod
    def softmax(x):
        exponentials = np.exp(x - np.max(x, axis=1, keepdims=True))
        return exponentials / np.sum(exponentials, axis=1, keepdims=True)

    def adamw(self, w, g, lr, m, v):
        m[:] = self.beta1 * m + (1 - self.beta1) * g
        v[:] = self.beta2 * v + (1 - self.beta2) * g**2
        corrected_first_moment = m / (1 - self.beta1**self.t)
        corrected_second_moment = v / (1 - self.beta2**self.t)
        w = w - lr * (
            corrected_first_moment /
            (np.sqrt(corrected_second_moment) + self.eps) +
            self.weight_decay * (w - 50.0)
        )
        return np.clip(w, 0.1, 99.9)

    @staticmethod
    def export_bin(w1, w2, path):
        w1_f64 = np.array(w1, dtype=np.float64)
        w2_f64 = np.array(w2, dtype=np.float64)
        with open(path, 'wb') as output_handle:
            output_handle.write(struct.pack('ii', w1_f64.shape[0], w1_f64.shape[1]))
            output_handle.write(w1_f64.tobytes())
            output_handle.write(struct.pack('ii', w2_f64.shape[0], w2_f64.shape[1]))
            output_handle.write(w2_f64.tobytes())

    def train(self, positions, labels, output_path, seed_weights=None,
              epochs=1000, batch=256, patience=150):
        num_positions = len(positions)
        shuffled_indices = np.random.permutation(num_positions)
        num_validation = int(num_positions * 0.15)
        validation_positions = positions[shuffled_indices[:num_validation]]
        validation_labels = labels[shuffled_indices[:num_validation]]
        train_positions = positions[shuffled_indices[num_validation:]]
        train_labels = labels[shuffled_indices[num_validation:]]

        if seed_weights:
            with open(seed_weights, 'rb') as seed_handle:
                seed_checkpoint = pickle.load(seed_handle)
            w1 = np.array(seed_checkpoint['weights1'], dtype=np.float32)
            w2 = np.array(seed_checkpoint['weights2'], dtype=np.float32)
            print(f"  Seeded from {seed_weights}")
        else:
            w1 = self.init_weights(self.input_size, self.hidden_size)
            w2 = self.init_weights(self.hidden_size, self.output_size)

        m1, v1 = np.zeros_like(w1), np.zeros_like(w1)
        m2, v2 = np.zeros_like(w2), np.zeros_like(w2)
        self.t = 0
        best_val_acc = 0.0
        no_improve = 0
        current_lr = self.lr

        print(f"  Training: {len(train_positions):,} train, {len(validation_positions):,} val, epochs={epochs}")

        for epoch in range(epochs):
            if no_improve > 0 and no_improve % 50 == 0 and current_lr > 1e-6:
                current_lr *= 0.8

            shuffled_train_indices = np.random.permutation(len(train_positions))
            shuffled_positions = train_positions[shuffled_train_indices]
            shuffled_labels = train_labels[shuffled_train_indices]
            epoch_loss = 0.0
            epoch_correct = 0

            for batch_start in range(0, len(train_positions), batch):
                batch_positions = shuffled_positions[batch_start:batch_start + batch]
                batch_labels = shuffled_labels[batch_start:batch_start + batch]
                current_batch_size = len(batch_positions)

                hidden = self.forward(batch_positions, w1)
                activated_hidden = self.relu(hidden)
                # Dropout
                dropout_mask = (
                    np.random.random(activated_hidden.shape) > 0.15
                ).astype(np.float32)
                dropped_hidden = activated_hidden * dropout_mask / 0.85
                logits = self.forward(dropped_hidden, w2)
                probabilities = self.softmax(logits)

                clipped_probabilities = np.clip(probabilities, 1e-15, 1-1e-15)
                one_hot = np.eye(self.output_size)[batch_labels]
                smoothed_targets = one_hot * 0.9 + 0.1 / self.output_size
                loss = -np.mean(
                    np.sum(smoothed_targets * np.log(clipped_probabilities), axis=1)
                )
                epoch_loss += loss * current_batch_size
                epoch_correct += np.sum(
                    np.argmax(probabilities, axis=1) == batch_labels
                )

                output_gradient = (
                    probabilities - smoothed_targets
                ) / current_batch_size
                w2_gradient = np.dot(dropped_hidden.T, output_gradient) / 50.0
                hidden_gradient = np.dot(
                    output_gradient, ((w2 - 50.0) / 50.0).T
                )
                hidden_gradient *= dropout_mask / 0.85
                hidden_gradient *= self.relu_d(hidden)
                w1_gradient = np.dot(batch_positions.T, hidden_gradient) / 50.0

                for gradient in [w1_gradient, w2_gradient]:
                    gradient_norm = np.linalg.norm(gradient)
                    if gradient_norm > 5.0:
                        gradient *= 5.0 / gradient_norm

                self.t += 1
                w1 = self.adamw(w1, w1_gradient, current_lr, m1, v1)
                w2 = self.adamw(w2, w2_gradient, current_lr, m2, v2)

            # Validation
            validation_hidden = self.forward(validation_positions, w1)
            activated_validation_hidden = self.relu(validation_hidden)
            validation_logits = self.forward(activated_validation_hidden, w2)
            validation_probabilities = self.softmax(validation_logits)
            val_acc = np.mean(
                np.argmax(validation_probabilities, axis=1) == validation_labels
            )
            train_acc = epoch_correct / len(train_positions)

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                no_improve = 0
                self.export_bin(w1, w2, output_path)
                checkpoint = {
                    'weights1': w1.tolist(), 'weights2': w2.tolist(),
                    'val_accuracy': float(val_acc), 'input_size': self.input_size,
                    'hidden_size': self.hidden_size, 'output_size': self.output_size,
                }
                with open(output_path.replace('.bin', '.pkl'), 'wb') as checkpoint_handle:
                    pickle.dump(checkpoint, checkpoint_handle)
            else:
                no_improve += 1

            if epoch % 50 == 0 or no_improve == 0:
                print(f"    Epoch {epoch:4d}: train={train_acc:.4f} val={val_acc:.4f} "
                      f"best={best_val_acc:.4f} lr={current_lr:.6f}")

            if no_improve >= patience:
                print(f"    Early stop at epoch {epoch}")
                break

        print(f"  Best val accuracy: {best_val_acc:.4f}")
        return best_val_acc


# ── Eval vs GnuGo ──

def eval_vs_gnugo(weights_path, num_games=20, mcts_iters=500, level=1):
    lib = load_engine()
    gnugo = GnuGoProcess(level=level)
    wins = 0

    for game_index in range(num_games):
        gnugo.new_game()
        lib.load_weights(weights_path)
        board = np.zeros(NUM_CELLS, dtype=np.int8)
        new_board = (ct.c_int8 * NUM_CELLS)()
        consecutive_passes = 0
        move_count = 0
        ko_hash = 0
        imc_is_black = (game_index % 2 == 0)
        resigned = False

        while move_count < MAX_MOVES and consecutive_passes < 2:
            black_turn = (move_count % 2 == 0)
            imc_turn = (black_turn == imc_is_black)
            color = "black" if black_turn else "white"
            current_player = 1 if black_turn else -1

            if imc_turn:
                lib.load_weights(weights_path)
                board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
                move = lib.mcts_search(
                    board_ptr, ct.c_int8(current_player),
                    ct.c_int(consecutive_passes), ct.c_int(move_count),
                    ct.c_uint64(ko_hash), ct.c_int(mcts_iters),
                    ct.c_double(0.7)
                )
                gtp_move = move_to_gtp(move)
                gnugo.play(color, gtp_move)
            else:
                gtp_move = gnugo.genmove(color)
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
                lib.apply_move_c(
                    board_ptr, ct.c_int(move),
                    ct.c_int8(current_player), new_board
                )
                board = np.frombuffer(new_board, dtype=np.int8).copy()
            move_count += 1

        if resigned:
            wins += 1
        else:
            board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
            black_score, white_score = score_position(board_2d)
            if ((imc_is_black and black_score > white_score) or
                    (not imc_is_black and white_score > black_score)):
                wins += 1

    gnugo.stop()
    return wins, num_games


def main():
    print("=" * 65)
    print("  Mixed Training: KataGo supervised + Self-play + GnuGo sparring")
    print("=" * 65)

    lib = load_engine()
    strong_weights = b"weights/final/strong.bin"
    strong_pkl = "weights/final/strong.pkl"
    output_dir = "weights/mixed"
    os.makedirs(output_dir, exist_ok=True)

    # ── Phase 1: Load KataGo data ──
    print("\n[Phase 1] Loading KataGo supervised data...")
    with open("training_data_katago_200k_163.json") as dataset_handle:
        katago = json.load(dataset_handle)
    katago_pos = np.array(katago['positions'], dtype=np.float32)
    katago_out = np.array(katago['game_outcomes'])
    katago_labels = np.ones(len(katago_out), dtype=int)
    katago_labels[katago_out < 0.35] = 0
    katago_labels[katago_out > 0.65] = 2
    print(f"  KataGo: {len(katago_pos):,} positions")
    print(f"  Classes: W={np.sum(katago_labels==0):,} D={np.sum(katago_labels==1):,} B={np.sum(katago_labels==2):,}")

    # ── Phase 2: Generate self-play data ──
    print("\n[Phase 2] Generating self-play data (100 games, 200 iters)...")
    lib.load_weights(strong_weights)
    stage_start = time.time()
    selfplay_features, selfplay_outcomes = generate_selfplay_data(
        lib, strong_weights, 100, 200
    )
    print(f"  Self-play: {len(selfplay_features):,} positions ({time.time()-stage_start:.0f}s)")

    selfplay_positions = np.array(selfplay_features, dtype=np.float32)
    selfplay_labels = np.ones(len(selfplay_outcomes), dtype=int)
    selfplay_outcomes_array = np.array(selfplay_outcomes)
    selfplay_labels[selfplay_outcomes_array < 0.35] = 0
    selfplay_labels[selfplay_outcomes_array > 0.65] = 2
    print(f"  Classes: W={np.sum(selfplay_labels==0):,} D={np.sum(selfplay_labels==1):,} B={np.sum(selfplay_labels==2):,}")

    # ── Phase 3: Generate GnuGo sparring data ──
    print("\n[Phase 3] Generating GnuGo sparring data (60 games vs L1, 200 iters)...")
    stage_start = time.time()
    gnugo_features, gnugo_outcomes = generate_gnugo_sparring_data(
        lib, strong_weights, 60, 200, gnugo_level=1)
    print(f"  GnuGo sparring: {len(gnugo_features):,} positions ({time.time()-stage_start:.0f}s)")

    gnugo_positions = np.array(gnugo_features, dtype=np.float32)
    gnugo_labels = np.ones(len(gnugo_outcomes), dtype=int)
    gnugo_outcomes_array = np.array(gnugo_outcomes)
    gnugo_labels[gnugo_outcomes_array < 0.35] = 0
    gnugo_labels[gnugo_outcomes_array > 0.65] = 2

    # ── Phase 4: Mix datasets ──
    # Weight: 50% KataGo, 25% self-play, 25% GnuGo sparring (by sampling)
    print("\n[Phase 4] Mixing datasets...")
    # Subsample KataGo to balance
    target_katago = 100000  # 100k from KataGo
    katago_indices = np.random.choice(
        len(katago_pos), min(target_katago, len(katago_pos)), replace=False
    )

    all_positions = np.concatenate([
        katago_pos[katago_indices], selfplay_positions, gnugo_positions
    ])
    all_labels = np.concatenate([
        katago_labels[katago_indices], selfplay_labels, gnugo_labels
    ])
    print(f"  Mixed dataset: {len(all_positions):,} positions")
    print(f"  Classes: W={np.sum(all_labels==0):,} D={np.sum(all_labels==1):,} B={np.sum(all_labels==2):,}")

    # ── Phase 5: Train ──
    print("\n[Phase 5] Training mixed model (seeded from strong)...")
    trainer = CrossbarTrainer(lr=0.002)
    output_path = os.path.join(output_dir, "mixed_v1.bin")
    trainer.train(all_positions, all_labels, output_path,
                  seed_weights=strong_pkl, epochs=1000, patience=150)

    # ── Phase 6: Also train from scratch ──
    print("\n[Phase 6] Training mixed model from scratch...")
    output_path2 = os.path.join(output_dir, "mixed_v2.bin")
    trainer2 = CrossbarTrainer(lr=0.003)
    trainer2.train(all_positions, all_labels, output_path2,
                   seed_weights=None, epochs=1500, patience=200)

    # ── Phase 7: Evaluate ──
    print("\n[Phase 7] Evaluating vs GnuGo L1 (20 games each)...")
    for name, path in [("mixed_v1 (seeded)", b"weights/mixed/mixed_v1.bin"),
                        ("mixed_v2 (scratch)", b"weights/mixed/mixed_v2.bin"),
                        ("current strong", strong_weights)]:
        wins, num_games = eval_vs_gnugo(path, 20, 500, level=1)
        print(f"  {name:25s}: {wins}/{num_games} = {wins/num_games*100:.0f}% vs GnuGo L1")

    print("\nEvaluating vs GnuGo L10 (20 games each)...")
    for name, path in [("mixed_v1 (seeded)", b"weights/mixed/mixed_v1.bin"),
                        ("mixed_v2 (scratch)", b"weights/mixed/mixed_v2.bin"),
                        ("current strong", strong_weights)]:
        wins, num_games = eval_vs_gnugo(path, 20, 500, level=10)
        print(f"  {name:25s}: {wins}/{num_games} = {wins/num_games*100:.0f}% vs GnuGo L10")

    print("\n" + "=" * 65)
    print("  Done!")
    print("=" * 65)


if __name__ == "__main__":
    main()
