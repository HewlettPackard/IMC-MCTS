#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Design Alternatives Ablation Study - Version 2 (Complete Energy Accounting)
============================================================================

Compares different implementation options for each module with complete energy breakdown:
1. Rollout: Software, Digital ASIC, FPGA, IMC
2. Selection: Sequential FSM, Hash Table, TCAM
3. Expansion: Software, Digital HW, Optimized

All with ADC/DAC, memory, and peripheral energy properly accounted for.
"""

import numpy as np
import pandas as pd
import json
import os
import sys
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../py_sst_cpp/components'))
from board_config import BoardSize, get_board_config


@dataclass
class AlternativeMetrics:
    """Metrics for a single implementation alternative"""
    module_name: str
    implementation: str
    board_size: int

    # Performance
    latency_per_op_ns: float

    # Energy breakdown
    compute_energy_pj: float
    adc_dac_energy_pj: float
    memory_energy_pj: float
    peripheral_energy_pj: float
    total_energy_pj: float

    # Hardware
    area_mm2: float
    power_mw: float

    # Comparison
    speedup_vs_baseline: float = 1.0
    energy_savings_vs_baseline: float = 1.0
    chosen: bool = False

    # Details
    num_memory_accesses: int = 0


# Energy constants (same as progressive buildup)
SRAM_ENERGY_PJ_PER_ACCESS = 200.0
ADC_ENERGY_PJ_8BIT = 5.0
DAC_ENERGY_PJ = 2.0
MAC_ENERGY_PJ_DIGITAL = 4.0
MAC_ENERGY_PJ_SOFTWARE = 75.0
IMC_OPERATION_ENERGY_PJ = 0.008


class RolloutAlternatives:
    """Compare different rollout implementations"""

    def __init__(self, board_size: int):
        self.board_size = board_size
        self.nn_input = board_size * board_size
        self.nn_hidden = 32
        self.nn_output = self.nn_input
        self.total_macs = self.nn_input * self.nn_hidden + self.nn_hidden * self.nn_output

    def software_arm_cpu(self) -> AlternativeMetrics:
        """ARM Cortex-M7 software implementation"""

        # Latency: 8 cycles/MAC @ 400 MHz
        latency_ns = self.total_macs * 8 * 2.5

        # Energy breakdown
        compute_energy = self.total_macs * MAC_ENERGY_PJ_SOFTWARE
        adc_dac_energy = 0.0
        num_mem_accesses = self.total_macs * 3  # Weights + activations
        memory_energy = num_mem_accesses * SRAM_ENERGY_PJ_PER_ACCESS
        peripheral_energy = compute_energy * 0.10  # Clock tree, control

        total_energy = compute_energy + adc_dac_energy + memory_energy + peripheral_energy

        return AlternativeMetrics(
            module_name="Rollout Unit",
            implementation="Software (ARM CPU)",
            board_size=self.board_size,
            latency_per_op_ns=latency_ns,
            compute_energy_pj=compute_energy,
            adc_dac_energy_pj=adc_dac_energy,
            memory_energy_pj=memory_energy,
            peripheral_energy_pj=peripheral_energy,
            total_energy_pj=total_energy,
            area_mm2=0.0,
            power_mw=400.0,
            speedup_vs_baseline=1.0,
            energy_savings_vs_baseline=1.0,
            chosen=False,
            num_memory_accesses=num_mem_accesses
        )

    def digital_asic(self) -> AlternativeMetrics:
        """Digital ASIC accelerator (Eyeriss-style)"""

        baseline = self.software_arm_cpu()

        # Latency: 1.5 cycles/MAC @ 500 MHz
        latency_ns = self.total_macs * 1.5 * 2.0

        # Energy breakdown
        compute_energy = self.total_macs * MAC_ENERGY_PJ_DIGITAL
        adc_dac_energy = 0.0
        num_mem_accesses = int(self.total_macs * 0.5)  # Better reuse
        memory_energy = num_mem_accesses * SRAM_ENERGY_PJ_PER_ACCESS
        peripheral_energy = compute_energy * 0.05

        total_energy = compute_energy + adc_dac_energy + memory_energy + peripheral_energy

        return AlternativeMetrics(
            module_name="Rollout Unit",
            implementation="Digital ASIC",
            board_size=self.board_size,
            latency_per_op_ns=latency_ns,
            compute_energy_pj=compute_energy,
            adc_dac_energy_pj=adc_dac_energy,
            memory_energy_pj=memory_energy,
            peripheral_energy_pj=peripheral_energy,
            total_energy_pj=total_energy,
            area_mm2=0.0012,
            power_mw=50.0,
            speedup_vs_baseline=baseline.latency_per_op_ns / latency_ns,
            energy_savings_vs_baseline=baseline.total_energy_pj / total_energy,
            chosen=False,
            num_memory_accesses=num_mem_accesses
        )

    def fpga(self) -> AlternativeMetrics:
        """FPGA implementation"""

        baseline = self.software_arm_cpu()

        # Latency: 3× slower than ASIC
        asic = self.digital_asic()
        latency_ns = asic.latency_per_op_ns * 3.0

        # Energy: 5× higher than ASIC
        compute_energy = asic.compute_energy_pj * 5.0
        adc_dac_energy = 0.0
        num_mem_accesses = asic.num_memory_accesses * 2
        memory_energy = num_mem_accesses * SRAM_ENERGY_PJ_PER_ACCESS
        peripheral_energy = compute_energy * 0.05

        total_energy = compute_energy + adc_dac_energy + memory_energy + peripheral_energy

        return AlternativeMetrics(
            module_name="Rollout Unit",
            implementation="FPGA",
            board_size=self.board_size,
            latency_per_op_ns=latency_ns,
            compute_energy_pj=compute_energy,
            adc_dac_energy_pj=adc_dac_energy,
            memory_energy_pj=memory_energy,
            peripheral_energy_pj=peripheral_energy,
            total_energy_pj=total_energy,
            area_mm2=0.0,  # External FPGA
            power_mw=120.0,
            speedup_vs_baseline=baseline.latency_per_op_ns / latency_ns,
            energy_savings_vs_baseline=baseline.total_energy_pj / total_energy,
            chosen=False,
            num_memory_accesses=num_mem_accesses
        )

    def imc_crossbar(self) -> AlternativeMetrics:
        """IMC crossbar (our design) - COMPLETE system from board_config"""

        baseline = self.software_arm_cpu()
        config = get_board_config(BoardSize(self.board_size))

        # Latency: Complete system with ADC/DAC conversion + analog MVM
        latency_ns = config.rollout_total_latency_ns  # 150 ns (realistic!)

        # Energy: Use complete system energy from board_config
        # This comes from real synthesis (automated + native 22nm ADC/DAC literature)
        total_energy = config.rollout_energy_pj_computed  # e.g., 9,650 pJ for 9x9

        # Breakdown for reporting (estimated from total)
        # Based on typical IMC system composition:
        # - ADC/DAC: ~70% (dominant in native 22nm literature models)
        # - Digital control: ~25%
        # - Crossbar analog: ~5%
        adc_dac_energy = total_energy * 0.70
        compute_energy = total_energy * 0.05
        peripheral_energy = total_energy * 0.25
        memory_energy = 0.0  # Weights in crossbar
        num_mem_accesses = self.nn_hidden + self.nn_output  # Activation reads

        return AlternativeMetrics(
            module_name="Rollout Unit",
            implementation="IMC Crossbar (chosen)",
            board_size=self.board_size,
            latency_per_op_ns=latency_ns,
            compute_energy_pj=compute_energy,
            adc_dac_energy_pj=adc_dac_energy,
            memory_energy_pj=memory_energy,
            peripheral_energy_pj=peripheral_energy,
            total_energy_pj=total_energy,
            area_mm2=config.rollout_total_area_mm2,
            power_mw=config.rollout_power_mw_computed,
            speedup_vs_baseline=baseline.latency_per_op_ns / latency_ns,
            energy_savings_vs_baseline=baseline.total_energy_pj / total_energy,
            chosen=True,
            num_memory_accesses=num_mem_accesses
        )


class SelectionAlternatives:
    """Compare different selection implementations"""

    def __init__(self, board_size: int):
        self.board_size = board_size
        self.num_transitions = 7  # Avg tree traversal depth

    def sequential_fsm(self) -> AlternativeMetrics:
        """Sequential FSM with comparisons"""

        # Latency: 20 ns per transition
        latency_ns = self.num_transitions * 20.0

        # Energy breakdown
        compute_energy = 30.0 * self.num_transitions  # Comparison logic
        adc_dac_energy = 0.0
        num_mem_accesses = 1  # Read node data
        memory_energy = num_mem_accesses * SRAM_ENERGY_PJ_PER_ACCESS
        peripheral_energy = 10.0 * self.num_transitions  # FSM control

        total_energy = compute_energy + adc_dac_energy + memory_energy + peripheral_energy

        return AlternativeMetrics(
            module_name="Selection Unit",
            implementation="Sequential FSM",
            board_size=self.board_size,
            latency_per_op_ns=latency_ns,
            compute_energy_pj=compute_energy,
            adc_dac_energy_pj=adc_dac_energy,
            memory_energy_pj=memory_energy,
            peripheral_energy_pj=peripheral_energy,
            total_energy_pj=total_energy,
            area_mm2=0.00002,
            power_mw=5.0,
            speedup_vs_baseline=1.0,
            energy_savings_vs_baseline=1.0,
            chosen=False,
            num_memory_accesses=num_mem_accesses
        )

    def hash_table(self) -> AlternativeMetrics:
        """Hash table lookup"""

        baseline = self.sequential_fsm()

        # Latency: 14 ns per transition (2 ns hash + 12 ns memory)
        latency_ns = self.num_transitions * 14.0

        # Energy breakdown
        compute_energy = 10.0 * self.num_transitions  # Hash computation
        adc_dac_energy = 0.0
        num_mem_accesses = 10  # Multiple memory probes for collisions
        memory_energy = num_mem_accesses * SRAM_ENERGY_PJ_PER_ACCESS
        peripheral_energy = 5.0 * self.num_transitions

        total_energy = compute_energy + adc_dac_energy + memory_energy + peripheral_energy

        return AlternativeMetrics(
            module_name="Selection Unit",
            implementation="Hash Table",
            board_size=self.board_size,
            latency_per_op_ns=latency_ns,
            compute_energy_pj=compute_energy,
            adc_dac_energy_pj=adc_dac_energy,
            memory_energy_pj=memory_energy,
            peripheral_energy_pj=peripheral_energy,
            total_energy_pj=total_energy,
            area_mm2=0.00050,
            power_mw=8.0,
            speedup_vs_baseline=baseline.latency_per_op_ns / latency_ns,
            energy_savings_vs_baseline=baseline.total_energy_pj / total_energy,
            chosen=False,
            num_memory_accesses=num_mem_accesses
        )

    def tcam(self) -> AlternativeMetrics:
        """TCAM parallel lookup (our design)"""

        baseline = self.sequential_fsm()
        config = get_board_config(BoardSize(self.board_size))

        # Latency: 1 ns per transition (parallel)
        latency_ns = self.num_transitions * 1.0

        # Energy breakdown
        compute_energy = 1.31 * self.num_transitions  # TCAM lookup
        adc_dac_energy = 0.0
        num_mem_accesses = 0  # No memory (TCAM is content-addressable)
        memory_energy = 0.0
        peripheral_energy = 0.5 * self.num_transitions  # Priority encoder

        total_energy = compute_energy + adc_dac_energy + memory_energy + peripheral_energy

        return AlternativeMetrics(
            module_name="Selection Unit",
            implementation="TCAM (chosen)",
            board_size=self.board_size,
            latency_per_op_ns=latency_ns,
            compute_energy_pj=compute_energy,
            adc_dac_energy_pj=adc_dac_energy,
            memory_energy_pj=memory_energy,
            peripheral_energy_pj=peripheral_energy,
            total_energy_pj=total_energy,
            area_mm2=config.tcam_area_mm2,
            power_mw=config.tcam_power_mw,
            speedup_vs_baseline=baseline.latency_per_op_ns / latency_ns,
            energy_savings_vs_baseline=baseline.total_energy_pj / total_energy,
            chosen=True,
            num_memory_accesses=num_mem_accesses
        )


class ExpansionAlternatives:
    """Compare different expansion implementations"""

    def __init__(self, board_size: int):
        self.board_size = board_size

    def software(self) -> AlternativeMetrics:
        """Software expansion on CPU"""

        # Latency: 500 ns for child node generation
        latency_ns = 500.0

        # Energy breakdown
        compute_energy = 200.0  # Bitboard operations
        adc_dac_energy = 0.0
        num_mem_accesses = 1  # Board state read
        memory_energy = num_mem_accesses * SRAM_ENERGY_PJ_PER_ACCESS
        peripheral_energy = 50.0

        total_energy = compute_energy + adc_dac_energy + memory_energy + peripheral_energy

        return AlternativeMetrics(
            module_name="Expansion Unit",
            implementation="Software",
            board_size=self.board_size,
            latency_per_op_ns=latency_ns,
            compute_energy_pj=compute_energy,
            adc_dac_energy_pj=adc_dac_energy,
            memory_energy_pj=memory_energy,
            peripheral_energy_pj=peripheral_energy,
            total_energy_pj=total_energy,
            area_mm2=0.0,
            power_mw=400.0,
            speedup_vs_baseline=1.0,
            energy_savings_vs_baseline=1.0,
            chosen=False,
            num_memory_accesses=num_mem_accesses
        )

    def digital_hardware(self) -> AlternativeMetrics:
        """Digital hardware expansion"""

        baseline = self.software()

        # Latency: 80 ns with combinational logic
        latency_ns = 80.0

        # Energy breakdown
        compute_energy = 30.0  # Logic gates
        adc_dac_energy = 0.0
        num_mem_accesses = 1
        memory_energy = num_mem_accesses * SRAM_ENERGY_PJ_PER_ACCESS
        peripheral_energy = 20.0

        total_energy = compute_energy + adc_dac_energy + memory_energy + peripheral_energy

        return AlternativeMetrics(
            module_name="Expansion Unit",
            implementation="Digital Hardware",
            board_size=self.board_size,
            latency_per_op_ns=latency_ns,
            compute_energy_pj=compute_energy,
            adc_dac_energy_pj=adc_dac_energy,
            memory_energy_pj=memory_energy,
            peripheral_energy_pj=peripheral_energy,
            total_energy_pj=total_energy,
            area_mm2=0.00030,
            power_mw=15.0,
            speedup_vs_baseline=baseline.latency_per_op_ns / latency_ns,
            energy_savings_vs_baseline=baseline.total_energy_pj / total_energy,
            chosen=False,
            num_memory_accesses=num_mem_accesses
        )

    def optimized(self) -> AlternativeMetrics:
        """Optimized expansion (our design)"""

        baseline = self.software()
        config = get_board_config(BoardSize(self.board_size))

        # Latency: From synthesis
        latency_ns = config.expansion_delay_ns

        # Energy breakdown
        expansion_energy = (config.expansion_power_mw * latency_ns) / 1e6

        compute_energy = expansion_energy * 0.3
        adc_dac_energy = 0.0
        num_mem_accesses = 2
        memory_energy = num_mem_accesses * SRAM_ENERGY_PJ_PER_ACCESS
        peripheral_energy = expansion_energy * 0.7

        total_energy = compute_energy + adc_dac_energy + memory_energy + peripheral_energy

        return AlternativeMetrics(
            module_name="Expansion Unit",
            implementation="Optimized (chosen)",
            board_size=self.board_size,
            latency_per_op_ns=latency_ns,
            compute_energy_pj=compute_energy,
            adc_dac_energy_pj=adc_dac_energy,
            memory_energy_pj=memory_energy,
            peripheral_energy_pj=peripheral_energy,
            total_energy_pj=total_energy,
            area_mm2=config.expansion_area_mm2,
            power_mw=config.expansion_power_mw,
            speedup_vs_baseline=baseline.latency_per_op_ns / latency_ns,
            energy_savings_vs_baseline=baseline.total_energy_pj / total_energy,
            chosen=True,
            num_memory_accesses=num_mem_accesses
        )


def run_design_alternatives_study_v2():
    """Run design alternatives study with complete energy accounting"""

    print("\n" + "="*80)
    print("DESIGN ALTERNATIVES ABLATION STUDY - V2 (COMPLETE ENERGY ACCOUNTING)")
    print("="*80)
    print("\nCompares different implementations for each module")
    print("Includes: ADC/DAC energy, memory energy (200 pJ/access), peripherals")
    print("Board sizes: 5×5, 9×9, 13×13 (boards with complete synthesis data)")
    print("="*80)

    board_sizes = [5, 9, 13]  # Only boards with complete automated synthesis + native 22nm ADC/DAC specs
    result_rows = []

    for board_size in board_sizes:
        print(f"\n{'='*80}")
        print(f"Board Size: {board_size}×{board_size}")
        print(f"{'='*80}\n")

        # Rollout alternatives
        rollout = RolloutAlternatives(board_size)
        rollout_alternatives = [
            rollout.software_arm_cpu(),
            rollout.digital_asic(),
            rollout.fpga(),
            rollout.imc_crossbar()
        ]

        print("ROLLOUT UNIT:")
        for alternative in rollout_alternatives:
            chosen_mark = "✓" if alternative.chosen else " "
            print(f"  [{chosen_mark}] {alternative.implementation:25s}: "
                  f"Speedup={alternative.speedup_vs_baseline:6.1f}×, "
                  f"Energy savings={alternative.energy_savings_vs_baseline:6.1f}×")
            print(f"      Energy: Compute={alternative.compute_energy_pj:.1f} pJ, "
                  f"ADC/DAC={alternative.adc_dac_energy_pj:.1f} pJ, "
                  f"Memory={alternative.memory_energy_pj:.1f} pJ, "
                  f"Total={alternative.total_energy_pj:.1f} pJ")
            result_rows.append(asdict(alternative))

        # Selection alternatives
        print("\nSELECTION UNIT:")
        selection = SelectionAlternatives(board_size)
        selection_alternatives = [
            selection.sequential_fsm(),
            selection.hash_table(),
            selection.tcam()
        ]

        for alternative in selection_alternatives:
            chosen_mark = "✓" if alternative.chosen else " "
            print(f"  [{chosen_mark}] {alternative.implementation:25s}: "
                  f"Speedup={alternative.speedup_vs_baseline:6.1f}×, "
                  f"Energy savings={alternative.energy_savings_vs_baseline:6.1f}×")
            print(f"      Energy: Compute={alternative.compute_energy_pj:.1f} pJ, "
                  f"Memory={alternative.memory_energy_pj:.1f} pJ, "
                  f"Total={alternative.total_energy_pj:.1f} pJ")
            result_rows.append(asdict(alternative))

        # Expansion alternatives
        print("\nEXPANSION UNIT:")
        expansion = ExpansionAlternatives(board_size)
        expansion_alternatives = [
            expansion.software(),
            expansion.digital_hardware(),
            expansion.optimized()
        ]

        for alternative in expansion_alternatives:
            chosen_mark = "✓" if alternative.chosen else " "
            print(f"  [{chosen_mark}] {alternative.implementation:25s}: "
                  f"Speedup={alternative.speedup_vs_baseline:6.1f}×, "
                  f"Energy savings={alternative.energy_savings_vs_baseline:6.1f}×")
            print(f"      Energy: Compute={alternative.compute_energy_pj:.1f} pJ, "
                  f"Memory={alternative.memory_energy_pj:.1f} pJ, "
                  f"Total={alternative.total_energy_pj:.1f} pJ")
            result_rows.append(asdict(alternative))

    # Save results
    os.makedirs('../../experiment_results', exist_ok=True)

    results_df = pd.DataFrame(result_rows)
    csv_file = '../../experiment_results/ablation_design_alternatives_v2.csv'
    results_df.to_csv(csv_file, index=False)
    print(f"\n{'='*80}")
    print(f"✅ Results saved to: {csv_file}")

    json_file = '../../experiment_results/ablation_design_alternatives_v2.json'
    with open(json_file, 'w') as f:
        json.dump(result_rows, f, indent=2)
    print(f"✅ Detailed results saved to: {json_file}")
    print(f"{'='*80}\n")

    # Print key comparison for 9×9
    results_9x9 = results_df[results_df['board_size'] == 9]

    print(f"KEY COMPARISONS (9×9 board):")
    print("\nRollout: IMC vs Software")
    imc = results_9x9[(results_9x9['module_name'] == 'Rollout Unit') &
                      (results_9x9['implementation'] == 'IMC Crossbar (chosen)')].iloc[0]
    sw = results_9x9[(results_9x9['module_name'] == 'Rollout Unit') &
                     (results_9x9['implementation'] == 'Software (ARM CPU)')].iloc[0]
    print(f"  Speedup: {imc['speedup_vs_baseline']:.1f}×")
    print(f"  Energy savings: {imc['energy_savings_vs_baseline']:.1f}×")
    print(f"  IMC total energy: {imc['total_energy_pj']:.1f} pJ (ADC/DAC: {imc['adc_dac_energy_pj']:.1f} pJ)")
    print(f"  Software total energy: {sw['total_energy_pj']:.1f} pJ")

    return results_df


if __name__ == "__main__":
    df = run_design_alternatives_study_v2()
    print("✅ Design alternatives ablation study (V2) complete!")
