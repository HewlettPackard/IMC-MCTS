#!/bin/bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

#===============================================================================
# KATAGO TRAINING DATA GENERATION SCRIPT
#===============================================================================
#
# Optional external-engine helper. This script generates Go training data using
# KataGo on a local machine. It clones/builds external code, downloads external
# model weights, and writes generated data under local output directories.
# These outputs are outside the default source release and SBOM scope. Review
# generated data separately before distributing it.
#
# USAGE:
#   1. Clone the repo on the machine that will generate data:
#      git clone https://github.com/HewlettPackard/IMC-MCTS.git
#      cd IMC-MCTS
#
#   2. Run this script:
#      chmod +x tournament/go_compiled/scripts/generate_katago_training_data.sh
#      ./tournament/go_compiled/scripts/generate_katago_training_data.sh
#
#   3. The script will:
#      - Build KataGo with CUDA
#      - Download neural network weights
#      - Generate 100k training positions
#
# REQUIREMENTS:
#   - NVIDIA GPU with CUDA
#   - CUDA toolkit installed
#   - cmake, git, wget
#   - ~2GB disk space
#
# ESTIMATED TIME: hardware-dependent
#===============================================================================

set -e  # Exit on error

echo "========================================"
echo "KATAGO TRAINING DATA GENERATOR"
echo "========================================"
echo ""

# Configuration
BOARD_SIZE=9
NUM_POSITIONS=100000
PLAYOUTS=200
OUTPUT_DIR="tournament/go_compiled/data/katago_training_data"
KATAGO_DIR="tournament/go_compiled/tools/katago_bin"

#-------------------------------------------------------------------------------
# STEP 1: Check prerequisites
#-------------------------------------------------------------------------------
echo "[1/6] Checking prerequisites..."

# Check for CUDA
if ! command -v nvcc &> /dev/null; then
    echo "ERROR: CUDA not found. Please install CUDA toolkit."
    echo "On Ubuntu: sudo apt install nvidia-cuda-toolkit"
    exit 1
fi

# Check for cmake
if ! command -v cmake &> /dev/null; then
    echo "ERROR: cmake not found. Please install cmake."
    exit 1
fi

# Check GPU
echo "Checking GPU..."
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || {
    echo "ERROR: No NVIDIA GPU detected"
    exit 1
}

echo "Prerequisites OK!"
echo ""

# Install tqdm for progress bars
pip install tqdm --quiet

#-------------------------------------------------------------------------------
# STEP 2: Clone/Build KataGo with CUDA
#-------------------------------------------------------------------------------
echo "[2/6] Building KataGo with CUDA backend..."

mkdir -p "$KATAGO_DIR"
cd "$KATAGO_DIR"

# Clone KataGo if not present
if [ ! -d "KataGo" ]; then
    echo "Cloning KataGo..."
    git clone https://github.com/lightvector/KataGo.git
fi

cd KataGo/cpp

# Clean previous build
rm -rf build
mkdir build
cd build

# Build with CUDA
echo "Running cmake with CUDA backend..."
cmake .. -DUSE_BACKEND=CUDA -DCMAKE_BUILD_TYPE=Release

echo "Building KataGo (this may take a few minutes)..."
make -j$(nproc)

# Verify build
./katago version
echo ""

# Go back to repo root
cd ../../../../../

#-------------------------------------------------------------------------------
# STEP 3: Download neural network weights
#-------------------------------------------------------------------------------
echo "[3/6] Downloading KataGo neural network..."

WEIGHTS_FILE="$KATAGO_DIR/kata1-b18c384nbt-s9996604416-d4316597426.bin.gz"

if [ ! -f "$WEIGHTS_FILE" ]; then
    echo "Downloading weights (~400MB)..."
    wget -O "$WEIGHTS_FILE" \
        "https://media.katagotraining.org/uploaded/networks/models/kata1/kata1-b18c384nbt-s9996604416-d4316597426.bin.gz"
else
    echo "Weights already downloaded."
fi

echo ""

#-------------------------------------------------------------------------------
# STEP 4: Create GTP config for data generation
#-------------------------------------------------------------------------------
echo "[4/6] Creating KataGo config..."

cat > "$KATAGO_DIR/datagen_config.cfg" << 'EOF'
# KataGo config for training data generation
logSearchInfo = false
logToStderr = false
maxVisits = 200
numSearchThreads = 8
nnCacheSizePowerOfTwo = 23
nnMutexPoolSizePowerOfTwo = 17
EOF

echo "Config created."
echo ""

#-------------------------------------------------------------------------------
# STEP 5: Generate training data
#-------------------------------------------------------------------------------
echo "[5/6] Generating training data..."
echo "  Board size: ${BOARD_SIZE}x${BOARD_SIZE}"
echo "  Positions: ${NUM_POSITIONS}"
echo "  Playouts per move: ${PLAYOUTS}"
echo ""

mkdir -p "$OUTPUT_DIR"

# Create data generation Python script
cat > "$OUTPUT_DIR/generate_data.py" << 'PYTHON_EOF'
#!/usr/bin/env python3
"""
Generate RICH training data using KataGo GPU.

Captures for each position:
- Board state (who is where)
- Win probability (KataGo evaluation)
- Game phase (opening/midgame/endgame)
- Move number
- Best move (what KataGo played)
- Stone counts
- Game ID (for tracking)
"""
import subprocess
import json
import numpy as np
import os
import sys
import time
from datetime import datetime
from tqdm import tqdm

class KataGoDataGenerator:
    def __init__(self, board_size=9, katago_path=None, model_path=None, config_path=None, playouts=200):
        self.board_size = board_size
        self.playouts = playouts
        self.max_moves = board_size * board_size

        script_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.join(script_dir, "..", "..", "tournament", "katago_bin")

        self.katago_path = katago_path or os.path.join(base_dir, "KataGo", "cpp", "build", "katago")
        self.model_path = model_path or os.path.join(base_dir, "kata1-b18c384nbt-s9996604416-d4316597426.bin.gz")
        self.config_path = config_path or os.path.join(base_dir, "datagen_config.cfg")

        self.process = None

    def start_engine(self):
        cmd = [self.katago_path, "gtp", "-model", self.model_path, "-config", self.config_path]
        self.process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self._send_command(f"boardsize {self.board_size}")
        self._send_command("clear_board")
        self._send_command(f"kata-set-param maxVisits {self.playouts}")

    def _send_command(self, cmd):
        self.process.stdin.write(cmd + "\n")
        self.process.stdin.flush()
        response = []
        while True:
            line = self.process.stdout.readline().strip()
            if not line:
                break
            if line.startswith("="):
                content = line[1:].strip()
                if content:
                    response.append(content)
        return " ".join(response)

    def get_position_evaluation(self):
        """Get KataGo's evaluation of current position."""
        response = self._send_command("kata-raw-nn 0")
        # Parse whiteWin value
        for line in response.split():
            if "whiteWin" in line:
                try:
                    return float(line.split(":")[1])
                except:
                    pass
        return 0.5

    def get_game_phase(self, move_num, total_stones):
        """Determine game phase based on move number and board fill."""
        fill_ratio = total_stones / self.max_moves

        if move_num <= 15 or fill_ratio < 0.15:
            return "opening"
        elif move_num >= 50 or fill_ratio > 0.60:
            return "endgame"
        else:
            return "midgame"

    def generate_game_positions(self, game_id):
        """Play a game and collect positions with RICH metadata."""
        self._send_command("clear_board")
        positions = []
        board = np.zeros((self.board_size, self.board_size), dtype=int)
        current_player = 1  # Black = 1, White = -1
        game_winner = None  # Track who wins

        move_history = []

        for move_num in range(self.max_moves):
            # Count stones
            black_stones = int(np.sum(board == 1))
            white_stones = int(np.sum(board == -1))
            total_stones = black_stones + white_stones

            # Get KataGo's evaluation BEFORE the move
            eval_score = self.get_position_evaluation()

            # Determine game phase
            game_phase = self.get_game_phase(move_num, total_stones)

            # Generate KataGo's move
            color = "black" if current_player == 1 else "white"
            move_response = self._send_command(f"genmove {color}")

            if move_response.upper() in ["PASS", "RESIGN", ""]:
                if move_response.upper() == "RESIGN":
                    game_winner = -current_player  # Opponent wins
                break

            # Parse move
            try:
                col = "ABCDEFGHJKLMNOPQRST".index(move_response[0].upper())
                row = self.board_size - int(move_response[1:])
                move_coord = (row, col)
            except:
                break

            # Create feature vector (board state)
            feature_vec = []
            for cell in board.flatten():
                if cell == 1:
                    feature_vec.extend([1.0, 0.0])
                elif cell == -1:
                    feature_vec.extend([0.0, 1.0])
                else:
                    feature_vec.extend([0.0, 0.0])

            # Win probability from Black's perspective
            black_win_prob = 1.0 - eval_score

            # Convert to discrete outcome for training compatibility
            # 0.0 = White wins, 0.5 = Draw, 1.0 = Black wins
            if black_win_prob < 0.35:
                discrete_outcome = 0.0   # White wins
            elif black_win_prob > 0.65:
                discrete_outcome = 1.0   # Black wins
            else:
                discrete_outcome = 0.5   # Draw

            # Store RICH position data
            position_data = {
                "features": feature_vec,
                "win_prob": black_win_prob,           # Original continuous value
                "discrete_outcome": discrete_outcome,  # For training compatibility
                "game_phase": game_phase,
                "move_num": move_num,
                "move_played": list(move_coord),  # What KataGo played
                "move_gtp": move_response,
                "to_play": "black" if current_player == 1 else "white",
                "black_stones": black_stones,
                "white_stones": white_stones,
                "game_id": game_id
            }
            positions.append(position_data)
            move_history.append(move_response)

            # Update board
            board[row, col] = current_player
            current_player = -current_player

        # Determine winner if not already set
        if game_winner is None:
            final_eval = self.get_position_evaluation()
            game_winner = 1 if final_eval < 0.5 else -1

        # Add final game outcome to all positions
        for pos in positions:
            pos["game_winner"] = "black" if game_winner == 1 else "white"
            pos["game_length"] = len(move_history)

        return positions, move_history

    def generate_dataset(self, num_positions, output_file):
        """Generate full dataset with rich metadata."""
        self.start_engine()

        all_positions = []
        games_data = []

        games_played = 0
        start_time = time.time()

        print(f"Generating {num_positions} positions with rich metadata...")
        print(f"Data includes: board state, win prob, game phase, move played, etc.")
        print()

        # Progress bar
        pbar = tqdm(total=num_positions, desc="Positions", unit="pos",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")

        while len(all_positions) < num_positions:
            games_played += 1
            positions, moves = self.generate_game_positions(game_id=games_played)

            prev_len = len(all_positions)
            all_positions.extend(positions)
            games_data.append({
                "game_id": games_played,
                "num_moves": len(moves),
                "moves": moves
            })

            # Update progress bar
            new_positions = len(all_positions) - prev_len
            pbar.update(min(new_positions, num_positions - prev_len))

            # Update description with game count and phase info
            if games_played % 5 == 0:
                phases = {"opening": 0, "midgame": 0, "endgame": 0}
                for p in all_positions[-500:]:  # Last 500 for efficiency
                    phases[p["game_phase"]] += 1
                pbar.set_postfix({"games": games_played, "O": phases["opening"], "M": phases["midgame"], "E": phases["endgame"]})

        pbar.close()

        # Trim to exact size
        all_positions = all_positions[:num_positions]

        # Extract simple arrays for training (backward compatible)
        simple_features = [p["features"] for p in all_positions]
        simple_outcomes = [p["discrete_outcome"] for p in all_positions]  # Use discrete for training!

        # Count final stats
        phases = {"opening": 0, "midgame": 0, "endgame": 0}
        outcomes_dist = {0.0: 0, 0.5: 0, 1.0: 0}
        for p in all_positions:
            phases[p["game_phase"]] += 1
            outcomes_dist[p["discrete_outcome"]] += 1

        # Save dataset
        dataset = {
            # Simple format (for existing training code)
            "positions": simple_features,
            "game_outcomes": simple_outcomes,

            # Rich format (full metadata)
            "rich_positions": all_positions,

            # Game records
            "games": games_data,

            # Metadata
            "metadata": {
                "dataset_type": "katago_rich_evaluation",
                "board_size": self.board_size,
                "num_positions": len(all_positions),
                "num_games": games_played,
                "playouts_per_move": self.playouts,
                "generation_date": datetime.now().isoformat(),
        "source": "KataGo self-play",
                "phase_distribution": phases,
                "outcome_distribution": {
                    "white_wins": outcomes_dist[0.0],
                    "draws": outcomes_dist[0.5],
                    "black_wins": outcomes_dist[1.0]
                },
                "label_format": "game_outcomes: 0.0=White wins, 0.5=Draw, 1.0=Black wins",
                "description": "Rich Go position data: board state + discrete outcome + game phase + move played"
            }
        }

        with open(output_file, 'w') as f:
            json.dump(dataset, f)

        print(f"\n{'='*60}")
        print(f"DATASET GENERATED!")
        print(f"{'='*60}")
        print(f"  Positions: {len(all_positions)}")
        print(f"  Games: {games_played}")
        print(f"  Time: {(time.time()-start_time)/60:.1f} minutes")
        print(f"  File: {output_file}")
        print(f"\n  Phase Distribution:")
        print(f"    Opening:  {phases['opening']:6d} ({100*phases['opening']/len(all_positions):.1f}%)")
        print(f"    Midgame:  {phases['midgame']:6d} ({100*phases['midgame']/len(all_positions):.1f}%)")
        print(f"    Endgame:  {phases['endgame']:6d} ({100*phases['endgame']/len(all_positions):.1f}%)")
        print(f"\n  Data includes:")
        print(f"    - Board state (feature vector)")
        print(f"    - Win probability (KataGo evaluation)")
        print(f"    - Game phase (opening/midgame/endgame)")
        print(f"    - Move played by KataGo")
        print(f"    - Stone counts, game ID, etc.")
        print(f"{'='*60}")

        self.process.terminate()
        return dataset

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--board_size", type=int, default=9)
    parser.add_argument("--num_positions", type=int, default=100000)
    parser.add_argument("--playouts", type=int, default=200)
    parser.add_argument("--output", type=str, default="katago_training_data_9x9.json")
    args = parser.parse_args()

    generator = KataGoDataGenerator(
        board_size=args.board_size,
        playouts=args.playouts
    )
    generator.generate_dataset(args.num_positions, args.output)
PYTHON_EOF

# Run the data generation
echo "Starting data generation. Runtime depends on local hardware..."
python3 "$OUTPUT_DIR/generate_data.py" \
    --board_size $BOARD_SIZE \
    --num_positions $NUM_POSITIONS \
    --playouts $PLAYOUTS \
    --output "$OUTPUT_DIR/katago_training_data_${BOARD_SIZE}x${BOARD_SIZE}.json"

echo ""

#-------------------------------------------------------------------------------
# STEP 6: Report generated files
#-------------------------------------------------------------------------------
echo "[6/6] Generated local training data."

echo ""
echo "========================================"
echo "DONE!"
echo "========================================"
echo ""
echo "File: $OUTPUT_DIR/katago_training_data_${BOARD_SIZE}x${BOARD_SIZE}.json"
echo ""
echo "NEXT STEPS:"
echo "  1. Review generated data before distribution."
echo "  2. Retrain the NN using the reviewed data."
echo ""
