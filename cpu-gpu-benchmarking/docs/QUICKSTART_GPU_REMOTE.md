# Quick Start Guide: Running on a Remote GPU System

Complete guide to run MCTS benchmarks on a remote GPU or HPC system and
generate publication tables.

**Estimated Time**: 30-60 minutes (depending on board sizes)

---

## Step 1: Prerequisites Check

First, verify the remote environment has what we need:

```bash
# Check Python version (need 3.7+)
python3 --version

# Check if CUDA is available
nvidia-smi

# Check CUDA compiler (optional, but helpful)
nvcc --version
```

**Expected Output**:
- Python 3.7 or higher
- `nvidia-smi` should show GPU information
- If `nvcc` not found, you may need to load CUDA module (see next step)

---

## Step 2: Load CUDA Module (HPC Systems)

If you're on an HPC system with module system:

```bash
# Check available CUDA modules
module avail cuda

# Load CUDA (adjust version as needed)
module load cuda

# Verify CUDA is loaded
nvcc --version
```

**Skip this step** if CUDA is already available in your PATH.

---

## Step 3: Clone Repository

```bash
# Navigate to your working directory
cd ~  # Or wherever you want to work

# Clone the repository
git clone https://github.com/HewlettPackard/IMC-MCTS.git

# Navigate into the directory
cd imc-mcts

# Verify files are there
ls -la
```

**Expected Output**: You should see:
- `main_cpu.py`
- `main_gpu_fair.py`
- `main_gpu_capability.py`
- `mcts_cpu/` directory
- `mcts_gpu/` directory
- `utils/` directory
- `README.md`

---

## Step 4: Install Python Dependencies

```bash
# Install dependencies
pip install -r requirements.txt

# Verify installations
python3 -c "import numpy; print('numpy:', numpy.__version__)"
python3 -c "import psutil; print('psutil:', psutil.__version__)"
python3 -c "import numba; print('numba:', numba.__version__)"

# CRITICAL: Check CUDA availability in numba
python3 -c "import numba.cuda; print('CUDA available:', numba.cuda.is_available())"
```

**Expected Output**:
- All imports should succeed
- Last command should print: `CUDA available: True`

**If CUDA not available**:
- Make sure CUDA module is loaded
- Check that `nvidia-smi` works
- You may need to set environment variables:
  ```bash
  export CUDA_HOME=/usr/local/cuda  # Adjust path
  export PATH=$CUDA_HOME/bin:$PATH
  export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
  ```

---

## Step 5: Run CPU Benchmark (Test + Baseline)

Start with CPU to verify everything works:

```bash
# Run CPU benchmark
python3 main_cpu.py
```

**What to Expect**:
- Console output showing progress for each board size (2×2, 3×3, 5×5, 9×9, 13×13, 19×19)
- Each board size runs 5 trials
- Shows latency, power, and energy per trial
- Creates CSV file in `results/` directory

**Example Output**:
```
======================================================================
MCTS CPU Benchmark (Python + Simplified Go)
Matching IMC-MCTS SST Medium Play Strength Configuration
======================================================================

System Information:
  System ID: local_system
  Processor: Intel(R) Xeon(R) Gold 6248R CPU @ 3.00GHz
  CPU Cores: 24
  Memory: 256.0 GB

Initializing power monitor...
Power monitoring method: RAPL

Running CPU benchmarks...
Board sizes: [2, 3, 5, 9, 13, 19]

  Running 2×2 board (200 iterations, 5 trials)...
    Trial 1/5... 2.3 ms
    Trial 2/5... 2.1 ms
    Trial 3/5... 2.2 ms
    Trial 4/5... 2.1 ms
    Trial 5/5... 2.2 ms
    Average: 2.2 ± 0.1 ms, 115.2 ± 2.3 mW, 252.5 ± 8.1 µJ

  Running 3×3 board (500 iterations, 5 trials)...
    ...

✅ Results saved to: results/mcts_benchmark_cpu_20251111_172530.csv
```

**Verify**:
```bash
# Check that CSV was created
ls -lh results/

# Preview the CSV (first few lines)
head -n 5 results/mcts_benchmark_*.csv
```

**Estimated Time**:
- 2×2 to 5×5: ~1 second each
- 9×9: ~30 seconds
- 13×13: ~2 minutes
- 19×19: ~3-4 minutes
- **Total: ~6-8 minutes**

---

## Step 6: Run GPU Benchmark - Fair Comparison Mode

Now test GPU in fair comparison mode (1 tree, 1 playout):

```bash
# Run GPU fair mode
python3 main_gpu_fair.py
```

**What to Expect**:
- Similar output to CPU benchmark
- Should show: "Mode: fair (n_trees=1, n_playouts=1, variant=ocp_thrifty)"
- First run may be slower due to CUDA JIT compilation
- Creates CSV file: `results/mcts_benchmark_gpu_fair_<timestamp>.csv`

**Example Output**:
```
======================================================================
MCTS GPU Benchmark (mcts_numba_cuda + Simplified Go)
Matching IMC-MCTS SST Medium Play Strength Configuration
Mode: fair (n_trees=1, n_playouts=1, variant=ocp_thrifty)
======================================================================

System Information:
  System ID: local_system
  GPU: NVIDIA Tesla V100-SXM2-32GB
  CPU Cores: 24
  Memory: 256.0 GB

Initializing power monitor...

Running GPU benchmarks...
Board sizes: [2, 3, 5, 9, 13, 19]

  Running 2×2 board (200 iterations, 5 trials)...
    GPU Config: n_trees=1, n_playouts=1, variant=ocp_thrifty
    Trial 1/5... 15.2 ms  (first trial includes JIT compilation)
    Trial 2/5... 1.8 ms
    Trial 3/5... 1.7 ms
    Trial 4/5... 1.8 ms
    Trial 5/5... 1.7 ms
    Average: 4.2 ± 5.1 ms, ...

  Running 3×3 board (500 iterations, 5 trials)...
    ...
```

**Note**: First trial will be slower due to CUDA JIT compilation. This is normal.

**Verify**:
```bash
# Check CSV was created
ls -lh results/mcts_benchmark_gpu_fair_*.csv

# Verify it has GPU config columns
head -n 2 results/mcts_benchmark_gpu_fair_*.csv | grep "n_trees"
# Should see: n_trees,n_playouts,variant
```

**Estimated Time**:
- First run: +30 seconds for JIT compilation
- Subsequent runs: Similar to CPU or faster
- **Total: ~10-15 minutes** (including compilation)

---

## Step 7: Run GPU Benchmark - Maximum Capability Mode

Test GPU maximum throughput (8 trees, 128 playouts):

```bash
# Run GPU capability mode
python3 main_gpu_capability.py
```

**What to Expect**:
- Should show: "Mode: capability (n_trees=8, n_playouts=128, variant=acp_prodigal)"
- May be faster than fair mode for larger boards
- Uses more GPU memory
- Creates CSV file: `results/mcts_benchmark_gpu_capability_<timestamp>.csv`

**Watch for**:
- GPU memory errors (if board too large or GPU has limited memory)
- If you get memory errors, you can skip this for now and just use fair mode

**Estimated Time**: ~10-15 minutes

---

## Step 8: Generate Publication Tables

Now generate publication-ready tables from all three benchmarks:

```bash
# Auto-find latest CSV files and generate tables
python3 utils/generate_tables.py --auto-find --board-size 9x9 --output-dir tables
```

**What to Expect**:
- Script finds latest CPU, GPU-fair, and GPU-capability CSV files
- Generates 6 files in `tables/` directory:
  - `phase_breakdown.md`, `.tex`, `.csv`
  - `scalability_analysis.md`, `.tex`, `.csv`
- Shows preview of tables in console

**Example Output**:
```
📂 Auto-detected files:
   CPU:      results/traditional/mcts_benchmark_cpu_<processor>_<timestamp>.csv
   GPU Fair: results/traditional/mcts_benchmark_gpu_fair_<timestamp>.csv
   GPU Cap:  results/traditional/mcts_benchmark_gpu_capability_<timestamp>.csv

📖 Loading data...
   CPU: 30 trials
   GPU Fair: 30 trials
   GPU Capability: 30 trials

📊 Generating phase breakdown table (board size: 9x9)...
   ✅ Phase breakdown saved to tables/phase_breakdown.[md|tex|csv]

📊 Generating scalability analysis table...
   ✅ Scalability analysis saved to tables/scalability_analysis.[md|tex|csv]

======================================================================
PREVIEW - Phase Breakdown Table
======================================================================
...
```

**Verify**:
```bash
# Check that tables were created
ls -lh tables/

# View markdown tables
cat tables/phase_breakdown.md
cat tables/scalability_analysis.md

# View LaTeX tables (for paper)
cat tables/phase_breakdown.tex
cat tables/scalability_analysis.tex
```

**Estimated Time**: ~5 seconds

---

## Step 9: Review Results

Check your results:

```bash
# View phase breakdown (Markdown format)
cat tables/phase_breakdown.md

# View scalability analysis
cat tables/scalability_analysis.md

# Check CSV files for detailed data
head -n 20 results/mcts_benchmark_gpu_fair_*.csv
```

**What to Look For**:
1. **CPU vs GPU-Fair comparison** (hardware comparison):
   - GPU should be similar or faster in latency
   - Check energy consumption differences

2. **GPU-Fair vs GPU-Capability** (parallelism benefit):
   - Capability mode should be significantly faster for large boards
   - May use more energy due to higher parallelism

3. **Scalability** (across board sizes):
   - Latency should increase with board size
   - Energy should scale proportionally

---

## Step 10: Download Results (Optional)

If you want to download results to your local machine:

```bash
# On your local machine
scp -r user@remote-host:/path/to/imc-mcts/results ./
scp -r user@remote-host:/path/to/imc-mcts/tables ./
```

Or use the tables directly from the remote environment for publication figures.

---

## Complete Command Summary

Here's the complete sequence to copy-paste:

```bash
# 1. Setup
cd ~
git clone https://github.com/HewlettPackard/IMC-MCTS.git
cd imc-mcts

# 2. Load CUDA (if on HPC)
module load cuda

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify CUDA
python3 -c "import numba.cuda; print('CUDA available:', numba.cuda.is_available())"

# 5. Run benchmarks (one at a time)
python3 main_cpu.py
python3 main_gpu_fair.py
python3 main_gpu_capability.py

# 6. Generate tables
python3 utils/generate_tables.py --auto-find --board-size 9x9 --output-dir tables

# 7. View results
cat tables/phase_breakdown.md
cat tables/scalability_analysis.md

# 8. List all output files
ls -lh results/
ls -lh tables/
```

**Total Estimated Time**: 30-60 minutes

---

## Troubleshooting

### Issue 1: CUDA Not Available

**Symptom**: `CUDA available: False`

**Solutions**:
```bash
# Try loading CUDA module
module load cuda

# Check NVIDIA driver
nvidia-smi

# Set environment variables manually
export CUDA_HOME=/usr/local/cuda
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# Reinstall numba
pip install --upgrade numba
```

### Issue 2: GPU Memory Error

**Symptom**: `CUDA out of memory` error during GPU capability mode

**Solution**: Skip capability mode for now, or reduce parameters:
```python
# Edit main_gpu_capability.py, change line 58 to:
main(n_trees=4, n_playouts=64, variant='acp_prodigal', mode_name='capability')
```

### Issue 3: Import Errors

**Symptom**: `ModuleNotFoundError: No module named 'mcts_cpu'`

**Solution**: Make sure you're in the right directory:
```bash
cd /path/to/imc-mcts
python3 main_cpu.py  # Use python3, not python
```

### Issue 4: Permission Errors (Power Monitoring)

**Symptom**: Warning about RAPL permissions

**This is OK**: The benchmark will fall back to estimation. For more accurate power:
```bash
sudo chmod -R a+r /sys/class/powercap/intel-rapl/
```

### Issue 5: Slow Performance

**Symptom**: GPU benchmarks take forever

**Check**:
1. First trial is always slow (JIT compilation) - this is normal
2. Check GPU utilization: `watch -n 1 nvidia-smi`
3. Verify correct GPU is being used (if multiple GPUs)

### Issue 6: Table Generation Fails

**Symptom**: `Error: No CPU benchmark files found`

**Solution**: Make sure you ran all benchmarks first:
```bash
ls results/
# Should see at least:
# - mcts_benchmark_*.csv (CPU)
# - mcts_benchmark_gpu_fair_*.csv (GPU fair)
```

If only some benchmarks completed, you can still generate partial tables:
```bash
# Manual file specification
python3 utils/generate_tables.py \
  --cpu-file results/mcts_benchmark_*.csv \
  --gpu-fair-file results/mcts_benchmark_gpu_fair_*.csv \
  --board-size 9x9
```

---

## Quick Test (Just 2×2 Board)

If you want to quickly test everything works before running full benchmarks:

```bash
# Test CPU (quick - should take ~1 second)
timeout 30 python3 main_cpu.py  # Will run only 2x2 before timeout

# Test GPU Fair (quick test)
timeout 60 python3 main_gpu_fair.py  # Includes JIT compilation

# If above works, run full benchmarks
python3 main_cpu.py
python3 main_gpu_fair.py
python3 main_gpu_capability.py
```

---

## Next Steps After Success

1. **Review your results**: Check if numbers make sense
2. **Copy LaTeX tables**: Use `.tex` files in publication materials
3. **Generate plots** (optional): Use CSV data to create graphs
4. **Compare to the IMC-MCTS accelerator**: Use tables to motivate your accelerator
5. **Review generated outputs locally**. Do not commit generated benchmark
   CSVs, tables, or plots to the source-only release.

---

## Expected Results Directory Structure

After completion, you should have:

```
imc-mcts/
├── results/
│   ├── mcts_benchmark_cpu_<processor>_<timestamp>.csv         # CPU results
│   ├── mcts_benchmark_gpu_fair_<timestamp>.csv                # GPU fair results
│   └── mcts_benchmark_gpu_capability_<timestamp>.csv          # GPU capability results
│
└── tables/
    ├── phase_breakdown.md         # Markdown table
    ├── phase_breakdown.tex        # LaTeX table (copy to paper)
    ├── phase_breakdown.csv        # Raw data
    ├── scalability_analysis.md    # Markdown table
    ├── scalability_analysis.tex   # LaTeX table (copy to paper)
    └── scalability_analysis.csv   # Raw data
```

---

## Contact

If you encounter issues not covered here:
1. Check the main README.md
2. Review the memory file: `11112025_memory.txt`
3. Open a GitHub issue
