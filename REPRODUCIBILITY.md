# Reproducibility Status

This source-only release excludes generated result tables, rendered figures,
datasets, logs, and trained weights. Reproducibility commands regenerate those
artifacts locally when the required optional inputs are available.

## Verified from a fresh clone

| Scope | Command | Status |
|---|---|---|
| Install | `python3 -m pip install -e .` | Pass on Python 3.10 and 3.12 |
| Public regression tests | `make check` | Pass: 5 tests |
| Paper figure rendering | `make paper` | Requires locally regenerated `paper/results/` tables |
| Cross-domain energy figure | `python paper/figure/regenerate_5c_cross_domain_energy.py` | Requires locally regenerated SGG tables |
| Generalizability demos | `python generalizability/demos/run_all_demos.py` | Pass for all 13 applications |
| Event-driven simulator | `python core/simulator/runs/run_2x2_hardware_metrics.py` and `run_9x9_hardware_metrics.py` | Pass |
| CPU benchmark build | `make bench-cpu` | Pass with a C++17 compiler |

The CI workflow also tests Python 3.10, 3.11, and 3.12.

## Reproducibility matrix

| Result family | Public status | Limitation |
|---|---|---|
| Paper plots | Locally re-renderable | Requires locally regenerated `paper/results/`; image bytes vary across plotting/font versions. |
| Figure 1 bottleneck data | Not end-to-end reproduced by the source-only release | Raw benchmark outputs are local-only. |
| Figures 4 and 6 | Locally regenerable | Requires local simulator/benchmark outputs. |
| Figure 5 energy scaling | Locally regenerable | Requires matching local configuration. |
| Figure 5c cross-domain energy | Locally regenerable | Requires regenerated datasets and weights. |
| Figure 7 ELO curves | Locally regenerable | Requires external engines and regenerated tournament outputs. |
| Table III CPU/GPU values | Locally re-measurable | Requires comparable CPU/GPU hardware and software versions. |
| Table III IMC values | Locally regenerable | Requires matching simulator configuration. |
| RTL/synthesis estimates | Reference RTL and public analysis scripts only | No supported, lint-clean unified build is provided; the authoritative file list, integration testbench, commercial flow output, aggregate result tables, and technology collateral are excluded. |
| External-engine tournaments | Environment-dependent | GNU Go, Pachi, KataGo, models, and exact engine versions are not vendored. |
| Training results | Not fully end-to-end reproducible | Large generated datasets and intermediate checkpoints are excluded from Git. |

## Known drift

Generated result tables are excluded from the source-only release. To rebuild
paper inputs after regenerating raw benchmark/simulator outputs, run:

```bash
python paper/figure/generate_data_files.py
```

The source-only release is intended for code inspection and local regeneration,
not as a frozen numeric artifact bundle.

## Required experiment record

For every new result, record:

- Commit SHA and command line.
- Random seed and complete configuration file.
- Python/compiler/CUDA and dependency versions.
- CPU/GPU model and operating mode.
- Input dataset or model checksum.
- Raw output file and the script that converts it into a paper table.

Do not commit foundry collateral, PDK files, commercial EDA libraries, private
measurement workbooks, or employer-owned source code. Public releases should
contain only aggregate releasable measurements and literature-derived models.
