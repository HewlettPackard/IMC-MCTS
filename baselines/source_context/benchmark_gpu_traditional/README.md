# GPU MCTS Benchmark

GPU-accelerated MCTS implementation using **mcts_numba_cuda** with simplified Go.

## Implementation Details

### Game: Simplified Go
- **Board sizes**: 2×2 through 19×19
- **Actions**: Board positions (0 to m×n-1) + pass (m×n)
- **Rules**:
  - Place stones on empty intersections
  - Pass moves allowed
  - Game ends after 2 consecutive passes OR board full
  - **No captures** (simplified version)
  - Winner determined by stone count

### MCTS Configuration
- **Parallelization**: Root parallelization (8 independent trees)
- **Playouts per node**: 128 (configurable)
- **Variant**: `acp_prodigal` (best performance)
- **4-Phase Instrumentation**:
  1. Selection (UCT policy)
  2. Expansion (add children)
  3. Simulation (random playouts)
  4. Backpropagation (update statistics)

### Power Monitoring
- Uses NVML (NVIDIA Management Library) for GPU power
- Falls back to estimation methods if NVML unavailable
- Per-phase power estimated proportionally to timing

## Installation

### Prerequisites
```bash
# 1. CUDA Toolkit (11.0+)
# On HPC systems:
module load cuda

# 2. Python packages
pip install numpy numba psutil
```

### Verify Installation
```bash
python3 -c "import numba.cuda; print('CUDA Available:', numba.cuda.is_available())"
```

## Usage

### Run Full Benchmark
```bash
python main_gpu.py
```

This will:
- Auto-detect your GPU
- Run benchmarks for all board sizes (2×2, 3×3, 5×5, 9×9, 13×13, 19×19)
- Generate CSV output in `results/` directory

### Output Format
CSV file: `results/mcts_benchmark_gpu_<mode>_<timestamp>.csv`

Columns match CPU benchmark format:
- System info: `timestamp`, `system_id`, `processor`, `power_method`
- Per-trial: `board_size`, `iterations`, `trial_num`
- Metrics: `total_latency_ms`, `total_power_mw`, `total_energy_uj`, `tree_size`
- Per-phase: `{phase}_latency_ms`, `{phase}_power_mw`, `{phase}_energy_uj`, `{phase}_percent`

## Configuration

Edit `mcts_gpu/benchmark.py` to modify:

```python
BENCHMARK_CONFIG = {
    board_size: {
        'iterations': int,      # MCTS iterations
        'exploration': float,   # UCB exploration constant (usually √2)
        'rollout_depth': int,   # Max playout depth (unused in GPU version)
        'trials': int           # Number of trials per board size
    }
}
```

MCTSNC parameters in `run_single_benchmark_gpu()`:
- `n_trees`: Number of parallel trees (default: 8)
- `n_playouts`: Playouts per node (default: 128, must be power of 2)
- `variant`: Algorithm variant (`acp_prodigal` recommended)
- `device_memory`: GPU memory in GiB (default: 2.0)
- `ucb_c`: UCB exploration constant

## Troubleshooting

### CUDA Not Available
```bash
# Check NVIDIA driver
nvidia-smi

# Check CUDA installation
nvcc --version

# Load CUDA module (HPC)
module load cuda
```

### Out of Memory
Reduce GPU memory usage by editing `mcts_gpu/benchmark.py`:
```python
ai = MCTSNC(
    ...
    n_trees=4,              # Reduce from 8
    n_playouts=64,          # Reduce from 128
    device_memory=1.0,      # Reduce from 2.0
    ...
)
```

### Slow Performance
- Increase parallelism: `n_trees=16`, `n_playouts=256`
- Check GPU utilization: `nvidia-smi dmon`
- Profile with: `nsys profile python main_gpu.py`

## Differences from CPU Version

| Feature | CPU Version | GPU Version |
|---------|-------------|-------------|
| **Implementation** | Pure Python | Numba CUDA |
| **Parallelization** | None (single-threaded) | Root (8 trees) + Per-node (128 playouts) |
| **Go Rules** | No captures | No captures |
| **Power Method** | RAPL/psutil | NVML |
| **Speed** | ~1-10 ms (small boards) | ~1-100 ms (includes overhead) |

## Future Enhancements

For full Go rules implementation, add to device functions:
- [ ] Capture detection (group/liberty counting)
- [ ] Ko rule enforcement
- [ ] Territory scoring (flood fill)
- [ ] Superko detection (optional)

See mcts_numba_cuda research report for details.

## Credits

Based on **mcts_numba_cuda** by Przemysław Klęsk:
- Repository: https://github.com/pklesk/mcts_numba_cuda
- Paper: "MCTS-NC: GPU parallelization of Monte Carlo Tree Search" (2025)

Adapted for hardware benchmarking with simplified Go rules.
