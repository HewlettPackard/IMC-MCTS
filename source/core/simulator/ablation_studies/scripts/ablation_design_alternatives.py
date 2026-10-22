#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Design Alternatives Ablation Study
====================================

Compares different implementation choices for each module:
1. Rollout Unit: Software vs Digital ASIC vs IMC Crossbar
2. Selection Unit: Sequential FSM vs Hash Table vs TCAM
3. Expansion Unit: Software vs Digital vs Hardware-optimized

Justifies why specific implementations were chosen through
head-to-head quantitative comparisons.

Data sources:
- Software: ARM Cortex-M7 benchmarks
- Digital ASIC: Eyeriss/DianNao literature
- IMC/TCAM: board_config.py actual synthesis data
- FPGA: Literature values (Xilinx/Intel FPGA papers)
"""

import numpy as np
import pandas as pd
import json
import os
import sys
from dataclasses import dataclass, asdict
from typing import Dict, List

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../py_sst_cpp/components'))
from board_config import BoardSize, get_board_config


@dataclass
class AlternativeMetrics:
    """Metrics for a specific implementation alternative"""
    module_name: str
    implementation: str
    board_size: int

    # Per-operation metrics
    latency_per_op_ns: float
    energy_per_op_pj: float

    # Hardware metrics
    area_mm2: float
    power_mw: float

    # Relative metrics (vs baseline for this module)
    speedup_vs_baseline: float = 1.0
    energy_efficiency_vs_baseline: float = 1.0

    # Justification
    notes: str = ""
    chosen: bool = False


# ============================================================================
# ROLLOUT UNIT ALTERNATIVES
# ============================================================================

class RolloutSoftware:
    """
    Rollout Alternative 1: Software Neural Network (Baseline)
    ARM Cortex-M7 @ 400 MHz running NN inference

    Data source: CMSIS-NN benchmarks
    """

    def __init__(self, board_size: int):
        self.board_size = board_size
        self.name = "Software (ARM CPU)"

        nn_input = board_size * board_size
        nn_hidden = 32
        self.macs = (nn_input * nn_hidden + nn_hidden * nn_input)

        # Software: 8 cycles/MAC @ 400 MHz (2.5 ns/cycle)
        self.latency_per_op_ns = self.macs * 8 * 2.5

        # Energy: 75 pJ/MAC + memory access (200 pJ × 2 reads)
        self.energy_per_op_pj = self.macs * (75.0 + 2 * 200.0)

        self.area_mm2 = 0.0  # External CPU
        self.power_mw = 400.0

    def get_metrics(self) -> AlternativeMetrics:
        return AlternativeMetrics(
            module_name="Rollout Unit",
            implementation=self.name,
            board_size=self.board_size,
            latency_per_op_ns=self.latency_per_op_ns,
            energy_per_op_pj=self.energy_per_op_pj,
            area_mm2=self.area_mm2,
            power_mw=self.power_mw,
            speedup_vs_baseline=1.0,
            energy_efficiency_vs_baseline=1.0,
            notes="Baseline - Sequential MAC operations",
            chosen=False
        )


class RolloutDigitalASIC:
    """
    Rollout Alternative 2: Digital ASIC NN Accelerator
    Systolic array or similar @ 500 MHz

    Data source: Eyeriss (ISCA 2016) scaled to 22nm
    - Original: 8.3 pJ/MAC @ 65nm
    - Scaled: ~4 pJ/MAC @ 22nm
    """

    def __init__(self, board_size: int, baseline_metrics: AlternativeMetrics):
        self.board_size = board_size
        self.name = "Digital ASIC"
        self.baseline = baseline_metrics

        nn_input = board_size * board_size
        nn_hidden = 32
        self.macs = (nn_input * nn_hidden + nn_hidden * nn_input)

        # Digital accelerator: 1.5 cycles/MAC @ 500 MHz (2 ns/cycle)
        # With pipelining and parallelism
        self.latency_per_op_ns = self.macs * 1.5 * 2.0

        # Energy: Based on Eyeriss @ 22nm scaling
        # Eyeriss: 8.3 pJ/MAC @ 65nm → ~4 pJ/MAC @ 22nm
        self.energy_per_op_pj = self.macs * 4.0

        # Area: Small systolic array
        # Scaled from Eyeriss (12.25 mm² @ 65nm for 168 PEs)
        self.area_mm2 = 0.0012

        self.power_mw = 50.0

    def get_metrics(self) -> AlternativeMetrics:
        speedup = self.baseline.latency_per_op_ns / self.latency_per_op_ns
        energy_eff = self.baseline.energy_per_op_pj / self.energy_per_op_pj

        return AlternativeMetrics(
            module_name="Rollout Unit",
            implementation=self.name,
            board_size=self.board_size,
            latency_per_op_ns=self.latency_per_op_ns,
            energy_per_op_pj=self.energy_per_op_pj,
            area_mm2=self.area_mm2,
            power_mw=self.power_mw,
            speedup_vs_baseline=speedup,
            energy_efficiency_vs_baseline=energy_eff,
            notes=f"{speedup:.1f}× faster but still digital (4 pJ/MAC)",
            chosen=False
        )


class RolloutFPGA:
    """
    Rollout Alternative 3: FPGA NN Accelerator
    Xilinx/Intel FPGA with DSP blocks

    Data source: FPGA NN accelerator literature
    - Latency: 2-3× slower than ASIC
    - Energy: 5-10× worse than ASIC
    """

    def __init__(self, board_size: int, baseline_metrics: AlternativeMetrics):
        self.board_size = board_size
        self.name = "FPGA"
        self.baseline = baseline_metrics

        nn_input = board_size * board_size
        nn_hidden = 32
        self.macs = (nn_input * nn_hidden + nn_hidden * nn_input)

        # FPGA: ~3× slower than ASIC
        asic_latency = self.macs * 1.5 * 2.0
        self.latency_per_op_ns = asic_latency * 3.0

        # Energy: ~5× worse than ASIC (routing overhead)
        asic_energy = self.macs * 4.0
        self.energy_per_op_pj = asic_energy * 5.0

        # Area: Not directly comparable (programmable fabric)
        self.area_mm2 = 0.0

        self.power_mw = 250.0  # Higher due to routing

    def get_metrics(self) -> AlternativeMetrics:
        speedup = self.baseline.latency_per_op_ns / self.latency_per_op_ns
        energy_eff = self.baseline.energy_per_op_pj / self.energy_per_op_pj

        return AlternativeMetrics(
            module_name="Rollout Unit",
            implementation=self.name,
            board_size=self.board_size,
            latency_per_op_ns=self.latency_per_op_ns,
            energy_per_op_pj=self.energy_per_op_pj,
            area_mm2=self.area_mm2,
            power_mw=self.power_mw,
            speedup_vs_baseline=speedup,
            energy_efficiency_vs_baseline=energy_eff,
            notes="Flexible but higher energy/latency",
            chosen=False
        )


class RolloutIMC:
    """
    Rollout Alternative 4: IMC Crossbar (Chosen)
    Analog In-Memory Computing with ReRAM crossbar

    Data source: board_config.py + CIM literature
    - 0.008 pJ per operation
    - 5 ns latency (1-cycle analog MVM)
    """

    def __init__(self, board_size: int, baseline_metrics: AlternativeMetrics):
        self.board_size = board_size
        self.name = "IMC Crossbar (chosen)"
        self.baseline = baseline_metrics

        config = get_board_config(BoardSize(board_size))

        nn_input = board_size * board_size
        nn_hidden = 32
        self.macs = (nn_input * nn_hidden + nn_hidden * nn_input)

        # IMC: Analog MVM in 5 ns (crossbar operation)
        self.latency_per_op_ns = config.crossbar_delay_ns  # 5 ns

        # Energy: Extremely efficient analog computation
        # 0.008 pJ per operation (from CIM literature)
        self.energy_per_op_pj = self.macs * 0.008

        self.area_mm2 = config.rollout_total_area_mm2
        self.power_mw = config.rollout_power_mw_computed

    def get_metrics(self) -> AlternativeMetrics:
        speedup = self.baseline.latency_per_op_ns / self.latency_per_op_ns
        energy_eff = self.baseline.energy_per_op_pj / self.energy_per_op_pj

        return AlternativeMetrics(
            module_name="Rollout Unit",
            implementation=self.name,
            board_size=self.board_size,
            latency_per_op_ns=self.latency_per_op_ns,
            energy_per_op_pj=self.energy_per_op_pj,
            area_mm2=self.area_mm2,
            power_mw=self.power_mw,
            speedup_vs_baseline=speedup,
            energy_efficiency_vs_baseline=energy_eff,
            notes=f"{speedup:.0f}× speedup, {energy_eff:.0f}× energy savings ✓",
            chosen=True
        )


# ============================================================================
# SELECTION UNIT ALTERNATIVES
# ============================================================================

class SelectionSequential:
    """
    Selection Alternative 1: Sequential FSM (Baseline)
    Traditional state machine with sequential comparisons

    Data source: Analytical model for digital FSM @ 22nm
    """

    def __init__(self, board_size: int):
        self.board_size = board_size
        self.name = "Sequential FSM"

        # Sequential state comparison: ~5 comparisons average
        # @ 500 MHz (2 ns/cycle)
        cycles_per_transition = 10  # Sequential logic
        self.latency_per_op_ns = cycles_per_transition * 2.0  # 20 ns

        # Energy: Register ops + comparators + branch logic
        self.energy_per_op_pj = 50.0

        # Area: Simple FSM
        self.area_mm2 = 0.00002  # 20 μm²

        self.power_mw = 5.0

    def get_metrics(self) -> AlternativeMetrics:
        return AlternativeMetrics(
            module_name="Selection Unit",
            implementation=self.name,
            board_size=self.board_size,
            latency_per_op_ns=self.latency_per_op_ns,
            energy_per_op_pj=self.energy_per_op_pj,
            area_mm2=self.area_mm2,
            power_mw=self.power_mw,
            speedup_vs_baseline=1.0,
            energy_efficiency_vs_baseline=1.0,
            notes="Baseline - Sequential state comparison",
            chosen=False
        )


class SelectionHashTable:
    """
    Selection Alternative 2: Hash Table Lookup
    Hardware hash table for tree node lookup

    Data source: Analytical model based on SRAM + hash logic
    """

    def __init__(self, board_size: int, baseline_metrics: AlternativeMetrics):
        self.board_size = board_size
        self.name = "Hash Table"
        self.baseline = baseline_metrics

        # Hash computation + SRAM access
        # Hash: 3-4 cycles, SRAM: 2-3 cycles
        cycles = 7
        self.latency_per_op_ns = cycles * 2.0  # 14 ns @ 500 MHz

        # Energy: Hash logic + SRAM read
        # Hash: ~20 pJ, SRAM read: ~200 pJ
        self.energy_per_op_pj = 220.0

        # Area: Hash table SRAM + logic
        self.area_mm2 = 0.0005  # Larger due to SRAM

        self.power_mw = 15.0

    def get_metrics(self) -> AlternativeMetrics:
        speedup = self.baseline.latency_per_op_ns / self.latency_per_op_ns
        energy_eff = self.baseline.energy_per_op_pj / self.energy_per_op_pj

        return AlternativeMetrics(
            module_name="Selection Unit",
            implementation=self.name,
            board_size=self.board_size,
            latency_per_op_ns=self.latency_per_op_ns,
            energy_per_op_pj=self.energy_per_op_pj,
            area_mm2=self.area_mm2,
            power_mw=self.power_mw,
            speedup_vs_baseline=speedup,
            energy_efficiency_vs_baseline=energy_eff,
            notes=f"{speedup:.1f}× faster but higher energy/area",
            chosen=False
        )


class SelectionTCAM:
    """
    Selection Alternative 3: TCAM-based Selection (Chosen)
    Parallel content-addressable memory lookup

    Data source: board_config.py TCAM specs
    """

    def __init__(self, board_size: int, baseline_metrics: AlternativeMetrics):
        self.board_size = board_size
        self.name = "TCAM (chosen)"
        self.baseline = baseline_metrics

        config = get_board_config(BoardSize(board_size))

        # TCAM: Parallel lookup in 1 cycle
        self.latency_per_op_ns = config.fsm_transition_delay_ns  # 1 ns

        # Energy: Parallel compare across all rows
        # From board_config: 1.31 pJ per transition
        self.energy_per_op_pj = 1.31

        self.area_mm2 = config.tcam_area_mm2  # 70.4 μm²

        self.power_mw = config.tcam_power_mw

    def get_metrics(self) -> AlternativeMetrics:
        speedup = self.baseline.latency_per_op_ns / self.latency_per_op_ns
        energy_eff = self.baseline.energy_per_op_pj / self.energy_per_op_pj

        return AlternativeMetrics(
            module_name="Selection Unit",
            implementation=self.name,
            board_size=self.board_size,
            latency_per_op_ns=self.latency_per_op_ns,
            energy_per_op_pj=self.energy_per_op_pj,
            area_mm2=self.area_mm2,
            power_mw=self.power_mw,
            speedup_vs_baseline=speedup,
            energy_efficiency_vs_baseline=energy_eff,
            notes=f"{speedup:.0f}× faster, small area overhead ✓",
            chosen=True
        )


# ============================================================================
# EXPANSION UNIT ALTERNATIVES
# ============================================================================

class ExpansionSoftware:
    """
    Expansion Alternative 1: Software (Baseline)
    CPU-based node creation and initialization
    """

    def __init__(self, board_size: int):
        self.board_size = board_size
        self.name = "Software"

        # Node creation: allocate + initialize
        # ~200 cycles @ 400 MHz (2.5 ns/cycle)
        cycles = 200
        self.latency_per_op_ns = cycles * 2.5  # 500 ns

        # Energy: Memory allocation + writes
        self.energy_per_op_pj = 400.0

        self.area_mm2 = 0.0  # External CPU
        self.power_mw = 100.0

    def get_metrics(self) -> AlternativeMetrics:
        return AlternativeMetrics(
            module_name="Expansion Unit",
            implementation=self.name,
            board_size=self.board_size,
            latency_per_op_ns=self.latency_per_op_ns,
            energy_per_op_pj=self.energy_per_op_pj,
            area_mm2=self.area_mm2,
            power_mw=self.power_mw,
            speedup_vs_baseline=1.0,
            energy_efficiency_vs_baseline=1.0,
            notes="Baseline - Software allocation",
            chosen=False
        )


class ExpansionDigital:
    """
    Expansion Alternative 2: Digital Hardware
    Simple hardware node allocator
    """

    def __init__(self, board_size: int, baseline_metrics: AlternativeMetrics):
        self.board_size = board_size
        self.name = "Digital Hardware"
        self.baseline = baseline_metrics

        # Hardware: Parallel initialization
        # ~40 cycles @ 500 MHz (2 ns/cycle)
        cycles = 40
        self.latency_per_op_ns = cycles * 2.0  # 80 ns

        # Energy: Register operations + control logic
        self.energy_per_op_pj = 80.0

        # Area: Control logic + buffers
        self.area_mm2 = 0.0003

        self.power_mw = 10.0

    def get_metrics(self) -> AlternativeMetrics:
        speedup = self.baseline.latency_per_op_ns / self.latency_per_op_ns
        energy_eff = self.baseline.energy_per_op_pj / self.energy_per_op_pj

        return AlternativeMetrics(
            module_name="Expansion Unit",
            implementation=self.name,
            board_size=self.board_size,
            latency_per_op_ns=self.latency_per_op_ns,
            energy_per_op_pj=self.energy_per_op_pj,
            area_mm2=self.area_mm2,
            power_mw=self.power_mw,
            speedup_vs_baseline=speedup,
            energy_efficiency_vs_baseline=energy_eff,
            notes=f"{speedup:.1f}× faster but not optimized",
            chosen=False
        )


class ExpansionOptimized:
    """
    Expansion Alternative 3: Optimized Hardware (Chosen)
    Specialized expansion unit from board_config

    Data source: board_config.py expansion specs
    """

    def __init__(self, board_size: int, baseline_metrics: AlternativeMetrics):
        self.board_size = board_size
        self.name = "Optimized (chosen)"
        self.baseline = baseline_metrics

        config = get_board_config(BoardSize(board_size))

        # Highly optimized parallel expansion
        self.latency_per_op_ns = config.expansion_delay_ns  # 2 ns

        # Energy from board_config (power × time)
        self.energy_per_op_pj = (config.expansion_power_mw * self.latency_per_op_ns) / 1e6

        self.area_mm2 = config.expansion_area_mm2
        self.power_mw = config.expansion_power_mw

    def get_metrics(self) -> AlternativeMetrics:
        speedup = self.baseline.latency_per_op_ns / self.latency_per_op_ns
        energy_eff = self.baseline.energy_per_op_pj / self.energy_per_op_pj

        return AlternativeMetrics(
            module_name="Expansion Unit",
            implementation=self.name,
            board_size=self.board_size,
            latency_per_op_ns=self.latency_per_op_ns,
            energy_per_op_pj=self.energy_per_op_pj,
            area_mm2=self.area_mm2,
            power_mw=self.power_mw,
            speedup_vs_baseline=speedup,
            energy_efficiency_vs_baseline=energy_eff,
            notes=f"{speedup:.0f}× speedup with optimization ✓",
            chosen=True
        )


def run_design_alternatives_study():
    """Run design alternatives comparison study"""

    print("\n" + "="*80)
    print("DESIGN ALTERNATIVES ABLATION STUDY")
    print("="*80)
    print("\nComparing implementation choices for each module")
    print("Justifies design decisions through quantitative comparisons")
    print("\nBoard sizes: 3×3, 5×5, 9×9, 13×13")
    print("="*80)

    board_sizes = [3, 5, 9, 13]
    result_rows = []

    for board_size in board_sizes:
        print(f"\n{'='*80}")
        print(f"Board Size: {board_size}×{board_size}")
        print(f"{'='*80}\n")

        # ===== ROLLOUT ALTERNATIVES =====
        print("ROLLOUT UNIT ALTERNATIVES:")
        print("-" * 80)

        rollout_sw = RolloutSoftware(board_size)
        rollout_sw_metrics = rollout_sw.get_metrics()

        rollout_alternatives = [
            rollout_sw,
            RolloutDigitalASIC(board_size, rollout_sw_metrics),
            RolloutFPGA(board_size, rollout_sw_metrics),
            RolloutIMC(board_size, rollout_sw_metrics)
        ]

        for alternative in rollout_alternatives:
            alternative_metrics = alternative.get_metrics()
            chosen_mark = "✓" if alternative_metrics.chosen else " "
            print(f"[{chosen_mark}] {alternative_metrics.implementation:20s}: "
                  f"{alternative_metrics.speedup_vs_baseline:6.1f}× speedup | "
                  f"{alternative_metrics.energy_efficiency_vs_baseline:6.1f}× energy | "
                  f"{alternative_metrics.latency_per_op_ns:7.1f} ns | "
                  f"{alternative_metrics.energy_per_op_pj:8.1f} pJ")
            print(f"    {alternative_metrics.notes}")
            result_rows.append(asdict(alternative_metrics))

        # ===== SELECTION ALTERNATIVES =====
        print("\n" + "-" * 80)
        print("SELECTION UNIT ALTERNATIVES:")
        print("-" * 80)

        sel_seq = SelectionSequential(board_size)
        sel_seq_metrics = sel_seq.get_metrics()

        selection_alternatives = [
            sel_seq,
            SelectionHashTable(board_size, sel_seq_metrics),
            SelectionTCAM(board_size, sel_seq_metrics)
        ]

        for alternative in selection_alternatives:
            alternative_metrics = alternative.get_metrics()
            chosen_mark = "✓" if alternative_metrics.chosen else " "
            print(f"[{chosen_mark}] {alternative_metrics.implementation:20s}: "
                  f"{alternative_metrics.speedup_vs_baseline:6.1f}× speedup | "
                  f"{alternative_metrics.energy_efficiency_vs_baseline:6.1f}× energy | "
                  f"{alternative_metrics.latency_per_op_ns:7.1f} ns | "
                  f"{alternative_metrics.energy_per_op_pj:8.1f} pJ")
            print(f"    {alternative_metrics.notes}")
            result_rows.append(asdict(alternative_metrics))

        # ===== EXPANSION ALTERNATIVES =====
        print("\n" + "-" * 80)
        print("EXPANSION UNIT ALTERNATIVES:")
        print("-" * 80)

        exp_sw = ExpansionSoftware(board_size)
        exp_sw_metrics = exp_sw.get_metrics()

        expansion_alternatives = [
            exp_sw,
            ExpansionDigital(board_size, exp_sw_metrics),
            ExpansionOptimized(board_size, exp_sw_metrics)
        ]

        for alternative in expansion_alternatives:
            alternative_metrics = alternative.get_metrics()
            chosen_mark = "✓" if alternative_metrics.chosen else " "
            print(f"[{chosen_mark}] {alternative_metrics.implementation:20s}: "
                  f"{alternative_metrics.speedup_vs_baseline:6.1f}× speedup | "
                  f"{alternative_metrics.energy_efficiency_vs_baseline:6.1f}× energy | "
                  f"{alternative_metrics.latency_per_op_ns:7.1f} ns | "
                  f"{alternative_metrics.energy_per_op_pj:8.1f} pJ")
            print(f"    {alternative_metrics.notes}")
            result_rows.append(asdict(alternative_metrics))

        print()

    # Save results
    os.makedirs('../../experiment_results', exist_ok=True)

    # CSV
    results_df = pd.DataFrame(result_rows)
    csv_file = '../../experiment_results/ablation_design_alternatives.csv'
    results_df.to_csv(csv_file, index=False)
    print(f"{'='*80}")
    print(f"✅ Results saved to: {csv_file}")

    # JSON
    json_file = '../../experiment_results/ablation_design_alternatives.json'
    with open(json_file, 'w') as f:
        json.dump(result_rows, f, indent=2)
    print(f"✅ Detailed results saved to: {json_file}")
    print(f"{'='*80}\n")

    return results_df


if __name__ == "__main__":
    df = run_design_alternatives_study()
    print("✅ Design alternatives ablation study complete!")
