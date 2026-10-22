# Old versus repaired IMC-MCTS

2026-09-12 UTC. Reviewed repair: 0ef0088. Release baseline: 93b7ba4.
Research stage remains Estimate; the Go adapter has a confirmed correctness
regression requiring repair before stronger functional claims.

The high-level search and division into Selection, Expansion, Rollout,
Backprop and FSM are preserved. However, the repair also chose concrete memory,
arithmetic and scheduling implementations. These are more than organization or
accounting fixes. Two priorities emerged: a Go value-perspective regression,
and an unresolved difference between the written TCAM-controller design and
the implemented digital FSM. Neither should be hidden under a blanket claim
that everything has the same meaning.

## Which old version is the reference?

The preserved release at 93b7ba4 is the primary executable reference. The
separate legacy try2 tree and submitted supplement are additional evidence,
already archived in the [Round 6 review](../p05_legacy_design_review/README.md).
They do not define one consistent golden implementation:

- The release event engine expands all empty cells at a visited leaf; its
  generic MCTS engine expands one child at a time. Earlier bounded probes
  produce 82 versus 3 nodes after two empty-9x9 iterations, respectively.
- The event engine uses two input channels and a two-layer neural evaluator.
  Other old evaluators/checkpoints have different shapes and conventions.
- The supplement describes board-pattern CAM rows, parent-ID child lookup,
  a TCAM FSM and single-cycle decisions. The active old event path does not
  implement all those mechanisms.

The comparison therefore distinguishes the original event algorithm, recovered
hardware intent and separate legacy helpers. It does not claim equivalence to
every old code path or publication statement.

## Comparison

| Part | Before repair | Repaired implementation | Classification and effect on meaning |
|---|---|---|---|
| MCTS stages | Selection, expansion, one neural evaluation, backpropagation, sequenced by a controller | Same stages and dependency order | Preserved at the high level; the new core is a separate implementation, not the identical old execution engine. |
| Expansion policy | Active event path evaluates an unvisited root, then creates all empty-cell children at a visited leaf in row-major order and chooses one for evaluation | Complete placement profile retains that policy | Preserved relative to the event path. It is not the old generic engine's one-child expansion policy. |
| Requested iterations | The API could report its requested budget while the controller used a different preset | Requested count is passed through and completion is checked; complete core runs its explicit budget | Bug fix. Correct execution can produce different totals. |
| Selection value convention | Event path stores the player-to-move value; parent UCB uses its complement, with first-unvisited and first-tie priority | Complete placement profile retains those conventions with fixed-point arithmetic | Intended behavior preserved, subject to finite precision. The Go override is inconsistent, described below. |
| Go gameplay | A separate legacy engine implements captures, suicide prevention, simple ko, passes, scoring and move cap; event diagnostics only place stones | Go adapter reuses the same rule-engine bytes, fixes stale pass-ko/history/legality defects and generates actual legal successors | Reuse plus integration and bug fixes. Host-assisted Go is a separate workload, not identical to placement or the old generic search. Terminal scoring overrides the neural value. |
| Neural function | Event path: interleaved Black/White inputs, two linear layers with ReLU, White/draw/Black softmax, black-player value | Same mathematical topology and output meaning; 9x9 default remains 162 to 96 to 3 | Preserved topology. Current mapping quantizes weights/activations and approximates output arithmetic, so values and choices can differ. |
| Trained weights | Some loaders accepted incompatible shapes or silently treated centered conductances as raw weights; API defaults were random | Explicit checkpoint identity, input/weight/output conventions, strict compatibility checks and archived-model dropdown | Bug fix and integration. Centering a trained checkpoint correctly can change its answers. Canonical random diagnostics do not establish trained strength. |
| CAM selection | Event engine traverses Python child lists while billing a CAM-like delay; separate board-hash transposition helper is not on that active path | Finite parent-ID to child-ID cache with authoritative SRAM backing, whole-list FIFO eviction and ordered match extraction | Explicit microarchitecture choice. It completes one reading of child-discovery intent; it is not equivalent to board-state transposition merging or a fully resident board-pattern CAM. |
| Tree and scratch storage | Logical node/child records, boards in Python objects, and disconnected or incompatible path/statistics/SRAM helpers | Bounded SRAM allocation for metadata, packed boards, path, candidate data, cache headers and neural intermediates; overflow stops the run | Necessary completeness work plus layout choices. Legacy buffer concepts were reused. Four-byte child pointers follow the old helper, whereas the supplement says eight-byte entries. |
| Crossbar mapping | Sign/DAC/ADC declarations exist, but the event model executes dense floating-point inference and its cost shape/schedule are incomplete | Differential bit slices, explicit layer boundary, hidden storage and serial conversions; 9x9 maps to four 256x128 physical arrays | Concrete mapping choices. The two mathematical layers remain; four physical tiles are not four neural layers. Geometry, active-row grouping and sharing are not uniquely established by the old code. |
| Arithmetic and randomness | Python/NumPy floating point and process-global randomness; several legacy RTL arithmetic blocks are incomplete or wrong | Local reproducible seeds; complete core uses Q17 values/Q32 UCB and xorshift32 modulo child selection | Reproducibility is a repair. Finite precision and generator replacement are explicit implementation changes: identical integer seeds need not produce old trees. Modulo choice has a small finite-word bias. |
| Latency and parallelism | Phase constants, incomplete transfer accounting, fractional-cycle truncation and nominal CAM/neural delays | Complete serialized service/RTL phase equations, one UCB lane, explicit transfers and converter sharing | Rounding/missing-work corrections plus a chosen serial architecture. The 225-cycle UCB service is one implementation, not a proof that the original concept inherently requires it. No pipeline overlap was added by the studio. |
| FSM technology | Written design specifies TCAM match plus next-state RAM; old helpers contain optional imports, with no working TCAM implementation recovered on the active path | Synthesized digital FSM/orchestration and routing glue | Functionally sequences the same phases, but is not a demonstrated TCAM FSM. This is an unresolved physical-design gap relative to the written architecture. |
| Expansion/backprop RTL | Existing detector, path and update concepts have address/completion/compile/arithmetic defects; record views disagree | Checked digital modules, explicit packed formats, correct fractional accumulation and finite-count guards; expansion/backprop share an owner | Repairs plus an integrated implementation. Error-on-overflow differs from the paper's saturation wording. Node arithmetic is digital with SRAM read/write, not a characterized compute-inside-SRAM macro. |
| Buffers | Path and child-statistics buffers already existed in the old design; array drive remains active through conversion groups | Existing staging is represented explicitly. Optional analog column holding is a separate readout configuration | Baseline completeness and a separate added variant. Column holding must not silently redefine the sustained-drive baseline. |
| Area, energy and power | Mixed table versions and source conditions; incomplete accounting and inconsistent process scaling | Compatible module reports, native22 CACTI, workbook cells, analog proxies and a single ownership ledger with documented conversion | Accounting repairs and new estimates. Different numerical totals do not by themselves mean a different algorithm. Absolute physical accuracy remains unvalidated. |
| System boundary and sizes | Files describe multiple sizes and tiled systems, but the active path models one search with incomplete interfaces | Complete core supports 2x2, 3x3, 5x5 and 9x9 with fixed SRAM macros; Go legality and host programming/I/O are outside timed core | Explicit narrowed validation boundary. It does not establish larger-board, multicore or end-to-end chip claims. |
| Studio and result identity | Scattered outputs and ambiguous labels; no current integrated live studio | One run identity and ledger feed board play, tree growth, architecture activity, timeline and exports | Presentation and reproducibility improvements. Animation speed does not change model cycles; generic MCTS/rule sources and benchmark artifacts remain preserved. |

## Confirmed Go regression

The baseline event implementation and current complete placement implementation
store each node's accumulated value for the player who is about to move there.
Selection correctly takes one minus the child's mean value to evaluate the
parent's outcome.

The Go adapter introduced at 5fd8367 changes backpropagation to store the
previous mover's value. It still inherits Selection and the UCB function that
subtracts that value from one. That additional reversal prefers the worse
outcome for the selecting parent when exploration terms are equal.

The controlled example supplies exact outcomes, so neural noise or quantization
cannot explain it. Both children have one visit and the root has two:

| Parent to move | Child 1 supplied outcome | Child 2 supplied outcome | Intended choice | Current Go choice |
|---|---|---|---|---|
| Black | Black wins | White wins | Child 1 | Child 2 |
| White | Black wins | White wins | Child 2 | Child 1 |

Fresh probes cover both colors, both child orders, and exploration 0 and 1.414.
All eight Go cases reverse the objective. All eight original-event controls
and four current-placement controls select the intended outcome. These are
synthetic stored-outcome probes, not completed games or a win-rate measurement.

The existing Go regression test checks that the child stores the previous
mover's value. It does not check the subsequent Selection decision, so it
asserts one side of an inconsistent contract. The Round 15 prose similarly
claims the parent maximizes its outcome without verifying the coupling.
Those historical statements need correction when the bug is repaired.

Recommended minimal repair: restore the same player-to-move storage convention
used by the original event and current placement scorer, then check both colors,
terminal overrides, root move/value reporting and studio exports together.
Account for every consumer of the Go convention before changing it. Version
new Go result identities and retain historical games. No need to redesign MCTS,
replace CAM/CIM, resynthesize RTL or rerun CPU/GPU benchmarks for this correction.
No production fix was applied during this comparison.

## What the evidence does and does not establish

Fresh evidence is in [run_20260912_042804Z](p00_runs/run_20260912_042804Z/evidence.json).
The probe extracts the exact original event method bodies from the independent
checkout's baseline Git objects. It uses untimed scaffolding for their event
interfaces and the actual current packed memory, backpropagation and selection
methods for current profiles. It never executes or edits the original project
in place. The original generic MCTS engine and underlying Go rule engine are
byte-identical to their preserved-release versions.

Reproduce from the repair checkout:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=. /Users/tmolomochir/miniforge3/bin/python -B p03_experiments/p40_old_vs_repaired/compare.py
```

The script writes a fresh small UTC evidence folder. A successful process exit
means the described counterexamples and controls were reproduced, not that Go
correctness passed. No full search, game, benchmark, synthesis or full test
suite was rerun. Production source hashes and the extracted baseline bodies
are retained. Analog physics and trained playing strength are outside this test.

Historical evidence, inspected rather than rerun:

- [Budget repair](../p00_iteration_budget/README.md) and commit 6f9fcde: requested budget reaches controller and completed counts are checked.
- [Evaluator contract](../p01_evaluator_contract/README.md) and [strict loading](../p02_evaluator_loading/README.md): incompatible generations and corrected interpretation.
- [Accounting correction](../p03_hardware_accounting/README.md): same tree/weights under the rounding and accounting fixes.
- [Memory comparison](../p06_tree_memory/p00_runs/run_20260909_011941Z/checks.json): three before/after tree and evaluator identities agree at that checkpoint.
- [Mapped neural comparison](../p07_neural_mapping/README.md): numerical error is measured; mapped search is not claimed identical to floating point.
- [Mapping source roles](../p07_neural_mapping/p00_runs/run_20260909_020327Z/mapping_sources.json): recovered declarations versus new candidate decisions.
- [Complete core](../p12_complete_core/README.md): digital RTL comparisons and a distinct arithmetic/random policy.
- [Go integration](../p15_workbook_models/README.md): inherited rules and the value-convention change that caused the regression above.
- [Readout variants](../p17_analog_readout/README.md): optional column holding kept separate from sustained drive.
- [Simple power](../p34_simple_power/README.md) and [component costs](../p35_component_ppa/README.md): current sources, ownership and estimation limits.

Current code anchors:

- [Complete placement stages](../../core/architecture/iteration_model.py), [UCB convention](../../core/architecture/ucb_arithmetic.py), [Go override](../../core/architecture/go_simulation.py).
- [Finite memory](../../core/simulator/tree_memory.py), [neural mapping provenance](../../core/architecture/neural_mapping.py), [FSM inventory](../../core/architecture/component_inventory.py).
- [Complete-core contract](../../core/architecture/COMPLETE_CORE_SPEC.md) and [current PPA contract](../../core/architecture/COMPONENT_PPA_SPEC.md). The former's old PPA paragraph is stale; use the latter for adopted costs.

## Decision and next move

Keep the existing repair and preserved original. Correct the Go value coupling
first, with an end-to-end selection regression and checks of its value consumers.
Then reconcile the TCAM FSM and CAM organization with the intended original
design before claiming full architectural fidelity. Keep existing mapping,
precision, randomness and serial-resource choices visible as implementation
assumptions. No broader optimization campaign follows from this comparison.
