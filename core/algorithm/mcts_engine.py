# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Game-agnostic MCTS engine with random rollouts (no NN needed).

Supports any game implementing the GameInterface ABC.
Uses UCB1 selection, full expansion, random rollouts, and backpropagation.
"""

import math
import random


class MCTSEngine:
    """Monte Carlo Tree Search engine with random rollouts."""

    def __init__(self, game, iterations=1000, exploration_c=None, eval_fn=None):
        self.game = game
        self.iterations = iterations
        self.eval_fn = eval_fn
        self.max_rollout_depth = 200
        # When using NN eval, reduce exploration since the value estimates
        # are more informed (less noise) than random rollouts.
        if exploration_c is not None:
            self.exploration_c = exploration_c
        elif eval_fn is not None:
            self.exploration_c = 0.7
        else:
            self.exploration_c = 1.414

    def _make_node(self, board, player, parent=None, move=None):
        """Create a new tree node."""
        return {
            "board": board,
            "player": player,
            "parent": parent,
            "move": move,
            "visits": 0,
            "value": 0.0,
            "children": [],
            "untried_moves": None,  # lazily initialized
            "is_terminal": None,
        }

    def _ucb1(self, node, child):
        """UCB1 selection formula with proper player perspective.

        Values are stored from player 1's perspective. When player 2 is
        selecting (node["player"] == 2), we flip the exploitation term so
        player 2 maximizes its own value (= minimizes player 1's value).
        """
        if child["visits"] == 0:
            return float("inf")
        exploitation_term = child["value"] / child["visits"]
        # Player 2 wants to minimize player 1's value
        if self.game.num_players == 2 and node["player"] == 2:
            exploitation_term = 1.0 - exploitation_term
        exploration_term = self.exploration_c * math.sqrt(
            math.log(node["visits"]) / child["visits"]
        )
        return exploitation_term + exploration_term

    def _select(self, nodes, root_idx):
        """Select a leaf node using UCB1."""
        node_index = root_idx
        while True:
            current_node = nodes[node_index]
            # Check terminal
            if current_node["is_terminal"] is None:
                current_node["is_terminal"] = self.game.is_terminal(current_node["board"])
            if current_node["is_terminal"]:
                return node_index
            # Initialize untried moves if needed
            if current_node["untried_moves"] is None:
                current_node["untried_moves"] = list(
                    self.game.get_legal_moves(current_node["board"], current_node["player"])
                )
            # If there are untried moves, this node needs expansion
            if current_node["untried_moves"]:
                return node_index
            # All moves tried; select best child via UCB1
            if not current_node["children"]:
                return node_index
            best_child_index = max(current_node["children"],
                                   key=lambda child_index: self._ucb1(current_node, nodes[child_index]))
            node_index = best_child_index
        return node_index

    def _expand(self, nodes, node_idx):
        """Expand ONE untried child per iteration (standard MCTS)."""
        parent_node = nodes[node_idx]
        if parent_node["is_terminal"] is None:
            parent_node["is_terminal"] = self.game.is_terminal(parent_node["board"])
        if parent_node["is_terminal"]:
            return node_idx
        if parent_node["untried_moves"] is None:
            parent_node["untried_moves"] = list(
                self.game.get_legal_moves(parent_node["board"], parent_node["player"])
            )
        if not parent_node["untried_moves"]:
            return node_idx

        # Pop one untried move and expand it
        selected_move = parent_node["untried_moves"].pop()
        child_board = self.game.apply_move(parent_node["board"], selected_move, parent_node["player"])
        if self.game.num_players == 1:
            next_player = 1
        else:
            next_player = 3 - parent_node["player"]
        child_node = self._make_node(child_board, next_player, node_idx, selected_move)
        child_index = len(nodes)
        nodes.append(child_node)
        parent_node["children"].append(child_index)

        return child_index

    def _rollout(self, board, player):
        """Evaluate a leaf position. Uses eval_fn if provided, else random rollout.
        Returns result for player 1."""
        if self.eval_fn is not None:
            # Always use true game result for terminal states
            if self.game.is_terminal(board):
                return self.game.get_result(board, 1)
            return self.eval_fn(board, player)
        current_board = board.copy()
        current_player = player

        for _ in range(self.max_rollout_depth):
            if self.game.is_terminal(current_board):
                break
            legal_moves = self.game.get_legal_moves(current_board, current_player)
            if not legal_moves:
                break
            selected_move = random.choice(legal_moves)
            current_board = self.game.apply_move(current_board, selected_move, current_player)
            if self.game.num_players == 1:
                current_player = 1
            else:
                current_player = 3 - current_player

        # Return result from player 1's perspective
        return self.game.get_result(current_board, 1)

    def _backpropagate(self, nodes, node_idx, result):
        """Backpropagate the rollout result up the tree.

        Always stores values from player 1's perspective. The perspective
        flip is handled during selection in _ucb1() instead.
        """
        node_index = node_idx
        while node_index is not None:
            current_node = nodes[node_index]
            current_node["visits"] += 1
            current_node["value"] += result  # Always from player 1's perspective
            node_index = current_node["parent"]

    def search(self, board, player):
        """
        Run MCTS search and return the best move.

        Args:
            board: Current board state
            player: Current player (1 or 2)

        Returns:
            Best move as (row, col) tuple
        """
        root_node = self._make_node(board, player)
        tree_nodes = [root_node]

        for _ in range(self.iterations):
            # Selection
            leaf_index = self._select(tree_nodes, 0)
            # Expansion
            child_index = self._expand(tree_nodes, leaf_index)
            # Rollout
            child_node = tree_nodes[child_index]
            rollout_result = self._rollout(child_node["board"], child_node["player"])
            # Backpropagation
            self._backpropagate(tree_nodes, child_index, rollout_result)

        # Choose move with most visits
        root_node = tree_nodes[0]
        if not root_node["children"]:
            legal_moves = self.game.get_legal_moves(board, player)
            return random.choice(legal_moves) if legal_moves else (0, 0)

        best_child_index = max(root_node["children"], key=lambda child_index: tree_nodes[child_index]["visits"])
        return tree_nodes[best_child_index]["move"]

    def play_game(self):
        """
        Play a complete game using MCTS for both players (or single player).

        Returns:
            Dictionary with game record: moves, result, game_length, scores
        """
        current_board = self.game.initial_state()
        current_player = 1
        move_history = []
        move_count = 0

        while not self.game.is_terminal(current_board) and move_count < 500:
            selected_move = self.search(current_board, current_player)
            current_board = self.game.apply_move(current_board, selected_move, current_player)
            move_history.append({"player": current_player, "move": selected_move})
            move_count += 1

            if self.game.num_players == 1:
                current_player = 1
            else:
                current_player = 3 - current_player

        result_p1 = self.game.get_result(current_board, 1)
        result_p2 = self.game.get_result(current_board, 2) if self.game.num_players == 2 else None

        # Collect game-specific metrics
        game_metrics = self.game.get_metrics(current_board)
        # Add path_length for navigation games (derived from move count)
        if "reached_goal" in game_metrics:
            game_metrics["path_length"] = move_count
            optimal_path_length = game_metrics.get("optimal_path_length", -1)
            if optimal_path_length > 0 and move_count > 0 and game_metrics.get("reached_goal"):
                game_metrics["path_efficiency"] = optimal_path_length / move_count
            else:
                game_metrics["path_efficiency"] = 0.0

        return {
            "game": self.game.name,
            "moves": move_history,
            "game_length": move_count,
            "result_p1": result_p1,
            "result_p2": result_p2,
            "num_players": self.game.num_players,
            "iterations": self.iterations,
            "metrics": game_metrics,
        }
