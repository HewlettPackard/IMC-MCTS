# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

# Makefile for MCTS Benchmarks (CPU and GPU, Traditional and Neural Network)
# ==============================================================================

# Compilers
CXX = g++
NVCC = nvcc

# Directories
SRC_DIR = .
INC_DIR = include

# Common flags
CXXFLAGS = -std=c++17 -O3 -march=native -ffast-math -Wall -Wextra -I$(INC_DIR)

# CUDA flags
NVCCFLAGS = -std=c++17 -O3 -arch=sm_80 -I$(INC_DIR)
CUDA_LIBS = -lcublas

# Targets
TARGET_CPU_TRAD = benchmark_cpu_traditional
TARGET_CPU_NN = benchmark_cpu_nn
TARGET_GPU_NN = benchmark_gpu_nn
TARGET_GPU_NN_BATCHED = benchmark_gpu_nn_batched

# Sources
SOURCE_CPU_TRAD = $(SRC_DIR)/benchmark_cpu_traditional.cpp
SOURCE_CPU_NN = $(SRC_DIR)/benchmark_cpu_nn.cpp
SOURCE_GPU_NN = $(SRC_DIR)/benchmark_gpu_nn.cu
SOURCE_GPU_NN_BATCHED = $(SRC_DIR)/benchmark_gpu_nn_batched.cu

# Default target: build all benchmarks
all: $(TARGET_CPU_TRAD) $(TARGET_CPU_NN) $(TARGET_GPU_NN) $(TARGET_GPU_NN_BATCHED)

# Build individual targets
$(TARGET_CPU_TRAD): $(SOURCE_CPU_TRAD)
	$(CXX) $(CXXFLAGS) -o $(TARGET_CPU_TRAD) $(SOURCE_CPU_TRAD)
	@echo "✓ Compiled: ./$(TARGET_CPU_TRAD)"

$(TARGET_CPU_NN): $(SOURCE_CPU_NN) $(INC_DIR)/nn_inference.h
	$(CXX) $(CXXFLAGS) -o $(TARGET_CPU_NN) $(SOURCE_CPU_NN)
	@echo "✓ Compiled: ./$(TARGET_CPU_NN)"

$(TARGET_GPU_NN): $(SOURCE_GPU_NN)
	$(NVCC) $(NVCCFLAGS) $(CUDA_LIBS) -o $(TARGET_GPU_NN) $(SOURCE_GPU_NN)
	@echo "✓ Compiled: ./$(TARGET_GPU_NN)"

$(TARGET_GPU_NN_BATCHED): $(SOURCE_GPU_NN_BATCHED)
	$(NVCC) $(NVCCFLAGS) $(CUDA_LIBS) -o $(TARGET_GPU_NN_BATCHED) $(SOURCE_GPU_NN_BATCHED)
	@echo "✓ Compiled: ./$(TARGET_GPU_NN_BATCHED)"

# Convenience targets for building specific benchmarks
cpu-trad: $(TARGET_CPU_TRAD)
cpu-nn: $(TARGET_CPU_NN)
gpu-nn: $(TARGET_GPU_NN)
gpu-nn-batched: $(TARGET_GPU_NN_BATCHED)

# Clean build artifacts
clean:
	rm -f $(TARGET_CPU_TRAD) $(TARGET_CPU_NN) $(TARGET_GPU_NN) $(TARGET_GPU_NN_BATCHED)
	@echo "✓ Cleaned all build artifacts"

# Test targets
test-cpu-trad: $(TARGET_CPU_TRAD)
	@echo "Testing CPU traditional MCTS (2x2, 1000 iterations)..."
	./$(TARGET_CPU_TRAD) --board-size 2 --iterations 1000

test-cpu-nn: $(TARGET_CPU_NN)
	@echo "Testing CPU NN-MCTS (2x2, 100 iterations)..."
	./$(TARGET_CPU_NN) --board-size 2 --iterations 100

test-gpu-nn: $(TARGET_GPU_NN)
	@echo "Testing GPU NN-MCTS (2x2, 100 iterations)..."
	./$(TARGET_GPU_NN) --board-size 2 --iterations 100

test: test-cpu-trad test-cpu-nn test-gpu-nn

# Benchmark targets (full runs)
benchmark-cpu-trad: $(TARGET_CPU_TRAD)
	@echo "Running CPU traditional benchmark (all sizes)..."
	./$(TARGET_CPU_TRAD) --all-sizes --iterations 5000

benchmark-cpu-nn: $(TARGET_CPU_NN)
	@echo "Running CPU NN benchmark (all sizes)..."
	./$(TARGET_CPU_NN) --all-sizes --iterations 1000

benchmark-gpu-nn: $(TARGET_GPU_NN)
	@echo "Running GPU NN benchmark (all sizes)..."
	./$(TARGET_GPU_NN) --all-sizes --iterations 1000

benchmark: benchmark-cpu-trad benchmark-cpu-nn benchmark-gpu-nn

# Help target
help:
	@echo "MCTS Benchmark Suite - Make targets:"
	@echo ""
	@echo "Build targets:"
	@echo "  make              - Build all benchmarks (default)"
	@echo "  make cpu-trad     - Build CPU traditional (random rollout)"
	@echo "  make cpu-nn       - Build CPU neural network"
	@echo "  make gpu-nn       - Build GPU neural network"
	@echo ""
	@echo "Test targets (quick validation):"
	@echo "  make test         - Test all benchmarks (2x2, few iterations)"
	@echo "  make test-cpu-trad - Test CPU traditional"
	@echo "  make test-cpu-nn  - Test CPU NN"
	@echo "  make test-gpu-nn  - Test GPU NN"
	@echo ""
	@echo "Benchmark targets (full runs):"
	@echo "  make benchmark    - Run all benchmarks (all sizes)"
	@echo "  make benchmark-cpu-trad - CPU traditional (5000 iter)"
	@echo "  make benchmark-cpu-nn   - CPU NN (1000 iter)"
	@echo "  make benchmark-gpu-nn   - GPU NN (1000 iter)"
	@echo ""
	@echo "Utility targets:"
	@echo "  make clean        - Remove all build artifacts"
	@echo "  make help         - Show this help message"

.PHONY: all cpu-trad cpu-nn gpu-nn clean test test-cpu-trad test-cpu-nn test-gpu-nn \
        benchmark benchmark-cpu-trad benchmark-cpu-nn benchmark-gpu-nn help
