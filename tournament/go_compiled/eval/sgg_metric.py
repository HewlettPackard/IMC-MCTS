# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Search Guidance Gain (SGG) Metric.

                P_nn - P_rand
SGG(game) = ─────────────────────────
             log2(N) * sqrt(B) / K_REF

Where:
    P_nn   : NN-MCTS performance (H2H win rate)
    P_rand : Random-MCTS baseline (0.50 for 2-player H2H)
    N      : MCTS iteration count
    B      : Effective playing-area cells (81 for 9x9 Go)
    K_REF  : log2(50) * sqrt(64) ~ 45.15

Interpretation:
    SGG > +0.05 : GREEN  -- NN helps meaningfully
    SGG in [-0.05, +0.05] : YELLOW -- marginal / noise
    SGG < -0.05 : RED    -- NN hurts
"""

import math
from typing import Dict, Any

# Reference constant: log2(50) * sqrt(64) ~ 45.15
K_REF = math.log2(50) * math.sqrt(64)


def compute_sgg(nn_win_rate: float,
                rand_win_rate: float = 0.50,
                iterations: int = 2000,
                board_cells: int = 81) -> Dict[str, Any]:
    """
    Compute Search Guidance Gain for a Go IMC-MCTS configuration.

    Args:
        nn_win_rate: NN-MCTS H2H win rate vs random MCTS (0.0 to 1.0)
        rand_win_rate: Random MCTS baseline (default 0.50)
        iterations: MCTS iterations used
        board_cells: Effective board cells (81 for 9x9 Go)

    Returns:
        Dict with raw_lift, sgg, verdict, and computation details
    """
    num_iterations = max(iterations, 2)
    num_board_cells = board_cells

    # SGG = (P_nn - P_rand) / (log2(N) * sqrt(B) / K_REF).
    raw_lift = nn_win_rate - rand_win_rate
    log2_N = math.log2(num_iterations)
    sqrt_B = math.sqrt(num_board_cells)

    denominator = log2_N * sqrt_B / K_REF
    sgg = raw_lift / denominator if denominator != 0 else 0.0

    if sgg > 0.05:
        verdict = "GREEN"
    elif sgg < -0.05:
        verdict = "RED"
    else:
        verdict = "YELLOW"

    return {
        'raw_lift': round(raw_lift, 4),
        'log2_N': round(log2_N, 4),
        'sqrt_B': round(sqrt_B, 4),
        'K_REF': round(K_REF, 4),
        'denominator': round(denominator, 4),
        'sgg': round(sgg, 4),
        'verdict': verdict,
        'iterations': iterations,
        'board_cells': board_cells,
    }


def compute_sgg_for_configs(results: Dict[str, float],
                            rand_key: str = "MCTS-Rollout",
                            iterations: int = 2000) -> Dict[str, Dict]:
    """
    Compute SGG for multiple configurations given H2H win rates.

    Args:
        results: {config_name: h2h_win_rate_vs_rollout}
        rand_key: Name of the random rollout baseline config
        iterations: MCTS iterations

    Returns:
        {config_name: sgg_result_dict}
    """
    sgg_results = {}
    for name, win_rate in results.items():
        if name == rand_key:
            continue
        sgg_results[name] = compute_sgg(win_rate, 0.50, iterations)
    return sgg_results


def print_sgg_table(sgg_results: Dict[str, Dict]):
    """Pretty-print SGG results."""
    print(f"\n{'Config':<25}{'Win Rate':<10}{'Raw Lift':<10}{'SGG':<10}{'Verdict':<10}")
    print("-" * 65)
    sorted_results = sorted(
        sgg_results.items(),
        key=lambda result_entry: result_entry[1]['sgg'],
        reverse=True
    )
    for name, result in sorted_results:
        win_rate = result['raw_lift'] + 0.50
        print(f"{name:<25}{win_rate:<10.3f}{result['raw_lift']:<10.4f}{result['sgg']:<10.4f}{result['verdict']:<10}")
