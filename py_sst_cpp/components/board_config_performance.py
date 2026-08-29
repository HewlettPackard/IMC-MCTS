# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Performance-Aware Board Configuration
======================================

Extends board_config.py to provide different hardware configurations based on
play strength (Low/Medium/High). The key difference is memory size, which scales
with the number of MCTS iterations.

Key Scaling Factors:
- More iterations → More tree nodes → More memory
- More memory → More area + more power

Usage:
    from py_sst_cpp.components.board_config_performance import get_board_config_with_performance

    config = get_board_config_with_performance(board_size=9, performance_level="medium")
"""

from dataclasses import replace
from typing import Union

try:
    from .board_config import get_board_config, BoardSize
    from .memory_scaling import get_memory_config
    from .performance_config import PerformanceLevel
except ImportError:
    from py_sst_cpp.components.board_config import get_board_config, BoardSize
    from py_sst_cpp.components.memory_scaling import get_memory_config
    from py_sst_cpp.components.performance_config import PerformanceLevel


# SRAM area/power scaling factors at 22nm
# Based on: 6T SRAM cell @ 22nm ≈ 0.15 μm² per bit
# Conservative estimates for embedded SRAM
SRAM_AREA_PER_KB_MM2 = 0.00001  # mm² per KB (0.01 mm² per MB)
SRAM_LEAKAGE_PER_KB_MW = 0.0005  # mW per KB (leakage only)
SRAM_DYNAMIC_PER_KB_MW = 0.0003  # mW per KB (dynamic, moderate activity)


def get_board_config_with_performance(board_size: int,
                                     performance_level: Union[str, PerformanceLevel]):
    """
    Get board configuration adjusted for specific performance level.

    Args:
        board_size: Board size (2, 3, 5, 9, 13, or 19)
        performance_level: Performance level ("low", "medium", "high" or PerformanceLevel enum)

    Returns:
        BoardConfig with memory, area, and power adjusted for performance level

    Raises:
        ValueError: If board_size or performance_level is invalid
    """
    # Convert string to enum if needed
    if isinstance(performance_level, str):
        performance_level = PerformanceLevel(performance_level.lower())

    # Get base configuration (these are typically sized for MEDIUM or HIGH)
    try:
        board_enum = BoardSize(board_size)
        base_config = get_board_config(board_enum)
    except (ValueError, KeyError):
        raise ValueError(f"Invalid board size: {board_size}")

    # Get memory requirements for this performance level
    try:
        memory_config = get_memory_config(board_size, performance_level)
    except ValueError:
        # Board size not in memory_scaling (e.g., 2x2, 3x3, 13x13)
        # Use simple scaling based on base config
        return _scale_config_simple(base_config, performance_level)

    # Calculate memory scaling ratio
    base_sram_kb = base_config.sram_size_kb
    target_sram_kb = int(memory_config.total_sram_kb)

    # Memory scaling ratio (target / baseline)
    # Assumes base_config is sized for HIGH or MEDIUM performance
    memory_scale_ratio = target_sram_kb / max(base_sram_kb, 1)

    # Clamp ratio to reasonable range (0.1x to 10x)
    memory_scale_ratio = max(0.1, min(memory_scale_ratio, 10.0))

    # Area and power scale proportionally with memory
    # Using conservative scaling: sqrt(ratio) for area, linear for power
    area_scale = memory_scale_ratio ** 0.5
    power_scale = memory_scale_ratio

    # Create modified config
    # Scale memory-related components (Selection and Backprop handle tree storage)
    scaled_config = replace(
        base_config,
        sram_size_kb=target_sram_kb,
        cam_entries=memory_config.cam_entries,
        # Scale Selection (60% of memory-related load)
        selection_area_mm2=base_config.selection_area_mm2 * area_scale,
        selection_power_mw=base_config.selection_power_mw * power_scale,
        # Scale Backprop (40% of memory-related load)
        backprop_area_mm2=base_config.backprop_area_mm2 * area_scale,
        backprop_power_mw=base_config.backprop_power_mw * power_scale,
    )

    return scaled_config


def _scale_config_simple(base_config, performance_level: PerformanceLevel):
    """
    Simple scaling for boards without detailed memory configs.

    Scales memory by estimated factors:
    - LOW: 0.25x baseline
    - MEDIUM: 0.5x baseline
    - HIGH: 1.0x baseline (no change, assumed baseline is HIGH)
    """
    scale_factors = {
        PerformanceLevel.LOW: 0.25,
        PerformanceLevel.MEDIUM: 0.5,
        PerformanceLevel.HIGH: 1.0,
    }

    memory_scale = scale_factors[performance_level]

    # Area scales as sqrt of memory, power scales linearly
    area_scale = memory_scale ** 0.5
    power_scale = memory_scale

    # Scale memory
    target_sram_kb = int(base_config.sram_size_kb * memory_scale)

    # Create modified config with scaled components
    scaled_config = replace(
        base_config,
        sram_size_kb=target_sram_kb,
        selection_area_mm2=base_config.selection_area_mm2 * area_scale,
        selection_power_mw=base_config.selection_power_mw * power_scale,
        backprop_area_mm2=base_config.backprop_area_mm2 * area_scale,
        backprop_power_mw=base_config.backprop_power_mw * power_scale,
    )

    return scaled_config


if __name__ == "__main__":
    print("="*80)
    print("PERFORMANCE-AWARE BOARD CONFIGURATION TEST")
    print("="*80)

    for board_size in [5, 9, 19]:
        print(f"\n{board_size}×{board_size} Board:")
        print("-" * 60)

        for perf in [PerformanceLevel.LOW, PerformanceLevel.MEDIUM, PerformanceLevel.HIGH]:
            config = get_board_config_with_performance(board_size, perf)

            print(f"\n  {perf.value.upper()}:")
            print(f"    SRAM:        {config.sram_size_kb:,} KB ({config.sram_size_kb/1024:.1f} MB)")
            print(f"    CAM Entries: {config.cam_entries:,}")
            print(f"    Total Area:  {config.total_area_mm2:.6f} mm²")
            print(f"    Total Power: {config.total_power_mw:.2f} mW")

    print("\n" + "="*80)
    print("✅ Performance-aware configuration loaded successfully!")
