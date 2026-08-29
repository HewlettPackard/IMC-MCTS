// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

/*
 * Full IMC-MCTS engine in C.
 *
 * Integrates:
 *   - 9x9 Go engine (from go_fast.c)
 *   - Behavioral crossbar NN (163 -> 96 -> 3, differential-pair encoding)
 *   - MCTS with UCB1 selection and NN evaluation
 *
 * Build: gcc -O3 -o imc_mcts imc_mcts.c go_fast.c -lm
 * Usage: ./imc_mcts weights.bin [iterations]
 *
 * Exposes a C API callable from Python via ctypes for tournament integration.
 */

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int rng_seeded = 0;
static void ensure_rng(void) {
    if (!rng_seeded) { srand(time(NULL)); rng_seeded = 1; }
}

#define BOARD_SIZE 9
#define NUM_CELLS 81
#define PASS_MOVE 81
#define INPUT_SIZE 163
#define HIDDEN_SIZE 96
#define OUTPUT_SIZE 3     /* Hardware: 3-class classification [P(White), P(Draw), P(Black)] */

#define MAX_NODES 200000
#define MAX_CHILDREN 82
#define MAX_GAME_MOVES 200

/* ---------- Go engine (from go_fast.c) ---------- */
extern int get_legal_moves(const int8_t *board, int8_t player,
                           uint64_t ko_hash, int *out_moves);
extern int apply_move_c(const int8_t *board, int pos, int8_t player,
                        int8_t *new_board);

/* ---------- Neural Network ---------- */

typedef struct {
    double w1[INPUT_SIZE * HIDDEN_SIZE];          /* 163 x 96 */
    double w2[HIDDEN_SIZE * OUTPUT_SIZE];         /* 96 x 3 */
    double w1_eff[INPUT_SIZE * HIDDEN_SIZE];
    double w2_eff[HIDDEN_SIZE * OUTPUT_SIZE];
} NNWeights;

static NNWeights nn;
static int nn_loaded = 0;

int load_weights(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;

    int rows1, cols1, rows2, cols2;
    if (fread(&rows1, 4, 1, f) != 1) goto fail;
    if (fread(&cols1, 4, 1, f) != 1) goto fail;
    if (rows1 != INPUT_SIZE || cols1 != HIDDEN_SIZE) goto fail;
    if (fread(nn.w1, sizeof(double), INPUT_SIZE * HIDDEN_SIZE, f) !=
        (size_t)(INPUT_SIZE * HIDDEN_SIZE))
        goto fail;

    if (fread(&rows2, 4, 1, f) != 1) goto fail;
    if (fread(&cols2, 4, 1, f) != 1) goto fail;
    if (rows2 != HIDDEN_SIZE || cols2 != OUTPUT_SIZE) goto fail;

    if (fread(nn.w2, sizeof(double), HIDDEN_SIZE * OUTPUT_SIZE, f) !=
        (size_t)(HIDDEN_SIZE * OUTPUT_SIZE))
        goto fail;

    fclose(f);

    /* Pre-normalize: w_eff = (G - 50) / 50 */
    for (int i = 0; i < INPUT_SIZE * HIDDEN_SIZE; i++)
        nn.w1_eff[i] = (nn.w1[i] - 50.0) / 50.0;
    for (int i = 0; i < HIDDEN_SIZE * OUTPUT_SIZE; i++)
        nn.w2_eff[i] = (nn.w2[i] - 50.0) / 50.0;

    nn_loaded = 1;
    return 0;

fail:
    fclose(f);
    return -1;
}

/* NN forward pass: board + current_player -> value from Black's perspective */
double nn_evaluate(const int8_t *board, int8_t current_player) {
    /* DAC: board -> voltages (vectorized 2-channel encoding + turn bit) */
    double voltages[INPUT_SIZE];
    for (int i = 0; i < NUM_CELLS; i++) {
        voltages[2 * i]     = (board[i] == 1)  ? 1.0 : 0.0;  /* Black channel */
        voltages[2 * i + 1] = (board[i] == -1) ? 1.0 : 0.0;  /* White channel */
    }
    /* 163rd input: turn bit (1.0 = Black to play, 0.0 = White to play) */
    voltages[162] = (current_player == 1) ? 1.0 : 0.0;

    /* Crossbar 1: voltages[162] x W1_eff[162x96] -> hidden[96] */
    double hidden[HIDDEN_SIZE];
    for (int j = 0; j < HIDDEN_SIZE; j++) {
        double sum = 0.0;
        for (int i = 0; i < INPUT_SIZE; i++)
            sum += voltages[i] * nn.w1_eff[i * HIDDEN_SIZE + j];
        /* ReLU */
        hidden[j] = sum > 0.0 ? sum : 0.0;
    }

    /* Crossbar 2: hidden[96] x W2_eff[96x3] -> output[3] */
    double output[OUTPUT_SIZE];
    for (int j = 0; j < OUTPUT_SIZE; j++) {
        double sum = 0.0;
        for (int i = 0; i < HIDDEN_SIZE; i++)
            sum += hidden[i] * nn.w2_eff[i * OUTPUT_SIZE + j];
        output[j] = sum;
    }

    /* Softmax -> [P(White), P(Draw), P(Black)] */
    double max_val = output[0];
    for (int i = 1; i < OUTPUT_SIZE; i++)
        if (output[i] > max_val) max_val = output[i];

    double exp_sum = 0.0;
    double probs[OUTPUT_SIZE];
    for (int i = 0; i < OUTPUT_SIZE; i++) {
        probs[i] = exp(output[i] - max_val);
        exp_sum += probs[i];
    }
    for (int i = 0; i < OUTPUT_SIZE; i++)
        probs[i] /= exp_sum;

    /* Value from Black's perspective: P(Black) + 0.5*P(Draw) */
    return probs[2] + 0.5 * probs[1];
}

/* ---------- Game State ---------- */

typedef struct {
    int8_t board[NUM_CELLS];
    int8_t current_player; /* 1=Black, -1=White */
    int consecutive_passes;
    int move_count;
    uint64_t ko_hash;
} GameState;

static void state_init(GameState *s) {
    memset(s->board, 0, NUM_CELLS);
    s->current_player = 1;
    s->consecutive_passes = 0;
    s->move_count = 0;
    s->ko_hash = 0;
}

static uint64_t board_hash_fnv(const int8_t *board) {
    uint64_t h = 14695981039346656037ULL;
    for (int i = 0; i < NUM_CELLS; i++) {
        h ^= (uint64_t)(uint8_t)board[i];
        h *= 1099511628211ULL;
    }
    return h;
}

static int state_is_terminal(const GameState *s) {
    if (s->consecutive_passes >= 2) return 1;
    if (s->move_count >= 2 * NUM_CELLS) return 1;
    return 0;
}

static void state_apply_move(const GameState *src, int move, GameState *dst) {
    dst->current_player = -src->current_player;
    dst->move_count = src->move_count + 1;

    if (move == PASS_MOVE) {
        memcpy(dst->board, src->board, NUM_CELLS);
        dst->consecutive_passes = src->consecutive_passes + 1;
        dst->ko_hash = src->ko_hash;
        return;
    }

    dst->consecutive_passes = 0;
    dst->ko_hash = board_hash_fnv(src->board);
    apply_move_c(src->board, move, src->current_player, dst->board);
}

/* Chinese area scoring. Returns score from Black's perspective (positive = Black ahead). */
static double score_position(const int8_t *board, double komi) {
    double black = 0, white = 0;
    int8_t visited[NUM_CELLS];
    memset(visited, 0, NUM_CELLS);

    for (int i = 0; i < NUM_CELLS; i++) {
        if (board[i] == 1) black += 1.0;
        else if (board[i] == -1) white += 1.0;
    }

    /* Territory: empty regions surrounded by single color.
     * Only mark EMPTY cells as visited so stones can border multiple regions. */
    for (int i = 0; i < NUM_CELLS; i++) {
        if (board[i] != 0 || visited[i]) continue;

        /* Flood fill empty region */
        int region[NUM_CELLS];
        int rsize = 0;
        int stack[NUM_CELLS];
        int sp = 0;
        int owners = 0; /* bitmask: bit0=black, bit1=white */

        stack[sp++] = i;
        visited[i] = 1;
        while (sp > 0) {
            int p = stack[--sp];
            region[rsize++] = p;
            int r = p / BOARD_SIZE, c = p % BOARD_SIZE;
            int dr[] = {-1, 1, 0, 0};
            int dc[] = {0, 0, -1, 1};
            for (int d = 0; d < 4; d++) {
                int nr = r + dr[d], nc = c + dc[d];
                if (nr >= 0 && nr < BOARD_SIZE && nc >= 0 && nc < BOARD_SIZE) {
                    int nb = nr * BOARD_SIZE + nc;
                    if (board[nb] != 0) {
                        /* Stone: note owner but don't mark visited */
                        if (board[nb] == 1) owners |= 1;
                        else owners |= 2;
                    } else if (!visited[nb]) {
                        /* Empty: mark visited and explore */
                        visited[nb] = 1;
                        stack[sp++] = nb;
                    }
                }
            }
        }

        if (owners == 1) black += rsize;      /* Only black borders */
        else if (owners == 2) white += rsize;  /* Only white borders */
    }

    return black - (white + komi);
}

static double state_result_black(const GameState *s) {
    double diff = score_position(s->board, 6.5);
    if (diff > 0) return 1.0;
    if (diff < 0) return 0.0;
    return 0.5;
}

/* ---------- MCTS ---------- */

typedef struct {
    int parent;
    int move;             /* Move that led to this node (0-80 or PASS_MOVE) */
    int visits;
    double value;         /* Accumulated value from Black's perspective */
    int children[MAX_CHILDREN];
    int num_children;
    int untried_moves[MAX_CHILDREN];
    int num_untried;
    int untried_initialized;
    int is_terminal;      /* -1=unknown, 0=no, 1=yes */
    GameState state;
} MCTSNode;

/* Global node pool */
static MCTSNode nodes[MAX_NODES];
static int num_nodes;

/* Eval cache */
#define EVAL_CACHE_SIZE 8192
#define EVAL_CACHE_MASK (EVAL_CACHE_SIZE - 1)
typedef struct { uint64_t hash; double value; int valid; } EvalEntry;
static EvalEntry eval_cache[EVAL_CACHE_SIZE];

static void eval_cache_clear(void) {
    for (int i = 0; i < EVAL_CACHE_SIZE; i++)
        eval_cache[i].valid = 0;
}

static int eval_cache_get(uint64_t hash, double *value) {
    int idx = (int)(hash & EVAL_CACHE_MASK);
    if (eval_cache[idx].valid && eval_cache[idx].hash == hash) {
        *value = eval_cache[idx].value;
        return 1;
    }
    return 0;
}

static void eval_cache_put(uint64_t hash, double value) {
    int idx = (int)(hash & EVAL_CACHE_MASK);
    eval_cache[idx].hash = hash;
    eval_cache[idx].value = value;
    eval_cache[idx].valid = 1;
}

static int make_node(const GameState *state, int parent, int move) {
    if (num_nodes >= MAX_NODES) return -1;
    int idx = num_nodes++;
    MCTSNode *n = &nodes[idx];
    n->parent = parent;
    n->move = move;
    n->visits = 0;
    n->value = 0.0;
    n->num_children = 0;
    n->num_untried = 0;
    n->untried_initialized = 0;
    n->is_terminal = -1;
    memcpy(&n->state, state, sizeof(GameState));
    return idx;
}

static void init_untried(int idx) {
    MCTSNode *n = &nodes[idx];
    if (n->untried_initialized) return;
    n->untried_initialized = 1;
    n->num_untried = get_legal_moves(n->state.board, n->state.current_player,
                                      n->state.ko_hash, n->untried_moves);
    /* Only allow pass if there are no board moves or game is late (>120 moves).
     * Without this, an overconfident NN causes MCTS to pass prematurely. */
    if (n->num_untried > 1 && n->state.move_count < 120) {
        /* Remove pass (always last) if there are board moves */
        if (n->untried_moves[n->num_untried - 1] == PASS_MOVE)
            n->num_untried--;
    }
    /* Shuffle untried moves for variety (Fisher-Yates) */
    ensure_rng();
    for (int i = n->num_untried - 1; i > 0; i--) {
        int j = rand() % (i + 1);
        int tmp = n->untried_moves[i];
        n->untried_moves[i] = n->untried_moves[j];
        n->untried_moves[j] = tmp;
    }
}

static int check_terminal(int idx) {
    MCTSNode *n = &nodes[idx];
    if (n->is_terminal == -1)
        n->is_terminal = state_is_terminal(&n->state) ? 1 : 0;
    return n->is_terminal;
}

static int mcts_select(double exploration_c) {
    int idx = 0;
    while (1) {
        if (check_terminal(idx)) return idx;

        init_untried(idx);
        MCTSNode *n = &nodes[idx];
        if (n->num_untried > 0) return idx;
        if (n->num_children == 0) return idx;

        /* UCB1 selection */
        double log_parent = log((double)n->visits);
        double best_score = -1e30;
        int best_child = n->children[0];

        for (int i = 0; i < n->num_children; i++) {
            int ci = n->children[i];
            MCTSNode *child = &nodes[ci];

            if (child->visits == 0) {
                best_child = ci;
                break;
            }

            double exploitation = child->value / child->visits;
            /* White wants to minimize Black's value */
            if (n->state.current_player == -1)
                exploitation = 1.0 - exploitation;

            double exploration = exploration_c * sqrt(log_parent / child->visits);
            double score = exploitation + exploration;

            if (score > best_score) {
                best_score = score;
                best_child = ci;
            }
        }
        idx = best_child;
    }
}

static int mcts_expand(int idx) {
    if (check_terminal(idx)) return idx;

    init_untried(idx);
    MCTSNode *n = &nodes[idx];
    if (n->num_untried == 0) return idx;

    /* Pop last untried move */
    int move = n->untried_moves[--n->num_untried];

    GameState child_state;
    state_apply_move(&n->state, move, &child_state);

    int child_idx = make_node(&child_state, idx, move);
    if (child_idx < 0) return idx; /* Out of nodes */

    n->children[n->num_children++] = child_idx;
    return child_idx;
}

static double mcts_evaluate(int idx) {
    MCTSNode *n = &nodes[idx];

    if (n->is_terminal == 1)
        return state_result_black(&n->state);

    uint64_t h = board_hash_fnv(n->state.board);
    if (n->state.current_player == -1)
        h ^= 0x9E3779B97F4A7C15ULL;
    double cached;
    if (eval_cache_get(h, &cached))
        return cached;

    double value = nn_evaluate(n->state.board, n->state.current_player);
    eval_cache_put(h, value);
    return value;
}

static void mcts_backprop(int idx, double value) {
    while (idx >= 0) {
        nodes[idx].visits++;
        nodes[idx].value += value;
        idx = nodes[idx].parent;
    }
}

/* Run MCTS search. Returns best move (0-80 or PASS_MOVE). */
int mcts_search(const int8_t *board, int8_t player, int consecutive_passes,
                int move_count, uint64_t ko_hash, int iterations,
                double exploration_c) {
    num_nodes = 0;
    eval_cache_clear();

    GameState root_state;
    memcpy(root_state.board, board, NUM_CELLS);
    root_state.current_player = player;
    root_state.consecutive_passes = consecutive_passes;
    root_state.move_count = move_count;
    root_state.ko_hash = ko_hash;

    int root = make_node(&root_state, -1, -1);

    for (int i = 0; i < iterations; i++) {
        int leaf = mcts_select(exploration_c);
        int child = mcts_expand(leaf);
        double value = mcts_evaluate(child);
        mcts_backprop(child, value);
    }

    /* Choose most-visited child */
    MCTSNode *r = &nodes[root];
    if (r->num_children == 0) {
        int moves[82];
        int n = get_legal_moves(board, player, ko_hash, moves);
        return n > 0 ? moves[0] : PASS_MOVE;
    }

    int best_child = r->children[0];
    int best_visits = nodes[best_child].visits;
    for (int i = 1; i < r->num_children; i++) {
        int ci = r->children[i];
        if (nodes[ci].visits > best_visits) {
            best_visits = nodes[ci].visits;
            best_child = ci;
        }
    }
    return nodes[best_child].move;
}

/* ---------- GTP Interface (for tournament integration) ---------- */

static GameState game_state;
static int game_iterations = 2000;
static double game_exploration_c = 0.7;

void gtp_init(int iterations) {
    state_init(&game_state);
    game_iterations = iterations;
}

/* Apply a move to the internal game state. Returns 0 on success. */
int gtp_play(int8_t player, int move) {
    GameState new_state;
    state_apply_move(&game_state, move, &new_state);
    memcpy(&game_state, &new_state, sizeof(GameState));
    return 0;
}

/* Generate a move for the given player. Returns move (0-80 or PASS_MOVE). */
int gtp_genmove(int8_t player) {
    if (game_state.current_player != player) {
        /* Shouldn't happen in normal play, but handle it */
        game_state.current_player = player;
    }
    return mcts_search(game_state.board, player,
                       game_state.consecutive_passes,
                       game_state.move_count,
                       game_state.ko_hash,
                       game_iterations,
                       game_exploration_c);
}

/* Get the current board state */
void gtp_get_board(int8_t *out_board) {
    memcpy(out_board, game_state.board, NUM_CELLS);
}

int gtp_is_terminal(void) {
    return state_is_terminal(&game_state);
}

/* Score from Black's perspective: positive = Black wins */
double gtp_score(void) {
    return score_position(game_state.board, 6.5);
}

/* ---------- Standalone benchmark / test ---------- */

#ifndef NO_MAIN
static void print_board(const int8_t *board) {
    const char *cols = "ABCDEFGHJ";
    printf("  ");
    for (int c = 0; c < BOARD_SIZE; c++) printf("%c ", cols[c]);
    printf("\n");
    for (int r = 0; r < BOARD_SIZE; r++) {
        printf("%2d", BOARD_SIZE - r);
        for (int c = 0; c < BOARD_SIZE; c++) {
            int8_t v = board[r * BOARD_SIZE + c];
            printf(" %c", v == 1 ? 'X' : v == -1 ? 'O' : '.');
        }
        printf(" %d\n", BOARD_SIZE - r);
    }
    printf("  ");
    for (int c = 0; c < BOARD_SIZE; c++) printf("%c ", cols[c]);
    printf("\n");
}

static const char *move_to_str(int move) {
    static char buf[8];
    if (move == PASS_MOVE) return "pass";
    const char *cols = "ABCDEFGHJ";
    int r = move / BOARD_SIZE, c = move % BOARD_SIZE;
    snprintf(buf, sizeof(buf), "%c%d", cols[c], BOARD_SIZE - r);
    return buf;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <weights.bin> [iterations]\n", argv[0]);
        return 1;
    }

    if (load_weights(argv[1]) != 0) {
        fprintf(stderr, "Failed to load weights from %s\n", argv[1]);
        return 1;
    }
    printf("Weights loaded.\n");

    int iterations = 2000;
    if (argc >= 3) iterations = atoi(argv[2]);
    printf("MCTS iterations: %d\n\n", iterations);

    /* Self-play benchmark */
    GameState state;
    state_init(&state);

    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);

    int move_count = 0;
    while (!state_is_terminal(&state) && move_count < MAX_GAME_MOVES) {
        int move = mcts_search(state.board, state.current_player,
                               state.consecutive_passes, state.move_count,
                               state.ko_hash, iterations, 0.7);

        printf("Move %3d (%s): %s\n", move_count + 1,
               state.current_player == 1 ? "B" : "W",
               move_to_str(move));

        GameState new_state;
        state_apply_move(&state, move, &new_state);
        memcpy(&state, &new_state, sizeof(GameState));
        move_count++;
    }

    clock_gettime(CLOCK_MONOTONIC, &t1);
    double elapsed = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9;

    printf("\n");
    print_board(state.board);

    double diff = score_position(state.board, 6.5);
    printf("\nResult: %s wins by %.1f\n",
           diff > 0 ? "Black" : "White", fabs(diff));
    printf("Game: %d moves in %.2f seconds (%.1f ms/move)\n",
           move_count, elapsed, elapsed * 1000.0 / move_count);

    return 0;
}
#endif
