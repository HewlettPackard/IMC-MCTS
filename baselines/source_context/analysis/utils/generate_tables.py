#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Generate Publication-Ready Tables from MCTS Benchmark Results
==============================================================

This script reads CSV files from the results/ directory and generates
publication-ready tables for research papers:

1. Phase Breakdown Table: Shows latency and energy for each MCTS phase
2. Scalability Analysis Table: Shows performance across different board sizes

Outputs:
    - Markdown format (for README, reports)
    - LaTeX format (for papers)
    - CSV format (for further analysis)

Usage:
    python utils/generate_tables.py [--board-size 9] [--output-dir tables]
"""

import os
import sys
import csv
import argparse
import statistics
from typing import Dict, List, Tuple
from pathlib import Path


def load_csv_file(filepath: str) -> List[Dict]:
    """Load and parse a CSV benchmark file"""
    results = []
    with open(filepath, 'r') as csv_file_handle:
        csv_reader = csv.DictReader(csv_file_handle)
        for row in csv_reader:
            # Convert numeric fields
            numeric_fields = [
                'num_positions', 'iterations', 'trial_num', 'n_trees', 'n_playouts',
                'total_latency_ms', 'total_power_mw', 'total_energy_uj', 'tree_size',
                'selection_latency_ms', 'selection_power_mw', 'selection_energy_uj', 'selection_percent',
                'expansion_latency_ms', 'expansion_power_mw', 'expansion_energy_uj', 'expansion_percent',
                'simulation_latency_ms', 'simulation_power_mw', 'simulation_energy_uj', 'simulation_percent',
                'backpropagation_latency_ms', 'backpropagation_power_mw', 'backpropagation_energy_uj', 'backpropagation_percent'
            ]
            for field_name in numeric_fields:
                if field_name in row and row[field_name]:
                    row[field_name] = float(row[field_name])
            results.append(row)
    return results


def aggregate_by_board_size(results: List[Dict]) -> Dict[str, List[Dict]]:
    """Group results by board size"""
    results_by_board_size = {}
    for result in results:
        board_size = result['board_size']
        if board_size not in results_by_board_size:
            results_by_board_size[board_size] = []
        results_by_board_size[board_size].append(result)
    return results_by_board_size


def calculate_stats(values: List[float]) -> Tuple[float, float]:
    """Calculate mean and standard deviation"""
    mean_value = statistics.mean(values)
    standard_deviation = statistics.stdev(values) if len(values) > 1 else 0.0
    return mean_value, standard_deviation


def format_value(mean: float, std: float, units: str = "", decimals: int = 1) -> str:
    """Format value as 'mean ± std units'"""
    if std == 0:
        return f"{mean:.{decimals}f}{units}"
    return f"{mean:.{decimals}f} ± {std:.{decimals}f}{units}"


def generate_phase_breakdown_table(cpu_data: List[Dict], gpu_fair_data: List[Dict],
                                   board_size: str = '9x9') -> Dict[str, str]:
    """
    Generate phase breakdown comparison table

    Returns dict with keys: 'markdown', 'latex', 'csv'
    """

    # Filter by board size
    cpu_trials = [t for t in cpu_data if t['board_size'] == board_size]
    gpu_trials = [t for t in gpu_fair_data if t['board_size'] == board_size]

    if not cpu_trials or not gpu_trials:
        return {
            'markdown': f"Error: No data for board size {board_size}",
            'latex': "",
            'csv': ""
        }

    phases = ['selection', 'expansion', 'simulation', 'backpropagation']
    phase_names = ['Selection', 'Expansion', 'Rollout', 'Backpropagation']

    # Calculate statistics for each phase
    table_rows = []
    for phase, display_name in zip(phases, phase_names):
        cpu_lat = [trial[f'{phase}_latency_ms'] for trial in cpu_trials]
        gpu_lat = [trial[f'{phase}_latency_ms'] for trial in gpu_trials]
        cpu_eng = [trial[f'{phase}_energy_uj'] / 1000 for trial in cpu_trials]  # Convert to mJ
        gpu_eng = [trial[f'{phase}_energy_uj'] / 1000 for trial in gpu_trials]  # Convert to mJ

        table_rows.append({
            'phase': display_name,
            'cpu_lat_mean': statistics.mean(cpu_lat),
            'cpu_lat_std': statistics.stdev(cpu_lat) if len(cpu_lat) > 1 else 0,
            'gpu_lat_mean': statistics.mean(gpu_lat),
            'gpu_lat_std': statistics.stdev(gpu_lat) if len(gpu_lat) > 1 else 0,
            'cpu_eng_mean': statistics.mean(cpu_eng),
            'cpu_eng_std': statistics.stdev(cpu_eng) if len(cpu_eng) > 1 else 0,
            'gpu_eng_mean': statistics.mean(gpu_eng),
            'gpu_eng_std': statistics.stdev(gpu_eng) if len(gpu_eng) > 1 else 0,
        })

    # Add totals
    cpu_total_lat = [trial['total_latency_ms'] for trial in cpu_trials]
    gpu_total_lat = [trial['total_latency_ms'] for trial in gpu_trials]
    cpu_total_eng = [trial['total_energy_uj'] / 1000 for trial in cpu_trials]
    gpu_total_eng = [trial['total_energy_uj'] / 1000 for trial in gpu_trials]

    table_rows.append({
        'phase': 'Total',
        'cpu_lat_mean': statistics.mean(cpu_total_lat),
        'cpu_lat_std': statistics.stdev(cpu_total_lat) if len(cpu_total_lat) > 1 else 0,
        'gpu_lat_mean': statistics.mean(gpu_total_lat),
        'gpu_lat_std': statistics.stdev(gpu_total_lat) if len(gpu_total_lat) > 1 else 0,
        'cpu_eng_mean': statistics.mean(cpu_total_eng),
        'cpu_eng_std': statistics.stdev(cpu_total_eng) if len(cpu_total_eng) > 1 else 0,
        'gpu_eng_mean': statistics.mean(gpu_total_eng),
        'gpu_eng_std': statistics.stdev(gpu_total_eng) if len(gpu_total_eng) > 1 else 0,
    })

    # Get iterations from config
    iterations = cpu_trials[0]['iterations']

    # Markdown format
    markdown_table = f"# Phase Breakdown Table - {board_size} Board ({iterations:.0f} iterations)\n\n"
    markdown_table += "| Phase            | Latency (ms)      |                   | Energy (mJ)      |                  |\n"
    markdown_table += "|------------------|-------------------|-------------------|------------------|------------------|\n"
    markdown_table += "|                  | **CPU**           | **GPU**           | **CPU**          | **GPU**          |\n"
    markdown_table += "|------------------|-------------------|-------------------|------------------|------------------|\n"

    for table_row in table_rows:
        phase = table_row['phase']
        cpu_lat = format_value(table_row['cpu_lat_mean'], table_row['cpu_lat_std'], "", 2)
        gpu_lat = format_value(table_row['gpu_lat_mean'], table_row['gpu_lat_std'], "", 2)
        cpu_eng = format_value(table_row['cpu_eng_mean'], table_row['cpu_eng_std'], "", 2)
        gpu_eng = format_value(table_row['gpu_eng_mean'], table_row['gpu_eng_std'], "", 2)

        separator = "|------------------|-------------------|-------------------|------------------|------------------|" if phase == 'Total' else ""
        if phase == 'Total':
            markdown_table += separator + "\n"
        markdown_table += f"| {phase:<16} | {cpu_lat:>17} | {gpu_lat:>17} | {cpu_eng:>16} | {gpu_eng:>16} |\n"

    # LaTeX format
    latex_table = "\\begin{table}[h]\n"
    latex_table += "\\centering\n"
    latex_table += f"\\caption{{Phase Breakdown - {board_size} Board ({iterations:.0f} iterations)}}\n"
    latex_table += "\\begin{tabular}{l|cc|cc}\n"
    latex_table += "\\hline\n"
    latex_table += " & \\multicolumn{2}{c|}{Latency (ms)} & \\multicolumn{2}{c}{Energy (mJ)} \\\\\n"
    latex_table += "Phase & CPU & GPU & CPU & GPU \\\\\n"
    latex_table += "\\hline\n"

    for table_row in table_rows:
        if table_row['phase'] == 'Total':
            latex_table += "\\hline\n"
        phase = table_row['phase']
        cpu_lat = f"{table_row['cpu_lat_mean']:.2f} $\\pm$ {table_row['cpu_lat_std']:.2f}" if table_row['cpu_lat_std'] > 0 else f"{table_row['cpu_lat_mean']:.2f}"
        gpu_lat = f"{table_row['gpu_lat_mean']:.2f} $\\pm$ {table_row['gpu_lat_std']:.2f}" if table_row['gpu_lat_std'] > 0 else f"{table_row['gpu_lat_mean']:.2f}"
        cpu_eng = f"{table_row['cpu_eng_mean']:.2f} $\\pm$ {table_row['cpu_eng_std']:.2f}" if table_row['cpu_eng_std'] > 0 else f"{table_row['cpu_eng_mean']:.2f}"
        gpu_eng = f"{table_row['gpu_eng_mean']:.2f} $\\pm$ {table_row['gpu_eng_std']:.2f}" if table_row['gpu_eng_std'] > 0 else f"{table_row['gpu_eng_mean']:.2f}"

        latex_table += f"{phase} & {cpu_lat} & {gpu_lat} & {cpu_eng} & {gpu_eng} \\\\\n"

    latex_table += "\\hline\n"
    latex_table += "\\end{tabular}\n"
    latex_table += "\\end{table}\n"

    # CSV format
    csv_table = "phase,cpu_latency_mean,cpu_latency_std,gpu_latency_mean,gpu_latency_std,cpu_energy_mean,cpu_energy_std,gpu_energy_mean,gpu_energy_std\n"
    for table_row in table_rows:
        csv_table += f"{table_row['phase']},{table_row['cpu_lat_mean']:.3f},{table_row['cpu_lat_std']:.3f},"
        csv_table += f"{table_row['gpu_lat_mean']:.3f},{table_row['gpu_lat_std']:.3f},"
        csv_table += f"{table_row['cpu_eng_mean']:.3f},{table_row['cpu_eng_std']:.3f},"
        csv_table += f"{table_row['gpu_eng_mean']:.3f},{table_row['gpu_eng_std']:.3f}\n"

    return {
        'markdown': markdown_table,
        'latex': latex_table,
        'csv': csv_table
    }


def generate_scalability_table(cpu_data: List[Dict], gpu_fair_data: List[Dict],
                               gpu_cap_data: List[Dict] = None) -> Dict[str, str]:
    """
    Generate scalability analysis table across all board sizes

    Returns dict with keys: 'markdown', 'latex', 'csv'
    """

    # Group by board size
    cpu_results_by_board_size = aggregate_by_board_size(cpu_data)
    gpu_fair_results_by_board_size = aggregate_by_board_size(gpu_fair_data)
    gpu_cap_results_by_board_size = aggregate_by_board_size(gpu_cap_data) if gpu_cap_data else {}

    board_sizes = sorted(
        cpu_results_by_board_size.keys(),
        key=lambda size_label: int(size_label.split('x')[0]),
    )

    table_rows = []
    for board_size in board_sizes:
        cpu_trials = cpu_results_by_board_size.get(board_size, [])
        gpu_fair_trials = gpu_fair_results_by_board_size.get(board_size, [])
        gpu_cap_trials = gpu_cap_results_by_board_size.get(board_size, [])

        if not cpu_trials or not gpu_fair_trials:
            continue

        iterations = cpu_trials[0]['iterations']

        # Calculate statistics
        cpu_lat = [trial['total_latency_ms'] for trial in cpu_trials]
        cpu_eng = [trial['total_energy_uj'] / 1000 for trial in cpu_trials]  # Convert to mJ
        gpu_fair_lat = [trial['total_latency_ms'] for trial in gpu_fair_trials]
        gpu_fair_eng = [trial['total_energy_uj'] / 1000 for trial in gpu_fair_trials]

        # Calculate derived metrics
        # Energy per move (mJ/iteration)
        cpu_eng_per_move = [energy_mj / iterations for energy_mj in cpu_eng]
        gpu_fair_eng_per_move = [energy_mj / iterations for energy_mj in gpu_fair_eng]

        # Throughput per Watt (iterations/s/W)
        # Throughput = iterations / (latency_ms / 1000) = iterations * 1000 / latency_ms
        # Power = energy_mJ / latency_ms = energy_mJ / latency_ms
        # Throughput/W = (iterations * 1000 / latency_ms) / (energy_mJ / latency_ms)
        #              = iterations * 1000 / energy_mJ
        cpu_throughput_per_w = [(iterations * 1000) / energy_mj for energy_mj in cpu_eng]
        gpu_fair_throughput_per_w = [(iterations * 1000) / energy_mj for energy_mj in gpu_fair_eng]

        table_row = {
            'board_size': board_size,
            'iterations': iterations,
            'cpu_lat_mean': statistics.mean(cpu_lat),
            'cpu_lat_std': statistics.stdev(cpu_lat) if len(cpu_lat) > 1 else 0,
            'gpu_fair_lat_mean': statistics.mean(gpu_fair_lat),
            'gpu_fair_lat_std': statistics.stdev(gpu_fair_lat) if len(gpu_fair_lat) > 1 else 0,
            'cpu_eng_mean': statistics.mean(cpu_eng),
            'cpu_eng_std': statistics.stdev(cpu_eng) if len(cpu_eng) > 1 else 0,
            'gpu_fair_eng_mean': statistics.mean(gpu_fair_eng),
            'gpu_fair_eng_std': statistics.stdev(gpu_fair_eng) if len(gpu_fair_eng) > 1 else 0,
            'cpu_eng_per_move_mean': statistics.mean(cpu_eng_per_move),
            'cpu_eng_per_move_std': statistics.stdev(cpu_eng_per_move) if len(cpu_eng_per_move) > 1 else 0,
            'gpu_fair_eng_per_move_mean': statistics.mean(gpu_fair_eng_per_move),
            'gpu_fair_eng_per_move_std': statistics.stdev(gpu_fair_eng_per_move) if len(gpu_fair_eng_per_move) > 1 else 0,
            'cpu_throughput_per_w_mean': statistics.mean(cpu_throughput_per_w),
            'cpu_throughput_per_w_std': statistics.stdev(cpu_throughput_per_w) if len(cpu_throughput_per_w) > 1 else 0,
            'gpu_fair_throughput_per_w_mean': statistics.mean(gpu_fair_throughput_per_w),
            'gpu_fair_throughput_per_w_std': statistics.stdev(gpu_fair_throughput_per_w) if len(gpu_fair_throughput_per_w) > 1 else 0,
        }

        # Add GPU capability data if available
        if gpu_cap_trials:
            gpu_cap_lat = [trial['total_latency_ms'] for trial in gpu_cap_trials]
            gpu_cap_eng = [trial['total_energy_uj'] / 1000 for trial in gpu_cap_trials]
            gpu_cap_eng_per_move = [energy_mj / iterations for energy_mj in gpu_cap_eng]
            gpu_cap_throughput_per_w = [(iterations * 1000) / energy_mj for energy_mj in gpu_cap_eng]

            table_row.update({
                'gpu_cap_lat_mean': statistics.mean(gpu_cap_lat),
                'gpu_cap_lat_std': statistics.stdev(gpu_cap_lat) if len(gpu_cap_lat) > 1 else 0,
                'gpu_cap_eng_mean': statistics.mean(gpu_cap_eng),
                'gpu_cap_eng_std': statistics.stdev(gpu_cap_eng) if len(gpu_cap_eng) > 1 else 0,
                'gpu_cap_eng_per_move_mean': statistics.mean(gpu_cap_eng_per_move),
                'gpu_cap_eng_per_move_std': statistics.stdev(gpu_cap_eng_per_move) if len(gpu_cap_eng_per_move) > 1 else 0,
                'gpu_cap_throughput_per_w_mean': statistics.mean(gpu_cap_throughput_per_w),
                'gpu_cap_throughput_per_w_std': statistics.stdev(gpu_cap_throughput_per_w) if len(gpu_cap_throughput_per_w) > 1 else 0,
            })

        table_rows.append(table_row)

    # Markdown format
    has_gpu_cap = any('gpu_cap_lat_mean' in table_row for table_row in table_rows)

    markdown_table = "# Scalability Analysis Table\n\n"
    markdown_table += "## Latency (ms)\n\n"
    if has_gpu_cap:
        markdown_table += "| Board Size | Iterations | CPU              | GPU (Fair)       | GPU (Capability) |\n"
        markdown_table += "|------------|------------|------------------|------------------|------------------|\n"
    else:
        markdown_table += "| Board Size | Iterations | CPU              | GPU (Fair)       |\n"
        markdown_table += "|------------|------------|------------------|------------------|\n"

    for table_row in table_rows:
        cpu_lat = format_value(table_row['cpu_lat_mean'], table_row['cpu_lat_std'], "", 1)
        gpu_fair_lat = format_value(table_row['gpu_fair_lat_mean'], table_row['gpu_fair_lat_std'], "", 1)

        if has_gpu_cap and 'gpu_cap_lat_mean' in table_row:
            gpu_cap_lat = format_value(table_row['gpu_cap_lat_mean'], table_row['gpu_cap_lat_std'], "", 1)
            markdown_table += f"| {table_row['board_size']:<10} | {table_row['iterations']:<10.0f} | {cpu_lat:>16} | {gpu_fair_lat:>16} | {gpu_cap_lat:>16} |\n"
        else:
            markdown_table += f"| {table_row['board_size']:<10} | {table_row['iterations']:<10.0f} | {cpu_lat:>16} | {gpu_fair_lat:>16} |\n"

    markdown_table += "\n## Energy (mJ)\n\n"
    if has_gpu_cap:
        markdown_table += "| Board Size | Iterations | CPU              | GPU (Fair)       | GPU (Capability) |\n"
        markdown_table += "|------------|------------|------------------|------------------|------------------|\n"
    else:
        markdown_table += "| Board Size | Iterations | CPU              | GPU (Fair)       |\n"
        markdown_table += "|------------|------------|------------------|------------------|\n"

    for table_row in table_rows:
        cpu_eng = format_value(table_row['cpu_eng_mean'], table_row['cpu_eng_std'], "", 1)
        gpu_fair_eng = format_value(table_row['gpu_fair_eng_mean'], table_row['gpu_fair_eng_std'], "", 1)

        if has_gpu_cap and 'gpu_cap_eng_mean' in table_row:
            gpu_cap_eng = format_value(table_row['gpu_cap_eng_mean'], table_row['gpu_cap_eng_std'], "", 1)
            markdown_table += f"| {table_row['board_size']:<10} | {table_row['iterations']:<10.0f} | {cpu_eng:>16} | {gpu_fair_eng:>16} | {gpu_cap_eng:>16} |\n"
        else:
            markdown_table += f"| {table_row['board_size']:<10} | {table_row['iterations']:<10.0f} | {cpu_eng:>16} | {gpu_fair_eng:>16} |\n"

    markdown_table += "\n## Energy per Move (mJ/iteration)\n\n"
    if has_gpu_cap:
        markdown_table += "| Board Size | CPU              | GPU (Fair)       | GPU (Capability) |\n"
        markdown_table += "|------------|------------------|------------------|------------------|\n"
    else:
        markdown_table += "| Board Size | CPU              | GPU (Fair)       |\n"
        markdown_table += "|------------|------------------|------------------|\n"

    for table_row in table_rows:
        cpu_epm = format_value(table_row['cpu_eng_per_move_mean'], table_row['cpu_eng_per_move_std'], "", 4)
        gpu_fair_epm = format_value(table_row['gpu_fair_eng_per_move_mean'], table_row['gpu_fair_eng_per_move_std'], "", 4)

        if has_gpu_cap and 'gpu_cap_eng_per_move_mean' in table_row:
            gpu_cap_epm = format_value(table_row['gpu_cap_eng_per_move_mean'], table_row['gpu_cap_eng_per_move_std'], "", 4)
            markdown_table += f"| {table_row['board_size']:<10} | {cpu_epm:>16} | {gpu_fair_epm:>16} | {gpu_cap_epm:>16} |\n"
        else:
            markdown_table += f"| {table_row['board_size']:<10} | {cpu_epm:>16} | {gpu_fair_epm:>16} |\n"

    markdown_table += "\n## Throughput per Watt (moves/s/W)\n\n"
    if has_gpu_cap:
        markdown_table += "| Board Size | CPU              | GPU (Fair)       | GPU (Capability) |\n"
        markdown_table += "|------------|------------------|------------------|------------------|\n"
    else:
        markdown_table += "| Board Size | CPU              | GPU (Fair)       |\n"
        markdown_table += "|------------|------------------|------------------|\n"

    for table_row in table_rows:
        cpu_tpw = format_value(table_row['cpu_throughput_per_w_mean'], table_row['cpu_throughput_per_w_std'], "", 1)
        gpu_fair_tpw = format_value(table_row['gpu_fair_throughput_per_w_mean'], table_row['gpu_fair_throughput_per_w_std'], "", 1)

        if has_gpu_cap and 'gpu_cap_throughput_per_w_mean' in table_row:
            gpu_cap_tpw = format_value(table_row['gpu_cap_throughput_per_w_mean'], table_row['gpu_cap_throughput_per_w_std'], "", 1)
            markdown_table += f"| {table_row['board_size']:<10} | {cpu_tpw:>16} | {gpu_fair_tpw:>16} | {gpu_cap_tpw:>16} |\n"
        else:
            markdown_table += f"| {table_row['board_size']:<10} | {cpu_tpw:>16} | {gpu_fair_tpw:>16} |\n"

    # LaTeX format
    latex_table = "\\begin{table}[h]\n\\centering\n"
    latex_table += "\\caption{Scalability Analysis}\n"

    if has_gpu_cap:
        latex_table += "\\begin{tabular}{l|r|rrr|rrr}\n\\hline\n"
        latex_table += " & & \\multicolumn{3}{c|}{Latency (ms)} & \\multicolumn{3}{c}{Energy (mJ)} \\\\\n"
        latex_table += "Board & Iter. & CPU & GPU-F & GPU-C & CPU & GPU-F & GPU-C \\\\\n"
    else:
        latex_table += "\\begin{tabular}{l|r|rr|rr}\n\\hline\n"
        latex_table += " & & \\multicolumn{2}{c|}{Latency (ms)} & \\multicolumn{2}{c}{Energy (mJ)} \\\\\n"
        latex_table += "Board & Iter. & CPU & GPU-F & CPU & GPU-F \\\\\n"

    latex_table += "\\hline\n"

    for table_row in table_rows:
        board_size_label = table_row['board_size']
        iterations = f"{table_row['iterations']:.0f}"
        cpu_lat = f"{table_row['cpu_lat_mean']:.1f}"
        gpu_fair_lat = f"{table_row['gpu_fair_lat_mean']:.1f}"
        cpu_eng = f"{table_row['cpu_eng_mean']:.1f}"
        gpu_fair_eng = f"{table_row['gpu_fair_eng_mean']:.1f}"

        if has_gpu_cap and 'gpu_cap_lat_mean' in table_row:
            gpu_cap_lat = f"{table_row['gpu_cap_lat_mean']:.1f}"
            gpu_cap_eng = f"{table_row['gpu_cap_eng_mean']:.1f}"
            latex_table += f"{board_size_label} & {iterations} & {cpu_lat} & {gpu_fair_lat} & {gpu_cap_lat} & {cpu_eng} & {gpu_fair_eng} & {gpu_cap_eng} \\\\\n"
        else:
            latex_table += f"{board_size_label} & {iterations} & {cpu_lat} & {gpu_fair_lat} & {cpu_eng} & {gpu_fair_eng} \\\\\n"

    latex_table += "\\hline\n\\end{tabular}\n\\end{table}\n"

    # CSV format
    csv_header = "board_size,iterations,cpu_lat_mean,cpu_lat_std,gpu_fair_lat_mean,gpu_fair_lat_std,"
    csv_header += "cpu_eng_mean,cpu_eng_std,gpu_fair_eng_mean,gpu_fair_eng_std,"
    csv_header += "cpu_eng_per_move_mean,cpu_eng_per_move_std,gpu_fair_eng_per_move_mean,gpu_fair_eng_per_move_std,"
    csv_header += "cpu_throughput_per_w_mean,cpu_throughput_per_w_std,gpu_fair_throughput_per_w_mean,gpu_fair_throughput_per_w_std"

    if has_gpu_cap:
        csv_header += ",gpu_cap_lat_mean,gpu_cap_lat_std,gpu_cap_eng_mean,gpu_cap_eng_std,"
        csv_header += "gpu_cap_eng_per_move_mean,gpu_cap_eng_per_move_std,gpu_cap_throughput_per_w_mean,gpu_cap_throughput_per_w_std"

    csv_header += "\n"

    csv_table = csv_header
    for table_row in table_rows:
        csv_line = f"{table_row['board_size']},{table_row['iterations']:.0f},"
        csv_line += f"{table_row['cpu_lat_mean']:.3f},{table_row['cpu_lat_std']:.3f},"
        csv_line += f"{table_row['gpu_fair_lat_mean']:.3f},{table_row['gpu_fair_lat_std']:.3f},"
        csv_line += f"{table_row['cpu_eng_mean']:.3f},{table_row['cpu_eng_std']:.3f},"
        csv_line += f"{table_row['gpu_fair_eng_mean']:.3f},{table_row['gpu_fair_eng_std']:.3f},"
        csv_line += f"{table_row['cpu_eng_per_move_mean']:.6f},{table_row['cpu_eng_per_move_std']:.6f},"
        csv_line += f"{table_row['gpu_fair_eng_per_move_mean']:.6f},{table_row['gpu_fair_eng_per_move_std']:.6f},"
        csv_line += f"{table_row['cpu_throughput_per_w_mean']:.3f},{table_row['cpu_throughput_per_w_std']:.3f},"
        csv_line += f"{table_row['gpu_fair_throughput_per_w_mean']:.3f},{table_row['gpu_fair_throughput_per_w_std']:.3f}"

        if has_gpu_cap and 'gpu_cap_lat_mean' in table_row:
            csv_line += f",{table_row['gpu_cap_lat_mean']:.3f},{table_row['gpu_cap_lat_std']:.3f},"
            csv_line += f"{table_row['gpu_cap_eng_mean']:.3f},{table_row['gpu_cap_eng_std']:.3f},"
            csv_line += f"{table_row['gpu_cap_eng_per_move_mean']:.6f},{table_row['gpu_cap_eng_per_move_std']:.6f},"
            csv_line += f"{table_row['gpu_cap_throughput_per_w_mean']:.3f},{table_row['gpu_cap_throughput_per_w_std']:.3f}"

        csv_table += csv_line + "\n"

    return {
        'markdown': markdown_table,
        'latex': latex_table,
        'csv': csv_table
    }


def main():
    argument_parser = argparse.ArgumentParser(description='Generate publication tables from MCTS benchmark results')
    argument_parser.add_argument('--cpu-file', type=str, help='Path to CPU benchmark CSV file')
    argument_parser.add_argument('--gpu-fair-file', type=str, help='Path to GPU fair mode CSV file')
    argument_parser.add_argument('--gpu-cap-file', type=str, help='Path to GPU capability mode CSV file (optional)')
    argument_parser.add_argument('--board-size', type=str, default='9x9', help='Board size for phase breakdown table (default: 9x9)')
    argument_parser.add_argument('--output-dir', type=str, default='tables', help='Output directory (default: tables)')
    argument_parser.add_argument('--auto-find', action='store_true', help='Automatically find latest CSV files in results/')

    arguments = argument_parser.parse_args()

    # Auto-find CSV files if requested
    if arguments.auto_find:
        results_dir = Path('results')
        if not results_dir.exists():
            print("❌ Error: results/ directory not found!")
            sys.exit(1)

        # Find files
        cpu_files = sorted(results_dir.glob('mcts_benchmark_*[!gpu]*.csv'), key=os.path.getmtime, reverse=True)
        gpu_fair_files = sorted(results_dir.glob('mcts_benchmark_gpu_fair_*.csv'), key=os.path.getmtime, reverse=True)
        gpu_cap_files = sorted(results_dir.glob('mcts_benchmark_gpu_capability_*.csv'), key=os.path.getmtime, reverse=True)

        if not cpu_files:
            print("❌ Error: No CPU benchmark files found in results/")
            sys.exit(1)
        if not gpu_fair_files:
            print("❌ Error: No GPU fair mode benchmark files found in results/")
            sys.exit(1)

        arguments.cpu_file = str(cpu_files[0])
        arguments.gpu_fair_file = str(gpu_fair_files[0])
        arguments.gpu_cap_file = str(gpu_cap_files[0]) if gpu_cap_files else None

        print(f"📂 Auto-detected files:")
        print(f"   CPU:      {arguments.cpu_file}")
        print(f"   GPU Fair: {arguments.gpu_fair_file}")
        if arguments.gpu_cap_file:
            print(f"   GPU Cap:  {arguments.gpu_cap_file}")

    # Validate required files
    if not arguments.cpu_file or not arguments.gpu_fair_file:
        print("❌ Error: --cpu-file and --gpu-fair-file are required (or use --auto-find)")
        argument_parser.print_help()
        sys.exit(1)

    # Load data
    print(f"\n📖 Loading data...")
    try:
        cpu_data = load_csv_file(arguments.cpu_file)
        gpu_fair_data = load_csv_file(arguments.gpu_fair_file)
        gpu_cap_data = load_csv_file(arguments.gpu_cap_file) if arguments.gpu_cap_file else None

        print(f"   CPU: {len(cpu_data)} trials")
        print(f"   GPU Fair: {len(gpu_fair_data)} trials")
        if gpu_cap_data:
            print(f"   GPU Capability: {len(gpu_cap_data)} trials")
    except Exception as error:
        print(f"❌ Error loading files: {error}")
        sys.exit(1)

    # Create output directory
    output_dir = Path(arguments.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Generate phase breakdown table
    print(f"\n📊 Generating phase breakdown table (board size: {arguments.board_size})...")
    phase_tables = generate_phase_breakdown_table(cpu_data, gpu_fair_data, arguments.board_size)

    # Save phase breakdown tables
    with open(output_dir / 'phase_breakdown.md', 'w') as output_file_handle:
        output_file_handle.write(phase_tables['markdown'])
    with open(output_dir / 'phase_breakdown.tex', 'w') as output_file_handle:
        output_file_handle.write(phase_tables['latex'])
    with open(output_dir / 'phase_breakdown.csv', 'w') as output_file_handle:
        output_file_handle.write(phase_tables['csv'])

    print(f"   ✅ Phase breakdown saved to {output_dir}/phase_breakdown.[md|tex|csv]")

    # Generate scalability table
    print(f"\n📊 Generating scalability analysis table...")
    scalability_tables = generate_scalability_table(cpu_data, gpu_fair_data, gpu_cap_data)

    # Save scalability tables
    with open(output_dir / 'scalability_analysis.md', 'w') as output_file_handle:
        output_file_handle.write(scalability_tables['markdown'])
    with open(output_dir / 'scalability_analysis.tex', 'w') as output_file_handle:
        output_file_handle.write(scalability_tables['latex'])
    with open(output_dir / 'scalability_analysis.csv', 'w') as output_file_handle:
        output_file_handle.write(scalability_tables['csv'])

    print(f"   ✅ Scalability analysis saved to {output_dir}/scalability_analysis.[md|tex|csv]")

    # Print preview
    print("\n" + "=" * 70)
    print("PREVIEW - Phase Breakdown Table")
    print("=" * 70)
    print(phase_tables['markdown'])

    print("\n" + "=" * 70)
    print("PREVIEW - Scalability Analysis Table")
    print("=" * 70)
    print(scalability_tables['markdown'])

    print("\n✅ Table generation complete!")
    print(f"📁 Output directory: {output_dir.absolute()}")


if __name__ == "__main__":
    main()
