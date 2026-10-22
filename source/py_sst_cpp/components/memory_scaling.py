# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Memory Scaling Configuration for MCTS Performance Levels

Memory requirements scale with MCTS iterations:
- More iterations → More tree nodes
- More nodes → More CAM entries, Node SRAM, Children SRAM

This module calculates memory requirements for each (board_size, performance_level) pair.

NOTE: board_config.py is the canonical source of truth for on-chip CAM/SRAM sizing.
Those values are sized for MEDIUM performance level (the paper's design point).
This module provides analytical memory estimates for what-if analysis across
different iteration counts, and for validating that board_config.py values are sufficient.
"""

from dataclasses import dataclass
from typing import Dict

# Import PerformanceLevel from performance_config
try:
    from .performance_config import PerformanceLevel
except ImportError:
    from py_sst_cpp.components.performance_config import PerformanceLevel


@dataclass
class MemoryConfig:
    """Memory configuration for a specific board size and performance level

    SRAM architecture: two separate arrays
    - Node SRAM: per-node metadata (24 bytes/entry), addressed by node_id
    - Children SRAM: pool of child pointers (4 bytes/entry)
      Pool-based: total entries = total_nodes - 1 (each non-root node appears
      as exactly one child pointer in its parent's child list)
    """
    board_size: int
    performance_level: PerformanceLevel
    iterations: int

    # Tree growth characteristics
    avg_nodes_per_iteration: float

    # Calculated memory requirements
    cam_entries: int
    node_sram_kb: float
    children_sram_kb: float
    total_sram_kb: float

    # Memory utilization (for validation)
    expected_nodes_created: int
    cam_utilization_percent: float


# Tree growth characteristics (empirical data from SST simulation)
# Measured at MEDIUM iteration counts via SST event-driven simulation.
# The SST expands ALL legal moves as children during expansion phase,
# so nodes_per_iteration reflects the average branching factor + 1.
TREE_GROWTH_RATES = {
    # 2x2: 200 iter → 65 nodes (0.33 nodes/iter, tiny tree)
    2: {'nodes_per_iteration': 0.33},
    # 3x3: 500 iter → 622 nodes (1.24 nodes/iter)
    3: {'nodes_per_iteration': 1.24},
    # 5x5: 1000 iter → 9,159 nodes (9.16 nodes/iter)
    5: {'nodes_per_iteration': 9.16},
    # 8x8: estimated ~3.0 nodes/iter (between 5x5 and 9x9)
    8: {'nodes_per_iteration': 3.0},
    # 9x9: 5000 iter → 6,562 nodes (1.31 nodes/iter, tree saturates)
    9: {'nodes_per_iteration': 1.31},
    # 11x11: estimated ~2.5 nodes/iter (between 9x9 and 13x13)
    11: {'nodes_per_iteration': 2.5},
    # 13x13: 7500 iter → 28,562 nodes (3.81 nodes/iter)
    13: {'nodes_per_iteration': 3.81},
    # 15x15: estimated ~6.0 nodes/iter (between 13x13 and 19x19)
    15: {'nodes_per_iteration': 6.0},
    # 19x19: 10000 iter → 130,322 nodes (13.03 nodes/iter)
    19: {'nodes_per_iteration': 13.03},
}

# Memory parameters
NODE_SIZE_BYTES = 24  # visits (4B), value (4B), parent_id (4B), children_start (4B), children_count (2B), flags (2B), padding (4B)
CHILD_PTR_BYTES = 4   # 32-bit child node ID (pool entry)


def calculate_memory_requirements(board_size: int, iterations: int,
                                  performance_level: PerformanceLevel) -> MemoryConfig:
    """
    Calculate memory requirements for given board size and iteration count.

    Uses pool-based children storage model:
    - Node SRAM: max_nodes × 24 bytes (per-node metadata)
    - Children SRAM: (max_nodes - 1) × 4 bytes (one pointer per parent-child edge)

    Args:
        board_size: Board size (2, 3, 5, 9, 13, or 19)
        iterations: Number of MCTS iterations
        performance_level: Performance level (for labeling)

    Returns:
        MemoryConfig with all memory specifications
    """
    if board_size not in TREE_GROWTH_RATES:
        raise ValueError(f"Unsupported board size: {board_size}")

    growth_rate = TREE_GROWTH_RATES[board_size]
    avg_nodes_per_iteration = growth_rate['nodes_per_iteration']

    # Calculate expected tree size
    expected_nodes_created = int(iterations * avg_nodes_per_iteration)

    # CAM sizing: Add 20% margin for tree variance
    cam_entries = int(expected_nodes_created * 1.2)
    # Round up to power of 2 for hardware efficiency
    cam_entries = max(1, 2 ** (cam_entries - 1).bit_length())

    # Node SRAM sizing (24 bytes per node entry)
    node_sram_bytes = expected_nodes_created * NODE_SIZE_BYTES * 1.2  # 20% margin
    node_sram_kb = node_sram_bytes / 1024

    # Children SRAM sizing (pool-based: one 4-byte pointer per parent-child edge)
    # In a tree, edges = nodes - 1 (every non-root node has exactly one parent)
    total_edges = max(0, expected_nodes_created - 1)
    children_sram_bytes = total_edges * CHILD_PTR_BYTES * 1.2  # 20% margin
    children_sram_kb = children_sram_bytes / 1024

    # Total SRAM
    total_sram_kb = node_sram_kb + children_sram_kb

    # CAM utilization
    cam_utilization_percent = (expected_nodes_created / cam_entries) * 100 if cam_entries > 0 else 0

    return MemoryConfig(
        board_size=board_size,
        performance_level=performance_level,
        iterations=iterations,
        avg_nodes_per_iteration=avg_nodes_per_iteration,
        cam_entries=cam_entries,
        node_sram_kb=node_sram_kb,
        children_sram_kb=children_sram_kb,
        total_sram_kb=total_sram_kb,
        expected_nodes_created=expected_nodes_created,
        cam_utilization_percent=cam_utilization_percent
    )


def get_memory_config(board_size: int, performance_level) -> MemoryConfig:
    """
    Get memory configuration for board size and performance level.

    Args:
        board_size: Board size (2, 3, 5, 9, 13, or 19)
        performance_level: PerformanceLevel enum or string

    Returns:
        MemoryConfig for the specified configuration
    """
    # Import here to avoid circular dependency
    try:
        from .performance_config import get_performance_config
    except ImportError:
        # Running as standalone script
        from py_sst_cpp.components.performance_config import get_performance_config

    # Convert string to enum if needed
    if isinstance(performance_level, str):
        performance_level = PerformanceLevel(performance_level.lower())

    # Get iteration count from performance config
    performance_config = get_performance_config(board_size, performance_level)
    iterations = performance_config['iterations']

    return calculate_memory_requirements(board_size, iterations, performance_level)


def print_memory_specs(board_size=None, performance_level=None):
    """
    Print memory specifications.

    Args:
        board_size: Board size (2, 3, 5, 9, 13, or 19), or None for all
        performance_level: PerformanceLevel or None for all
    """
    if board_size is not None:
        board_sizes = [board_size]
    else:
        board_sizes = [2, 3, 5, 8, 9, 11, 13, 15, 19]

    if performance_level is not None:
        if isinstance(performance_level, str):
            performance_level = PerformanceLevel(performance_level.lower())
        perf_levels = [performance_level]
    else:
        perf_levels = [PerformanceLevel.LOW, PerformanceLevel.MEDIUM, PerformanceLevel.HIGH]

    for size in board_sizes:
        print(f"\n{'='*90}")
        print(f"{size}×{size} Board - Memory Requirements")
        print(f"{'='*90}")

        for perf in perf_levels:
            memory_config = get_memory_config(size, perf)

            print(f"\n{perf.value.upper()}:")
            print(f"  MCTS Iterations:         {memory_config.iterations:,}")
            print(f"  Expected Node Allocations: {memory_config.expected_nodes_created:,}")
            print(f"  Avg Nodes/Iteration:     {memory_config.avg_nodes_per_iteration:.1f}")
            print(f"  ---")
            print(f"  CAM Entries:             {memory_config.cam_entries:,}")
            print(f"  CAM Utilization:         {memory_config.cam_utilization_percent:.1f}%")
            print(f"  ---")
            print(f"  Node SRAM:               {memory_config.node_sram_kb:.1f} KB")
            print(f"  Children SRAM:           {memory_config.children_sram_kb:.1f} KB")
            print(f"  Total SRAM:              {memory_config.total_sram_kb:.1f} KB ({memory_config.total_sram_kb/1024:.2f} MB)")


def print_memory_comparison_table(board_size):
    """Print comparison table for all performance levels of a board size."""
    print(f"\n{board_size}×{board_size} Board - Memory Comparison")
    print(f"{'='*110}")
    print(f"{'Level':<10} {'Iter':>8} {'Nodes':>8} {'CAM':>8} {'Util':>6} {'Node KB':>10} {'Child KB':>10} {'Total MB':>10}")
    print(f"{'-'*110}")

    for perf in [PerformanceLevel.LOW, PerformanceLevel.MEDIUM, PerformanceLevel.HIGH]:
        memory_config = get_memory_config(board_size, perf)
        print(f"{perf.value.upper():<10} "
              f"{memory_config.iterations:>8,} "
              f"{memory_config.expected_nodes_created:>8,} "
              f"{memory_config.cam_entries:>8,} "
              f"{memory_config.cam_utilization_percent:>5.1f}% "
              f"{memory_config.node_sram_kb:>10.1f} "
              f"{memory_config.children_sram_kb:>10.1f} "
              f"{memory_config.total_sram_kb/1024:>10.2f}")
    print(f"{'='*110}\n")


if __name__ == "__main__":
    print("IMC-MCTS - Memory Scaling Configuration")
    print("="*90)

    # Print all memory specifications
    print_memory_specs()

    # Print comparison tables
    print("\n" + "="*90)
    print("MEMORY COMPARISON TABLES")
    print("="*90)
    for size in [2, 3, 5, 9, 13, 19]:
        print_memory_comparison_table(size)

    # Example usage
    print("\n" + "="*90)
    print("USAGE EXAMPLE")
    print("="*90)

    mem_config = get_memory_config(5, PerformanceLevel.MEDIUM)
    print(f"\n5×5 Board, MEDIUM performance:")
    print(f"  Iterations: {mem_config.iterations:,}")
    print(f"  Expected nodes: {mem_config.expected_nodes_created:,}")
    print(f"  CAM entries: {mem_config.cam_entries:,}")
    print(f"  Total SRAM: {mem_config.total_sram_kb/1024:.2f} MB")

    # 9x9 medium example (design point)
    mem_config = get_memory_config(9, PerformanceLevel.MEDIUM)
    print(f"\n9×9 Board, MEDIUM performance (design point):")
    print(f"  Iterations: {mem_config.iterations:,}")
    print(f"  Expected nodes: {mem_config.expected_nodes_created:,}")
    print(f"  CAM entries: {mem_config.cam_entries:,}")
    print(f"  Total SRAM: {mem_config.total_sram_kb/1024:.2f} MB")
