#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
IMPROVED MEMRISTOR CROSSBAR - Go Position Evaluation

Improvements:
1. Two-layer crossbar architecture with intermediate nonlinearity
2. Proper 3-class output encoding (softmax)
3. Better feature extraction and preprocessing
4. Improved gradient flow and initialization
5. Physically realistic crossbar simulation

Architecture: 50 → [Crossbar1: 50×32] → ReLU → [Crossbar2: 32×3] → Softmax
"""

import os
import json
import numpy as np
import argparse
import pickle
from datetime import datetime

class ImprovedMemristorEvaluator:
    """Improved two-layer memristor crossbar for Go position evaluation"""
    
    def __init__(self, board_size=5, learning_rate=0.003,
                 hidden_size=32, output_size=3, regression=False):
        self.board_size = board_size
        self.board_size_sq = board_size * board_size
        self.input_size = self.board_size_sq * 2 + 1  # 2 per cell + 1 turn indicator
        self.hidden_size = hidden_size  # 32 intermediate features
        self.regression = regression
        self.output_size = 1 if regression else output_size
        self.learning_rate = learning_rate

        # AdamW optimizer parameters
        self.beta1 = 0.9
        self.beta2 = 0.999
        self.eps = 1e-8
        self.weight_decay = 0.001  # Reduced for better learning

        # Adam states will be initialized when training starts
        self.m1 = None  # First layer momentum
        self.v1 = None  # First layer velocity
        self.m2 = None  # Second layer momentum
        self.v2 = None  # Second layer velocity
        self.t = 0      # Time step

        mode_str = "regression" if regression else "3-class classification"
        print("IMPROVED MEMRISTOR CROSSBAR EVALUATOR")
        print("=" * 60)
        print(f"Task: Position evaluation ({mode_str})")
        print(f"Board size: {board_size}x{board_size}")
        print(f"Architecture:")
        print(f"   Input: {self.input_size} features (Black/White channels)")
        print(f"   Crossbar 1: {self.input_size}x{self.hidden_size} -> ReLU activation")
        if regression:
            print(f"   Crossbar 2: {self.hidden_size}x1 -> Sigmoid")
            print(f"   Output: continuous value in [0, 1]")
        else:
            print(f"   Crossbar 2: {self.hidden_size}x{self.output_size} -> Softmax")
            print(f"   Output: 3 classes (Black wins, Draw, White wins)")
        print(f"Learning rate: {learning_rate}")
        print(f"Optimizer: AdamW with weight decay {self.weight_decay}")
        print()
    
    def load_dataset(self, dataset_path):
        """Load position evaluation dataset"""
        print(f"Loading dataset: {dataset_path}")

        with open(dataset_path, 'r') as f:
            dataset = json.load(f)

        print(f"   Loaded {len(dataset['positions']):,} positions")

        if 'game_outcomes' in dataset:
            outcomes = np.array(dataset['game_outcomes'])

            if self.regression:
                # Regression: use continuous values directly
                dataset['regression_targets'] = outcomes.astype(np.float32)
                print(f"   Regression targets: min={outcomes.min():.3f}, "
                      f"max={outcomes.max():.3f}, mean={outcomes.mean():.3f}, "
                      f"std={outcomes.std():.3f}")
                unique_vals = np.unique(np.round(outcomes, 2))
                print(f"   Unique values (rounded): {len(unique_vals)}")
            else:
                print(f"   Outcome distribution:")
                print(f"      Black wins (1.0): {np.sum(outcomes == 1.0):,} ({np.mean(outcomes == 1.0):.1%})")
                print(f"      White wins (0.0): {np.sum(outcomes == 0.0):,} ({np.mean(outcomes == 0.0):.1%})")
                print(f"      Draws (0.5): {np.sum(outcomes == 0.5):,} ({np.mean(outcomes == 0.5):.1%})")

                # Convert to 3-class labels
                class_labels = np.zeros(len(outcomes), dtype=int)
                class_labels[outcomes == 0.0] = 0  # White wins
                class_labels[outcomes == 0.5] = 1  # Draw
                class_labels[outcomes == 1.0] = 2  # Black wins
                dataset['class_labels'] = class_labels.tolist()

        return dataset
    
    def initialize_crossbar_weights(self, input_dim, output_dim, 
                                   name="crossbar"):
        """Initialize memristor crossbar weights with proper scaling"""
        # Xavier/Glorot initialization adapted for positive weights
        fan_in = input_dim
        fan_out = output_dim
        
        # Standard deviation for Xavier init
        std = np.sqrt(2.0 / (fan_in + fan_out))
        
        # Generate weights in [-1, 1] range first
        weights_norm = np.random.normal(0, std, (input_dim, output_dim))
        
        # Map to conductance range [0.1, 99.9] centered at 50
        # With differential-pair normalization (W-50)/50, effective weights
        # will be ~ N(0, Xavier_std) since spread/scale = 50/50 = 1
        weights = 50.0 + (weights_norm * 50.0)
        weights = np.clip(weights, 0.1, 99.9)   # Keep in valid conductance range
        
        print(f"   {name}: {input_dim}x{output_dim}")
        print(f"      Weight range: [{weights.min():.1f}, {weights.max():.1f}]")
        print(f"      Weight mean/std: {weights.mean():.1f} +/- {weights.std():.1f}")
        
        return weights.astype(np.float32)
    
    def crossbar_forward(self, inputs, weights):
        """Forward pass through memristor crossbar (differential pair encoding).

        Conductances in [0.1, 99.9] are mapped to effective weights via:
            W_eff = (G - 50) / 50
        so G=0.1 -> -0.998 (inhibitory), G=50 -> 0 (neutral), G=99.9 -> +0.998 (excitatory).
        This is the standard differential-pair approach in neuromorphic computing.
        """
        normalized_weights = (weights - 50.0) / 50.0
        currents = np.dot(inputs, normalized_weights)
        return currents
    
    def relu_activation(self, x):
        """ReLU activation function"""
        return np.maximum(0, x)
    
    def relu_derivative(self, x):
        """ReLU derivative"""
        return (x > 0).astype(np.float32)
    
    def sigmoid(self, x):
        """Stable sigmoid implementation"""
        return np.where(x >= 0,
                        1 / (1 + np.exp(-x)),
                        np.exp(x) / (1 + np.exp(x)))

    def softmax(self, x):
        """Stable softmax implementation"""
        # Subtract max for numerical stability
        x_max = np.max(x, axis=1, keepdims=True)
        x_stable = x - x_max
        exp_x = np.exp(x_stable)
        return exp_x / np.sum(exp_x, axis=1, keepdims=True)
    
    def cross_entropy_loss(self, predictions, labels):
        """Cross-entropy loss for multi-class classification"""
        # Convert labels to one-hot if needed
        if len(labels.shape) == 1:
            num_classes = predictions.shape[1]
            one_hot = np.zeros((len(labels), num_classes))
            one_hot[np.arange(len(labels)), labels] = 1
            labels = one_hot
        
        # Clip predictions to avoid log(0)
        predictions = np.clip(predictions, 1e-15, 1 - 1e-15)
        
        # Cross-entropy loss
        loss = -np.mean(np.sum(labels * np.log(predictions), axis=1))
        return loss
    
    def calculate_accuracy(self, predictions, labels):
        """Calculate classification accuracy"""
        predicted_classes = np.argmax(predictions, axis=1)
        if len(labels.shape) > 1:  # One-hot encoded
            true_classes = np.argmax(labels, axis=1)
        else:
            true_classes = labels
        
        accuracy = np.mean(predicted_classes == true_classes)
        return accuracy
    
    def train(self, dataset, max_epochs=2000, 
              output_dir="improved_weights", patience=200, 
              batch_size=256):
        """Train improved two-layer memristor crossbar"""
        
        print(f"Training Improved Memristor Crossbar")
        print(f"   Max epochs: {max_epochs}, Patience: {patience}")
        print(f"   Output directory: {output_dir}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Prepare data
        positions = np.array(dataset['positions'], dtype=np.float32)

        # Auto-detect input size from dataset (handles enhanced feature encodings)
        actual_input_size = positions.shape[1]
        if actual_input_size != self.input_size:
            print(f"   NOTE: Adjusting input_size from {self.input_size} to "
                  f"{actual_input_size} (dataset feature dim)")
            self.input_size = actual_input_size

        if self.regression:
            targets = np.array(dataset['regression_targets'], dtype=np.float32)
            print(f"   Dataset: {len(positions):,} positions (regression)")
        else:
            class_labels = np.array(dataset['class_labels'], dtype=int)
            targets = class_labels
            print(f"   Dataset: {len(positions):,} positions")
            print(f"   Classes: {np.unique(class_labels)} (0=White wins, 1=Draw, 2=Black wins)")

        # Initialize crossbar weights
        print(f"   Initializing memristor crossbars...")
        weights1 = self.initialize_crossbar_weights(self.input_size, self.hidden_size, "Crossbar1")
        weights2 = self.initialize_crossbar_weights(self.hidden_size, self.output_size, "Crossbar2")
        
        # Initialize optimizer states
        self.m1 = np.zeros_like(weights1)
        self.v1 = np.zeros_like(weights1)
        self.m2 = np.zeros_like(weights2)
        self.v2 = np.zeros_like(weights2)
        self.t = 0
        
        # Training tracking
        best_accuracy = 0.0
        no_improvement_count = 0
        training_log = {'epoch': [], 'loss': [], 'accuracy': [], 'learning_rate': []}
        
        # Dynamic learning rate
        current_lr = self.learning_rate
        lr_patience = 50
        lr_factor = 0.8
        min_lr = 1e-6
        epochs_since_improvement = 0
        
        print(f"   Starting training...")
        
        for epoch in range(max_epochs):
            # Learning rate scheduling
            if epochs_since_improvement >= lr_patience and current_lr > min_lr:
                current_lr *= lr_factor
                epochs_since_improvement = 0
                print(f"   Learning rate reduced to {current_lr:.6f}")
            
            # Shuffle data each epoch
            shuffle_idx = np.random.permutation(len(positions))
            positions_shuffled = positions[shuffle_idx]
            targets_shuffled = targets[shuffle_idx]

            # Mini-batch training
            num_batches = (len(positions) + batch_size - 1) // batch_size
            epoch_loss = 0.0
            epoch_correct = 0

            for batch_idx in range(num_batches):
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(positions))

                batch_x = positions_shuffled[start_idx:end_idx]
                batch_y = targets_shuffled[start_idx:end_idx]
                current_batch_size = len(batch_x)

                # Forward pass
                # Layer 1: Input -> Crossbar1 -> ReLU
                hidden_currents = self.crossbar_forward(batch_x, weights1)
                hidden_outputs = self.relu_activation(hidden_currents)

                # Layer 2: Hidden -> Crossbar2 -> output activation
                output_currents = self.crossbar_forward(hidden_outputs, weights2)

                if self.regression:
                    # Regression: sigmoid output, MSE loss
                    output_vals = self.sigmoid(output_currents).squeeze()  # (batch,)
                    loss = float(np.mean((output_vals - batch_y) ** 2))
                    # R² as "accuracy" metric for regression
                    ss_res = np.sum((output_vals - batch_y) ** 2)
                    ss_tot = np.sum((batch_y - np.mean(batch_y)) ** 2) + 1e-15
                    accuracy = max(0.0, 1.0 - ss_res / ss_tot)

                    # Backward: dL/dlogit = dL/dout * sigmoid'(logit)
                    #   dL/dout = 2*(out - target) / batch_size
                    sigmoid_deriv = output_vals * (1 - output_vals)
                    output_errors = (2.0 * (output_vals - batch_y) / current_batch_size
                                     * sigmoid_deriv).reshape(-1, 1)
                else:
                    # Classification: softmax output, cross-entropy loss
                    output_probs = self.softmax(output_currents)
                    loss = self.cross_entropy_loss(output_probs, batch_y)
                    accuracy = self.calculate_accuracy(output_probs, batch_y)

                    # Backward: softmax + CE gradient
                    one_hot_y = np.zeros((current_batch_size, self.output_size))
                    one_hot_y[np.arange(current_batch_size), batch_y] = 1
                    output_errors = (output_probs - one_hot_y) / current_batch_size

                # Gradients for weights2 (Crossbar2)
                # Forward: output = hidden @ (W2-50)/50, so dL/dW2 = (1/50) * hidden.T @ dL/dout
                weights2_grad = np.dot(hidden_outputs.T, output_errors) / 50.0

                # Hidden layer gradients (through crossbar2)
                hidden_errors = np.dot(output_errors, ((weights2 - 50.0) / 50.0).T)
                hidden_errors *= self.relu_derivative(hidden_currents)  # ReLU derivative

                # Gradients for weights1 (Crossbar1)
                # Forward: hidden = input @ (W1-50)/50, so dL/dW1 = (1/50) * input.T @ dL/dhidden
                weights1_grad = np.dot(batch_x.T, hidden_errors) / 50.0
                
                # Gradient clipping
                grad_norm1 = np.linalg.norm(weights1_grad)
                grad_norm2 = np.linalg.norm(weights2_grad)
                max_grad_norm = 5.0
                
                if grad_norm1 > max_grad_norm:
                    weights1_grad *= max_grad_norm / grad_norm1
                if grad_norm2 > max_grad_norm:
                    weights2_grad *= max_grad_norm / grad_norm2
                
                # AdamW updates (increment timestep once per batch, not per layer)
                self.t += 1
                weights1 = self._adamw_update(weights1, weights1_grad, current_lr,
                                            self.m1, self.v1, layer_name="Crossbar1")
                weights2 = self._adamw_update(weights2, weights2_grad, current_lr,
                                            self.m2, self.v2, layer_name="Crossbar2")
                
                epoch_loss += loss * current_batch_size
                epoch_correct += accuracy * current_batch_size
            
            # Calculate epoch metrics
            epoch_loss /= len(positions)
            epoch_accuracy = epoch_correct / len(positions)
            
            # Track progress
            training_log['epoch'].append(epoch)
            training_log['loss'].append(float(epoch_loss))
            training_log['accuracy'].append(float(epoch_accuracy))
            training_log['learning_rate'].append(float(current_lr))
            
            # Check for improvement
            if epoch_accuracy > best_accuracy:
                best_accuracy = epoch_accuracy
                no_improvement_count = 0
                epochs_since_improvement = 0
                
                # Save best model
                checkpoint = {
                    'weights1': weights1.tolist(),
                    'weights2': weights2.tolist(),
                    'accuracy': float(epoch_accuracy),
                    'loss': float(epoch_loss),
                    'epoch': epoch,
                    'learning_rate': current_lr,
                    'architecture': 'two_layer_memristor_crossbar',
                    'input_size': self.input_size,
                    'hidden_size': self.hidden_size,
                    'output_size': self.output_size,
                    'mode': 'regression' if self.regression else 'classification',
                }
                
                best_path = os.path.join(output_dir, "best_improved_model.pkl")
                with open(best_path, 'wb') as f:
                    pickle.dump(checkpoint, f)
                
                # Save milestone checkpoints
                if epoch_accuracy >= 0.5:  # Above random baseline
                    milestone_path = os.path.join(output_dir, f"model_at_{epoch_accuracy*100:.2f}percent.pkl")
                    with open(milestone_path, 'wb') as f:
                        pickle.dump(checkpoint, f)
                    metric_name = "R²" if self.regression else "accuracy"
                    print(f"   NEW MILESTONE: {epoch_accuracy*100:.2f}% {metric_name}!")
                
            else:
                no_improvement_count += 1
                epochs_since_improvement += 1
            
            # Progress reporting
            if epoch % 10 == 0 or epoch_accuracy > best_accuracy:
                metric_label = "R²" if self.regression else "Acc"
                print(f"   Epoch {epoch:4d}: Loss={epoch_loss:.6f}, "
                      f"{metric_label}={epoch_accuracy:.4f} (Best: {best_accuracy:.4f}), LR={current_lr:.6f}")
            
            # Early stopping
            if no_improvement_count >= patience:
                print(f"   Early stopping: no improvement for {patience} epochs")
                break
                
            # No artificial accuracy cap — let early stopping handle convergence
        
        # Save final summary
        summary = {
            'architecture': 'two_layer_memristor_crossbar',
            'board_size': self.board_size,
            'input_size': self.input_size,
            'hidden_size': self.hidden_size,
            'output_size': self.output_size,
            'learning_rate': self.learning_rate,
            'final_accuracy': float(best_accuracy),
            'mode': 'regression' if self.regression else 'classification',
            'total_epochs': len(training_log['epoch']),
            'training_log': training_log,
            'training_time': datetime.now().isoformat()
        }
        
        summary_path = os.path.join(output_dir, f"training_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"   Training complete!")
        print(f"      Final accuracy: {best_accuracy:.4f}")
        print(f"      Total epochs: {len(training_log['epoch'])}")
        print(f"      Summary: {summary_path}")
        
        return summary
    
    def _adamw_update(self, weights, gradients,
                      lr, m, v,
                      layer_name=""):
        """AdamW optimizer update with memristor constraints"""
        # Update biased moment estimates
        m[:] = self.beta1 * m + (1 - self.beta1) * gradients
        v[:] = self.beta2 * v + (1 - self.beta2) * (gradients ** 2)
        
        # Bias correction
        m_hat = m / (1 - self.beta1 ** self.t)
        v_hat = v / (1 - self.beta2 ** self.t)
        
        # AdamW update — regularize toward center conductance (50 = effective zero)
        weights = weights - lr * (m_hat / (np.sqrt(v_hat) + self.eps) +
                                 self.weight_decay * (weights - 50.0))
        
        # Enforce memristor conductance constraints
        weights = np.clip(weights, 0.1, 99.9)
        
        return weights

def main():
    """Main training entry point"""
    parser = argparse.ArgumentParser(description="Improved Memristor Crossbar Evaluator")
    parser.add_argument('--dataset', type=str, required=True,
                       help='Path to dataset JSON file')
    parser.add_argument('--epochs', type=int, default=2000,
                       help='Maximum training epochs')
    parser.add_argument('--learning_rate', type=float, default=0.003,
                       help='Learning rate')
    parser.add_argument('--board_size', type=int, default=5,
                       help='Go board size')
    parser.add_argument('--hidden_size', type=int, default=32,
                       help='Hidden layer size')
    parser.add_argument('--output_dir', type=str, default='improved_weights',
                       help='Output directory')
    parser.add_argument('--patience', type=int, default=200,
                       help='Early stopping patience')
    parser.add_argument('--batch_size', type=int, default=256,
                       help='Batch size')
    parser.add_argument('--regression', action='store_true',
                       help='Use regression (MSE + sigmoid) instead of classification (CE + softmax)')

    args = parser.parse_args()

    # Create evaluator
    evaluator = ImprovedMemristorEvaluator(
        board_size=args.board_size,
        learning_rate=args.learning_rate,
        hidden_size=args.hidden_size,
        regression=args.regression
    )
    
    # Load dataset
    dataset = evaluator.load_dataset(args.dataset)
    
    if dataset:
        # Train model
        results = evaluator.train(
            dataset,
            max_epochs=args.epochs,
            output_dir=args.output_dir,
            patience=args.patience,
            batch_size=args.batch_size
        )
        
        print(f"\nTraining complete!")
        print(f"Model saved to: {args.output_dir}/")
        print(f"Final accuracy: {results['final_accuracy']:.4f}")
    else:
        print("Failed to load dataset")

if __name__ == "__main__":
    main()
