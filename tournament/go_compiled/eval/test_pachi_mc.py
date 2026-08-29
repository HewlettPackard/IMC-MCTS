#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Quick test: Pachi-montecarlo vs GnuGo L10, 10 games."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from training.selfplay_iterative import GTPProcess, board_to_features, board_hash_fnv, score_position, BOARD_SIZE, NUM_CELLS, PASS_MOVE, MAX_MOVES, move_to_gtp, gtp_to_move
from paths import GNUGO_BIN as GNUGO, PACHI_BIN as PACHI
import numpy as np
import time

def play_gtp_game(engine_a_cmd, engine_b_cmd, num_games=10):
    a_wins = 0
    for game_index in range(num_games):
        engine_a = GTPProcess(engine_a_cmd)
        engine_b = GTPProcess(engine_b_cmd)
        a_is_black = (game_index % 2 == 0)
        black_engine = engine_a if a_is_black else engine_b
        white_engine = engine_b if a_is_black else engine_a

        move_count = 0
        consecutive_passes = 0
        resigned = False

        while move_count < MAX_MOVES and consecutive_passes < 2:
            if move_count % 2 == 0:  # Black's turn
                gtp_move = black_engine.genmove("black")
            else:  # White's turn
                gtp_move = white_engine.genmove("white")

            color = "black" if move_count % 2 == 0 else "white"
            other_engine = white_engine if move_count % 2 == 0 else black_engine

            if gtp_move.upper() == "RESIGN":
                resigned = True
                # The engine that resigned loses
                resigner_is_a = (move_count % 2 == 0 and a_is_black) or \
                               (move_count % 2 == 1 and not a_is_black)
                if not resigner_is_a:
                    a_wins += 1
                break

            other_engine.play(color, gtp_move)

            if gtp_move.upper() == "PASS":
                consecutive_passes += 1
            else:
                consecutive_passes = 0

            move_count += 1

        if not resigned:
            # Use GnuGo's final_score or estimate
            # Just count who has more territory via the engines
            score_str = black_engine._send("final_score")
            if score_str and score_str.strip():
                s = score_str.strip()
                if s.startswith("B"):
                    winner_is_black = True
                elif s.startswith("W"):
                    winner_is_black = False
                else:
                    winner_is_black = None

                if winner_is_black is not None:
                    a_won = (winner_is_black and a_is_black) or \
                           (not winner_is_black and not a_is_black)
                    if a_won:
                        a_wins += 1

        engine_a.stop()
        engine_b.stop()
        result = "A wins" if (resigned and not resigner_is_a) or (not resigned and a_won) else "B wins"
        print(f"  Game {game_index+1}: {result} ({move_count} moves)", flush=True)

    return a_wins, num_games

print("Pachi-MC vs GnuGo-L10 (10 games)", flush=True)
match_start_time = time.time()
wins, total = play_gtp_game(
    [PACHI, "-e", "montecarlo"],
    [GNUGO, "--mode", "gtp", "--level", "10"],
    10
)
print(f"\nPachi-MC: {wins}/{total} ({wins/total*100:.0f}%) in {time.time()-match_start_time:.0f}s", flush=True)
