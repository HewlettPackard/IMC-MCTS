#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
KataGo Training Data Generator.

Generates 200k positions from KataGo self-play for crossbar NN training.
- 50 visits per move (fast search)
- 163 features per position (9x9 x 2 channels + turn bit)
- Color-flip augmentation: each position included twice
- Discrete outcome labels: <0.35 -> White(0.0), >0.65 -> Black(1.0), else Draw(0.5)

Phase distribution target: 30% opening, 30% midgame, 40% endgame
Outcome distribution target: ~41% White, ~17% Draw, ~41% Black
"""

import json
import os
import sys
import subprocess
import numpy as np
from datetime import datetime
from typing import Tuple, Optional
from multiprocessing import Process, Queue


class KataGoDataGenerator:
    """Generate training data from KataGo self-play."""

    def __init__(self, board_size: int = 9,
                 katago_path: str = "katago",
                 model_path: Optional[str] = None,
                 config_path: Optional[str] = None,
                 visits: int = 50):
        self.board_size = board_size
        self.visits = visits
        self.katago_path = katago_path
        self.model_path = model_path
        self.config_path = config_path

        # GTP column letters (skip I)
        self._col_letters = "ABCDEFGHJKLMNOPQRST"

    def _start_katago(self):
        """Start KataGo GTP process."""
        command = [self.katago_path, "gtp"]
        if self.model_path:
            command += ["-model", self.model_path]
        if self.config_path:
            command += ["-config", self.config_path]

        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )

        self._send(f"boardsize {self.board_size}")
        self._send("clear_board")
        self._send(f"komi 6.5")
        self._send(f"kata-set-param maxVisits {self.visits}")

    def _send(self, command: str) -> str:
        """Send GTP command and return full response.

        GTP protocol: response starts with '=' (success) or '?' (error),
        followed by content lines, terminated by a blank line.
        """
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

        response_lines = []
        first_line = True
        while True:
            line = self.process.stdout.readline()
            if not line:  # EOF
                break
            line = line.rstrip('\n\r')
            if line.strip() == '' and not first_line:
                break
            if first_line:
                first_line = False
                if line.startswith("?"):
                    raise RuntimeError(f"KataGo error: {line}")
                if line.startswith("="):
                    content = line[1:].strip()
                    if content:
                        response_lines.append(content)
                    continue
            response_lines.append(line.strip())
        return "\n".join(response_lines)

    def _gtp_to_coord(self, gtp_move: str) -> Tuple[int, int]:
        gtp_move = gtp_move.strip().upper()
        if gtp_move in ("PASS", "RESIGN"):
            return (-1, -1)
        col = self._col_letters.index(gtp_move[0])
        row = self.board_size - int(gtp_move[1:])
        return (row, col)

    def board_to_features(self, board: np.ndarray, current_player: int = 1) -> list:
        """Convert board to 163 features (2 channels per cell + turn bit)."""
        features = []
        for cell in board.flatten():
            if cell == 1:      # Black
                features.extend([1.0, 0.0])
            elif cell == -1:   # White
                features.extend([0.0, 1.0])
            else:
                features.extend([0.0, 0.0])
        # 163rd feature: turn bit (1.0 = Black to play, 0.0 = White to play)
        features.append(1.0 if current_player == 1 else 0.0)
        return features

    def color_flip_features(self, features: list) -> list:
        """Color-flip augmentation: swap black/white channels + flip turn bit."""
        flipped = []
        # Swap the 81 channel pairs (first 162 elements)
        for feature_index in range(0, 162, 2):
            flipped.extend([
                features[feature_index + 1],
                features[feature_index]
            ])
        # Flip the 163rd turn bit
        flipped.append(1.0 - features[162])
        return flipped

    def get_game_phase(self, move_num: int, total_moves: int) -> str:
        """Classify move into game phase."""
        ratio = move_num / max(total_moves, 1)
        if ratio < 0.25:
            return "opening"
        elif ratio < 0.6:
            return "midgame"
        else:
            return "endgame"

    def discretize_outcome(self, win_prob: float) -> float:
        """Convert continuous KataGo win probability to discrete label."""
        if win_prob < 0.35:
            return 0.0   # White wins
        elif win_prob > 0.65:
            return 1.0   # Black wins
        else:
            return 0.5   # Draw

    def raw_outcome(self, win_prob: float) -> float:
        """Return raw win probability (no discretization)."""
        return float(np.clip(win_prob, 0.0, 1.0))

    def play_game(self) -> list:
        """Play one self-play game, return list of (features, outcome, phase)."""
        self._send("clear_board")
        board = np.zeros((self.board_size, self.board_size), dtype=int)
        positions = []
        move_num = 0
        current_player = 1  # Black first
        consecutive_passes = 0

        while True:
            # Get KataGo's move
            color = "black" if current_player == 1 else "white"
            try:
                response = self._send(f"genmove {color}")
            except RuntimeError:
                break

            gtp_move = response.strip().split()[0] if response.strip() else "PASS"
            gtp_move = gtp_move.upper()

            if gtp_move in ("PASS", "RESIGN"):
                consecutive_passes += 1
                if consecutive_passes >= 2 or gtp_move == "RESIGN":
                    break
                current_player = -current_player
                move_num += 1
                continue

            consecutive_passes = 0
            row, col = self._gtp_to_coord(gtp_move)

            if 0 <= row < self.board_size and 0 <= col < self.board_size:
                board[row, col] = current_player

            # Get KataGo's win probability for current position
            try:
                analysis = self._send("kata-raw-nn 0")
                win_prob = 0.5  # Default
                for line in analysis.split("\n"):
                    if line.startswith("whiteWin "):
                        win_prob = 1.0 - float(line.split()[1])  # Convert to Black win prob
                        break
            except (RuntimeError, ValueError, IndexError):
                win_prob = 0.5

            # Record position with raw win probability
            features = self.board_to_features(board, current_player)
            outcome = self.raw_outcome(win_prob)
            phase = self.get_game_phase(move_num, 81)  # 81 = 9x9 max moves
            positions.append((features, outcome, phase))

            current_player = -current_player
            move_num += 1

            if move_num > 2 * self.board_size * self.board_size:
                break

        return positions

    def generate(self, target_positions: int = 200000,
                 output_path: str = "training_data.json"):
        """
        Generate training dataset with color-flip augmentation.

        Each position is included twice: original + color-flipped.
        """
        print(f"Generating {target_positions:,} positions from KataGo self-play")
        print(f"  Board: {self.board_size}x{self.board_size}")
        print(f"  Visits: {self.visits}")
        print(f"  Output: {output_path}")

        self._start_katago()

        all_features = []
        all_outcomes = []
        phase_counts = {"opening": 0, "midgame": 0, "endgame": 0}
        game_count = 0

        # Each game position yields two samples after color flipping.
        raw_target = target_positions // 2

        try:
            while len(all_features) < target_positions:
                game_positions = self.play_game()
                game_count += 1

                for features, outcome, phase in game_positions:
                    if len(all_features) >= target_positions:
                        break

                    # Original position
                    all_features.append(features)
                    all_outcomes.append(outcome)
                    phase_counts[phase] += 1

                    # Color-flipped augmentation
                    flipped_features = self.color_flip_features(features)
                    flipped_outcome = 1.0 - outcome  # Invert label
                    all_features.append(flipped_features)
                    all_outcomes.append(flipped_outcome)
                    phase_counts[phase] += 1

                if game_count % 50 == 0:
                    print(f"  Games: {game_count}, Positions: {len(all_features):,}/{target_positions:,}")

        finally:
            try:
                self._send("quit")
                self.process.terminate()
            except Exception:
                pass

        # Truncate to exact target
        all_features = all_features[:target_positions]
        all_outcomes = all_outcomes[:target_positions]

        # Compute statistics
        outcomes_array = np.array(all_outcomes)
        stats = {
            "total_positions": len(all_features),
            "total_games": game_count,
            "white_wins": int(np.sum(outcomes_array == 0.0)),
            "draws": int(np.sum(outcomes_array == 0.5)),
            "black_wins": int(np.sum(outcomes_array == 1.0)),
            "phase_distribution": phase_counts,
        }

        # Save dataset
        dataset = {
            "positions": all_features,
            "game_outcomes": all_outcomes,
            "metadata": {
                "board_size": self.board_size,
                "feature_size": self.board_size * self.board_size * 2 + 1,
                "visits_per_move": self.visits,
                "color_flip_augmentation": True,
                "generation_date": datetime.now().isoformat(),
                "statistics": stats,
            }
        }

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w') as output_handle:
            json.dump(dataset, output_handle)

        print(f"\nGeneration complete!")
        print(f"  Total positions: {len(all_features):,}")
        print(f"  Games played: {game_count}")
        print(f"  White wins: {stats['white_wins']:,} ({stats['white_wins']/len(all_features):.1%})")
        print(f"  Draws: {stats['draws']:,} ({stats['draws']/len(all_features):.1%})")
        print(f"  Black wins: {stats['black_wins']:,} ({stats['black_wins']/len(all_features):.1%})")
        print(f"  Saved to: {output_path}")

        return stats


def _worker(worker_id, target_positions, katago_path, model_path, config_path,
            visits, board_size, result_queue):
    """Worker process: generate positions and put them on the queue."""
    generator = KataGoDataGenerator(
        board_size=board_size,
        katago_path=katago_path,
        model_path=model_path,
        config_path=config_path,
        visits=visits,
    )
    generator._start_katago()
    all_features = []
    all_outcomes = []
    game_count = 0
    try:
        while len(all_features) < target_positions:
            game_positions = generator.play_game()
            game_count += 1
            for features, outcome, phase in game_positions:
                if len(all_features) >= target_positions:
                    break
                all_features.append(features)
                all_outcomes.append(outcome)
                flipped_features = generator.color_flip_features(features)
                all_features.append(flipped_features)
                all_outcomes.append(1.0 - outcome)
            if game_count % 20 == 0:
                print(f"  Worker {worker_id}: {game_count} games, {len(all_features):,} positions",
                      flush=True)
    finally:
        try:
            generator._send("quit")
            generator.process.terminate()
        except Exception:
            pass
    result_queue.put((all_features[:target_positions], all_outcomes[:target_positions], game_count))


def generate_parallel(target_positions, output_path, katago_path, model_path,
                      config_path, visits, board_size, num_workers):
    """Generate training data using multiple parallel KataGo workers."""
    per_worker = (target_positions + num_workers - 1) // num_workers
    print(f"Generating {target_positions:,} positions with {num_workers} workers "
          f"({per_worker:,} each)", flush=True)

    result_queue = Queue()
    workers = []
    for worker_id in range(num_workers):
        worker = Process(target=_worker, args=(
            worker_id, per_worker, katago_path, model_path, config_path,
            visits, board_size, result_queue))
        worker.start()
        workers.append(worker)

    # Collect results
    all_features = []
    all_outcomes = []
    total_games = 0
    for _ in range(num_workers):
        worker_features, worker_outcomes, worker_games = result_queue.get()
        all_features.extend(worker_features)
        all_outcomes.extend(worker_outcomes)
        total_games += worker_games

    for worker in workers:
        worker.join()

    # Truncate
    all_features = all_features[:target_positions]
    all_outcomes = all_outcomes[:target_positions]

    outcomes_array = np.array(all_outcomes)
    stats = {
        "total_positions": len(all_features),
        "total_games": total_games,
        "white_wins": int(np.sum(outcomes_array == 0.0)),
        "draws": int(np.sum(outcomes_array == 0.5)),
        "black_wins": int(np.sum(outcomes_array == 1.0)),
    }

    dataset = {
        "positions": all_features,
        "game_outcomes": all_outcomes,
        "metadata": {
            "board_size": board_size,
            "feature_size": board_size * board_size * 2,
            "visits_per_move": visits,
            "color_flip_augmentation": True,
            "generation_date": datetime.now().isoformat(),
            "statistics": stats,
        }
    }

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w') as output_handle:
        json.dump(dataset, output_handle)

    print(f"\nGeneration complete!", flush=True)
    print(f"  Total positions: {len(all_features):,}")
    print(f"  Games played: {total_games}")
    print(f"  White wins: {stats['white_wins']:,} ({stats['white_wins']/len(all_features):.1%})")
    print(f"  Draws: {stats['draws']:,} ({stats['draws']/len(all_features):.1%})")
    print(f"  Black wins: {stats['black_wins']:,} ({stats['black_wins']/len(all_features):.1%})")
    print(f"  Saved to: {output_path}")
    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate KataGo training data")
    parser.add_argument('--positions', type=int, default=200000)
    parser.add_argument('--output', type=str, default='training_data.json')
    parser.add_argument('--katago', type=str, default='katago')
    parser.add_argument('--model', type=str, default=None)
    parser.add_argument('--config', type=str, default=None)
    parser.add_argument('--visits', type=int, default=50)
    parser.add_argument('--board-size', type=int, default=9)
    parser.add_argument('--workers', type=int, default=1,
                        help='Number of parallel KataGo workers')
    args = parser.parse_args()

    if args.workers > 1:
        generate_parallel(
            target_positions=args.positions,
            output_path=args.output,
            katago_path=args.katago,
            model_path=args.model,
            config_path=args.config,
            visits=args.visits,
            board_size=args.board_size,
            num_workers=args.workers,
        )
    else:
        generator = KataGoDataGenerator(
            board_size=args.board_size,
            katago_path=args.katago,
            model_path=args.model,
            config_path=args.config,
            visits=args.visits,
        )
        generator.generate(
            target_positions=args.positions,
            output_path=args.output
        )


if __name__ == "__main__":
    main()
