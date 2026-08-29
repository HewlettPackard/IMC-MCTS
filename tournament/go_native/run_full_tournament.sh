#!/bin/bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

#
# Full Tournament - 50 games per matchup with 5000 iterations per move
# This is the complete tournament study configuration.
#
# Total games: 6 matchups × 50 games = 300 games
# Estimated time: 25-75 hours (sequential)
#
# Recommend running overnight or over a weekend
#

cd "$(dirname "$0")"

echo "Starting Full Tournament..."
echo "==========================="
echo ""
echo "Configuration:"
echo "  - 50 games per matchup"
echo "  - 5000 iterations per move"
echo "  - 60 move limit per game"
echo "  - Total: 300 games"
echo ""
echo "Estimated time: 25-75 hours"
echo "This will run continuously - recommend using tmux/screen!"
echo ""
echo "Press Ctrl+C to interrupt (progress will be saved)"
echo ""
read -p "Press Enter to start..."

# Run tournament with output logging
python3 tournament_runner.py \
    --games 50 \
    --iterations 5000 \
    --max-moves 60 \
    --output tournament_results_full \
    2>&1 | tee tournament_log_full.txt

echo ""
echo "Full tournament complete!"
echo "Results saved to: tournament_results_full/"
