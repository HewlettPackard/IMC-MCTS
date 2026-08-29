#!/bin/bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

# Pachi test - 2 games per matchup
# 3 NN players (proper Go) + Pachi = 4 players
# 6 matchups × 2 games = 12 total games

set -e

echo "========================================="
echo "PACHI 12-GAME TEST (PROPER GO RULES)"
echo "========================================="
echo ""
echo "Configuration:"
echo "  • 3 NN Players (PROPER Go): 82%, 70%, 58%"
echo "  • 1 Baseline: Pachi"
echo "  • 4 total players"
echo "  • 6 matchups"
echo "  • 2 games per matchup"
echo "  • 12 total games"
echo ""
echo "Goal: Validate Go rules fix with Pachi"
echo "Iterations per move: 500"
echo "Output: pachi_12games"
echo ""
echo "========================================="
echo ""

python3 tournament_runner.py \
    --games 2 \
    --iterations 500 \
    --players "3plus1_proper_pachi" \
    --output pachi_12games

echo ""
echo "========================================="
echo "12-game test complete!"
echo "Results saved to: pachi_12games/"
echo "========================================="
