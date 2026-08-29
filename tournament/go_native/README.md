# Crossbar Accuracy vs ELO Tournament

Tournament infrastructure for evaluating the relationship between crossbar neural network accuracy and MCTS playing strength (ELO rating).

## Overview

This tournament system compares different accuracy levels of the accelerator crossbar implementations.

### 4-Player Configuration (Default)
- **High Accuracy**: 81.95% (best_improved_model.pkl)
- **Medium-High Accuracy**: 75.35% (model_at_75.35percent.pkl)
- **Medium Accuracy**: 65.00% (model_at_65.00percent.pkl)
- **Low Accuracy**: 55.50% (model_at_55.50percent.pkl)

### 10-Player Configuration (Extended)
- **Player 1**: 81.95% (best_improved_model.pkl)
- **Player 2**: 78.00% (model_at_78.00percent.pkl)
- **Player 3**: 74.00% (model_at_74.00percent.pkl)
- **Player 4**: 70.05% (model_at_70.05percent.pkl)
- **Player 5**: 66.00% (model_at_66.00percent.pkl)
- **Player 6**: 62.10% (model_at_62.10percent.pkl)
- **Player 7**: 58.20% (model_at_58.20percent.pkl)
- **Player 8**: 54.35% (model_at_54.35percent.pkl)
- **Player 9**: 52.15% (model_at_52.15percent.pkl)
- **Player 10**: 50.20% (model_at_50.20percent.pkl)

## Components

### Core Modules

1. **heuristic_eval.py** - Position evaluation using training heuristic
   - Formula: `score = material + 0.5×territory + 0.1×liberties`
   - Same evaluation used in NN training for consistency

2. **mcts_player.py** - Standalone MCTS implementation
   - Simplified player without SST dependencies
   - Uses UCB1 for tree traversal
   - Supports different NN weight files

3. **game_controller.py** - Game orchestration
   - Manages full games between two players
   - Applies moves alternately
   - Evaluates final position with heuristic

4. **config_loader.py** - Configuration management
   - Loads 4 or 10 accuracy-level NN weights
   - Validates weight files exist
   - Provides AcceleratorConfig objects

5. **elo_calculator.py** - ELO rating system
   - Standard chess-style ELO (K=32)
   - Tracks rating evolution
   - Calculates rankings and statistics

### Tournament Runner

6. **tournament_runner.py** - Full tournament execution
   - Round-robin: 6 matchups × 50 games = 300 total
   - Parallel execution support
   - Progress tracking and checkpointing
   - Result export (JSON/CSV)

### Analysis

7. **analysis/plot_results.py** - Visualization
   - ELO vs accuracy curve
   - Win rate heatmap
   - Energy per ELO point
   - Score distribution

## Game Rules

**Simplified "Go" Rules** (matching training data):
- Legal moves: Any empty position (no captures, ko, or suicide checking)
- Game ends: When board is full
- Winner determined by heuristic:
  - `score = material_diff + 0.5×territory_diff + 0.1×liberty_diff`
  - score > 1.5 → Black wins
  - score < -1.5 → White wins
  - otherwise → Draw

**Territory**: 3×3 neighborhood heuristic (majority nearby stones)
**Liberties**: Individual stone liberties (NOT group liberties)

## Usage

### Test Components

```bash
# Test heuristic evaluator
python3 heuristic_eval.py

# Test configuration loader
python3 config_loader.py 9

# Test ELO calculator
python3 elo_calculator.py

# Test MCTS player
python3 mcts_player.py

# Test game controller
python3 game_controller.py
```

### Run Tournament

#### 4-Player Tournaments
```bash
# Quick validation (5 games per matchup, 30 total games)
python3 tournament_runner.py --games 5 --iterations 500 --players 4 --output tournament_results_quick

# Full tournament (50 games per matchup, 300 total games)
./run_full_tournament.sh

# Or manually:
python3 tournament_runner.py --games 50 --iterations 5000 --players 4
```

#### 10-Player Tournaments
```bash
# Quick validation (5 games per matchup, 225 total games)
python3 tournament_runner.py --games 5 --iterations 500 --players 10 --output tournament_results_10p_quick

# Full tournament (50 games per matchup, 2250 total games)
./run_full_tournament_10players.sh

# Or manually:
python3 tournament_runner.py --games 50 --iterations 5000 --players 10
```

### Analyze Results

```bash
# Generate plots
python3 analysis/plot_results.py tournament_results.json
```

## Parameters

### Default Settings (9×9 board)

- **Iterations per move**: 5000 (500 for quick tests)
- **Exploration constant**: 1.41 (√2)
- **Max moves per game**: 60 (early termination to preserve evaluation diversity)
- **Games per matchup**: 50 (5 for quick tests)
- **Total tournament games**:
  - 4 players: 6 matchups × 50 games = 300 games
  - 10 players: 45 matchups × 50 games = 2250 games

### Compute Time Estimates

**Per game** (9×9, 5000 iterations/move):
- Moves per game: ~40-50 (up to 60 max)
- Iterations: ~5000 × 45 = 225,000 total
- Time: ~5-15 minutes (CPU-dependent)

**Full tournaments**:
- **4 players** (300 games): ~25-75 hours (1-3 days)
- **10 players** (2250 games): ~200-600 hours (8-25 days)

**Quick validation**:
- **4 players** (30 games): ~30-60 minutes
- **10 players** (225 games): ~4-6 hours

## Output Files

### Tournament Results
- `tournament_results.json` - Complete game records
- `elo_ratings.json` - Final ELO ratings and rankings
- `game_records/` - Individual game records

### Analysis
- `plots/elo_vs_accuracy.png` - Main result figure
- `plots/winrate_matrix.png` - Head-to-head heatmap
- `plots/energy_efficiency.png` - Energy per ELO point
- `stats/tournament_stats.txt` - Statistical summary

## Expected Results

### Hypothesis
Higher crossbar accuracy → Better MCTS playing strength (ELO)

### Key Metrics
1. **ELO vs Accuracy**: Expect positive correlation
2. **Win Rates**: High accuracy should dominate low accuracy
3. **Energy Efficiency**: Trade-off between accuracy cost and ELO gain
4. **Score Diversity**: Heuristic prevents monotonic 13:12 outcomes

## Status

1. ✅ Core infrastructure complete
2. ✅ Tournament runner implemented
3. ✅ Validation tournament (30 games, 4 players)
4. ✅ Analysis plots and visualizations
5. ✅ 10-player configuration added
6. ⏳ Run full 4-player tournament (300 games)
7. ⏳ Run full 10-player tournament (2250 games)
8. ⏳ Review results

## Notes

- Uses exact same heuristic as NN training (material + 0.5×territory + 0.1×liberties)
- No real Go rules (captures, ko, etc.) - matches training data
- MCTS player is standalone (doesn't require full SST simulation)
- Can extend to other board sizes (5×5, 13×13) if needed
