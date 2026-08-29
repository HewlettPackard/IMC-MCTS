# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
MCTS Engine with Behavioral RTL Simulator as Evaluator.

Supports both NN-guided evaluation (via BehavioralSimulator) and
random rollout baseline. Uses proper Go rules for move generation.

Architecture:
  - UCB1 selection (c=0.7 for NN, c=1.414 for random rollout)
  - Single-child expansion per iteration
  - Eval cache to avoid redundant NN forward passes
  - Perspective-correct backpropagation
"""

import math
import random
import numpy as np
from typing import Tuple, Optional, Dict, List

from engine.go_engine import GoEngine
from engine.behavioral_sim import BehavioralSimulator


class MCTSEngine:
    """MCTS with behavioral simulator evaluation."""

    def __init__(
        self,
        go_engine: GoEngine,
        simulator: Optional[BehavioralSimulator] = None,
        iterations: int = 2000,
        exploration_c: Optional[float] = None,
        max_rollout_depth: int = 200,
    ):
        """
        Args:
            go_engine: Go rules engine
            simulator: BehavioralSimulator for NN eval (None = random rollout)
            iterations: MCTS iterations per move
            exploration_c: UCB1 exploration constant (auto: 0.7 for NN, 1.414 for rollout)
            max_rollout_depth: Max depth for random rollouts
        """
        self.go = go_engine
        self.sim = simulator
        self.iterations = iterations
        self.max_rollout_depth = max_rollout_depth

        if exploration_c is not None:
            self.c = exploration_c
        elif simulator is not None:
            self.c = 0.7  # NN-guided: less exploration needed
        else:
            self.c = 1.414  # Random rollout: sqrt(2)

        # Cache NN values by board and side to move during one search.
        self._eval_cache: Dict[int, float] = {}
        self._cache_hits = 0
        self._cache_misses = 0

        # Cache legal move lists by board during one search.
        self._legal_cache: Dict[int, list] = {}

    def _board_hash(self, board: np.ndarray) -> int:
        """Fast hash for eval cache."""
        return hash(board.tobytes())

    def _make_node(self, state: dict, parent_idx: Optional[int] = None,
                   move: Optional[Tuple[int, int]] = None) -> dict:
        """Create a new tree node."""
        return {
            'state': state,
            'parent': parent_idx,
            'move': move,
            'visits': 0,
            'value': 0.0,       # Accumulated value from Black's perspective
            'children': [],      # List of child indices
            'untried_moves': None,  # Lazily initialized
            'is_terminal': None,
        }

    def _select(self, nodes: List[dict]) -> int:
        """Select leaf node using vectorized UCB1."""
        idx = 0
        while True:
            node = nodes[idx]

            if node['is_terminal'] is None:
                node['is_terminal'] = self.go.is_terminal(node['state'])
            if node['is_terminal']:
                return idx

            if node['untried_moves'] is None:
                board_hash = self._board_hash(node['state']['board'])
                if board_hash in self._legal_cache:
                    node['untried_moves'] = list(self._legal_cache[board_hash])
                else:
                    moves = list(self.go.get_legal_moves(node['state']))
                    self._legal_cache[board_hash] = moves
                    node['untried_moves'] = list(moves)
                # Only allow pass if no board moves or game is late
                if (len(node['untried_moves']) > 1
                        and node['state']['move_count'] < 120
                        and node['untried_moves'][-1] == (-1, -1)):
                    node['untried_moves'].pop()
            if node['untried_moves']:
                return idx

            children = node['children']
            if not children:
                return idx

            # Compute all child UCB1 scores in one vectorized step.
            n_children = len(children)
            visits = np.empty(n_children, dtype=np.float64)
            values = np.empty(n_children, dtype=np.float64)
            for child_offset, child_index in enumerate(children):
                visits[child_offset] = nodes[child_index]['visits']
                values[child_offset] = nodes[child_index]['value']

            # Preserve first-child priority among unvisited children.
            zero_mask = visits == 0
            if np.any(zero_mask):
                idx = children[np.argmax(zero_mask)]
                continue

            exploitation = values / visits
            if node['state']['current_player'] == -1:
                exploitation = 1.0 - exploitation

            exploration = self.c * np.sqrt(math.log(node['visits']) / visits)
            scores = exploitation + exploration
            idx = children[np.argmax(scores)]

    def _expand(self, nodes: List[dict], node_idx: int) -> int:
        """Expand one untried child."""
        node = nodes[node_idx]

        if node['is_terminal'] is None:
            node['is_terminal'] = self.go.is_terminal(node['state'])
        if node['is_terminal']:
            return node_idx

        if node['untried_moves'] is None:
            board_hash = self._board_hash(node['state']['board'])
            if board_hash in self._legal_cache:
                node['untried_moves'] = list(self._legal_cache[board_hash])
            else:
                moves = list(self.go.get_legal_moves(node['state']))
                self._legal_cache[board_hash] = moves
                node['untried_moves'] = list(moves)
            # Only allow pass if no board moves or game is late
            if (len(node['untried_moves']) > 1
                    and node['state']['move_count'] < 120
                    and node['untried_moves'][-1] == (-1, -1)):
                node['untried_moves'].pop()
        if not node['untried_moves']:
            return node_idx

        move = node['untried_moves'].pop()
        new_state = self.go.apply_move(node['state'], move, lightweight=True)

        child = self._make_node(new_state, node_idx, move)
        child_idx = len(nodes)
        nodes.append(child)
        node['children'].append(child_idx)

        return child_idx

    def _evaluate(self, state: dict) -> float:
        """Evaluate position. Returns value from Black's perspective [0, 1]."""
        # Terminal states use the exact Go score.
        if self.go.is_terminal(state):
            return self.go.get_result_black(state)

        # Non-terminal NN evaluation uses board plus side-to-move caching.
        if self.sim is not None:
            board = state['board']
            player = state['current_player']
            # Include current_player in cache key so same board with different
            # player to move gets different evaluations
            cache_key = (self._board_hash(board), player)
            if cache_key in self._eval_cache:
                self._cache_hits += 1
                return self._eval_cache[cache_key]

            self._cache_misses += 1
            value = self.sim.evaluate(board, player)
            self._eval_cache[cache_key] = value
            return value

        # Without an NN, estimate the leaf by random rollout.
        return self._random_rollout(state)

    def _random_rollout(self, state: dict) -> float:
        """Random rollout to terminal state. Returns result for Black."""
        rollout_state = state
        for _ in range(self.max_rollout_depth):
            if self.go.is_terminal(rollout_state):
                break
            moves = self.go.get_legal_moves(rollout_state)
            if not moves:
                break
            move = random.choice(moves)
            rollout_state = self.go.apply_move(rollout_state, move)

        return self.go.get_result_black(rollout_state)

    def _backpropagate(self, nodes: List[dict], node_idx: int, value: float):
        """Backpropagate value up the tree. Value is always from Black's perspective."""
        idx = node_idx
        while idx is not None:
            nodes[idx]['visits'] += 1
            nodes[idx]['value'] += value
            idx = nodes[idx]['parent']

    def search(self, state: dict) -> Tuple[int, int]:
        """
        Run MCTS search and return the best move.

        Args:
            state: Current game state (from GoEngine)

        Returns:
            Best move as (row, col) tuple, or (-1, -1) for pass
        """
        # Start each search with fresh evaluation and legal-move caches.
        self._eval_cache.clear()
        self._legal_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0

        root = self._make_node(state)
        nodes = [root]

        # Run selection, expansion, evaluation, and backpropagation explicitly.
        for _ in range(self.iterations):
            leaf_idx = self._select(nodes)
            child_idx = self._expand(nodes, leaf_idx)
            value = self._evaluate(nodes[child_idx]['state'])
            self._backpropagate(nodes, child_idx, value)

        # Return the most visited root child after the fixed budget.
        if not root['children']:
            moves = self.go.get_legal_moves(state)
            return random.choice(moves) if moves else (-1, -1)

        best_child_idx = max(root['children'], key=lambda child_index: nodes[child_index]['visits'])
        return nodes[best_child_idx]['move']

    def get_stats(self) -> dict:
        """Return search statistics."""
        return {
            'iterations': self.iterations,
            'exploration_c': self.c,
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'has_nn': self.sim is not None,
        }


def test_mcts_engine():
    """Quick test with random rollout."""
    go = GoEngine(9)
    state = go.initial_state()

    # Random rollout MCTS (no NN)
    mcts = MCTSEngine(go, simulator=None, iterations=100)
    move = mcts.search(state)
    assert move is not None
    assert move == (-1, -1) or (0 <= move[0] < 9 and 0 <= move[1] < 9)

    print(f"MCTS test passed! First move: {move}")
    print(f"Stats: {mcts.get_stats()}")


if __name__ == "__main__":
    test_mcts_engine()
