#!/bin/bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

#
# Full Tournament - 7 NN + 3 Baselines (10 Total Players)
# 50 games per matchup with full iterations
# For final tournament results
#
# Total games: 45 matchups × 50 games = 2250 games
# Estimated time: ~200-600 hours (8-25 days)
#

cd "$(dirname "$0")"

echo "Starting Full Tournament (7 NN + 3 Baselines)..."
echo "================================================="
echo ""
echo "Configuration:"
echo "  - 7 NN players (82%, 74%, 70%, 66%, 62%, 54%, 50%)"
echo "  - 3 Baseline players (Random, Greedy, Pachi)"
echo "  - 50 games per matchup"
echo "  - 5000 iterations per move"
echo "  - 60 move limit per game"
echo "  - Total: 45 matchups × 50 games = 2250 games"
echo ""
echo "⚠️  WARNING: This will take 8-25 DAYS to complete!"
echo "    Use tmux/screen to run in background."
echo ""
echo "Estimated time: 200-600 hours (8-25 days)"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."
echo ""

python3 tournament_runner.py \
    --games 50 \
    --iterations 5000 \
    --max-moves 60 \
    --players 7plus3 \
    --output tournament_results_7+3

echo ""
echo "Full tournament complete!"
echo "Results saved to: tournament_results_7+3/"
echo ""
echo "Generating plots..."
python3 analysis/plot_results_styled.py tournament_results_7+3/tournament_results.json
echo ""
echo "Done! Check tournament_results_7+3/plots_styled/ for visualizations."
echo ""
