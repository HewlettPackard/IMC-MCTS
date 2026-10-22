# RTL and Aggregate Synthesis Artifacts

This directory contains the project-owned SystemVerilog, public analysis code,
and memory-model inputs used by the accelerator architecture study. Generated
synthesis reports and aggregate result tables are local-only outputs.

## Contents

| Path | Contents |
|---|---|
| `rtl/` | Exploratory SystemVerilog snapshots for architecture studies |
| `postprocess/` | Plotting and report-generation scripts |
| `data/CAM_cell_choices.csv` | Literature-collected CAM-cell comparison data |
| `data/memory_characterization/` | Public memory-model configurations |

## RTL support status

The board-size RTL variants are included for code inspection and research
traceability. They are not a supported standalone implementation, are not
lint-clean when all files are passed to Verilator or Icarus, and are not
covered by CI. This source-only snapshot does not include an authoritative
file list, integration testbench, synthesis script, or the original commercial
tool setup. Do not treat a whole-directory compile as a defined design or
these sources as signoff-ready RTL.

## Run local post-processing

From the repository root:

```bash
python rtl_synthesis/postprocess/visualize_synthesis_results.py
python rtl_synthesis/postprocess/synthesis_results_summary.py
```

These scripts expect locally regenerated synthesis summary inputs. They do not
rerun the original commercial synthesis flow.

## Public-release boundary

This repository intentionally excludes foundry libraries, PDK collateral,
commercial EDA setup and license files, private measurement workbooks, and
machine-specific paths. Generated aggregate numbers should be treated as local
research artifacts, not as a reproducible signoff flow.

See [`../REPRODUCIBILITY.md`](../REPRODUCIBILITY.md) for provenance limitations.
