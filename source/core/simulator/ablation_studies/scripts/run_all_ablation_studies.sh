#!/bin/bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

#
# Master Script for Running All Ablation Studies
# ================================================
#
# This script runs all ablation study scripts in sequence:
# 1. Progressive build-up study
# 2. Design alternatives study
# 3. LaTeX table generation
# 4. Plot generation
#
# Output:
# - CSV/JSON data files in experiment_results/
# - LaTeX tables (printed to console)
# - PNG plots in plots/
#

set -e  # Exit on error

echo "================================================================================"
echo "RUNNING ALL ABLATION STUDIES"
echo "================================================================================"
echo ""
echo "This will generate:"
echo "  - Performance data (CSV/JSON)"
echo "  - LaTeX tables (copy-paste ready)"
echo "  - Publication-quality plots (300 DPI)"
echo ""
echo "================================================================================"
echo ""

# Change to scripts/analysis directory
cd "$(dirname "$0")"

# Step 1: Run progressive build-up study
echo "Step 1/4: Running progressive build-up study..."
echo "--------------------------------------------------------------------------------"
python3 ablation_progressive_buildup.py
echo ""

# Step 2: Run design alternatives study
echo "Step 2/4: Running design alternatives study..."
echo "--------------------------------------------------------------------------------"
python3 ablation_design_alternatives.py
echo ""

# Step 3: Generate LaTeX tables
echo "Step 3/4: Generating LaTeX tables..."
echo "--------------------------------------------------------------------------------"
python3 generate_ablation_tables.py
echo ""

# Step 4: Generate plots
echo "Step 4/4: Generating plots..."
echo "--------------------------------------------------------------------------------"
python3 plot_ablation_study.py
echo ""

echo "================================================================================"
echo "✅ ALL ABLATION STUDIES COMPLETE!"
echo "================================================================================"
echo ""
echo "Output files:"
echo "  📄 experiment_results/ablation_progressive_buildup.csv"
echo "  📄 experiment_results/ablation_design_alternatives.csv"
echo "  📊 plots/ablation_progressive_speedup.png"
echo "  📊 plots/ablation_design_alternatives.png"
echo "  📊 plots/ablation_scalability.png"
echo ""
echo "LaTeX tables were printed above - scroll up to copy them"
echo "================================================================================"
