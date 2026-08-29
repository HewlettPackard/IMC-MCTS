#!/bin/bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

# 5+3 TOURNAMENT with PROPER GO RULES - Test against KataGo
# 6 NN players (trained with proper Go: captures, suicide, etc.) + 2 baselines
# 8 players = 28 matchups × 5 games = 140 total games

set -e  # Exit on error

echo "========================================="
echo "5+3 TOURNAMENT (PROPER GO RULES + KataGo)"
echo "========================================="
echo ""
echo "Configuration:"
echo "  • 6 NN Players (PROPER Go): 82%, 76%, 70%, 64%, 58%, 50%"
echo "  • 3 Baselines: Random, KataGo-1k, KataGo-5k"
echo "  • 8 total players"
echo "  • 28 matchups"
echo "  • 5 games per matchup"
echo "  • 140 total games"
echo ""
echo "Key Differences from Old Training:"
echo "  ✓ Stone captures enforced"
echo "  ✓ Suicide moves prevented"
echo "  ✓ Group liberties tracked"
echo "  ✓ Compatible with KataGo (real Go rules)"
echo ""
echo "Iterations per move: 500 (quick test)"
echo "Output: tournament_results_5plus3_proper_katago"
echo ""
echo "========================================="
echo ""

python3 tournament_runner.py \
    --games 5 \
    --iterations 500 \
    --players "5plus3_proper" \
    --output tournament_results_5plus3_proper_katago

echo ""
echo "========================================="
echo "Tournament complete!"
echo "Results saved to: tournament_results_5plus3_proper_katago/"
echo "========================================="
