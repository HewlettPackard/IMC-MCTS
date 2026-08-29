#!/bin/bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

# Pachi test - 2 games per matchup
# 6 NN players (proper Go) + Pachi = 7 players
# 21 matchups × 2 games = 42 total games

set -e

echo "========================================="
echo "PACHI TEST (PROPER GO RULES) - 2 GAMES EACH"
echo "========================================="
echo ""
echo "Configuration:"
echo "  • 6 NN Players (PROPER Go): 82%, 76%, 70%, 64%, 58%, 50%"
echo "  • 1 Baseline: Pachi"
echo "  • 7 total players"
echo "  • 21 matchups"
echo "  • 2 games per matchup"
echo "  • 42 total games"
echo ""
echo "Goal: Extended test with Pachi (real Go engine)"
echo "Iterations per move: 500"
echo "Output: pachi_test_2games"
echo ""
echo "========================================="
echo ""

python3 tournament_runner.py \
    --games 2 \
    --iterations 500 \
    --players "5plus1_proper_pachi" \
    --output pachi_test_2games

echo ""
echo "========================================="
echo "Test complete!"
echo "Results saved to: pachi_test_2games/"
echo "========================================="
