# Single-child architectural execution, revision 1

This is the default for new custom placement and Go searches. The explicit
`complete_serial_q32_v2` and legacy Go profiles remain replayable references
with their original full-expansion behavior. The new profile names begin
`single_child_`; every result records its exact policy, layout and sources.

## Search semantics

Evaluate the root once before expansion. On later iterations, selection stops
at a nonterminal node with untried legal actions, even if it already has
children. Use the existing integer UCB only once all actions are represented.
Choose one remaining action with the existing xorshift32/modulo mechanism,
in row-major action order with Go pass last. Allocate one node and one edge,
evaluate that child and backpropagate along the path. Terminal visits allocate
nothing. Existing rules, model inputs, weights, quantization and value
perspective are unchanged. Equal-UCB and final-visit ties prefer the first
allocated child; allocation order is now the seeded expansion order.

The submitted supplement's Algorithm 1 adds one child but omits the selection
stop condition for untried moves. This implementation makes that condition
explicit. The recovered tournament engine also expands incrementally, but
its first-iteration behavior, RNG, pass suppression and floating arithmetic
are different. This is not a claim of identical historical playing strength.

## Stored state

The SRAM banks stay at three 512 KiB node banks plus one 512 KiB child bank.
Existing 24-byte metadata and packed board encoding retain their offsets.
Each node gains an extension after its board: 4-byte remaining-action count,
4-byte child-list tail index and a word-aligned action bitmap. Count
`0xffffffff` means the bitmap has not been initialized. On first revisiting
the node, legal actions initialize its bitmap and count once. Each expansion
clears one bit and decrements the count. No full child board is reserved for
untried actions. Go legal-mask generation remains host work, as before;
receiving/storing the mask and processing it are charged in the model.

For 9x9, the bitmap is 12 bytes and the complete node stride is 68 bytes.
One child edge uses 8 bytes: child ID and next-edge index. The parent stores
the list head, count and tail. Tail linking is constant work without list
relocation or copying. Every header, bitmap and edge read/write is metered.
The host node dictionary is an observation mirror, not the action authority.
Go rule/history metadata remain outside the modeled SRAM boundary.

CAM misses walk the linked records before filling the existing parent-child
cache. Normal selection caches only fully expanded parents. Defensive cache
invalidation on append flushes cached lists and charges every invalidated row
and header transaction, retaining contiguous circular FIFO allocation.

## Timing and cost coverage

Single-child control is an architectural service estimate, not a synthesized
controller. SRAM words take two service cycles plus one request cycle, as in
the existing serialized-interface assumption. Selection explicitly charges
node decode/branch (3 cycles), action-count checks (1), candidate control (4),
linked-edge following (1 per record) and existing CAM/UCB services. Placement
legal detection scans one board cell per cycle; Go mask delivery takes one
modeled latch cycle, excluding host legality computation. Expansion scans
one action bit per cycle and charges 35 cycles for registered seeded choice
and iterative remainder, following the retained choice-block schedule.
Append control takes three cycles; move application takes one modeled control
cycle, with Go successor computation excluded. Phase starts take two cycles.
Commit takes four cycles: iteration completion and three budget comparisons.
Unchanged neural and backprop equations retain their existing integer
primitive timing. All recorded services must fit their owning phase interval.

The selection, tree-update and top-level glue reports do not characterize
the new controller or layout. For the reviewed 9x9, H96, CAM1024, 2 MiB
geometry, controller_estimates.json now supplies explicitly labeled
closest-report proxies with a 25% whole-parent engineering allowance.
The 163-input neural controller uses the 162-input report under that same
allowance; the exact 162-input neural parent keeps its matching report.
Area, active dynamic, clock-only idle and leakage receive the allowance
before the existing single node conversion. Per-node metadata is already
priced in SRAM and is not charged as another register bank. The 0%, 25%
and 100% allowance scenarios are sensitivity assumptions, not calibrated
confidence intervals or guaranteed bounds. No native timing/area result
is assigned to an estimated revised controller. Unreviewed geometries stay
excluded. Matching new-controller characterization and whole-chip PPA remain
unavailable. See CONTROLLER_ESTIMATE_SPEC.md for ownership and limitations.

## Capacity and outputs

At a completed iteration boundary, stop if the node or edge pool is full,
or the path high-water mark has reached its configured quota. This conservative
path rule applies only when the workload can grow a deeper path: the placement
bound is initial empty cells plus the root, and Go uses its remaining move
limit plus the root. A stack that fits the entire possible path does not cause
a stop on terminal revisits. Below that bound, the conservative path rule may
stop before other branches exhaust their capacity. If the
requested iteration count has been completed, report Complete instead.
No pruning, eviction of tree nodes, restart or memory enlargement is implicit.
All phases of every reported iteration finish, including backprop and commit.
Capacity preflight precedes random-state advancement, action consumption and
child allocation. On a memory-limited search, preserve the result and actual
iteration count. A game may commit the most-visited root child then stops the
session for inspection; if no root child exists, report that no move was found.
Memory-limited results must not enter complete-budget canonical snapshots.

Installed SRAM area stays fixed. Smaller trees do not imply a smaller chip,
and lower known subtotals caused by excluded controller costs are not savings.
