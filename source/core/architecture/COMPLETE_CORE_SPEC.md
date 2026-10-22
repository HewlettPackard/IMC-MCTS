# Complete serialized core, revision 2

The `complete_serial_q32_v2` profile connects the existing packed selector
and neural sequencer to expansion, backpropagation and actual UCB arithmetic.
It is separate from the preserved Accelerator reference and mapped-neural
profiles. Its software entry point is `CompleteSimulation` in
`iteration_model.py`. Its digital top is
`rtl_synthesis/p03_iteration_core/p00_rtl/imc_iteration_core.sv`.

## Reuse and corrections

The old empty-position detector and child-state generator supply the same
row-major two-bit placement semantics. The old path and SRAM writers describe
useful sequencing, but their short addresses, fixed counts and initial-only
ready sampling do not meet the current packed-memory/backpressure contract.
The old statistics updater increments a draw by one and wraps its 8-bit count.
New backpropagation preserves fractional values and rejects count overflow.

The old 2x2 UCB returns wins plus C, independently of nonzero visit counts.
The 5x5 calculator has unreachable valid assignments (`else if (start)` follows
the same condition), and does not finish the recorded 96-cycle probe. Its
logarithm/square-root placeholders also do not compute UCB. The 7x7 logarithm
table contains zeros. Those legacy files and their reports remain historical
evidence. Their physical costs cannot price this replacement.

## Execution contract

One job runs per coordinated reset of core, SRAM responders and CAM. The host
preloads a valid root/packed board, a 4,097-word exponential LUT, and the
programmed cell arrays. The host supplies an iteration budget, allocation
limits, exploration constant and quantization shifts. The RTL latches inputs
at accepted start. Completion is held until accepted; a new job requires reset.
Runtime errors stop work and identify the failing phase. SRAM writes already
acknowledged before an error remain committed, so a failed job cannot resume.

Selection uses the unchanged whole-parent FIFO CAM cache, ordered child IDs,
first-unvisited priority and first ties. Expansion creates all empty-cell
children in row-major order and preflights node, edge and path capacity.
One xorshift32 step chooses `word % child_count`; seed zero maps to
`0x6d2b79f5`. The generator advances only when children are created. This is
the named `xorshift32_modulo_v1` policy, distinct from Python `random.choice`.
Modulo choice has a small finite-word bias and is not labeled uniform sampling.

The neural sequencer reads the selected node's packed board directly. Expansion
still uses the working-board buffer. Each neural result is an unsigned Q17
black-player value. Backpropagation consumes the packed path leaf to root,
adding this value for black-to-play nodes and its complement for white-to-play.
The root starts with black to play. This remains empty-cell placement, with
no Go captures, ko, terminal scoring or task-quality claim.

All boards use three 512 KiB node banks and one 512 KiB child bank, with one
32-bit outstanding access and serialized owner arbitration. Node, edge and
path controls are allocation quotas within those fixed macros, not area
resizing. The supported one-row-tile software configurations are 2x2, 3x3,
5x5 and 9x9, with 32 hidden outputs for 2x2/3x3 and 96 for 5x5/9x9.

## Arithmetic

`ucb_q32_ln256_v1` computes `1 - value/visits + C*sqrt(ln(parent)/visits)`.
Its visited inputs require `1 <= child <= parent < 2^32`, an exact nonnegative
Q17 sum no larger than child visits, and finite `0 <= C <= 8`. Unvisited
children exit in the selector before reaching this calculator.

A sum of Q17 values across a 32-bit visit count needs 49 integer bits and is
exactly representable in the existing binary64 SRAM field. The codec checks
that representation before integer addition. Division and logarithm use Q48;
the logarithm normalizes the parent count and linearly interpolates a 257-entry
`ln(1+i/256)` table generated at Decimal precision 80. The 104-bit restoring
square root takes 52 steps. C and final scores round to Q32 with nearest-even
rounding. The exact Q32 score is encoded as binary64 for the unchanged selector.

The calculator takes 222 cycles from accepted request to valid result under
its local clock. The selector additionally spends request/capture/compare
cycles. Numerical acceptance is absolute score error <= 1e-5 and unchanged
decisions when the binary64 top-two margin exceeds 2e-5. Recorded vectors have
maximum error 3.043e-6 and all 10,000 tested choice groups agree. This is a
diagnostic test set, not a universal identity guarantee or trained-task result.

## Cycle model and boundary

The software model follows the same tree and packed-memory operations. The
cycle contract assumes one-cycle bank response after issue, one router issue
cycle, a three-cycle CAM request/response transaction, and the existing ideal
neural drive/settle/ADC services. No interface stalls are assumed in reported
software latency; separate stalled RTL tests verify backpressure behavior.

With B packed board words and K new children, the local expansion latency is
20 cycles for a skipped expansion, `24+9B` for a full board, and
`71+9B+K(26+6B)` for an expansion. Revision 2 registers the empty count
and uses an exact 32-bit iterative remainder, adding 35 cycles only when
children are created. The active source is byte-identical to the returned
tree-update v2 synthesis packet. No extra SRAM transaction is introduced. Backpropagation costs 35 cycles per path
node. Selection charges each metadata/path, CAM, candidate and arithmetic
state according to the checked controller. Each phase has two owner/start/
completion cycles, and iteration commit adds one cycle. Neural timing reuses
the verified sequencer service trace and its SRAM/ADC/divider handshake costs.

Saved phase boundaries are checked against RTL. The optional low-level
software memory trace preserves request order and service counts, aggregating
controller gaps at phase ends. It is not a per-cycle waveform and must not be
used as power activity. The clock remains an assumed 500 MHz; generic gate
simulation has no cell delays and does not prove physical timing closure.

## PPA accounting

The four SRAM macros use pinned native 22 nm CACTI estimates and receive no
further scaling. The compatible 9x9 configuration now also has seven returned
65 nm digital parent reports: selector, UCB, neural, tree update, two SRAM
routers and top-level glue. The glue report excludes those child parents.
Count each installed parent once; its internal instances are already included.
Do not add a combined whole-core synthesis area to these module costs.

The current simple power model uses reported vectorless dynamic power while
active, the reported clock-network group while idle, and leakage over elapsed
core time. This is an approximation, not measured workload activity. Apply
`(22/65)^2` to digital area and `(22/65)*(0.8/1.0)^2` to digital dynamic energy
once. Native65 leakage remains an explicit unchanged proxy. No additional
server synthesis or waveform capture is required to use this model.

The shared component ledger also includes workbook CIM/driver/front-end
estimates, a CACTI CAM proxy, a SAR ADC proxy and explicit physical allowances.
These source conditions do not establish a common physical operating point.
Host Go rules, I/O, pads/package and weight programming remain outside the
preloaded-core boundary. Whole-chip totals remain null. Smaller configurations
with unmatched digital reports retain missing costs instead of borrowing 9x9
numbers. See [COMPONENT_PPA_SPEC.md](COMPONENT_PPA_SPEC.md),
[BLOCK_POWER_SPEC.md](BLOCK_POWER_SPEC.md) and
[TECHNOLOGY_SPEC.md](TECHNOLOGY_SPEC.md) for current sources and limits.

Revision 2 native tree-update characterization: 35,855.520030 um² at TSMC65,
TT 1 V/25 C, 2 ns, zero reported setup/capacitance/transition violations.
Slack is rounded to 0.00 ns. This standalone wire-load result does not
establish system or 22 nm physical closure. Its child divider and codec
are included in the parent area. See PLAN_ROUND_23.md for the admission.
