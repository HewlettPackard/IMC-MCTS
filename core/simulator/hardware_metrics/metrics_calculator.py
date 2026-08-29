# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Metrics Calculator - Performance Analysis from SST + Hardware Models
====================================================================

Combines SST timing data with hardware models to compute:
- Latency (from SST cycles)
- Energy (power × time)
- Throughput (operations/sec)
- Energy efficiency (operations/joule)

This module combines activity counters with power models, following the same
general method used by tools such as McPAT.
"""

from typing import Dict, Any
from .hardware_model import HardwareModel
from .activity_tracker import ActivityTracker


class MetricsCalculator:
    """Combine SST cycles, hardware costs, and operation counts."""

    def __init__(self, hardware_model: HardwareModel, activity_tracker: ActivityTracker):
        """
        Initialize metrics calculator.

        Args:
            hardware_model: Hardware specifications
            activity_tracker: Activity statistics
        """
        self.hw = hardware_model
        self.activity = activity_tracker

        # Clock parameters for the 500 MHz reference configuration.
        # This model previously used 100 MHz.
        self.clock_frequency_hz = 500e6  # 500 MHz (matches board_config.py)
        self.clock_period_ns = 1e9 / self.clock_frequency_hz  # 2 ns

        # Simulation results (to be set after simulation)
        self.simulation_cycles = 0
        self.wall_clock_time_s = 0.0

    def set_simulation_results(self, simulation_cycles: int, wall_clock_time_s: float):
        """
        Set simulation timing results.

        Args:
            simulation_cycles: Total cycles from SST simulation
            wall_clock_time_s: Wall-clock time for simulation run
        """
        self.simulation_cycles = simulation_cycles
        self.wall_clock_time_s = wall_clock_time_s

    # ========================================================================
    # Latency Calculations
    # ========================================================================

    def get_hardware_latency_ns(self) -> float:
        """
        Calculate hardware latency from SST cycles.

        Returns:
            Hardware latency in nanoseconds
        """
        latency_ns = self.simulation_cycles * self.clock_period_ns
        return latency_ns

    def get_hardware_latency_us(self) -> float:
        """Hardware latency in microseconds"""
        return self.get_hardware_latency_ns() / 1000.0

    def get_hardware_latency_ms(self) -> float:
        """Hardware latency in milliseconds"""
        return self.get_hardware_latency_ns() / 1e6

    def get_latency_per_iteration_ns(self) -> float:
        """Average latency per MCTS iteration in nanoseconds"""
        if self.activity.total_iterations == 0:
            return 0.0
        return self.get_hardware_latency_ns() / self.activity.total_iterations

    # ========================================================================
    # Energy Calculations
    # ========================================================================

    def get_total_energy_nj(self) -> float:
        """
        Calculate total energy consumption.

        Energy = Power × Time
        Power (mW) × Time (μs) = Energy (nJ)

        Returns:
            Total energy in nanojoules
        """
        power_mw = self.hw.total_power_mw
        latency_us = self.get_hardware_latency_us()
        energy_nj = power_mw * latency_us
        return energy_nj

    def get_total_energy_mj(self) -> float:
        """Total energy in millijoules"""
        return self.get_total_energy_nj() / 1e6

    def get_energy_per_iteration_nj(self) -> float:
        """Average energy per MCTS iteration in nanojoules"""
        if self.activity.total_iterations == 0:
            return 0.0
        return self.get_total_energy_nj() / self.activity.total_iterations

    def get_energy_breakdown(self) -> Dict[str, float]:
        """
        Estimate energy breakdown by component.

        Uses power breakdown and assumes uniform activity.
        More sophisticated models could weight by actual activity.

        Returns:
            Energy per component in nanojoules
        """
        latency_us = self.get_hardware_latency_us()
        power_breakdown = self.hw.get_power_breakdown()

        return {
            component: power_mw * latency_us
            for component, power_mw in power_breakdown.items()
        }

    # ========================================================================
    # Throughput Calculations
    # ========================================================================

    def get_throughput_iterations_per_sec(self) -> float:
        """Throughput in iterations per second"""
        latency_s = self.get_hardware_latency_ns() / 1e9
        if latency_s == 0:
            return 0.0
        iterations = self.activity.total_iterations
        throughput_iter_per_s = iterations / latency_s
        return throughput_iter_per_s

    def get_throughput_moves_per_sec(self) -> float:
        """Throughput in game moves evaluated per second"""
        # Approximate: each iteration explores ~10-50 moves depending on tree
        average_moves_per_iteration = 20
        throughput_iter_per_s = self.get_throughput_iterations_per_sec()
        return throughput_iter_per_s * average_moves_per_iteration

    # ========================================================================
    # Efficiency Calculations
    # ========================================================================

    def get_energy_efficiency_iterations_per_joule(self) -> float:
        """Energy efficiency: iterations per joule"""
        total_energy_nj = self.get_total_energy_nj()
        energy_j = total_energy_nj / 1e9
        if energy_j == 0:
            return 0.0
        iterations = self.activity.total_iterations
        return iterations / energy_j

    def get_power_efficiency_iterations_per_watt(self) -> float:
        """Power efficiency: iterations per second per watt"""
        total_power_mw = self.hw.total_power_mw
        power_w = total_power_mw / 1000.0
        if power_w == 0:
            return 0.0
        throughput_iter_per_s = self.get_throughput_iterations_per_sec()
        return throughput_iter_per_s / power_w

    # ========================================================================
    # Area Efficiency
    # ========================================================================

    def get_area_efficiency_iterations_per_mm2_per_sec(self) -> float:
        """Area efficiency: iterations per mm² per second"""
        total_area_mm2 = self.hw.total_area_mm2
        if total_area_mm2 == 0:
            return 0.0
        throughput_iter_per_s = self.get_throughput_iterations_per_sec()
        return throughput_iter_per_s / total_area_mm2

    # ========================================================================
    # Summary Methods
    # ========================================================================
    # NOTE (cleanup): get_speedup_vs_wall_clock() was removed. It computed
    # (Python-interpreter time) / (simulated hardware time), which is just
    # a measure of how slow the Python simulator is — not a research-meaningful
    # speedup. A real "speedup vs CPU" comparison must use the CPU benchmark
    # binary in benchmarks/ for the same operation.

    def get_performance_summary(self) -> Dict[str, Any]:
        """Collect timing, energy, throughput, and efficiency metrics."""
        return {
            # Timing
            'simulation_cycles': self.simulation_cycles,
            'hardware_latency_ns': self.get_hardware_latency_ns(),
            'hardware_latency_us': self.get_hardware_latency_us(),
            'hardware_latency_ms': self.get_hardware_latency_ms(),
            'latency_per_iteration_ns': self.get_latency_per_iteration_ns(),
            'wall_clock_time_s': self.wall_clock_time_s,

            # Energy
            'total_energy_nj': self.get_total_energy_nj(),
            'total_energy_mj': self.get_total_energy_mj(),
            'energy_per_iteration_nj': self.get_energy_per_iteration_nj(),
            'energy_breakdown_nj': self.get_energy_breakdown(),

            # Throughput
            'throughput_iter_per_sec': self.get_throughput_iterations_per_sec(),
            'throughput_moves_per_sec': self.get_throughput_moves_per_sec(),

            # Efficiency
            'energy_efficiency_iter_per_joule': self.get_energy_efficiency_iterations_per_joule(),
            'power_efficiency_iter_per_watt': self.get_power_efficiency_iterations_per_watt(),
            'area_efficiency_iter_per_mm2_per_sec': self.get_area_efficiency_iterations_per_mm2_per_sec(),
        }

    def get_complete_report(self) -> Dict[str, Any]:
        """Collect hardware, activity, and derived performance metrics."""
        return {
            'hardware': self.hw.get_summary(),
            'activity': self.activity.get_summary(),
            'performance': self.get_performance_summary()
        }

    def print_summary(self):
        """Print human-readable performance summary"""
        print("=" * 80)
        print("HARDWARE PERFORMANCE ANALYSIS")
        print("=" * 80)
        print()

        # Hardware
        print("Hardware Configuration:")
        print(f"  Board Size: {self.hw.board_size}x{self.hw.board_size}")
        print(f"  Total Area: {self.hw.total_area_mm2:.4f} mm²")
        print(f"  Total Power: {self.hw.total_power_mw:.2f} mW")
        print()

        # Activity
        print("Activity Statistics:")
        print(f"  Total Iterations: {self.activity.total_iterations}")
        print(f"  Tree Size: {self.activity.tree_size} nodes")
        print()

        # Performance
        performance = self.get_performance_summary()
        print("Performance Metrics:")
        print(f"  Hardware Latency: {performance['hardware_latency_us']:.3f} μs ({performance['latency_per_iteration_ns']:.1f} ns/iter)")
        print(f"  Total Energy: {performance['total_energy_nj']:.2f} nJ ({performance['total_energy_mj']:.6f} mJ)")
        print(f"  Throughput: {performance['throughput_iter_per_sec']:.1f} iter/s")
        print(f"  Energy Efficiency: {performance['energy_efficiency_iter_per_joule']/1e6:.2f} M iter/J")
        print()

        print("=" * 80)

    def __str__(self) -> str:
        return (f"MetricsCalculator({self.simulation_cycles} cycles, "
                f"{self.get_hardware_latency_us():.2f} μs, "
                f"{self.get_total_energy_nj():.2f} nJ)")
