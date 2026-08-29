#!/bin/bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

# Full 5+3 tournament: 5 NN players + Random + KataGo-1k + KataGo-5k
# 8 players = 28 matchups × 50 games = 1400 total games

set -e  # Exit on error

echo "========================================="
echo "5+3 TOURNAMENT (with KataGo) - FULL"
echo "========================================="
echo ""
echo "Configuration:"
echo "  • 5 NN Players: 82%, 74%, 66%, 54%, 50%"
echo "  • 3 Baselines: Random, KataGo-1k, KataGo-5k"
echo "  • 8 total players"
echo "  • 28 matchups"
echo "  • 50 games per matchup"
echo "  • 1400 total games"
echo ""
echo "Iterations per move: 5000 (full strength)"
echo "Output: tournament_results_5plus3_katago_FINAL"
echo ""
echo "⚠️  WARNING: This will take MANY hours to complete!"
echo "⚠️  Estimated time: 20-40 hours depending on CPU"
echo ""
echo "========================================="
echo ""

# Confirm before starting
read -p "Continue with full tournament? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Tournament cancelled."
    exit 1
fi

python3 tournament_runner.py \
    --games 50 \
    --iterations 5000 \
    --players "5plus3" \
    --output tournament_results_5plus3_katago_FINAL

echo ""
echo "========================================="
echo "Tournament complete!"
echo "Results saved to: tournament_results_5plus3_katago_FINAL/"
echo "========================================="
