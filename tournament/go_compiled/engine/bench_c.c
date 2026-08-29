// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

/*
 * Benchmark: how fast is the C Go engine for MCTS-like workloads?
 * Simulates 1000 iterations of: get_legal_moves + apply_move + board_hash
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

/* Import from go_fast.c (we'll link them) */
extern int get_legal_moves(const int8_t *board, int8_t player, uint64_t ko_hash, int *out_moves);
extern int apply_move_c(const int8_t *board, int pos, int8_t player, int8_t *new_board);

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

int main(void) {
    int8_t board[81];
    int8_t new_board[81];
    int moves[82];
    memset(board, 0, 81);

    /* Place a few stones for a realistic mid-game position */
    int black_pos[] = {40, 22, 58, 30, 50, 10, 70, 20, 60};
    int white_pos[] = {31, 49, 13, 67, 41, 21, 59, 11, 69};
    for (int i = 0; i < 9; i++) {
        board[black_pos[i]] = 1;
        board[white_pos[i]] = -1;
    }

    int reps = 200; /* iterations per "move" */
    int num_moves = 5;

    double t0 = now_ms();

    for (int m = 0; m < num_moves; m++) {
        for (int iter = 0; iter < reps; iter++) {
            /* Simulate MCTS iteration: get legal moves + pick one + apply */
            int n = get_legal_moves(board, 1, 0, moves);
            int pick = moves[iter % n];
            if (pick < 81) {
                apply_move_c(board, pick, 1, new_board);
            }
            /* Simulate second get_legal_moves (for expansion) */
            get_legal_moves(new_board, -1, 0, moves);
        }
    }

    double elapsed = now_ms() - t0;
    printf("Pure C: %d moves x %d iters = %d ops in %.3f ms\n",
           num_moves, reps, num_moves * reps, elapsed);
    printf("Per iteration: %.3f us\n", elapsed * 1000.0 / (num_moves * reps));
    printf("Per move (200 iters): %.3f ms\n", elapsed / num_moves);

    /* Now benchmark just get_legal_moves */
    t0 = now_ms();
    for (int i = 0; i < 10000; i++) {
        get_legal_moves(board, 1, 0, moves);
    }
    elapsed = now_ms() - t0;
    printf("\nget_legal_moves x10000: %.3f ms (%.3f us each)\n", elapsed, elapsed * 100.0);

    /* Benchmark apply_move */
    t0 = now_ms();
    for (int i = 0; i < 10000; i++) {
        apply_move_c(board, 40, 1, new_board);
    }
    elapsed = now_ms() - t0;
    printf("apply_move x10000: %.3f ms (%.3f us each)\n", elapsed, elapsed * 100.0);

    return 0;
}
