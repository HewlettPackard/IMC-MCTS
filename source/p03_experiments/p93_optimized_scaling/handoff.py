# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
from pathlib import Path
import csv,json,hashlib,difflib
ROOT=Path.cwd();H=ROOT/'p03_experiments/p93_optimized_scaling'
rows=list(csv.DictReader((H/'p04_figures/totals.csv').open()))
summary='\n'.join(f"| {r['board_size']}×{r['board_size']} | {int(r['iterations']):,} | {float(r['latency_ms']):.3f} | {float(r['energy_mj']):.3f} | {float(r['power_mw']):.3f} | {float(r['area_mm2']):.3f} |" for r in rows if r['tier']=='Medium')
text=f'''# Morning handoff: optimized IMC-MCTS scaling, 29 September 2026

The approved modeled scaling campaign is complete. All 18 board/budget searches finished, the optimized nine-by-nine reference is reproduced, Studio supports the approved board-dependent memories, and both AUTHOR FIX paper projects are updated in blue and compile. This establishes modeled functional/scheduling readiness, not physical crossbar or chip validation.

## Primary result

One empty 9×9 Go board, Go-strong weights, medium budget of 5,000 iterations, seed 0, 500-MHz assumed clock:

- Latency: **55.186986 ms**, 27,593,493 cycles.
- Energy: **3.881492849 mJ** per complete search.
- Average power: **70.333481 mW** (1,000 × mJ/ms).
- Installed modeled area: **5.810570485 mm²**, including 2 MiB SRAM, 32 native-area ADC budgets and physical allowance.
- Phases: selection 24.537884 ms; expansion 2.878402 ms; neural 26.660000 ms; backpropagation 1.070700 ms; completion 0.040000 ms.

These reproduce the existing optimized design, not a new optimization gain. The 16 UCB scorers, 32 shared ADCs, 128-bit readout, eight accumulation lanes and two result banks are retained. Weights occupy two offset-encoded 8-bit 1T1M arrays, 163×96 and 96×3 at 9×9.

## Completed scaling data

All six boards completed all three approved budgets. `scaling_all18.csv` is the raw 18-case seed-0 diagnostic sweep. `p04_figures/totals.csv` is the presentation dataset: its 9×9 medium cell uses the trained primary reference consistently with the paper, while the other 17 cells use diagnostic weights. These two datasets are intentionally distinguished.

Medium-budget presentation results:

| Board | Iterations | Latency (ms) | Energy (mJ) | Power (mW) | Area (mm²) |
|---|---:|---:|---:|---:|---:|
{summary}

The largest high-budget case, 19×19 with 20,000 iterations, completes in **620.304396 ms**, **62.110058 mJ**, **100.128354 mW**, with **8.347620320 mm²** and **4.5 MiB SRAM**. Its first array is 723×96, second 96×3, and neural evaluation takes 5,431 modeled cycles. The high budget is twice medium at every board size.

## Evidence and implementation

- `p00_before`: source/dirty-diff backup and preserved nine-by-nine reference.
- `hardware_audit.json`: Super-T workbook values and source cells, separate assumptions, board memory characterizations and largest-case requirements.
- `all_tests_final.log`: **271 tests pass**. Tests cover trained 9×9 regressions, larger-board policy comparisons, independent integer dot products, bounds and pipeline resource checks. Shared policy primitives limit independence of whole-search comparisons.
- `reference_regression.json`: complete 5,000-iteration cycle/phase/tree/child-memory match to the saved optimized result, plus a final-source repeat. Expanded path storage moves node addresses; no byte-identical node-memory claim across old/new layouts.
- `sweep_manifest.json`, each run's `verification.json` and `SHA256SUMS.json`: completion, packed SRAM, cycle and unit checks.
- `final_verification.json`, `final_source_sha256.json`, `source_snapshot.tar.gz`: source identities and reproducibility audit.
- `p03_studio_checks/browser_checks.json`: six board presets, 19×19 live allocation, pause/cancel, completed small move, reload and byte-matched downloaded JSON/CSV. No browser errors.
- Current local Studio is refreshed at http://127.0.0.1:4784/. Selecting a board sets the latest optimized architecture with that board's CAM, SRAM and iteration presets. Existing historical records retain their old identities. The HPE server deployment was not changed.

## Paper and figures

Only the two authorized Overleaf **AUTHOR FIX** projects were edited. Prior sources and figures are preserved in `p02_paper_before`; visible writing/table edits remain blue.

- Abstract, reference results, methods and supplement use the same 9×9 medium/Go-strong numbers and architecture.
- Supplementary S1 now describes executed memory/budget configurations; S3 is regenerated from the primary component ledger.
- Figure 2d/e regenerated in the original plotting style, including shared memory. Installed area is constant across budgets for a given board.
- Figure 3b/c regenerated with the trained primary point and unchanged processor data/formulas. Numerical gain ratios are explicitly not matched-workload claims; batched GPU factors remain extrapolations.
- Extended Data energy table uses the new medium-budget IMC values, retaining processor values and marking comparison ratios pending.
- Compiled previews: `p05_pdf/manuscript/main.pdf` and `p05_pdf/supplement/main.pdf`. Both compile; rendered pages checked, no overfull boxes or unresolved references. Existing font/bookmark warnings remain.
- Plot PDFs/PNGs and exact CSVs: `p04_figures/`. No panel letters are embedded in the new individual plots.

## Remaining uncertainties and paper items

1. Super-T supplied cell parameters remain authoritative. Reliable 256-level operation, ideal 12-bit conversion, common bias/interface compatibility, three-cycle settling and large-array wire effects are **not physically validated**. The 723-row custom array is an engineering geometry assumption.
2. Native published ADC area/event-energy budgets, retained digital report scaling, larger-board parent geometry, register/ALU estimates, memory-router scaling and fixed mean activity/conductance are disclosed proxies. The reported precision is reproducibility, not accuracy of a silicon measurement.
3. Host Go rules/history, I/O, weight programming and startup calibration remain outside the modeled preloaded core.
4. One seed and initial position per configuration do not characterize workload variation or playing strength. Scaling weights are diagnostic. The historical 500-simulation tournament is separate from the 5,000-iteration reference.
5. Figure 2a-c retains the conceptual historical schematic; its caption points to current resource counts in the text. Figure 3a retains the historical fixed-5,000-iteration curve because the approved board budgets differ. These are explicitly labeled and still need a future figure-level reconciliation before a fully unified submission. Historical cross-domain, noise and process-projection material is also qualified, not revalidated.
6. CPU/GPU workload/checkpoint/boundary matching is still unresolved. No new superiority claim follows from merely plotting the new point. No CPU/GPU or tournament reruns, publication, remote deployment or repository push occurred.

Next human review: inspect the new data and blue paper changes, then decide how to reconcile the retained historical panels and comparison evidence. Another optimization campaign is not required for these completed scaling results.
'''
(H/'MORNING_HANDOFF.md').write_text(text)
(H/'README.md').write_text('# Round 93: optimized scaling\n\nStart with [MORNING_HANDOFF.md](MORNING_HANDOFF.md).\n\nRun `python -B -m p03_experiments.p93_optimized_scaling.run --board 19 --budget high` for the largest approved diagnostic case. `sweep.py` runs the 18 approved cases after the regression gate. `figures.py` regenerates the original-style panels. Paper scripts retain the exact authorized edits and are guarded against overwriting changed source; they are not general repeat-in-place editors.\n')
p=ROOT/'ARCH_MENTOR.md'
p.write_text(p.read_text()+'''\n## Round 93: verified optimized board-size scaling, 2026-09-29\n\nThe current Studio scope now supersedes Round 91's nine-by-nine-only limitation: approved boards 2,3,5,9,13,19 use the existing 16-UCB/32-ADC parallel schedule and board_sized_s1_v1 CAM/SRAM budgets. All 18 diagnostic searches complete; 271 tests and isolated browser/export checks pass. The 9x9 medium Go-strong reference reproduces 55.186986 ms, 3.881492849 mJ, 70.333481 mW and 5.810570485 mm2. Node offsets change with the 163-entry path reservation; numerical tree and cycles match the saved optimized reference. Super-T workbook values remain the crossbar source; larger-array settling/precision and cost proxies are not physically validated. Both approved AUTHOR FIX projects are updated in blue and compiled; historical figure/baseline/tournament limitations remain explicit. See p03_experiments/p93_optimized_scaling/MORNING_HANDOFF.md and final_verification.json. No new optimization, benchmark/tournament rerun, deployment or push.\n''')
p=ROOT/'ROUND93_PLAN.md';p.write_text(p.read_text()+'''\n## Outcome\n\nSteps 1-9 completed within the modeled and authorized scope; all 18 searches and the trained reference completed. Source audit, regression logs, original-style plots, blue AUTHOR FIX edits, compiled PDFs and morning handoff are in p03_experiments/p93_optimized_scaling. Remaining physical and historical-comparison uncertainties are listed explicitly in MORNING_HANDOFF.md.\n''')
print('Saved morning handoff, reproducibility README and architecture/plan outcome')
