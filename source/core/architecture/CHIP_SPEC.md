# IMC-MCTS chip and simulator specification

Rounds 5–12, 2026-09-09 UTC (2026-09-08 local). Target confirmed by the user:
one defensible 22 nm architecture model, configurable experiments, and one
traceable result definition per paper case. The interactive studio follows
validation. [SCOPE.md](../../SCOPE.md) preserves the original and CPU/GPU work.

This document separates requirements and proposed implementation choices from
the current code. It does not certify the legacy costs or select a trained
checkpoint. The [accounting audit](HARDWARE_ACCOUNTING.md) retains the evidence.

Round 7 implements the [single-core memory contract](MEMORY_SPEC.md): packed
node/board storage, bounded scratch and child pointers, a parent-link CAM cache,
and serialized 32-bit transactions. Its service times remain uncalibrated.
The [Round 7 evidence](../../p03_experiments/p06_tree_memory/README.md) supersedes
old event-timing diagnostics while preserving their search computation.

Round 8 adds explicit finite-precision neural execution as the opt-in
`neural_mode='mapped'`. The [neural contract](NEURAL_SPEC.md) specifies both
layers, signed cell slicing, converter sharing, intermediate SRAM, and output
logic. The default `reference` mode retains the prior computation and timing.
Mapped mode has no PPA totals until compatible costs exist for its new geometry.

Round 9 adds opt-in [characterized SRAM profiles](SRAM_SPEC.md) for the mapped
9x9 candidate: three 512 KiB node macros and one 512 KiB child macro, native
22 nm CACTI HP or LSTP. SRAM service timing and partial access/leakage costs
are traceable to raw tool outputs. Routing and the remaining chip costs are
still uncharacterized; no whole-chip PPA is reported for mapped execution.

Rounds 10–11 implement digital primitives and the complete neural controller,
with an opt-in cycle-verified neural schedule. Round 12 adds
[packed selection/cache RTL](SEARCH_RTL_SPEC.md), explicit match/child-ID
buffers and serialized node-SRAM ownership shared with the neural core.
Scoring arithmetic remains external; expansion/backpropagation and complete
iteration RTL remain pending. No new selection timing or physical totals are
adopted by the simulator in Round 12.

## Technology and cost sources

Digital synthesis originated at 65 nm, per the user. The modeled chip target
is 22 nm. A digital cost record must retain its 65 nm source and a single,
explicit conversion to 22 nm. An already converted 22 nm table can instead
serve as a derived input with that conversion in its provenance, but it must
not be converted again. Native-node memory and analog records keep their own
source node and method. Targeting one node does not imply every block was
synthesized or measured at that node.

Each primitive cost record must state source file/hash, component boundary,
source/target node, units, method, voltage/corner/frequency/activity when known,
conversion formula/factors, and status. A fitted/extrapolated row stays labeled
as such. Frequency normalization is separate from technology conversion;
dynamic power and leakage cannot both receive an unexplained frequency factor.

Round 4 found that several digital area numerators match the archived table
already labeled 22 nm, then receive another `/2.5`; rollout uses a different
source family. Power factors also differ. Reconcile the records before changing
totals. The user's clarification settles the intended conversion direction,
not which existing fitted row has the correct numerical history.

Round 9 reconstructs all 102 archived area cells with one `(22/65)^2`
conversion and all 101 available power cells with the recorded global factor.
The latter's voltage/frequency/activity basis is unrecovered. These are fitted
legacy blocks with incompatible or unverified interfaces, so the reconciled
tables remain archival evidence. See the
[cost-source report](../../p03_experiments/p08_cost_sources/README.md).

The current supported timing reference remains 500 MHz (2 ns/cycle). Other
clocks require a supported timing/cost record. A process conversion alone does
not establish timing closure at 500 MHz. Physical accuracy must be reported
against available synthesis/memory/device evidence, with explicit omissions.

## One chip description, one workload description

| Description | Owns | Required behavior |
| --- | --- | --- |
| Chip profile | Target process/clock, array geometry, converters, precision, SRAM/CAM capacities, ports/banks, buffers, interconnect, cost records | Resources are fixed throughout a run. Changing memory size selects a different physical profile and changes its area/accounting. |
| Workload | Application/rules, initial state, evaluator/weights, board/problem size, iterations, exploration policy, seeds | Budget changes the work. It does not silently enlarge the chip. Unsupported mappings must be rejected. |
| Execution | Simulator sources, numerical environment, mode, ordered events, completed work, utilization, overflow/stalls | Time follows dependencies and resource availability. Host runtime stays separate. |
| Result | Area breakdown, activity/idle/leakage energy, modeled time, average power, configuration and execution identity | Totals are computed from one component ledger. Missing costs remain visible. |

The current API still chooses a different legacy hardware table for each board
size. It does not yet implement one maximum-size chip executing arbitrary
smaller problems, nor selectable memory banks. Those abilities require an
explicit mapping, not just another input field.

Round 6 recovered the paper's tiled-chip intent (multiple cores, shared L2,
controllers, and host interface). The active event model resolves one search
system with its phase units. Establish a complete core model before claiming
whole-chip traffic, throughput, or cost. Replication and shared resources need
explicit ownership and contention; setup/weight-programming amortization also
needs a declared result boundary. See the [legacy design review](../../p03_experiments/p05_legacy_design_review/README.md).

Keep analytical and event results distinct. Analytical mode is an estimate;
event mode resolves scheduled operations. Agreement is an internal check, not
evidence that either matches silicon. The current event algorithm uses empty
cell placement, not complete Go legality/capture/ko. Validate application rules
and search behavior against a functional reference before claiming strength.

## Required dataflow and physical owners

```text
root state -> state storage -> selection -> expansion -> neural evaluation
                                   ^                         |
                                   |                         v
                              next iteration <- backpropagation

selection: CAM + node metadata + child pointers + selected-path storage
expansion: source board -> child construction -> state/metadata/pointer writes
evaluation: input staging -> DAC -> array -> ADC -> hidden activation/storage
                         -> DAC -> array -> ADC -> output/value logic
backpropagation: selected path -> node read/modify/write -> commit
```

Start with one search iteration in flight. Each iteration depends on the prior
backpropagation. Intra-phase parallelism must be represented with actual lanes,
ports, and ownership. Pipelining cannot remove dependent layer latency or allow
reuse of a resource before it is free. Broader overlap is a later, tested design
choice, rather than a discount applied to a phase delay.

**Selection contract:** the paper describes parent-ID queries returning
children, while the old CAM helper performs board-hash transposition lookup.
Before Round 7 the active engine directly scanned child lists. Parent-key discovery and
board-state identity are separate operations; define each row/key and returned
payload before assigning CAM capacity or cost. SRAM delivery, UCB lanes and
arithmetic, match extraction, and reduction must follow their actual schedule.
Keep optional transposition merging separate until graph links, edge statistics,
state identity, and capacity behavior are correct.

Round 7 adopts a finite parent-link cache backed by authoritative child SRAM,
whole-list FIFO eviction, ordered match extraction, and one UCB lane. It
preserves the event algorithm as `evaluate_root_then_expand_all_placement_v1`
and binary64 arithmetic as a reference. This resolves the diagnostic contract;
it does not validate Go rules, fixed-point hardware, or the paper's strength.

| Resource to specify or add | Reason and initial implementation direction |
| --- | --- |
| Node metadata SRAM | Existing logical format is 24 bytes/node. Freeze fields, widths, signed value arithmetic, capacity, banking, and ports. Visits/value updates must charge reads and writes. |
| Child-pointer SRAM | Existing logical format is 4 bytes/edge. Allocate contiguous child lists and charge pointer writes and selection reads. |
| Board-state storage | Python stores a board per node, outside the stated metadata format. First model explicit packed snapshots addressed by node ID; compact move-history reconstruction can be a later alternative with its own replay cost. Add rules-specific state when the real workload is integrated. |
| Working-board buffer | Expansion/evaluation need a staged board. Charge its fetch and updates. Generate children in a stream instead of assuming every child can be committed in one cycle. |
| Selected-path buffer | Backpropagation consumes the selected node IDs, including the chosen expansion child. Give this a bounded depth and explicit write/read traffic. |
| Hidden activation and partial-sum storage | The 96 hidden outputs must survive first-layer conversion and be available to layer 2. Size using mapped precision and tiling, not host float64 array bytes. |
| Output/value registers and logic | Own the three logits, normalization/value calculation, and value transfer to backpropagation. |
| CAM occupancy/controller | Specify exactly what a row stores and searches, its update/coherence policy, and misses/eviction. The current 1,024 rows cannot be treated as unlimited tree storage. |
| Transfer/controller state | Give requests owners and completion events. Count bank contention and backpressure. Additional queues or double buffers are justified only by an explicit overlap schedule. |

Round 6 recovery correction: a 32-entry path stack, 49-entry child-address and
statistics staging, packed-board encoding, and SRAM controllers already exist
in the older code. At that checkpoint they were not integrated into the active
event/cost path. The path stack rejected address zero, a write controller could
omit completion for a valid single-write batch, and the 7x7 SRAM interface failed
compilation. Reuse those concepts with explicit repairs, not wholesale imports.
The paper's 8-byte child entry, the helper's 4-byte pointer, and the RTL's
different record views must be reconciled. Tree ID widths follow capacity,
not the number of board cells. These are implementation blockers and format
decisions, not evidence that every resource must be newly designed.

Round 7 repairs those three blocks and checks all nonempty write masks, root
zero, and four-word SRAM reads/writes, including an unintended setup write.
Their legacy 16-bit path and four-word SRAM interfaces still need adaptation;
these directed repairs are not a complete synthesized implementation of the
new memory subsystem. The simulator now partitions node SRAM for bounded path,
board, candidate-statistics, and cache-header scratch, then 24-byte metadata
plus aligned packed-board slots. Child SRAM uses four-byte pointers. Fixed
SRAM macro capacities are retained; capacity quotas do not resize the chip.

For the current 9x9 placement diagnostic, two bits per cell imply
`ceil(2*81/8) = 21` bytes per packed board, before alignment or extra rules state.
Round 7 pads this to 24 bytes per board with four-byte alignment.
It is not a characterized SRAM macro. Hidden
staging requires at least `ceil(96*activation_bits/8)` bytes; tiled partial sums
may need more. Buffer area/leakage must enter the component ledger when their
implementation and cost evidence exist.

Initial memory-model policy: finite on-chip capacity, explicit allocation, and
a clear capacity error if an allocation cannot complete. No unpriced DRAM spill,
automatic resizing, dropped children, or successful metrics for a partial
search. Implement spill only with its transfers, energy, and scheduling.
Counters must include the root and high-water usage. Exact-fit and one-entry
overflow cases provide independent checks. Round 7 implements this policy,
including root/high-water counts, and charges serialized 32-bit transfers
through one port per SRAM without cross-resource overlap. Board storage and
scratch are documented partitions. Configurable banks/overlap remain future work.

## Neural mapping

The current 9x9 evaluator is `162 -> 96 -> 3` with ReLU then softmax/value.
It has 15,840 logical weights. The cost table's `81 -> 96 -> 3` shape cannot
stand in for it. Preserve the floating-point computation as a functional
reference while defining the hardware arithmetic.

Before changing neural PPA, record:

1. Weight representation: sign scheme, effective precision, cells/slices per
   weight, clipping/scaling, and a compatible checkpoint contract.
2. Input/activation precision and encoding, ADC precision/range, accumulation
   width, ReLU/output implementation, and approximation error checks.
3. Array rows/columns and mapping of every logical dimension to space or time,
   row/column tiles, slices, partial sums, and utilization.
4. DAC/ADC banks and sharing, sample/hold where needed, the two dependent layer
   schedules, intermediate storage/transfers, and reuse conflicts.

The recovered supplement already declares differential conductance pairs,
binary (1-bit) DAC inputs, and 8-bit ADCs. Retain these as the intended starting
design, subject to mapping and numerical validation. The missing decisions are
cell precision/slicing, differential readout, hidden arithmetic/encoding, and
physical scheduling. Its simplified two-array drawing does not specify the
intermediate ReLU/conversion path. A multi-bit hidden value driving a binary
DAC needs explicit temporal encoding/accumulation or another defined circuit.
The archived N²×32 `DualCrossbarNN` helper is a different evaluator generation
and cannot supply this two-layer model's weights or costs.

For a digitized intermediate interface, layer conversions cover 162 + 96 input
values and 96 + 3 output values per forward pass. These are logical values;
physical converter counts follow sharing and precision. With A usable ADC
lanes, H outputs alone require at least `ceil(H/A)` conversion groups before
any extra sign/slice/tile work. The phase schedule must expose those groups.
The legacy 14 ns aggregate is not an accepted two-layer schedule.

Round 8 implements and tests the named candidate with 8-bit signed weights,
4-bit cells, differential branches, 8-bit hidden activations, 8-bit ADCs,
16 active rows, and three shared ADC/S&H lanes. Four 256×128 resident arrays
hold the 9x9 network. Its complete serialized inference uses 81 pulses, 4,800
conversions, and 24,814 assumed service cycles. Hidden/output/LUT storage adds
16,512 bytes inside the existing node SRAM. The working example and independent
counts are in [NEURAL_SPEC.md](NEURAL_SPEC.md); numerical errors and exact source
artifacts are in the [Round 8 report](../../p03_experiments/p07_neural_mapping/README.md).
These choices are explicit and opt-in. The default remains the reproducible
reference, and no new energy/area/power ledger is claimed. Analog effects,
physical timing, and trained task validation remain open.

## Consistent results and paper cases

For one chip, area is fixed. Workload activity, tree depth, memory traffic,
precision/mapping, and iteration count determine time and energy. Average
power is integrated energy divided by modeled duration. A constant reference
power is a distinct modeling assumption, not measured workload average power.
Equal board dimensions across applications do not guarantee equal work.

One paper case must resolve to a complete workload/chip definition and one
versioned result artifact. If it represents many initial states/seeds, specify
the dataset and aggregation method once. Application cases retain distinct
identities. Never silently reuse the same short label for different budgets,
weights, modes, source versions, or physical assumptions.

Round 5 implements the first API-level part of this contract:

- `seed=0` by default; child selection and diagnostic weights use local streams.
  Repeating a call or running another case first does not consume its randomness.
- `result.run_identity.configuration` records the actual mode, reference
  hardware fields, initial board/player, rules identifier, budget, exploration
  constant, seed, and evaluator identity. Medium and explicit 5,000 iterations
  on 9x9 are equivalent when their effective settings match.
- `configuration_sha256` identifies those inputs. `execution_sha256` also
  identifies Python source hashes and the recorded numerical environment.
  The source manifest conservatively includes all Python files in `core/` and
  `py_sst_cpp/`; an unrelated file change there may also change this identifier.
- `result.simulation` records completed iterations, cycles, tree size/hash,
  activity, and separate host runtime. The hash of a run does not include its
  wall-clock duration or output location.
- JSON serialization preserves these records beside the numerical results.
  The execution identity is provenance, not a proof of calibration or bitwise
  portability across all numerical environments. Archive the environment and
  validate numerical tolerances for cross-platform replication.

The API is still random-evaluator diagnostic mode. Canonical trained-checkpoint
selection, a paper-case registry, suite aggregation, and routing old application
reporters through this interface remain pending. No paper result is promoted
from this checkpoint's diagnostics.

## Order and acceptance criteria

1. **Repeatable foundation:** local seeds, complete case/version records,
   exact completed-iteration checks, and preserved seed-0 behavior. Round 5.
2. **Selection and memory:** freeze the CAM query and canonical expansion
   policy, physical record layout, finite allocation, board/path buffers,
   port/bank transfer schedule, arithmetic and completion semantics, and stalls.
   Repair the recovered buffer/controller contracts. Hand-check root-zero,
   sparse writes, unique addresses, all SRAM words, one versus many children,
   a two-iteration expansion, and exact-fit/overflow cases. Round 7 implements
   and validates the serialized reference contract; integrated RTL and physical
   calibration remain pending. See [MEMORY_SPEC.md](MEMORY_SPEC.md).
3. **Neural mapping:** signed/precision mapping, both converter stages,
   intermediate storage, activation/output work, and scheduled dependencies.
   Compare numerical inference against the reference and count all operations.
   Round 8 implements and validates the ideal integer serial candidate. Physical
   calibration and application accuracy remain pending.
4. **22 nm cost ledger:** reconcile digital source/conversion records and
   obtain compatible memory/peripheral costs. Sum disjoint area and
   activity/idle/leakage energy. Report calibration error and missing evidence.
5. **Workload validation and publication runs:** integrate validated task rules
   and chosen weights, define case IDs/seeds/aggregation, regenerate only
   simulator outputs, then migrate reporters to one result registry.
6. **Organization and studio:** move code with verified imports/provenance and
   preserve frozen artifacts byte-for-byte; the later studio consumes the same
   simulator interface, event stream, configurations, and cost ledger.

Steps 2 and 3 establish resource counts and scheduling before step 4 assigns
physical totals. Organization can accompany stable module boundaries; it must
not create another calculation path. A full sweep is useful after these checks,
not as a substitute for them.
