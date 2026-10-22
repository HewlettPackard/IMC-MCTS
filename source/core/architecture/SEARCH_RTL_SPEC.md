# Cached selection and shared SRAM RTL

Round 12 implements `imc_cached_selector` and `imc_search_core` in
[`rtl_synthesis/p02_search_control`](../../rtl_synthesis/p02_search_control/).
The reference is the packed [memory contract](MEMORY_SPEC.md), not the legacy
node struct or a second software cache. This is a selection controller with
external UCB arithmetic, plus operation-level integration of the existing
[neural sequencer](NEURAL_RTL_SPEC.md).

The production Python schedules and Round 11 RTL/filelist remain unchanged.
Selection timings measured here use explicit test responders and are not
promoted into the architecture API. Expansion, backpropagation and complete
MCTS iteration control remain to be implemented in this format.

## Storage and ownership

For the mapped 9x9 configuration, the address map is unchanged:

| Node SRAM region | Byte offset | Bytes |
| --- | ---: | ---: |
| Path, up to 82 node IDs | 0 | 328 |
| Working board | 328 | 24 |
| One staged candidate | 352 | 16 |
| 1,024 cache headers | 368 | 16,384 |
| Neural scratch and exponential LUT | 16,752 | 16,512 |
| Packed nodes, 48 bytes each | 33,264 | Remaining 1,539,600 |

Three 512 KiB node banks and one 512 KiB child bank use the existing 32-bit
routers. Packed node capacity is 32,075; child capacity is 131,072 pointers.
Selection reads six metadata words, then writes each selected ID to path SRAM.
The host supplies allocated-node/edge bounds and consumes the returned path
before the next operation. It preloads valid packed topology, statistics,
boards and the neural LUT. Node SRAM persists across controller reset.

Two previously implicit pieces of storage are now real RTL registers:

| Local storage | Capacity formula | 9x9 bits | Role |
| --- | --- | ---: | --- |
| CAM match mask | CAM entries | 1,024 | Retain a search response while reading matched rows |
| Ordered child IDs | 32 x board_size squared | 2,592 | Retain the complete emitted child list before candidate evaluation |
| Shared transfer buffer | Six 32-bit words | 192 | Node metadata, cache headers and staged-candidate transfers |

The first two total 3,616 bits. The 16-byte candidate SRAM stores one child,
so it cannot replace the child-ID buffer without changing the reference
traffic/order. Register costs belong to the selector's synthesized digital
boundary, not CACTI SRAM. Additional state includes FIFO pointers/counters,
latched request limits, current/best scores and IDs, and transfer control.
These allocations are not physical area estimates.

## Selection sequence

1. Latch the start arguments. Read the root metadata, validate limits and push
   its ID to path SRAM. A node with no visits or no children is the leaf.
2. Search the parent-key CAM. On a miss, evict the oldest whole parent lists
   until the new list fits. Read each evicted header and invalidate its rows.
3. Read the authoritative child pointers from child SRAM and fill successive
   circular CAM rows. Write a four-word cache header and the parent's packed
   flag/header-slot word, then search again.
4. On a hit, read/validate its SRAM header. Read all matching CAM rows in list
   order into the child-ID registers. Reject missing/extra matches, invalid
   rows, wrong parents and out-of-range child IDs. Clear each consumed bit.
5. For each candidate, read six metadata words, write four candidate words to
   scratch, and read them back. The first unvisited child wins immediately.
   Otherwise request a UCB score. Strictly greater finite scores replace the
   best candidate, preserving the first child on ties, including signed zero.
6. Read the winning child's metadata, push its ID and continue until a leaf.
   Hold leaf ID, path depth and error until result acceptance.

Cache rows and headers each use FIFO head/tail counters. Lists are contiguous
in circular row order and topology is immutable while cached. Statistics may
change between operations. Changing a cached child list requires coordinated
cache invalidation/reset; the interface does not provide coherent host edits.
Stale header flags after reset/eviction are ignored unless the CAM reports a
hit. A miss always writes a new header and parent flag before use.

## Interfaces and timing

Every request uses valid/ready, is accepted on a rising edge, and holds its
payload until acceptance. At most one request is outstanding per controller.
Responses must arrive after request acceptance and remain valid until ready.
No same-edge combinational response is supported. Completion is also held
under backpressure. Testbenches sample completion on settled clock edges.

| Boundary | Payload and behavior |
| --- | --- |
| Selection start | `root_id`, `nodes_used`, `edges_used`, `path_limit` (32 bits each), binary64 exploration constant |
| Node SRAM | Aligned byte address, 32-bit read/write data, response/error |
| Child SRAM | Aligned byte address, read-only 32-bit child ID, response/error |
| CAM request | Operation 0 search, 1 fill, 2 invalidate, 3 read; row index, parent ID and child ID |
| CAM response | Search match mask, or read parent/child/valid; error applies to all operations |
| Score request | Parent and child visits (32 bits), child accumulated value and exploration constant (binary64 bits) |
| Score response | Finite binary64 score or error |
| Selection result | Leaf ID, path depth, error, poison status |

The score provider must compute the existing child-to-parent value convention:
`1 - child_value/child_visits + C*sqrt(log(parent_visits)/child_visits)`.
It is only called for positive child visits. Division, log and square root
are external dependencies. This controller preserves binary64 transport and
comparison; it does not claim a synthesized UCB arithmetic lane. Fixtures
supply Python-reference answers through that interface. Their three-cycle
unstalled responder is a verification choice, not a hardware cost or estimate.
NaN and infinite values/results are rejected. The command exploration encoding
must be finite with its sign bit clear.

`imc_search_core` grants the entire node router to one operation. Selection
wins simultaneous starts. It retains ownership through accepted completion;
the other operation cannot start during that interval. The next command can
be accepted on the following clock edge. A separate one-bank child router
serves selection. The unchanged neural sequencer owns its existing ADC/array
interfaces only during neural execution. The wrapper does not automatically
invoke inference after selection, or perform expansion/backpropagation.

The physical SRAM-bank interface has no macro-error pin, so its logical error
reports router address/decode failures. Logical selector tests separately
inject node-read, node-write and child-read response failures. Supporting
macro ECC or a new bank-error signal would require an explicit router change.

## Reset and errors

Active-low reset clears controller state, match/child buffers, FIFO counters
and poison. Reset the CAM validity and all outstanding responders together.
SRAM contents are not automatically cleared. A failed operation may have
already written a partial path, cache header or candidate; no rollback is
claimed. The caller discards the failed result and resets/reinitializes the
affected cache/operation before reuse.

| Error | Meaning | Recovery |
| ---: | --- | --- |
| 0 | Completed selection | Accept result |
| 1 | Invalid configuration, bounds or child ID | Invalid start does no work; runtime failure poisons |
| 2 | Node/child SRAM response failure | Coordinated reset |
| 3 | CAM response failure | Coordinated reset |
| 4 | Malformed header, row, candidate or nonfinite stored value | Repair source state and reset |
| 5 | Scorer failure or nonfinite result | Repair provider and reset |
| 6 | Path limit exceeded | Discard partial path; reset and supply sufficient capacity |
| 7 | Illegal controller state | Reset |
| 8 | Start received while poisoned | Reset before selection |

Neural error codes retain their existing specification. A neural ADC failure
does not mutate the selection cache; the tests verify a subsequent warm
selection. This does not guarantee recovery from arbitrary physical faults.

## Cost boundary

The integrated top includes the selector, child-ID/match buffers, neural
sequencer, its digital arithmetic and both SRAM routers. Do not add standalone
child-module area/power again. SRAM macros, CAM storage/search/readout, analog
arrays/converters, UCB arithmetic, clock/power infrastructure, expansion and
backpropagation remain outside this synthesized top.

Generic Yosys netlists establish synthesizability and digital functional
replay only. No standard-cell library, STA, physical placement or gate delays
are included. The separate 65 nm DC template records raw-source provenance
and performs no scaling or power adoption. Apply a documented 65-to-22 nm
conversion once when real digital reports exist. Native 22 nm CACTI SRAM is
not rescaled. Whole-chip area, power and energy remain unavailable.
