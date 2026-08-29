#!/bin/bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

###############################################################################
# Run SST Simulations for Main Boards with Complete Specs
###############################################################################
#
# Runs SST simulations for boards with complete specifications (automated
# synthesis + native 22nm ADC/DAC literature models):
#   - 5x5, 9x9, 13x13, 19x19
#   - All performance levels (low, medium, high)
#   - 12 total simulations
#
# Output: sst_logs/run_NxN_performance_LEVEL.log
#
###############################################################################

echo "========================================================================"
echo "SST SIMULATION - MAIN BOARDS WITH COMPLETE SPECS"
echo "========================================================================"
echo ""
echo "Running 12 SST simulations (4 board sizes × 3 performance levels)"
echo "Boards: 5x5, 9x9, 13x13, 19x19"
echo "Specs: Automated synthesis + Native 22nm ADC/DAC literature models"
echo ""

# Create logs directory
mkdir -p sst_logs

# Main board sizes (with complete specs)
BOARD_SIZES=(5 9 13 19)

# Performance levels
LEVELS=(low medium high)

# Total count
TOTAL=$((${#BOARD_SIZES[@]} * ${#LEVELS[@]}))
CURRENT=0

echo "Starting simulations..."
echo ""

# Run all combinations
for SIZE in "${BOARD_SIZES[@]}"; do
    for LEVEL in "${LEVELS[@]}"; do
        CURRENT=$((CURRENT + 1))
        LOGFILE="sst_logs/run_${SIZE}x${SIZE}_performance_${LEVEL}.log"

        echo "[$CURRENT/$TOTAL] Running ${SIZE}×${SIZE} board, $LEVEL performance..."
        echo "         Output: $LOGFILE"

        # Run simulation and save log (with timeout of 10 minutes)
        timeout 600 python3 run_${SIZE}x${SIZE}_performance.py $LEVEL > "$LOGFILE" 2>&1

        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 0 ]; then
            echo "         ✅ Complete"
        elif [ $EXIT_CODE -eq 124 ]; then
            echo "         ⚠️  Timeout (see log for partial results)"
        else
            echo "         ⚠️  Error (exit code: $EXIT_CODE, see log for details)"
        fi
        echo ""
    done
done

echo "========================================================================"
echo "SIMULATION COMPLETE"
echo "========================================================================"
echo ""
echo "Generated $TOTAL SST simulation logs in sst_logs/"
echo ""
echo "Logs:"
for SIZE in "${BOARD_SIZES[@]}"; do
    for LEVEL in "${LEVELS[@]}"; do
        LOGFILE="sst_logs/run_${SIZE}x${SIZE}_performance_${LEVEL}.log"
        if [ -f "$LOGFILE" ]; then
            FILESIZE=$(wc -l < "$LOGFILE")
            echo "  ✅ $LOGFILE ($FILESIZE lines)"
        fi
    done
done
echo ""
echo "✅ All simulations use updated board_config.py with:"
echo "   - Automated synthesis for digital logic"
echo "   - Native 22nm ADC/DAC literature models (Haraldstad, Eslahi)"
echo "   - Complete timing/energy specifications"
echo ""
