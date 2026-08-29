# Event-Driven Simulator

This directory documents the public accelerator event-driven simulator. The
implementation models the Selection, Expansion, Rollout, and Backpropagation
stages and reports latency, energy, area, and activity estimates.

## Run

From the repository root:

```bash
python core/simulator/runs/run_9x9_hardware_metrics.py
make sim
```

The first command runs one 9x9 configuration. `make sim` runs each supported
board size and takes longer.

## Scope

- [`CAM_ARCHITECTURE_DOCUMENTATION.md`](CAM_ARCHITECTURE_DOCUMENTATION.md)
  explains the CAM-backed transposition model.
- `core/simulator/hardware_metrics/` contains the analytical/event-driven components.
- `core/simulator/ablation_studies/` contains exploratory analysis scripts.

Generated simulator result tables are local-only outputs and are not shipped in
the source-only release.

The simulator uses public aggregate assumptions and literature-derived models.
It does not include foundry libraries, PDK collateral, commercial tool setup,
or a signoff-quality implementation flow. See
[`../../../REPRODUCIBILITY.md`](../../../REPRODUCIBILITY.md) before using the
reported values in a publication.
