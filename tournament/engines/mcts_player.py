# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
MCTS Player for Tournament Play.

Standalone MCTS implementation using the same logic as Accelerator components
but without SST dependencies for simpler integration in tournament play.

Loads and uses trained crossbar NN weights
for position evaluation instead of heuristic with random noise.
"""

import numpy as np
import random
import pickle
import math
import os
from typing import List, Tuple, Optional

from tournament.engines.heuristic_eval import HeuristicEvaluator
from tournament.engines.go_rules import GoRules


class CrossbarNN:
    """
    Memristor Crossbar Neural Network Evaluator.

    Architecture: N inputs → hidden (ReLU) → 3 outputs (softmax)
    - Input: 2 features per cell (black channel, white channel)
    - Output: [White wins, Draw, Black wins] probabilities

    This performs the ACTUAL forward pass through the trained crossbar weights.
    """

    def __init__(self, weights_file: str, board_size: int = 9):
        """Load trained weights from pickle file."""
        self.board_size = board_size
        self.input_size = board_size * board_size * 2
        self.weights_file = weights_file

        with open(weights_file, 'rb') as weights_handle:
            model = pickle.load(weights_handle)

        # Restore both crossbar conductance matrices from the training checkpoint.
        self.weights1 = np.array(model['weights1'])
        self.weights2 = np.array(model['weights2'])
        self.trained_accuracy = model.get('accuracy', 0.0)
        self.epoch = model.get('epoch', 0)

        # Reject a checkpoint trained for a different board size.
        expected_input = self.input_size
        actual_input = self.weights1.shape[0]
        if actual_input != expected_input:
            raise ValueError(f"Weight dimension mismatch: expected {expected_input} inputs, "
                           f"got {actual_input}. Board size may be wrong.")

    def board_to_features(self, board: np.ndarray) -> np.ndarray:
        """
        Convert board state to feature vector.

        Args:
            board: (N,N) array with 1=Black, -1=White, 0=Empty

        Returns:
            Feature vector with 2 channels per cell
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
            features: Input vector

        Returns:
            Softmax output [P(White), P(Draw), P(Black)]
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
            board: (N,N) board state

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

    def __init__(self, board_state: np.ndarray, parent: Optional['MCTSNode'] = None, move: Optional[Tuple[int, int]] = None, go_rules: Optional[GoRules] = None, player_id: int = 1):
        self.board_state = board_state.copy()
        self.parent = parent
        self.move = move  # Move that led to this state
        self.children: List['MCTSNode'] = []
        self.visits = 0
        self.value = 0.0
        self.untried_moves: List[Tuple[int, int]] = []
        self.player_to_move = player_id  # Track whose turn it is at this node

        # Enumerate legal moves for the side that acts at this node.
        board_size = board_state.shape[0]
        for row in range(board_size):
            for col in range(board_size):
                if board_state[row, col] == 0:
                    if go_rules is None or go_rules.is_legal_move(board_state, row, col, player_id):
                        self.untried_moves.append((row, col))

    def is_fully_expanded(self) -> bool:
        """Check if all children have been expanded."""
        return len(self.untried_moves) == 0

    def is_terminal(self) -> bool:
        """Check if this is a terminal node (board full)."""
        return len(self.untried_moves) == 0 and len(self.children) == 0

    def best_child(self, exploration_constant: float = 1.41, mcts_player_id: int = 1) -> 'MCTSNode':
        """Select best child using UCB1 with proper player perspective.

        Values are stored from the MCTS owner's perspective. When it's the
        opponent's turn (self.player_to_move != mcts_player_id), we flip
        the exploitation term to model adversarial play.
        """
        best_score = -float('inf')
        best_node = None

        for child in self.children:
            if child.visits == 0:
                return child  # Prioritize unvisited children

            exploitation = child.value / child.visits
            # The opponent selects against the MCTS owner's stored value.
            if self.player_to_move != mcts_player_id:
                exploitation = 1.0 - exploitation
            exploration = exploration_constant * math.sqrt(math.log(self.visits) / child.visits)
            score = exploitation + exploration

            if score > best_score:
                best_score = score
                best_node = child

        return best_node

    def most_visited_child(self) -> 'MCTSNode':
        """Get child with most visits (for final move selection)."""
        return max(self.children, key=lambda child: child.visits)


class SimplifiedMCTSPlayer:
    """
    Simplified MCTS player for tournament play.

    This is a standalone implementation that matches the logic of Accelerator
    components but without SST dependencies.

    Loads and uses trained crossbar NN weights.
    """

    def __init__(
        self,
        board_size: int,
        weights_file: Optional[str] = None,
        iterations: int = 5000,
        exploration_constant: float = 1.41,
        player_id: int = 1,  # 1 for Black, -1 for White
        accuracy: float = 1.0  # Now only used for display, actual accuracy comes from trained model
    ):
        """
        Initialize MCTS player.

        Args:
            board_size: Size of board (e.g., 9 for 9x9)
            weights_file: Path to NN weights pickle file (None = heuristic fallback)
            iterations: Number of MCTS iterations per move
            exploration_constant: UCB1 exploration parameter
            player_id: Player color (1 = Black, -1 = White)
            accuracy: Display accuracy (actual accuracy comes from loaded model)
        """
        self.board_size = board_size
        self.iterations = iterations
        self.exploration_constant = exploration_constant
        self.player_id = player_id
        self.weights_file = weights_file
        self.accuracy = accuracy

        # Keep move legality and captures consistent with the tournament board.
        self.go_rules = GoRules(board_size)

        # Load the trained crossbar when a usable checkpoint is available.
        self.crossbar_nn = None
        if weights_file is not None and os.path.exists(weights_file):
            try:
                self.crossbar_nn = CrossbarNN(weights_file, board_size)
                self.accuracy = self.crossbar_nn.trained_accuracy
                print(f"  Loaded CrossbarNN: {self.crossbar_nn.weights1.shape} → {self.crossbar_nn.weights2.shape}")
                print(f"  Trained accuracy: {self.accuracy:.2%}")
            except Exception as e:
                print(f"  WARNING: Failed to load CrossbarNN from {weights_file}: {e}")
                print(f"  Falling back to heuristic evaluator")
                self.crossbar_nn = None

        # Retain the training heuristic as the no-checkpoint fallback.
        self.evaluator = HeuristicEvaluator(board_size)

        # Expose tree state for tournament logging.
        self.root: Optional[MCTSNode] = None
        self.total_nodes = 0

    def select_move(self, board_state: np.ndarray) -> Tuple[int, int]:
        """
        Select best move for current board position using MCTS.

        Args:
            board_state: numpy array (board_size, board_size) with:
                         1 = Black, -1 = White, 0 = Empty

        Returns:
            Tuple of (row, col) for best move
        """
        # Build a fresh search tree for this board position.
        self.root = MCTSNode(board_state, go_rules=self.go_rules, player_id=self.player_id)
        self.total_nodes = 1

        # Run selection, expansion, evaluation, and backpropagation explicitly.
        for _ in range(self.iterations):
            # 1. Select a tree frontier with UCB1.
            node = self._select(self.root)

            # 2. Expand one legal untried move.
            if not node.is_terminal():
                node = self._expand(node)
                self.total_nodes += 1

            # 3. Evaluate the leaf with the NN or heuristic fallback.
            value = self._simulate(node)

            # 4. Accumulate the owner-perspective value to the root.
            self._backpropagate(node, value)

        # Return the most visited root move after the fixed search budget.
        if len(self.root.children) == 0:
            # No valid moves
            return (-1, -1)

        best_child = self.root.most_visited_child()
        return best_child.move

    def _select(self, node: MCTSNode) -> MCTSNode:
        """
        Selection phase: Traverse tree using UCB1 until we find a node to expand.

        Args:
            node: Current node

        Returns:
            Leaf node to expand
        """
        while not node.is_terminal():
            if not node.is_fully_expanded():
                return node
            else:
                node = node.best_child(self.exploration_constant, self.player_id)

        return node

    def _expand(self, node: MCTSNode) -> MCTSNode:
        """
        Expansion phase: Add a new child to the tree.

        Args:
            node: Node to expand

        Returns:
            Newly created child node
        """
        if len(node.untried_moves) == 0:
            return node

        # Sample one untried move without changing the remaining order.
        move = random.choice(node.untried_moves)
        node.untried_moves.remove(move)

        # Apply the candidate move on a private board copy.
        row, col = move
        new_board = node.board_state.copy()

        # Infer the side to move from the current stone counts.
        black_stones = np.sum(node.board_state == 1)
        white_stones = np.sum(node.board_state == -1)

        if black_stones == white_stones:
            current_player = 1  # Black moves (if equal, black goes first)
        else:
            current_player = -1  # White moves

        # Apply captures and suicide rules exactly once.
        legal, captured = self.go_rules.apply_move(new_board, row, col, current_player)

        # The node filtered this move already; retain the defensive check.
        if not legal:
            return node

        # Build the child with legal moves for the next player.
        next_player = -current_player
        child = MCTSNode(new_board, parent=node, move=move, go_rules=self.go_rules, player_id=next_player)
        node.children.append(child)

        return child

    def _simulate(self, node: MCTSNode) -> float:
        """
        Simulation phase: Evaluate position using trained crossbar NN.

        Uses the trained crossbar neural network
        for position evaluation instead of heuristic with random noise.

        The crossbar NN performs:
            features = board_to_features(board)  # 162 features for 9x9
            hidden = ReLU(features @ weights1)   # 162 → 64
            output = softmax(hidden @ weights2)  # 64 → 3 [P(W), P(D), P(B)]

        Args:
            node: Node to simulate from

        Returns:
            Value estimate (1.0 = Black wins, 0.0 = White wins, 0.5 = draw)
        """
        # Evaluate from Black's perspective using the selected value model.
        if self.crossbar_nn is not None:
            outcome = self.crossbar_nn.evaluate(node.board_state)
        else:
            outcome, details = self.evaluator.evaluate_position(node.board_state)

        # Convert the black-perspective outcome to the MCTS owner's perspective.
        if self.player_id == -1:  # White player
            value = 1.0 - outcome
        else:  # Black player
            value = outcome

        return value

    def _backpropagate(self, node: MCTSNode, value: float):
        """
        Backpropagation phase: Update statistics up the tree.

        Args:
            node: Leaf node to start from
            value: Simulated value
        """
        while node is not None:
            node.visits += 1
            node.value += value
            node = node.parent

    def get_tree_stats(self) -> dict:
        """
        Get statistics about the MCTS tree.

        Returns:
            Dictionary with tree statistics
        """
        if self.root is None:
            return {'nodes': 0, 'root_visits': 0}

        return {
            'nodes': self.total_nodes,
            'root_visits': self.root.visits,
            'root_value': self.root.value,
            'root_children': len(self.root.children)
        }


def test_mcts_player():
    """Test MCTS player on simple position."""
    print("Testing MCTS Player")
    print("=" * 80)

    # Create test board (5x5)
    board = np.zeros((5, 5), dtype=int)
    board[2, 2] = 1  # Black in center

    # Create player
    player = SimplifiedMCTSPlayer(
        board_size=5,
        weights_file=None,
        iterations=500,
        player_id=-1  # White to move
    )

    print("Test board (White to move):")
    for row in board:
        print(" ".join([
            'B' if x == 1 else 'W' if x == -1 else '.'
            for x in row
        ]))
    print()

    print(f"Running {player.iterations} MCTS iterations...")
    move = player.select_move(board)

    print(f"Selected move: {move} (row={move[0]}, col={move[1]})")
    print()

    stats = player.get_tree_stats()
    print(f"Tree statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print()

    # Verify move is valid
    assert board[move[0], move[1]] == 0, "Selected move should be on empty position"

    print("✓ MCTS player test passed!")


if __name__ == "__main__":
    test_mcts_player()
