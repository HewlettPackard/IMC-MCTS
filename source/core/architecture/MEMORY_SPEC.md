# Single-core tree-memory contract

Rounds 7–9, 2026-09-09 UTC. Implemented by
[`TreeMemory`](../simulator/tree_memory.py) and used by
`Accelerator.analyze('simulate')`. Model: `parent_link_cache_serial_v1`.
The [experiment report](../../p03_experiments/p06_tree_memory/README.md)
contains source snapshots, tests, and before/after diagnostics.

Round 9 adds optional native 22 nm CACTI HP/LSTP profiles for the mapped 9x9
candidate. The physical pools are three 512 KiB node macros plus one 512 KiB
child macro, with two serialized cycles per 32-bit word (one tool-derived
macro cycle plus one assumed routing cycle). The existing partitions and
default memory profile are unchanged. Partial SRAM costs appear separately in
`accounting.sram`; full-chip costs remain unavailable. See [SRAM_SPEC.md](SRAM_SPEC.md).

This bounded, serialized service model resolves allocation, traffic, ordering,
and completion. Round 8 optionally adds [neural scratch and execution](NEURAL_SPEC.md)
with `neural_mode='mapped'`. Service times and physical costs remain uncalibrated. It does
not establish clock closure, a synthesized memory subsystem, or complete PPA.

## Computation and allocation

The named policy is `evaluate_root_then_expand_all_placement_v1`. An unvisited
leaf is evaluated first. On a later visit, a leaf expands every empty cell in
row-major order, then evaluates one randomly selected new child. Selection
preserves the existing UCB1 computation, tie order, and first-unvisited-child
priority. Full boards create no children. Values and UCB arithmetic remain
binary64 to preserve the functional reference. No fixed-point or one-cycle
binary64 hardware implementation is claimed.

This is an empty-cell placement diagnostic with seeded random weights. Full Go
legality, captures, ko, terminal scoring, and a trained paper case are absent.
State transpositions are not merged. Every nonroot node has one parent, and
child lists are allocated once. Node IDs are consecutive u32 values independent
of board coordinates. Root ID zero is valid.

Each expansion checks node slots, child-pointer slots, and selected-path room
before allocating any children. Capacity failure propagates through the event
engine and cannot return successful metrics for partial work. There is no
spill, resizing, recycling, or dropped-child policy. Earlier phases may have
completed before failure; the error does not roll back the entire run.

## Record layout and physical homes

Node metadata is little-endian `<IdIIHH`, 24 bytes. Binary64 values reuse the
old padding word. This changes the field layout and is not binary-compatible
with every archived helper or RTL record.

| Byte offset | Field | Representation |
| --- | --- | --- |
| 0 | Visits | u32 |
| 4 | Accumulated value | f64, two 32-bit words |
| 12 | Parent node ID | u32; `0xffffffff` means no parent |
| 16 | Child-pool start | u32 index into child SRAM; sentinel before attachment |
| 20 | Child count | u16 |
| 22 | Flags | bit 0 is white to move; bits 1 through 15 give a cache-header slot |

A cache-header slot is usable only after a CAM hit. Stale flags after eviction
cannot imply residency. Statistics are decoded from packed SRAM. The host node
dictionary remains as an observation mirror.

Each board follows its metadata. Cells use two bits, row-major, least
significant cell first: 0 empty, 1 black, 2 white; 3 invalid. Zero padding aligns
boards to four bytes. For N×N, `board_bytes = 4 * ceil(ceil(2*N*N/8)/4)` and
`node_stride = 24 + board_bytes`. A 9x9 board uses 24 aligned bytes, so a node
and board use 48 bytes. Extra rules state is not included.

Node SRAM contains these non-overlapping regions in order:

| Region | Size | Purpose |
| --- | --- | --- |
| Selected path | `4 * (N*N+1)` bytes | Root through deepest placement leaf; pushed during selection/expansion, popped during backpropagation |
| Working board | `board_bytes` | Expansion and neural-input staging |
| Candidate statistics | 16 bytes | u32 child ID, u32 visits, f64 value, one candidate at a time |
| CAM group headers | `16 * cam_entries` bytes | Four u32 fields: parent ID, first physical row, child count, valid |
| Neural scratch, mapped mode only | `align4(hidden_size) + 16,416` bytes | Hidden values, logits, probabilities, output value, and exponential LUT |
| Node and board slots | Remaining SRAM, rounded down to complete strides | `node_base + node_id * node_stride` |

Child SRAM stores authoritative contiguous u32 child IDs, four bytes per edge.
Lists are immutable after attachment. Child statistics reside in node SRAM.
Scratch and boards consume existing capacity; no SRAM macro is silently added.

The legacy 9x9 profile has 1,572,864 bytes of node SRAM, 524,288 bytes of child
SRAM, and 1,024 CAM rows of 512 bits. Reference-mode scratch reserves 16,752 bytes, leaving
32,419 node slots, 131,072 edge slots, and 82 path IDs. These derive from the
legacy profile, not newly characterized macros. Different board sizes still
select different legacy physical profiles.

Mapped mode reserves another 16,512 neural bytes for 9x9. Node slots start at
33,264 and capacity becomes 32,075. The child/path capacities remain unchanged.
The LUT is physically present in the backing SRAM bytes; 4,097 initialization
word writes are billed once per run. Its external source/preload interface
remains unmodeled. All neural intermediate reads and writes use this reserved
partition. Per-inference word counts and cycles join the shared memory totals.

## CAM cache and ordered output

CAM caches parent-key child links. A logical row holds parent ID, child ID,
and validity, at least 65 bits. The physical reference stays 512 bits per row;
unused bits do not reduce its reported area. Child SRAM remains authoritative
when the tree exceeds CAM capacity.

Whole parent lists are cached and evicted in FIFO insertion order. Hits do
not promote groups. Rows follow a circular sequence; first-row/count headers
preserve child order when a list wraps. A complete list must fit in CAM.

Each nonempty lookup bills:

1. Exact parent-key CAM search.
2. On a miss: eviction-header reads, row invalidations, child-pointer reads,
   row fills, header write, parent flag-word update, and another CAM search.
3. A four-word header read and serialized child-ID output in list order.
4. For each examined candidate: metadata read, scratch write/read, and UCB
   evaluation. Unvisited candidates return before UCB arithmetic; the full
   CAM match list has already been emitted in this baseline.

The bounded Python cache represents CAM behavior and FIFO controller state.
Match extraction, circular-order logic, free-list/head/tail registers,
validity reset, and control circuits still need RTL and cost evidence.

## Transactions and service assumptions

One iteration is in flight. Each SRAM has one 32-bit port; UCB uses one lane.
All transactions are serialized, including across SRAMs and compute resources.
There is no pipelining, banking, overlap, or asynchronous request queue. This
baseline does not establish that overlap is impossible or that it is optimal.

| Service | 9x9 cycles | Source and status |
| --- | --- | --- |
| SRAM word read/write | 1 | `ceil(sram_access_delay_ns / 2)`; per-word interpretation is an uncalibrated assumption |
| CAM search | 1 | `ceil(cam_lookup_delay_ns / 2)`; uncalibrated legacy delay |
| CAM row fill/invalidate | 1 | SRAM-delay proxy, uncalibrated |
| CAM child-ID output | 1 per ID | New serialized 32-bit output assumption, not characterized encoder timing |
| Visited-candidate UCB | 1 | `ceil(selection_delay_ns / 2)` per candidate; no matching synthesized binary64 implementation |
| Empty-position scan / child construction | 1 each | `ceil(expansion_delay_ns / 2)`; parallel scan and per-child construction assumed |
| Statistics arithmetic | 1 per node | `ceil(backprop_delay_ns / 2)`; transfers charged separately |
| Neural computation, reference mode | 7 | Legacy rounded 14 ns aggregate, unresolved; board transfers are additional |
| Neural computation, mapped mode | 24,814 | Complete 9x9 integer service template; uncalibrated; board fetch/init are additional |
| Inter-phase controller | 1 per transition, four per iteration | Existing rounded FSM delay; completion handling adds no fifth cycle |

Rounded services have a one-cycle minimum at the sole supported 500 MHz
reference. Original delays are in
[`board_config.py`](../../py_sst_cpp/components/board_config.py); `memory_config`
centralizes the transformation. Each run records this configuration, source
description, and status. No physical constant or node conversion changed.

Initialization bills the root metadata and board write. Board loading bills
source read, scratch write, and scratch read. Expansion reads the working board
for each child, writes its metadata/board and pointer, then commits the parent
list descriptor. Backpropagation bills path pop, six-word metadata read,
arithmetic, and three-word stats write. Candidate scratch incurs four words
written and four read per candidate. A register bypass is a separate design.

Memory effects are applied eagerly within each phase; completion is scheduled
after its recorded operations finish. Consumers cannot execute before that
completion. Intermediate physical visibility and per-word RTL events are not
modeled. The trace is a service schedule, not gate-level or calibrated cycle
accuracy.

## Interface and observations

```python
from core.architecture.accelerator_api import Accelerator

result = Accelerator(
    board_size=9, iterations=200, seed=0,
    capture_memory_trace=True,
).analyze('simulate')
memory = result.simulation['memory']
print(memory['nodes_used'], memory['cam_high_water'])
print(memory['operations'], memory['schedule_sha256'])
transactions = memory['transactions']
```

Optional `memory_limits={'nodes': 82, 'edges': 81, 'path_entries': 2}` imposes
allocation quotas within the physical profile. It changes identity, not SRAM
macro sizes or area. Excessive/invalid quotas are rejected. Analytical mode
rejects nonempty quotas because it does not allocate a tree. Trace capture is
observational and excluded from configuration identity. Large traces require
explicit capture; normal runs retain counters, occupancy, durations, and a hash.

The main Accelerator event API installs this backend. Old direct component
callers without `TreeMemory` retain legacy phase timing. Analytical mode also
remains the legacy phase estimate. Do not combine them under one result label.

## Verification and remaining physical work

The independently counted two-iteration 9x9 case has 12 initialization cycles,
53 for iteration 1, and 1,706 for iteration 2: 1,771 total. It creates 82 nodes
and 81 edges. Warm-cache selection costs 35 cycles for one visited child and
1,315 for 81, including root/leaf access. Tests cover packed state, root zero,
exact fit, overflow, FIFO eviction/refill, wrap order, and propagated errors.

Directed RTL checks repaired sparse-mask completion, root-zero validity,
illegal slices, missing final-word capture, and an unintended setup write.
The old path block remains 32×16-bit, and the SRAM controller uses a four-word
record. Neither implements this full memory contract. Post-acceptance write
backpressure, new-format adapters, cache control, parameterized paths,
arithmetic, synthesis, and timing closure remain open.

Reference-mode energy still equals legacy fixed power times duration.
Its area/power sources remain unchanged and incomplete. Mapped mode withholds
energy, power, and area because its neural geometry has no compatible cost
model. Tree/board/scratch SRAM words and actual CAM/UCB work are counted;
mapped mode also counts internal neural transfers, LUT initialization, and
converter/arithmetic operations. No calibrated activity-based energy is claimed.
Host traffic, weight programming, reset, physical controls, wires, and
idle/leakage still need boundaries and source records. Next: exact CACTI SRAM
configurations, the reconciled 65 nm source to 22 nm digital ledger, and
independent calibration of the new neural geometry.
