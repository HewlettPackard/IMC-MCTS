# IMC-MCTS Studio

The studio follows one search through the board, growing tree and architecture.
The main controls are board size, iterations per move, rollout model and
opponent. **Advanced** contains the seed, exploration, saved cases, game rules
and hardware settings. The interface and renderer run locally without external
browser dependencies.

## Current architecture is the default

Studio follows the architecture declared by `core/architecture/studio_current.py`, backed by `parallel_datapath.json`. It runs `SizedParallelDatapathGoSimulation`, not the earlier reference engine: 16 UCB scorers and two candidate banks; two custom 8-bit 1T1M arrays (163 × 96 and 96 × 3) with offset correction; 32 shared 12-bit ADCs, two digital result banks, a 128-bit bus and eight accumulator lanes. The 9x9 reference installs 2 MiB SRAM and 1,024 CAM entries; the approved table below sets memory for other boards. The first array has 2N²+1 rows at board size N; the second stays 96 × 3.

This implementation supports boards 2, 3, 5, 9, 13 and 19 with the same parallel schedule. Trained Go-strong and Go-weak are available at 9x9; seeded random weights support hardware diagnostics at every approved size. All 18 budget cases completed in Round 93; see `p03_experiments/p93_optimized_scaling/MORNING_HANDOFF.md`. The current-profile controls reject unsupported board, memory and readout combinations. Advanced → Architecture exposes the explicitly historical reference/scaling profile. Saved runs retain their original identities. No earlier result is relabeled as current.

Execution, Dataflow, Area & parts, live timeline, costs and exports use the same selected profile. The current execution profile remains `ucb16_adc32_buffered_v2`; its adopted cost profile is `ucb16_adc32_buffered_estimate_v6`. The selector wrapper, sixteen disjoint UCB lanes and connected digital readout now use the retained p08 native65 synthesis reports. The selector wrapper excludes its UCB children, so the inclusive selection top is never added as a second owner. Connected readout contains its result banks, staging and accumulation banks. Residual selection/neural control and offset correction remain disclosed engineering allocations. Included children are never billed again.

The reports describe native65 TT, 1 V, 25 °C at a 2 ns constraint. The final `after_resize` selection/readout reports pass their scoped synthesis constraints. Original packet acceptance remains `UNVERIFIED`, with the selection `driver_resize.svf` missing; original-RTL/full-design equivalence remains `UNVERIFIED`. Area is cell area, scaled once to the target node. Connected digital dynamic power is preliminary vectorless power, charged over actual elapsed time in the explicit `all_elapsed_vectorless` scenario. Equal default active/idle values do not establish an idle-clock split or workload switching. Dynamic-energy conversion and native65 leakage remain separate assumptions. Full-core physical timing, analog precision and host Go rules/interfaces remain outside this evidence.

Retained components still use the source-linked cost method and current operation census. Partial phases and multi-move sessions are priced from their own work; saved whole-search energy is not rescaled. Source identities and snapshots include the connected characterization, raw adopted reports and bound RTL. Health, previews, editable defaults, component tables, area views and exports identify the same cost profile and source digest. Saved v5 results retain their original costs and are labeled as historical costs even when their execution architecture is still current. Supported 13x13/19x19 diagnostic configurations display their available cost charts.

**Project rule:** update Studio together with each architecture revision. Keep one explicit current-profile declaration, test engine/inventory/cost consistency, and label historical modes. See root `AGENTS.md`.

Historical scaling searches use **single-child expansion** with board-dependent CAM,
node SRAM and child SRAM from the approved Supplementary Table S1 settings.
The same hardware table controls preview, allocation, presets and exports.
The first iteration evaluates the root; each later expansion selects one
untried legal move. Selection returns to partially expanded parents until all
legal moves have children. Remaining-action bitmaps and linked child records
are stored and charged. See [the execution contract](../core/architecture/SINGLE_CHILD_SPEC.md).

Saved cases explicitly retain legacy full expansion. Their profiles and old
results remain separate. A memory-limited search saves its actual completed
iterations and reason; a game places the best evaluated root move and stops.
If no root move has been evaluated, the game reports that no move was placed.
Memory-limited records are excluded from complete-budget canonical snapshots.
In historical profiles, changed selection/update/FSM costs follow their preserved coverage;
new control timing is an architectural service model, not an RTL timing proof.

In the explicitly selected historical scaling profile, selecting a board installs its memory configuration and iteration presets:

| Board | CAM entries | Node SRAM (KiB) | Child SRAM (KiB) | Low | Medium | High |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2x2 | 128 | 192 | 64 | 50 | 200 | 400 |
| 3x3 | 256 | 384 | 128 | 75 | 500 | 1,000 |
| 5x5 | 512 | 768 | 256 | 100 | 1,000 | 2,000 |
| 9x9 | 1,024 | 1,536 | 512 | 500 | 5,000 | 10,000 |
| 13x13 | 1,536 | 2,048 | 1,024 | 1,000 | 7,500 | 15,000 |
| 19x19 | 2,048 | 3,584 | 1,024 | 2,000 | 10,000 | 20,000 |

Changing board size retains the selected tier. Reloading a session or loading
a saved case preserves its exact budget, including older non-preset budgets.
All six sizes can run with seeded diagnostic weights; the playable paper
models require 9x9 Go. Go reserves its full move-bound path within node SRAM.
The high presets all completed for the tested empty-board, seed-0 diagnostic
searches. This checks modeled capacity, not playing strength or physical closure.

The historical Round 81 update added native-22-nm CACTI evidence for smaller SRAM banks and a
2048-row CAM proxy (also used as a padded estimate for 1536 logical rows).
Matching cost profiles follow installed bank sizes and counts. Digital parts
without a matching report remain explicitly excluded from known totals.
At Round 81, Studio used the reference serial scorer and differential rollout;
the separate optimized four-scorer/eight-ADC/two-array figure model used
the same sizing table. See [Round 81 evidence](../p03_experiments/p81_board_sizing/README.md).

From the independent repair checkout:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/tmolomochir/miniforge3/bin/python -B -m p05_studio.p00_app.server --port 4784
```

Open http://127.0.0.1:4784. The server binds to this computer only; `--port`
selects a different port. Browser reload reconnects to the current session
while the server remains running.

Restart the Studio process after installing a cost revision. Program and preview
caches include the cost profile and source identity. Existing saved searches and
sessions remain immutable and keep their original ledgers and source snapshots.

Round 54 runs in a fresh process on 4784; the older processes remain intact.
It reduces host execution overhead without changing the modeled search.
Rollout animation groups reuse the fixed schedule, while LUT addresses remain
input dependent. Live PPA uses a per-job inventory and power table validated
against the original reports at setup. Every response prices one captured
snapshot outside the search/control lock. A different hardware configuration
cannot reuse that prepared inventory. Final saved results still rebuild costs
and check source identities through the result registry.

Host wall time includes simulation, display and file writing. It is separate
from modeled chip latency. Performance evidence and exact before/after checks
are in `p03_experiments/p54_performance/README.md`.

Changing workload settings after a run clears its displayed metrics, export
links, tree and pipeline, and returns the page to a configuration preview.
The saved run remains in the results history. Editing the initial board
preserves the stones you enter; **New game** clears them. Playback settings
do not invalidate a completed result. A failed run's explanation remains
visible through speed changes and reconnects until a new configuration or
run replaces it.

Round 42 runs from `p03_reference_repair`; the old checkout's game on 4782
and server on 4781 remain intact. Advanced > Saved case includes the trained
9x9 Go/H96/5000 reference. The Verified reference results table reads the same
immutable CSV as its download. Go values now use the player-to-move convention;
displayed Black values are checked for both playing colors. Original TCAM
control remains a documented gap in the current digital implementation.

The component table groups parts under Selection, Expansion, Rollout,
Backprop, FSM and Shared memory, with External below them. Each group and
part has its own dropdown. Show all parts opens the full inventory, including
SRAM cell arrays, decoders, drivers, read/write circuits and wiring. Expansion
and Backprop share a controller, whose cost appears once under Expansion.
The regrouping leaves the cost ledger and CSV unchanged.

The Rollout model menu contains ten paper entries. **Go-strong** and **Go-weak**
are selectable for 9x9 Go. Connect Four, Othello, Hex, Go (the separate
cross-domain example), FrozenLake, MiniGrid, HP Protein Fold and Minesweeper
remain visible but disabled because their specific model files are unrecovered.
The two playable models preserve all 163 inputs, including Black to play.
Older models and diagnostics remain attached to their saved cases; restoring
one does not silently substitute a paper model. Computer opponents use the
same input layout so session totals describe one chip configuration.

## Play and inspect

- **IMC-MCTS plays as** selects Black or White against a human or computer
  opponent. Black is the default and opens a fresh game. Choose White to let
  the opponent open; **Me** then means you play Black. The choice locks during
  the game and survives a browser reload. Self-play uses both colors and
  disables this selector, as does **Explore one position**.
- **One move** runs and commits one engine move, then waits. Press it again to
  continue the same game, preserving its board, turn, captures, ko and passes.
- **Until game ends** keeps playing. Against **Me**, the engine plays your
  selected architecture color and waits for your legal move on the other side.
  Click the played board or use **Pass** in Go, including the opening Black
  turn when the architecture plays White.
- **Itself** uses the same model and search settings on both sides.
  **Computer · MCTS** uses our engine with its own model, budget and seed.
- **Save & end session** finishes a stopped prefix and enables the aggregate
  exports. **Stop** cancels active work, retaining committed moves and failed
  or cancelled search evidence. **New game** stops an active job and clears the
  display before another configuration is started.
- **Explore one position**, under Advanced, runs a single decision budget
  without permanently placing its trial positions on the played board.

Go uses the existing legacy rules: captures, suicide prevention, simple ko,
passing, Chinese area scoring and the existing move cap. Empty-cell placement
remains available for diagnostics and is preserved in named placement cases.
Model choices use hashed checkpoint files and explicit compatibility checks.
The new turn-aware mapping has software checks, but no matching 163-input
neural-controller synthesis report. That controller's area and power are
excluded from known totals; existing component coefficients are unchanged.
Playing strength has not been remeasured. See the
[model implementation and evidence](../p03_experiments/p45_studio_paper_models/README.md).

## One playback timeline

**Live breakdown**, immediately below the pipeline, contains four pie charts:
installed area, accumulated energy, average power and simulated latency.
Area is available in the configuration preview and remains fixed during a
run. The other charts update with live activity and aggregate across moves
in a game. Reload restores the current totals; New game clears old activity.

Area, energy and power sum the same parent components as the result ledger.
Shared hardware is counted once, so Expansion and Backprop share one cost
slice. Nested inventory rows are already included in their parent. Unestimated
parts remain labeled as missing; slice percentages describe the known subtotal.
The power chart uses each component's energy divided by the same simulated
elapsed time, so its percentages match the energy chart.

Latency slices use exclusive search-stage cycles at the existing assumed
500 MHz clock. Memory work is already included in the stages. FSM finish
shows only the final cycle of each iteration; other control remains within
its stage. Hover or focus a legend entry to highlight a slice. Charts arrange
as four columns, two columns or one column as available screen width changes.
See [Round 46 validation](../p03_experiments/p46_presets_charts/README.md).

**Pipeline · cycle timeline**, below Tree growth, shows cycle intervals for
Selection, Expansion, Rollout, Backprop, FSM and Shared memory. Expand a group
or choose **Show parts** to reveal the same functional units as the architecture
diagram. Click a bar for its operation and start/end cycles; click a part name
for its internal pieces. **Fit**, zoom, drag/arrow-key pan, **Follow**, iteration
selection and **Enlarge** control this view. Pause, Step and the global speed
slider remain the only playback clock.

Stage boundaries match the simulator's phase events. Parts show ordered service
intervals; control gaps are grouped at stage end. The local neural schedule is
reused once per program, with its outer-controller remainder shown separately
at the end of Rollout. These service positions are not exact internal RTL
waveforms or electrical active-time intervals. Helpers without separate
service timing are marked as included in their parent, and the stage envelopes
already include the shared memory work shown below. Do not add row lengths
together. Striped control time stays in its owning stage; the source trace
does not split it among the global FSM and local controllers. The FSM row
shows the one-cycle finish, with other control already included in stage
totals. Expansion and Backprop still share one tree-update instance.

The timeline retains the latest 12 iterations of the current computer search
in memory and resynchronizes after missed polls or reload. Each new search
starts at cycle zero. Saved per-search latency and cycle summaries are
unchanged; there are no per-cycle trace files or extra waveform dumps.
Tree-history selection is independent of this current-search timeline.

In Tree growth, **Node > Inspect** shows an inline error for a missing or
invalid ID and clears the previous node's board and statistics. Branch actions
are disabled until a valid node is selected. **Root**, **Follow search** or
another valid ID restores the inspector. See the
[node lookup regression](../p03_experiments/p48_node_lookup/README.md).

The global speed slider controls phase/group presentation and the pause between
moves. **Pause** freezes playback; **Step** advances a phase at fast settings
or a counted activity group in detailed mode. Pacing never changes simulated
cycles, random choices, activity counters or cost calculations.

The diagram uses **Selection, Expansion, Rollout, Backprop and FSM**, with
shared memory alongside them. Click a functional unit, then open its internal
groups for buffers, counters and arithmetic details, or choose **Enlarge**.
This is the main functional hierarchy, not an exhaustive gate/transistor
inventory. **Programmed crossbars** displays
the actual selected model's cell codes. The displayed program is bound to the
same model key as its snapshot, including when opponents change weights.
Optional column holding appears only as an installed resource in its selected
readout profile. Expansion and backpropagation share one tree-update module;
SRAM scratch regions are not additional physical memory blocks. Rollout uses
the existing neural value estimate. **FSM finish** takes four cycles in the single-child profile (commit plus
three memory-budget checks), and one cycle in preserved legacy profiles. The global FSM also controls the other stages;
their control time is already included in their phase totals.

Activity comes from the simulator's ordered memory-service records and resolved
neural schedule. Repeated work is grouped by operation and layer in first-use
order. The tree, board and cost counters describe the completed phase whose
activity is displayed. These are modeled service groups, not internal pin
waveforms or exact positions of aggregated controller gaps. At fast speeds,
intermediate drawing is summarized; a bounded delta history and full checkpoint
fallback preserve all tree nodes and their latest statistics.

## Tree growth

Every node is a small board with its visits and player-labeled value sum.
The sum uses the player to move at that node. The inspector also displays the
Black mean: sum/visits at Black nodes, or 1-sum/visits at White nodes.
Unvisited nodes have no mean. Live and archived trees use absolute board colors.
Children appear on
expansion and statistics update after Backprop. All allocated children are
included automatically, with no nine-child paging or placeholder nodes.
Drag to pan, scroll or use the buttons to zoom, and click a board to inspect it.
The Node field also supports direct keyboard selection and centers that board.
**Root** returns to the starting position, **Overview** fits the entire tree,
and **Follow search** tracks the selected node. **Enlarge** uses more screen
space. Large trees are wide; zoom in from Overview to read individual boards.

Branches may be collapsed manually and **Show all branches** opens them again.
The layout retains every visible branch; only boards outside the viewport are
skipped during drawing. Spacing is computed per depth so a large descendant
subtree does not spread the root's immediate children far apart.

Each move starts a fresh tree, matching the simulator's existing policy.
The move selector can inspect a completed search tree from its verified saved
artifact; **Current search** returns to the live view. A hypothetical node
never commits a stone to the played board.

## Results and evidence

Single-position records are saved in `p04_results/p01_runs/`. Game sessions use
`p04_results/p02_plays/run_.../`, with every engine search under `p01_searches/`,
plus the move list, session policy, source snapshot and aggregate JSON/CSV.
New interactive sessions record `studio_turns_v3`, including `architecture_side`
in session policy, identity and summary CSV. Move CSV includes actor, model,
seed and search budget. Older results preserve their original schema and costs.
Human moves have zero billed
core work. Computer-versus-engine sessions include both sides' simulated searches
on one reused chip and provide per-player totals; they are not CPU benchmarks.

Core time, SRAM accesses and digital activity counters sum the completed engine
searches. Physical area is counted once. Human thinking/input, display pacing,
host game rules, resets/preload and programming remain outside modeled core time.
Source identities and checksums accompany saved search and session evidence.

**Components: area, power and timing** shows installed owners with expandable
subblocks. **Show all parts** opens the entire inventory, including internal
buffers, arithmetic, SRAM regions and analog circuits. Source details stay
collapsed until requested. Area is the row's installed total. Power is its
average contribution over the same search/session. Cycles show active/service
time at 500 MHz; overlapping module times do not sum to chip latency. Included
subblocks are not billed again. Coverage is per column: children of an
unestimated parent show **Excluded** for the missing area/power, while their
timing can still be included in a recorded parent schedule. This also applies
to nested parts and Backprop parts displayed separately from their shared
Expansion owner. Before a search, workload columns say **Run search**.

**Inside one search** and its phase details use only that search's counters.
After placement, they retain the completed computer move's identity and
counters, including while waiting for or committing a human move. Session
results, workload pies and **Where the cycles go** retain cumulative totals.
The next move gets fresh search counters when its search begins.

Round 35 adds CAM and analog proxies plus explicit physical allowances to the
existing SRAM/digital costs. The default 9×9 core has estimates for all 16 cost
owners; smaller configurations still show missing compatible digital reports.
Host I/O and weight programming are visible but excluded, not free. Whole-chip
totals stay unavailable. Digital area receives `(22/65)^2` once and dynamic
energy receives the documented approximation. Native65 leakage remains a
proxy; native22 sources receive no second conversion. Saved older results
retain their original cost model. Start a new search to use the new model.

**Component CSV** exports every nested entry, its owner, included/count flags,
area, average power, cycles, source and model identity. It is available for
new completed searches and sessions, alongside JSON, summary and block-power
exports. Read [the component assumptions](../core/architecture/COMPONENT_PPA_SPEC.md)
and [Round 35 checks](../p03_experiments/p35_component_ppa/README.md).

Current board/hierarchy presentation: [Round 33](../p03_experiments/p33_board_tree/README.md).
Session and synchronization implementation: [Round 32](../p03_experiments/p32_studio_views/README.md).
The design rationale is in [Round 31](../PLAN_ROUND_31.md); the reusable block
model is described in [BLOCK_POWER_SPEC.md](../core/architecture/BLOCK_POWER_SPEC.md).
`p00_app/` owns job control and observations, `p01_static/` owns the interface,
and ignored `p02_runtime/run_.../` folders hold local process logs.
