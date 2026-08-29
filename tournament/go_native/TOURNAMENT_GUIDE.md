# Tournament Execution Guide

Complete guide for running the Crossbar Accuracy vs ELO tournament study.

## 🎯 Quick Start

### Option 1: Quick Validation Test (30 games, ~30-60 minutes)
```bash
cd tournament/go_native
python3 tournament_runner.py --games 5 --iterations 500 --players 4 --output tournament_results_quick
```

### Option 2: Full Tournament (300 games, ~25-75 hours)
```bash
cd tournament/go_native
./run_full_tournament.sh
```

### Option 3: Custom Configuration
```bash
python3 tournament_runner.py --games 10 --iterations 1000 --output my_results
```

## 📊 Tournament Configurations

### 4 Accuracy Levels (9×9 Board)
1. **High Accuracy**: 81.95% - `best_improved_model.pkl`
2. **Medium-High**: 75.35% - `model_at_75.35percent.pkl`
3. **Medium**: 65.00% - `model_at_65.00percent.pkl`
4. **Low**: 55.50% - `model_at_55.50percent.pkl`

### Matchups (Round-Robin)
- High vs Medium-High
- High vs Medium
- High vs Low
- Medium-High vs Medium
- Medium-High vs Low
- Medium vs Low

**Total: 6 matchups**

## ⚙️ Parameters

### Quick Test
- Games per matchup: 5
- Iterations per move: 500
- Max moves: 60
- **Total: 30 games**
- **Time: ~30-60 minutes**

### Full Tournament
- Games per matchup: 50
- Iterations per move: 5000
- Max moves: 60
- **Total: 300 games**
- **Time: ~25-75 hours**

### Computation Estimates (per game)
- Moves per game: ~60 (early termination)
- MCTS iterations: 60 × 5000 = 300,000 per game
- Time: ~5-15 minutes per game (CPU-dependent)

## 📁 Output Files

After running, results are saved to the output directory (default: `tournament_results/`):

### Main Results
- `tournament_results.json` - Complete tournament data
  - All game records
  - ELO ratings
  - Matchup statistics
  - Configuration info

- `elo_ratings.json` - Final ELO rankings
  - Player ratings
  - Win/loss/draw records
  - Rating evolution history

### Checkpoints
- `checkpoint_25_games.json`
- `checkpoint_50_games.json`
- `checkpoint_75_games.json`
- ... (every 25 games)

These allow resuming if interrupted!

## 🔄 Monitoring Progress

The tournament runner prints progress updates:
- Every 10 games: Progress percentage, ETA, current rankings
- Every 25 games: Checkpoint saved
- After each matchup: Summary statistics

### Example Output
```
--- Progress: 50/300 games (16.7%) ---
    Elapsed: 1.25h
    ETA: 6.23h

    Current ELO Rankings:
      1. High Accuracy              Rating: 1584.2 (W/L/D: 15/3/2)
      2. Medium-High Accuracy       Rating: 1512.5 (W/L/D: 12/6/2)
      3. Medium Accuracy            Rating: 1475.8 (W/L/D: 8/10/2)
      4. Low Accuracy               Rating: 1427.5 (W/L/D: 5/13/2)
```

## 🛑 Interrupting & Resuming

### To Interrupt
Press `Ctrl+C` - progress will be saved to checkpoint

### Current Limitation
⚠️ **Resume not yet implemented** - tournament starts from beginning if interrupted

**Workaround**: Run quick tests first to validate, then run full tournament in a persistent session (tmux/screen)

## 🔬 Expected Results

### Hypothesis
Higher crossbar accuracy → Higher ELO rating

### Key Metrics to Observe
1. **ELO Rankings**
   - High Accuracy should rank #1
   - Clear separation between accuracy tiers

2. **Win Rates**
   - High vs Low: ~80-90% win rate expected
   - Adjacent tiers: ~60-70% win rate

3. **Score Breakdown**
   - Territory control differences
   - Liberty advantage patterns
   - Material differences

## 🚀 Recommendations

### For Quick Validation
```bash
python3 tournament_runner.py --games 5 --iterations 500 --players 4 --output tournament_results_quick
```
- Verify system works correctly
- Check for any bugs
- Estimate full tournament time
- Validate ELO trends

### For Full Tournament
1. **Use tmux or screen**:
   ```bash
   tmux new -s tournament
   cd tournament/go_native
   ./run_full_tournament.sh
   # Detach: Ctrl+B, then D
   # Reattach: tmux attach -t tournament
   ```

2. **Monitor resources**:
   ```bash
   htop  # CPU usage
   watch -n 60 'tail -20 tournament_log_*.txt'  # Progress
   ```

3. **Estimate completion**:
   - Check progress updates every few hours
   - ETA is calculated based on average game time

## 📈 Next Steps After Tournament

1. **Verify Results**:
   ```bash
   python3 -m json.tool tournament_results/tournament_results.json | less
   ```

2. **Generate Plots**:
   ```bash
   python3 analysis/plot_results.py tournament_results/tournament_results.json
   ```

## 🐛 Troubleshooting

### Problem: Games all end in draws
**Solution**: Verify early termination is enabled (max_moves=60)

### Problem: Tournament too slow
**Solutions**:
- Reduce iterations: `--iterations 1000`
- Reduce games: `--games 10`
- Use quick test first

### Problem: Out of memory
**Solution**: MCTS trees should clear between moves - check system RAM

### Problem: Want to stop and resume
**Solution**:
- Let current game finish (don't kill -9)
- Check latest checkpoint file
- Resume support is not part of the source-only release; re-run from the start if needed.

## 📝 Game Rules Reminder

**Simplified "Go" (matching training data)**:
- Legal moves: Any empty position
- No captures, no ko rule, no suicide checking
- Game ends: After 60 moves (early termination)
- Evaluation: `score = material + 0.5×territory + 0.1×liberties`
  - score > 1.5 → Black wins
  - score < -1.5 → White wins
  - otherwise → Draw

**Why these rules?**
- Exact same evaluation as NN training
- Ensures consistency between training and tournament
- Territory/liberties matter (not just stone count)

## Analysis and Reporting

### Key Figures
1. ELO vs Crossbar Accuracy (scatter plot with trend line)
2. Win Rate Matrix (4×4 heatmap)
3. Energy per ELO Point (if energy data available)
4. Score Component Analysis (material vs territory vs liberties)

### Key Statistics
- ELO rating difference per 10% accuracy
- Win rate correlation with accuracy difference
- Statistical significance (p-values)
- Confidence intervals on ELO ratings
