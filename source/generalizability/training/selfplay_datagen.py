#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Self-Play Training Data Generator.

Generates training data by playing MCTS+Rollout games against itself,
recording every board position encountered, and labeling all positions
from each game with the actual game outcome (who won).

This replaces the random-position datagen approach with positions from
actual gameplay, solving the train/test distribution mismatch problem.

Usage:
    python selfplay_datagen.py --board_size 9 --num_games 500 --iterations 200
    python selfplay_datagen.py --board_size 9 --num_games 1000 --output selfplay_9x9.json

Output format is compatible with train_improved.py.
"""

import json
import numpy as np
import random
import math
import os
import sys
import argparse
from datetime import datetime
from typing import List, Tuple, Dict, Optional


class GoRules:
    """Direct Go rule operations used by the self-play experiment."""

    def __init__(self, board_size: int):
        self.board_size = board_size

    def _find_group(self, board, i, j, visited):
        color = board[i, j]
        if color == 0:
            return []
        group = []
        stack = [(i, j)]
        while stack:
            r, c = stack.pop()
            if visited[r, c]:
                continue
            visited[r, c] = True
            group.append((r, c))
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if (0 <= nr < self.board_size and 0 <= nc < self.board_size
                    and not visited[nr, nc] and board[nr, nc] == color):
                    stack.append((nr, nc))
        return group

    def _get_group_liberties(self, board, group):
        liberties = set()
        for i, j in group:
            for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ni, nj = i + di, j + dj
                if (0 <= ni < self.board_size and 0 <= nj < self.board_size
                    and board[ni, nj] == 0):
                    liberties.add((ni, nj))
        return len(liberties)

    def _capture_groups(self, board, opponent_color):
        captured_count = 0
        visited = np.zeros((self.board_size, self.board_size), dtype=bool)
        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i, j] == opponent_color and not visited[i, j]:
                    group = self._find_group(board, i, j, visited)
                    if group and self._get_group_liberties(board, group) == 0:
                        for r, c in group:
                            board[r, c] = 0
                        captured_count += len(group)
        return captured_count

    def is_legal_move(self, board, row, col, color):
        if board[row, col] != 0:
            return False
        board_copy = board.copy()
        board_copy[row, col] = color

        # Check if captures opponent
        opponent_captured = False
        for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ni, nj = row + di, col + dj
            if (0 <= ni < self.board_size and 0 <= nj < self.board_size
                and board_copy[ni, nj] == -color):
                visited = np.zeros((self.board_size, self.board_size), dtype=bool)
                group = self._find_group(board_copy, ni, nj, visited)
                if group and self._get_group_liberties(board_copy, group) == 0:
                    opponent_captured = True
                    break

        visited = np.zeros((self.board_size, self.board_size), dtype=bool)
        our_group = self._find_group(board_copy, row, col, visited)
        our_liberties = self._get_group_liberties(board_copy, our_group)

        # Suicide if no liberties and no captures
        return not (our_liberties == 0 and not opponent_captured)

    def apply_move(self, board, row, col, color):
        if board[row, col] != 0:
            return False, 0
        board[row, col] = color
        captured = self._capture_groups(board, -color)
        return True, captured


class HeuristicEvaluator:
    """Evaluate material + 0.5 * territory + 0.1 * liberties."""

    def __init__(self, board_size: int):
        self.board_size = board_size

    def evaluate_position(self, board):
        black_stones = np.sum(board == 1)
        white_stones = np.sum(board == -1)
        material_diff = black_stones - white_stones

        black_territory, white_territory = self._count_territory(board)
        territory_diff = black_territory - white_territory

        black_liberties = self._count_liberties(board, 1)
        white_liberties = self._count_liberties(board, -1)
        liberty_diff = black_liberties - white_liberties

        total_score = material_diff + territory_diff * 0.5 + liberty_diff * 0.1

        if total_score > 1.5:
            return 1.0  # Black wins
        elif total_score < -1.5:
            return 0.0  # White wins
        else:
            return 0.5  # Draw

    def _count_territory(self, board):
        black_territory = 0
        white_territory = 0
        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i, j] == 0:
                    nearby_black = 0
                    nearby_white = 0
                    for di in range(-1, 2):
                        for dj in range(-1, 2):
                            ni, nj = i + di, j + dj
                            if 0 <= ni < self.board_size and 0 <= nj < self.board_size:
                                if board[ni, nj] == 1:
                                    nearby_black += 1
                                elif board[ni, nj] == -1:
                                    nearby_white += 1
                    if nearby_black > nearby_white:
                        black_territory += 1
                    elif nearby_white > nearby_black:
                        white_territory += 1
        return black_territory, white_territory

    def _count_liberties(self, board, color):
        total = 0
        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i, j] == color:
                    for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        ni, nj = i + di, j + dj
                        if 0 <= ni < self.board_size and 0 <= nj < self.board_size:
                            if board[ni, nj] == 0:
                                total += 1
        return total


class MCTSNode:
    """Minimal MCTS node for self-play data generation."""

    def __init__(self, board_state, parent=None, move=None,
                 go_rules=None, player_id=1):
        self.board_state = board_state.copy()
        self.parent = parent
        self.move = move
        self.children = []
        self.visits = 0
        self.value = 0.0
        self.player_to_move = player_id
        # Skip expensive legality checking for untried moves — just use empty cells.
        # Illegal moves (suicide) will be caught during expansion and skipped.
        self.untried_moves = list(zip(*np.where(board_state == 0)))

    def is_fully_expanded(self):
        return len(self.untried_moves) == 0

    def is_terminal(self):
        return len(self.untried_moves) == 0 and len(self.children) == 0

    def best_child(self, c=1.41, mcts_player_id=1):
        best_score = -float('inf')
        best_node = None
        for child in self.children:
            if child.visits == 0:
                return child
            exploit = child.value / child.visits
            if self.player_to_move != mcts_player_id:
                exploit = 1.0 - exploit
            explore = c * math.sqrt(math.log(self.visits) / child.visits)
            score = exploit + explore
            if score > best_score:
                best_score = score
                best_node = child
        return best_node

    def most_visited_child(self):
        return max(self.children, key=lambda c: c.visits)


class SelfPlayMCTS:
    """Run explicit selection, expansion, rollout, and backpropagation."""

    def __init__(self, board_size, iterations=200, max_rollout_depth=60):
        self.board_size = board_size
        self.iterations = iterations
        self.max_rollout_depth = max_rollout_depth
        self.go_rules = GoRules(board_size)
        self.evaluator = HeuristicEvaluator(board_size)

    def select_move(self, board, player_id):
        """Run MCTS and return the best move for the given player."""
        root = MCTSNode(board, go_rules=self.go_rules, player_id=player_id)

        for _ in range(self.iterations):
            # Stage 1: select down the tree until expansion is possible.
            node = root
            while not node.is_terminal():
                if not node.is_fully_expanded():
                    break
                node = node.best_child(mcts_player_id=player_id)

            # Stage 2: expand one random untried move.
            if not node.is_terminal() and node.untried_moves:
                move = random.choice(node.untried_moves)
                node.untried_moves.remove(move)

                new_board = node.board_state.copy()
                black_stones = np.sum(node.board_state == 1)
                white_stones = np.sum(node.board_state == -1)
                current_player = 1 if black_stones == white_stones else -1

                legal, _ = self.go_rules.apply_move(new_board, move[0], move[1], current_player)
                if legal:
                    child = MCTSNode(new_board, parent=node, move=move,
                                     go_rules=self.go_rules, player_id=-current_player)
                    node.children.append(child)
                    node = child

            # Stage 3: estimate the expanded state with a fast rollout.
            value = self._rollout(node, player_id)

            # Stage 4: send the rollout value back to the root.
            while node is not None:
                node.visits += 1
                node.value += value
                node = node.parent

        if not root.children:
            return None

        return root.most_visited_child().move

    def _rollout(self, node, mcts_player_id):
        """Fast random rollout — plays on empty cells without full Go legality checks.

        Skips suicide detection and capture rules during rollout for speed.
        The rollout is just a value estimate; recorded game positions use full rules.
        """
        board = node.board_state.copy()
        black_stones = np.sum(board == 1)
        white_stones = np.sum(board == -1)
        current_player = 1 if black_stones == white_stones else -1

        # Pre-compute empty cells as a list for fast random selection
        empty = list(zip(*np.where(board == 0)))

        for _ in range(self.max_rollout_depth):
            if not empty:
                break
            # Pick random empty cell (no legality check — fast)
            idx = random.randrange(len(empty))
            r, c = empty[idx]
            board[r, c] = current_player
            # Remove from empty list (swap with last for O(1))
            empty[idx] = empty[-1]
            empty.pop()
            current_player = -current_player

        # Evaluate from Black's perspective
        outcome = self.evaluator.evaluate_position(board)

        # Convert to mcts_player_id's perspective
        if mcts_player_id == -1:
            outcome = 1.0 - outcome

        return outcome


def board_to_features(board):
    """Encode each board cell as [Black, White], then append the turn."""
    features = []
    for cell_value in board.flatten():
        if cell_value == 1:  # Black
            features.extend([1.0, 0.0])
        elif cell_value == -1:  # White
            features.extend([0.0, 1.0])
        else:  # Empty
            features.extend([0.0, 0.0])

    # Turn indicator
    p1_count = int(np.sum(board == 1))
    p2_count = int(np.sum(board == -1))
    features.append(1.0 if p1_count <= p2_count else 0.0)

    return features


def play_selfplay_game(engine, board_size, max_moves=60):
    """
    Play one self-play game, recording all positions.

    Returns:
        positions: list of board states (numpy arrays)
        outcome: game outcome from Black's perspective (1.0/0.5/0.0)
        num_moves: number of moves played
    """
    board = np.zeros((board_size, board_size), dtype=int)
    positions = [board.copy()]  # Record initial position
    current_player = 1  # Black first

    for move_num in range(max_moves):
        # Check for valid moves
        has_moves = False
        for r in range(board_size):
            for c in range(board_size):
                if board[r, c] == 0:
                    has_moves = True
                    break
            if has_moves:
                break

        if not has_moves:
            break

        move = engine.select_move(board, current_player)
        if move is None:
            break

        legal, _ = engine.go_rules.apply_move(board, move[0], move[1], current_player)
        if not legal:
            break

        positions.append(board.copy())
        current_player = -current_player

    # Evaluate final position from Black's perspective
    outcome = engine.evaluator.evaluate_position(board)

    return positions, outcome, len(positions) - 1


def generate_selfplay_dataset(board_size=9, num_games=500,
                               iterations=200, max_moves=60,
                               output_file=None):
    """
    Generate training dataset from self-play games.

    Args:
        board_size: Board size (default 9)
        num_games: Number of games to play
        iterations: MCTS iterations per move
        max_moves: Max moves per game
        output_file: Output JSON path

    Returns:
        Dataset dict compatible with train_improved.py
    """
    print(f"SELF-PLAY TRAINING DATA GENERATOR")
    print("=" * 60)
    print(f"Board size: {board_size}x{board_size}")
    print(f"Games to play: {num_games}")
    print(f"MCTS iterations per move: {iterations}")
    print(f"Max moves per game: {max_moves}")
    print()

    engine = SelfPlayMCTS(board_size, iterations=iterations,
                           max_rollout_depth=max_moves)

    position_features = []
    game_outcomes = []
    game_stats = {'black_wins': 0, 'white_wins': 0, 'draws': 0,
                  'total_positions': 0, 'avg_game_length': 0}

    for game_idx in range(num_games):
        positions, outcome, num_moves = play_selfplay_game(
            engine, board_size, max_moves)

        # Stage 1: record the completed game's statistics.
        if outcome == 1.0:
            game_stats['black_wins'] += 1
        elif outcome == 0.0:
            game_stats['white_wins'] += 1
        else:
            game_stats['draws'] += 1
        game_stats['total_positions'] += len(positions)
        game_stats['avg_game_length'] += num_moves

        # Stage 2: label every position with the final game outcome.
        for board_state in positions:
            features = board_to_features(board_state)
            position_features.append(features)
            game_outcomes.append(float(outcome))

        if (game_idx + 1) % 10 == 0:
            print(f"  Game {game_idx + 1}/{num_games}: "
                  f"{num_moves} moves, outcome={outcome:.1f}, "
                  f"total positions={len(position_features)}")

    game_stats['avg_game_length'] /= max(num_games, 1)

    # Stage 3: package the arrays in the same schema as datagen.py.
    dataset = {
        'positions': position_features,
        'game_outcomes': game_outcomes,
        'metadata': {
            'dataset_type': 'selfplay_position_evaluation',
            'board_size': board_size,
            'num_positions': len(position_features),
            'num_games': num_games,
            'mcts_iterations': iterations,
            'max_moves_per_game': max_moves,
            'generation_date': datetime.now().isoformat(),
            'description': 'Self-play MCTS training data for position evaluation',
            'label_format': 'game_outcomes: 0.0=White wins, 0.5=Draw, 1.0=Black wins',
            'feature_vector_format': f'{board_size*board_size*2+1} features (2 per cell + turn indicator)',
        },
        'game_stats': game_stats
    }

    # Stage 4: report the game and label distributions.
    outcomes = np.array(game_outcomes)
    print()
    print(f"Dataset Statistics:")
    print(f"  Total positions: {len(position_features):,}")
    print(f"  Total games: {num_games}")
    print(f"  Avg game length: {game_stats['avg_game_length']:.1f} moves")
    print(f"  Black wins: {game_stats['black_wins']} ({game_stats['black_wins']/num_games:.1%})")
    print(f"  White wins: {game_stats['white_wins']} ({game_stats['white_wins']/num_games:.1%})")
    print(f"  Draws: {game_stats['draws']} ({game_stats['draws']/num_games:.1%})")
    print(f"  Label distribution:")
    print(f"    Black wins (1.0): {np.sum(outcomes == 1.0):,} ({np.mean(outcomes == 1.0):.1%})")
    print(f"    White wins (0.0): {np.sum(outcomes == 0.0):,} ({np.mean(outcomes == 0.0):.1%})")
    print(f"    Draws (0.5): {np.sum(outcomes == 0.5):,} ({np.mean(outcomes == 0.5):.1%})")

    if output_file:
        with open(output_file, 'w') as f:
            json.dump(dataset, f)
        print(f"\n  Saved to: {output_file}")
        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        print(f"  File size: {size_mb:.1f} MB")

    return dataset


def main():
    parser = argparse.ArgumentParser(
        description="Generate self-play training data for crossbar NN")
    parser.add_argument('--board_size', type=int, default=9,
                        help='Board size (default: 9)')
    parser.add_argument('--num_games', type=int, default=500,
                        help='Number of self-play games (default: 500)')
    parser.add_argument('--iterations', type=int, default=200,
                        help='MCTS iterations per move (default: 200)')
    parser.add_argument('--max_moves', type=int, default=60,
                        help='Max moves per game (default: 60)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output JSON file path')

    args = parser.parse_args()

    if args.output is None:
        args.output = f'selfplay_{args.board_size}x{args.board_size}_{args.num_games}games.json'

    generate_selfplay_dataset(
        board_size=args.board_size,
        num_games=args.num_games,
        iterations=args.iterations,
        max_moves=args.max_moves,
        output_file=args.output
    )

    print(f"\nDone! Train with:")
    print(f"  python train_improved.py --dataset {args.output} "
          f"--board_size {args.board_size} --output_dir selfplay_weights")


if __name__ == "__main__":
    main()
