// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

/**
 * MCTS GPU Neural Network Benchmark — BATCHED VERSION
 * ====================================================
 *
 * Batched leaf evaluation for fair GPU comparison.
 * Instead of evaluating one position per iteration (underutilizing the GPU),
 * this version accumulates B leaf positions and evaluates them in one cuBLAS call.
 *
 * This implements "virtual loss" batching (standard in Leela Chess Zero, KataGo):
 *   1. Run selection + expansion for B iterations, adding virtual losses
 *   2. Batch all B leaf positions into one GPU inference call
 *   3. Backpropagate all B results, removing virtual losses
 *
 * Usage:
 *   ./benchmark_gpu_nn_batched --board-size 9 --iterations 5000 --batch-size 64
 *   ./benchmark_gpu_nn_batched --all-sizes --batch-size 64
 *   ./benchmark_gpu_nn_batched --all-sizes --batch-size 256
 *
 * Compilation:
 *   nvcc -std=c++17 -O3 -arch=sm_80 -lcublas -o benchmark_gpu_nn_batched benchmark_gpu_nn_batched.cu
 */

#include <iostream>
#include <vector>
#include <unordered_map>
#include <map>
#include <memory>
#include <cmath>
#include <random>
#include <chrono>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <cstring>
#include <algorithm>
#include <thread>
#include <unistd.h>
#include <cuda_runtime.h>
#include <cublas_v2.h>

// ============================================================================
// CUDA ERROR CHECKING
// ============================================================================

#define CUDA_CHECK(call) \
    do { \
        cudaError_t err = call; \
        if (err != cudaSuccess) { \
            std::cerr << "CUDA error in " << __FILE__ << ":" << __LINE__ << ": " \
                      << cudaGetErrorString(err) << std::endl; \
            exit(1); \
        } \
    } while(0)

#define CUBLAS_CHECK(call) \
    do { \
        cublasStatus_t status = call; \
        if (status != CUBLAS_STATUS_SUCCESS) { \
            std::cerr << "cuBLAS error in " << __FILE__ << ":" << __LINE__ << std::endl; \
            exit(1); \
        } \
    } while(0)

// ============================================================================
// NETWORK ARCHITECTURE SPECIFICATIONS
// ============================================================================

struct NetworkArchitecture {
    int input_size;
    int hidden_size;
    int output_size;
};

static const std::map<int, NetworkArchitecture> ARCH_MAP = {
    {2, {8, 16, 3}},
    {3, {18, 24, 3}},
    {5, {50, 32, 3}},
    {9, {162, 96, 3}},
    {13, {338, 128, 3}},
    {19, {722, 192, 3}}
};

// ============================================================================
// CUDA KERNELS
// ============================================================================

__global__ void relu_kernel(float* data, int size) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) {
        data[idx] = fmaxf(0.0f, data[idx]);
    }
}

__global__ void softmax_kernel(float* data, int batch_size, int num_classes) {
    int batch_idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (batch_idx < batch_size) {
        float* row = data + batch_idx * num_classes;
        float max_val = row[0];
        for (int i = 1; i < num_classes; i++) {
            max_val = fmaxf(max_val, row[i]);
        }
        float sum = 0.0f;
        for (int i = 0; i < num_classes; i++) {
            row[i] = expf(row[i] - max_val);
            sum += row[i];
        }
        for (int i = 0; i < num_classes; i++) {
            row[i] /= sum;
        }
    }
}

__global__ void encode_board_kernel(const int* boards, float* encoded,
                                     int batch_size, int board_size_sq,
                                     const int* current_players) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int batch_idx = idx / (2 * board_size_sq);
    int pos_idx = idx % (2 * board_size_sq);

    if (batch_idx < batch_size) {
        int channel = pos_idx / board_size_sq;
        int cell_idx = pos_idx % board_size_sq;
        int board_value = boards[batch_idx * board_size_sq + cell_idx];
        int current_player = current_players[batch_idx];

        if (current_player == 1) {
            if (channel == 0) encoded[idx] = (board_value == 1) ? 1.0f : 0.0f;
            else               encoded[idx] = (board_value == 2) ? 1.0f : 0.0f;
        } else {
            if (channel == 0) encoded[idx] = (board_value == 2) ? 1.0f : 0.0f;
            else               encoded[idx] = (board_value == 1) ? 1.0f : 0.0f;
        }
    }
}

// ============================================================================
// GPU NEURAL NETWORK CLASS (same as single-position version)
// ============================================================================

class GPUNeuralNetwork {
private:
    int board_size;
    NetworkArchitecture arch;
    cublasHandle_t cublas_handle;
    float* d_weights1;
    float* d_weights2;
    float* d_input;
    float* d_hidden;
    float* d_output;
    int max_batch_size;

    void load_weights(const std::string& filepath, float** d_weights, int rows, int cols) {
        std::ifstream file(filepath, std::ios::binary);
        if (!file.is_open()) {
            throw std::runtime_error("Failed to open weight file: " + filepath);
        }
        int32_t file_rows, file_cols;
        file.read(reinterpret_cast<char*>(&file_rows), sizeof(int32_t));
        file.read(reinterpret_cast<char*>(&file_cols), sizeof(int32_t));
        if (file_rows != rows || file_cols != cols) {
            throw std::runtime_error("Weight dimension mismatch");
        }
        std::vector<float> h_weights(rows * cols);
        file.read(reinterpret_cast<char*>(h_weights.data()), rows * cols * sizeof(float));
        file.close();
        CUDA_CHECK(cudaMalloc(d_weights, rows * cols * sizeof(float)));
        CUDA_CHECK(cudaMemcpy(*d_weights, h_weights.data(), rows * cols * sizeof(float),
                             cudaMemcpyHostToDevice));
    }

public:
    GPUNeuralNetwork(int size, int batch_size = 256)
        : board_size(size), max_batch_size(batch_size) {
        auto it = ARCH_MAP.find(board_size);
        if (it == ARCH_MAP.end()) {
            throw std::runtime_error("Unsupported board size: " + std::to_string(board_size));
        }
        arch = it->second;
        CUBLAS_CHECK(cublasCreate(&cublas_handle));
        std::string weights_dir = "weights/" + std::to_string(board_size) + "x" +
                                 std::to_string(board_size) + "/";
        load_weights(weights_dir + "weights1.bin", &d_weights1, arch.input_size, arch.hidden_size);
        load_weights(weights_dir + "weights2.bin", &d_weights2, arch.hidden_size, arch.output_size);
        CUDA_CHECK(cudaMalloc(&d_input, max_batch_size * arch.input_size * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&d_hidden, max_batch_size * arch.hidden_size * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&d_output, max_batch_size * arch.output_size * sizeof(float)));
        std::cout << "GPU Neural network loaded: " << board_size << "x" << board_size
                  << " (" << arch.input_size << "->" << arch.hidden_size << "->" << arch.output_size << ")"
                  << " max_batch=" << max_batch_size << std::endl;
    }

    ~GPUNeuralNetwork() {
        cudaFree(d_weights1); cudaFree(d_weights2);
        cudaFree(d_input); cudaFree(d_hidden); cudaFree(d_output);
        cublasDestroy(cublas_handle);
    }

    void forward_batch(const std::vector<std::vector<int>>& boards,
                      const std::vector<int>& current_players,
                      std::vector<float>& outputs) {
        int batch_size = boards.size();
        if (batch_size == 0) return;
        if (batch_size > max_batch_size) {
            throw std::runtime_error("Batch size " + std::to_string(batch_size) +
                                     " exceeds maximum " + std::to_string(max_batch_size));
        }

        int board_size_sq = board_size * board_size;
        std::vector<int> h_boards(batch_size * board_size_sq);
        for (int i = 0; i < batch_size; i++) {
            std::copy(boards[i].begin(), boards[i].end(),
                     h_boards.begin() + i * board_size_sq);
        }

        int* d_boards;
        int* d_players;
        CUDA_CHECK(cudaMalloc(&d_boards, batch_size * board_size_sq * sizeof(int)));
        CUDA_CHECK(cudaMalloc(&d_players, batch_size * sizeof(int)));
        CUDA_CHECK(cudaMemcpy(d_boards, h_boards.data(),
                             batch_size * board_size_sq * sizeof(int), cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaMemcpy(d_players, current_players.data(),
                             batch_size * sizeof(int), cudaMemcpyHostToDevice));

        int total_elements = batch_size * arch.input_size;
        int threads = 256;
        int blocks = (total_elements + threads - 1) / threads;
        encode_board_kernel<<<blocks, threads>>>(d_boards, d_input, batch_size,
                                                  board_size_sq, d_players);

        const float alpha = 1.0f, beta = 0.0f;
        CUBLAS_CHECK(cublasSgemm(cublas_handle, CUBLAS_OP_T, CUBLAS_OP_N,
                                arch.hidden_size, batch_size, arch.input_size,
                                &alpha, d_weights1, arch.input_size,
                                d_input, arch.input_size,
                                &beta, d_hidden, arch.hidden_size));

        int hidden_elements = batch_size * arch.hidden_size;
        blocks = (hidden_elements + threads - 1) / threads;
        relu_kernel<<<blocks, threads>>>(d_hidden, hidden_elements);

        CUBLAS_CHECK(cublasSgemm(cublas_handle, CUBLAS_OP_T, CUBLAS_OP_N,
                                arch.output_size, batch_size, arch.hidden_size,
                                &alpha, d_weights2, arch.hidden_size,
                                d_hidden, arch.hidden_size,
                                &beta, d_output, arch.output_size));

        blocks = (batch_size + threads - 1) / threads;
        softmax_kernel<<<blocks, threads>>>(d_output, batch_size, arch.output_size);

        std::vector<float> h_output(batch_size * arch.output_size);
        CUDA_CHECK(cudaMemcpy(h_output.data(), d_output,
                             batch_size * arch.output_size * sizeof(float),
                             cudaMemcpyDeviceToHost));

        outputs.resize(batch_size);
        for (int i = 0; i < batch_size; i++) {
            float* probs = &h_output[i * arch.output_size];
            if (current_players[i] == 1) {
                outputs[i] = probs[2] * 1.0f + probs[1] * 0.0f + probs[0] * (-1.0f);
            } else {
                outputs[i] = probs[0] * 1.0f + probs[1] * 0.0f + probs[2] * (-1.0f);
            }
        }

        cudaFree(d_boards);
        cudaFree(d_players);
    }
};

// ============================================================================
// SYSTEM UTILITIES
// ============================================================================

std::string get_system_id() {
    return "local_system";
}

std::string get_gpu_name() {
    cudaDeviceProp prop;
    CUDA_CHECK(cudaGetDeviceProperties(&prop, 0));
    return std::string(prop.name);
}

std::string sanitize_filename(const std::string& str) {
    std::string result;
    for (char c : str) {
        if (std::isalnum(c)) result += std::tolower(c);
        else if (c == ' ' || c == '-' || c == '(' || c == ')') {
            if (!result.empty() && result.back() != '_') result += '_';
        }
    }
    while (!result.empty() && result.back() == '_') result.pop_back();
    return result;
}

// ============================================================================
// ENERGY MONITORING
// ============================================================================

class GPUEnergyMonitor {
private:
    double tdp_watts;
    double estimate_tdp() {
        std::string gpu_name = get_gpu_name();
        if (gpu_name.find("H100") != std::string::npos) return 700.0;
        if (gpu_name.find("A100") != std::string::npos) return 400.0;
        if (gpu_name.find("V100") != std::string::npos) return 300.0;
        return 250.0;
    }
public:
    GPUEnergyMonitor() { tdp_watts = estimate_tdp(); }
    double estimate_energy(double time_seconds) { return tdp_watts * time_seconds; }
    double get_tdp() const { return tdp_watts; }
};

// ============================================================================
// GAME STATE
// ============================================================================

struct Move {
    int row, col;
    Move(int r = -1, int c = -1) : row(r), col(c) {}
    bool is_valid() const { return row >= 0 && col >= 0; }
};

class GameState {
public:
    static const int MAX_SIZE = 19;
    int board[MAX_SIZE][MAX_SIZE];
    int board_size;
    int current_player;
    int move_count;

    GameState(int size = 5) : board_size(size), current_player(1), move_count(0) {
        memset(board, 0, sizeof(board));
    }

    std::vector<Move> get_legal_moves() const {
        std::vector<Move> moves;
        for (int i = 0; i < board_size; i++)
            for (int j = 0; j < board_size; j++)
                if (board[i][j] == 0) moves.emplace_back(i, j);
        return moves;
    }

    void apply_move(const Move& move) {
        board[move.row][move.col] = current_player;
        current_player = 3 - current_player;
        move_count++;
    }

    bool is_terminal() const { return move_count >= board_size * board_size; }

    std::vector<int> to_vector() const {
        std::vector<int> vec(board_size * board_size);
        for (int i = 0; i < board_size; i++)
            for (int j = 0; j < board_size; j++)
                vec[i * board_size + j] = board[i][j];
        return vec;
    }

    size_t hash() const {
        size_t h = 0;
        for (int i = 0; i < board_size; i++)
            for (int j = 0; j < board_size; j++)
                h = h * 31 + board[i][j];
        return h;
    }
};

struct GameStateHash {
    size_t operator()(const GameState& state) const { return state.hash(); }
};
struct GameStateEqual {
    bool operator()(const GameState& a, const GameState& b) const {
        if (a.board_size != b.board_size) return false;
        for (int i = 0; i < a.board_size; i++)
            for (int j = 0; j < a.board_size; j++)
                if (a.board[i][j] != b.board[i][j]) return false;
        return true;
    }
};

// ============================================================================
// MCTS NODE
// ============================================================================

struct MCTSNode {
    GameState state;
    MCTSNode* parent;
    std::unordered_map<Move*, MCTSNode*, std::hash<Move*>> children;
    int visits;
    double wins;
    double virtual_loss;  // For batched evaluation
    std::vector<Move> untried_moves;

    MCTSNode(const GameState& s, MCTSNode* p = nullptr)
        : state(s), parent(p), visits(0), wins(0.0), virtual_loss(0.0) {
        untried_moves = s.get_legal_moves();
    }

    ~MCTSNode() {
        for (auto& pair : children) {
            delete pair.first;
            delete pair.second;
        }
    }

    bool is_fully_expanded() const { return untried_moves.empty(); }
    bool is_terminal() const { return state.is_terminal(); }

    double ucb1(double exploration_constant) const {
        if (visits == 0) return INFINITY;
        // Include virtual loss in visit count to discourage re-selection
        double effective_visits = visits + virtual_loss;
        double exploitation = wins / effective_visits;
        double exploration = exploration_constant * std::sqrt(std::log(parent->visits + parent->virtual_loss) / effective_visits);
        return exploitation + exploration;
    }
};

// ============================================================================
// BATCHED MCTS ENGINE
// ============================================================================

struct PendingEval {
    MCTSNode* node;
    std::vector<int> board_vec;
    int current_player;
};

class BatchedMCTSEngine {
private:
    std::mt19937 rng;
    double exploration_constant;
    MCTSNode* root;
    GPUNeuralNetwork* neural_net;
    int batch_size;

    // Timing accumulators
    double time_selection;
    double time_expansion;
    double time_simulation;
    double time_backprop;

public:
    BatchedMCTSEngine(int board_size, int batch_sz = 64,
                      double exploration = 1.414, unsigned seed = 42)
        : rng(seed), exploration_constant(exploration), root(nullptr),
          batch_size(batch_sz),
          time_selection(0), time_expansion(0), time_simulation(0), time_backprop(0) {
        neural_net = new GPUNeuralNetwork(board_size, batch_sz);
    }

    ~BatchedMCTSEngine() {
        if (root) delete root;
        if (neural_net) delete neural_net;
    }

    std::vector<double> get_phase_times() const {
        return {time_selection, time_expansion, time_simulation, time_backprop};
    }

    MCTSNode* selection(MCTSNode* node) {
        while (!node->is_terminal()) {
            if (!node->is_fully_expanded()) return node;
            double best_score = -INFINITY;
            MCTSNode* best_child = nullptr;
            for (auto& pair : node->children) {
                MCTSNode* child = pair.second;
                double score = child->ucb1(exploration_constant);
                if (score > best_score) {
                    best_score = score;
                    best_child = child;
                }
            }
            if (!best_child) break;
            node = best_child;
        }
        return node;
    }

    MCTSNode* expansion(MCTSNode* node) {
        if (!node->untried_moves.empty()) {
            std::uniform_int_distribution<size_t> dist(0, node->untried_moves.size() - 1);
            size_t idx = dist(rng);
            Move move = node->untried_moves[idx];
            node->untried_moves.erase(node->untried_moves.begin() + idx);

            GameState new_state = node->state;
            new_state.apply_move(move);

            Move* move_ptr = new Move(move);
            MCTSNode* child = new MCTSNode(new_state, node);
            node->children[move_ptr] = child;
            return child;
        }
        return node;
    }

    void backpropagation(MCTSNode* node, double result) {
        while (node != nullptr) {
            node->visits++;
            node->wins += result;
            node->virtual_loss = std::max(0.0, node->virtual_loss - 1.0);
            result = 1.0 - result;
            node = node->parent;
        }
    }

    void add_virtual_loss(MCTSNode* node) {
        while (node != nullptr) {
            node->virtual_loss += 1.0;
            node = node->parent;
        }
    }

    void search(const GameState& initial_state, int total_iterations) {
        using Clock = std::chrono::high_resolution_clock;

        if (root) delete root;
        root = new MCTSNode(initial_state);
        time_selection = time_expansion = time_simulation = time_backprop = 0;

        int completed = 0;
        while (completed < total_iterations) {
            int current_batch = std::min(batch_size, total_iterations - completed);

            // Phase 1 & 2: Selection + Expansion for the batch
            std::vector<PendingEval> pending;
            pending.reserve(current_batch);

            auto t0 = Clock::now();
            for (int i = 0; i < current_batch; i++) {
                MCTSNode* node = selection(root);
                auto t1 = Clock::now();
                time_selection += std::chrono::duration<double>(t1 - t0).count();

                t0 = t1;
                if (!node->is_terminal() && node->visits > 0) {
                    node = expansion(node);
                }
                t1 = Clock::now();
                time_expansion += std::chrono::duration<double>(t1 - t0).count();

                // Add virtual loss to discourage re-selecting this path
                add_virtual_loss(node);

                // Buffer for batch evaluation
                PendingEval pe;
                pe.node = node;
                pe.board_vec = node->state.to_vector();
                pe.current_player = node->state.current_player;
                pending.push_back(pe);

                t0 = Clock::now();
            }

            // Phase 3: Batch GPU evaluation
            auto t_sim_start = Clock::now();

            std::vector<std::vector<int>> boards(pending.size());
            std::vector<int> players(pending.size());
            for (size_t i = 0; i < pending.size(); i++) {
                boards[i] = pending[i].board_vec;
                players[i] = pending[i].current_player;
            }

            std::vector<float> nn_values;
            neural_net->forward_batch(boards, players, nn_values);

            auto t_sim_end = Clock::now();
            time_simulation += std::chrono::duration<double>(t_sim_end - t_sim_start).count();

            // Phase 4: Backpropagation for all
            auto t_bp_start = Clock::now();
            for (size_t i = 0; i < pending.size(); i++) {
                double result = (nn_values[i] + 1.0) / 2.0;  // Map [-1,1] to [0,1]
                backpropagation(pending[i].node, result);
            }
            auto t_bp_end = Clock::now();
            time_backprop += std::chrono::duration<double>(t_bp_end - t_bp_start).count();

            completed += current_batch;
        }
    }

    int count_nodes(MCTSNode* node) const {
        if (!node) return 0;
        int count = 1;
        for (auto& pair : node->children) count += count_nodes(pair.second);
        return count;
    }

    int get_tree_size() const { return count_nodes(root); }
};

// ============================================================================
// BENCHMARKING
// ============================================================================

struct BenchmarkResult {
    int board_size;
    int iterations;
    int batch_size;
    double total_time_s;
    double iterations_per_sec;
    double energy_j;
    double energy_per_iter_uj;
    int tree_size;
    std::vector<double> phase_times;
    std::string gpu_name;
    double tdp_watts;
    int trial_num;
};

BenchmarkResult run_benchmark(int board_size, int iterations, int batch_size) {
    std::cout << "\n" << std::string(70, '=') << std::endl;
    std::cout << "MCTS GPU NN BATCHED Benchmark - " << board_size << "x" << board_size
              << " (batch=" << batch_size << ")" << std::endl;
    std::cout << std::string(70, '=') << std::endl;
    std::cout << "Iterations: " << iterations << ", Batch size: " << batch_size << std::endl;

    GPUEnergyMonitor energy_monitor;
    BatchedMCTSEngine engine(board_size, batch_size);
    GameState initial_state(board_size);

    // Warmup
    {
        BatchedMCTSEngine warmup_engine(board_size, batch_size);
        GameState warmup_state(board_size);
        warmup_engine.search(warmup_state, std::min(batch_size * 2, iterations));
    }

    auto time_start = std::chrono::high_resolution_clock::now();
    engine.search(initial_state, iterations);
    auto time_end = std::chrono::high_resolution_clock::now();

    double total_time = std::chrono::duration<double>(time_end - time_start).count();
    double energy_consumed = energy_monitor.estimate_energy(total_time);

    BenchmarkResult result;
    result.board_size = board_size;
    result.iterations = iterations;
    result.batch_size = batch_size;
    result.total_time_s = total_time;
    result.iterations_per_sec = iterations / total_time;
    result.energy_j = energy_consumed;
    result.energy_per_iter_uj = (energy_consumed * 1e6) / iterations;
    result.tree_size = engine.get_tree_size();
    result.phase_times = engine.get_phase_times();
    result.gpu_name = get_gpu_name();
    result.tdp_watts = energy_monitor.get_tdp();

    std::cout << "\nResults:" << std::endl;
    std::cout << "  GPU: " << result.gpu_name << std::endl;
    std::cout << "  Batch size: " << batch_size << std::endl;
    std::cout << "  Total time: " << total_time * 1000.0 << " ms" << std::endl;
    std::cout << "  Throughput: " << result.iterations_per_sec << " iter/s" << std::endl;
    std::cout << "  Energy (est): " << energy_consumed << " J (" << energy_consumed * 1000 << " mJ)" << std::endl;
    std::cout << "  Energy/iter: " << result.energy_per_iter_uj << " uJ" << std::endl;
    std::cout << "  Tree size: " << result.tree_size << " nodes" << std::endl;

    // Phase breakdown
    auto pt = result.phase_times;
    double phase_total = pt[0] + pt[1] + pt[2] + pt[3];
    if (phase_total > 0) {
        std::cout << "  Phase breakdown:" << std::endl;
        std::cout << "    Selection:     " << pt[0]*1000 << " ms (" << pt[0]/phase_total*100 << "%)" << std::endl;
        std::cout << "    Expansion:     " << pt[1]*1000 << " ms (" << pt[1]/phase_total*100 << "%)" << std::endl;
        std::cout << "    Simulation:    " << pt[2]*1000 << " ms (" << pt[2]/phase_total*100 << "%)" << std::endl;
        std::cout << "    Backprop:      " << pt[3]*1000 << " ms (" << pt[3]/phase_total*100 << "%)" << std::endl;
    }

    return result;
}

void write_csv_header(std::ofstream& csv) {
    csv << "timestamp,system_id,processor,cpu_count,power_method,board_size,num_positions,"
        << "iterations,batch_size,trial_num,"
        << "total_latency_ms,total_power_mw,total_energy_uj,tree_size,"
        << "selection_latency_ms,selection_power_mw,selection_energy_uj,selection_percent,"
        << "expansion_latency_ms,expansion_power_mw,expansion_energy_uj,expansion_percent,"
        << "simulation_latency_ms,simulation_power_mw,simulation_energy_uj,simulation_percent,"
        << "backpropagation_latency_ms,backpropagation_power_mw,backpropagation_energy_uj,backpropagation_percent"
        << std::endl;
}

void write_csv_row(std::ofstream& csv, const BenchmarkResult& result) {
    auto now = std::chrono::system_clock::now();
    auto now_time_t = std::chrono::system_clock::to_time_t(now);
    char timestamp[100];
    std::strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", std::localtime(&now_time_t));

    cudaDeviceProp prop;
    cudaGetDeviceProperties(&prop, 0);
    int sm_count = prop.multiProcessorCount;

    double total_latency_ms = result.total_time_s * 1000.0;
    double total_energy_uj = result.energy_j * 1e6;
    double total_power_mw = (total_latency_ms > 0) ? (total_energy_uj / total_latency_ms) : 0.0;

    double selection_ms = result.phase_times[0] * 1000.0;
    double expansion_ms = result.phase_times[1] * 1000.0;
    double simulation_ms = result.phase_times[2] * 1000.0;
    double backprop_ms = result.phase_times[3] * 1000.0;
    double phase_total_ms = selection_ms + expansion_ms + simulation_ms + backprop_ms;

    auto phase_energy = [&](double ms) { return (phase_total_ms > 0) ? (ms / phase_total_ms * total_energy_uj) : 0.0; };
    auto phase_power = [&](double ms, double uj) { return (ms > 0) ? (uj / ms) : 0.0; };
    auto phase_pct = [&](double ms) { return (phase_total_ms > 0) ? (ms / phase_total_ms * 100.0) : 0.0; };

    int num_positions = result.board_size * result.board_size;

    csv << std::fixed << std::setprecision(6);
    csv << timestamp << "," << get_system_id() << "," << result.gpu_name << ","
        << sm_count << ",TDP," << result.board_size << "," << num_positions << ","
        << result.iterations << "," << result.batch_size << "," << result.trial_num << ","
        << total_latency_ms << "," << total_power_mw << "," << total_energy_uj << ","
        << result.tree_size << ","
        << selection_ms << "," << phase_power(selection_ms, phase_energy(selection_ms)) << ","
        << phase_energy(selection_ms) << "," << phase_pct(selection_ms) << ","
        << expansion_ms << "," << phase_power(expansion_ms, phase_energy(expansion_ms)) << ","
        << phase_energy(expansion_ms) << "," << phase_pct(expansion_ms) << ","
        << simulation_ms << "," << phase_power(simulation_ms, phase_energy(simulation_ms)) << ","
        << phase_energy(simulation_ms) << "," << phase_pct(simulation_ms) << ","
        << backprop_ms << "," << phase_power(backprop_ms, phase_energy(backprop_ms)) << ","
        << phase_energy(backprop_ms) << "," << phase_pct(backprop_ms) << std::endl;
}

// ============================================================================
// MAIN
// ============================================================================

int main(int argc, char* argv[]) {
    int board_size = 9;
    int iterations = 5000;
    int batch_size = 64;
    bool all_sizes = false;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--board-size" && i + 1 < argc) board_size = std::stoi(argv[++i]);
        else if (arg == "--iterations" && i + 1 < argc) iterations = std::stoi(argv[++i]);
        else if (arg == "--batch-size" && i + 1 < argc) batch_size = std::stoi(argv[++i]);
        else if (arg == "--all-sizes") all_sizes = true;
        else if (arg == "--help") {
            std::cout << "Usage: " << argv[0] << " [options]\n"
                      << "Options:\n"
                      << "  --board-size N    Board size (default: 9)\n"
                      << "  --iterations N    Total iterations (default: 5000)\n"
                      << "  --batch-size N    Batch size for GPU inference (default: 64)\n"
                      << "  --all-sizes       Run for all board sizes\n"
                      << "  --help            Show this help\n";
            return 0;
        }
    }

    std::string gpu_name = sanitize_filename(get_gpu_name());

    auto now = std::chrono::system_clock::now();
    std::time_t now_time = std::chrono::system_clock::to_time_t(now);
    std::tm* tm_now = std::localtime(&now_time);
    std::stringstream ts;
    ts << std::put_time(tm_now, "%Y%m%d_%H%M%S");

    std::string csv_filename = "results/nn/gpu_nn_batched_b" + std::to_string(batch_size) +
                               "_" + gpu_name + "_" + ts.str() + ".csv";

    std::ofstream csv(csv_filename);
    if (!csv.is_open()) {
        std::cerr << "ERROR: Failed to open CSV file: " << csv_filename << std::endl;
        return 1;
    }
    write_csv_header(csv);

    if (all_sizes) {
        std::vector<std::pair<int, int>> size_iterations = {
            {2, 200}, {3, 500}, {5, 1000}, {9, 5000}, {13, 7500}, {19, 10000}
        };
        const int num_trials = 5;

        for (const auto& [size, iters] : size_iterations) {
            for (int trial = 1; trial <= num_trials; trial++) {
                BenchmarkResult result = run_benchmark(size, iters, batch_size);
                result.trial_num = trial;
                write_csv_row(csv, result);
            }
        }
    } else {
        BenchmarkResult result = run_benchmark(board_size, iterations, batch_size);
        result.trial_num = 1;
        write_csv_row(csv, result);
    }

    csv.close();
    std::cout << "\nResults written to: " << csv_filename << std::endl;
    return 0;
}
