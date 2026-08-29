#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Quick test: Pachi-UCT (nopatterns) vs GnuGo L10, 10 games."""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from training.selfplay_iterative import GTPProcess, PASS_MOVE, MAX_MOVES
from paths import GNUGO_BIN as GNUGO, PACHI_BIN as PACHI

def play_gtp_match(cmd_a, cmd_b, num_games=10):
    a_wins = 0
    for game_index in range(num_games):
        engine_a = GTPProcess(cmd_a)
        engine_b = GTPProcess(cmd_b)
        a_is_black = (game_index % 2 == 0)
        engines = {
            True: engine_a if a_is_black else engine_b,
            False: engine_b if a_is_black else engine_a,
        }

        move_count = 0
        consecutive_passes = 0
        a_won = False
        resigned = False

        while move_count < MAX_MOVES and consecutive_passes < 2:
            is_black_turn = (move_count % 2 == 0)
            color = "black" if is_black_turn else "white"
            active_engine = engines[is_black_turn]
            other_engine = engines[not is_black_turn]

            gtp_move = active_engine.genmove(color)
            if gtp_move.upper() == "RESIGN":
                resigned = True
                mover_is_a = (is_black_turn == a_is_black)
                a_won = not mover_is_a
                break

            other_engine.play(color, gtp_move)
            if gtp_move.upper() == "PASS":
                consecutive_passes += 1
            else:
                consecutive_passes = 0
            move_count += 1

        if not resigned:
            # Ask the black engine for final score
            score_str = engines[True]._send("final_score").strip()
            if score_str.startswith("B"):
                a_won = a_is_black
            elif score_str.startswith("W"):
                a_won = not a_is_black

        if a_won:
            a_wins += 1
        winner_name = "Pachi" if a_won else "GnuGo"
        print(f"  Game {game_index+1}: {winner_name} wins ({move_count} moves)", flush=True)
        engine_a.stop()
        engine_b.stop()

    return a_wins, num_games

print("Pachi-UCT (nopatterns) vs GnuGo-L10 (10 games)", flush=True)
match_start_time = time.time()
wins, total = play_gtp_match(
    [PACHI, "--nopatterns", "-t", "=1000"],
    [GNUGO, "--mode", "gtp", "--level", "10"],
    10
)
print(f"\nPachi-UCT: {wins}/{total} ({wins/total*100:.0f}%) in {time.time()-match_start_time:.0f}s", flush=True)
