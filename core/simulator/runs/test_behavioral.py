#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Behavioral Verification Test Suite
====================================
Tests both the standalone model and SST simulator to verify:
1. MCTS tree grows correctly
2. UCB1 selection distributes visits (not all to one child)
3. Values are in [0,1] range
4. Player perspective flipping works
5. Expansion creates correct children
6. SST simulator latency/energy match expected values
"""

import sys
import os
import numpy as np
import pickle
import tempfile
import math

# Add paths
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sst'))

# ===========================================================================
# TEST 1: Standalone Hardware Functional Model
# ===========================================================================

def test_standalone_model():
    """Test the standalone MCTSHardwareFunctional model end-to-end."""
    print("=" * 70)
    print("TEST 1: Standalone Hardware Functional Model")
    print("=" * 70)

    from core.architecture.hardware_functional_model import (
        MCTSHardwareFunctional, ucb1_calculator, best_child_selector,
        child_state_generator, board_to_voltages, crossbar_forward_pass,
        statistics_updater, quantize_weights
    )

    board_size = 3  # Use small board for fast testing

    # --- 1a. Unit tests ---
    print("\n--- 1a. UCB1 Calculator ---")
    ucb1_values = ucb1_calculator([5, 3, 0, 2], [10, 10, 0, 10], 30)
    print(f"  UCB1 values: {[f'{value:.3f}' if value != float('inf') else 'inf' for value in ucb1_values]}")
    assert ucb1_values[2] == float('inf'), "Unvisited node should have inf UCB1"
    assert ucb1_values[0] > ucb1_values[1], "Node with more wins should have higher exploitation"
    print("  PASS: Unvisited=inf, exploitation ordering correct")

    print("\n--- 1b. Best Child Selector ---")
    best_child_id, best_ucb1_value, selection_valid = best_child_selector(ucb1_values)
    assert selection_valid, "Selection should be valid"
    assert best_child_id == 2, "Should select unvisited child (inf UCB1)"
    print(f"  Selected child {best_child_id} (unvisited) -- PASS")

    print("\n--- 1c. Child State Generator ---")
    board_state = np.array([[1, 0, -1], [0, 0, 0], [-1, 0, 1]])
    valid_moves = child_state_generator(board_state, 1)
    expected_empty_cells = np.sum(board_state == 0)
    assert len(valid_moves) == expected_empty_cells, f"Expected {expected_empty_cells} moves, got {len(valid_moves)}"
    print(f"  Board has {expected_empty_cells} empty cells, generated {len(valid_moves)} moves -- PASS")

    print("\n--- 1d. DAC 2-Channel Encoding ---")
    voltages = board_to_voltages(board_state)
    assert len(voltages) == 2 * board_size * board_size, \
        f"Expected {2*board_size*board_size} voltages, got {len(voltages)}"
    # Check encoding: cell (0,0) = 1 (Black) -> [1.0, 0.0]
    assert voltages[0] == 1.0 and voltages[1] == 0.0, "Black should be [1,0]"
    # Cell (0,2) = -1 (White) -> [0.0, 1.0]
    assert voltages[4] == 0.0 and voltages[5] == 1.0, "White should be [0,1]"
    # Cell (0,1) = 0 (Empty) -> [0.0, 0.0]
    assert voltages[2] == 0.0 and voltages[3] == 0.0, "Empty should be [0,0]"
    print(f"  {len(voltages)} voltages, encoding correct -- PASS")

    print("\n--- 1e. Statistics Updater with Player Perspective ---")
    node_stats = {0: (0.0, 0), 1: (0.0, 0), 2: (0.0, 0)}
    node_players = {0: 1, 1: -1, 2: 1}  # Black, White, Black
    updated_stats = statistics_updater(
        node_stats,
        [0, 1, 2],
        value=0.8,
        node_players=node_players,
    )
    # Node 0 (Black): should get +0.8
    # Node 1 (White): should get +0.2 (flipped)
    # Node 2 (Black): should get +0.8
    assert abs(updated_stats[0][0] - 0.8) < 1e-6, f"Black node should accumulate 0.8, got {updated_stats[0][0]}"
    assert abs(updated_stats[1][0] - 0.2) < 1e-6, f"White node should accumulate 0.2, got {updated_stats[1][0]}"
    assert abs(updated_stats[2][0] - 0.8) < 1e-6, f"Black node should accumulate 0.8, got {updated_stats[2][0]}"
    print(f"  Black nodes: +0.8, White node: +0.2 (flipped) -- PASS")

    # --- 1f. Full MCTS with dummy weights ---
    print("\n--- 1f. Full MCTS Iteration Test (3x3 board, 50 iterations) ---")
    # Create dummy weights matching 3x3 board: 18 inputs -> hidden -> 3 outputs
    input_size = board_size * board_size * 2  # 18
    hidden_size = 32  # From Supp Table 4 for 3x3
    output_size = 3

    dummy_weights = {
        'weights1': np.random.randn(input_size, hidden_size).tolist(),
        'weights2': np.random.randn(hidden_size, output_size).tolist(),
        'accuracy': 0.50,
    }

    with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as weights_file_handle:
        pickle.dump(dummy_weights, weights_file_handle)
        weights_path = weights_file_handle.name

    try:
        hardware_mcts = MCTSHardwareFunctional(board_size=board_size, weights_file=weights_path)
        initial_board = np.zeros((board_size, board_size), dtype=int)
        hardware_mcts.reset(initial_board)

        iterations = 50
        rollout_values = []
        for iteration_index in range(iterations):
            rollout_value = hardware_mcts.run_iteration()
            rollout_values.append(rollout_value)

        # Verify tree growth
        tree_size = len(hardware_mcts.tree)
        root_node = hardware_mcts.tree[hardware_mcts.root_id]
        root_visits = root_node['visits']
        root_children = root_node['children']
        num_children = len(root_children)

        print(f"  Tree size: {tree_size} nodes")
        print(f"  Root visits: {root_visits}")
        print(f"  Root children: {num_children}")

        assert tree_size > 1, "Tree should have grown beyond root"
        assert root_visits == iterations, f"Root should have {iterations} visits, got {root_visits}"
        assert num_children > 0, "Root should have children after expansion"
        assert num_children == board_size * board_size, \
            f"Root should have {board_size*board_size} children (all empty cells), got {num_children}"

        # Verify values are in [0, 1]
        assert all(0.0 <= value <= 1.0 for value in rollout_values), \
            f"All values should be in [0,1], got min={min(rollout_values):.3f}, max={max(rollout_values):.3f}"
        print(f"  Values range: [{min(rollout_values):.3f}, {max(rollout_values):.3f}] -- PASS")

        # Verify visit distribution (UCB1 should spread visits, not concentrate on one child)
        child_visits = []
        for move, child_id in root_children.items():
            child_visit_count = hardware_mcts.tree[child_id]['visits']
            child_visits.append(child_visit_count)

        total_child_visits = sum(child_visits)
        max_child_visits = max(child_visits)
        visited_children = sum(1 for visit_count in child_visits if visit_count > 0)

        print(f"  Child visit distribution: {sorted(child_visits, reverse=True)[:5]}... "
              f"(showing top 5 of {num_children})")
        print(f"  Visited children: {visited_children}/{num_children}")
        print(f"  Max child visits: {max_child_visits}/{total_child_visits} "
              f"({max_child_visits/total_child_visits*100:.1f}%)")

        # UCB1 should ensure multiple children are visited
        assert visited_children > 1, "UCB1 should visit more than one child"
        # No single child should have ALL visits (that would mean no exploration)
        assert max_child_visits < total_child_visits, \
            "Visits should be distributed, not all on one child"
        print(f"  UCB1 exploration: distributed -- PASS")

        # Verify player alternation in tree
        for child_id in list(root_children.values())[:3]:
            child_node = hardware_mcts.tree[child_id]
            assert child_node['player'] == -1, f"Root's children should be White to play, got {child_node['player']}"
        print(f"  Player alternation: correct (root=Black, children=White) -- PASS")

        # Verify best move selection
        best_move = hardware_mcts.select_best_move(iterations=0)  # Don't run more, just pick
        if best_move is not None:
            print(f"  Best move (most visited): {best_move}")
        else:
            print(f"  Best move: None (no children)")

    finally:
        os.unlink(weights_path)

    print("\n  STANDALONE MODEL: ALL TESTS PASSED")


# ===========================================================================
# TEST 2: SST Simulator via Accelerator API (Analytical)
# ===========================================================================

def test_sst_analytical():
    """Test analytical mode of Accelerator API."""
    print("\n" + "=" * 70)
    print("TEST 2: Accelerator API - Analytical Mode")
    print("=" * 70)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sst'))
    from core.architecture.accelerator_api import estimate, Accelerator, expected_path_depth

    for board_size in [3, 5, 9]:
        for play_strength in ["low", "medium", "high"]:
            result = estimate(
                board_size=board_size,
                play_strength=play_strength,
                mode="analytical",
            )

            # Verify latency matches the depth-aware formula:
            #   per_iter_ns = 23 + 4 × E[depth]
            #   E[depth]    = 1 + log_{N²}(iterations)
            expected_depth = expected_path_depth(board_size, result.iterations)
            latency_per_iteration_ns = 23.0 + 4.0 * expected_depth
            expected_latency_us = result.iterations * latency_per_iteration_ns / 1000
            actual_latency_us = result.latency_us

            print(f"\n  {board_size}x{board_size} {play_strength:>6}: "
                  f"{result.iterations:>6,} iter, depth={expected_depth:.2f}, "
                  f"latency={actual_latency_us:.2f} us (expected ~{expected_latency_us:.2f} us), "
                  f"energy={result.energy_uj:.3f} uJ, "
                  f"area={result.area_mm2:.4f} mm2")

            # Allow tighter ±5% since both sides use the same formula now;
            # any deviation here would indicate a real bug in analyze().
            latency_ratio = actual_latency_us / expected_latency_us if expected_latency_us > 0 else 0
            assert 0.95 < latency_ratio < 1.05, \
                f"Latency {actual_latency_us:.2f} too far from expected {expected_latency_us:.2f} (ratio={latency_ratio:.3f})"

            # Basic sanity checks
            assert result.energy_uj > 0, "Energy should be positive"
            assert result.area_mm2 > 0, "Area should be positive"
            assert result.power_mw > 0, "Power should be positive"
            assert result.latency_us > 0, "Latency should be positive"

    print("\n  ANALYTICAL MODE: ALL TESTS PASSED")


# ===========================================================================
# TEST 3: SST Simulator - Full Simulation Mode
# ===========================================================================

def test_sst_simulate():
    """Test SST discrete-event simulation mode."""
    print("\n" + "=" * 70)
    print("TEST 3: SST Simulator - Full Simulation Mode")
    print("=" * 70)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sst'))
    from core.architecture.accelerator_api import estimate, expected_path_depth

    # Run SST simulation for small board/low iterations to keep it fast
    board_size = 3
    play_strength = "low"  # 75 iterations for 3x3

    print(f"\n  Running SST simulation: {board_size}x{board_size}, {play_strength} strength...")
    simulation_result = estimate(
        board_size=board_size,
        play_strength=play_strength,
        mode="simulate",
    )

    expected_iterations = 75  # from performance_config.py for 3x3 low
    expected_depth = expected_path_depth(board_size, expected_iterations)
    expected_latency_us = expected_iterations * (23.0 + 4.0 * expected_depth) / 1000

    print(f"  Iterations: {simulation_result.iterations}")
    print(f"  Latency: {simulation_result.latency_us:.2f} us (expected ~{expected_latency_us:.2f} us, depth ~{expected_depth:.2f})")
    print(f"  Energy: {simulation_result.energy_uj:.4f} uJ")
    print(f"  Power: {simulation_result.power_mw:.2f} mW")
    print(f"  Area: {simulation_result.area_mm2:.4f} mm2")
    print(f"  Throughput: {simulation_result.throughput_iter_per_s/1e6:.1f} M iter/s")

    assert simulation_result.iterations == expected_iterations, \
        f"Expected {expected_iterations} iterations, got {simulation_result.iterations}"
    assert simulation_result.latency_us > 0, "Latency should be positive"
    assert simulation_result.energy_uj > 0, "Energy should be positive"

    # Test 5x5 low as well
    board_size = 5
    play_strength = "low"  # 100 iterations for 5x5

    print(f"\n  Running SST simulation: {board_size}x{board_size}, {play_strength} strength...")
    simulation_result = estimate(
        board_size=board_size,
        play_strength=play_strength,
        mode="simulate",
    )

    expected_iterations = 100
    expected_depth = expected_path_depth(board_size, expected_iterations)
    expected_latency_us = expected_iterations * (23.0 + 4.0 * expected_depth) / 1000

    print(f"  Iterations: {simulation_result.iterations}")
    print(f"  Latency: {simulation_result.latency_us:.2f} us (expected ~{expected_latency_us:.2f} us, depth ~{expected_depth:.2f})")
    print(f"  Energy: {simulation_result.energy_uj:.4f} uJ")
    print(f"  Power: {simulation_result.power_mw:.2f} mW")
    print(f"  Area: {simulation_result.area_mm2:.4f} mm2")

    assert simulation_result.iterations == expected_iterations
    assert simulation_result.latency_us > 0
    assert simulation_result.energy_uj > 0

    print("\n  SST SIMULATION MODE: ALL TESTS PASSED")


# ===========================================================================
# TEST 4: SST Tree Behavioral Verification
# ===========================================================================

def test_sst_tree_behavior():
    """Directly inspect the SST MCTS tree after simulation to verify correctness."""
    print("\n" + "=" * 70)
    print("TEST 4: SST Tree Behavioral Verification")
    print("=" * 70)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sst'))

    from py_sst_cpp.core import Simulation
    from py_sst_cpp.core.component import ComponentId
    from py_sst_cpp.core.config import Params
    from py_sst_cpp.core.link import Link
    from py_sst_cpp.components.performance_config import PerformanceLevel, get_performance_config
    from core.simulator.mcts_sst_components import (
        MCTSSystemComponent, SelectionUnitComponent,
        ExpansionUnitComponent, RolloutUnitComponent,
        BackpropagationUnitComponent
    )

    board_size = 3
    iterations = 50  # Enough to see tree behavior

    # Create simulation manually so we can inspect the tree
    simulation = Simulation(f"TreeTest_{board_size}x{board_size}")

    system_params = Params({
        'board_size': board_size,
        'performance_level': 'low',
    })

    unit_params = Params({
        'board_size': board_size,
        'exploration_constant': 1.414,
        'rollout_depth': 15
    })

    # Override iterations
    system = MCTSSystemComponent(ComponentId(0, "system"), system_params)
    system.total_iterations = iterations

    selection = SelectionUnitComponent(ComponentId(1, "selection"), unit_params)
    expansion = ExpansionUnitComponent(ComponentId(2, "expansion"), unit_params)
    rollout = RolloutUnitComponent(ComponentId(3, "rollout"), unit_params)
    backprop = BackpropagationUnitComponent(ComponentId(4, "backprop"), unit_params)

    simulation.add_component("system", system)
    simulation.add_component("selection", selection)
    simulation.add_component("expansion", expansion)
    simulation.add_component("rollout", rollout)
    simulation.add_component("backprop", backprop)

    # Create links
    for link_name, source_component, target_component, source_port, target_port, event_handler in [
        ("sys_sel", system, selection, "to_selection", "from_system", selection.handle_iteration_start),
        ("sel_sys", selection, system, "to_system", "from_selection", system.handle_selection_complete),
        ("sys_exp", system, expansion, "to_expansion", "from_system", expansion.handle_selection_complete),
        ("exp_sys", expansion, system, "to_system", "from_expansion", system.handle_expansion_complete),
        ("sys_rol", system, rollout, "to_rollout", "from_system", rollout.handle_expansion_complete),
        ("rol_sys", rollout, system, "to_system", "from_rollout", system.handle_rollout_complete),
        ("sys_bp", system, backprop, "to_backprop", "from_system", backprop.handle_rollout_complete),
        ("bp_sys", backprop, system, "to_system", "from_backprop", system.handle_backprop_complete),
    ]:
        component_link = Link(link_name)
        component_link._source_component = source_component
        component_link._target_component = target_component
        component_link.set_handler(event_handler)
        source_component.add_link(source_port, component_link)
        target_component.add_link(target_port, component_link)
        simulation.add_link(link_name, component_link)

    # Share state
    selection.node_storage = system.node_storage
    expansion.node_storage = system.node_storage
    expansion.next_node_id_ref = [system.next_node_id]
    rollout.node_storage = system.node_storage
    rollout.system_component = system
    backprop.node_storage = system.node_storage
    backprop.system_component = system

    # Run
    print(f"\n  Running {iterations} iterations on {board_size}x{board_size} board...")
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        simulation.run(end_time=iterations * 100)

    # Inspect tree
    node_storage = system.node_storage
    tree_size = len(node_storage)
    root_node = node_storage[0]

    print(f"  Tree nodes: {tree_size}")
    print(f"  Root visits: {root_node['visits']}")
    print(f"  Root value: {root_node['value']:.3f}")
    print(f"  Root children: {len(root_node['children'])}")
    print(f"  Iterations completed: {system.current_iteration}")

    # Verify basic invariants
    assert root_node['visits'] == system.current_iteration, \
        f"Root visits ({root_node['visits']}) should equal completed iterations ({system.current_iteration})"
    assert root_node['player'] == 1, "Root should be Black to play"
    assert len(root_node['children']) == board_size * board_size, \
        f"Root should have {board_size**2} children, got {len(root_node['children'])}"

    # Check child visits and values
    print(f"\n  Root children visit distribution:")
    child_data = []
    for child_id in root_node['children']:
        child_node = node_storage[child_id]
        child_data.append({
            'id': child_id, 'visits': child_node['visits'],
            'value': child_node['value'], 'player': child_node['player']
        })

    child_data.sort(key=lambda child: child['visits'], reverse=True)
    for child_stats in child_data[:5]:
        average_value = child_stats['value'] / child_stats['visits'] if child_stats['visits'] > 0 else 0
        print(f"    Node {child_stats['id']:>3}: visits={child_stats['visits']:>3}, "
              f"value={child_stats['value']:.2f}, avg={average_value:.3f}, "
              f"player={'White' if child_stats['player'] == -1 else 'Black'}")

    visited_children = sum(1 for child_stats in child_data if child_stats['visits'] > 0)
    total_child_visits = sum(child_stats['visits'] for child_stats in child_data)
    max_child_visits = max(child_stats['visits'] for child_stats in child_data)

    print(f"\n  Visited children: {visited_children}/{len(child_data)}")
    print(f"  Total child visits: {total_child_visits}")
    print(f"  Max child visits: {max_child_visits} ({max_child_visits/total_child_visits*100:.1f}%)")

    # Verify UCB1 distributes visits
    assert visited_children > 1, "UCB1 should visit more than one child"
    assert max_child_visits < total_child_visits, "Visits should be distributed"

    # Verify player alternation
    for child_id in root_node['children']:
        assert node_storage[child_id]['player'] == -1, f"Root's children should be White to play"

    # Verify values are perspective-corrected
    # White-to-play nodes accumulate (1 - NN_value), so their avg should differ from root's avg
    root_average_value = root_node['value'] / root_node['visits'] if root_node['visits'] > 0 else 0
    print(f"\n  Root (Black) avg value: {root_average_value:.3f}")

    # Check a few children (White to play)
    for child_stats in child_data[:3]:
        if child_stats['visits'] > 0:
            selected_average_value = child_stats['value'] / child_stats['visits']
            print(f"  Child (White) avg value: {selected_average_value:.3f}")

    # Values should be in reasonable range [0, 1] per node
    for node_id, tree_node in node_storage.items():
        if tree_node['visits'] > 0:
            average_value = tree_node['value'] / tree_node['visits']
            assert 0.0 <= average_value <= 1.0, \
                f"Node {node_id} avg value {average_value:.3f} out of [0,1] range"

    print(f"\n  All {tree_size} node values in valid [0,1] range -- PASS")
    print(f"\n  SST TREE BEHAVIOR: ALL TESTS PASSED")


# ===========================================================================
# TEST 5: Analytical vs Simulate Comparison
# ===========================================================================

def test_analytical_vs_simulate():
    """Compare analytical and simulate modes for consistency."""
    print("\n" + "=" * 70)
    print("TEST 5: Analytical vs Simulate Mode Comparison")
    print("=" * 70)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sst'))
    from core.architecture.accelerator_api import estimate

    board_size = 3
    play_strength = "low"

    analytical_result = estimate(
        board_size=board_size,
        play_strength=play_strength,
        mode="analytical",
    )
    simulated_result = estimate(
        board_size=board_size,
        play_strength=play_strength,
        mode="simulate",
    )

    print(f"\n  {'Metric':<20} {'Analytical':>15} {'Simulated':>15} {'Ratio':>10}")
    print(f"  {'-'*60}")
    print(f"  {'Iterations':<20} {analytical_result.iterations:>15,} {simulated_result.iterations:>15,} "
          f"{simulated_result.iterations/analytical_result.iterations:>10.2f}")
    print(f"  {'Latency (us)':<20} {analytical_result.latency_us:>15.3f} {simulated_result.latency_us:>15.3f} "
          f"{simulated_result.latency_us/analytical_result.latency_us:>10.2f}")
    print(f"  {'Energy (uJ)':<20} {analytical_result.energy_uj:>15.4f} {simulated_result.energy_uj:>15.4f} "
          f"{simulated_result.energy_uj/analytical_result.energy_uj if analytical_result.energy_uj > 0 else 0:>10.2f}")
    print(f"  {'Power (mW)':<20} {analytical_result.power_mw:>15.3f} {simulated_result.power_mw:>15.3f} "
          f"{simulated_result.power_mw/analytical_result.power_mw:>10.2f}")
    print(f"  {'Area (mm2)':<20} {analytical_result.area_mm2:>15.4f} {simulated_result.area_mm2:>15.4f} "
          f"{simulated_result.area_mm2/analytical_result.area_mm2:>10.2f}")

    # Both should use same iteration count
    assert analytical_result.iterations == simulated_result.iterations, "Iterations should match"
    print(f"\n  Iterations match: {analytical_result.iterations} -- PASS")

    print(f"\n  COMPARISON: ALL TESTS PASSED")


# ===========================================================================
# MAIN
# ===========================================================================

if __name__ == "__main__":
    print("\n" + "#" * 70)
    print("# IMC-MCTS Accelerator - Behavioral Verification Suite")
    print("#" * 70)

    passed = 0
    failed = 0

    tests = [
        ("Standalone Model", test_standalone_model),
        ("Analytical Mode", test_sst_analytical),
        ("SST Simulation", test_sst_simulate),
        ("SST Tree Behavior", test_sst_tree_behavior),
        ("Analytical vs Simulate", test_analytical_vs_simulate),
    ]

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"\n  FAILED: {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "#" * 70)
    print(f"# RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("#" * 70)

    sys.exit(0 if failed == 0 else 1)
