# Original design and repaired implementation

Round 42, 2026-09-14 UTC. This records the current implementation boundary,
not an architecture optimization. The original project remains preserved.

| Part | Recovered intent | Current implementation and limit |
| --- | --- | --- |
| Selection | Find a node's children, then apply UCB | Parent-ID CAM lookup supplies ordered child IDs; one serialized UCB unit. A single lookup does not make the entire selection path one cycle. |
| Expansion | Allocate successor states and child links | Packed SRAM nodes and 32-bit child pointers, capacity preflight and finite buffers. Go successor generation stays on the host. |
| Rollout | Differential CIM evaluation with shared conversion | Existing signed, sliced 8-bit mapping and three shared ADC lanes. Default sustained drive is preserved; column hold remains a separate profile. |
| Backprop | Update visit counts and values along the path | Values belong to the player to move, as in the original event path. The Go adapter's previous reversal is repaired in profile v3. |
| FSM | TCAM matches state and inputs, then next-state RAM | Returned hardware implements digital FSM/glue. No functional TCAM controller or matching characterization was recovered. This physical fidelity gap remains explicit. |
| Shared memory | Tree/state storage and temporary buffering | Three node banks and one child bank; scratch allocations, routers and cache buffers have separate ownership. |

The submitted CAM description mixes board-pattern storage with querying a
parent ID to retrieve all child addresses. The active original event path
instead scans a Python child list. An unrelated board-hash helper was not on
that path. These are inconsistent descriptions, not proof of a functioning
board-key associative search in the old simulator. The repaired cache retains
the child-discovery role: one parent key maps to its ordered child IDs, whole
lists enter/leave together, and SRAM remains authoritative. It does not merge
transpositions or change the MCTS tree into a graph.

The logical CAM row needs a 32-bit parent key, a 32-bit child payload and valid
state. The CACTI proxy pads the tag to 36 bits; that tool padding does not change
the logical node address width. Child pointers in SRAM occupy four bytes,
consistent with the implemented address range and earlier helper. The paper's
eight-byte entry wording is not used to silently double the physical banks.
Capacity limits are allocations within installed SRAM, not smaller fabricated
macros. Cache misses/fills, ordered output and SRAM service are charged.

The legacy optional TCAM import points to a missing `tcam_fsm` module and
falls back to string-state control. Board-configuration TCAM area constants do
not establish the transition table or a physical controller. The current glue
report therefore stays labeled digital. A TCAM implementation would require
the state/input encoding, transition rows and priorities, next-state/control
payload and access schedule, followed by compatible area/power assumptions.
Adding a CAM area constant to the existing digital glue would neither implement
that controller nor avoid double counting. The user decision about restoring
TCAM control remains open; no primitive is silently substituted in this round.

The original UCB objective, neural evaluation role, expansion/backpropagation
stages and most-visited move policy remain. Finite precision, xorshift32 choice,
packed layout and serialized service are documented implementation choices.
Fixing a value bug can change the explored tree, cycle count and energy. Old
buggy Go results remain historical and must not be treated as profile-v3 data.

Evidence: [original design review](../../p03_experiments/p05_legacy_design_review/README.md),
[old versus repaired comparison](../../p03_experiments/p40_old_vs_repaired/README.md),
`py_sst_cpp/components/common/base_components.py` (optional TCAM import),
`core/simulator/tree_memory.py` (cache contract), and
`rtl_synthesis/p03_iteration_core/p00_rtl/imc_iteration_core.sv` (digital control).
The machine-readable [contract](architecture_contract.json) is included in new
run identities and source archives. It records the existing hardware for the
trained reference; it does not claim original TCAM fidelity or complete-chip PPA.
