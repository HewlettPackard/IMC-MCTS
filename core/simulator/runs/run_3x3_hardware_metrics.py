#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Accelerator 3x3 Event-Driven Hardware Analysis
==================================================================

Combines SST discrete-event timing with analytical area, energy, power, and
throughput estimates.

Usage:
    python run_3x3_hardware_metrics.py [low|medium|high]
"""

import sys
import os

# Add parent directory to path to import from run_5x5_hardware_metrics
sys.path.insert(0, os.path.dirname(__file__))

# Import the main function and utilities from run_5x5_hardware_metrics
from run_5x5_hardware_metrics import *

# Override board_size in create_simulation calls
_original_create_simulation = create_simulation

def create_simulation(board_size: int, performance_level: PerformanceLevel):
    """Override to use 3x3 board"""
    return _original_create_simulation(3, performance_level)

def main():
    """Run the SST simulation with hardware performance analysis for 3x3"""
    parser = argparse.ArgumentParser(
        description='Accelerator 3x3 MCTS with Event-Driven Hardware Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Performance Levels:
  low     - Fast search, 50 iterations
  medium  - Balanced, 500 iterations (default)
  high    - Strong play, 5000 iterations

This uses:
  - SST discrete-event simulation for cycle-accurate timing
  - hardware metrics model for area, power, energy, throughput analysis
        """
    )
    parser.add_argument('performance', nargs='?', default='medium',
                       choices=['low', 'medium', 'high'],
                       help='Performance level (default: medium)')

    args = parser.parse_args()

    print("="*80)
    print("Accelerator 3x3 MCTS - Event-Driven Hardware Analysis")
    print("="*80)
    print()

    # Create simulation
    performance_level = PerformanceLevel(args.performance.lower())
    simulation, system = create_simulation(
        board_size=3,
        performance_level=performance_level,
    )

    # Get expected iterations for end time calculation
    performance_config = get_performance_config(3, performance_level)
    expected_iterations = performance_config['iterations']

    # Calculate end time (rough estimate: ~100 cycles per iteration)
    simulation_end_time = expected_iterations * 100

    # Initialize hardware metrics model
    print("Initializing hardware metrics model...")
    hardware_model = HardwareModel(board_size=3)
    activity_tracker = ActivityTracker()
    activity_tracker.attach_to_simulation(simulation, system)
    metrics_calculator = MetricsCalculator(hardware_model, activity_tracker)
    print("  ✓ hardware metrics model ready")
    print()

    print(f"Starting SST simulation...")
    print(f"Expected iterations: {expected_iterations}")
    print(f"Simulation end time: {simulation_end_time} cycles")
    print("="*80)
    print()

    start_wall_time = time.time()

    # Run the simulation!
    simulation.run(end_time=simulation_end_time)

    end_wall_time = time.time()
    wall_clock_time_s = end_wall_time - start_wall_time

    print()
    print("="*80)
    print(f"SST SIMULATION COMPLETE")
    print("="*80)
    print(f"Wall-clock time: {wall_clock_time_s:.3f} seconds")
    print(f"Final simulation time: {simulation.get_current_time()} cycles")
    print()

    # Collect activity statistics
    print("Collecting activity statistics...")
    activity_tracker.collect_statistics()
    print("  ✓ Activity statistics collected")
    print()

    # Set simulation results in metrics calculator
    metrics_calculator.set_simulation_results(
        simulation_cycles=simulation.get_current_time(),
        wall_clock_time_s=wall_clock_time_s
    )

    # Print hardware performance analysis
    metrics_calculator.print_summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())
