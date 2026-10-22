#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Cross-Domain Results Table Generator.

Runs all 13 games with MCTS, collects behavioral metrics, pulls hardware
metrics from accelerator_api.estimate(), and outputs a unified CSV matching
the paper's Table format (Section 6.4).

With --nn, also runs NN-guided MCTS (via CrossbarEvaluator) and compares
quality metrics against random-rollout MCTS.  For 2-player games this
includes head-to-head matches (NN-MCTS vs Random-MCTS).

Usage:
    python generalizability/sweeps/run_cross_domain.py --num-games 20 --output-csv cross_domain_results.csv
    python generalizability/sweeps/run_cross_domain.py --num-games 5 --nn --output-csv cross_domain_nn.csv
"""

import argparse
import sys
import time
import csv

from generalizability.games import GAME_REGISTRY, APP_BOARD_SIZES, GAME_ITERATIONS
from core.algorithm.mcts_engine import MCTSEngine
from generalizability.evaluation.normalized_metric import compute_sgg, EFFECTIVE_CELLS

# Domain classification for the results table
GAME_DOMAINS = {
    "go": "Board Games",
    "hex": "Board Games",
    "gomoku": "Board Games",
    "havannah": "Board Games",
    "othello": "Board Games",
    "connect_four": "Board Games",
    "pente": "Board Games",
    "breakthrough": "Board Games",
    "protein_folding": "Optimization",
    "nonograms": "Puzzles",
    "frozen_lake": "Navigation",
    "minigrid": "Navigation",
    "minesweeper": "Puzzles",
}

# Encoding description for the results table
GAME_ENCODINGS = {
    "go": "1/2 stone + meta",
    "hex": "1/2 stone",
    "gomoku": "1/2 stone",
    "havannah": "1/2 stone (hex mask)",
    "othello": "1/2 stone",
    "connect_four": "1/2 stone (gravity)",
    "pente": "1/2 stone + captures",
    "breakthrough": "1/2 piece",
    "protein_folding": "1=H, 2=P",
    "nonograms": "0/1/2 cell state",
    "frozen_lake": "0-3 cell type",
    "minigrid": "0-3 cell type",
    "minesweeper": "0/1/2 cell state",
}

# Primary quality metric name per game
PRIMARY_METRIC = {
    "go": "avg_total_captures",
    "hex": "avg_move_efficiency",
    "gomoku": "avg_move_efficiency",
    "havannah": "mode_win_type",
    "othello": "avg_piece_differential",
    "connect_four": "avg_move_efficiency",
    "pente": "avg_capture_pairs_p1",
    "breakthrough": "avg_pieces_remaining_p1",
    "protein_folding": "avg_optimality_ratio",
    "nonograms": "avg_accuracy",
    "frozen_lake": "avg_path_efficiency",
    "minigrid": "avg_path_efficiency",
    "minesweeper": "avg_cells_revealed_pct",
}


def run_behavioral(game_key, iterations, num_games, eval_fn=None):
    """Run MCTS games and collect behavioral stats + metrics.

    If *eval_fn* is provided it is passed to MCTSEngine to replace random
    rollouts with NN evaluation.
    """
    game = GAME_REGISTRY[game_key]
    engine = MCTSEngine(game, iterations=iterations, eval_fn=eval_fn)
    results = []

    for _ in range(num_games):
        record = engine.play_game()
        results.append(record)

    # Basic stats
    game_lengths = [r["game_length"] for r in results]
    avg_length = sum(game_lengths) / len(game_lengths)

    if game.num_players == 2:
        wins = sum(1 for r in results if r["result_p1"] == 1.0)
        draws = sum(1 for r in results if r["result_p1"] == 0.5)
        losses = sum(1 for r in results if r["result_p1"] == 0.0)
        win_rate = wins / num_games
        avg_score = sum(r["result_p1"] for r in results) / num_games
    else:
        wins = sum(1 for r in results if r["result_p1"] >= 0.5)
        draws = 0
        losses = num_games - wins
        win_rate = wins / num_games
        avg_score = sum(r["result_p1"] for r in results) / num_games

    # Aggregate game-specific metrics
    all_metrics = [r.get("metrics", {}) for r in results]
    agg = {}
    if all_metrics:
        for key in all_metrics[0]:
            vals = [m[key] for m in all_metrics if key in m]
            if not vals:
                continue
            if isinstance(vals[0], (int, float)):
                agg[f"avg_{key}"] = sum(vals) / len(vals)
            else:
                from collections import Counter
                agg[f"mode_{key}"] = Counter(vals).most_common(1)[0][0]

    stats = {
        "game_key": game_key,
        "game": game.name,
        "board_size": game.board_size,
        "iterations": iterations,
        "num_games": num_games,
        "win_rate": win_rate,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "avg_length": avg_length,
        "avg_score": avg_score,
    }
    stats.update(agg)
    return stats


# ------------------------------------------------------------------
# Head-to-head (2-player): NN-MCTS vs Random-MCTS
# ------------------------------------------------------------------
def play_head_to_head(game_key, nn_engine, random_engine, num_games):
    """Play NN-MCTS against Random-MCTS for 2-player games.

    Half the games NN plays as P1, half as P2 (controls first-move advantage).
    Returns NN win/draw/loss counts and win rate.
    """
    game = GAME_REGISTRY[game_key]
    nn_wins, nn_draws, nn_losses = 0, 0, 0
    half = num_games // 2

    for i in range(num_games):
        nn_is_p1 = i < half
        board = game.initial_state()
        player = 1
        move_count = 0

        while not game.is_terminal(board) and move_count < 500:
            if (player == 1) == nn_is_p1:
                move = nn_engine.search(board, player)
            else:
                move = random_engine.search(board, player)
            board = game.apply_move(board, move, player)
            player = 3 - player
            move_count += 1

        result_p1 = game.get_result(board, 1)
        nn_result = result_p1 if nn_is_p1 else (1.0 - result_p1)

        if nn_result > 0.5:
            nn_wins += 1
        elif nn_result < 0.5:
            nn_losses += 1
        else:
            nn_draws += 1

    return {
        "nn_wins": nn_wins,
        "nn_draws": nn_draws,
        "nn_losses": nn_losses,
        "nn_win_rate": nn_wins / num_games if num_games else 0.0,
    }


# ------------------------------------------------------------------
# NN-vs-Random comparison driver
# ------------------------------------------------------------------
def run_nn_vs_random(game_key, iterations, num_games, eval_fn):
    """Run both random and NN MCTS, compare quality metrics.

    For 2-player games, also plays head-to-head matches.
    For 1-player games, compares quality metrics directly.
    """
    game = GAME_REGISTRY[game_key]

    # Random baseline
    rand_stats = run_behavioral(game_key, iterations, num_games, eval_fn=None)

    # NN-guided
    nn_stats = run_behavioral(game_key, iterations, num_games, eval_fn=eval_fn)

    # Primary metric comparison
    primary_key = PRIMARY_METRIC.get(game_key, "")
    rand_val = rand_stats.get(primary_key)
    nn_val = nn_stats.get(primary_key)

    result = {
        "game_key": game_key,
        "game": game.name,
        "board_size": game.board_size,
        "iterations": iterations,
        "num_games": num_games,
        "Random_Quality": _fmt_metric(rand_val),
        "NN_Quality": _fmt_metric(nn_val),
        "Quality_Metric": primary_key.replace("avg_", "").replace("mode_", ""),
    }

    # Compute improvement on game-specific metric
    if isinstance(rand_val, (int, float)) and isinstance(nn_val, (int, float)):
        if rand_val != 0:
            result["NN_Improvement"] = f"{(nn_val - rand_val) / abs(rand_val):+.1%}"
        else:
            result["NN_Improvement"] = f"{nn_val - rand_val:+.3f}"
    else:
        result["NN_Improvement"] = ""

    # Universal metrics (comparable across all games)
    result["Random_WinRate"] = f"{rand_stats['win_rate']:.1%}"
    result["NN_WinRate"] = f"{nn_stats['win_rate']:.1%}"
    result["Random_AvgScore"] = f"{rand_stats['avg_score']:.3f}"
    result["NN_AvgScore"] = f"{nn_stats['avg_score']:.3f}"
    score_lift = nn_stats["avg_score"] - rand_stats["avg_score"]
    result["Score_Lift"] = f"{score_lift:+.3f}"

    # Head-to-head for 2-player games
    if game.num_players == 2:
        nn_engine = MCTSEngine(game, iterations=iterations, eval_fn=eval_fn)
        rand_engine = MCTSEngine(game, iterations=iterations)
        h2h = play_head_to_head(game_key, nn_engine, rand_engine, num_games)
        result["H2H_NN_WinRate"] = f"{h2h['nn_win_rate']:.1%}"
        result["H2H_W_D_L"] = f"{h2h['nn_wins']}/{h2h['nn_draws']}/{h2h['nn_losses']}"
    else:
        result["H2H_NN_WinRate"] = ""
        result["H2H_W_D_L"] = ""

    # Compute Search Guidance Gain (SGG) -- normalized metric
    if game.num_players == 2:
        sgg_nn_perf = h2h['nn_win_rate']
        sgg_rand_perf = 0.50
    else:
        sgg_nn_perf = nn_stats['avg_score']
        sgg_rand_perf = rand_stats['avg_score']

    sgg = compute_sgg(game_key, sgg_nn_perf, sgg_rand_perf,
                       iterations, game.num_players)
    result["P_rand"] = f"{sgg_rand_perf:.3f}"
    result["P_nn"] = f"{sgg_nn_perf:.3f}"
    result["Raw_Lift"] = f"{sgg['raw_lift']:+.4f}"
    result["SGG"] = f"{sgg['sgg']:+.4f}"
    result["SGG_Verdict"] = sgg['verdict']
    result["Effective_Cells"] = sgg['effective_cells']

    return result


def _fmt_metric(val):
    if isinstance(val, float):
        return f"{val:.3f}"
    elif val is None:
        return ""
    return str(val)


def get_hardware_estimates(game_key, strength="medium"):
    """Get hardware estimates from accelerator_api."""
    try:
        from core.architecture.accelerator_api import estimate
        board_size = APP_BOARD_SIZES[game_key]
        result = estimate(board_size=board_size, play_strength=strength, mode="analytical")
        return {
            "area_mm2": result.area_mm2,
            "energy_uj": result.energy_uj,
            "latency_us": result.latency_us,
            "power_mw": result.power_mw,
        }
    except Exception as e:
        print(f"    [WARNING] Hardware estimate failed for {game_key}: {e}")
        return {
            "area_mm2": None,
            "energy_uj": None,
            "latency_us": None,
            "power_mw": None,
        }


def build_cross_domain_table(behavioral, hardware, nn_results=None):
    """Combine behavioral and hardware results into the paper table format.

    If *nn_results* is provided, adds Random_Quality, NN_Quality,
    NN_Improvement, and (for 2-player) H2H columns.
    """
    # Index NN results by game_key
    nn_by_key = {}
    if nn_results:
        for nr in nn_results:
            nn_by_key[nr["game_key"]] = nr

    rows = []
    for b in behavioral:
        gk = b["game_key"]
        hw = hardware.get(gk, {})
        primary_key = PRIMARY_METRIC.get(gk, "")
        primary_val = b.get(primary_key, "")

        row = {
            "Domain": GAME_DOMAINS.get(gk, ""),
            "Application": b["game"],
            "Encoding": GAME_ENCODINGS.get(gk, ""),
            "Board": f"{b['board_size']}x{b['board_size']}",
            "Crossbar": f"{b['board_size']}x{b['board_size']}",
            "MCTS_Iterations": b["iterations"],
            "Num_Games": b["num_games"],
            "Win_Rate": f"{b['win_rate']:.1%}",
            "W_D_L": f"{b['wins']}/{b['draws']}/{b['losses']}",
            "Avg_Length": f"{b['avg_length']:.1f}",
            "Avg_Score": f"{b['avg_score']:.3f}",
            "Area_mm2": f"{hw.get('area_mm2', 0):.4f}" if hw.get("area_mm2") else "",
            "Energy_uJ": f"{hw.get('energy_uj', 0):.3f}" if hw.get("energy_uj") else "",
            "Latency_us": f"{hw.get('latency_us', 0):.2f}" if hw.get("latency_us") else "",
            "Power_mW": f"{hw.get('power_mw', 0):.2f}" if hw.get("power_mw") else "",
            "Quality_Metric": primary_key.replace("avg_", "").replace("mode_", ""),
            "Quality_Value": f"{primary_val:.3f}" if isinstance(primary_val, float) else str(primary_val),
        }

        # Append NN comparison columns
        nr = nn_by_key.get(gk)
        nn_cols = [
            "Random_Quality", "NN_Quality", "NN_Improvement",
            "Random_WinRate", "NN_WinRate",
            "Random_AvgScore", "NN_AvgScore", "Score_Lift",
            "H2H_NN_WinRate", "H2H_W_D_L",
            "P_rand", "P_nn", "Raw_Lift", "SGG", "SGG_Verdict",
            "Effective_Cells",
        ]
        if nr is not None:
            for col in nn_cols:
                row[col] = nr.get(col, "")
        elif nn_results is not None:
            for col in nn_cols:
                row[col] = ""

        rows.append(row)
    return rows


def print_cross_domain_table(rows):
    """Print the cross-domain table in a readable format."""
    has_nn = any("NN_Quality" in r and r["NN_Quality"] for r in rows)
    has_sgg = any("SGG" in r and r.get("SGG") for r in rows)

    header = (
        f"{'Domain':<14} {'Application':<18} {'Board':>5} "
        f"{'WinRate':>8} {'AvgScore':>8} "
        f"{'Area(mm2)':>10} {'Energy(uJ)':>11} {'Latency(us)':>12} "
        f"{'Quality':>12} {'Value':>10}"
    )
    if has_nn:
        header += (
            f"  {'RandQ':>8} {'NN_Q':>8} {'Impr':>8}"
            f"  {'R_Win%':>7} {'N_Win%':>7} {'R_Scr':>6} {'N_Scr':>6} {'Lift':>7}"
            f"  {'H2H_Win':>8}"
        )
    if has_sgg:
        header += f"  {'SGG':>7} {'Verdict':>8}"
    sep = "-" * len(header)

    print("\n" + "=" * len(header))
    print("Accelerator Cross-Domain Results Table (Section 6.4)")
    print("=" * len(header))
    print(header)
    print(sep)

    current_domain = None
    for r in rows:
        if r["Domain"] != current_domain:
            if current_domain is not None:
                print(sep)
            current_domain = r["Domain"]
        line = (
            f"{r['Domain']:<14} {r['Application']:<18} {r['Board']:>5} "
            f"{r['Win_Rate']:>8} {r['Avg_Score']:>8} "
            f"{r['Area_mm2']:>10} {r['Energy_uJ']:>11} {r['Latency_us']:>12} "
            f"{r['Quality_Metric']:>12} {r['Quality_Value']:>10}"
        )
        if has_nn:
            line += (
                f"  {r.get('Random_Quality', ''):>8} "
                f"{r.get('NN_Quality', ''):>8} "
                f"{r.get('NN_Improvement', ''):>8}"
                f"  {r.get('Random_WinRate', ''):>7} "
                f"{r.get('NN_WinRate', ''):>7} "
                f"{r.get('Random_AvgScore', ''):>6} "
                f"{r.get('NN_AvgScore', ''):>6} "
                f"{r.get('Score_Lift', ''):>7}"
                f"  {r.get('H2H_NN_WinRate', ''):>8}"
            )
        if has_sgg:
            line += (
                f"  {r.get('SGG', ''):>7} "
                f"{r.get('SGG_Verdict', ''):>8}"
            )
        print(line)
    print(sep)


def save_cross_domain_csv(rows, filepath):
    """Save cross-domain table to CSV."""
    if not rows:
        return
    keys = list(rows[0].keys())
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCross-domain results saved to: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Accelerator Cross-Domain Results Table Generator"
    )
    parser.add_argument(
        "--iterations", type=int, default=None,
        help="Flat MCTS iteration override (default: use per-game scaled iterations)"
    )
    parser.add_argument(
        "--num-games", type=int, default=20,
        help="Number of games per application (default: 20)"
    )
    parser.add_argument(
        "--output-csv", type=str, default="cross_domain_results.csv",
        help="Output CSV filepath (default: cross_domain_results.csv)"
    )
    parser.add_argument(
        "--hw-strength", type=str, default="medium",
        choices=["low", "medium", "high"],
        help="Hardware estimation play strength (default: medium)"
    )
    parser.add_argument(
        "--nn", action="store_true",
        help="Enable NN-vs-Random comparison using CrossbarEvaluator"
    )
    parser.add_argument(
        "--weights-source", type=str, default="auto",
        choices=["auto", "selfplay", "coach"],
        help="Weight source for NN evaluation (default: auto)"
    )
    parser.add_argument(
        "--use-designed-iters", action="store_true",
        help="Force per-game designed iteration counts (overrides --iterations)"
    )
    parser.add_argument(
        "--games", nargs="+", default=None,
        help="Run only these games (default: all 13)"
    )
    args = parser.parse_args()

    # --use-designed-iters overrides any --iterations value
    if args.use_designed_iters:
        args.iterations = None

    # Filter games if requested
    game_keys = list(GAME_REGISTRY.keys())
    if args.games:
        game_keys = [g for g in args.games if g in GAME_REGISTRY]
        if not game_keys:
            print(f"ERROR: no valid games in {args.games}")
            print(f"Available: {list(GAME_REGISTRY.keys())}")
            sys.exit(1)

    total_start = time.time()

    # 1. Run behavioral evaluation
    print("=" * 60)
    print(f"Phase 1: Behavioral Evaluation ({len(game_keys)} games)")
    print("=" * 60)
    behavioral_results = []
    for game_key in game_keys:
        game = GAME_REGISTRY[game_key]
        iters = args.iterations if args.iterations is not None else GAME_ITERATIONS[game_key]
        print(f"  {game.name:<20} ({iters} iter x {args.num_games} games) ...",
              end=" ", flush=True)
        t0 = time.time()
        stats = run_behavioral(game_key, iters, args.num_games)
        elapsed = time.time() - t0
        print(f"done ({elapsed:.1f}s)")
        behavioral_results.append(stats)

    # 2. Collect hardware estimates
    print(f"\n{'=' * 60}")
    print("Phase 2: Hardware Estimation")
    print("=" * 60)
    hardware_results = {}
    for game_key in game_keys:
        print(f"  Estimating hardware for {game_key}...", end=" ", flush=True)
        hw = get_hardware_estimates(game_key, args.hw_strength)
        hardware_results[game_key] = hw
        if hw.get("area_mm2"):
            print(f"area={hw['area_mm2']:.4f} mm2, energy={hw['energy_uj']:.3f} uJ")
        else:
            print("(no estimate)")

    # 3. NN-vs-Random comparison (optional)
    nn_results = None
    if args.nn:
        print(f"\n{'=' * 60}")
        print("Phase 3: NN-vs-Random Comparison")
        print("=" * 60)
        from generalizability.evaluation.crossbar_evaluator import make_evaluator
        nn_results = []
        for game_key in game_keys:
            game = GAME_REGISTRY[game_key]
            iters = args.iterations if args.iterations is not None else GAME_ITERATIONS[game_key]
            print(f"  {game.name:<20} NN vs Random ({iters} iter x {args.num_games} games) ...",
                  end=" ", flush=True)
            t0 = time.time()
            try:
                ev = make_evaluator(game_key, weights_source=args.weights_source)
                nr = run_nn_vs_random(game_key, iters, args.num_games, ev)
                nn_results.append(nr)
                parts = [f"rand={nr['Random_Quality']}", f"nn={nr['NN_Quality']}"]
                if nr.get("NN_Improvement"):
                    parts.append(f"impr={nr['NN_Improvement']}")
                if nr.get("Score_Lift"):
                    parts.append(f"lift={nr['Score_Lift']}")
                if nr.get("H2H_NN_WinRate"):
                    parts.append(f"h2h={nr['H2H_NN_WinRate']}")
                elapsed = time.time() - t0
                print(f"{', '.join(parts)} ({elapsed:.1f}s)")
            except Exception as e:
                elapsed = time.time() - t0
                print(f"FAILED: {e} ({elapsed:.1f}s)")

    # 4. Build and output cross-domain table
    phase_label = "Phase 4" if args.nn else "Phase 3"
    print(f"\n{'=' * 60}")
    print(f"{phase_label}: Cross-Domain Table")
    print("=" * 60)
    table_rows = build_cross_domain_table(behavioral_results, hardware_results,
                                          nn_results)
    print_cross_domain_table(table_rows)

    total_elapsed = time.time() - total_start
    print(f"\nTotal elapsed time: {total_elapsed:.1f}s")

    # Save CSV
    save_cross_domain_csv(table_rows, args.output_csv)


if __name__ == "__main__":
    main()
