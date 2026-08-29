#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Iterative mixed training: KataGo + heavy GnuGo sparring.
Each iteration: spar vs GnuGo L1, mix with KataGo data, retrain.
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
COL_LETTERS = "ABCDEFGHJKLMNOPQRST"

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
    def __init__(self, level=1):
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


def spar_vs_gnugo(lib, weights_path, num_games, mcts_iters, gnugo_level=1):
    """Play games vs GnuGo, collect ALL positions (both sides)."""
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
        positions = []  # ALL positions, both players
        resigned = False

        while move_count < MAX_MOVES and consecutive_passes < 2:
            black_turn = (move_count % 2 == 0)
            imc_turn = (black_turn == imc_is_black)
            current_player = 1 if black_turn else -1

            # Record EVERY position
            features = board_to_features(board, current_player)
            positions.append((features, current_player))

            if imc_turn:
                color = "black" if black_turn else "white"
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
                color = "black" if black_turn else "white"
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
            outcome = 1.0  # IMC wins (GnuGo resigned)
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

        for features, player in positions:
            all_features.append(features)
            all_outcomes.append(outcome)
            flipped_features = color_flip_features(features)
            all_features.append(flipped_features)
            all_outcomes.append(1.0 - outcome)

        if (game_index + 1) % 20 == 0:
            print(f"      Sparring {game_index+1}/{num_games} (wins: {wins})")

    gnugo.stop()
    return all_features, all_outcomes, wins


def export_bin(w1, w2, path):
    w1_f64 = np.array(w1, dtype=np.float64)
    w2_f64 = np.array(w2, dtype=np.float64)
    with open(path, 'wb') as output_handle:
        output_handle.write(struct.pack('ii', w1_f64.shape[0], w1_f64.shape[1]))
        output_handle.write(w1_f64.tobytes())
        output_handle.write(struct.pack('ii', w2_f64.shape[0], w2_f64.shape[1]))
        output_handle.write(w2_f64.tobytes())


def train_model(positions, labels, output_path, seed_pkl=None, epochs=800, patience=150, lr=0.002):
    input_size = 163
    hidden_size = 96
    output_size = 3
    num_positions = len(positions)
    shuffled_indices = np.random.permutation(num_positions)
    num_validation = int(num_positions * 0.15)
    validation_positions = positions[shuffled_indices[:num_validation]]
    validation_labels = labels[shuffled_indices[:num_validation]]
    train_positions = positions[shuffled_indices[num_validation:]]
    train_labels = labels[shuffled_indices[num_validation:]]

    if seed_pkl and os.path.exists(seed_pkl):
        with open(seed_pkl, 'rb') as seed_handle:
            seed_checkpoint = pickle.load(seed_handle)
        w1 = np.array(seed_checkpoint['weights1'], dtype=np.float32)
        w2 = np.array(seed_checkpoint['weights2'], dtype=np.float32)
    else:
        w1_std = np.sqrt(2.0 / (input_size + hidden_size))
        w1 = np.clip(
            50.0 + np.random.normal(
                0, w1_std, (input_size, hidden_size)
            ) * 50.0,
            0.1, 99.9
        ).astype(np.float32)
        w2_std = np.sqrt(2.0 / (hidden_size + output_size))
        w2 = np.clip(
            50.0 + np.random.normal(
                0, w2_std, (hidden_size, output_size)
            ) * 50.0,
            0.1, 99.9
        ).astype(np.float32)

    m1, v1 = np.zeros_like(w1), np.zeros_like(w1)
    m2, v2 = np.zeros_like(w2), np.zeros_like(w2)
    beta1 = 0.9
    beta2 = 0.999
    eps = 1e-8
    weight_decay = 0.001
    adam_step = 0
    best_val_acc = 0.0
    no_improve = 0
    current_lr = lr
    batch_size = 256

    for epoch in range(epochs):
        if no_improve > 0 and no_improve % 50 == 0 and current_lr > 1e-6:
            current_lr *= 0.8
        shuffled_train_indices = np.random.permutation(len(train_positions))
        shuffled_positions = train_positions[shuffled_train_indices]
        shuffled_labels = train_labels[shuffled_train_indices]
        epoch_correct = 0

        for batch_start in range(0, len(train_positions), batch_size):
            batch_positions = shuffled_positions[
                batch_start:batch_start + batch_size
            ]
            batch_labels = shuffled_labels[
                batch_start:batch_start + batch_size
            ]
            current_batch_size = len(batch_positions)

            hidden = np.dot(batch_positions, (w1 - 50.0) / 50.0)
            activated_hidden = np.maximum(0, hidden)
            dropout_mask = (
                np.random.random(activated_hidden.shape) > 0.15
            ).astype(np.float32)
            dropped_hidden = activated_hidden * dropout_mask / 0.85
            logits = np.dot(dropped_hidden, (w2 - 50.0) / 50.0)
            exponentials = np.exp(
                logits - np.max(logits, axis=1, keepdims=True)
            )
            probabilities = exponentials / np.sum(
                exponentials, axis=1, keepdims=True
            )
            epoch_correct += np.sum(
                np.argmax(probabilities, axis=1) == batch_labels
            )

            one_hot = np.eye(output_size)[batch_labels]
            smoothed_targets = one_hot * 0.9 + 0.1 / output_size
            output_gradient = (
                probabilities - smoothed_targets
            ) / current_batch_size
            w2_gradient = np.dot(dropped_hidden.T, output_gradient) / 50.0
            hidden_gradient = (
                np.dot(output_gradient, ((w2 - 50.0) / 50.0).T) *
                dropout_mask / 0.85 *
                (hidden > 0).astype(np.float32)
            )
            w1_gradient = np.dot(batch_positions.T, hidden_gradient) / 50.0

            for gradient in [w1_gradient, w2_gradient]:
                gradient_norm = np.linalg.norm(gradient)
                if gradient_norm > 5.0:
                    gradient *= 5.0 / gradient_norm

            adam_step += 1
            for weights, gradient, first_moment, second_moment in [
                (w1, w1_gradient, m1, v1),
                (w2, w2_gradient, m2, v2),
            ]:
                first_moment[:] = beta1 * first_moment + (1 - beta1) * gradient
                second_moment[:] = beta2 * second_moment + (1 - beta2) * gradient**2
                corrected_first_moment = first_moment / (1 - beta1**adam_step)
                corrected_second_moment = second_moment / (1 - beta2**adam_step)
                weights[:] = np.clip(
                    weights - current_lr * (
                        corrected_first_moment /
                        (np.sqrt(corrected_second_moment) + eps) +
                        weight_decay * (weights - 50.0)
                    ),
                    0.1, 99.9
                )

        # Validation
        validation_hidden = np.maximum(
            0, np.dot(validation_positions, (w1 - 50.0) / 50.0)
        )
        validation_logits = np.dot(
            validation_hidden, (w2 - 50.0) / 50.0
        )
        validation_exponentials = np.exp(
            validation_logits -
            np.max(validation_logits, axis=1, keepdims=True)
        )
        validation_probabilities = validation_exponentials / np.sum(
            validation_exponentials, axis=1, keepdims=True
        )
        val_acc = np.mean(
            np.argmax(validation_probabilities, axis=1) == validation_labels
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            no_improve = 0
            export_bin(w1, w2, output_path)
            with open(output_path.replace('.bin', '.pkl'), 'wb') as checkpoint_handle:
                pickle.dump({'weights1': w1.tolist(), 'weights2': w2.tolist(),
                            'val_accuracy': float(val_acc)}, checkpoint_handle)
        else:
            no_improve += 1

        if epoch % 100 == 0:
            print(f"      Epoch {epoch:4d}: val={val_acc:.4f} best={best_val_acc:.4f}")

        if no_improve >= patience:
            break

    print(f"      Best val: {best_val_acc:.4f}")
    return best_val_acc


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
    return wins


def main():
    print("=" * 65)
    print("  Iterative Mixed Training: KataGo + GnuGo Sparring")
    print("=" * 65)

    lib = load_engine()
    output_dir = "weights/mixed_v2"
    os.makedirs(output_dir, exist_ok=True)

    # Load KataGo data once
    print("\nLoading KataGo data...")
    with open("training_data_katago_200k_163.json") as dataset_handle:
        katago = json.load(dataset_handle)
    katago_pos = np.array(katago['positions'], dtype=np.float32)
    katago_out = np.array(katago['game_outcomes'])
    katago_labels = np.ones(len(katago_out), dtype=int)
    katago_labels[katago_out < 0.35] = 0
    katago_labels[katago_out > 0.65] = 2
    print(f"  KataGo: {len(katago_pos):,} positions")

    # Start from mixed_v1 (the model that got 40% vs L1)
    current_weights = b"weights/mixed/mixed_v1.bin"
    current_pkl = "weights/mixed/mixed_v1.pkl"

    num_iterations = 5
    sparring_games = 100  # More games per iteration
    mcts_iters = 200

    for iteration in range(num_iterations):
        print(f"\n{'='*50}")
        print(f"  Iteration {iteration+1}/{num_iterations}")
        print(f"{'='*50}")

        # Phase 1: Spar vs GnuGo L1
        print(f"\n  [Sparring] {sparring_games} games vs GnuGo L1...")
        stage_start = time.time()
        spar_features, spar_outcomes, spar_wins = spar_vs_gnugo(
            lib, current_weights, sparring_games, mcts_iters, gnugo_level=1)
        print(f"    Won {spar_wins}/{sparring_games} ({spar_wins/sparring_games*100:.0f}%) in {time.time()-stage_start:.0f}s")
        print(f"    Collected {len(spar_features):,} positions")

        sparring_positions = np.array(spar_features, dtype=np.float32)
        sparring_labels = np.ones(len(spar_outcomes), dtype=int)
        sparring_outcomes_array = np.array(spar_outcomes)
        sparring_labels[sparring_outcomes_array < 0.35] = 0
        sparring_labels[sparring_outcomes_array > 0.65] = 2

        # Phase 2: Also spar vs GnuGo L10 (fewer games)
        print(f"\n  [Sparring] 40 games vs GnuGo L10...")
        stage_start = time.time()
        level10_features, level10_outcomes, level10_wins = spar_vs_gnugo(
            lib, current_weights, 40, mcts_iters, gnugo_level=10)
        print(f"    Won {level10_wins}/40 ({level10_wins/40*100:.0f}%) in {time.time()-stage_start:.0f}s")

        level10_positions = np.array(level10_features, dtype=np.float32)
        level10_labels = np.ones(len(level10_outcomes), dtype=int)
        level10_outcomes_array = np.array(level10_outcomes)
        level10_labels[level10_outcomes_array < 0.35] = 0
        level10_labels[level10_outcomes_array > 0.65] = 2

        # Phase 3: Mix data (70% KataGo + 30% sparring)
        # Subsample KataGo to keep total manageable
        katago_indices = np.random.choice(len(katago_pos), 80000, replace=False)
        all_positions = np.concatenate([
            katago_pos[katago_indices], sparring_positions, level10_positions
        ])
        all_labels = np.concatenate([
            katago_labels[katago_indices], sparring_labels, level10_labels
        ])
        print(f"\n  [Training] Mixed dataset: {len(all_positions):,} positions")

        # Phase 4: Train (seeded from current model)
        iteration_path = os.path.join(output_dir, f"iter{iteration}.bin")
        train_model(all_positions, all_labels, iteration_path, seed_pkl=current_pkl,
                    epochs=600, patience=100, lr=0.002)

        current_weights = iteration_path.encode()
        current_pkl = iteration_path.replace('.bin', '.pkl')

        # Phase 5: Quick eval
        print(f"\n  [Eval] vs GnuGo L1 (20 games, 500 iters)...")
        level1_wins = eval_vs_gnugo(current_weights, 20, 500, level=1)
        print(f"    Result: {level1_wins}/20 = {level1_wins/20*100:.0f}% vs L1")

        print(f"  [Eval] vs GnuGo L10 (20 games, 500 iters)...")
        level10_wins = eval_vs_gnugo(current_weights, 20, 500, level=10)
        print(f"    Result: {level10_wins}/20 = {level10_wins/20*100:.0f}% vs L10")

    print(f"\n{'='*65}")
    print("  Final Results")
    print(f"{'='*65}")

    # Final eval with more games
    best_path = os.path.join(output_dir, f"iter{num_iterations-1}.bin").encode()
    print(f"\nFinal model vs GnuGo L1 (20 games)...")
    level1_wins = eval_vs_gnugo(best_path, 20, 500, level=1)
    print(f"  {level1_wins}/20 = {level1_wins/20*100:.0f}%")

    print(f"Final model vs GnuGo L10 (20 games)...")
    level10_wins = eval_vs_gnugo(best_path, 20, 500, level=10)
    print(f"  {level10_wins}/20 = {level10_wins/20*100:.0f}%")

    # Copy best to final
    import shutil
    shutil.copy2(os.path.join(output_dir, f"iter{num_iterations-1}.bin"),
                 "weights/final/strong.bin")
    shutil.copy2(os.path.join(output_dir, f"iter{num_iterations-1}.pkl"),
                 "weights/final/strong.pkl")
    print(f"\nCopied best model to weights/final/strong.bin")


if __name__ == "__main__":
    main()
