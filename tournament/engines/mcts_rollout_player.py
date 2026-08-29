# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
MCTS Player with Random Rollouts for Tournament Play.

This is the proper MCTS baseline: tree search with random rollout evaluation
(no neural network). It uses the same tree structure and perspective-correct
UCB1 selection as the NN-based players, but evaluates leaf nodes by playing
random moves to terminal/max-depth and scoring with the heuristic evaluator.

This player enables the critical comparison:
  MCTS+NN (crossbar) vs MCTS+Rollout (same iterations)
which proves whether the NN gives useful signal beyond random rollouts.
"""

import numpy as np
import random
import math
from typing import List, Tuple, Optional

from tournament.engines.heuristic_eval import HeuristicEvaluator
from tournament.engines.go_rules import GoRules


class MCTSNode:
    """Node in the MCTS tree."""

    def __init__(self, board_state: np.ndarray, parent: Optional['MCTSNode'] = None,
                 move: Optional[Tuple[int, int]] = None, go_rules: Optional[GoRules] = None,
                 player_id: int = 1):
        self.board_state = board_state.copy()
        self.parent = parent
        self.move = move
        self.children: List['MCTSNode'] = []
        self.visits = 0
        self.value = 0.0
        self.untried_moves: List[Tuple[int, int]] = []
        self.player_to_move = player_id  # Track whose turn it is

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

    def best_child(self, exploration_constant: float = 1.41, mcts_player_id: int = 1) -> 'MCTSNode':
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
            exploration = exploration_constant * math.sqrt(math.log(self.visits) / child.visits)
            score = exploitation + exploration

            if score > best_score:
                best_score = score
                best_node = child

        return best_node

    def most_visited_child(self) -> 'MCTSNode':
        return max(self.children, key=lambda child: child.visits)


class MCTSRolloutPlayer:
    """
    MCTS player using random rollouts for leaf evaluation.

    This is the standard MCTS baseline without any neural network.
    Leaf nodes are evaluated by playing random legal moves until terminal
    state or max depth, then scoring with the heuristic evaluator.
    """

    def __init__(
        self,
        board_size: int,
        iterations: int = 1000,
        exploration_constant: float = 1.41,
        player_id: int = 1,
        max_rollout_depth: int = 80,
        **kwargs
    ):
        self.board_size = board_size
        self.iterations = iterations
        self.exploration_constant = exploration_constant
        self.player_id = player_id
        self.max_rollout_depth = max_rollout_depth

        self.go_rules = GoRules(board_size)
        self.evaluator = HeuristicEvaluator(board_size)

        self.root: Optional[MCTSNode] = None
        self.total_nodes = 0

    def select_move(self, board_state: np.ndarray) -> Tuple[int, int]:
        """Select best move using MCTS with random rollouts."""
        # Build a fresh search tree for this board position.
        self.root = MCTSNode(board_state, go_rules=self.go_rules, player_id=self.player_id)
        self.total_nodes = 1

        # Run the four MCTS stages for the fixed iteration budget.
        for _ in range(self.iterations):
            # 1. Select a tree frontier with UCB1.
            node = self._select(self.root)

            # 2. Expand one legal untried move.
            if not node.is_terminal():
                node = self._expand(node)
                self.total_nodes += 1

            # 3. Estimate the leaf with a random rollout.
            value = self._rollout(node)

            # 4. Accumulate the owner-perspective value to the root.
            self._backpropagate(node, value)

        if len(self.root.children) == 0:
            return (-1, -1)

        return self.root.most_visited_child().move

    def _select(self, node: MCTSNode) -> MCTSNode:
        while not node.is_terminal():
            if not node.is_fully_expanded():
                return node
            else:
                node = node.best_child(self.exploration_constant, self.player_id)
        return node

    def _expand(self, node: MCTSNode) -> MCTSNode:
        if len(node.untried_moves) == 0:
            return node

        move = random.choice(node.untried_moves)
        node.untried_moves.remove(move)

        row, col = move
        new_board = node.board_state.copy()

        # Infer the side to move from the current stone counts.
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

    def _rollout(self, node: MCTSNode) -> float:
        """
        Random rollout: play random legal moves until terminal or max depth,
        then evaluate with heuristic.

        Returns value from the MCTS owner's perspective.
        """
        rollout_board = node.board_state.copy()

        # Infer the side to move at the start of the rollout.
        black_stones = np.sum(rollout_board == 1)
        white_stones = np.sum(rollout_board == -1)
        current_player = 1 if black_stones == white_stones else -1

        for _ in range(self.max_rollout_depth):
            # Enumerate legal rollout moves in row-major order.
            legal_moves = []
            for row in range(self.board_size):
                for col in range(self.board_size):
                    if rollout_board[row, col] == 0:
                        if self.go_rules.is_legal_move(rollout_board, row, col, current_player):
                            legal_moves.append((row, col))

            if not legal_moves:
                break

            # Sample one legal rollout move, then alternate players.
            move = random.choice(legal_moves)
            self.go_rules.apply_move(rollout_board, move[0], move[1], current_player)
            current_player = -current_player

        # Score the final rollout position from Black's perspective.
        outcome, _ = self.evaluator.evaluate_position(rollout_board)

        # Convert the outcome to the MCTS owner's perspective.
        if self.player_id == -1:
            outcome = 1.0 - outcome

        return outcome

    def _backpropagate(self, node: MCTSNode, value: float):
        """Backpropagate value (from MCTS owner's perspective) up the tree."""
        while node is not None:
            node.visits += 1
            node.value += value
            node = node.parent

    def get_tree_stats(self) -> dict:
        if self.root is None:
            return {'nodes': 0, 'root_visits': 0, 'type': 'mcts_rollout'}

        return {
            'nodes': self.total_nodes,
            'root_visits': self.root.visits,
            'root_value': self.root.value,
            'root_children': len(self.root.children),
            'type': 'mcts_rollout'
        }


if __name__ == "__main__":
    print("Testing MCTS Rollout Player")
    print("=" * 60)

    board = np.zeros((9, 9), dtype=int)
    board[4, 4] = 1   # Black center
    board[3, 4] = -1   # White

    player = MCTSRolloutPlayer(
        board_size=9,
        iterations=100,
        player_id=1
    )

    print(f"Running {player.iterations} MCTS+Rollout iterations...")
    move = player.select_move(board)
    print(f"Selected move: {move}")
    stats = player.get_tree_stats()
    print(f"Tree stats: {stats}")
    print("Done.")
