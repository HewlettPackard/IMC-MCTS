// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

/*
 * Fast C implementation of Go board operations for 9x9.
 * Compiled as shared library, called via ctypes.
 *
 * Board: int8_t[81], 1=Black, -1=White, 0=Empty
 * Moves: int (0-80 for board positions, 81 for pass)
 */

#include <stdint.h>
#include <string.h>

#define BOARD_SIZE 9
#define NUM_CELLS 81
#define PASS_MOVE 81

/* Neighbor offsets for (r*9+c) flat indexing */
static int neighbors[NUM_CELLS][4];
static int num_neighbors[NUM_CELLS];
static int initialized = 0;

static void init_neighbors(void) {
    if (initialized) return;
    int dr[] = {-1, 1, 0, 0};
    int dc[] = {0, 0, -1, 1};
    for (int r = 0; r < BOARD_SIZE; r++) {
        for (int c = 0; c < BOARD_SIZE; c++) {
            int idx = r * BOARD_SIZE + c;
            int n = 0;
            for (int d = 0; d < 4; d++) {
                int nr = r + dr[d], nc = c + dc[d];
                if (nr >= 0 && nr < BOARD_SIZE && nc >= 0 && nc < BOARD_SIZE) {
                    neighbors[idx][n++] = nr * BOARD_SIZE + nc;
                }
            }
            num_neighbors[idx] = n;
        }
    }
    initialized = 1;
}

/* Flood fill to find group. Returns group size, fills group[] array. */
static int find_group(const int8_t *board, int pos, int8_t *visited, int *group) {
    int8_t color = board[pos];
    int size = 0;
    int stack[NUM_CELLS];
    int sp = 0;
    stack[sp++] = pos;
    visited[pos] = 1;
    while (sp > 0) {
        int p = stack[--sp];
        group[size++] = p;
        for (int i = 0; i < num_neighbors[p]; i++) {
            int nb = neighbors[p][i];
            if (!visited[nb] && board[nb] == color) {
                visited[nb] = 1;
                stack[sp++] = nb;
            }
        }
    }
    return size;
}

/* Count liberties of a group */
static int group_liberties(const int8_t *board, const int *group, int size) {
    int8_t seen[NUM_CELLS];
    memset(seen, 0, NUM_CELLS);
    int libs = 0;
    for (int i = 0; i < size; i++) {
        int p = group[i];
        for (int j = 0; j < num_neighbors[p]; j++) {
            int nb = neighbors[p][j];
            if (board[nb] == 0 && !seen[nb]) {
                seen[nb] = 1;
                libs++;
            }
        }
    }
    return libs;
}

/* Remove dead groups of color 'opponent'. Returns capture count. */
static int capture_dead(int8_t *board, int8_t opponent) {
    int8_t visited[NUM_CELLS];
    memset(visited, 0, NUM_CELLS);
    int group[NUM_CELLS];
    int total_captured = 0;
    for (int p = 0; p < NUM_CELLS; p++) {
        if (board[p] == opponent && !visited[p]) {
            int gsize = find_group(board, p, visited, group);
            if (group_liberties(board, group, gsize) == 0) {
                for (int i = 0; i < gsize; i++) {
                    board[group[i]] = 0;
                }
                total_captured += gsize;
            }
        }
    }
    return total_captured;
}

/* Simple board hash for ko detection */
static uint64_t board_hash(const int8_t *board) {
    /* FNV-1a hash */
    uint64_t h = 14695981039346656037ULL;
    for (int i = 0; i < NUM_CELLS; i++) {
        h ^= (uint64_t)(uint8_t)board[i];
        h *= 1099511628211ULL;
    }
    return h;
}

/*
 * Check if move at position pos is legal for player.
 * ko_hash: hash of board before the previous move (0 if no ko context).
 * Returns 1 if legal, 0 if not.
 */
int is_legal(const int8_t *board, int pos, int8_t player, uint64_t ko_hash) {
    init_neighbors();
    if (board[pos] != 0) return 0;

    int8_t opponent = -player;

    /* Fast path: has an empty neighbor */
    for (int i = 0; i < num_neighbors[pos]; i++) {
        if (board[neighbors[pos][i]] == 0) return 1;
    }

    /* Slow path: simulate placement */
    int8_t scratch[NUM_CELLS];
    memcpy(scratch, board, NUM_CELLS);
    scratch[pos] = player;

    int captured = capture_dead(scratch, opponent);

    /* Check suicide */
    int8_t visited[NUM_CELLS];
    int group[NUM_CELLS];
    memset(visited, 0, NUM_CELLS);
    int gsize = find_group(scratch, pos, visited, group);
    if (group_liberties(scratch, group, gsize) == 0) return 0;

    /* Ko check */
    if (captured > 0 && ko_hash != 0) {
        uint64_t new_hash = board_hash(scratch);
        if (new_hash == ko_hash) return 0;
    }

    return 1;
}

/*
 * Get all legal moves for player.
 * out_moves: output array (max 82 entries: 81 positions + pass)
 * Returns number of legal moves written.
 */
int get_legal_moves(const int8_t *board, int8_t player, uint64_t ko_hash, int *out_moves) {
    init_neighbors();
    int n = 0;
    for (int pos = 0; pos < NUM_CELLS; pos++) {
        if (board[pos] == 0 && is_legal(board, pos, player, ko_hash)) {
            out_moves[n++] = pos;
        }
    }
    out_moves[n++] = PASS_MOVE; /* pass is always legal */
    return n;
}

/*
 * Apply move: place stone, capture, return info.
 * new_board: output (copy of board with move applied)
 * Returns: number of captures made. -1 if pass.
 */
int apply_move_c(const int8_t *board, int pos, int8_t player, int8_t *new_board) {
    init_neighbors();
    memcpy(new_board, board, NUM_CELLS);

    if (pos == PASS_MOVE) return -1;

    new_board[pos] = player;
    int captured = capture_dead(new_board, -player);
    return captured;
}
