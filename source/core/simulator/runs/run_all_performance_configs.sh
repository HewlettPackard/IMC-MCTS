#!/bin/bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

###############################################################################
# Run All Performance Configurations and Save SST Logs
###############################################################################
#
# This script runs SST simulations for all board sizes (2x2, 3x3, 5x5, 9x9,
# 13x13, 19x19) at all performance levels (low, medium, high) and saves
# authentic SST simulation logs.
#
# Output: run_NxN_performance_LEVEL.log
#
###############################################################################

echo "========================================================================"
echo "SST SIMULATION LOG GENERATION"
echo "========================================================================"
echo ""
echo "This will run 18 SST simulations (6 board sizes × 3 performance levels)"
echo "Each simulation produces an authentic SST log with full trace output."
echo ""

# Create logs directory
mkdir -p sst_logs

# Board sizes to test
BOARD_SIZES=(2 3 5 9 13 19)

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

        # Run simulation and save log
        python3 run_${SIZE}x${SIZE}_performance.py $LEVEL > "$LOGFILE" 2>&1

        if [ $? -eq 0 ]; then
            echo "         ✅ Complete"
        else
            echo "         ⚠️  Error (see log for details)"
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
echo "These logs show authentic SST simulation output with:"
echo "  - Timestamp-based logging (microseconds)"
echo "  - Rank and core information"
echo "  - Component-level trace messages"
echo "  - Performance and energy statistics"
echo ""
echo "Performance sweep complete."
