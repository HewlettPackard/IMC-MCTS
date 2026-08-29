#!/bin/bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

#
# Full Tournament - 10 Players
# 50 games per matchup with 5000 iterations per move
# This is the extended tournament study configuration.
#
# Total games: 45 matchups × 50 games = 2250 games
# Estimated time: 200-600 hours (sequential) = ~8-25 days
#
# STRONGLY recommend running overnight or over multiple days
# Use tmux/screen to prevent interruption
#

cd "$(dirname "$0")"

echo "Starting Full Tournament (10 Players)..."
echo "========================================="
echo ""
echo "Configuration:"
echo "  - 10 players (50.20% to 81.95% accuracy)"
echo "  - 50 games per matchup"
echo "  - 5000 iterations per move"
echo "  - 60 move limit per game"
echo "  - Total: 45 matchups × 50 games = 2250 games"
echo ""
echo "Estimated time: 200-600 hours (~8-25 days)"
echo "This will run continuously - MUST use tmux/screen!"
echo ""
echo "Checkpoints saved every 25 games for recovery"
echo "Press Ctrl+C to interrupt (progress will be saved)"
echo ""
read -p "Press Enter to start..."

# Run tournament with output logging
python3 tournament_runner.py \
    --games 50 \
    --iterations 5000 \
    --max-moves 60 \
    --players 10 \
    --output tournament_results_10players_full \
    2>&1 | tee tournament_log_10players_full.txt

echo ""
echo "Full tournament complete!"
echo "Results saved to: tournament_results_10players_full/"
echo ""
echo "To generate plots:"
echo "  cd analysis"
echo "  python3 plot_results.py ../tournament_results_10players_full/tournament_results.json"
