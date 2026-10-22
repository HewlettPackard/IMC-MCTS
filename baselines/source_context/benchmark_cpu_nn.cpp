// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

/**
 * MCTS CPU Neural Network Benchmark
 * ==================================
 *
 * CPU-based Monte Carlo Tree Search with Neural Network rollout evaluation.
 * This benchmark uses the same architecture as the traditional random-rollout
 * CPU baseline, but replaces random simulation with NN-based position evaluation.
 *
 * Key differences from traditional MCTS:
 * - Selection: UCB1 tree policy (unchanged)
 * - Expansion: Add single child node (unchanged)
 * - Rollout: Neural network evaluation (CHANGED from random simulation)
 * - Backpropagation: Update statistics along path (unchanged)
 *
 * Features:
 * - Per-phase timing (Selection, Expansion, Rollout, Backpropagation)
 * - Intel RAPL energy monitoring (with TDP fallback)
 * - 29-column CSV output matching Python format
 * - Automatic weight loading for board sizes 2×2 to 19×19
 *
 * Compilation:
 *   g++ -std=c++17 -O3 -march=native -I/usr/include/eigen3 -o benchmark_cpu_nn benchmark_cpu_nn.cpp
 *
 * Usage:
 *   ./benchmark_cpu_nn --board-size 5 --iterations 1000
 *   ./benchmark_cpu_nn --all-sizes
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
#include "nn_inference.h"

// ============================================================================
// SYSTEM INFORMATION UTILITIES
// ============================================================================

std::string get_system_id() {
    return "local_system";
}

std::string get_processor_name() {
    std::ifstream cpuinfo("/proc/cpuinfo");
    std::string line;
    while (std::getline(cpuinfo, line)) {
        if (line.find("model name") != std::string::npos) {
            size_t colon = line.find(':');
            if (colon != std::string::npos) {
                std::string name = line.substr(colon + 1);
                name.erase(0, name.find_first_not_of(" \t"));
                return name;
            }
        }
    }
    return "Unknown CPU";
}

int get_cpu_count() {
    std::ifstream cpuinfo("/proc/cpuinfo");
    std::string line;
    int physical_cores = 0;
    int last_physical_id = -1;

    while (std::getline(cpuinfo, line)) {
        if (line.find("physical id") != std::string::npos) {
            size_t colon = line.find(':');
            if (colon != std::string::npos) {
                int id = std::stoi(line.substr(colon + 1));
                if (id != last_physical_id) {
                    physical_cores++;
                    last_physical_id = id;
                }
            }
        }
    }

    if (physical_cores == 0) {
        physical_cores = std::thread::hardware_concurrency();
        if (physical_cores > 0) {
            physical_cores = physical_cores / 2;
        }
    }

    return physical_cores > 0 ? physical_cores : 1;
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
// ENERGY MONITORING (Intel RAPL)
// ============================================================================

class EnergyMonitor {
private:
    std::vector<std::string> rapl_files;
    std::vector<double> max_energy_uj;
    double tdp_watts;
    bool rapl_available;

    void detect_rapl() {
        std::string base_path = "/sys/class/powercap/intel-rapl/intel-rapl:0/";
        std::string energy_file = base_path + "energy_uj";
        std::string max_energy_file = base_path + "max_energy_range_uj";

        if (std::ifstream(energy_file).good()) {
            rapl_files.push_back(energy_file);
            std::ifstream max_file(max_energy_file);
            if (max_file.good()) {
                double max_uj;
                max_file >> max_uj;
                max_energy_uj.push_back(max_uj);
            } else {
                max_energy_uj.push_back(0);
            }
            rapl_available = true;
        } else {
            rapl_available = false;
        }
    }

    double estimate_tdp() {
        std::string cpu_name = get_processor_name();
        if (cpu_name.find("5945WX") != std::string::npos) return 280.0;
        if (cpu_name.find("8462Y+") != std::string::npos) return 300.0;
        return 100.0;
    }

public:
    EnergyMonitor() : tdp_watts(0), rapl_available(false) {
        detect_rapl();
        if (!rapl_available) {
            tdp_watts = estimate_tdp();
        }
    }

    double read_energy_joules() {
        if (rapl_available && !rapl_files.empty()) {
            std::ifstream file(rapl_files[0]);
            if (file.good()) {
                double uj;
                file >> uj;
                return uj / 1e6;
            }
        }
        return 0.0;
    }

    bool is_rapl_available() const { return rapl_available; }
    double get_tdp() const { return tdp_watts; }
};

// ============================================================================
// GAME STATE REPRESENTATION
// ============================================================================

struct Move {
    int row;
    int col;

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

    // Convert board to flat vector for NN encoding
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
    size_t operator()(const GameState& state) const {
        return state.hash();
    }
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
// MCTS NODE AND ENGINE WITH NEURAL NETWORK EVALUATION
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

    bool is_fully_expanded() const {
        return untried_moves.empty();
    }

    bool is_terminal() const {
        return state.is_terminal();
    }

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
    MCTSNeuralNetwork* neural_net;

public:
    MCTSEngine(int board_size, double exploration = 1.414, unsigned seed = 42)
        : rng(seed), exploration_constant(exploration), root(nullptr), phase_times(4, 0.0) {
        // Initialize neural network for this board size
        try {
            neural_net = new MCTSNeuralNetwork(board_size);
            std::cout << "Neural network loaded successfully for " << board_size << "×" << board_size << " board" << std::endl;
        } catch (const std::exception& e) {
            std::cerr << "ERROR: Failed to load neural network: " << e.what() << std::endl;
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

    // Phase 1: Selection
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

    // Phase 2: Expansion
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

    // Phase 3: Rollout using Neural Network Evaluation
    double simulation(const GameState& state) {
        // Convert game state to NN input format
        std::vector<int> board_vec = state.to_vector();

        // Evaluate position using neural network
        double nn_value = neural_net->evaluate(board_vec, state.current_player);

        // Convert from [-1, 1] to [0, 1] range for MCTS
        // nn_value: +1 (current player wins) → 1.0
        // nn_value:  0 (draw)                → 0.5
        // nn_value: -1 (current player loses) → 0.0
        return (nn_value + 1.0) / 2.0;
    }

    // Phase 4: Backpropagation
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

        // PHASE 1: SELECTION
        auto t_start = Clock::now();
        MCTSNode* node = selection(root);
        auto t_end = Clock::now();
        phase_times[0] += std::chrono::duration<double>(t_end - t_start).count();

        // PHASE 2: EXPANSION
        t_start = Clock::now();
        if (!node->is_terminal() && node->visits > 0) {
            node = expansion(node);
        }
        t_end = Clock::now();
        phase_times[1] += std::chrono::duration<double>(t_end - t_start).count();

        // PHASE 3: ROLLOUT (Neural Network Evaluation)
        t_start = Clock::now();
        double result = simulation(node->state);
        t_end = Clock::now();
        phase_times[2] += std::chrono::duration<double>(t_end - t_start).count();

        // PHASE 4: BACKPROPAGATION
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

    Move get_best_move() const {
        if (!root || root->children.empty()) {
            return Move(-1, -1);
        }

        MCTSNode* best_child = nullptr;
        int max_visits = -1;
        for (auto& pair : root->children) {
            MCTSNode* child = pair.second;
            if (child->visits > max_visits) {
                max_visits = child->visits;
                best_child = child;
            }
        }

        for (auto& pair : root->children) {
            if (pair.second == best_child) {
                return *pair.first;
            }
        }
        return Move(-1, -1);
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
    bool rapl_available;
    double tdp_watts;
    int trial_num;
};

BenchmarkResult run_benchmark(int board_size, int iterations) {
    std::cout << "\n" << std::string(70, '=') << std::endl;
    std::cout << "MCTS CPU NN Benchmark - " << board_size << "×" << board_size << " Board" << std::endl;
    std::cout << std::string(70, '=') << std::endl;
    std::cout << "Iterations: " << iterations << std::endl;

    EnergyMonitor energy_monitor;
    MCTSEngine engine(board_size);
    GameState initial_state(board_size);

    double energy_start = energy_monitor.read_energy_joules();
    auto time_start = std::chrono::high_resolution_clock::now();

    engine.search(initial_state, iterations);

    auto time_end = std::chrono::high_resolution_clock::now();
    double energy_end = energy_monitor.read_energy_joules();

    double total_time = std::chrono::duration<double>(time_end - time_start).count();
    double energy_consumed = 0.0;

    if (energy_monitor.is_rapl_available()) {
        energy_consumed = energy_end - energy_start;
        if (energy_consumed < 0) {
            energy_consumed += energy_monitor.read_energy_joules();
        }
    } else {
        energy_consumed = energy_monitor.get_tdp() * total_time;
    }

    BenchmarkResult result;
    result.board_size = board_size;
    result.iterations = iterations;
    result.total_time_s = total_time;
    result.iterations_per_sec = iterations / total_time;
    result.energy_j = energy_consumed;
    result.energy_per_iter_uj = (energy_consumed * 1e6) / iterations;
    result.tree_size = engine.get_tree_size();
    result.phase_times = engine.get_phase_times();
    result.rapl_available = energy_monitor.is_rapl_available();
    result.tdp_watts = energy_monitor.get_tdp();

    std::cout << "\nResults:" << std::endl;
    std::cout << "  Total time: " << total_time << " s" << std::endl;
    std::cout << "  Throughput: " << result.iterations_per_sec << " iter/s" << std::endl;
    std::cout << "  Energy: " << energy_consumed << " J" << std::endl;
    std::cout << "  Energy/iter: " << result.energy_per_iter_uj << " µJ" << std::endl;
    std::cout << "  Tree size: " << result.tree_size << " nodes" << std::endl;
    std::cout << "\nPhase timings:" << std::endl;
    std::cout << "  Selection:       " << result.phase_times[0] << " s" << std::endl;
    std::cout << "  Expansion:       " << result.phase_times[1] << " s" << std::endl;
    std::cout << "  Rollout (NN):    " << result.phase_times[2] << " s" << std::endl;
    std::cout << "  Backpropagation: " << result.phase_times[3] << " s" << std::endl;

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

    std::string system_id = get_system_id();
    std::string processor = get_processor_name();
    int core_count = get_cpu_count();

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

    // Phase energies in µJ (proportional to time since power is roughly constant)
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
        << system_id << ","
        << processor << ","
        << core_count << ","
        << (result.rapl_available ? "RAPL" : "TDP") << ","
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

    std::string processor = sanitize_filename(get_processor_name());

    // Generate timestamp for unique filename
    auto now = std::chrono::system_clock::now();
    std::time_t now_time = std::chrono::system_clock::to_time_t(now);
    std::tm* tm_now = std::localtime(&now_time);
    std::stringstream timestamp_ss;
    timestamp_ss << std::put_time(tm_now, "%Y%m%d_%H%M%S");
    std::string timestamp_str = timestamp_ss.str();

    std::string csv_filename = "results/nn/cpu_nn_mcts_" + processor + "_" + timestamp_str + ".csv";

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
                result.trial_num = trial;  // Set trial number
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
