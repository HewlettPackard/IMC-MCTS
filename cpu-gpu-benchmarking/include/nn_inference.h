// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

#ifndef NN_INFERENCE_H
#define NN_INFERENCE_H

#include <iostream>
#include <fstream>
#include <cstdint>
#include <cmath>
#include <map>
#include <string>
#include <vector>
#include <algorithm>
#include <stdexcept>

// Architecture specifications for each board size
struct NetworkArchitecture {
    int input_size;
    int hidden_size;
    int output_size;
};

// Architecture mapping for different board sizes
static const std::map<int, NetworkArchitecture> ARCH_MAP = {
    {2, {8, 16, 3}},      // 2×2: 8→16→3
    {3, {18, 24, 3}},     // 3×3: 18→24→3
    {5, {50, 32, 3}},     // 5×5: 50→32→3
    {9, {162, 96, 3}},    // 9×9: 162→96→3
    {13, {338, 128, 3}},  // 13×13: 338→128→3
    {19, {722, 192, 3}}   // 19×19: 722→192→3
};

class MCTSNeuralNetwork {
private:
    int board_size;
    NetworkArchitecture arch;
    std::vector<float> weights1;  // Input → Hidden (row-major)
    std::vector<float> weights2;  // Hidden → Output (row-major)

    // Load binary weight file
    void load_weights(const std::string& filepath, std::vector<float>& weights, int& rows, int& cols) {
        std::ifstream file(filepath, std::ios::binary);
        if (!file.is_open()) {
            throw std::runtime_error("Failed to open weight file: " + filepath);
        }

        // Read dimensions (2 × 4 bytes = 8 bytes header)
        int32_t file_rows, file_cols;
        file.read(reinterpret_cast<char*>(&file_rows), sizeof(int32_t));
        file.read(reinterpret_cast<char*>(&file_cols), sizeof(int32_t));
        rows = file_rows;
        cols = file_cols;

        // Read weight data
        weights.resize(rows * cols);
        file.read(reinterpret_cast<char*>(weights.data()), rows * cols * sizeof(float));

        file.close();
    }

    // Matrix-vector multiplication: y = W^T * x
    std::vector<float> matvec(const std::vector<float>& W, int rows, int cols, const std::vector<float>& x) {
        std::vector<float> y(cols, 0.0f);
        for (int j = 0; j < cols; j++) {
            for (int i = 0; i < rows; i++) {
                y[j] += W[i * cols + j] * x[i];
            }
        }
        return y;
    }

    // ReLU activation function
    void relu_inplace(std::vector<float>& x) {
        for (float& val : x) {
            val = std::max(0.0f, val);
        }
    }

    // Softmax activation function
    void softmax_inplace(std::vector<float>& x) {
        float max_val = *std::max_element(x.begin(), x.end());
        float sum = 0.0f;
        for (float& val : x) {
            val = std::exp(val - max_val);
            sum += val;
        }
        for (float& val : x) {
            val /= sum;
        }
    }

public:
    // Constructor: auto-detect architecture and load weights
    MCTSNeuralNetwork(int size) : board_size(size) {
        // Get architecture for this board size
        auto it = ARCH_MAP.find(board_size);
        if (it == ARCH_MAP.end()) {
            throw std::runtime_error("Unsupported board size: " + std::to_string(board_size));
        }
        arch = it->second;

        // Construct weight file paths
        std::string weights_dir = "weights/" + std::to_string(board_size) + "x" + std::to_string(board_size) + "/";
        std::string weights1_path = weights_dir + "weights1.bin";
        std::string weights2_path = weights_dir + "weights2.bin";

        // Load weights
        int w1_rows, w1_cols, w2_rows, w2_cols;
        load_weights(weights1_path, weights1, w1_rows, w1_cols);
        load_weights(weights2_path, weights2, w2_rows, w2_cols);

        // Validate dimensions
        if (w1_rows != arch.input_size || w1_cols != arch.hidden_size) {
            throw std::runtime_error("weights1 dimension mismatch: expected " +
                std::to_string(arch.input_size) + "×" + std::to_string(arch.hidden_size) +
                ", got " + std::to_string(w1_rows) + "×" + std::to_string(w1_cols));
        }
        if (w2_rows != arch.hidden_size || w2_cols != arch.output_size) {
            throw std::runtime_error("weights2 dimension mismatch: expected " +
                std::to_string(arch.hidden_size) + "×" + std::to_string(arch.output_size) +
                ", got " + std::to_string(w2_rows) + "×" + std::to_string(w2_cols));
        }

        std::cout << "Loaded " << board_size << "×" << board_size << " network: "
                  << arch.input_size << "→" << arch.hidden_size << "→" << arch.output_size << std::endl;
    }

    // Encode board state to 2-channel representation
    // board: 0=empty, 1=black, 2=white
    // current_player: 1=black, 2=white
    std::vector<float> encode_board(const std::vector<int>& board, int current_player) {
        int n = board_size * board_size;
        std::vector<float> encoded(2 * n);

        // 2-bit encoding: black channel + white channel
        for (int i = 0; i < n; i++) {
            if (current_player == 1) {
                // Black's perspective
                encoded[i] = (board[i] == 1) ? 1.0f : 0.0f;         // Black stones
                encoded[i + n] = (board[i] == 2) ? 1.0f : 0.0f;     // White stones
            } else {
                // White's perspective (swap channels)
                encoded[i] = (board[i] == 2) ? 1.0f : 0.0f;         // White stones
                encoded[i + n] = (board[i] == 1) ? 1.0f : 0.0f;     // Black stones
            }
        }

        return encoded;
    }

    // Forward pass: Input → Hidden (ReLU) → Output (Softmax)
    std::vector<float> forward(const std::vector<float>& input) {
        // Layer 1: Input → Hidden with ReLU
        std::vector<float> hidden = matvec(weights1, arch.input_size, arch.hidden_size, input);
        relu_inplace(hidden);

        // Layer 2: Hidden → Output with Softmax
        std::vector<float> output = matvec(weights2, arch.hidden_size, arch.output_size, hidden);
        softmax_inplace(output);

        return output;
    }

    // Evaluate position for MCTS rollout
    // Returns: value from current player's perspective [-1, 1]
    //   +1 = current player wins
    //    0 = draw
    //   -1 = current player loses
    double evaluate(const std::vector<int>& board, int current_player) {
        std::vector<float> encoded = encode_board(board, current_player);
        std::vector<float> probs = forward(encoded);

        // probs = [P(white wins), P(draw), P(black wins)]
        // Return expected value from current player's perspective
        if (current_player == 1) {
            // Black's perspective: black wins (+1), draw (0), white wins (-1)
            return probs[2] * 1.0 + probs[1] * 0.0 + probs[0] * (-1.0);
        } else {
            // White's perspective: white wins (+1), draw (0), black wins (-1)
            return probs[0] * 1.0 + probs[1] * 0.0 + probs[2] * (-1.0);
        }
    }

    // Get win probability for current player (for debugging/analysis)
    double get_win_probability(const std::vector<int>& board, int current_player) {
        std::vector<float> encoded = encode_board(board, current_player);
        std::vector<float> probs = forward(encoded);

        if (current_player == 1) {
            return probs[2];  // P(black wins)
        } else {
            return probs[0];  // P(white wins)
        }
    }
};

#endif // NN_INFERENCE_H
