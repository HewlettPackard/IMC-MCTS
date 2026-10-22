# Implemented digital interfaces and remaining physical costs

Round 11 update: [NEURAL_RTL_SPEC.md](NEURAL_RTL_SPEC.md) now connects these
unchanged primitives through a full neural sequencer, signed scale lane and
node-SRAM wrapper. That specification supersedes the integration gaps below
for the neural path. The following Round 10 primitive contracts and evidence
remain valid. Full MCTS control and physical characterization remain open.

Round 10, 2026-09-09 UTC. Applies to the mapped 9x9 candidate from
[NEURAL_SPEC.md](NEURAL_SPEC.md) and the two native 22 nm profiles from
[SRAM_SPEC.md](SRAM_SPEC.md). Existing simulator code, profiles and results are
unchanged. These blocks are executable implementation candidates for later
integration and 65 nm characterization. Whole-chip mapped PPA remains null.

## Ownership and observable behavior

| Implemented block | Simulator operation/resource | Included hardware | Still external |
| --- | --- | --- | --- |
| Shared shift accumulator | `shift_add`, partial-sum clear and storage | 32 x 32-bit sum registers, one signed arithmetic lane, shift logic, write decode, read mux, invalid/overflow flags | ADC output capture, array/column selection, tile sequencer, hidden scaling/writeback |
| Rounded divider | Three output probability divisions | 48/32-bit restoring arithmetic, remainder, quotient, count, rounding and control | Exponential LUT SRAM, LUT addressing, sum of three exponentials, value reduction |
| Node SRAM router | Node/board, scratch, neural SRAM word transfers | Three-bank decode, request registers, one response holding register, FSM | SRAM macros, packed-record logic, client arbitration and full memory sequencer |
| Child SRAM router | Authoritative child-pointer SRAM word transfers | One-bank instance of the same router | Child-list allocation/traversal, SRAM macro |

The accumulator register array is digital storage. Do not also count it in
CACTI SRAM. The LUT and hidden vector already occupy the reserved neural SRAM
region; routers do not duplicate those arrays. The routers add explicit
request/response registers and control, which the simulator previously listed
only as uncharacterized control. No extra SRAM macro is required for them.

## Shift accumulator

`cmd_valid` submits a command on each rising edge; `clear` takes priority.
`cmd_addr`, `adc_code`, `shift_amount` and `subtract` select a signed update.
`cmd_done` and `cmd_error` report that command after the edge. A rejected
command still completes, with its sum unchanged. `read_addr` provides a
combinational read; an invalid read returns zero. Active-low asynchronous
reset clears every entry and both flags.

Weights occupy `[positive low, positive high, negative low, negative high]`
columns. Each 8-bit unsigned ADC code is shifted by `input_bit + 4*cell_slice`,
then added or subtracted into one signed 32-bit entry. Only shifts 0 through
11 are valid. A 33-bit intermediate detects signed overflow before storing.
The shared lane accepts one update per clock and clears all entries in one
clock. More than 32 output neurons use successive tiles and clear/writeback
steps owned by the external sequencer.

The default register bank contains 1,024 data bits. The five-entry elaboration
tests invalid address handling; the 32-entry netlist replays actual 9x9 mapped
commands. Both positive and negative overflow preserve the previous sum.
The vector generator is intentionally limited to this 9x9 mapping, whose
input rows fit within 256. Larger networks with multiple row tiles require
separate cross-tile accumulation tests before reuse.

## Rounded divider

When `ready && start`, the accepting edge loads numerator and denominator.
There are 48 subsequent restoring-division edges and one rounding edge.
This is 50 occupied service edges including setup, or 49 elapsed cycles from
the accepting edge to the `done` edge. A new request can be accepted on the
following edge. This matches the schedule's setup + 48 bit steps + rounding.

The quotient rounds to nearest with ties to even. The remainder reports the
unrounded integer division remainder, so it need not reconstruct the
numerator with the rounded quotient. Numerator width is 48; denominator and
stored remainder widths are 32. The doubled remainder and trial subtraction
use 33-bit combinational values. The old schedule's register budget names a
33-bit remainder register; that conservative budget is not the RTL register
count. Reconcile the census to the actual netlist before adopting costs.

Busy requests are ignored. A zero denominator immediately produces
`done=1, error=1`, zero quotient/remainder, and stays ready. `clear` aborts and
zeros state; asynchronous reset also aborts. The mapped LUT denominator is
positive and fits 32 bits; numerator is a Q30 exponential shifted by 16.
The supported default elaboration is 48/32. Parameterized widths below two
numerator bits are not supported.

## SRAM bank router

Requests use `req_valid/req_ready`; responses use `rsp_valid/rsp_ready` with a
32-bit value and error flag. Address is a **byte address**, aligned to four
bytes. One transaction is outstanding. Write payload and routing information
are captured at acceptance, so callers may change inputs immediately afterward.

The default 21-bit address spans three 512 KiB node banks. Bits above bit 18
select the bank; bits 18:2 form its 17-bit word address. The one-bank child
instance retains the same address width so out-of-capacity requests are
detected. Invalid alignment or bank indices return an error without issuing
a physical access. The supported geometry requires `BANK_BYTE_W >= 3`,
`ADDR_W > BANK_BYTE_W`, and a bank count representable by the bank-index bits.

For an unstalled one-cycle bank:

1. Edge 0: accept and register a request.
2. Edge 1: selected bank accepts the registered request.
3. Edge 2: consume its response and optionally accept the next request.

This permits the existing two-cycle word cadence. Timing at 500 MHz remains
uncharacterized. `bank_ready` can delay issue indefinitely without losing or
duplicating it. Each issued read **or write** must produce one response on its
matching bank, available while the controller is waiting. Zero-cycle
combinational acknowledgments at the issue edge are not supported. The bank
may pulse the response: a stalled consumer causes the router to capture it
in the 32-bit holding register until it is accepted. The bank cannot send
another response before another request is issued.

The bank interfaces and this router must reset together. Reset aborts pending
work; without coordinated reset a late bank response could belong to an old
request. No handshakes are interpreted during reset. The module returns to
idle with `req_ready` asserted, response/issue outputs inactive.

## Verification and cost boundary

The [hardware package](../../rtl_synthesis/p01_mapped_core/README.md) includes
the sources, filelist, testbenches, generic synthesis checks and DC template.
All 31 tool checks pass. Ten simulation executions include six RTL tests and
four generic netlist replays. The accumulator replay checks 19,612 commands
and 396 final dense-product outputs; the divider replays 12 mapped probability
cases plus directed arithmetic/control cases. This is deterministic digital
validation, not exhaustive formal verification or silicon validation.

| Synthesized generic elaboration | Generic cells | Flip-flop bits |
| --- | ---: | ---: |
| Accumulator, 32 entries | 5,634 | 1,026 |
| Divider, 48/32 bits | 1,085 | 171 |
| Node router, three banks | 610 | 89 |
| Child router, one bank | 336 | 89 |

These are Yosys generic counts, including automatically encoded state and
control. They have no technology area or power meaning. The design still
needs a full sequencer, activation/value arithmetic, SRAM adapters/arbitration,
CAM/cache control and binary64-reference UCB implementation or a separately
validated precision replacement. Existing repaired legacy buffers are not
automatically compatible with these ports and packed formats.

Obtain matching 65 nm library reports with corner, clock/load constraints,
netlists and workload activity before digital PPA. Preserve the original
reports and convert once to 22 nm with explicit factors and assumptions.
Do not import the old fitted digital totals or an unrelated 40 nm EAM result.
No chip cost is enabled by this round's structural checks.

## Converter evidence

The isolated [NeuroSim SAR probe](../../p03_experiments/p09_digital_periphery/README.md)
provides sensitivity evidence at native 65 and 22 nm. It does not establish
our converter's physical cost. Its fixed 1 ns decision step ignores the clock
argument; 8 bits reports 9 ns at both 500 MHz and 1 GHz. The architecture
currently reserves nine 500 MHz cycles, or 18 ns, for conversion. Keeping that
service time does not justify scaling the probe's energy to it.

The probe also lacks modeled leakage, explicit sample/hold/reference costs,
input accuracy, the device-current distribution, binary row drivers, column
muxes and extracted array wiring. Its reported 22 nm technology supply is
0.85 V, while the CACTI profiles use 0.8 V; these are separate source conditions.
Define and characterize the intended analog operating point before combining
them. Neither native estimate receives the digital 65-to-22 nm conversion.
