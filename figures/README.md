# Figure and table reproduction

Run from the package root with the Python environment described in the root instructions:

```sh
python -B figures/regenerate.py
```

Optional rendered-PDF comparison (requires PyMuPDF in addition to NumPy, Pandas and Matplotlib):

```sh
python -B figures/regenerate.py --verify-render
```

The entry point verifies the SHA-256 identity of the packaged inputs and plotters, then writes only to `figures/generated/`. It runs a fixed list of six plotting scripts and never launches a simulation, benchmark, training process or tournament. It never installs files in a paper directory. It can be launched from any current directory because paths resolve relative to the package.

The plotted values and styles are preserved. Plotter adaptations only replace machine-specific input/output paths and, for Figure 2d/e, extract the original drawing routine from its experiment runner. Extended Data Figure 1 pins DejaVu Serif, the font embedded in its canonical archived PDF, instead of relying on a machine-dependent fallback. The original source hashes and packaged hashes are recorded in `inputs_manifest.json`; coverage and paper-asset mappings are in `coverage.json`. Stored expected PDFs are the exact current manuscript assets, before any regeneration. Output PDFs can differ byte-for-byte because of PDF metadata, font availability or rendering-library versions. The optional check reports raster identity and differences without silently replacing the expected files.

## Coverage

| Paper item | Packaged support | Evidence boundary |
| --- | --- | --- |
| Figure 1a–c | Original supplied vector PDFs | Conceptual diagrams; editable native source not recovered in this package. |
| Figure 2a–c | Original supplied vector PDF | Conceptual chip/tile/dataflow diagram. This is not generated from the simulator. |
| Figure 2d/e | CSVs and original drawing routine | Replots all 18 archived board/budget rows. Expansion/backpropagation display allocation is retained. |
| Figure 3a | CSV and plotter | Replots archived energy per iteration within a move. CPU/GPU values are archived baseline records; no baseline is rerun. |
| Figure 3b | CSV and plotter | Replots archived per-move energy and latency under the paper's distinct implementation/accounting boundaries. |
| Figure 3c | CSV, ratio derivation and plotter | Preserves the approved orange/blue steps and thick red combined-ratio caps. The ratios are implementation-specific comparisons, not isolated causal hardware/algorithm gains. |
| Figure 3d | **ON HOLD** | No Elo data, tournament records, plot asset or regeneration target is included here. |
| Figure 4a | Archived quality CSVs and original plotter | **Replot only.** Does not reproduce model training, identify the missing exact trained checkpoint/encoder pairs, or rerun functional evaluations. |
| Figure 4b | CSV and original plotter | Replots archived current-architecture energy projections. Non-Go tasks are diagnostic cost projections, not recovered trained hardware mappings. |
| Extended Data Figure 1 | Original frozen bottleneck CSV and plotter | Replots archived CPU/GPU phase fractions. Does not rerun profiling or independently recover power traces. |
| Extended Data Tables 1–4 | Exact approved LaTeX table extracts | These preserve the current manuscript tables. Numerical/literature extraction is not a new experiment or independent prior-work verification. |
| Supplementary Tables S1–S7 | Exact approved LaTeX table extracts | These preserve current supplement tables, including clearly marked historical/provisional comparisons. |

## Inputs and units

`data/figure_inputs/` contains byte-preserved CSV inputs. Resource scaling uses `resources/`; Figure 3a uses `fig3a/`; Figures 3b/c share `comparisons/fig3bc.csv`; Figure 4 uses `applications/`. Extra application source CSVs are archived functional results, not trained model artifacts. `bottleneck/` contains the archived phase-fraction CSV.

The primary hardware example is 9×9 medium with 5,000 iterations per move. Figure 3a reports average energy per iteration within a move, in µJ, whereas Figure 3b and the Figure 3c energy ratios use total energy per move, in mJ. Figure 4a uses its historical functional evaluation budgets, separately from the 5,000-iteration diagnostic cost projection in Figure 4b. See the supplied table captions and root REPRODUCIBILITY.md for the packaged configurations and evidence limits.

This figure entry point reuses frozen numerical result tables. To reproduce the simulator result calculations rather than just their visualization, use the root simulator/accounting instructions. Replotting agreement does not validate physical accuracy or establish equal-work/equal-quality CPU/GPU comparisons.
