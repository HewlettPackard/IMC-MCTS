// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

/*
 * Michi-C: Lightweight random-rollout MCTS for 9x9 Go.
 * No neural network — uses Monte Carlo playouts for evaluation.
 * Designed as a weak-to-medium baseline opponent for tournaments.
 *
 * Reuses go_fast.c for board operations.
 * Build: gcc -O3 -march=native -shared -fPIC -o michi_c.so michi_c.c go_fast.c -lm
 */

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define BOARD_SIZE 9
#define NUM_CELLS 81
#define PASS_MOVE 81
#define MAX_GAME_MOVES 200

/* From go_fast.c */
extern int get_legal_moves(const int8_t *board, int8_t player,
                           uint64_t ko_hash, int *out_moves);
extern int apply_move_c(const int8_t *board, int pos, int8_t player,
                        int8_t *new_board);
extern int is_legal(const int8_t *board, int pos, int8_t player,
                    uint64_t ko_hash);

/* ---------- RNG (xorshift64) ---------- */

static uint64_t rng_state = 0;

static void rng_seed(void) {
    if (rng_state == 0)
        rng_state = (uint64_t)time(NULL) ^ 0xdeadbeefcafeULL;
}

static uint64_t rng_next(void) {
    uint64_t x = rng_state;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    rng_state = x;
    return x;
}

static int rng_int(int n) {
    return (int)(rng_next() % (uint64_t)n);
}

/* ---------- Scoring ---------- */

static double score_position(const int8_t *board, double komi) {
    double black = 0, white = 0;
    int8_t visited[NUM_CELLS];
    memset(visited, 0, NUM_CELLS);

    for (int i = 0; i < NUM_CELLS; i++) {
        if (board[i] == 1) black += 1.0;
        else if (board[i] == -1) white += 1.0;
    }

    for (int i = 0; i < NUM_CELLS; i++) {
        if (board[i] != 0 || visited[i]) continue;
        int region[NUM_CELLS], rsize = 0;
        int stack[NUM_CELLS], sp = 0;
        int owners = 0;

        stack[sp++] = i;
        visited[i] = 1;
        while (sp > 0) {
            int p = stack[--sp];
            region[rsize++] = p;
            int r = p / BOARD_SIZE, c = p % BOARD_SIZE;
            int dr[] = {-1, 1, 0, 0}, dc[] = {0, 0, -1, 1};
            for (int d = 0; d < 4; d++) {
                int nr = r + dr[d], nc = c + dc[d];
                if (nr >= 0 && nr < BOARD_SIZE && nc >= 0 && nc < BOARD_SIZE) {
                    int nb = nr * BOARD_SIZE + nc;
                    if (board[nb] != 0) {
                        if (board[nb] == 1) owners |= 1;
                        else owners |= 2;
                    } else if (!visited[nb]) {
                        visited[nb] = 1;
                        stack[sp++] = nb;
                    }
                }
            }
        }
        if (owners == 1) black += rsize;
        else if (owners == 2) white += rsize;
    }
    return black - (white + komi);
}

/* ---------- Random Playout ---------- */

static uint64_t board_hash_fnv(const int8_t *board) {
    uint64_t h = 14695981039346656037ULL;
    for (int i = 0; i < NUM_CELLS; i++) {
        h ^= (uint64_t)(uint8_t)board[i];
        h *= 1099511628211ULL;
    }
    return h;
}

/*
 * Play a random game from the given position to completion.
 * Returns result from Black's perspective: 1.0 (B wins), 0.0 (W wins), 0.5 (draw).
 */
static double random_playout(const int8_t *start_board, int8_t start_player,
                             int start_passes, int start_moves) {
    int8_t board[NUM_CELLS], new_board[NUM_CELLS];
    memcpy(board, start_board, NUM_CELLS);
    int8_t player = start_player;
    int passes = start_passes;
    int moves = start_moves;
    uint64_t ko_hash = 0;

    while (moves < MAX_GAME_MOVES && passes < 2) {
        int legal[82];
        int n_legal = get_legal_moves(board, player, ko_hash, legal);

        /* Remove pass unless it's the only move or game is late */
        if (n_legal > 1 && moves < 150) {
            if (legal[n_legal - 1] == PASS_MOVE)
                n_legal--;
        }

        /* Pick random legal move */
        int move = legal[rng_int(n_legal)];

        if (move == PASS_MOVE) {
            passes++;
        } else {
            passes = 0;
            ko_hash = board_hash_fnv(board);
            apply_move_c(board, move, player, new_board);
            memcpy(board, new_board, NUM_CELLS);
        }
        player = -player;
        moves++;
    }

    double diff = score_position(board, 6.5);
    if (diff > 0) return 1.0;
    if (diff < 0) return 0.0;
    return 0.5;
}

/* ---------- MCTS ---------- */

#define MAX_NODES 50000
#define MAX_CHILDREN 82

typedef struct {
    int parent;
    int move;
    int visits;
    double value;          /* accumulated value from Black's perspective */
    int children[MAX_CHILDREN];
    int num_children;
    int untried_moves[MAX_CHILDREN];
    int num_untried;
    int expanded;
    int8_t board[NUM_CELLS];
    int8_t player;
    int consecutive_passes;
    int move_count;
    uint64_t ko_hash;
} MCTSNode;

static MCTSNode nodes[MAX_NODES];
static int num_nodes;

static int make_node(const int8_t *board, int8_t player, int passes,
                     int move_count, uint64_t ko_hash, int parent, int move) {
    if (num_nodes >= MAX_NODES) return -1;
    int idx = num_nodes++;
    MCTSNode *n = &nodes[idx];
    n->parent = parent;
    n->move = move;
    n->visits = 0;
    n->value = 0.0;
    n->num_children = 0;
    n->num_untried = 0;
    n->expanded = 0;
    memcpy(n->board, board, NUM_CELLS);
    n->player = player;
    n->consecutive_passes = passes;
    n->move_count = move_count;
    n->ko_hash = ko_hash;
    return idx;
}

static void expand_node(int idx) {
    MCTSNode *n = &nodes[idx];
    if (n->expanded) return;
    n->expanded = 1;

    n->num_untried = get_legal_moves(n->board, n->player, n->ko_hash, n->untried_moves);

    /* Remove pass unless late game */
    if (n->num_untried > 1 && n->move_count < 120) {
        if (n->untried_moves[n->num_untried - 1] == PASS_MOVE)
            n->num_untried--;
    }

    /* Shuffle */
    for (int i = n->num_untried - 1; i > 0; i--) {
        int j = rng_int(i + 1);
        int tmp = n->untried_moves[i];
        n->untried_moves[i] = n->untried_moves[j];
        n->untried_moves[j] = tmp;
    }
}

static int is_terminal(MCTSNode *n) {
    return (n->consecutive_passes >= 2) || (n->move_count >= MAX_GAME_MOVES);
}

/* UCB1 selection */
static int select_child(int idx, double exploration_c) {
    while (1) {
        MCTSNode *n = &nodes[idx];
        if (is_terminal(n)) return idx;

        expand_node(idx);
        if (n->num_untried > 0) return idx;
        if (n->num_children == 0) return idx;

        double log_parent = log((double)n->visits);
        double best_score = -1e30;
        int best_child = n->children[0];

        for (int i = 0; i < n->num_children; i++) {
            int ci = n->children[i];
            MCTSNode *child = &nodes[ci];
            if (child->visits == 0) { best_child = ci; break; }

            double exploit = child->value / child->visits;
            if (n->player == -1) exploit = 1.0 - exploit;
            double explore = exploration_c * sqrt(log_parent / child->visits);

            if (exploit + explore > best_score) {
                best_score = exploit + explore;
                best_child = ci;
            }
        }
        idx = best_child;
    }
}

/* Expand: pop an untried move, create child */
static int expand(int idx) {
    MCTSNode *n = &nodes[idx];
    if (is_terminal(n) || n->num_untried == 0) return idx;

    int move = n->untried_moves[--n->num_untried];

    int8_t new_board[NUM_CELLS];
    int new_passes;
    uint64_t new_ko;

    if (move == PASS_MOVE) {
        memcpy(new_board, n->board, NUM_CELLS);
        new_passes = n->consecutive_passes + 1;
        new_ko = n->ko_hash;
    } else {
        new_passes = 0;
        new_ko = board_hash_fnv(n->board);
        apply_move_c(n->board, move, n->player, new_board);
    }

    int child = make_node(new_board, -n->player, new_passes,
                          n->move_count + 1, new_ko, idx, move);
    if (child < 0) return idx;

    n->children[n->num_children++] = child;
    return child;
}

/* Backpropagate */
static void backprop(int idx, double value) {
    while (idx >= 0) {
        nodes[idx].visits++;
        nodes[idx].value += value;
        idx = nodes[idx].parent;
    }
}

/*
 * Run MCTS with random rollouts. Returns best move.
 * This is the main API, callable from Python via ctypes.
 */
int michi_search(const int8_t *board, int8_t player, int consecutive_passes,
                 int move_count, uint64_t ko_hash, int iterations,
                 double exploration_c) {
    rng_seed();
    num_nodes = 0;

    int root = make_node(board, player, consecutive_passes,
                         move_count, ko_hash, -1, -1);

    for (int i = 0; i < iterations; i++) {
        int leaf = select_child(root, exploration_c);
        int child = expand(leaf);

        /* Evaluate by random playout */
        MCTSNode *cn = &nodes[child];
        double value;
        if (is_terminal(cn)) {
            double diff = score_position(cn->board, 6.5);
            value = (diff > 0) ? 1.0 : (diff < 0) ? 0.0 : 0.5;
        } else {
            value = random_playout(cn->board, cn->player,
                                   cn->consecutive_passes, cn->move_count);
        }

        backprop(child, value);
    }

    /* Choose most-visited child */
    MCTSNode *r = &nodes[root];
    if (r->num_children == 0) {
        int moves[82];
        int n = get_legal_moves(board, player, ko_hash, moves);
        return n > 0 ? moves[0] : PASS_MOVE;
    }

    int best = r->children[0];
    int best_visits = nodes[best].visits;
    for (int i = 1; i < r->num_children; i++) {
        int ci = r->children[i];
        if (nodes[ci].visits > best_visits) {
            best_visits = nodes[ci].visits;
            best = ci;
        }
    }
    return nodes[best].move;
}
