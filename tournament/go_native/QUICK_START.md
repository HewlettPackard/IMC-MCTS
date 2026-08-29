# Quick Start Guide

## TL;DR - Run Tournaments

### 4 Players (Recommended)
```bash
cd tournament/go_native

# Full tournament (300 games, ~1-3 days)
tmux new -s tournament
./run_full_tournament.sh
```

### 10 Players (Extended Analysis)
```bash
cd tournament/go_native

# Full tournament (2250 games, ~8-25 DAYS)
tmux new -s tournament_10p
./run_full_tournament_10players.sh
```

## Generate Plots

After tournament completes:
```bash
cd analysis
python3 plot_results.py ../tournament_results_full/tournament_results.json
```

Outputs:
- `plots/elo_vs_accuracy.png` - Main result figure
- `plots/winrate_matrix.png` - Head-to-head heatmap
- `plots/score_distribution.png` - Game outcome distribution
- `plots/elo_evolution.png` - Rating changes over time
- `plots/tournament_summary.txt` - Statistical summary

## What's Been Built

### ✅ Complete Tournament System
- **4-player config**: 81.95%, 75.35%, 65.00%, 55.50% accuracy
- **10-player config**: 50.20% to 81.95% (evenly spaced)
- **Validation results**: Strong correlation (r=0.963), ~56 ELO per 10% accuracy
- **Ready to run**: Full tournament configurations

### ✅ Key Features
- Uses exact same heuristic as NN training
- Early termination at 60 moves (preserves evaluation diversity)
- ELO rating system (K=32, chess-style)
- Accuracy-based noise (simulates NN errors)
- Checkpoints every 25 games (safe to interrupt)
- Publication-quality visualizations

## Validation Results (30 games)

```
Player                  Accuracy   ELO    Win%
─────────────────────────────────────────────
High Accuracy           81.95%    1587   73.3%
Medium-High Accuracy    75.35%    1520   53.3%
Medium Accuracy         65.00%    1457   33.3%
Low Accuracy            55.50%    1437   20.0%

Correlation: r = 0.963
Trend: ~56 ELO points per 10% accuracy increase
```

## Tournament Sizes

| Config | Players | Matchups | Games/Matchup | Total Games | Quick Test | Full Tournament |
|--------|---------|----------|---------------|-------------|------------|-----------------|
| 4-player | 4 | 6 | 50 | 300 | 30-60 min | 1-3 days |
| 10-player | 10 | 45 | 50 | 2250 | 4-6 hours | 8-25 days |

## Important Tips

1. **Always use tmux/screen for full tournaments**
   ```bash
   tmux new -s tournament
   ./run_full_tournament.sh
   # Detach: Ctrl+B, then D
   # Re-attach: tmux attach -t tournament
   ```

2. **Checkpoints save progress every 25 games**
   - Safe to Ctrl+C interrupt
   - Results saved automatically

3. **Validate your configuration first**
   - Confirm the players and settings are correct
   - Check the correlation on a short run
   - Low time investment before the long tournament

4. **10-player tournament is LONG**
   - 2250 games takes 8-25 days
   - Plan accordingly
   - Consider running 4-player first

## File Locations

### Scripts
- `run_full_tournament.sh` - 4-player full tournament
- `run_full_tournament_10players.sh` - 10-player full tournament

### Results
- `tournament_results_full/` - Full tournament output
- `tournament_results_10players_*/` - 10-player output
- `checkpoint_*.json` - Progress checkpoints (every 25 games)

### Analysis
- `analysis/plot_results.py` - Generate all plots
- Results saved to `plots/` subdirectory

## Need Help?

See full documentation:
- `README.md` - Detailed system documentation
- Generated tournament outputs are local-only and excluded from the source release.

## Reporting Workflow

**Recommended workflow:**

1. Run 4-player full tournament (300 games)
   ```bash
   tmux new -s tournament
   ./run_full_tournament.sh
   ```

2. Generate plots
   ```bash
   cd analysis
   python3 plot_results.py ../tournament_results_full/tournament_results.json
   ```

3. Use `plots/elo_vs_accuracy.png` as main figure

4. Report:
   - Correlation coefficient (r)
   - ELO gain per 10% accuracy
   - Win rate analysis
   - Statistical significance

5. (Optional) Run 10-player tournament for extended analysis
