#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Crossbar Neural Network Player for Tournament Play.

Uses the ACTUAL trained memristor crossbar NN (162→64→3) for position evaluation.
"""

import numpy as np
import pickle
import random
import math
import os
from typing import Tuple

from tournament.engines.go_rules import GoRules


class CrossbarNN:
    """
    Memristor Crossbar Neural Network Evaluator.

    Architecture: 162 inputs → 64 hidden (ReLU) → 3 outputs (softmax)
    - Input: 2 features per cell (black channel, white channel) = 9x9x2 = 162
    - Output: [White wins, Draw, Black wins] probabilities
    """

    def __init__(self, weights_file: str, board_size: int = 9):
        """Load trained weights from pickle file."""
        self.board_size = board_size
        self.input_size = board_size * board_size * 2  # 162 for 9x9

        with open(weights_file, 'rb') as weights_handle:
            model = pickle.load(weights_handle)

        # Restore both crossbar conductance matrices from the training checkpoint.
        self.weights1 = np.array(model['weights1'])  # (162, 64)
        self.weights2 = np.array(model['weights2'])  # (64, 3)
        self.accuracy = model.get('accuracy', 0.0)
        self.epoch = model.get('epoch', 0)

        print(f"Loaded CrossbarNN: {self.weights1.shape} → {self.weights2.shape}")
        print(f"  Trained accuracy: {self.accuracy:.2%} (epoch {self.epoch})")

    def board_to_features(self, board: np.ndarray) -> np.ndarray:
        """
        Convert board state to 162-feature input vector.

        Args:
            board: (9,9) array with 1=Black, -1=White, 0=Empty

        Returns:
            (162,) feature vector with 2 channels per cell
        """
        features = []
        for cell in board.flatten():
            if cell == 1:  # Black
                features.extend([1.0, 0.0])
            elif cell == -1:  # White
                features.extend([0.0, 1.0])
            else:  # Empty
                features.extend([0.0, 0.0])
        return np.array(features)

    def forward(self, features: np.ndarray) -> np.ndarray:
        """
        Forward pass through the crossbar NN.

        Args:
            features: (162,) input vector

        Returns:
            (3,) softmax output [P(White), P(Draw), P(Black)]
        """
        # Hidden crossbar: h = ReLU(x @ W1).
        hidden = np.maximum(0, features @ self.weights1)

        # Output crossbar: p = softmax(h @ W2).
        logits = hidden @ self.weights2
        exp_logits = np.exp(logits - np.max(logits))  # Numerical stability
        probabilities = exp_logits / np.sum(exp_logits)

        return probabilities

    def evaluate(self, board: np.ndarray) -> float:
        """
        Evaluate board position using the trained NN.

        Args:
            board: (9,9) board state

        Returns:
            Value from Black's perspective: 1.0=Black wins, 0.0=White wins, 0.5=Draw
        """
        features = self.board_to_features(board)
        probabilities = self.forward(features)

        # Convert [P(White), P(Draw), P(Black)] to a black-perspective value.
        value = probabilities[2] * 1.0 + probabilities[1] * 0.5 + probabilities[0] * 0.0

        return value


class MCTSNode:
    """Node in the MCTS tree."""

    def __init__(self, board_state: np.ndarray, parent=None, move=None,
                 go_rules=None, player_id: int = 1):
        self.board_state = board_state.copy()
        self.parent = parent
        self.move = move
        self.children = []
        self.visits = 0
        self.value = 0.0
        self.untried_moves = []
        self.player_to_move = player_id  # Track whose turn it is at this node

        board_size = board_state.shape[0]
        for row in range(board_size):
            for col in range(board_size):
                if board_state[row, col] == 0:
                    if go_rules is None or go_rules.is_legal_move(board_state, row, col, player_id):
                        self.untried_moves.append((row, col))

    def is_fully_expanded(self) -> bool:
        return len(self.untried_moves) == 0

    def is_terminal(self) -> bool:
        return len(self.untried_moves) == 0 and len(self.children) == 0

    def best_child(self, c: float = 1.41, mcts_player_id: int = 1):
        """Select best child using UCB1 with proper player perspective."""
        best_score = -float('inf')
        best_node = None
        for child in self.children:
            if child.visits == 0:
                return child
            exploitation = child.value / child.visits
            # The opponent selects against the MCTS owner's stored value.
            if self.player_to_move != mcts_player_id:
                exploitation = 1.0 - exploitation
            exploration = c * math.sqrt(math.log(self.visits) / child.visits)
            score = exploitation + exploration
            if score > best_score:
                best_score = score
                best_node = child
        return best_node

    def most_visited_child(self):
        return max(self.children, key=lambda child: child.visits)


class CrossbarMCTSPlayer:
    """
    MCTS Player using the REAL trained Crossbar Neural Network for evaluation.
    """

    def __init__(self, board_size: int, weights_file: str,
                 iterations: int = 1000, player_id: int = 1):
        """
        Initialize MCTS player with trained crossbar NN.

        Args:
            board_size: Board size (9 for 9x9)
            weights_file: Path to trained model pickle file
            iterations: MCTS iterations per move
            player_id: 1 for Black, -1 for White
        """
        self.board_size = board_size
        self.iterations = iterations
        self.player_id = player_id
        self.weights_file = weights_file

        # Load the trained crossbar and the shared Go legality model.
        self.nn = CrossbarNN(weights_file, board_size)
        self.go_rules = GoRules(board_size)

        self.root = None

    def select_move(self, board_state: np.ndarray) -> Tuple[int, int]:
        """Select best move using MCTS with NN evaluation."""
        # Build a fresh search tree for this board position.
        self.root = MCTSNode(board_state, go_rules=self.go_rules, player_id=self.player_id)

        # Run selection, expansion, NN evaluation, and backpropagation explicitly.
        for _ in range(self.iterations):
            # 1. Select a tree frontier with UCB1.
            node = self._select(self.root)

            # 2. Expand one legal untried move.
            if not node.is_terminal():
                node = self._expand(node)

            # 3. Evaluate the leaf with the trained crossbar.
            value = self._evaluate_with_nn(node)

            # 4. Accumulate the owner-perspective value to the root.
            self._backpropagate(node, value)

        if len(self.root.children) == 0:
            return (-1, -1)

        return self.root.most_visited_child().move

    def _select(self, node: MCTSNode) -> MCTSNode:
        while not node.is_terminal():
            if not node.is_fully_expanded():
                return node
            node = node.best_child(mcts_player_id=self.player_id)
        return node

    def _expand(self, node: MCTSNode) -> MCTSNode:
        if len(node.untried_moves) == 0:
            return node

        move = random.choice(node.untried_moves)
        node.untried_moves.remove(move)

        row, col = move
        new_board = node.board_state.copy()

        black_stones = np.sum(node.board_state == 1)
        white_stones = np.sum(node.board_state == -1)
        current_player = 1 if black_stones == white_stones else -1

        legal, _ = self.go_rules.apply_move(new_board, row, col, current_player)
        if not legal:
            return node

        next_player = -current_player
        child = MCTSNode(new_board, parent=node, move=move,
                        go_rules=self.go_rules, player_id=next_player)
        node.children.append(child)
        return child

    def _evaluate_with_nn(self, node: MCTSNode) -> float:
        """
        Evaluate position using the REAL trained crossbar NN!
        """
        # Evaluate from Black's perspective with the trained crossbar.
        value = self.nn.evaluate(node.board_state)

        # Convert the result to the MCTS owner's perspective.
        if self.player_id == -1:  # White
            value = 1.0 - value

        return value

    def _backpropagate(self, node: MCTSNode, value: float):
        while node is not None:
            node.visits += 1
            node.value += value
            node = node.parent


def test_crossbar_player():
    """Quick test of the crossbar NN player."""
    weights_78 = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'pachi_training_data', 'weights_9x9_7k_v2', 'best_improved_model.pkl')

    print("Testing CrossbarNN Player")
    print("=" * 60)

    player = CrossbarMCTSPlayer(
        board_size=9,
        weights_file=weights_78,
        iterations=100,
        player_id=1
    )

    # Test on empty board
    board = np.zeros((9, 9), dtype=int)
    print("\nEmpty board evaluation:")
    value = player.nn.evaluate(board)
    print(f"  NN value (Black perspective): {value:.3f}")

    # Test with some stones
    board[4, 4] = 1  # Black center
    board[3, 4] = -1  # White
    print("\nWith stones (Black center, White above):")
    value = player.nn.evaluate(board)
    print(f"  NN value (Black perspective): {value:.3f}")

    # Test move selection
    print(f"\nSelecting move with {player.iterations} MCTS iterations...")
    move = player.select_move(board)
    print(f"  Selected move: {move}")

    print("\n✓ CrossbarNN player test passed!")


if __name__ == "__main__":
    test_crossbar_player()
