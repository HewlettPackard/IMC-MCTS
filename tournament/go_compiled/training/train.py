#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Trainer for 163->96->3 Crossbar Neural Network.

Architecture: 163 inputs (9x9 x 2 channels + turn bit) -> 96 hidden -> 3 outputs
  - Differential-pair normalization: W_eff = (G - 50) / 50
  - Conductance range: [0.1, 99.9] nS
  - AdamW optimizer with weight decay toward center conductance (50 nS)
  - Xavier/Glorot initialization mapped to conductance range
"""

import os
import sys
import json
import struct
import numpy as np
import pickle
import argparse
from datetime import datetime
from typing import Dict, List, Tuple


class CrossbarTrainer:
    """Train 2-layer memristor crossbar NN for Go position evaluation."""

    def __init__(self, board_size: int = 9, hidden_size: int = 96,
                 learning_rate: float = 0.003):
        self.board_size = board_size
        self.input_size = board_size * board_size * 2 + 1  # 163 (2 channels + turn bit)
        self.hidden_size = hidden_size
        self.output_size = 3  # Hardware: [P(White), P(Draw), P(Black)]
        self.learning_rate = learning_rate

        # AdamW parameters
        self.beta1 = 0.9
        self.beta2 = 0.999
        self.eps = 1e-8
        self.weight_decay = 0.001
        self.t = 0

        print(f"CrossbarTrainer: {self.input_size} -> {self.hidden_size} -> {self.output_size}")
        print(f"  Board: {board_size}x{board_size}, LR: {learning_rate}")

    def initialize_weights(self, fan_in: int, fan_out: int) -> np.ndarray:
        """Xavier/Glorot init mapped to conductance range [0.1, 99.9]."""
        xavier_std = np.sqrt(2.0 / (fan_in + fan_out))
        normalized_weights = np.random.normal(
            0,
            xavier_std,
            (fan_in, fan_out)
        )
        weights = 50.0 + normalized_weights * 50.0
        return np.clip(weights, 0.1, 99.9).astype(np.float32)

    def crossbar_forward(self, inputs: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """Forward pass with differential-pair normalization."""
        effective_weights = (weights - 50.0) / 50.0
        return np.dot(inputs, effective_weights)

    @staticmethod
    def relu(x: np.ndarray) -> np.ndarray:
        return np.maximum(0, x)

    @staticmethod
    def relu_deriv(x: np.ndarray) -> np.ndarray:
        return (x > 0).astype(np.float32)

    @staticmethod
    def softmax(x: np.ndarray) -> np.ndarray:
        row_max = np.max(x, axis=1, keepdims=True)
        exponentials = np.exp(x - row_max)
        return exponentials / np.sum(exponentials, axis=1, keepdims=True)

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
        """Load training data. Returns (positions, class_labels)."""
        print(f"Loading: {dataset_path}")
        with open(dataset_path, 'r') as dataset_handle:
            dataset = json.load(dataset_handle)

        positions = np.array(dataset['positions'], dtype=np.float32)
        outcomes = np.array(dataset['game_outcomes'])

        # Outcomes are already from Black's perspective (datagen converts whiteWin
        # to 1-whiteWin, and color-flip augmentation inverts outcomes consistently)
        # Hardware 3-class: 0=White wins, 1=Draw, 2=Black wins
        labels = np.ones(len(outcomes), dtype=int)  # default = Draw (1)
        labels[outcomes < 0.35] = 0   # White wins
        labels[outcomes > 0.65] = 2   # Black wins

        # Auto-adjust input size if needed
        if positions.shape[1] != self.input_size:
            print(f"  Adjusting input_size: {self.input_size} -> {positions.shape[1]}")
            self.input_size = positions.shape[1]

        print(f"  Positions: {len(positions):,}")
        print(f"  Classes: White={np.sum(labels==0):,}, Draw={np.sum(labels==1):,}, "
              f"Black={np.sum(labels==2):,}")

        return positions, labels

    @staticmethod
    def export_bin(w1: np.ndarray, w2: np.ndarray, filepath: str):
        """Export weights to binary format for C engine compatibility."""
        w1_f64 = np.array(w1, dtype=np.float64)
        w2_f64 = np.array(w2, dtype=np.float64)
        with open(filepath, 'wb') as output_handle:
            output_handle.write(struct.pack('ii', w1_f64.shape[0], w1_f64.shape[1]))
            output_handle.write(w1_f64.tobytes())
            output_handle.write(struct.pack('ii', w2_f64.shape[0], w2_f64.shape[1]))
            output_handle.write(w2_f64.tobytes())
        print(f"  Exported binary weights: {filepath}")

    def train(self, dataset_path: str, output_dir: str = "weights/full_precision",
              max_epochs: int = 2000, patience: int = 200, batch_size: int = 256,
              val_split: float = 0.15, label_smoothing: float = 0.1,
              dropout_rate: float = 0.15):
        """Train the crossbar NN with validation split and regularization.

        Args:
            val_split: Fraction of data held out for validation.
            label_smoothing: Smoothing factor (0 = hard labels, 0.1 = standard).
            dropout_rate: Dropout probability for hidden layer during training.
        """
        positions, labels = self.load_dataset(dataset_path)

        os.makedirs(output_dir, exist_ok=True)

        # Train/validation split (stratified shuffle)
        num_positions = len(positions)
        shuffled_indices = np.random.permutation(num_positions)
        num_validation = int(num_positions * val_split)
        val_idx = shuffled_indices[:num_validation]
        train_idx = shuffled_indices[num_validation:]

        train_pos, train_lab = positions[train_idx], labels[train_idx]
        val_pos, val_lab = positions[val_idx], labels[val_idx]

        print(f"  Train: {len(train_pos):,}, Val: {len(val_pos):,} ({val_split*100:.0f}% split)")
        print(f"  Label smoothing: {label_smoothing}, Dropout: {dropout_rate}")

        # Initialize weights
        w1 = self.initialize_weights(self.input_size, self.hidden_size)
        w2 = self.initialize_weights(self.hidden_size, self.output_size)

        # Adam states
        m1, v1 = np.zeros_like(w1), np.zeros_like(w1)
        m2, v2 = np.zeros_like(w2), np.zeros_like(w2)
        self.t = 0

        best_val_accuracy = 0.0
        best_val_loss = float('inf')
        no_improve = 0
        milestones = {0.60: '60pct', 0.70: '70pct', 0.80: '80pct'}
        milestones_hit = set()
        current_lr = self.learning_rate
        lr_patience = 50
        lr_factor = 0.8
        min_lr = 1e-6
        epochs_since_lr_reduce = 0

        log = {'epoch': [], 'train_loss': [], 'train_accuracy': [],
               'val_loss': [], 'val_accuracy': [], 'lr': []}

        print(f"\nTraining: max_epochs={max_epochs}, patience={patience}, batch={batch_size}")

        for epoch in range(max_epochs):
            # LR scheduling
            if epochs_since_lr_reduce >= lr_patience and current_lr > min_lr:
                current_lr *= lr_factor
                epochs_since_lr_reduce = 0

            # Shuffle training data
            shuffled_indices = np.random.permutation(len(train_pos))
            shuffled_positions = train_pos[shuffled_indices]
            shuffled_labels = train_lab[shuffled_indices]

            epoch_loss = 0.0
            epoch_correct = 0
            num_batches = (len(train_pos) + batch_size - 1) // batch_size

            for batch_index in range(num_batches):
                batch_start = batch_index * batch_size
                batch_end = min(batch_start + batch_size, len(train_pos))
                batch_positions = shuffled_positions[batch_start:batch_end]
                batch_labels = shuffled_labels[batch_start:batch_end]
                current_batch_size = len(batch_positions)

                # Forward (training mode with dropout)
                hidden = self.crossbar_forward(batch_positions, w1)
                hidden_act = self.relu(hidden)

                # Dropout on hidden layer
                if dropout_rate > 0:
                    drop_mask = (np.random.random(hidden_act.shape) > dropout_rate).astype(np.float32)
                    hidden_act_dropped = hidden_act * drop_mask / (1.0 - dropout_rate)
                else:
                    hidden_act_dropped = hidden_act
                    drop_mask = None

                output = self.crossbar_forward(hidden_act_dropped, w2)
                probs = self.softmax(output)

                # Loss with label smoothing
                probs_clip = np.clip(probs, 1e-15, 1 - 1e-15)
                one_hot = np.eye(self.output_size)[batch_labels]
                if label_smoothing > 0:
                    smooth_targets = one_hot * (1.0 - label_smoothing) + \
                                     label_smoothing / self.output_size
                else:
                    smooth_targets = one_hot

                loss = -np.mean(np.sum(smooth_targets * np.log(probs_clip), axis=1))
                acc = np.mean(np.argmax(probs, axis=1) == batch_labels)

                # Backward (using smooth targets)
                d_output = (probs - smooth_targets) / current_batch_size

                # Gradients (chain rule through differential-pair normalization)
                w2_grad = np.dot(hidden_act_dropped.T, d_output) / 50.0

                d_hidden = np.dot(d_output, ((w2 - 50.0) / 50.0).T)
                # Backprop through dropout
                if drop_mask is not None:
                    d_hidden *= drop_mask / (1.0 - dropout_rate)
                d_hidden *= self.relu_deriv(hidden)
                w1_grad = np.dot(batch_positions.T, d_hidden) / 50.0

                # Gradient clipping
                for gradient in [w1_grad, w2_grad]:
                    gradient_norm = np.linalg.norm(gradient)
                    if gradient_norm > 5.0:
                        gradient *= 5.0 / gradient_norm

                # Update
                self.t += 1
                w1 = self.adamw_update(w1, w1_grad, current_lr, m1, v1)
                w2 = self.adamw_update(w2, w2_grad, current_lr, m2, v2)

                epoch_loss += loss * current_batch_size
                epoch_correct += acc * current_batch_size

            train_loss = epoch_loss / len(train_pos)
            train_acc = epoch_correct / len(train_pos)

            # Validation (no dropout, no label smoothing)
            val_hidden = self.crossbar_forward(val_pos, w1)
            val_hidden_act = self.relu(val_hidden)
            val_output = self.crossbar_forward(val_hidden_act, w2)
            val_probs = self.softmax(val_output)
            val_probs_clip = np.clip(val_probs, 1e-15, 1 - 1e-15)
            val_loss = -np.mean(np.sum(
                np.eye(self.output_size)[val_lab] * np.log(val_probs_clip), axis=1))
            val_acc = np.mean(np.argmax(val_probs, axis=1) == val_lab)

            log['epoch'].append(epoch)
            log['train_loss'].append(float(train_loss))
            log['train_accuracy'].append(float(train_acc))
            log['val_loss'].append(float(val_loss))
            log['val_accuracy'].append(float(val_acc))
            log['lr'].append(float(current_lr))

            # Track best validation accuracy
            if val_acc > best_val_accuracy:
                best_val_accuracy = val_acc
                best_val_loss = val_loss
                no_improve = 0
                epochs_since_lr_reduce = 0

                # Save best model
                checkpoint = {
                    'weights1': w1.tolist(),
                    'weights2': w2.tolist(),
                    'accuracy': float(val_acc),
                    'train_accuracy': float(train_acc),
                    'val_accuracy': float(val_acc),
                    'val_loss': float(val_loss),
                    'loss': float(train_loss),
                    'epoch': epoch,
                    'architecture': 'two_layer_memristor_crossbar',
                    'input_size': self.input_size,
                    'hidden_size': self.hidden_size,
                    'output_size': self.output_size,
                    'label_smoothing': label_smoothing,
                    'dropout_rate': dropout_rate,
                }
                with open(os.path.join(output_dir, "best_model.pkl"), 'wb') as checkpoint_handle:
                    pickle.dump(checkpoint, checkpoint_handle)
                self.export_bin(w1, w2, os.path.join(output_dir, "best_model.bin"))
            else:
                no_improve += 1
                epochs_since_lr_reduce += 1

            # Milestone checkpoints
            for threshold, name in milestones.items():
                if threshold not in milestones_hit and val_acc >= threshold:
                    milestones_hit.add(threshold)
                    milestone_dir = os.path.join(output_dir, name)
                    os.makedirs(milestone_dir, exist_ok=True)
                    milestone_checkpoint = {
                        'weights1': w1.tolist(),
                        'weights2': w2.tolist(),
                        'val_accuracy': float(val_acc),
                        'epoch': epoch,
                        'input_size': self.input_size,
                        'hidden_size': self.hidden_size,
                        'output_size': self.output_size,
                    }
                    with open(os.path.join(milestone_dir, "model.pkl"), 'wb') as checkpoint_handle:
                        pickle.dump(milestone_checkpoint, checkpoint_handle)
                    self.export_bin(w1, w2, os.path.join(milestone_dir, "weights.bin"))
                    print(f"  *** Milestone {name}: val_acc={val_acc:.4f} at epoch {epoch} ***")

            if epoch % 50 == 0 or no_improve == 0:
                gap = train_acc - val_acc
                print(f"  Epoch {epoch:4d}: train={train_acc:.4f} val={val_acc:.4f} "
                      f"gap={gap:+.4f} loss={val_loss:.4f} "
                      f"(best_val={best_val_accuracy:.4f}) lr={current_lr:.6f}")

            if no_improve >= patience:
                print(f"  Early stopping at epoch {epoch} (val not improving)")
                break

        # Save summary
        summary = {
            'architecture': '163_96_3_softmax',
            'board_size': self.board_size,
            'best_val_accuracy': float(best_val_accuracy),
            'best_val_loss': float(best_val_loss),
            'total_epochs': len(log['epoch']),
            'label_smoothing': label_smoothing,
            'dropout_rate': dropout_rate,
            'val_split': val_split,
            'training_log': log,
        }
        with open(os.path.join(output_dir, "training_summary.json"), 'w') as summary_handle:
            json.dump(summary, summary_handle, indent=2)

        print(f"\nTraining complete! Best val accuracy: {best_val_accuracy:.4f}")
        print(f"Model saved to: {output_dir}/best_model.pkl")

        return summary


def main():
    parser = argparse.ArgumentParser(description="Train Crossbar NN for Go")
    parser.add_argument('--dataset', type=str, required=True,
                        help='Path to training data JSON')
    parser.add_argument('--output', type=str, default='weights/full_precision',
                        help='Output directory')
    parser.add_argument('--epochs', type=int, default=2000)
    parser.add_argument('--hidden', type=int, default=96)
    parser.add_argument('--lr', type=float, default=0.003)
    parser.add_argument('--batch', type=int, default=256)
    parser.add_argument('--patience', type=int, default=200)
    args = parser.parse_args()

    trainer = CrossbarTrainer(board_size=9, hidden_size=args.hidden,
                               learning_rate=args.lr)
    trainer.train(args.dataset, output_dir=args.output,
                  max_epochs=args.epochs, patience=args.patience,
                  batch_size=args.batch)


if __name__ == "__main__":
    main()
