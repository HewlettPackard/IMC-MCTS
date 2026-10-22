#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Crossbar Hardware Model with Literature-Calibrated Constants
============================================================

Area, power, and timing modeling for memristor crossbars using a
literature-calibrated 256×256, 22nm baseline. The public literature link will
be added in a later release.

Based on: MCTS_IMC2/02_HARDWARE_DESIGN/core/components/crossbar_core.py
"""

import numpy as np
from typing import Dict, Any


class CrossbarHardwareModel:
    """
    Crossbar hardware model using literature-calibrated constants.

    Calibration baseline (256×256 at 22nm; literature link forthcoming):
    - Cell size: 0.0424 µm²
    - Cell resistance: 100 MΩ
    - Read voltage: 0.4V
    - Read energy: 47.41 pJ
    - Write energy: 3159.3 pJ
    - Array power: 6.2 mW
    """

    def __init__(self):
        # Literature-calibrated 256×256 crossbar baseline at 22nm.
        self.supert_specs = {
            'base_size': 256,
            'cell_size_um2': 0.0424,
            'cell_resolution_bits': 4,
            'weight_resolution_bits': 8,
            'technology_nm': 22,
            'cell_on_resistance_mohm': 100.0,
            'read_voltage_v': 0.4,
            'cell_capacitance_ff': 0.21875,
            'wire_cap_per_cell_ff': 0.06434768838116875,
            'cell_on_read_current_na': 4,
            'column_read_current_ua': 1.024,
            'array_cv2_energy_pj': 20.779460918438076,
            'array_iv_energy_pj': 26.6338304,
            'array_total_energy_pj': 47.41329131843808,
            'xbar_energy_pj': 3159.3308913184383,
            'xbar_power_mw': 6.198935710182502,
            'always_on_power_mw': 3.0455908568491687,
            'scaling_power_mw': 4.097063253333332
        }

        # Technology node scaling factors (area and power scale differently)
        self.tech_node_scaling = {
            '65nm': {'area': 1.0, 'power': 1.0},
            '45nm': {'area': 0.69, 'power': 0.75},
            '28nm': {'area': 0.43, 'power': 0.55},
            '22nm': {'area': 0.34, 'power': 0.45},
            '16nm': {'area': 0.25, 'power': 0.35}
        }

    def estimate_crossbar(self, rows: int, cols: int, tech_node: str = '28nm') -> Dict[str, Any]:
        """
        Estimate crossbar array specifications

        Args:
            rows: Number of rows (input dimension)
            cols: Number of columns (output dimension)
            tech_node: Technology node (default 28nm to match synthesis data)

        Returns:
            Dictionary with area, power, timing, and energy specs
        """
        # Calculate number of memristor devices
        total_devices = rows * cols

        # Get technology scaling factors
        technology_scaling = self.tech_node_scaling.get(tech_node, self.tech_node_scaling['28nm'])
        area_scaling = technology_scaling['area']
        power_scaling = technology_scaling['power']

        # Calculate cell area
        cell_area_um2 = self.supert_specs['cell_size_um2'] * area_scaling

        # Calculate array overhead (routing, DAC, ADC, control)
        # Smaller arrays have proportionally higher overhead
        base_overhead = 1.5  # 50% base overhead for logic
        routing_overhead = 1.0 + 0.1 * np.sqrt(total_devices / 1000.0)  # Routing scales with sqrt
        dac_adc_overhead = 1.0 + 0.05 * (rows / 100.0)  # DAC/ADC scales with inputs
        overhead_factor = base_overhead * routing_overhead * dac_adc_overhead

        # Calculate total crossbar area
        array_area_um2 = cell_area_um2 * total_devices * overhead_factor
        array_area_mm2 = array_area_um2 / 1e6

        # Minimum area threshold (peripheral circuits)
        min_area_mm2 = 0.0001  # 0.1 mm² minimum
        if array_area_mm2 < min_area_mm2:
            array_area_mm2 = min_area_mm2

        # Calculate power consumption
        power_mw = self._calculate_power(
            area_mm2=array_area_mm2,
            total_devices=total_devices,
            rows=rows,
            cols=cols,
            power_scaling=power_scaling
        )

        # Calculate energy per operation
        energy_pj = self._calculate_energy(
            total_devices=total_devices,
            power_scaling=power_scaling
        )

        # Calculate timing (1-2 cycles for analog MVM)
        # Analog crossbar is FAST - single cycle for matrix-vector multiply
        read_latency_cycles = 1  # Analog parallel computation
        read_latency_ns = 2.5    # Assuming 400MHz clock (2.5ns period)
        write_latency_ms = 64    # Literature-calibrated write latency

        # Calculate frequency
        frequency_mhz = 1000 / read_latency_ns  # 400 MHz

        hardware_specs = {
            # Area
            'area_mm2': array_area_mm2,
            'area_um2': array_area_um2,
            'cell_size_um2': cell_area_um2,

            # Power
            'power_mw': power_mw,
            'static_power_mw': power_mw * 0.3,  # 30% static
            'dynamic_power_mw': power_mw * 0.7,  # 70% dynamic

            # Energy
            'read_energy_pj': energy_pj['read'],
            'write_energy_pj': energy_pj['write'],

            # Timing
            'read_latency_cycles': read_latency_cycles,
            'read_latency_ns': read_latency_ns,
            'write_latency_ms': write_latency_ms,
            'frequency_mhz': frequency_mhz,

            # Architecture
            'rows': rows,
            'cols': cols,
            'total_devices': total_devices,
            'technology': tech_node,
            'overhead_factor': overhead_factor,
            'tech_scaling': technology_scaling,

            # Specifications
            'cell_resolution_bits': self.supert_specs['cell_resolution_bits'],
            'weight_resolution_bits': self.supert_specs['weight_resolution_bits'],
            'read_voltage_v': self.supert_specs['read_voltage_v']
        }

        return hardware_specs

    def _calculate_power(self, area_mm2: float, total_devices: int, rows: int,
                        cols: int, power_scaling: float) -> float:
        """
        Calculate crossbar power consumption

        Power has three components:
        1. Static leakage power (proportional to devices)
        2. Dynamic switching power (proportional to operations)
        3. Peripheral power (DAC, ADC, control)
        """
        # Static power density (mW/mm²) - leakage current
        static_power_density = 10.0 * power_scaling
        static_power_mw = static_power_density * area_mm2

        # Dynamic power density (mW/mm²) - switching energy
        # Activity factor = 0.1 (10% of devices switching per cycle)
        dynamic_power_density = 50.0 * power_scaling
        activity_factor = 0.1
        dynamic_power_mw = dynamic_power_density * area_mm2 * activity_factor

        # Peripheral power (DAC, ADC, control circuits)
        # Scales with number of inputs (DAC) and outputs (ADC)
        dac_power_mw = 0.05 * rows * power_scaling  # 50µW per DAC
        adc_power_mw = 0.10 * cols * power_scaling  # 100µW per ADC
        control_power_mw = 0.5 * power_scaling      # 0.5mW control logic

        total_power_mw = static_power_mw + dynamic_power_mw + dac_power_mw + adc_power_mw + control_power_mw

        return total_power_mw

    def _calculate_energy(self, total_devices: int, power_scaling: float) -> Dict[str, float]:
        """
        Calculate energy per operation (read/write)

        Based on the literature-calibrated baseline, scaled to actual size.
        """
        # Energy scaling from the 256×256 baseline (65,536 devices).
        baseline_devices = self.supert_specs['base_size'] ** 2
        energy_scale = total_devices / baseline_devices

        # Read energy (analog MVM is energy-efficient)
        read_energy_pj = self.supert_specs['array_total_energy_pj'] * energy_scale * power_scaling

        # Write energy (high voltage pulses, much more expensive)
        write_energy_pj = self.supert_specs['xbar_energy_pj'] * energy_scale * power_scaling

        return {
            'read': read_energy_pj,
            'write': write_energy_pj
        }

    def get_scaling_analysis(self, board_sizes: list = [2, 3, 5, 9, 19],
                            tech_node: str = '28nm') -> Dict[str, Dict[str, Any]]:
        """
        Analyze crossbar scaling across different board sizes

        Args:
            board_sizes: List of board dimensions to analyze
            tech_node: Technology node

        Returns:
            Dictionary mapping board_size to specs
        """
        # Hidden layer sizes matching training architecture
        # 2-layer NN: N² inputs → hidden → 3 outputs (win/loss/draw)
        HIDDEN_SIZES = {2: 32, 3: 32, 5: 96, 8: 96, 9: 96, 11: 96, 13: 96, 15: 96, 19: 96}

        scaling_results = {}

        for board_size in board_sizes:
            crossbar_rows = board_size * board_size
            crossbar_cols = HIDDEN_SIZES.get(board_size, 96)  # Hidden layer size from training

            hardware_specs = self.estimate_crossbar(crossbar_rows, crossbar_cols, tech_node)

            scaling_results[f"{board_size}x{board_size}"] = {
                'board_size': board_size,
                'crossbar_dims': f"{crossbar_rows}×{crossbar_cols}",
                'area_mm2': hardware_specs['area_mm2'],
                'area_um2': hardware_specs['area_um2'],
                'power_mw': hardware_specs['power_mw'],
                'read_energy_pj': hardware_specs['read_energy_pj'],
                'read_latency_cycles': hardware_specs['read_latency_cycles'],
                'total_devices': hardware_specs['total_devices'],
                'efficiency_devices_per_mm2': hardware_specs['total_devices'] / hardware_specs['area_mm2']
            }

        return scaling_results


def main():
    """Test crossbar hardware model"""
    print("🔬 Crossbar Hardware Model - Literature Calibrated")
    print("=" * 70)

    model = CrossbarHardwareModel()

    # Test different board sizes
    print("\n1. Scaling Analysis Across Board Sizes")
    print("-" * 70)

    scaling = model.get_scaling_analysis(board_sizes=[2, 5, 9, 19], tech_node='28nm')

    print(f"\n{'Board':<8} {'Crossbar':<12} {'Area (mm²)':<12} {'Power (mW)':<12} {'Devices':<10}")
    print("-" * 70)

    for board_key, specs in scaling.items():
        print(f"{board_key:<8} {specs['crossbar_dims']:<12} "
              f"{specs['area_mm2']:<12.4f} {specs['power_mw']:<12.2f} "
              f"{specs['total_devices']:<10}")

    # Detailed specs for 5×5
    print("\n2. Detailed Specs for 5×5 Board (25×32 crossbar)")
    print("-" * 70)

    specs_5x5 = model.estimate_crossbar(rows=25, cols=32, tech_node='28nm')

    print(f"\nArchitecture:")
    print(f"  Dimensions: {specs_5x5['rows']}×{specs_5x5['cols']}")
    print(f"  Total memristors: {specs_5x5['total_devices']}")
    print(f"  Cell size: {specs_5x5['cell_size_um2']:.4f} µm²")
    print(f"  Technology: {specs_5x5['technology']}")

    print(f"\nArea:")
    print(f"  Array area: {specs_5x5['area_mm2']:.6f} mm² ({specs_5x5['area_um2']:.1f} µm²)")
    print(f"  Overhead factor: {specs_5x5['overhead_factor']:.2f}×")

    print(f"\nPower:")
    print(f"  Total power: {specs_5x5['power_mw']:.3f} mW")
    print(f"  Static power: {specs_5x5['static_power_mw']:.3f} mW")
    print(f"  Dynamic power: {specs_5x5['dynamic_power_mw']:.3f} mW")

    print(f"\nEnergy:")
    print(f"  Read energy: {specs_5x5['read_energy_pj']:.2f} pJ")
    print(f"  Write energy: {specs_5x5['write_energy_pj']:.2f} pJ")

    print(f"\nTiming:")
    print(f"  Read latency: {specs_5x5['read_latency_cycles']} cycle ({specs_5x5['read_latency_ns']:.2f} ns)")
    print(f"  Operating frequency: {specs_5x5['frequency_mhz']:.0f} MHz")
    print(f"  Write latency: {specs_5x5['write_latency_ms']:.0f} ms")

    print("\n✅ Crossbar hardware model test complete!")


if __name__ == "__main__":
    main()
