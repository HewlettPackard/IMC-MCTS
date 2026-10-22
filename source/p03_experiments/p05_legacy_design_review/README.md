# Round 6: previous-code recovery and architecture review

2026-09-09 UTC (2026-09-08 local). Stage: Model. Reviewed the preserved
`legacy/try2` tree (`ab4e80d`), original release (`93b7ba4`), active repair code
(`2d23fd6`), and the submitted manuscript/supplement. This is a bounded design
review, not a complete RTL certification or a new implementation.

## Assessment

Keep the multi-primitive direction: associative lookup, task-specific expansion
logic, stationary neural weights in RRAM, and local tree statistics fit distinct
parts of MCTS. The design's advantage still needs to be demonstrated after
charging the complete data path. The main improvement is a consistent contract
between the algorithm, memories, arithmetic, and schedule. More hardware by
itself will not resolve the current disagreements.

The older version already contains a packed-board encoder, path stack,
child-address/statistics buffers, memory interfaces, and neural mapping helpers.
The previous round's missing-resource list meant missing from the active
simulator and its explicit cost ledger. It should not be read as evidence that
these concepts never existed. Several implementations are useful starting
points but cannot be reconnected unchanged.

## Evidence and reproduction

- [Document record](p00_runs/run_20260909_003326Z/source_documents.json): exact
  original PDF paths/hashes, lossless compressed text extracts, and rendered
  manuscript architecture page. The papers were read, not edited.
- [Probe run](p00_runs/run_20260909_004053Z/metadata.json): source snapshots,
  per-version file hashes, compressed diffs/logs, commands, and tool versions.
  [Python observations](p00_runs/run_20260909_004053Z/python_findings.json) give
  the numerical witnesses without promoting any new PPA values.
- [History search](p00_runs/run_20260909_004053Z/history_search.json): 37 legacy
  commits inspected for a file ending in `tcam_fsm.py`, with no matches. This
  bounded negative does not establish absence of equivalent control logic.
- Reproduce the executable probes from this checkout with
  `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -B -m p03_experiments.p05_legacy_design_review.run`.
  Each invocation writes a fresh UTC run. The original repository is read only
  for version comparison/history; all executed Python/RTL comes from the repair
  copy. The selected legacy bodies differ mainly in headers and naming, as
  recorded in the exact diffs.

The 17 review checks reproduced the expected observations. These are checks
that defects exist, not 17 passing hardware correctness tests. The memory
controller passes Icarus syntax and Verilator lint; its single-write functional
case fails. The path stack passes Icarus syntax, has five unwaived Verilator
warnings, and fails the root-zero compatibility case. The SRAM interface fails
both Icarus and Verilator compilation. No synthesis, timing closure, gate-level
simulation, analog characterization, or CPU/GPU benchmark was performed.

## What to recover

| Existing asset | Evidence | Reuse decision |
| --- | --- | --- |
| Two-bit board packing and Zobrist helpers | `py_sst_cpp/components/common/board_state_encoder.py:32` | Reuse packing after input-convention tests. Replace global RNG seeding and include all task state needed for identity. Hash matches need full-key verification. |
| 24-byte node and 4-byte child-pointer layout | `py_sst_cpp/components/memory_scaling.py:80` | A useful logical starting point. Freeze field semantics, allocator, and actual SRAM interfaces; the helper currently estimates capacity rather than enforcing it. |
| 32-entry, 16-bit path stack | `rtl_synthesis/rtl/path_address_extractor_7x7.sv:8` | Reuse the concept after root-zero, depth, width, reset, and completion repairs. Its multi-cycle operation belongs in the simulator. |
| Child address/statistics staging | `rtl_synthesis/rtl/children_address_gen_7x7.sv:26`, `child_stats_access_7x7.sv:28` | Reuse bounded staging and streaming concepts. Replace address allocation assumptions and connect the SRAM interface. |
| Task abstraction and functional evaluator | `core/algorithm/mcts_engine.py`, `core/architecture/hardware_functional_model.py` | Reuse as reference machinery after choosing one expansion policy, state encoding, and value perspective. |
| Old CAM transposition helper | `py_sst_cpp/components/common/base_components.py:90` | Keep as evidence. Capacity, collisions, state completeness, and DAG updates need repair before optional transposition support. |
| Old `DualCrossbarNN` and cost helper | `py_sst_cpp/components/crossbar_nn.py:46`, `crossbar_hardware.py:35` | Archive as a different model generation. Do not substitute their weights or costs into the current two-layer evaluator. |

## Priority 1: define selection and memory together

The supplement, Note 4.1 (extracted lines 427–451), says CAM rows store board
patterns, a query with the current node ID returns all child addresses, and
SRAM supplies statistics for a single-cycle UCB decision. Those are separate
operations. A board-pattern key does not by itself encode the parent-to-child
relation. Specify parent tags or another explicit index if child discovery is
the intended associative operation.

The old helper instead maps a board hash to one node for transposition lookup.
Searching `core/` and `py_sst_cpp/` found definitions and documentation, but no
executable caller of its lookup/insert/merge methods. The active selection unit
inherits directly from `Component`, scans Python child lists, and bills a
depth-dependent delay (`core/simulator/mcts_sst_components.py:341, 408, 448`).
The probe examines 1 versus 81 visited children on the same two-node path and
charges **2 cycles in both cases**. Constant latency could be justified by
sufficient hardware, but that lane/bank/port organization is absent here.

The recovered RTL also does not establish a single-cycle complete selection:
`child_stats_access_7x7.sv:140` fetches children through a memory FSM, and
`best_child_selector_7x7.sv:73` scans candidates across cycles. CAM match time,
match-address extraction, SRAM delivery, UCB arithmetic, and reduction must
each appear in the schedule. UCB's log, division, square root, quantization,
unvisited-node priority, tie policy, and player perspective need a numerical
contract before assigning their latency.

**Recommendation:** retain parent-key CAM selection as a candidate design and
make it explicit. Keep board-state transposition lookup separate and optional.
Later compare the complete CAM path with the existing contiguous-child-list
SRAM alternative inside the architecture simulator. A key lookup alone is not
the comparison boundary. No CPU/GPU work is required for that comparison.

The memory organization must settle these mismatches:

- The supplement says 8 bytes per child entry; the sizing helper says 4 bytes.
  Node records are 24 bytes in that helper, 128 bits in the 7x7 read interface,
  and only two 16-bit statistics in the 7x7 write controller. Different views
  could be valid, but offsets and ownership are not defined between them.
- `children_address_gen_7x7.sv:38, 58, 69` uses a fixed level offset and a
  four-byte child stride. Under that formula, parent addresses 0 and 4 can
  produce the same child address (indices 1 and 0). This is a source-derived
  alias witness, not an executed RTL test. Use an actual allocator/child-list
  base address instead of a level-offset shortcut.
- `memory_write_controller_7x7.sv:40` only accepts node IDs 0–48. A tree's node
  capacity is not the number of board cells. Address widths must follow the
  configured storage capacity, independently of board dimensions.
- The 9x9 profile has 1,024 CAM rows while the saved Round 5 tree has 6,562
  nodes. It cannot hold one board per tree node without another storage/policy
  decision. Choose a fully resident design or a finite CAM cache with explicit
  backing storage and misses. Do not silently assume the best of both.

Recover the path and statistics buffers; add an explicit working-board buffer
and a physical home for every retained board. Two bits per 9x9 board require
21 packed bytes before alignment, player/rules state, or metadata. Start with
finite on-chip capacity and a visible capacity error. Add external spill only
when its traffic and cost are modeled.

## Priority 2: finish the two-layer neural data path

The paper already specifies differential conductance pairs, binary DAC inputs,
and 8-bit ADCs (supplement Note 4.3, extracted lines 485–506). This corrects the
earlier impression that all precision/sign decisions were unspecified. These
are design declarations, not verified physical cost records.

For 9x9, the intended matrices are **162×96 and 96×3**. The current functional
reference includes a hidden ReLU. The paper's simplified DAC → array 1 → array
2 → ADC drawing does not explain how hidden activations are produced and fed
to the second layer. Two linear arrays alone do not implement the ReLU network.

Recommended digitized boundary, subject to explicit mapping validation:

```text
board buffer -> binary input driver -> differential array 1
             -> conversion / signed and tile accumulation -> ReLU
             -> hidden-activation buffer -> layer-2 input encoding
             -> differential array 2 -> conversion / accumulation
             -> output/value logic -> backpropagation
```

Specify converter sharing, active rows, differential readout, weight precision,
cell slices, partial sums, and both layer schedules. If layer 2 receives a
multi-bit activation through a binary DAC, define its temporal encoding, such
as bit-serial pulses with accumulation, or explicitly choose another circuit.
Do not infer one pulse per activation. An 8-bit ADC specification alone does
not settle hidden precision or the signed/partial-sum datapath.

The archived `DualCrossbarNN` uses one N²×32 conductance matrix and can fall
back entirely to stone counting when untrained (`crossbar_nn.py:247`). It is
not a replacement for the current 162→96→3 evaluator. Its companion cost helper
declares a native 22 nm cell then applies scaling factors referenced to 65 nm
(`crossbar_hardware.py:35–86`), and counts one device per logical weight despite
declaring different cell/weight resolutions. Do not import those totals.

Calibrate the chosen mapping with compatible array/peripheral evidence. The
[official NeuroSim V1.4 documentation](https://github.com/neurosim/DNN_NeuroSim_V1.4)
provides configurable technology, array size, cell precision, ADC precision,
and row parallelism. It is a possible independent estimator after matching
our mapping, not validation of the existing constants. The local NeuroSim path
named by the mentor skill was unavailable in this session; no such run occurred.
Preserve separate array, conversion, accumulation, other peripheral, interconnect,
and buffer costs. Diagnose the observed breakdown rather than force a preset
component to dominate.

## Priority 3: make one algorithm drive the hardware work

The placement probe produced **3 nodes versus 82 nodes after two iterations**:
the generic MCTS engine expands one child at a time; the active event engine
first evaluates the root, then creates all 81 children. This is an expansion
policy difference, not an inference accuracy comparison. Both choices can be
modeled, but a result label must identify which one ran.

The supplement itself needs reconciliation: Note 1.1 describes generating all
legal moves, but Algorithm 1 inserts one random child only after visiting the
leaf. That pseudocode also lacks the generic engine's untried-move handling.
Do not use the printed pseudocode as an executable golden reference without
resolving this difference. This review leaves the current diagnostic behavior
unchanged and records the policy decision before any publication rerun.

Choose one canonical workload definition with real application rules, initial
state, selected checkpoint, value perspective, expansion/tie policies, budget,
and seeds. The architecture simulator should consume those operations through
a clear interface. Keep feedback from hardware arithmetic into the search when
quantization/noise changes values or choices. Replaying a fixed trace is valid
only for variations that preserve the functional trajectory, or as an explicitly
limited timing study.

The CAM probes give further reasons to defer transposition merging: a
one-row declaration accepts two entries; an injected equal hash matches the
wrong board; merging nodes leaves both dangling child and parent links.
Matching must account for side to move and relevant rule history, and sharing
states turns the tree into a graph with explicit edge statistics/update rules.
None of these defects is on the active event selection path today.

## Priority 4: validate one core before claiming a tiled chip

The manuscript's Figure 2 includes tiles, shared L2, controllers, multiple
cores, and a PCIe host interface. The active event model creates one search
system with its four phase units. It does not resolve shared-L2 contention,
inter-core traffic, or host transfers. Define core versus whole-chip boundaries
for latency, area, energy, and setup/programming amortization.

Start with one complete iteration in flight. Verify selection, expansion,
evaluation, and backpropagation dependencies, finite-port contention, and
completion. Multi-core scaling, queues, double buffering, and external memory
become later choices justified by measured simulator bottlenecks. A small
fixed-function controller is also worth comparing with TCAM control internally;
the optional old TCAM import is not a functioning controller implementation.
Do not assign a TCAM benefit merely because its storage appears in a cost table.

## Confirmed RTL reuse blockers

| Finding | Verification | Consequence |
| --- | --- | --- |
| Single-write batch never signals done | `memory_write_controller.sv:87–119`; mask `111` passes, mask `001` writes once but fails completion | Fix completion semantics before event integration. |
| Node zero is reported invalid after a correct stack pop | `path_address_extractor_7x7.sv:184`; address 7 passes, address 0 fails | The active root is node 0. Validity must be independent of address value, or an explicit address adapter must exist. |
| Variable ordinary part-selects do not compile | `node_sram_access_7x7.sv:78, 163`; Icarus and Verilator both reject | Repair RTL before taking its synthesis costs as evidence for this source. |
| Fourth read word is never captured | Same module, `burst_counter < 3` guard at line 77 | Source inspection only: subsequent read-data verification must cover all four words after syntax repair. |
| Child-statistics SRAM ports are disconnected | `child_stats_access_7x7.sv:68–75` | A staging-buffer prototype exists, but there is no working end-to-end SRAM path here. |

## Next implementation and acceptance checks

The next concrete move is a **single-core selection-to-backpropagation memory
contract**, reusing the existing buffer concepts. First freeze the CAM query,
node/edge/state records, ID allocation, path validity, arithmetic semantics,
ports, and request/completion rules. Then implement the bounded model and
relevant RTL repairs in a fresh round.

Acceptance checks: root-zero and sparse-write completion; every SRAM word
transferred; unique allocated addresses; exact-fit and one-entry overflow;
hand-counted one-child versus many-child selection; and a two-iteration
end-to-end operation trace that matches the chosen functional policy. Connect
the explicit neural schedule next, then reconcile the single 65-to-22 nm
conversion and disjoint physical cost ledger.

One paper case resolves to one complete configuration and versioned result.
Different applications on the same chip retain fixed area but can legitimately
have different latency, energy, and average power. Reusing the label “9x9” is
not enough to establish equal work. Canonical case generation and the later
studio should read the same simulator interface and result artifacts.
