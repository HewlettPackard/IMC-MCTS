# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Performance Level Configuration for IMC-MCTS Accelerator

This module defines three performance levels (LOW, MEDIUM, HIGH) for each board size.
The primary performance knob is the number of MCTS iterations, which directly trades
off latency vs play quality.

LATENCY MODEL — DEPTH-AWARE:
==================================================
Per-iteration hardware latency depends on the MCTS tree depth at that
iteration, because Selection performs ONE CAM lookup per node descended,
and Backprop walks the path doing one SRAM read-modify-write per node.

  - Selection:     2 ns + 1 ns × E[depth]
  - Expansion:     2 ns + 1 ns SRAM access = 3 ns           (one expansion/iter)
  - Rollout:       14 ns (DAC + crossbar + ADC, parallel)
  - Backprop:      (2 ns + 1 ns SRAM access) × E[depth] = 3 ns × E[depth]
  - FSM:           4 × 1 ns transitions = 4 ns
  -------------------------------------------------------------
  Total:           23 + 4 × E[depth]   ns per iteration

  E[depth] = 1 + log_{N²}(iterations)  — fitted from SST measurements;
  see accelerator_api.expected_path_depth().

For typical configs (depth ≈ 2–3): ~31–35 ns/iter.
For 2×2 medium with depth ≈ 4.5: ~41 ns/iter.

The legacy "26 ns/iter" approximation (= 23 + 4×~0.75) implicitly assumed
a flat depth of ~1, which made the analytical mode silently agree with a
depth-blind SST simulator. Both modes are now genuinely independent and
agree to within ~5% across the 6 design points we have measured.

DEPRECATED FIELDS (kept for back-compat, not used at runtime):
  - 'expected_latency_us', 'expected_energy_nj' in each per-board dict
    were precomputed using the old `× 26 ns / 1000` formula. They are
    OUT OF DATE relative to the current depth-aware analytical model.
    Use accelerator_api.estimate(..., mode='analytical') for live values.

Usage:
    from py_sst_cpp.components.performance_config import get_performance_config, PerformanceLevel

    config = get_performance_config(board_size=5, performance=PerformanceLevel.MEDIUM)
    print(f"Iterations: {config['iterations']}")
"""

from enum import Enum


class PerformanceLevel(Enum):
    """Performance level enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Performance configurations for each board size
PERFORMANCE_CONFIGS = {
    # 2x2 Board Configuration
    # Hardware latency: iterations × 26 ns / 1000 = μs
    2: {
        PerformanceLevel.LOW: {
            'iterations': 50,
            'exploration_constant': 1.0,

            'rollout_depth': 10,
            'description': 'Fast search, weak play',
            'expected_latency_us': 1.3,      # 50 × 26 ns = 1.3 μs
            'expected_energy_nj': 0.12,      # ~0.09 mW × 1.3 μs
            'play_strength': 'Weak'
        },
        PerformanceLevel.MEDIUM: {
            'iterations': 200,
            'exploration_constant': 1.414,

            'rollout_depth': 10,
            'description': 'Balanced search, medium play',
            'expected_latency_us': 5.2,      # 200 × 26 ns = 5.2 μs
            'expected_energy_nj': 0.47,
            'play_strength': 'Medium'
        },
        PerformanceLevel.HIGH: {
            'iterations': 1000,
            'exploration_constant': 1.414,

            'rollout_depth': 10,
            'description': 'Deep search, strong play',
            'expected_latency_us': 26,       # 1000 × 26 ns = 26 μs
            'expected_energy_nj': 2.3,
            'play_strength': 'Strong'
        }
    },

    # 3x3 Board Configuration
    # Hardware latency: iterations × 26 ns / 1000 = μs
    3: {
        PerformanceLevel.LOW: {
            'iterations': 75,
            'exploration_constant': 1.0,

            'rollout_depth': 15,
            'description': 'Fast search, weak play',
            'expected_latency_us': 1.95,     # 75 × 26 ns = 1.95 μs
            'expected_energy_nj': 0.5,
            'play_strength': 'Weak'
        },
        PerformanceLevel.MEDIUM: {
            'iterations': 500,
            'exploration_constant': 1.414,

            'rollout_depth': 15,
            'description': 'Balanced search, medium play',
            'expected_latency_us': 13,       # 500 × 26 ns = 13 μs
            'expected_energy_nj': 3.4,
            'play_strength': 'Medium'
        },
        PerformanceLevel.HIGH: {
            'iterations': 5000,
            'exploration_constant': 1.414,

            'rollout_depth': 12,
            'description': 'Deep search, strong play',
            'expected_latency_us': 130,      # 5000 × 26 ns = 130 μs
            'expected_energy_nj': 34,
            'play_strength': 'Strong'
        }
    },

    # 5x5 Board Configuration
    # Hardware latency: iterations × 26 ns / 1000 = μs
    5: {
        PerformanceLevel.LOW: {
            'iterations': 100,
            'exploration_constant': 1.0,

            'rollout_depth': 25,
            'description': 'Fast search, weak play',
            'expected_latency_us': 2.6,      # 100 × 26 ns = 2.6 μs
            'expected_energy_nj': 1.5,
            'play_strength': 'Weak-Medium'
        },
        PerformanceLevel.MEDIUM: {
            'iterations': 1000,
            'exploration_constant': 1.414,

            'rollout_depth': 25,
            'description': 'Balanced search, medium play',
            'expected_latency_us': 26,       # 1000 × 26 ns = 26 μs
            'expected_energy_nj': 15,
            'play_strength': 'Medium-Strong'
        },
        PerformanceLevel.HIGH: {
            'iterations': 10000,
            'exploration_constant': 1.414,

            'rollout_depth': 15,
            'description': 'Deep search, strong play',
            'expected_latency_us': 260,      # 10000 × 26 ns = 260 μs
            'expected_energy_nj': 150,
            'play_strength': 'Very Strong'
        }
    },

    # 8x8 Board Configuration
    # Hardware latency: iterations × 26 ns / 1000 = μs
    8: {
        PerformanceLevel.LOW: {
            'iterations': 400,
            'exploration_constant': 1.0,
            'rollout_depth': 40,
            'description': 'Fast search, weak play',
            'expected_latency_us': 10.4,     # 400 × 26 ns = 10.4 μs
            'expected_energy_nj': 90,
            'play_strength': 'Weak'
        },
        PerformanceLevel.MEDIUM: {
            'iterations': 4000,
            'exploration_constant': 1.414,
            'rollout_depth': 40,
            'description': 'Balanced search, medium play',
            'expected_latency_us': 104,      # 4000 × 26 ns = 104 μs
            'expected_energy_nj': 900,
            'play_strength': 'Medium'
        },
        PerformanceLevel.HIGH: {
            'iterations': 40000,
            'exploration_constant': 1.414,
            'rollout_depth': 25,
            'description': 'Deep search, strong play',
            'expected_latency_us': 1040,     # 40000 × 26 ns = 1040 μs
            'expected_energy_nj': 9000,
            'play_strength': 'Strong'
        }
    },

    # 9x9 Board Configuration
    # Hardware latency: iterations × 26 ns / 1000 = μs
    9: {
        PerformanceLevel.LOW: {
            'iterations': 500,
            'exploration_constant': 1.0,

            'rollout_depth': 40,
            'description': 'Fast search, weak play',
            'expected_latency_us': 13,       # 500 × 26 ns = 13 μs
            'expected_energy_nj': 115,       # ~88 mW × 13 μs / 10
            'play_strength': 'Weak'
        },
        PerformanceLevel.MEDIUM: {
            'iterations': 5000,
            'exploration_constant': 1.414,

            'rollout_depth': 40,
            'description': 'Balanced search, medium play',
            'expected_latency_us': 130,      # 5000 × 26 ns = 130 μs
            'expected_energy_nj': 1150,      # ~88 mW × 130 μs / 10
            'play_strength': 'Medium'
        },
        PerformanceLevel.HIGH: {
            'iterations': 50000,
            'exploration_constant': 1.414,

            'rollout_depth': 25,
            'description': 'Deep search, strong play',
            'expected_latency_us': 1300,     # 50000 × 26 ns = 1300 μs = 1.3 ms
            'expected_energy_nj': 11500,     # ~88 mW × 1300 μs / 10
            'play_strength': 'Strong'
        }
    },

    # 11x11 Board Configuration
    # Hardware latency: iterations × 26 ns / 1000 = μs
    11: {
        PerformanceLevel.LOW: {
            'iterations': 750,
            'exploration_constant': 1.0,
            'rollout_depth': 50,
            'description': 'Fast search, weak play',
            'expected_latency_us': 19.5,     # 750 × 26 ns = 19.5 μs
            'expected_energy_nj': 160,
            'play_strength': 'Weak'
        },
        PerformanceLevel.MEDIUM: {
            'iterations': 6000,
            'exploration_constant': 1.414,
            'rollout_depth': 50,
            'description': 'Balanced search, medium play',
            'expected_latency_us': 156,      # 6000 × 26 ns = 156 μs
            'expected_energy_nj': 1280,
            'play_strength': 'Medium'
        },
        PerformanceLevel.HIGH: {
            'iterations': 60000,
            'exploration_constant': 1.414,
            'rollout_depth': 35,
            'description': 'Deep search, strong play',
            'expected_latency_us': 1560,     # 60000 × 26 ns = 1560 μs
            'expected_energy_nj': 12800,
            'play_strength': 'Strong'
        }
    },

    # 13x13 Board Configuration
    # Hardware latency: iterations × 26 ns / 1000 = μs
    13: {
        PerformanceLevel.LOW: {
            'iterations': 1000,
            'exploration_constant': 1.0,

            'rollout_depth': 60,
            'description': 'Fast search, weak play',
            'expected_latency_us': 26,       # 1000 × 26 ns = 26 μs
            'expected_energy_nj': 210,
            'play_strength': 'Weak'
        },
        PerformanceLevel.MEDIUM: {
            'iterations': 7500,
            'exploration_constant': 1.414,

            'rollout_depth': 60,
            'description': 'Balanced search, medium play',
            'expected_latency_us': 195,      # 7500 × 26 ns = 195 μs
            'expected_energy_nj': 1580,
            'play_strength': 'Medium'
        },
        PerformanceLevel.HIGH: {
            'iterations': 75000,
            'exploration_constant': 1.414,

            'rollout_depth': 40,
            'description': 'Deep search, strong play',
            'expected_latency_us': 1950,     # 75000 × 26 ns = 1950 μs = 1.95 ms
            'expected_energy_nj': 15800,
            'play_strength': 'Strong'
        }
    },

    # 15x15 Board Configuration
    # Hardware latency: iterations × 26 ns / 1000 = μs
    15: {
        PerformanceLevel.LOW: {
            'iterations': 1500,
            'exploration_constant': 1.0,
            'rollout_depth': 65,
            'description': 'Fast search, weak play',
            'expected_latency_us': 39,       # 1500 × 26 ns = 39 μs
            'expected_energy_nj': 320,
            'play_strength': 'Weak'
        },
        PerformanceLevel.MEDIUM: {
            'iterations': 8500,
            'exploration_constant': 1.414,
            'rollout_depth': 65,
            'description': 'Balanced search, medium play',
            'expected_latency_us': 221,      # 8500 × 26 ns = 221 μs
            'expected_energy_nj': 1800,
            'play_strength': 'Medium'
        },
        PerformanceLevel.HIGH: {
            'iterations': 85000,
            'exploration_constant': 1.414,
            'rollout_depth': 45,
            'description': 'Deep search, strong play',
            'expected_latency_us': 2210,     # 85000 × 26 ns = 2210 μs
            'expected_energy_nj': 18000,
            'play_strength': 'Strong'
        }
    },

    # 19x19 Board Configuration
    # Hardware latency: iterations × 26 ns / 1000 = μs
    19: {
        PerformanceLevel.LOW: {
            'iterations': 2000,
            'exploration_constant': 1.0,

            'rollout_depth': 80,
            'description': 'Fast search, very weak play',
            'expected_latency_us': 52,       # 2000 × 26 ns = 52 μs
            'expected_energy_nj': 1560,
            'play_strength': 'Very Weak'
        },
        PerformanceLevel.MEDIUM: {
            'iterations': 10000,
            'exploration_constant': 1.414,

            'rollout_depth': 80,
            'description': 'Balanced search, weak play',
            'expected_latency_us': 260,      # 10000 × 26 ns = 260 μs
            'expected_energy_nj': 7800,
            'play_strength': 'Weak'
        },
        PerformanceLevel.HIGH: {
            'iterations': 100000,
            'exploration_constant': 1.414,

            'rollout_depth': 50,
            'description': 'Deep search, competitive play',
            'expected_latency_us': 2600,     # 100000 × 26 ns = 2600 μs = 2.6 ms
            'expected_energy_nj': 78000,
            'play_strength': 'Competitive'
        }
    }
}


def get_performance_config(board_size, performance):
    """
    Get performance configuration for a given board size and performance level.

    Args:
        board_size (int): Board size (2, 3, 5, 9, 13, or 19)
        performance (PerformanceLevel or str): Performance level

    Returns:
        dict: Performance configuration dictionary

    Raises:
        ValueError: If board_size or performance level is invalid
    """
    if board_size not in PERFORMANCE_CONFIGS:
        raise ValueError(f"Invalid board size: {board_size}. Must be 2, 3, 5, 8, 9, 11, 13, 15, or 19.")

    # Convert string to enum if needed
    if isinstance(performance, str):
        try:
            performance = PerformanceLevel(performance.lower())
        except ValueError:
            raise ValueError(f"Invalid performance level: {performance}. Must be 'low', 'medium', or 'high'.")

    if not isinstance(performance, PerformanceLevel):
        raise ValueError(f"Performance must be PerformanceLevel enum or string")

    return PERFORMANCE_CONFIGS[board_size][performance].copy()


def get_all_configs(board_size):
    """
    Get all performance configurations for a given board size.

    Args:
        board_size (int): Board size (2, 3, 5, 9, 13, or 19)

    Returns:
        dict: Dictionary mapping PerformanceLevel to configuration
    """
    if board_size not in PERFORMANCE_CONFIGS:
        raise ValueError(f"Invalid board size: {board_size}. Must be 2, 3, 5, 8, 9, 11, 13, 15, or 19.")

    return PERFORMANCE_CONFIGS[board_size].copy()


def print_performance_specs(board_size=None):
    """
    Print performance specifications for board sizes.

    Args:
        board_size (int, optional): Board size to print. If None, prints all.
    """
    if board_size is not None:
        board_sizes = [board_size]
    else:
        board_sizes = [2, 3, 5, 8, 9, 11, 13, 15, 19]

    for size in board_sizes:
        print(f"\n{'='*80}")
        print(f"{size}x{size} Board - Performance Levels")
        print(f"{'='*80}")

        for perf_level in [PerformanceLevel.LOW, PerformanceLevel.MEDIUM, PerformanceLevel.HIGH]:
            performance_config = get_performance_config(size, perf_level)
            print(f"\n{perf_level.value.upper()}:")
            print(f"  Description:         {performance_config['description']}")
            print(f"  MCTS Iterations:     {performance_config['iterations']:,}")
            print(f"  Exploration C:       {performance_config['exploration_constant']:.3f}")
            print(f"  Rollout Depth:       {performance_config['rollout_depth']} moves")
            print(f"  Expected Latency:    {performance_config['expected_latency_us']:.1f} μs")
            print(f"  Expected Energy:     {performance_config['expected_energy_nj']:.1f} nJ")
            print(f"  Play Strength:       {performance_config['play_strength']}")


def print_comparison_table(board_size):
    """
    Print comparison table for all performance levels of a board size.

    Args:
        board_size (int): Board size (2, 3, 5, 9, 13, or 19)
    """
    print(f"\n{board_size}x{board_size} Board - Performance Comparison")
    print(f"{'='*100}")
    print(f"{'Level':<10} {'Iter':>8} {'Explor':>7} {'Depth':>7} {'Latency':>10} {'Energy':>10} {'Strength':<15}")
    print(f"{'-'*90}")

    for perf_level in [PerformanceLevel.LOW, PerformanceLevel.MEDIUM, PerformanceLevel.HIGH]:
        performance_config = get_performance_config(board_size, perf_level)
        print(f"{perf_level.value.upper():<10} "
              f"{performance_config['iterations']:>8,} "
              f"{performance_config['exploration_constant']:>7.3f} "
              f"{performance_config['rollout_depth']:>7} "
              f"{performance_config['expected_latency_us']:>9.1f}μs "
              f"{performance_config['expected_energy_nj']:>9.1f}nJ "
              f"{performance_config['play_strength']:<15}")
    print(f"{'='*90}\n")


# Quick reference constants for common use
ITERATIONS_5X5_LOW = 100
ITERATIONS_5X5_MEDIUM = 1000
ITERATIONS_5X5_HIGH = 10000

ITERATIONS_8X8_LOW = 400
ITERATIONS_8X8_MEDIUM = 4000
ITERATIONS_8X8_HIGH = 40000

ITERATIONS_9X9_LOW = 500
ITERATIONS_9X9_MEDIUM = 5000
ITERATIONS_9X9_HIGH = 50000

ITERATIONS_11X11_LOW = 750
ITERATIONS_11X11_MEDIUM = 6000
ITERATIONS_11X11_HIGH = 60000

ITERATIONS_13X13_LOW = 1000
ITERATIONS_13X13_MEDIUM = 7500
ITERATIONS_13X13_HIGH = 75000

ITERATIONS_15X15_LOW = 1500
ITERATIONS_15X15_MEDIUM = 8500
ITERATIONS_15X15_HIGH = 85000

ITERATIONS_19X19_LOW = 2000
ITERATIONS_19X19_MEDIUM = 10000
ITERATIONS_19X19_HIGH = 100000


if __name__ == "__main__":
    # Demo usage
    print("IMC-MCTS Accelerator - Performance Configuration")
    print("="*80)

    # Print all specifications
    print_performance_specs()

    # Print comparison tables
    print("\n" + "="*80)
    print("COMPARISON TABLES")
    print("="*80)
    for size in [2, 3, 5, 9, 13, 19]:
        print_comparison_table(size)

    # Example usage
    print("\n" + "="*80)
    print("USAGE EXAMPLE")
    print("="*80)

    config = get_performance_config(5, PerformanceLevel.MEDIUM)
    print(f"\n5x5 Board, MEDIUM performance:")
    print(f"  Iterations: {config['iterations']}")
    print(f"  Exploration constant: {config['exploration_constant']}")
    print(f"  Expected latency: {config['expected_latency_us']} μs")

    # Using string
    config2 = get_performance_config(9, "high")
    print(f"\n9x9 Board, HIGH performance:")
    print(f"  Iterations: {config2['iterations']}")
    print(f"  Play strength: {config2['play_strength']}")
