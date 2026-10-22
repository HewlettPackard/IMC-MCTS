// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

/**
 * MCTS CPU Benchmark - Python-Compatible C++ Implementation
 * ==========================================================
 *
 * Optimized single-threaded Monte Carlo Tree Search benchmark for CPU evaluation.
 * Output format matches Python implementation for consistency with analysis tools.
 *
 * Features:
 * - Per-phase timing (Selection, Expansion, Simulation, Backpropagation)
 * - Intel RAPL energy monitoring (with TDP fallback)
 * - 29-column CSV output matching Python format exactly
 * - System information detection (anonymized system ID, CPU model, core count)
 *
 * Compilation:
 *   g++ -std=c++17 -O3 -march=native -ffast-math -o mcts_cpu_benchmark mcts_cpu_benchmark.cpp
 *
 * Usage:
 *   ./mcts_cpu_benchmark --board-size 5 --iterations 1000
 *   ./mcts_cpu_benchmark --all-sizes
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
                // Trim leading whitespace
                name.erase(0, name.find_first_not_of(" \t"));
                return name;
            }
        }
    }
    return "Unknown CPU";
}

int get_cpu_count() {
    // Count physical cores from /proc/cpuinfo
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

    // Fallback to hardware concurrency if parsing failed
    if (physical_cores == 0) {
        physical_cores = std::thread::hardware_concurrency();
        if (physical_cores > 0) {
            physical_cores = physical_cores / 2;  // Assume hyperthreading
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
    // Remove trailing underscores
    while (!result.empty() && result.back() == '_') {
        result.pop_back();
    }
    return result;
}

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
    int current_player;  // 1 or 2
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

    double evaluate() const {
        int count1 = 0, count2 = 0;
        for (int i = 0; i < board_size; i++) {
            for (int j = 0; j < board_size; j++) {
                if (board[i][j] == 1) count1++;
                else if (board[i][j] == 2) count2++;
            }
        }
        if (count1 > count2) return 1.0;
        if (count2 > count1) return 0.0;
        return 0.5;
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
// MCTS NODE AND ENGINE
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
            delete pair.first;  // Delete Move
            delete pair.second; // Delete MCTSNode
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

    // Phase timing accumulators (in seconds)
    double phase_times[4];  // selection, expansion, simulation, backpropagation

public:
    MCTSEngine(double c = std::sqrt(2.0)) : exploration_constant(c), root(nullptr) {
        std::random_device rd;
        rng.seed(rd());
        reset_phase_times();
    }

    ~MCTSEngine() {
        if (root) delete root;
    }

    void reset_phase_times() {
        for (int i = 0; i < 4; i++) {
            phase_times[i] = 0.0;
        }
    }

    void get_phase_times(double times[4]) const {
        for (int i = 0; i < 4; i++) {
            times[i] = phase_times[i];
        }
    }

    // Phase 1: Selection
    MCTSNode* selection(MCTSNode* node) {
        while (!node->is_terminal() && node->is_fully_expanded()) {
            MCTSNode* best = nullptr;
            double best_ucb = -INFINITY;
            for (auto& pair : node->children) {
                double ucb = pair.second->ucb1(exploration_constant);
                if (ucb > best_ucb) {
                    best_ucb = ucb;
                    best = pair.second;
                }
            }
            node = best;
        }
        return node;
    }

    // Phase 2: Expansion
    MCTSNode* expansion(MCTSNode* node) {
        if (!node->untried_moves.empty()) {
            std::uniform_int_distribution<int> dist(0, node->untried_moves.size() - 1);
            int idx = dist(rng);
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

    // Phase 3: Simulation (Rollout)
    double simulation(const GameState& initial_state) {
        GameState state = initial_state;
        std::uniform_int_distribution<int> dist(0, 1000000);

        while (!state.is_terminal()) {
            auto moves = state.get_legal_moves();
            if (moves.empty()) break;
            int idx = dist(rng) % moves.size();
            state.apply_move(moves[idx]);
        }

        return state.evaluate();
    }

    // Phase 4: Backpropagation
    void backpropagation(MCTSNode* node, double result) {
        while (node != nullptr) {
            node->visits++;
            node->wins += result;
            result = 1.0 - result;  // Flip result for alternating players
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

        // PHASE 3: SIMULATION
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

        MCTSNode* best = nullptr;
        int best_visits = -1;
        for (auto& pair : root->children) {
            if (pair.second->visits > best_visits) {
                best_visits = pair.second->visits;
                best = pair.second;
            }
        }

        for (auto& pair : root->children) {
            if (pair.second == best) {
                return *(pair.first);
            }
        }

        return Move(-1, -1);
    }
};

// ============================================================================
// ENERGY MONITORING
// ============================================================================

// CPU usage tracking structure
struct CPUStats {
    long long user, nice, system, idle, iowait, irq, softirq, steal;

    long long total() const {
        return user + nice + system + idle + iowait + irq + softirq + steal;
    }

    long long active() const {
        return user + nice + system + irq + softirq + steal;
    }
};

class EnergyMonitor {
private:
    bool rapl_available;
    long long start_energy_uj;
    double tdp_watts;
    double idle_watts;  // Idle power consumption
    std::chrono::high_resolution_clock::time_point start_time;
    std::string energy_file;
    CPUStats start_cpu_stats;

    bool check_rapl_available() {
        energy_file = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj";
        std::ifstream file(energy_file);
        return file.good();
    }

    long long read_energy_uj() {
        std::ifstream file(energy_file);
        long long energy;
        if (file >> energy) {
            return energy;
        }
        return 0;
    }

    CPUStats read_cpu_stats() {
        CPUStats stats = {0, 0, 0, 0, 0, 0, 0, 0};
        std::ifstream file("/proc/stat");
        std::string line;

        if (std::getline(file, line)) {
            // Parse: cpu  user nice system idle iowait irq softirq steal
            std::istringstream iss(line);
            std::string cpu_label;
            iss >> cpu_label >> stats.user >> stats.nice >> stats.system
                >> stats.idle >> stats.iowait >> stats.irq >> stats.softirq >> stats.steal;
        }

        return stats;
    }

    double get_cpu_percent() {
        CPUStats end_stats = read_cpu_stats();

        long long total_delta = end_stats.total() - start_cpu_stats.total();
        long long active_delta = end_stats.active() - start_cpu_stats.active();

        if (total_delta == 0) {
            return 0.0;  // Avoid division by zero
        }

        return 100.0 * active_delta / total_delta;
    }

public:
    EnergyMonitor(double tdp = 55.3, double idle = 20.0) : tdp_watts(tdp), idle_watts(idle) {
        rapl_available = check_rapl_available();
        if (rapl_available) {
            std::cout << "✓ Using Intel RAPL for accurate energy measurement" << std::endl;
        } else {
            std::cout << "⚠ RAPL not available, using psutil-style estimation (TDP="
                      << tdp << "W, Idle=" << idle << "W)" << std::endl;
        }
    }

    void start() {
        start_time = std::chrono::high_resolution_clock::now();
        if (rapl_available) {
            start_energy_uj = read_energy_uj();
        } else {
            start_cpu_stats = read_cpu_stats();
        }
    }

    double get_energy_joules(double actual_duration_s = -1) {
        if (rapl_available) {
            long long end_energy_uj = read_energy_uj();
            long long delta_uj = end_energy_uj - start_energy_uj;

            // Handle counter wraparound (happens at ~2^32 microjoules ≈ 4.3kJ)
            if (delta_uj < 0) {
                delta_uj += (1LL << 32);
            }

            return delta_uj / 1e6;  // Convert to joules
        } else {
            // psutil-style estimation: Power = Idle + (TDP - Idle) × CPU%
            // Use actual benchmark duration if provided, otherwise measure internally
            double duration_s;
            if (actual_duration_s > 0) {
                duration_s = actual_duration_s;
            } else {
                auto end_time = std::chrono::high_resolution_clock::now();
                duration_s = std::chrono::duration<double>(end_time - start_time).count();
            }

            // For very short workloads (< 2ms), CPU% measurement is unreliable
            // Use a fixed power estimate based on stable measurements from longer workloads (5×5+)
            double avg_power;
            if (duration_s < 0.002) {
                // Use fixed 65W based on stable measurements from longer workloads
                avg_power = 65.0;
            } else {
                double cpu_percent = get_cpu_percent() / 100.0;  // Convert to 0-1 range
                avg_power = idle_watts + (tdp_watts - idle_watts) * cpu_percent;
            }
            return avg_power * duration_s;
        }
    }

    std::string get_method() const {
        return rapl_available ? "RAPL" : "psutil";
    }
};

// ============================================================================
// BENCHMARK RESULT STRUCTURE
// ============================================================================

struct BenchmarkResult {
    // System info
    std::string timestamp;
    std::string system_id;
    std::string processor;
    int cpu_count;
    std::string power_method;

    // Trial info
    int board_size;
    int num_positions;
    int iterations;
    int trial_num;

    // Total metrics
    double total_latency_ms;
    double total_power_mw;
    double total_energy_uj;
    int tree_size;

    // Phase metrics (4 phases × 4 metrics each)
    struct PhaseMetrics {
        double latency_ms;
        double power_mw;
        double energy_uj;
        double percent;
    };
    PhaseMetrics phases[4];  // selection, expansion, simulation, backpropagation
};

// ============================================================================
// BENCHMARK CLASS
// ============================================================================

class Benchmark {
private:
    double cpu_tdp;
    double cpu_idle;
    std::string system_id;
    std::string processor;
    int cpu_count;

public:
    Benchmark(double tdp = 55.3, double idle = 20.0) : cpu_tdp(tdp), cpu_idle(idle) {
        system_id = get_system_id();
        processor = get_processor_name();
        cpu_count = get_cpu_count();

        std::cout << "System Information:" << std::endl;
        std::cout << "  System ID: " << system_id << std::endl;
        std::cout << "  Processor: " << processor << std::endl;
        std::cout << "  Physical Cores: " << cpu_count << std::endl;
        std::cout << std::endl;
    }

    BenchmarkResult run_trial(int board_size, int iterations, int trial_num) {
        GameState initial_state(board_size);
        MCTSEngine engine(std::sqrt(2.0));
        EnergyMonitor monitor(cpu_tdp, cpu_idle);

        // Run MCTS search
        monitor.start();
        auto start = std::chrono::high_resolution_clock::now();

        engine.search(initial_state, iterations);

        auto end = std::chrono::high_resolution_clock::now();
        double elapsed_s = std::chrono::duration<double>(end - start).count();
        double total_energy_j = monitor.get_energy_joules(elapsed_s);

        // Get timing measurements
        double phase_times_s[4];
        engine.get_phase_times(phase_times_s);

        // Build result structure
        BenchmarkResult result;

        // System info
        auto now = std::chrono::system_clock::now();
        auto time_t = std::chrono::system_clock::to_time_t(now);
        std::ostringstream oss;
        oss << std::put_time(std::localtime(&time_t), "%Y-%m-%d %H:%M:%S");
        result.timestamp = oss.str();
        result.system_id = system_id;
        result.processor = processor;
        result.cpu_count = cpu_count;
        result.power_method = monitor.get_method();

        // Trial info
        result.board_size = board_size;
        result.num_positions = board_size * board_size;
        result.iterations = iterations;
        result.trial_num = trial_num;

        // Total metrics
        result.total_latency_ms = elapsed_s * 1000.0;
        result.total_power_mw = (total_energy_j / elapsed_s) * 1000.0;
        result.total_energy_uj = total_energy_j * 1e6;
        result.tree_size = engine.get_tree_size();

        // Phase metrics
        for (int i = 0; i < 4; i++) {
            double phase_ms = phase_times_s[i] * 1000.0;
            double phase_percent = (phase_times_s[i] / elapsed_s) * 100.0;
            double phase_power = result.total_power_mw * (phase_percent / 100.0);
            double phase_energy = result.total_energy_uj * (phase_percent / 100.0);

            result.phases[i].latency_ms = phase_ms;
            result.phases[i].power_mw = phase_power;
            result.phases[i].energy_uj = phase_energy;
            result.phases[i].percent = phase_percent;
        }

        // Print trial summary
        std::cout << "  Trial " << trial_num << "/" << std::flush;
        std::cout << " " << static_cast<int>(iterations / (elapsed_s / 1000.0)) << " iter/s, ";
        std::cout << std::fixed << std::setprecision(3) << elapsed_s * 1000.0 << " ms, ";
        std::cout << std::fixed << std::setprecision(2) << result.total_energy_uj / 1000.0 << " mJ" << std::endl;

        return result;
    }

    void save_results_csv(const std::vector<BenchmarkResult>& results, const std::string& filename) {
        std::ofstream file(filename);

        // Write header (29 columns)
        file << "timestamp,system_id,processor,cpu_count,power_method,"
             << "board_size,num_positions,iterations,trial_num,"
             << "total_latency_ms,total_power_mw,total_energy_uj,tree_size,"
             << "selection_latency_ms,selection_power_mw,selection_energy_uj,selection_percent,"
             << "expansion_latency_ms,expansion_power_mw,expansion_energy_uj,expansion_percent,"
             << "simulation_latency_ms,simulation_power_mw,simulation_energy_uj,simulation_percent,"
             << "backpropagation_latency_ms,backpropagation_power_mw,backpropagation_energy_uj,backpropagation_percent\n";

        // Write data rows
        for (const auto& r : results) {
            file << r.timestamp << ","
                 << r.system_id << ","
                 << r.processor << ","
                 << r.cpu_count << ","
                 << r.power_method << ","
                 << r.board_size << ","
                 << r.num_positions << ","
                 << r.iterations << ","
                 << r.trial_num << ","
                 << std::fixed << std::setprecision(6) << r.total_latency_ms << ","
                 << std::fixed << std::setprecision(6) << r.total_power_mw << ","
                 << std::fixed << std::setprecision(6) << r.total_energy_uj << ","
                 << r.tree_size;

            for (int i = 0; i < 4; i++) {
                file << "," << std::fixed << std::setprecision(6) << r.phases[i].latency_ms
                     << "," << std::fixed << std::setprecision(6) << r.phases[i].power_mw
                     << "," << std::fixed << std::setprecision(6) << r.phases[i].energy_uj
                     << "," << std::fixed << std::setprecision(6) << r.phases[i].percent;
            }
            file << "\n";
        }

        std::cout << "\n✓ Results saved to: " << filename << std::endl;
    }

    void print_summary(const std::vector<BenchmarkResult>& results) {
        std::cout << "\n=== BENCHMARK SUMMARY ===" << std::endl;
        std::cout << std::setw(10) << "Board"
                  << std::setw(15) << "Throughput"
                  << std::setw(15) << "Latency"
                  << std::setw(15) << "Energy/Iter"
                  << std::setw(12) << "Power" << std::endl;
        std::cout << std::setw(10) << "Size"
                  << std::setw(15) << "(iter/s)"
                  << std::setw(15) << "(ms/iter)"
                  << std::setw(15) << "(µJ)"
                  << std::setw(12) << "(W)" << std::endl;
        std::cout << std::string(62, '-') << std::endl;

        // Group by board size
        std::map<int, std::vector<const BenchmarkResult*>> by_size;
        for (const auto& r : results) {
            by_size[r.board_size].push_back(&r);
        }

        for (const auto& pair : by_size) {
            int size = pair.first;
            const auto& trials = pair.second;

            double avg_throughput = 0, avg_latency = 0, avg_energy = 0, avg_power = 0;
            for (const auto* r : trials) {
                avg_throughput += (r->iterations * 1000.0) / r->total_latency_ms;
                avg_latency += r->total_latency_ms / r->iterations;
                avg_energy += r->total_energy_uj / r->iterations;
                avg_power += r->total_power_mw / 1000.0;
            }
            avg_throughput /= trials.size();
            avg_latency /= trials.size();
            avg_energy /= trials.size();
            avg_power /= trials.size();

            std::cout << std::setw(7) << size << "×" << std::setw(2) << std::left << size << std::right
                      << std::setw(15) << static_cast<int>(avg_throughput)
                      << std::setw(15) << std::fixed << std::setprecision(6) << avg_latency
                      << std::setw(15) << std::fixed << std::setprecision(2) << avg_energy
                      << std::setw(12) << std::fixed << std::setprecision(1) << avg_power << std::endl;
        }
    }
};

// ============================================================================
// MAIN FUNCTION
// ============================================================================

int main(int argc, char** argv) {
    // Default parameters
    int board_size = -1;
    int iterations = 1000;
    int trials = 5;
    int warmup_trials = 0;
    double tdp = 55.3;
    double idle_power = 20.0;
    bool all_sizes = false;

    // Parse command-line arguments
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--board-size" && i + 1 < argc) {
            board_size = std::stoi(argv[++i]);
        } else if (arg == "--iterations" && i + 1 < argc) {
            iterations = std::stoi(argv[++i]);
        } else if (arg == "--trials" && i + 1 < argc) {
            trials = std::stoi(argv[++i]);
        } else if (arg == "--warmup" && i + 1 < argc) {
            warmup_trials = std::stoi(argv[++i]);
        } else if (arg == "--tdp" && i + 1 < argc) {
            tdp = std::stod(argv[++i]);
        } else if (arg == "--idle" && i + 1 < argc) {
            idle_power = std::stod(argv[++i]);
        } else if (arg == "--all-sizes") {
            all_sizes = true;
        } else if (arg == "--help") {
            std::cout << "MCTS CPU Benchmark - C++ Implementation\n"
                      << "=======================================\n\n"
                      << "Usage:\n"
                      << "  " << argv[0] << " [options]\n\n"
                      << "Options:\n"
                      << "  --board-size N     Run single board size N×N (2-19)\n"
                      << "  --iterations N     Number of MCTS iterations (default: 1000)\n"
                      << "                     Ignored when --all-sizes is used (auto per size)\n"
                      << "  --trials N         Number of trials per size (default: 5)\n"
                      << "  --warmup N         Number of warmup trials before measurement (default: 0)\n"
                      << "  --all-sizes        Run all board sizes with standard iteration counts:\n"
                      << "                       2×2:200, 3×3:500, 5×5:1K, 9×9:5K, 13×13:7.5K, 19×19:10K\n"
                      << "  --tdp W            CPU TDP in watts (default: 55.3)\n"
                      << "  --idle W           CPU idle power in watts (default: 20.0)\n"
                      << "                     Used for psutil-style estimation when RAPL unavailable\n"
                      << "  --help             Show this help message\n\n"
                      << "Power Measurement:\n"
                      << "  - RAPL (Intel): Hardware counters (accurate)\n"
                      << "  - psutil (fallback): Power = Idle + (TDP - Idle) × CPU%\n\n"
                      << "Examples:\n"
                      << "  " << argv[0] << " --board-size 5 --iterations 1000\n"
                      << "  " << argv[0] << " --all-sizes\n"
                      << "  " << argv[0] << " --all-sizes --trials 3\n"
                      << "  " << argv[0] << " --all-sizes --tdp 100 --idle 25\n";
            return 0;
        }
    }

    // Helper function: Get standard iteration count for a board size
    auto get_iterations_for_board = [](int size) -> int {
        switch (size) {
            case 2:  return 200;
            case 3:  return 500;
            case 5:  return 1000;
            case 9:  return 5000;
            case 13: return 7500;
            case 19: return 10000;
            default: return 1000;  // fallback
        }
    };

    // Determine board sizes to test
    std::vector<int> board_sizes;
    if (all_sizes) {
        board_sizes = {2, 3, 5, 9, 13, 19};
    } else if (board_size > 0) {
        board_sizes = {board_size};
    } else {
        std::cerr << "Error: Must specify --board-size or --all-sizes\n";
        std::cerr << "Run with --help for usage information\n";
        return 1;
    }

    // Print configuration
    std::cout << "MCTS CPU Benchmark (C++)\n";
    std::cout << "========================\n";
    std::cout << "Board sizes: ";
    for (int size : board_sizes) {
        std::cout << size << "×" << size << " ";
    }
    std::cout << "\n";
    if (all_sizes) {
        std::cout << "Iterations: (auto per board size)\n";
    } else {
        std::cout << "Iterations: " << iterations << "\n";
    }
    std::cout << "Trials: " << trials << "\n";
    if (warmup_trials > 0) {
        std::cout << "Warmup trials: " << warmup_trials << "\n";
    }
    std::cout << "CPU TDP: " << tdp << "W\n";
    std::cout << "CPU Idle: " << idle_power << "W\n\n";

    // Initialize benchmark
    Benchmark benchmark(tdp, idle_power);
    std::vector<BenchmarkResult> all_results;

    // Run benchmarks
    for (int size : board_sizes) {
        // Use standard iterations for --all-sizes, otherwise use user-specified value
        int size_iterations = all_sizes ? get_iterations_for_board(size) : iterations;

        std::cout << "--- Testing " << size << "×" << size << " board ("
                  << size_iterations << " iterations) ---" << std::endl;

        // Run warmup trials (not recorded)
        if (warmup_trials > 0) {
            std::cout << "  Running " << warmup_trials << " warmup trials..." << std::endl;
            for (int warmup = 1; warmup <= warmup_trials; warmup++) {
                benchmark.run_trial(size, size_iterations, warmup);
            }
        }

        // Run actual measured trials
        for (int trial = 1; trial <= trials; trial++) {
            BenchmarkResult result = benchmark.run_trial(size, size_iterations, trial);
            all_results.push_back(result);
        }
        std::cout << std::endl;
    }

    // Generate filename: mcts_benchmark_cpu_<devicename>_<YYYYMMDD>_<HHMMSS>.csv
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    std::ostringstream filename_oss;
    filename_oss << "results/traditional/mcts_benchmark_cpu_"
                 << sanitize_filename(get_processor_name()) << "_"
                 << std::put_time(std::localtime(&time_t), "%Y%m%d_%H%M%S")
                 << ".csv";
    std::string filename = filename_oss.str();

    // Save results and print summary
    benchmark.save_results_csv(all_results, filename);
    benchmark.print_summary(all_results);

    return 0;
}
