#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Trainer for 163->96->1 Crossbar Neural Network (regression mode).

Predicts Black's win probability as a continuous value in [0, 1].
Uses sigmoid output + MSE loss instead of 3-class softmax + cross-entropy.

Architecture: 163 inputs -> 96 hidden (ReLU) -> 1 output (sigmoid)
  - Differential-pair normalization: W_eff = (G - 50) / 50
  - Conductance range: [0.1, 99.9] nS
"""

import os
import json
import numpy as np
import pickle
import struct
import argparse
import time
from typing import Tuple


class CrossbarRegressionTrainer:
    """Train 2-layer memristor crossbar NN for Go win probability regression."""

    def __init__(self, board_size: int = 9, hidden_size: int = 96,
                 learning_rate: float = 0.003):
        self.board_size = board_size
        self.input_size = board_size * board_size * 2 + 1  # 163 (2 channels + turn bit)
        self.hidden_size = hidden_size
        self.output_size = 1
        self.learning_rate = learning_rate

        # AdamW parameters
        self.beta1 = 0.9
        self.beta2 = 0.999
        self.eps = 1e-8
        self.weight_decay = 0.001
        self.t = 0

        print(f"CrossbarRegressionTrainer: {self.input_size} -> {self.hidden_size} -> 1 (sigmoid)")

    def initialize_weights(self, fan_in: int, fan_out: int) -> np.ndarray:
        """Xavier/Glorot init mapped to conductance range [0.1, 99.9]."""
        xavier_std = np.sqrt(2.0 / (fan_in + fan_out))
        weights = 50.0 + np.random.normal(
            0,
            xavier_std,
            (fan_in, fan_out)
        ) * 50.0
        return np.clip(weights, 0.1, 99.9).astype(np.float32)

    @staticmethod
    def sigmoid(x: np.ndarray) -> np.ndarray:
        """Numerically stable sigmoid."""
        positive_mask = x >= 0
        output = np.zeros_like(x)
        output[positive_mask] = 1.0 / (1.0 + np.exp(-x[positive_mask]))
        exponentials = np.exp(x[~positive_mask])
        output[~positive_mask] = exponentials / (1.0 + exponentials)
        return output

    def adamw_update(self, weights, gradients, lr, m, v):
        """AdamW update with regularization toward center conductance (50)."""
        m[:] = self.beta1 * m + (1 - self.beta1) * gradients
        v[:] = self.beta2 * v + (1 - self.beta2) * (gradients ** 2)
        corrected_first_moment = m / (1 - self.beta1 ** self.t)
        corrected_second_moment = v / (1 - self.beta2 ** self.t)
        weights = weights - lr * (corrected_first_moment / (np.sqrt(corrected_second_moment) + self.eps) +
                                   self.weight_decay * (weights - 50.0))
        return np.clip(weights, 0.1, 99.9)

    def load_dataset(self, dataset_path: str) -> Tuple[np.ndarray, np.ndarray]:
        """Load training data. Returns (positions, win_probs)."""
        print(f"Loading: {dataset_path}")
        with open(dataset_path, 'r') as dataset_handle:
            dataset = json.load(dataset_handle)

        positions = np.array(dataset['positions'], dtype=np.float32)
        win_probs = np.array(dataset['game_outcomes'], dtype=np.float32)

        if positions.shape[1] != self.input_size:
            print(f"  Adjusting input_size: {self.input_size} -> {positions.shape[1]}")
            self.input_size = positions.shape[1]

        print(f"  Positions: {len(positions):,}")
        print(f"  Win prob range: [{win_probs.min():.3f}, {win_probs.max():.3f}]")
        print(f"  Win prob mean: {win_probs.mean():.3f}, std: {win_probs.std():.3f}")

        return positions, win_probs

    def train(self, dataset_path: str, output_dir: str = "weights/regression",
              max_epochs: int = 500, patience: int = 100, batch_size: int = 256,
              val_split: float = 0.15, target_val_loss: float = 0.0):
        """Train the crossbar NN with MSE regression."""
        positions, win_probs = self.load_dataset(dataset_path)

        os.makedirs(output_dir, exist_ok=True)

        # Train/validation split
        num_positions = len(positions)
        shuffled_indices = np.random.permutation(num_positions)
        num_validation = int(num_positions * val_split)
        train_pos = positions[shuffled_indices[num_validation:]]
        train_wp = win_probs[shuffled_indices[num_validation:]]
        val_pos = positions[shuffled_indices[:num_validation]]
        val_wp = win_probs[shuffled_indices[:num_validation]]

        print(f"  Train: {len(train_pos):,}, Val: {len(val_pos):,}")

        # Initialize weights
        w1 = self.initialize_weights(self.input_size, self.hidden_size)
        w2 = self.initialize_weights(self.hidden_size, self.output_size)

        m1, v1 = np.zeros_like(w1), np.zeros_like(w1)
        m2, v2 = np.zeros_like(w2), np.zeros_like(w2)
        self.t = 0

        best_val_loss = float('inf')
        no_improve = 0
        current_lr = self.learning_rate
        lr_patience = 40
        lr_factor = 0.7
        min_lr = 1e-6
        epochs_since_lr_reduce = 0

        print(f"\nTraining: max_epochs={max_epochs}, patience={patience}, batch={batch_size}")
        training_start_time = time.time()

        for epoch in range(max_epochs):
            if epochs_since_lr_reduce >= lr_patience and current_lr > min_lr:
                current_lr *= lr_factor
                epochs_since_lr_reduce = 0

            shuffled_indices = np.random.permutation(len(train_pos))
            epoch_loss = 0.0

            for batch_start in range(0, len(train_pos), batch_size):
                batch_indices = shuffled_indices[batch_start:batch_start+batch_size]
                batch_positions = train_pos[batch_indices]
                batch_targets = train_wp[batch_indices]
                current_batch_size = len(batch_positions)

                # Forward: input -> hidden (ReLU) -> output (sigmoid)
                w1_eff = (w1 - 50.0) / 50.0
                w2_eff = (w2 - 50.0) / 50.0

                hidden = batch_positions @ w1_eff
                hidden_act = np.maximum(0, hidden)
                logits = (hidden_act @ w2_eff).ravel()  # (bs,)
                preds = self.sigmoid(logits)

                # MSE loss
                diff = preds - batch_targets
                loss = np.mean(diff ** 2)
                epoch_loss += loss * current_batch_size

                # Backward: d_loss/d_preds = 2*(preds - y) / bs
                d_preds = 2.0 * diff / current_batch_size
                # sigmoid derivative: sig * (1 - sig)
                d_logits = d_preds * preds * (1.0 - preds)
                d_logits = d_logits.reshape(-1, 1)

                w2_grad = hidden_act.T @ d_logits / 50.0
                d_hidden = (d_logits @ w2_eff.T) * (hidden > 0)
                w1_grad = batch_positions.T @ d_hidden / 50.0

                for gradient in [w1_grad, w2_grad]:
                    gradient_norm = np.linalg.norm(gradient)
                    if gradient_norm > 5.0:
                        gradient *= 5.0 / gradient_norm

                self.t += 1
                w1 = self.adamw_update(w1, w1_grad, current_lr, m1, v1)
                w2 = self.adamw_update(w2, w2_grad, current_lr, m2, v2)

            train_loss = epoch_loss / len(train_pos)

            # Validation
            w1_eff = (w1 - 50.0) / 50.0
            w2_eff = (w2 - 50.0) / 50.0
            val_hidden = np.maximum(0, val_pos @ w1_eff)
            val_preds = self.sigmoid((val_hidden @ w2_eff).ravel())
            val_loss = np.mean((val_preds - val_wp) ** 2)

            # Classification accuracy (for comparison)
            val_correct = np.mean(((val_preds > 0.5).astype(int)) == ((val_wp > 0.5).astype(int)))

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                no_improve = 0
                epochs_since_lr_reduce = 0

                checkpoint = {
                    'weights1': w1.tolist(),
                    'weights2': w2.tolist(),
                    'val_mse': float(val_loss),
                    'train_mse': float(train_loss),
                    'epoch': epoch,
                    'mode': 'regression',
                    'architecture': '163_96_1_sigmoid',
                    'input_size': self.input_size,
                    'hidden_size': self.hidden_size,
                    'output_size': 1,
                }
                with open(os.path.join(output_dir, "best_model.pkl"), 'wb') as checkpoint_handle:
                    pickle.dump(checkpoint, checkpoint_handle)
            else:
                no_improve += 1
                epochs_since_lr_reduce += 1

            if epoch % 25 == 0 or no_improve == 0:
                print(f"  Epoch {epoch:3d}: train_mse={train_loss:.6f} val_mse={val_loss:.6f} "
                      f"val_cls_acc={val_correct:.4f} lr={current_lr:.6f} "
                      f"pred_range=[{val_preds.min():.3f},{val_preds.max():.3f}]")

            if no_improve >= patience:
                print(f"  Early stopping at epoch {epoch}")
                break

        elapsed = time.time() - training_start_time
        print(f"\nDone in {elapsed:.1f}s. Best val MSE: {best_val_loss:.6f}")

        # Reload best weights and export binary
        best_model_path = os.path.join(output_dir, "best_model.pkl")
        best = pickle.load(open(best_model_path, 'rb'))
        w1_best = np.array(best['weights1'], dtype=np.float64)
        w2_best = np.array(best['weights2'], dtype=np.float64)

        # For C engine compatibility: pad w2 from (96,1) to (96,3)
        # Output mapping: slot[0]=unused, slot[1]=unused, slot[2]=sigmoid logit
        # The C engine computes: value = softmax([o0,o1,o2])[2] + 0.5*softmax(...)[1]
        # Instead, we'll need to update the C engine to handle 1-output sigmoid.
        # For now, save the raw weights and handle in the evaluator.
        with open(os.path.join(output_dir, "weights.bin"), 'wb') as output_handle:
            output_handle.write(struct.pack('ii', w1_best.shape[0], w1_best.shape[1]))
            output_handle.write(w1_best.tobytes())
            # Pad w2 to (96, 3) for C engine compatibility
            # Map: [large_negative, 0, logit] so softmax -> [~0, ~sigmoid, ~(1-sigmoid)]
            # Actually simpler: just save (96,1) and update C engine
            output_handle.write(struct.pack('ii', w2_best.shape[0], w2_best.shape[1]))
            output_handle.write(w2_best.tobytes())

        print(f"Saved to {output_dir}/")
        return best_val_loss


def main():
    parser = argparse.ArgumentParser(description="Train Crossbar NN (regression)")
    parser.add_argument('--dataset', type=str, required=True)
    parser.add_argument('--output', type=str, default='weights/regression')
    parser.add_argument('--epochs', type=int, default=500)
    parser.add_argument('--hidden', type=int, default=96)
    parser.add_argument('--lr', type=float, default=0.003)
    parser.add_argument('--batch', type=int, default=256)
    parser.add_argument('--patience', type=int, default=100)
    args = parser.parse_args()

    trainer = CrossbarRegressionTrainer(board_size=9, hidden_size=args.hidden,
                                         learning_rate=args.lr)
    trainer.train(args.dataset, output_dir=args.output,
                  max_epochs=args.epochs, patience=args.patience,
                  batch_size=args.batch)


if __name__ == "__main__":
    main()
