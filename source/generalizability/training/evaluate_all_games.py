#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
MCTS+NN vs MCTS+Random Evaluation Framework

Compares crossbar NN-guided MCTS against random-rollout MCTS across all 13 games.
For 2-player games: plays head-to-head, alternating colors.
For 1-player games: compares success rates on the same starting states.

Usage:
  python evaluate_all_games.py                          # All games
  python evaluate_all_games.py --games hex gomoku        # Specific games
  python evaluate_all_games.py --num_games 50 --mcts_iter 200  # More games/search
"""

import os
import sys
import math
import json
import pickle
import random
import time
import importlib.util
import argparse
import numpy as np
from typing import List, Tuple, Optional, Dict, Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

from generalizability.games import GAME_REGISTRY

# Game -> (board_size, hidden_size)
GAME_CONFIGS = {
    'go':               (9,  96),
    'hex':              (11, 96),
    'gomoku':           (15, 128),
    'havannah':         (15, 128),
    'othello':          (8,  96),
    'connect_four':     (8,  96),
    'pente':            (19, 192),
    'breakthrough':     (8,  96),
    'protein_folding':  (13, 128),
    'nonograms':        (9,  96),
    'frozen_lake':      (8,  96),
    'minigrid':         (8,  96),
    'minesweeper':      (9,  96),
}


# ---------------------------------------------------------------------------
# Crossbar NN (inference only)
# ---------------------------------------------------------------------------
class CrossbarNN:
    """Load conductance matrices and run the explicit crossbar forward pass."""

    def __init__(self, weights_path: str):
        with open(weights_path, 'rb') as f:
            ckpt = pickle.load(f)
        self.weights1 = np.array(ckpt['weights1'], dtype=np.float32)
        self.weights2 = np.array(ckpt['weights2'], dtype=np.float32)

    def evaluate(self, features: np.ndarray) -> float:
        """Forward pass → value in [-1, 1].  Positive favours P1/good outcome."""
        W1_eff = (self.weights1 - 50.0) / 50.0
        hidden = np.maximum(0, features @ W1_eff)

        W2_eff = (self.weights2 - 50.0) / 50.0
        logits = hidden @ W2_eff
        if self.weights2.shape[1] == 1:
            # Regression mode: sigmoid → [0,1] → map to [-1,1]
            logit = float(logits[0])
            probability = 1.0 / (1.0 + np.exp(-np.clip(logit, -20, 20)))
            return probability * 2.0 - 1.0  # [0,1] → [-1,1]
        else:
            # Classification mode: softmax → P(P1 wins) - P(P2 wins)
            exp_logits = np.exp(logits - logits.max())
            probabilities = exp_logits / exp_logits.sum()
            # class 0 = P2 wins / bad,  class 1 = draw / neutral,  class 2 = P1 wins / good
            return float(probabilities[2] - probabilities[0])


# ---------------------------------------------------------------------------
# Coach loader (for board_to_features)
# ---------------------------------------------------------------------------
_coach_cache: Dict[str, Any] = {}


def load_coach(game_name: str):
    """Load the game's existing board-to-feature conversion."""
    if game_name in _coach_cache:
        return _coach_cache[game_name]
    coach_path = os.path.join(SCRIPT_DIR, 'games', game_name, 'coach.py')
    spec = importlib.util.spec_from_file_location(f'{game_name}_coach', coach_path)
    coach_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(coach_module)
    coach = coach_module.GameCoach()
    _coach_cache[game_name] = coach
    return coach


# ---------------------------------------------------------------------------
# MCTS
# ---------------------------------------------------------------------------
class MCTSNode:
    __slots__ = ('board', 'player', 'parent', 'move', 'children',
                 'untried_moves', 'visits', 'value')

    def __init__(self, board, player, parent=None, move=None):
        self.board = board
        self.player = player          # player to move from this node
        self.parent = parent
        self.move = move
        self.children: List['MCTSNode'] = []
        self.untried_moves: Optional[list] = None
        self.visits = 0
        self.value = 0.0              # cumulative value from MOVER's perspective
                                      # (the player who chose the move to reach this node)

    def ucb1(self, c: float = 1.414) -> float:
        if self.visits == 0:
            return float('inf')
        return (self.value / self.visits) + c * math.sqrt(
            math.log(self.parent.visits) / self.visits)


def mcts_search(game, board, player, nn: Optional[CrossbarNN],
                coach, num_iterations: int, max_rollout: int = 150,
                mix_lambda: float = 0.0) -> Optional[tuple]:
    """Run MCTS and return the best move.

    If nn is not None, leaf evaluation uses the crossbar NN.
    When mix_lambda > 0, blends NN value with a random rollout:
      result = (1 - mix_lambda) * nn_value + mix_lambda * rollout_value
    Otherwise, random rollouts are used.
    """
    root = MCTSNode(board, player)
    is_two_player = game.num_players == 2

    for _ in range(num_iterations):
        node = root
        sim_board = board.copy()
        sim_player = player

        # Stage 1: select until this simulation can expand.
        while (node.untried_moves is not None and
               len(node.untried_moves) == 0 and
               node.children):
            node = max(node.children, key=lambda n: n.ucb1())
            sim_board = node.board
            sim_player = node.player

        # Stage 2: expand one legal move.
        if node.untried_moves is None:
            if game.is_terminal(sim_board):
                node.untried_moves = []
            else:
                node.untried_moves = list(game.get_legal_moves(sim_board, sim_player))
                random.shuffle(node.untried_moves)

        if node.untried_moves and not game.is_terminal(sim_board):
            move = node.untried_moves.pop()
            new_board = game.apply_move(sim_board, move, sim_player)
            next_player = (3 - sim_player) if is_two_player else 1
            child = MCTSNode(new_board, next_player, parent=node, move=move)
            node.children.append(child)
            node = child
            sim_board = new_board
            sim_player = next_player

        # Stage 3: evaluate the leaf with the crossbar or a rollout.
        if nn is not None:
            # NN evaluation
            features = coach.board_to_features(sim_board)
            # Append turn indicator: 1.0 = P1's turn, 0.0 = P2's turn
            features.append(1.0 if sim_player == 1 else 0.0)
            features = np.array(features, dtype=np.float32)
            crossbar_value = nn.evaluate(features)             # [-1, 1]
            nn_result = (crossbar_value + 1.0) / 2.0            # [0, 1] from P1 perspective
            if mix_lambda > 0:
                # Blend NN value with a random rollout (AlphaGo-style)
                rollout_result = _random_rollout(game, sim_board.copy(), sim_player,
                                                 is_two_player, max_rollout)
                result_p1 = (1 - mix_lambda) * nn_result + mix_lambda * rollout_result
            else:
                result_p1 = nn_result
        else:
            # Random rollout
            result_p1 = _random_rollout(game, sim_board, sim_player,
                                        is_two_player, max_rollout)

        # Stage 4: backpropagate from the node's player perspective.
        # Store value from the node's player-to-move perspective
        while node is not None:
            node.visits += 1
            if is_two_player:
                node.value += result_p1 if node.player == 1 else (1.0 - result_p1)
            else:
                node.value += result_p1
            node = node.parent

    # Pick most-visited child
    if not root.children:
        moves = game.get_legal_moves(board, player)
        return random.choice(moves) if moves else None
    best = max(root.children, key=lambda n: n.visits)
    return best.move


def _random_rollout(game, board, player, is_two_player: bool,
                    max_depth: int) -> float:
    """Play random moves until terminal or depth limit.  Returns result in [0,1] for P1."""
    for _ in range(max_depth):
        if game.is_terminal(board):
            break
        moves = game.get_legal_moves(board, player)
        if not moves:
            break
        move = random.choice(moves)
        board = game.apply_move(board, move, player)
        player = (3 - player) if is_two_player else 1

    if game.is_terminal(board):
        return game.get_result(board, 1)   # from P1's perspective
    return 0.5  # timeout → uncertain


# ---------------------------------------------------------------------------
# Game playing
# ---------------------------------------------------------------------------
def play_two_player_game(game, coach, nn: Optional[CrossbarNN],
                         nn_is_player: int, mcts_iter: int,
                         max_moves: int, mix_lambda: float = 0.0) -> Dict:
    """Play one 2-player game.  nn_is_player = 1 or 2."""
    board = game.initial_state()
    current = 1
    move_count = 0

    while not game.is_terminal(board) and move_count < max_moves:
        moves = game.get_legal_moves(board, current)
        if not moves:
            break
        if current == nn_is_player:
            move = mcts_search(game, board, current, nn, coach, mcts_iter,
                               mix_lambda=mix_lambda)
        else:
            move = mcts_search(game, board, current, None, coach, mcts_iter)
        if move is None:
            break
        board = game.apply_move(board, move, current)
        current = 3 - current
        move_count += 1

    result_p1 = game.get_result(board, 1) if game.is_terminal(board) else 0.5
    nn_result = result_p1 if nn_is_player == 1 else (1.0 - result_p1)
    return {
        'nn_result': nn_result,       # 1.0 = NN won, 0.0 = NN lost, 0.5 = draw
        'result_p1': result_p1,
        'moves': move_count,
        'nn_side': nn_is_player,
    }


def play_single_player_game(game, coach, nn: Optional[CrossbarNN],
                            mcts_iter: int, max_moves: int,
                            mix_lambda: float = 0.0) -> Dict:
    """Play one single-player episode with MCTS+NN or MCTS+Random."""
    board = game.initial_state()
    move_count = 0

    while not game.is_terminal(board) and move_count < max_moves:
        moves = game.get_legal_moves(board, 1)
        if not moves:
            break
        move = mcts_search(game, board, 1, nn, coach, mcts_iter,
                           mix_lambda=mix_lambda)
        if move is None:
            break
        board = game.apply_move(board, move, 1)
        move_count += 1

    result = game.get_result(board, 1) if game.is_terminal(board) else 0.0
    return {'result': result, 'moves': move_count}


# ---------------------------------------------------------------------------
# Per-game evaluation
# ---------------------------------------------------------------------------
def evaluate_game(game_name: str, num_games: int, mcts_iter: int,
                  mix_lambda: float = 0.0) -> Dict:
    """Run full MCTS+NN vs MCTS+Random comparison for one game."""
    game = GAME_REGISTRY[game_name]
    board_size, hidden_size = GAME_CONFIGS[game_name]

    # Load coach and NN
    coach = load_coach(game_name)
    # Prefer self-play weights (trained on gameplay positions) over coach weights
    selfplay_path = os.path.join(SCRIPT_DIR, 'selfplay_data',
                                 f'weights_{game_name}', 'best_improved_model.pkl')
    coach_path = os.path.join(SCRIPT_DIR, 'games', game_name,
                              'results', 'best_improved_model.pkl')
    if os.path.exists(selfplay_path):
        weights_path = selfplay_path
        weights_source = 'selfplay'
    elif os.path.exists(coach_path):
        weights_path = coach_path
        weights_source = 'coach'
    else:
        return {'error': f'No trained weights found for {game_name}'}
    nn = CrossbarNN(weights_path)
    actual_hidden = nn.weights1.shape[1]

    max_moves = board_size * board_size * 2
    is_two_player = game.num_players == 2

    results = {
        'game': game_name,
        'board_size': board_size,
        'hidden_size': actual_hidden,
        'num_players': game.num_players,
        'mcts_iterations': mcts_iter,
        'num_games': num_games,
        'weights_source': weights_source,
    }

    t0 = time.time()

    if is_two_player:
        nn_wins, nn_losses, nn_draws = 0, 0, 0
        rand_wins, rand_losses, rand_draws = 0, 0, 0
        nn_move_lens, rand_move_lens = [], []
        half = num_games // 2

        for i in range(num_games):
            nn_side = 1 if i < half else 2
            res = play_two_player_game(game, coach, nn, nn_side, mcts_iter, max_moves,
                                         mix_lambda=mix_lambda)
            nn_move_lens.append(res['moves'])
            if res['nn_result'] > 0.5:
                nn_wins += 1
            elif res['nn_result'] < 0.5:
                nn_losses += 1
            else:
                nn_draws += 1

        # Also play games where "random" side uses MCTS+Random vs itself
        # (not needed — the comparison IS NN vs Random already)
        results['nn_wins'] = nn_wins
        results['nn_losses'] = nn_losses
        results['nn_draws'] = nn_draws
        results['nn_win_rate'] = nn_wins / num_games
        results['avg_game_length'] = np.mean(nn_move_lens)

    else:
        # Single-player: run same number of episodes with NN and with Random
        nn_scores, rand_scores = [], []
        nn_lens, rand_lens = [], []

        for _ in range(num_games):
            # NN-guided MCTS
            res_nn = play_single_player_game(game, coach, nn, mcts_iter, max_moves,
                                             mix_lambda=mix_lambda)
            nn_scores.append(res_nn['result'])
            nn_lens.append(res_nn['moves'])

            # Random-rollout MCTS
            res_rand = play_single_player_game(game, coach, None, mcts_iter, max_moves)
            rand_scores.append(res_rand['result'])
            rand_lens.append(res_rand['moves'])

        results['nn_avg_score'] = float(np.mean(nn_scores))
        results['rand_avg_score'] = float(np.mean(rand_scores))
        results['nn_success_rate'] = float(np.mean([1.0 if s >= 0.5 else 0.0 for s in nn_scores]))
        results['rand_success_rate'] = float(np.mean([1.0 if s >= 0.5 else 0.0 for s in rand_scores]))
        results['nn_avg_length'] = float(np.mean(nn_lens))
        results['rand_avg_length'] = float(np.mean(rand_lens))

    results['elapsed_sec'] = round(time.time() - t0, 1)
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='MCTS+NN vs MCTS+Random Evaluation')
    parser.add_argument('--games', nargs='+', default=None,
                        help='Games to evaluate (default: all)')
    parser.add_argument('--num_games', type=int, default=20,
                        help='Games per matchup (default 20)')
    parser.add_argument('--mcts_iter', type=int, default=100,
                        help='MCTS iterations per move (default 100)')
    parser.add_argument('--mix', type=float, default=0.0,
                        help='NN/rollout mixing ratio: 0=NN-only, 0.5=50/50, 1=rollout-only (default 0)')
    parser.add_argument('--output', type=str, default=None,
                        help='Save results JSON to this path')
    args = parser.parse_args()

    games = args.games or list(GAME_CONFIGS.keys())
    evaluation_results = []

    print("=" * 80)
    print("  MCTS+NN vs MCTS+Random Evaluation")
    print(f"  Games: {', '.join(games)}")
    print(f"  Games per matchup: {args.num_games}")
    print(f"  MCTS iterations/move: {args.mcts_iter}")
    if args.mix > 0:
        print(f"  NN/Rollout mixing: {args.mix:.0%} rollout + {1-args.mix:.0%} NN")
    print("=" * 80)
    print()

    for gname in games:
        if gname not in GAME_CONFIGS:
            print(f"  [SKIP] Unknown game: {gname}")
            continue
        board_size, hidden_size = GAME_CONFIGS[gname]
        game = GAME_REGISTRY[gname]
        print(f"  [{gname.upper()}] {board_size}x{board_size}  "
              f"{'2-player' if game.num_players == 2 else '1-player'}  "
              f"crossbar {board_size**2 * 2 + 1}→{hidden_size}→3")

        game_result = evaluate_game(gname, args.num_games, args.mcts_iter,
                                    mix_lambda=args.mix)
        evaluation_results.append(game_result)

        if 'error' in game_result:
            print(f"    ERROR: {game_result['error']}")
        elif game.num_players == 2:
            print(f"    [{game_result.get('weights_source','?')}] NN Win Rate: {game_result['nn_win_rate']:.0%}  "
                  f"(W:{game_result['nn_wins']} L:{game_result['nn_losses']} D:{game_result['nn_draws']})  "
                  f"Avg moves: {game_result['avg_game_length']:.0f}  "
                  f"hidden={game_result['hidden_size']}  "
                  f"[{game_result['elapsed_sec']}s]")
        else:
            print(f"    [{game_result.get('weights_source','?')}] NN success: {game_result['nn_success_rate']:.0%}  "
                  f"Rand success: {game_result['rand_success_rate']:.0%}  "
                  f"Improvement: {game_result['nn_success_rate'] - game_result['rand_success_rate']:+.0%}  "
                  f"hidden={game_result['hidden_size']}  "
                  f"[{game_result['elapsed_sec']}s]")
        print()

    # Summary table
    print("=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    print(f"  {'Game':<18} {'Board':>5}  {'Crossbar':>14}  {'NN vs Random':>14}  {'Avg Len':>7}")
    print("-" * 80)
    for game_result in evaluation_results:
        if 'error' in game_result:
            print(f"  {game_result['game']:<18} {'ERROR':>5}")
            continue
        bs = game_result['board_size']
        hs = game_result['hidden_size']
        crossbar = f"{bs**2*2+1}→{hs}→3"
        if game_result['num_players'] == 2:
            metric = f"{game_result['nn_win_rate']:>5.0%} win"
            length = f"{game_result['avg_game_length']:>5.0f}"
        else:
            metric = f"+{game_result['nn_success_rate'] - game_result['rand_success_rate']:>4.0%}"
            length = f"{game_result['nn_avg_length']:>5.0f}"
        print(f"  {game_result['game']:<18} {bs:>2}x{bs:<2}  {crossbar:>14}  {metric:>14}  {length:>7}")

    # Save results
    output_path = args.output or os.path.join(SCRIPT_DIR, 'evaluation_results.json')
    with open(output_path, 'w') as f:
        json.dump(evaluation_results, f, indent=2)
    print(f"\n  Results saved: {output_path}")


if __name__ == '__main__':
    main()
