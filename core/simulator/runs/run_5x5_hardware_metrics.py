#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Accelerator 5x5 Event-Driven Hardware Analysis
==================================================================

Combines SST discrete-event timing with analytical area, energy, power, and
throughput estimates.

Architecture:
- SST provides cycle-accurate timing
- The hardware metrics layer provides area, power, energy, throughput metrics

Usage:
    python run_5x5_hardware_metrics.py [low|medium|high]
"""

import sys
import os
import argparse
import time
from datetime import datetime

import numpy as np

from py_sst_cpp.core import Simulation
from py_sst_cpp.core.component import ComponentId
from py_sst_cpp.core.config import Params
from py_sst_cpp.core.link import Link
from py_sst_cpp.components.board_config import BoardSize, get_board_config
from py_sst_cpp.components.performance_config import PerformanceLevel, get_performance_config

# Import SST components
from core.simulator.mcts_sst_components import (
    MCTSSystemComponent,
    SelectionUnitComponent,
    ExpansionUnitComponent,
    RolloutUnitComponent,
    BackpropagationUnitComponent,
    _find_best_weights,
)

# Import hardware metrics model
from core.simulator.hardware_metrics import HardwareModel, ActivityTracker, MetricsCalculator


# Deterministic seed for reproducibility — a fresh seed per run would mean
# different rollout NN weights and different random child picks, making
# results non-comparable across runs. Override via SEED env var if needed.
SEED = int(os.environ.get("IMC_MCTS_SEED", "42"))


def create_simulation(board_size: int, performance_level: PerformanceLevel):
    """
    Create and configure the SST simulation with all components and links.

    Args:
        board_size: Board size (5 for 5x5)
        performance_level: Performance level (LOW, MEDIUM, HIGH)

    Returns:
        Configured Simulation object
    """
    # Set numpy seed BEFORE creating components — RolloutUnit's __init__
    # initializes its NN weights via np.random.randn, which we want to be
    # either (a) overwritten by trained weights below, or (b) deterministic
    # if no trained weights are available.
    np.random.seed(SEED)
    import random as _python_random
    _python_random.seed(SEED)

    # Create simulation
    sim = Simulation(f"Accelerator_{board_size}x{board_size}_MCTS")

    print(f"Creating SST simulation for {board_size}x{board_size} board...")
    print(f"Performance level: {performance_level.value}")
    print("="*80)

    # Get configurations
    perf_config = get_performance_config(board_size, performance_level)

    # Create component parameters
    system_params = Params({
        'board_size': board_size,
        'performance_level': performance_level.value,
    })

    unit_params = Params({
        'board_size': board_size,
        'exploration_constant': perf_config['exploration_constant'],
        'rollout_depth': perf_config['rollout_depth']
    })

    # Create components
    print("Creating components...")

    system = MCTSSystemComponent(
        ComponentId(0, "mcts_system"),
        system_params
    )

    selection = SelectionUnitComponent(
        ComponentId(1, "selection_unit"),
        unit_params
    )

    expansion = ExpansionUnitComponent(
        ComponentId(2, "expansion_unit"),
        unit_params
    )

    rollout = RolloutUnitComponent(
        ComponentId(3, "rollout_unit"),
        unit_params
    )

    backprop = BackpropagationUnitComponent(
        ComponentId(4, "backprop_unit"),
        unit_params
    )

    # Add components to simulation
    sim.add_component("system", system)
    sim.add_component("selection", selection)
    sim.add_component("expansion", expansion)
    sim.add_component("rollout", rollout)
    sim.add_component("backprop", backprop)

    print(f"  ✓ Created {len(sim._components)} components")

    # Create links between components
    print("Creating links...")

    # System <-> Selection
    link_sys_to_sel = Link("system_to_selection")
    link_sys_to_sel._source_component = system
    link_sys_to_sel._target_component = selection
    link_sel_to_sys = Link("selection_to_system")
    link_sel_to_sys._source_component = selection
    link_sel_to_sys._target_component = system

    system.add_link("to_selection", link_sys_to_sel)
    selection.add_link("from_system", link_sys_to_sel)
    selection.add_link("to_system", link_sel_to_sys)
    system.add_link("from_selection", link_sel_to_sys)

    # System <-> Expansion
    link_sys_to_exp = Link("system_to_expansion")
    link_sys_to_exp._source_component = system
    link_sys_to_exp._target_component = expansion
    link_exp_to_sys = Link("expansion_to_system")
    link_exp_to_sys._source_component = expansion
    link_exp_to_sys._target_component = system

    system.add_link("to_expansion", link_sys_to_exp)
    expansion.add_link("from_system", link_sys_to_exp)
    expansion.add_link("to_system", link_exp_to_sys)
    system.add_link("from_expansion", link_exp_to_sys)

    # System <-> Rollout
    link_sys_to_rol = Link("system_to_rollout")
    link_sys_to_rol._source_component = system
    link_sys_to_rol._target_component = rollout
    link_rol_to_sys = Link("rollout_to_system")
    link_rol_to_sys._source_component = rollout
    link_rol_to_sys._target_component = system

    system.add_link("to_rollout", link_sys_to_rol)
    rollout.add_link("from_system", link_sys_to_rol)
    rollout.add_link("to_system", link_rol_to_sys)
    system.add_link("from_rollout", link_rol_to_sys)

    # System <-> Backprop
    link_sys_to_bak = Link("system_to_backprop")
    link_sys_to_bak._source_component = system
    link_sys_to_bak._target_component = backprop
    link_bak_to_sys = Link("backprop_to_system")
    link_bak_to_sys._source_component = backprop
    link_bak_to_sys._target_component = system

    system.add_link("to_backprop", link_sys_to_bak)
    backprop.add_link("from_system", link_sys_to_bak)
    backprop.add_link("to_system", link_bak_to_sys)
    system.add_link("from_backprop", link_bak_to_sys)

    sim.add_link("system_to_selection", link_sys_to_sel)
    sim.add_link("selection_to_system", link_sel_to_sys)
    sim.add_link("system_to_expansion", link_sys_to_exp)
    sim.add_link("expansion_to_system", link_exp_to_sys)
    sim.add_link("system_to_rollout", link_sys_to_rol)
    sim.add_link("rollout_to_system", link_rol_to_sys)
    sim.add_link("system_to_backprop", link_sys_to_bak)
    sim.add_link("backprop_to_system", link_bak_to_sys)

    print(f"  ✓ Created {len(sim._links)} links")

    # Share node storage between components
    selection.node_storage = system.node_storage
    expansion.node_storage = system.node_storage
    expansion.next_node_id_ref = [system.next_node_id]
    backprop.node_storage = system.node_storage
    backprop.system_component = system

    # Load trained NN weights for the rollout unit. Without these, rollout
    # produces noise — hardware timing/energy claims are still valid, but
    # MCTS value distributions and play-quality claims would be meaningless.
    weights_path = _find_best_weights(board_size)
    if weights_path:
        try:
            rollout.load_weights(weights_path)
            print(f"  ✓ Rollout NN: loaded {os.path.basename(weights_path)}")
        except Exception as e:
            print(f"  ⚠ Rollout NN: failed to load weights ({e}); using random.")
            print(f"    MCTS play-quality results from this run are NOT MEANINGFUL.")
    else:
        print(f"  ⚠ Rollout NN: no trained weights found for {board_size}x{board_size}.")
        print(f"    Looked in: training/results/weights_{board_size}x{board_size}/")
        print(f"    Using RANDOM weights — timing/energy results valid, MCTS play")
        print(f"    quality is NOT MEANINGFUL. Train weights or load existing ones.")
    # System.rollout_weights_loaded flag for downstream tools / metadata
    system._rollout_weights_loaded = bool(weights_path)
    system._rollout_weights_path = weights_path or "(random)"

    # Wire up event handlers
    print("Wiring event handlers...")

    link_sys_to_sel.set_handler(selection.handle_iteration_start)
    link_sel_to_sys.set_handler(system.handle_selection_complete)
    link_sys_to_exp.set_handler(expansion.handle_selection_complete)
    link_exp_to_sys.set_handler(system.handle_expansion_complete)
    link_sys_to_rol.set_handler(rollout.handle_expansion_complete)
    link_rol_to_sys.set_handler(system.handle_rollout_complete)
    link_sys_to_bak.set_handler(backprop.handle_rollout_complete)
    link_bak_to_sys.set_handler(system.handle_backprop_complete)

    print(f"  ✓ Wired event handlers")
    print("="*80)
    print("SST simulation configured successfully")
    print()

    return sim, system


def main():
    """Run the SST simulation with hardware performance analysis"""
    parser = argparse.ArgumentParser(
        description='Accelerator 5x5 MCTS with Event-Driven Hardware Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Performance Levels:
  low     - Fast search, 100 iterations
  medium  - Balanced, 1000 iterations (default)
  high    - Strong play, 10000 iterations

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
    print("Accelerator 5x5 MCTS - Event-Driven Hardware Analysis")
    print("="*80)
    print()

    # Create simulation
    perf_level = PerformanceLevel(args.performance.lower())
    sim, system = create_simulation(board_size=5, performance_level=perf_level)

    # Get expected iterations for end time calculation
    perf_config = get_performance_config(5, perf_level)
    expected_iterations = perf_config['iterations']

    # Calculate end time (rough estimate: ~100 cycles per iteration)
    end_time = expected_iterations * 100

    # Initialize hardware metrics model
    print("Initializing hardware metrics model...")
    hardware_model = HardwareModel(board_size=5)
    activity_tracker = ActivityTracker()
    activity_tracker.attach_to_simulation(sim, system)
    metrics_calculator = MetricsCalculator(hardware_model, activity_tracker)
    print("  ✓ hardware metrics model ready")
    print()

    print(f"Starting SST simulation...")
    print(f"Expected iterations: {expected_iterations}")
    print(f"Simulation end time: {end_time} cycles")
    print("="*80)
    print()

    start_wall_time = time.time()

    # Run the simulation!
    sim.run(end_time=end_time)

    end_wall_time = time.time()
    elapsed = end_wall_time - start_wall_time

    print()
    print("="*80)
    print(f"SST SIMULATION COMPLETE")
    print("="*80)
    print(f"Wall-clock time: {elapsed:.3f} seconds")
    print(f"Final simulation time: {sim.get_current_time()} cycles")
    print()

    # Collect activity statistics
    print("Collecting activity statistics...")
    activity_tracker.collect_statistics()
    print("  ✓ Activity statistics collected")
    print()

    # Set simulation results in metrics calculator
    metrics_calculator.set_simulation_results(
        simulation_cycles=sim.get_current_time(),
        wall_clock_time_s=elapsed
    )

    # Print hardware performance analysis
    metrics_calculator.print_summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())
