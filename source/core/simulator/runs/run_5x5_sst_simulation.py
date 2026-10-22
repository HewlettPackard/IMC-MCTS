#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Accelerator 5x5 SST Simulation - TRUE Discrete-Event Simulation
===============================================================

This script uses the py_SST discrete-event simulation engine with:
- Proper SST Components
- Event-driven communication
- Link-based connections
- Cycle-accurate timing

Usage:
    python run_5x5_sst_simulation.py [low|medium|high]
"""

import sys
import os
import argparse
import time
from datetime import datetime

# Add py_sst_cpp to path

from py_sst_cpp.core import Simulation
from py_sst_cpp.core.component import ComponentId
from py_sst_cpp.core.config import Params
from py_sst_cpp.core.link import Link
from py_sst_cpp.components.board_config import BoardSize, get_board_config
from py_sst_cpp.components.performance_config import PerformanceLevel, get_performance_config

# Import our SST components
from core.simulator.mcts_sst_components import (
    MCTSSystemComponent,
    SelectionUnitComponent,
    ExpansionUnitComponent,
    RolloutUnitComponent,
    BackpropagationUnitComponent
)


def create_simulation(board_size: int, performance_level: PerformanceLevel):
    """
    Create and configure the SST simulation with all components and links.

    Args:
        board_size: Board size (5 for 5x5)
        performance_level: Performance level (LOW, MEDIUM, HIGH)

    Returns:
        Configured Simulation object
    """
    # Create simulation
    simulation = Simulation(f"Accelerator_{board_size}x{board_size}_MCTS")

    print(f"Creating SST simulation for {board_size}x{board_size} board...")
    print(f"Performance level: {performance_level.value}")
    print("="*80)

    # Get configurations
    performance_config = get_performance_config(board_size, performance_level)

    # Create component parameters
    system_params = Params({
        'board_size': board_size,
        'performance_level': performance_level.value,
    })

    unit_params = Params({
        'board_size': board_size,
        'exploration_constant': performance_config['exploration_constant'],
        'rollout_depth': performance_config['rollout_depth']
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
    simulation.add_component("system", system)
    simulation.add_component("selection", selection)
    simulation.add_component("expansion", expansion)
    simulation.add_component("rollout", rollout)
    simulation.add_component("backprop", backprop)

    print(f"  ✓ Created {len(simulation._components)} components")

    # Create links between components
    print("Creating links...")

    # System <-> Selection
    link_system_to_selection = Link("system_to_selection")
    link_system_to_selection._source_component = system
    link_system_to_selection._target_component = selection
    link_selection_to_system = Link("selection_to_system")
    link_selection_to_system._source_component = selection
    link_selection_to_system._target_component = system

    system.add_link("to_selection", link_system_to_selection)
    selection.add_link("from_system", link_system_to_selection)
    selection.add_link("to_system", link_selection_to_system)
    system.add_link("from_selection", link_selection_to_system)

    # System <-> Expansion
    link_system_to_expansion = Link("system_to_expansion")
    link_system_to_expansion._source_component = system
    link_system_to_expansion._target_component = expansion
    link_expansion_to_system = Link("expansion_to_system")
    link_expansion_to_system._source_component = expansion
    link_expansion_to_system._target_component = system

    system.add_link("to_expansion", link_system_to_expansion)
    expansion.add_link("from_system", link_system_to_expansion)
    expansion.add_link("to_system", link_expansion_to_system)
    system.add_link("from_expansion", link_expansion_to_system)

    # System <-> Rollout
    link_system_to_rollout = Link("system_to_rollout")
    link_system_to_rollout._source_component = system
    link_system_to_rollout._target_component = rollout
    link_rollout_to_system = Link("rollout_to_system")
    link_rollout_to_system._source_component = rollout
    link_rollout_to_system._target_component = system

    system.add_link("to_rollout", link_system_to_rollout)
    rollout.add_link("from_system", link_system_to_rollout)
    rollout.add_link("to_system", link_rollout_to_system)
    system.add_link("from_rollout", link_rollout_to_system)

    # System <-> Backprop
    link_system_to_backprop = Link("system_to_backprop")
    link_system_to_backprop._source_component = system
    link_system_to_backprop._target_component = backprop
    link_backprop_to_system = Link("backprop_to_system")
    link_backprop_to_system._source_component = backprop
    link_backprop_to_system._target_component = system

    system.add_link("to_backprop", link_system_to_backprop)
    backprop.add_link("from_system", link_system_to_backprop)
    backprop.add_link("to_system", link_backprop_to_system)
    system.add_link("from_backprop", link_backprop_to_system)

    simulation.add_link("system_to_selection", link_system_to_selection)
    simulation.add_link("selection_to_system", link_selection_to_system)
    simulation.add_link("system_to_expansion", link_system_to_expansion)
    simulation.add_link("expansion_to_system", link_expansion_to_system)
    simulation.add_link("system_to_rollout", link_system_to_rollout)
    simulation.add_link("rollout_to_system", link_rollout_to_system)
    simulation.add_link("system_to_backprop", link_system_to_backprop)
    simulation.add_link("backprop_to_system", link_backprop_to_system)

    print(f"  ✓ Created {len(simulation._links)} links")

    # Share node storage between components (they all need access to the tree)
    selection.node_storage = system.node_storage
    expansion.node_storage = system.node_storage
    expansion.next_node_id_ref = [system.next_node_id]  # Pass by reference
    backprop.node_storage = system.node_storage

    # Backprop needs reference to system for accessing current path and value
    backprop.system_component = system

    # Wire up event handlers
    print("Wiring event handlers...")

    # Configure link event handlers
    # When selection receives iteration start -> handle it
    link_system_to_selection.set_handler(selection.handle_iteration_start)

    # When system receives selection complete -> handle it
    link_selection_to_system.set_handler(system.handle_selection_complete)

    # When expansion receives selection complete -> handle it
    link_system_to_expansion.set_handler(expansion.handle_selection_complete)

    # When system receives expansion complete -> handle it
    link_expansion_to_system.set_handler(system.handle_expansion_complete)

    # When rollout receives expansion complete -> handle it
    link_system_to_rollout.set_handler(rollout.handle_expansion_complete)

    # When system receives rollout complete -> handle it
    link_rollout_to_system.set_handler(system.handle_rollout_complete)

    # When backprop receives event -> handle it
    link_system_to_backprop.set_handler(backprop.handle_rollout_complete)

    # When system receives backprop complete -> handle it
    link_backprop_to_system.set_handler(system.handle_backprop_complete)

    print(f"  ✓ Wired event handlers")

    print("="*80)
    print("SST simulation configured successfully")
    print()

    return simulation


def main():
    """Run the SST simulation"""
    parser = argparse.ArgumentParser(
        description='Accelerator 5x5 MCTS SST Simulation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Performance Levels:
  low     - Fast search, 100 iterations
  medium  - Balanced, 1000 iterations (default)
  high    - Strong play, 10000 iterations

This uses TRUE SST discrete-event simulation with:
  - Component-based architecture
  - Event-driven communication
  - Cycle-accurate timing
        """
    )
    parser.add_argument('performance', nargs='?', default='medium',
                       choices=['low', 'medium', 'high'],
                       help='Performance level (default: medium)')

    args = parser.parse_args()

    # Create simulation
    performance_level = PerformanceLevel(args.performance.lower())
    simulation = create_simulation(
        board_size=5,
        performance_level=performance_level,
    )

    # Get expected iterations for end time calculation
    performance_config = get_performance_config(5, performance_level)
    expected_iterations = performance_config['iterations']

    # Calculate end time (rough estimate: ~100 cycles per iteration)
    simulation_end_time = expected_iterations * 100

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
    print(f"Wall-clock time: {wall_clock_time_s:.2f} seconds")
    print(f"Final simulation time: {simulation.get_current_time()} cycles")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
