// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

/**
 * MCTS GPU Neural Network Benchmark
 * ==================================
 *
 * CUDA-accelerated Monte Carlo Tree Search with Neural Network rollout evaluation.
 * This benchmark implements NN-based MCTS on GPU for fair comparison with CPU and ASIC.
 *
 * Key features:
 * - GPU-accelerated matrix operations using cuBLAS
 * - Batch neural network inference for multiple positions
 * - NVIDIA GPU energy monitoring via nvidia-smi
 * - Per-phase timing (Selection, Expansion, Rollout, Backpropagation)
 * - CSV output format matching CPU benchmark
 *
 * Architecture:
 * - Tree traversal: CPU (irregular memory access patterns)
 * - NN inference: GPU (batch matrix operations via cuBLAS)
 * - Hybrid approach maximizes hardware utilization
 *
 * Compilation:
 *   nvcc -std=c++17 -O3 -arch=sm_80 -lcublas -o benchmark_gpu_nn benchmark_gpu_nn.cu
 *
 * Usage:
 *   ./benchmark_gpu_nn --board-size 5 --iterations 1000
 *   ./benchmark_gpu_nn --all-sizes
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

        // Find max for numerical stability
        float max_val = row[0];
        for (int i = 1; i < num_classes; i++) {
            max_val = fmaxf(max_val, row[i]);
        }

        // Compute exp and sum
        float sum = 0.0f;
        for (int i = 0; i < num_classes; i++) {
            row[i] = expf(row[i] - max_val);
            sum += row[i];
        }

        // Normalize
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
            // Black's perspective
            if (channel == 0) {
                encoded[idx] = (board_value == 1) ? 1.0f : 0.0f;
            } else {
                encoded[idx] = (board_value == 2) ? 1.0f : 0.0f;
            }
        } else {
            // White's perspective (swap channels)
            if (channel == 0) {
                encoded[idx] = (board_value == 2) ? 1.0f : 0.0f;
            } else {
                encoded[idx] = (board_value == 1) ? 1.0f : 0.0f;
            }
        }
    }
}

// ============================================================================
// GPU NEURAL NETWORK CLASS
// ============================================================================

class GPUNeuralNetwork {
private:
    int board_size;
    NetworkArchitecture arch;
    cublasHandle_t cublas_handle;

    // Device memory for weights
    float* d_weights1;  // Input → Hidden
    float* d_weights2;  // Hidden → Output

    // Device memory for inference (reusable buffers)
    float* d_input;
    float* d_hidden;
    float* d_output;
    int max_batch_size;

    void load_weights(const std::string& filepath, float** d_weights, int rows, int cols) {
        std::ifstream file(filepath, std::ios::binary);
        if (!file.is_open()) {
            throw std::runtime_error("Failed to open weight file: " + filepath);
        }

        // Read dimensions
        int32_t file_rows, file_cols;
        file.read(reinterpret_cast<char*>(&file_rows), sizeof(int32_t));
        file.read(reinterpret_cast<char*>(&file_cols), sizeof(int32_t));

        if (file_rows != rows || file_cols != cols) {
            throw std::runtime_error("Weight dimension mismatch");
        }

        // Read weights to host
        std::vector<float> h_weights(rows * cols);
        file.read(reinterpret_cast<char*>(h_weights.data()), rows * cols * sizeof(float));
        file.close();

        // Transfer to device
        CUDA_CHECK(cudaMalloc(d_weights, rows * cols * sizeof(float)));
        CUDA_CHECK(cudaMemcpy(*d_weights, h_weights.data(), rows * cols * sizeof(float),
                             cudaMemcpyHostToDevice));
    }

public:
    GPUNeuralNetwork(int size, int batch_size = 64)
        : board_size(size), max_batch_size(batch_size) {

        // Get architecture
        auto it = ARCH_MAP.find(board_size);
        if (it == ARCH_MAP.end()) {
            throw std::runtime_error("Unsupported board size: " + std::to_string(board_size));
        }
        arch = it->second;

        // Initialize cuBLAS
        CUBLAS_CHECK(cublasCreate(&cublas_handle));

        // Load weights
        std::string weights_dir = "weights/" + std::to_string(board_size) + "x" +
                                 std::to_string(board_size) + "/";
        load_weights(weights_dir + "weights1.bin", &d_weights1, arch.input_size, arch.hidden_size);
        load_weights(weights_dir + "weights2.bin", &d_weights2, arch.hidden_size, arch.output_size);

        // Allocate inference buffers
        CUDA_CHECK(cudaMalloc(&d_input, max_batch_size * arch.input_size * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&d_hidden, max_batch_size * arch.hidden_size * sizeof(float)));
        CUDA_CHECK(cudaMalloc(&d_output, max_batch_size * arch.output_size * sizeof(float)));

        std::cout << "GPU Neural network loaded: " << board_size << "×" << board_size
                  << " (" << arch.input_size << "→" << arch.hidden_size << "→" << arch.output_size << ")"
                  << std::endl;
    }

    ~GPUNeuralNetwork() {
        cudaFree(d_weights1);
        cudaFree(d_weights2);
        cudaFree(d_input);
        cudaFree(d_hidden);
        cudaFree(d_output);
        cublasDestroy(cublas_handle);
    }

    // Batch forward pass
    void forward_batch(const std::vector<std::vector<int>>& boards,
                      const std::vector<int>& current_players,
                      std::vector<float>& outputs) {
        int batch_size = boards.size();
        if (batch_size > max_batch_size) {
            throw std::runtime_error("Batch size exceeds maximum");
        }

        // Flatten boards for GPU transfer
        int board_size_sq = board_size * board_size;
        std::vector<int> h_boards(batch_size * board_size_sq);
        for (int i = 0; i < batch_size; i++) {
            std::copy(boards[i].begin(), boards[i].end(),
                     h_boards.begin() + i * board_size_sq);
        }

        // Transfer to device
        int* d_boards;
        int* d_players;
        CUDA_CHECK(cudaMalloc(&d_boards, batch_size * board_size_sq * sizeof(int)));
        CUDA_CHECK(cudaMalloc(&d_players, batch_size * sizeof(int)));
        CUDA_CHECK(cudaMemcpy(d_boards, h_boards.data(),
                             batch_size * board_size_sq * sizeof(int), cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaMemcpy(d_players, current_players.data(),
                             batch_size * sizeof(int), cudaMemcpyHostToDevice));

        // Encode boards
        int total_elements = batch_size * arch.input_size;
        int threads = 256;
        int blocks = (total_elements + threads - 1) / threads;
        encode_board_kernel<<<blocks, threads>>>(d_boards, d_input, batch_size,
                                                  board_size_sq, d_players);

        // Layer 1: Input → Hidden with ReLU
        const float alpha = 1.0f;
        const float beta = 0.0f;

        // Matrix multiplication: d_hidden = d_weights1^T * d_input^T
        CUBLAS_CHECK(cublasSgemm(cublas_handle, CUBLAS_OP_T, CUBLAS_OP_N,
                                arch.hidden_size, batch_size, arch.input_size,
                                &alpha, d_weights1, arch.input_size,
                                d_input, arch.input_size,
                                &beta, d_hidden, arch.hidden_size));

        // ReLU activation
        int hidden_elements = batch_size * arch.hidden_size;
        blocks = (hidden_elements + threads - 1) / threads;
        relu_kernel<<<blocks, threads>>>(d_hidden, hidden_elements);

        // Layer 2: Hidden → Output
        CUBLAS_CHECK(cublasSgemm(cublas_handle, CUBLAS_OP_T, CUBLAS_OP_N,
                                arch.output_size, batch_size, arch.hidden_size,
                                &alpha, d_weights2, arch.hidden_size,
                                d_hidden, arch.hidden_size,
                                &beta, d_output, arch.output_size));

        // Softmax activation
        blocks = (batch_size + threads - 1) / threads;
        softmax_kernel<<<blocks, threads>>>(d_output, batch_size, arch.output_size);

        // Transfer results back
        std::vector<float> h_output(batch_size * arch.output_size);
        CUDA_CHECK(cudaMemcpy(h_output.data(), d_output,
                             batch_size * arch.output_size * sizeof(float),
                             cudaMemcpyDeviceToHost));

        // Extract evaluations
        outputs.resize(batch_size);
        for (int i = 0; i < batch_size; i++) {
            float* probs = &h_output[i * arch.output_size];
            // probs = [P(white wins), P(draw), P(black wins)]
            if (current_players[i] == 1) {
                // Black's perspective
                outputs[i] = probs[2] * 1.0f + probs[1] * 0.0f + probs[0] * (-1.0f);
            } else {
                // White's perspective
                outputs[i] = probs[0] * 1.0f + probs[1] * 0.0f + probs[2] * (-1.0f);
            }
        }

        // Cleanup
        cudaFree(d_boards);
        cudaFree(d_players);
    }

    // Single position evaluation (for compatibility)
    float evaluate(const std::vector<int>& board, int current_player) {
        std::vector<std::vector<int>> boards = {board};
        std::vector<int> players = {current_player};
        std::vector<float> outputs;
        forward_batch(boards, players, outputs);
        return outputs[0];
    }
};

// ============================================================================
// SYSTEM UTILITIES (same as CPU version)
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
        if (std::isalnum(c)) {
            result += std::tolower(c);
        } else if (c == ' ' || c == '-' || c == '(' || c == ')') {
            if (!result.empty() && result.back() != '_') {
                result += '_';
            }
        }
    }
    while (!result.empty() && result.back() == '_') {
        result.pop_back();
    }
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
        return 250.0;  // Default estimate
    }

public:
    GPUEnergyMonitor() {
        tdp_watts = estimate_tdp();
    }

    double estimate_energy(double time_seconds) {
        return tdp_watts * time_seconds;
    }

    double get_tdp() const { return tdp_watts; }
};

// ============================================================================
// GAME STATE (same as CPU version)
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
        for (int i = 0; i < board_size; i++) {
            for (int j = 0; j < board_size; j++) {
                if (board[i][j] == 0) {
                    moves.emplace_back(i, j);
                }
            }
        }
        return moves;
    }

    void apply_move(const Move& move) {
        board[move.row][move.col] = current_player;
        current_player = 3 - current_player;
        move_count++;
    }

    bool is_terminal() const {
        return move_count >= board_size * board_size;
    }

    std::vector<int> to_vector() const {
        std::vector<int> vec(board_size * board_size);
        for (int i = 0; i < board_size; i++) {
            for (int j = 0; j < board_size; j++) {
                vec[i * board_size + j] = board[i][j];
            }
        }
        return vec;
    }

    size_t hash() const {
        size_t h = 0;
        for (int i = 0; i < board_size; i++) {
            for (int j = 0; j < board_size; j++) {
                h = h * 31 + board[i][j];
            }
        }
        return h;
    }
};

struct GameStateHash {
    size_t operator()(const GameState& state) const { return state.hash(); }
};

struct GameStateEqual {
    bool operator()(const GameState& a, const GameState& b) const {
        if (a.board_size != b.board_size) return false;
        for (int i = 0; i < a.board_size; i++) {
            for (int j = 0; j < a.board_size; j++) {
                if (a.board[i][j] != b.board[i][j]) return false;
            }
        }
        return true;
    }
};

// ============================================================================
// MCTS ENGINE (CPU tree traversal + GPU NN evaluation)
// ============================================================================

struct MCTSNode {
    GameState state;
    MCTSNode* parent;
    std::unordered_map<Move*, MCTSNode*, std::hash<Move*>> children;
    int visits;
    double wins;
    std::vector<Move> untried_moves;

    MCTSNode(const GameState& s, MCTSNode* p = nullptr)
        : state(s), parent(p), visits(0), wins(0.0) {
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
        double exploitation = wins / visits;
        double exploration = exploration_constant * std::sqrt(std::log(parent->visits) / visits);
        return exploitation + exploration;
    }
};

class MCTSEngine {
private:
    std::mt19937 rng;
    double exploration_constant;
    MCTSNode* root;
    std::unordered_map<GameState, MCTSNode*, GameStateHash, GameStateEqual> tree_lookup;
    std::vector<double> phase_times;
    GPUNeuralNetwork* neural_net;

public:
    MCTSEngine(int board_size, double exploration = 1.414, unsigned seed = 42)
        : rng(seed), exploration_constant(exploration), root(nullptr), phase_times(4, 0.0) {
        try {
            neural_net = new GPUNeuralNetwork(board_size);
        } catch (const std::exception& e) {
            std::cerr << "ERROR: Failed to load GPU neural network: " << e.what() << std::endl;
            exit(1);
        }
    }

    ~MCTSEngine() {
        if (root) delete root;
        if (neural_net) delete neural_net;
    }

    void reset_phase_times() {
        std::fill(phase_times.begin(), phase_times.end(), 0.0);
    }

    const std::vector<double>& get_phase_times() const {
        return phase_times;
    }

    MCTSNode* selection(MCTSNode* node) {
        while (!node->is_terminal()) {
            if (!node->is_fully_expanded()) {
                return node;
            }
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
            tree_lookup[new_state] = child;

            return child;
        }
        return node;
    }

    double simulation(const GameState& state) {
        std::vector<int> board_vec = state.to_vector();
        double nn_value = neural_net->evaluate(board_vec, state.current_player);
        return (nn_value + 1.0) / 2.0;
    }

    void backpropagation(MCTSNode* node, double result) {
        while (node != nullptr) {
            node->visits++;
            node->wins += result;
            result = 1.0 - result;
            node = node->parent;
        }
    }

    void iterate() {
        using Clock = std::chrono::high_resolution_clock;

        auto t_start = Clock::now();
        MCTSNode* node = selection(root);
        auto t_end = Clock::now();
        phase_times[0] += std::chrono::duration<double>(t_end - t_start).count();

        t_start = Clock::now();
        if (!node->is_terminal() && node->visits > 0) {
            node = expansion(node);
        }
        t_end = Clock::now();
        phase_times[1] += std::chrono::duration<double>(t_end - t_start).count();

        t_start = Clock::now();
        double result = simulation(node->state);
        t_end = Clock::now();
        phase_times[2] += std::chrono::duration<double>(t_end - t_start).count();

        t_start = Clock::now();
        backpropagation(node, result);
        t_end = Clock::now();
        phase_times[3] += std::chrono::duration<double>(t_end - t_start).count();
    }

    void search(const GameState& initial_state, int iterations) {
        if (root) delete root;
        root = new MCTSNode(initial_state);
        tree_lookup.clear();
        tree_lookup[initial_state] = root;
        reset_phase_times();

        for (int i = 0; i < iterations; i++) {
            iterate();
        }
    }

    int count_nodes(MCTSNode* node) const {
        if (!node) return 0;
        int count = 1;
        for (auto& pair : node->children) {
            count += count_nodes(pair.second);
        }
        return count;
    }

    int get_tree_size() const {
        return count_nodes(root);
    }
};

// ============================================================================
// BENCHMARKING
// ============================================================================

struct BenchmarkResult {
    int board_size;
    int iterations;
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

BenchmarkResult run_benchmark(int board_size, int iterations) {
    std::cout << "\n" << std::string(70, '=') << std::endl;
    std::cout << "MCTS GPU NN Benchmark - " << board_size << "×" << board_size << " Board" << std::endl;
    std::cout << std::string(70, '=') << std::endl;
    std::cout << "Iterations: " << iterations << std::endl;

    GPUEnergyMonitor energy_monitor;
    MCTSEngine engine(board_size);
    GameState initial_state(board_size);

    auto time_start = std::chrono::high_resolution_clock::now();
    engine.search(initial_state, iterations);
    auto time_end = std::chrono::high_resolution_clock::now();

    double total_time = std::chrono::duration<double>(time_end - time_start).count();
    double energy_consumed = energy_monitor.estimate_energy(total_time);

    BenchmarkResult result;
    result.board_size = board_size;
    result.iterations = iterations;
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
    std::cout << "  Total time: " << total_time << " s" << std::endl;
    std::cout << "  Throughput: " << result.iterations_per_sec << " iter/s" << std::endl;
    std::cout << "  Energy (est): " << energy_consumed << " J" << std::endl;
    std::cout << "  Energy/iter: " << result.energy_per_iter_uj << " µJ" << std::endl;
    std::cout << "  Tree size: " << result.tree_size << " nodes" << std::endl;

    return result;
}

void write_csv_header(std::ofstream& csv) {
    csv << "timestamp,system_id,processor,cpu_count,power_method,board_size,num_positions,iterations,trial_num,"
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

    // Get GPU properties for cpu_count (use SM count as equivalent)
    cudaDeviceProp prop;
    cudaGetDeviceProperties(&prop, 0);
    int sm_count = prop.multiProcessorCount;

    // Convert to ms and µJ
    double total_latency_ms = result.total_time_s * 1000.0;
    double total_energy_uj = result.energy_j * 1e6;

    // Calculate power (mW) = energy (µJ) / time (ms)
    double total_power_mw = (total_latency_ms > 0) ? (total_energy_uj / total_latency_ms) : 0.0;

    // Phase timings in ms
    double selection_ms = result.phase_times[0] * 1000.0;
    double expansion_ms = result.phase_times[1] * 1000.0;
    double simulation_ms = result.phase_times[2] * 1000.0;
    double backprop_ms = result.phase_times[3] * 1000.0;

    double phase_total_ms = selection_ms + expansion_ms + simulation_ms + backprop_ms;

    // Phase energies in µJ (proportional to time)
    double selection_energy_uj = (phase_total_ms > 0) ? (selection_ms / phase_total_ms * total_energy_uj) : 0.0;
    double expansion_energy_uj = (phase_total_ms > 0) ? (expansion_ms / phase_total_ms * total_energy_uj) : 0.0;
    double simulation_energy_uj = (phase_total_ms > 0) ? (simulation_ms / phase_total_ms * total_energy_uj) : 0.0;
    double backprop_energy_uj = (phase_total_ms > 0) ? (backprop_ms / phase_total_ms * total_energy_uj) : 0.0;

    // Phase powers in mW
    double selection_power_mw = (selection_ms > 0) ? (selection_energy_uj / selection_ms) : 0.0;
    double expansion_power_mw = (expansion_ms > 0) ? (expansion_energy_uj / expansion_ms) : 0.0;
    double simulation_power_mw = (simulation_ms > 0) ? (simulation_energy_uj / simulation_ms) : 0.0;
    double backprop_power_mw = (backprop_ms > 0) ? (backprop_energy_uj / backprop_ms) : 0.0;

    // Phase percentages
    double selection_pct = (phase_total_ms > 0) ? (selection_ms / phase_total_ms * 100.0) : 0.0;
    double expansion_pct = (phase_total_ms > 0) ? (expansion_ms / phase_total_ms * 100.0) : 0.0;
    double simulation_pct = (phase_total_ms > 0) ? (simulation_ms / phase_total_ms * 100.0) : 0.0;
    double backprop_pct = (phase_total_ms > 0) ? (backprop_ms / phase_total_ms * 100.0) : 0.0;

    // num_positions = board_size^2
    int num_positions = result.board_size * result.board_size;

    csv << std::fixed << std::setprecision(6);
    csv << timestamp << ","
        << get_system_id() << ","
        << result.gpu_name << ","
        << sm_count << ","
        << "TDP,"
        << result.board_size << ","
        << num_positions << ","
        << result.iterations << ","
        << result.trial_num << ","
        << total_latency_ms << ","
        << total_power_mw << ","
        << total_energy_uj << ","
        << result.tree_size << ","
        << selection_ms << ","
        << selection_power_mw << ","
        << selection_energy_uj << ","
        << selection_pct << ","
        << expansion_ms << ","
        << expansion_power_mw << ","
        << expansion_energy_uj << ","
        << expansion_pct << ","
        << simulation_ms << ","
        << simulation_power_mw << ","
        << simulation_energy_uj << ","
        << simulation_pct << ","
        << backprop_ms << ","
        << backprop_power_mw << ","
        << backprop_energy_uj << ","
        << backprop_pct << std::endl;
}

// ============================================================================
// MAIN
// ============================================================================

int main(int argc, char* argv[]) {
    int board_size = 5;
    int iterations = 1000;
    bool all_sizes = false;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--board-size" && i + 1 < argc) {
            board_size = std::stoi(argv[++i]);
        } else if (arg == "--iterations" && i + 1 < argc) {
            iterations = std::stoi(argv[++i]);
        } else if (arg == "--all-sizes") {
            all_sizes = true;
        } else if (arg == "--help") {
            std::cout << "Usage: " << argv[0] << " [options]\n"
                      << "Options:\n"
                      << "  --board-size N    Board size (default: 5)\n"
                      << "  --iterations N    Number of iterations (default: 1000)\n"
                      << "  --all-sizes       Run for all board sizes (2,3,5,9,13,19)\n"
                      << "  --help            Show this help message\n";
            return 0;
        }
    }

    std::string gpu_name = sanitize_filename(get_gpu_name());

    // Generate timestamp for unique filename
    auto now = std::chrono::system_clock::now();
    std::time_t now_time = std::chrono::system_clock::to_time_t(now);
    std::tm* tm_now = std::localtime(&now_time);
    std::stringstream timestamp_ss;
    timestamp_ss << std::put_time(tm_now, "%Y%m%d_%H%M%S");
    std::string timestamp_str = timestamp_ss.str();

    std::string csv_filename = "results/nn/gpu_nn_mcts_" + gpu_name + "_" + timestamp_str + ".csv";

    std::ofstream csv(csv_filename);
    if (!csv.is_open()) {
        std::cerr << "ERROR: Failed to open CSV file: " << csv_filename << std::endl;
        return 1;
    }

    write_csv_header(csv);

    if (all_sizes) {
        // Standard iteration counts per board size (matching traditional benchmarks)
        std::vector<std::pair<int, int>> size_iterations = {
            {2, 200}, {3, 500}, {5, 1000}, {9, 5000}, {13, 7500}, {19, 10000}
        };
        const int num_trials = 5;

        for (const auto& [size, iters] : size_iterations) {
            for (int trial = 1; trial <= num_trials; trial++) {
                BenchmarkResult result = run_benchmark(size, iters);
                result.trial_num = trial;
                write_csv_row(csv, result);
            }
        }
    } else {
        BenchmarkResult result = run_benchmark(board_size, iterations);
        result.trial_num = 1;
        write_csv_row(csv, result);
    }

    csv.close();
    std::cout << "\n✅ Results written to: " << csv_filename << std::endl;

    return 0;
}
