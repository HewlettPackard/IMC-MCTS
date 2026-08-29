#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
 Round-robin tournament: 7 players.
KataGo, Pachi, IMC-strong, GnuGo-L10, Michi-C, IMC-weak, Random.
Saves game-by-game ELO progression for plotting.
"""

import sys
import os
import time
import json
import math
import re
import random
import ctypes as ct
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "training"))
from selfplay_iterative import (
    load_engine, GTPProcess, board_hash_fnv, score_position,
    move_to_gtp, gtp_to_move,
    BOARD_SIZE, NUM_CELLS, PASS_MOVE, MAX_MOVES,
)

# ──────────── Config ────────────
OUTPUT_DIR = "tournament_main"
GAMES_PER_MATCHUP = 50
from paths import GNUGO_BIN, KATAGO_BIN, KATAGO_MODEL, KATAGO_CFG
PACHI_BIN = os.path.join(SCRIPT_DIR, "tools", "pachi_9x9")  # local 9x9-tuned variant
IMC_LIB_PATH = os.path.join(SCRIPT_DIR, "engine", "imc_mcts.so")
MICHI_LIB_PATH = os.path.join(SCRIPT_DIR, "engine", "michi_c.so")

# Player types:
#   "gtp"    - external GTP process (KataGo, Pachi, GnuGo)
#   "imc"    - IMC-MCTS C engine with NN weights
#   "michi"  - Michi-C random-rollout MCTS (no NN)
#   "random" - uniform random legal moves
PLAYERS = [
    {"name": "KataGo",     "type": "gtp",
     "cmd": [KATAGO_BIN, "gtp", "-model", KATAGO_MODEL, "-config", KATAGO_CFG]},
    {"name": "Pachi-UCT",  "type": "gtp",
     "cmd": [PACHI_BIN, "--nopatterns", "-t", "~500", "-d", "0", "no_tbook", "threads=4"]},
    {"name": "IMC-strong",  "type": "imc",
     "weights": "weights/pachi_spar/best_model.bin", "sims": 500},
    {"name": "GnuGo-L10",  "type": "gtp",
     "cmd": [GNUGO_BIN, "--mode", "gtp", "--level", "10"]},
    {"name": "Michi-C",     "type": "michi", "sims": 200},
    {"name": "IMC-weak",    "type": "imc",
     "weights": "weights/60pct/weights.bin", "sims": 500},
    {"name": "Random",      "type": "random"},
]

# ──────────── ELO ────────────
K_FACTOR = 32
INIT_ELO = 1500

class ELOTracker:
    def __init__(self, names):
        self.ratings = {player_name: float(INIT_ELO) for player_name in names}
        self.history = []
        self.records = {
            player_name: {"wins": 0, "losses": 0, "draws": 0}
            for player_name in names
        }

    def update(self, player_a, player_b, result_a, game_id, matchup):
        rating_a = self.ratings[player_a]
        rating_b = self.ratings[player_b]

        # E_A = 1 / (1 + 10^((R_B - R_A) / 400)).
        expected_a = 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))
        expected_b = 1.0 - expected_a

        # R_new = R_old + K * (actual - expected).
        self.ratings[player_a] += K_FACTOR * (result_a - expected_a)
        self.ratings[player_b] += K_FACTOR * ((1.0 - result_a) - expected_b)

        if result_a == 1.0:
            self.records[player_a]["wins"] += 1
            self.records[player_b]["losses"] += 1
        elif result_a == 0.0:
            self.records[player_b]["wins"] += 1
            self.records[player_a]["losses"] += 1
        else:
            self.records[player_a]["draws"] += 1
            self.records[player_b]["draws"] += 1

        self.history.append({
            "game_id": game_id, "matchup": matchup,
            "result_a": result_a, "ratings": dict(self.ratings),
        })

# ──────────── Resume Support ────────────

def parse_checkpoint(log_path):
    completed_games = []
    current_matchup_index = -1
    game_re = re.compile(
        r'\s*G\s*(\d+):\s+(.+?)\(B\)\s+vs\s+(.+?)\(W\)\s+->\s+(.+?)(?:\s+\(resign\))?\s+\((\d+)mv,\s+(\d+)s\)'
    )
    with open(log_path) as log_handle:
        for line in log_handle:
            matchup_match = re.match(r'Matchup (\d+)/\d+:', line.strip())
            if matchup_match:
                current_matchup_index = int(matchup_match.group(1)) - 1
                continue
            game_match = game_re.match(line)
            if game_match:
                game_index = int(game_match.group(1)) - 1
                black_name = game_match.group(2).strip()
                white_name = game_match.group(3).strip()
                winner = game_match.group(4).strip()
                moves = int(game_match.group(5))
                time_s = int(game_match.group(6))
                resigned = '(resign)' in line
                completed_games.append((
                    current_matchup_index,
                    game_index,
                    black_name,
                    white_name,
                    winner,
                    resigned,
                    moves,
                    time_s,
                ))
    return completed_games

# ──────────── Game Engine ────────────

def play_game(imc_lib, michi_lib, player_black, player_white, game_id):
    """Play one game. Returns result from Black's perspective (1.0/0.0/0.5)."""
    # Start one GTP process for each external player in this game.
    gtp_engines = {}
    for player_config in [player_black, player_white]:
        if player_config["type"] == "gtp" and player_config["name"] not in gtp_engines:
            gtp_engines[player_config["name"]] = GTPProcess(player_config["cmd"])

    # Initialize the shared C-compatible game state.
    board = np.zeros(NUM_CELLS, dtype=np.int8)
    new_board = (ct.c_int8 * NUM_CELLS)()
    current_player = 1  # Black first
    consecutive_passes = 0
    move_count = 0
    ko_hash = 0
    resigned = False
    moves_log = []

    while move_count < MAX_MOVES:
        if consecutive_passes >= 2:
            break

        black_to_move = (current_player == 1)
        current_config = player_black if black_to_move else player_white
        color_str = "black" if black_to_move else "white"
        opponent_config = player_white if black_to_move else player_black

        if current_config["type"] == "imc":
            # Load this player's crossbar weights and run IMC MCTS.
            weights_path = os.path.abspath(current_config["weights"]).encode()
            imc_lib.load_weights(weights_path)
            board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
            move = imc_lib.mcts_search(
                board_ptr, ct.c_int8(current_player),
                ct.c_int(consecutive_passes), ct.c_int(move_count),
                ct.c_uint64(ko_hash), ct.c_int(current_config["sims"]),
                ct.c_double(0.7))
            gtp_move = move_to_gtp(move)

        elif current_config["type"] == "michi":
            # Run Michi's random-rollout MCTS on the same board state.
            board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
            move = michi_lib.michi_search(
                board_ptr, ct.c_int8(current_player),
                ct.c_int(consecutive_passes), ct.c_int(move_count),
                ct.c_uint64(ko_hash), ct.c_int(current_config["sims"]),
                ct.c_double(1.4))
            gtp_move = move_to_gtp(move)

        elif current_config["type"] == "random":
            # Enumerate legal moves, then sample uniformly from the same order.
            board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
            legal_array = (ct.c_int * 82)()
            num_legal = imc_lib.get_legal_moves(
                board_ptr, ct.c_int8(current_player),
                ct.c_uint64(ko_hash), legal_array)
            legal_moves = [legal_array[index] for index in range(num_legal)]
            if len(legal_moves) > 1 and move_count < 150:
                legal_moves = [move for move in legal_moves if move != PASS_MOVE]
            move = random.choice(legal_moves)
            gtp_move = move_to_gtp(move)

        else:
            # Ask the active external engine to generate its move.
            gtp_engine = gtp_engines[current_config["name"]]
            gtp_move = gtp_engine.genmove(color_str)
            if gtp_move.upper() == "RESIGN":
                resigned = True
                break
            move = gtp_to_move(gtp_move)

        # Synchronize any external opponent with the selected move.
        if current_config["type"] != "gtp":
            if opponent_config["type"] == "gtp" and opponent_config["name"] in gtp_engines:
                gtp_engines[opponent_config["name"]].play(color_str, gtp_move)
        else:
            if opponent_config["type"] == "gtp" and opponent_config["name"] in gtp_engines:
                gtp_engines[opponent_config["name"]].play(color_str, gtp_move)

        moves_log.append({"move": move_count + 1, "player": color_str, "gtp": gtp_move})

        # Apply pass state or update the shared C board after a normal move.
        if gtp_move.upper() == "PASS" or move == PASS_MOVE:
            consecutive_passes += 1
        else:
            consecutive_passes = 0
            ko_hash = board_hash_fnv(board)
            board_ptr = board.ctypes.data_as(ct.POINTER(ct.c_int8))
            imc_lib.apply_move_c(board_ptr, ct.c_int(move),
                             ct.c_int8(current_player), new_board)
            board = np.frombuffer(new_board, dtype=np.int8).copy()

        current_player = -current_player
        move_count += 1

    # Convert resignation or Chinese area score to Black's outcome.
    if resigned:
        outcome = 0.0 if current_player == 1 else 1.0
    else:
        board_2d = board.reshape(BOARD_SIZE, BOARD_SIZE)
        black_score, white_score = score_position(board_2d)
        if black_score > white_score:
            outcome = 1.0
        elif white_score > black_score:
            outcome = 0.0
        else:
            outcome = 0.5

    # Stop every external engine started for this game.
    for gtp_engine in gtp_engines.values():
        gtp_engine.stop()

    return outcome, move_count, resigned, moves_log


# ──────────── Main Tournament ────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load C libraries
    imc_lib = ct.CDLL(IMC_LIB_PATH)
    imc_lib.load_weights.argtypes = [ct.c_char_p]
    imc_lib.load_weights.restype = ct.c_int
    imc_lib.mcts_search.argtypes = [
        ct.POINTER(ct.c_int8), ct.c_int8, ct.c_int, ct.c_int,
        ct.c_uint64, ct.c_int, ct.c_double,
    ]
    imc_lib.mcts_search.restype = ct.c_int
    imc_lib.apply_move_c.argtypes = [
        ct.POINTER(ct.c_int8), ct.c_int, ct.c_int8, ct.POINTER(ct.c_int8)
    ]
    imc_lib.apply_move_c.restype = ct.c_int
    imc_lib.get_legal_moves.argtypes = [
        ct.POINTER(ct.c_int8), ct.c_int8, ct.c_uint64, ct.POINTER(ct.c_int)
    ]
    imc_lib.get_legal_moves.restype = ct.c_int

    michi_lib = ct.CDLL(MICHI_LIB_PATH)
    michi_lib.michi_search.argtypes = [
        ct.POINTER(ct.c_int8), ct.c_int8, ct.c_int, ct.c_int,
        ct.c_uint64, ct.c_int, ct.c_double,
    ]
    michi_lib.michi_search.restype = ct.c_int

    names = [player["name"] for player in PLAYERS]
    elo = ELOTracker(names)
    all_games = []
    game_id = 0

    num_players = len(PLAYERS)
    matchups = [
        (player1_index, player2_index)
        for player1_index in range(num_players)
        for player2_index in range(player1_index + 1, num_players)
    ]
    total_games = len(matchups) * GAMES_PER_MATCHUP

    # ──── Load Checkpoint ────
    log_path = os.path.join(OUTPUT_DIR, "tournament.log")
    completed_games = []
    resume_mode = False
    if os.path.exists(log_path):
        completed_games = parse_checkpoint(log_path)
        if completed_games:
            resume_mode = True
            print(
                f"RESUMING from checkpoint: {len(completed_games)} games already played",
                flush=True
            )

    completed_game_keys = set()
    for (
        matchup_index,
        game_index,
        black_name,
        white_name,
        winner,
        resigned,
        moves,
        time_s,
    ) in completed_games:
        completed_game_keys.add((matchup_index, game_index))

    if not resume_mode:
        print("=" * 70, flush=True)
        print(f"ROUND-ROBIN TOURNAMENT: {OUTPUT_DIR}", flush=True)
        print("=" * 70, flush=True)
        print(f"Players: {', '.join(names)}", flush=True)
        print(f"Matchups: {len(matchups)}, Games/matchup: {GAMES_PER_MATCHUP}", flush=True)
        print(f"Total games: {total_games}", flush=True)
        print("=" * 70, flush=True)

    # Tee new tournament output to the checkpoint log.
    log_handle = open(log_path, "a")

    def log(msg):
        print(msg, flush=True)
        log_handle.write(msg + "\n")
        log_handle.flush()

    tournament_start_time = time.time()

    # Run every matchup with alternating colors and replay completed games.
    for matchup_index, (player1_index, player2_index) in enumerate(matchups):
        player1 = PLAYERS[player1_index]
        player2 = PLAYERS[player2_index]
        matchup_games_completed = sum(
            1 for (completed_matchup, completed_game, *_) in completed_games
            if completed_matchup == matchup_index
        )

        if resume_mode and matchup_games_completed == GAMES_PER_MATCHUP:
            print(f"\n  [Replay] Matchup {matchup_index+1}/{len(matchups)}: "
                  f"{player1['name']} vs {player2['name']} ({matchup_games_completed} games)", flush=True)
        else:
            log(f"\n{'─'*70}")
            if resume_mode and matchup_games_completed > 0:
                log(f"Matchup {matchup_index+1}/{len(matchups)}: {player1['name']} vs {player2['name']} "
                    f"(resuming from game {matchup_games_completed + 1})")
            else:
                log(f"Matchup {matchup_index+1}/{len(matchups)}: {player1['name']} vs {player2['name']}")
            log(f"{'─'*70}")

        matchup_wins = {player1["name"]: 0, player2["name"]: 0, "draws": 0}

        for game_index in range(GAMES_PER_MATCHUP):
            game_id += 1
            if game_index % 2 == 0:
                black_player, white_player = player1, player2
            else:
                black_player, white_player = player2, player1

            if (matchup_index, game_index) in completed_game_keys:
                # Replay the matching checkpoint entry in original log order.
                for (
                    checkpoint_matchup,
                    checkpoint_game,
                    checkpoint_black,
                    checkpoint_white,
                    checkpoint_winner,
                    checkpoint_resigned,
                    checkpoint_moves,
                    checkpoint_time,
                ) in completed_games:
                    if checkpoint_matchup == matchup_index and checkpoint_game == game_index:
                        if checkpoint_winner == checkpoint_black:
                            outcome = 1.0
                        elif checkpoint_winner == checkpoint_white:
                            outcome = 0.0
                        else:
                            outcome = 0.5
                        winner = checkpoint_winner

                        if player1["name"] == checkpoint_black:
                            result_player1 = outcome
                        else:
                            result_player1 = 1.0 - outcome
                        elo.update(
                            player1["name"],
                            player2["name"],
                            result_player1,
                            game_id,
                            f"{player1['name']} vs {player2['name']}"
                        )

                        if winner == player1["name"]:
                            matchup_wins[player1["name"]] += 1
                        elif winner == player2["name"]:
                            matchup_wins[player2["name"]] += 1
                        else:
                            matchup_wins["draws"] += 1

                        all_games.append({
                            "game_id": game_id,
                            "black": checkpoint_black, "white": checkpoint_white,
                            "winner": winner, "outcome_black": outcome,
                            "moves": checkpoint_moves, "resigned": checkpoint_resigned,
                            "time_s": checkpoint_time, "elo_after": dict(elo.ratings),
                        })
                        break
                continue

            game_start_time = time.time()
            outcome, moves, resigned, moves_log_data = play_game(
                imc_lib, michi_lib, black_player, white_player, game_id)
            elapsed = time.time() - game_start_time

            if outcome == 1.0:
                winner = black_player["name"]
            elif outcome == 0.0:
                winner = white_player["name"]
            else:
                winner = "Draw"

            if player1["name"] == black_player["name"]:
                result_player1 = outcome
            else:
                result_player1 = 1.0 - outcome
            elo.update(
                player1["name"],
                player2["name"],
                result_player1,
                game_id,
                f"{player1['name']} vs {player2['name']}"
            )

            if winner == player1["name"]:
                matchup_wins[player1["name"]] += 1
            elif winner == player2["name"]:
                matchup_wins[player2["name"]] += 1
            else:
                matchup_wins["draws"] += 1

            all_games.append({
                "game_id": game_id,
                "black": black_player["name"], "white": white_player["name"],
                "winner": winner, "outcome_black": outcome,
                "moves": moves, "resigned": resigned,
                "time_s": round(elapsed, 1),
                "elo_after": dict(elo.ratings),
            })

            resignation_suffix = " (resign)" if resigned else ""
            log(f"  G{game_index+1:>3}: {black_player['name']}(B) vs {white_player['name']}(W) "
                f"-> {winner}{resignation_suffix} ({moves}mv, {elapsed:.0f}s) "
                f"ELO: {elo.ratings[player1['name']]:.0f}/{elo.ratings[player2['name']]:.0f}")

        log(f"  Summary: {player1['name']}={matchup_wins[player1['name']]} "
            f"{player2['name']}={matchup_wins[player2['name']]} "
            f"Draws={matchup_wins['draws']}")

    elapsed_total = time.time() - tournament_start_time

    # ──── Final Results ────
    log(f"\n{'='*70}")
    log("FINAL RESULTS")
    log(f"{'='*70}")
    log(f"Total time: {elapsed_total/60:.1f} min ({total_games} games)\n")

    log(f"{'Rank':<5} {'Player':<20} {'ELO':>8} {'W':>4} {'L':>4} {'D':>4}")
    log("-" * 50)
    sorted_players = sorted(
        elo.ratings.items(),
        key=lambda rating_entry: -rating_entry[1]
    )
    for rank, (name, rating) in enumerate(sorted_players, 1):
        player_record = elo.records[name]
        log(f"{rank:<5} {name:<20} {rating:>8.1f} {player_record['wins']:>4} {player_record['losses']:>4} {player_record['draws']:>4}")

    # ──── Save Everything ────
    results = {
        "tournament": OUTPUT_DIR,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "players": [
                {key: value for key, value in player.items() if key != "cmd"}
                for player in PLAYERS
            ],
            "games_per_matchup": GAMES_PER_MATCHUP,
            "total_games": total_games,
        },
        "final_elo": dict(elo.ratings),
        "records": elo.records,
        "elo_history": elo.history,
        "games": all_games,
        "elapsed_s": round(elapsed_total, 1),
    }

    results_path = os.path.join(OUTPUT_DIR, "tournament_results.json")
    with open(results_path, "w") as results_handle:
        json.dump(results, results_handle, indent=2)
    log(f"\nResults saved to {results_path}")

    csv_path = os.path.join(OUTPUT_DIR, "elo_progression.csv")
    with open(csv_path, "w") as csv_handle:
        csv_handle.write("game_id," + ",".join(names) + "\n")
        csv_handle.write(f"0,{','.join([str(INIT_ELO)] * len(names))}\n")
        for rating_snapshot in elo.history:
            csv_row = [str(rating_snapshot["game_id"])]
            for player_name in names:
                csv_row.append(f"{rating_snapshot['ratings'][player_name]:.1f}")
            csv_handle.write(",".join(csv_row) + "\n")
    log(f"ELO progression saved to {csv_path}")
    log(f"\nDone! All data in {OUTPUT_DIR}/")

    log_handle.close()


if __name__ == "__main__":
    main()
