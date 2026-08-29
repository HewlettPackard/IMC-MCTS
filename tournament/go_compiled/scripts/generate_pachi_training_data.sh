#!/bin/bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

#===============================================================================
# Optional external-engine helper. Generates Pachi training data locally.
# Generated data is outside the default source release and SBOM scope.
#===============================================================================

set -e

NUM_POSITIONS=${1:-100000}

echo "============================================================"
echo "  PACHI TRAINING DATA GENERATOR (CPU-only)"
echo "============================================================"
echo "  Positions to generate: $NUM_POSITIONS"
echo "============================================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PACHI_BIN="$SCRIPT_DIR/../tournament/pachi/pachi"

if [ ! -f "$PACHI_BIN" ]; then
    echo "ERROR: Pachi not found at $PACHI_BIN"
    exit 1
fi

OUTPUT_DIR="$PROJECT_DIR/pachi_training_data"
mkdir -p "$OUTPUT_DIR"

pip install tqdm --quiet 2>/dev/null || true

cat > "$OUTPUT_DIR/generate_data.py" << 'PYTHON_EOF'
#!/usr/bin/env python3
"""Pachi training data generator."""
import subprocess
import json
import numpy as np
import os
import sys
import time
import argparse
from datetime import datetime

try:
    from tqdm import tqdm
except ImportError:
    class tqdm:
        def __init__(self, total=None, **kwargs):
            self.total = total
            self.n = 0
        def update(self, n=1):
            self.n += n
            pct = 100*self.n/self.total if self.total else 0
            print(f"\rProgress: {self.n}/{self.total} ({pct:.1f}%)", end="", flush=True)
        def set_postfix(self, d):
            pass
        def close(self):
            print()


class PachiGame:
    def __init__(self, pachi_path, board_size=9):
        self.pachi_path = pachi_path
        self.board_size = board_size
        self.process = None

    def start(self):
        cmd = [self.pachi_path, "threads=1", "max_tree_size=128"]
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
            bufsize=1
        )
        self._cmd(f"boardsize {self.board_size}")
        self._cmd("clear_board")
        self._cmd("komi 5.5")  # Standard komi for fair play
        self._cmd("time_settings 0 1 1")

    def _cmd(self, command):
        """Send GTP command and get response."""
        if not self.process:
            return ""
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

        result = ""
        while True:
            line = self.process.stdout.readline()
            if line == "\n" or line == "":
                break
            if line.startswith("="):
                result = line[1:].strip()
            elif line.startswith("?"):
                break
        return result

    def play_game(self, game_id):
        self._cmd("clear_board")
        positions = []
        board = np.zeros((self.board_size, self.board_size), dtype=int)
        player = 1  # 1=black, -1=white
        passes = 0
        winner = None  # Track winner from resign

        for move_num in range(self.board_size * self.board_size):
            color = "black" if player == 1 else "white"
            response = self._cmd(f"genmove {color}")

            if not response:
                break

            move = response.split()[0] if response else "PASS"

            if move.upper() == "PASS":
                passes += 1
                if passes >= 2:
                    break
                player = -player
                continue
            elif move.upper() == "RESIGN":
                # Current player resigns, opponent wins
                winner = -player  # Opponent wins
                break
            else:
                passes = 0

            try:
                col = "ABCDEFGHJKLMNOPQRST".index(move[0].upper())
                row = self.board_size - int(move[1:])
            except:
                break

            # Save position BEFORE updating board
            features = []
            for cell in board.flatten():
                if cell == 1:
                    features.extend([1.0, 0.0])
                elif cell == -1:
                    features.extend([0.0, 1.0])
                else:
                    features.extend([0.0, 0.0])

            if move_num < 15:
                phase = "opening"
            elif move_num > 50:
                phase = "endgame"
            else:
                phase = "midgame"

            positions.append({
                "features": features,
                "phase": phase,
                "move_num": move_num,
                "game_id": game_id
            })

            board[row, col] = player
            player = -player

        # Get final score if no resign
        if winner is None:
            score = self._cmd("final_score")
            if score.startswith("B"):
                winner = 1  # Black wins
            elif score.startswith("W"):
                winner = -1  # White wins
            else:
                winner = 0  # Draw

        # Assign outcomes based on winner
        for i, pos in enumerate(positions):
            progress = (i + 1) / max(len(positions), 1)
            if winner == 1:  # Black wins
                pos["discrete_outcome"] = 1.0 if progress > 0.3 else 0.5
            elif winner == -1:  # White wins
                pos["discrete_outcome"] = 0.0 if progress > 0.3 else 0.5
            else:
                pos["discrete_outcome"] = 0.5

        return positions, winner

    def close(self):
        if self.process:
            try:
                self._cmd("quit")
                self.process.terminate()
            except:
                pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--positions", type=int, default=100000)
    parser.add_argument("--board-size", type=int, default=9)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--pachi-path", type=str, required=True)
    args = parser.parse_args()

    if args.output is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        args.output = os.path.join(script_dir, f"positions_{args.positions//1000}k_9x9.json")

    print(f"Generating {args.positions} positions...")
    print(f"~1 sec/move, ~40 moves/game, ~40 positions/game")
    print(f"Estimated time: ~{args.positions / 40 / 60:.0f} minutes")
    print()

    game = PachiGame(args.pachi_path, args.board_size)
    game.start()

    all_positions = []
    games_played = 0
    wins = {"black": 0, "white": 0, "draw": 0}
    start_time = time.time()

    pbar = tqdm(total=args.positions, desc="Positions", unit="pos")

    while len(all_positions) < args.positions:
        games_played += 1
        positions, winner = game.play_game(games_played)

        if winner == 1:
            wins["black"] += 1
        elif winner == -1:
            wins["white"] += 1
        else:
            wins["draw"] += 1

        prev_len = len(all_positions)
        all_positions.extend(positions)
        new_pos = len(all_positions) - prev_len

        pbar.update(min(new_pos, args.positions - prev_len))

        if games_played % 5 == 0:
            elapsed = time.time() - start_time
            rate = len(all_positions) / elapsed if elapsed > 0 else 0
            pbar.set_postfix({
                "games": games_played,
                "pos/s": f"{rate:.1f}",
                "B": wins["black"],
                "W": wins["white"]
            })

    pbar.close()
    game.close()

    all_positions = all_positions[:args.positions]

    phases = {"opening": 0, "midgame": 0, "endgame": 0}
    outcomes = {0.0: 0, 0.5: 0, 1.0: 0}
    for p in all_positions:
        phases[p["phase"]] += 1
        outcomes[p["discrete_outcome"]] += 1

    dataset = {
        "positions": [p["features"] for p in all_positions],
        "game_outcomes": [p["discrete_outcome"] for p in all_positions],
        "metadata": {
            "dataset_type": "pachi_evaluation",
            "board_size": args.board_size,
            "num_positions": len(all_positions),
            "num_games": games_played,
            "source": "Pachi self-play (CPU)",
            "generation_date": datetime.now().isoformat(),
            "phase_distribution": phases,
            "outcome_distribution": {
                "white_wins": outcomes[0.0],
                "draws": outcomes[0.5],
                "black_wins": outcomes[1.0]
            }
        }
    }

    with open(args.output, 'w') as f:
        json.dump(dataset, f)

    elapsed = time.time() - start_time

    print(f"\n{'='*50}")
    print(f"DONE!")
    print(f"  Positions: {len(all_positions)}")
    print(f"  Games: {games_played}")
    print(f"  Time: {elapsed/60:.1f} min ({len(all_positions)/elapsed:.1f} pos/s)")
    print(f"  File: {args.output}")
    print(f"  Phases: O={phases['opening']} M={phases['midgame']} E={phases['endgame']}")
    print(f"  Outcomes: W={outcomes[0.0]} D={outcomes[0.5]} B={outcomes[1.0]}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
PYTHON_EOF

chmod +x "$OUTPUT_DIR/generate_data.py"

echo ""
echo "Starting generation..."
echo ""

python3 "$OUTPUT_DIR/generate_data.py" \
    --positions "$NUM_POSITIONS" \
    --pachi-path "$PACHI_BIN" \
    --output "$OUTPUT_DIR/positions_${NUM_POSITIONS}_9x9.json"

echo ""
echo "Done. Review generated data separately before distribution."
