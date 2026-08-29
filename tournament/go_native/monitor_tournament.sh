#!/bin/bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

# Monitor tournament progress

RESULTS_DIR="${1:-tournament_results_5plus3_katago_quick}"

echo "Monitoring tournament in: $RESULTS_DIR"
echo "Press Ctrl+C to stop monitoring"
echo ""

while true; do
    clear
    echo "=========================================="
    echo "TOURNAMENT PROGRESS MONITOR"
    echo "=========================================="
    echo ""

    # Check if tournament process is running
    if ps aux | grep -q "[t]ournament_runner.py"; then
        echo "Status: ✓ Tournament is RUNNING"
        echo ""

        # Find latest checkpoint
        if [ -d "$RESULTS_DIR" ]; then
            LATEST=$(ls -t "$RESULTS_DIR"/checkpoint_*.json 2>/dev/null | head -1)
            if [ -n "$LATEST" ]; then
                GAMES=$(basename "$LATEST" | grep -oP '\d+')
                echo "Latest checkpoint: $GAMES games completed"
                echo "File: $(basename $LATEST)"
                echo ""

                # Estimate progress
                TOTAL=140
                PERCENT=$((GAMES * 100 / TOTAL))
                echo "Progress: $GAMES/$TOTAL games ($PERCENT%)"

                # Progress bar
                BARS=$((PERCENT / 2))
                printf "["
                for i in $(seq 1 50); do
                    if [ $i -le $BARS ]; then
                        printf "="
                    else
                        printf " "
                    fi
                done
                printf "] $PERCENT%%\n"
                echo ""

                # Show last game from checkpoint
                python3 -c "
import json
try:
    with open('$LATEST') as f:
        data = json.load(f)
        matchups = data.get('matchup_results', {})
        if matchups:
            last_key = list(matchups.keys())[-1]
            last_matchup = matchups[last_key]
            games = last_matchup.get('games', [])
            if games:
                last_game = games[-1]
                print(f\"Last game:\")
                print(f\"  {last_game['black_player']} (B) vs {last_game['white_player']} (W)\")
                print(f\"  Winner: {last_game['winner']}\")
                print(f\"  Score: {last_game['final_score']:.2f}\")
except Exception as e:
    print(f'Could not parse checkpoint: {e}')
" 2>/dev/null
            else
                echo "Waiting for first checkpoint..."
            fi
        else
            echo "No checkpoints yet - tournament initializing..."
        fi
    else
        echo "Status: ✗ Tournament not running"
        echo ""

        # Check if completed
        if [ -f "$RESULTS_DIR/tournament_results.json" ]; then
            echo "Tournament COMPLETED!"
            echo "Results in: $RESULTS_DIR/"
            break
        fi
    fi

    echo ""
    echo "Refreshing in 10 seconds... (Ctrl+C to exit)"
    sleep 10
done
