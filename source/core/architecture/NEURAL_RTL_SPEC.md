# Neural controller and SRAM integration

Round 11, 2026-09-09 UTC. Implements the mapped inference from
[NEURAL_SPEC.md](NEURAL_SPEC.md), using the arithmetic and bank interfaces in
[DIGITAL_SPEC.md](DIGITAL_SPEC.md). The complete neural path passes digital RTL
and generic netlist checks. Full MCTS control, analog fidelity, library timing
closure and whole-chip PPA remain open.

## Implemented path

`imc_neural_core` connects `imc_neural_sequencer` to one three-bank node SRAM
router. The sequencer owns one accumulator, one rounded divider and one shared
signed scaling/saturation lane. The existing accumulator, divider and router
sources are unchanged from Round 10.

One inference reads a packed board, drives the first array layer, captures
three-lane ADC responses, accumulates signed slice contributions, applies ReLU
and nearest-even scaling, and stores packed u8 hidden values. The second layer
reads those hidden values and executes all eight input bits. It scales and
stores three signed Q12 logits, rereads them, finds the maximum, reads three
Q30 exponentials from the SRAM LUT, sums them, divides and rounds three Q16
probabilities, and stores the Q17 value `2*p_black + p_draw`.

The default mapping is 162 inputs, 96 hidden units and three outputs. The
controller supports a single 256-row tile per layer, with successive 32-output
tiles. Parameterized 8-input/5-hidden elaboration is also verified. The Python
service model supports larger row-tiled mappings; this controller does not
implement them. The named simulator timing option is restricted to the
verified 162-96-3 configuration, three ADC lanes and 16 active rows.

## Start, completion and storage

`start && ready` accepts a request. `board_base`, `neural_base`, `hidden_shift`
and `logit_shift` are captured on that edge and may change afterward.
`hidden_shift` is unsigned six-bit (0 through 63); `logit_shift` is signed
eight-bit. Hidden scaling uses the profile's nonnegative shift; logit scaling
may multiply or divide. `imc_fixed_scale`
rounds signed right shifts to nearest even and saturates signed 32-bit left
shifts without wrapping, including shifts outside the data width.

`result_valid` holds `value_code` and `result_error` until `result_ready`.
One inference is outstanding. The completion edge follows the final SRAM
write response. Result backpressure extends ownership but is outside the
reported start-to-result latency.

The board and scratch bases must be word aligned, disjoint and inside the
three 512 KiB node banks. The scratch layout is:

| Region | Offset for 96 hidden units | Bytes |
| --- | ---: | ---: |
| Packed hidden vector | 0 | 96 |
| Signed logits | 96 | 12 |
| Probabilities | 108 | 12 |
| Value | 120 | 4 |
| Exponential LUT | 124 | 16,388 |

The neural region occupies the existing 16,512-byte reservation. Hidden tails
are padded to four bytes and written with zero padding. Board features are
interleaved black/white occupancy, packed least-significant bit first. The
caller supplies a valid board and the matching quantization shifts, programmed
weights and LUT before starting. This controller does not program array
weights or initialize the LUT. The architecture API separately bills the
4,097 initialization word writes once per search.

Hidden activation and writes interleave: four activation cycles, then one
word request/response. Each output logit similarly gets one scale cycle and
one word transfer. These dependencies are explicit in `rtl_serial_v1`.

## External memory and analog boundary

The sequencer's aligned 32-bit memory request/response interface connects to
the Round 10 router. The core exposes three physical bank ports with 17-bit
word addresses, 32-bit data and one response per accepted read or write. It
owns the node SRAM interface for the inference. Arbitration with other MCTS
clients is an external dependency; the current simulator serializes them.

`drive_valid/drive_ready` transmits array ID, row start/count, input bit and a
16-bit row-drive vector. The controller holds the selected array active while
its columns are multiplexed and converted. It waits three settle cycles,
issues one mux-select cycle and one sample/hold cycle, then handshakes an ADC
request. `column_start` and `column_count` select up to three columns.
`adc_rsp_valid/adc_rsp_ready` returns three packed eight-bit codes and an
error flag. Inactive tail lanes are ignored. Response wait and request/drive
backpressure add cycles without issuing duplicate work.

The verification environment calculates ideal cell-code ADC answers from
independent integer products and checks every request's array, row, bit,
driven bits and column metadata before returning them. It supplies a
nine-cycle request-to-response ADC and a synchronous one-cycle SRAM bank.
These are explicit interface assumptions. No analog array, converter,
sample/hold, voltage reference, row driver or column mux is synthesized here.
The three settle cycles and the 500 MHz target are not physical timing proof.

All digital interfaces, SRAM banks and the ADC provider must reset together.
Reset aborts outstanding work and clears controller/router state. A response
from a pre-reset request must not be delivered after reset. There is no
independent soft-abort or timeout port; an external interface that never
responds can stall indefinitely.

## Errors

| Code | Meaning |
| --- | --- |
| 0 | Successful inference |
| 1 | Unsupported dimensions, alignment, capacity or overlapping regions |
| 2 | Memory response error |
| 3 | ADC response error |
| 4 | Accumulator command or overflow error |
| 5 | Invalid exponential LUT value (zero or above 2^30) |
| 6 | Division error or probability above 2^16 |
| 7 | Illegal controller state |

Errors complete with zero value. Invalid base configurations issue no memory
or ADC work. A later error may leave partial scratch writes; the caller must
discard that inference. Hidden/logit saturation is reported by separate
pulses and follows the numerical contract, rather than becoming an error.
The maximum-minus-logit subtraction is widened to 33 bits before LUT scaling
and clamping, so extreme signed logits cannot wrap.

Directed tests cover configuration errors, early/late ADC errors, invalid
LUT entries and reset while an ADC response is pending. Primitive tests cover
router and accumulator errors. This is not exhaustive verification of every
sequencer fault path or formal equivalence proof.

## Timing and simulator identity

```python
result = Accelerator(
    board_size=9, iterations=5000, seed=0,
    neural_mode='mapped', memory_profile='cacti_22nm_lstp',
    neural_timing='rtl_serial_v1',
).analyze('simulate')
```

`neural_timing='service'` is the default and retains the earlier configuration,
schedule and numerical records. `rtl_serial_v1` requires mapped 9x9 simulation
and either characterized CACTI profile. It is accepted by the constructor,
static `Accelerator.estimate` and module-level `estimate`. Unsupported or
mutated configurations fail instead of falling back to another timing model.

| Per-inference contribution | Existing CACTI service cycles | Added controller cycles |
| --- | ---: | ---: |
| SRAM, 96 words | 192 | 96 |
| ADC, 1,611 groups | 14,499 | 1,611 |
| Three rounded divisions | 150 | 3 |
| Other scheduled work | 10,069 | 0 |
| Total | 24,910 | 1,710 |

The implemented controller takes **26,620 cycles** from accepted start to
result under the unstalled test conditions. The added SRAM request cycle is
controller overhead. CACTI macro service and per-access energy are unchanged.
The router itself can accept requests every two cycles with a pipelined
client; this sequencer waits for each response and starts its next request on
the following cycle. ADC request and divider-result capture are likewise
explicit controller work.

`reconcile.py` compares every debug state cycle against the new Python
schedule for empty, black, white and patterned 9x9 boards, two runs each.
The core and generic netlist also reproduce identical stalled-pattern
latencies of 29,629 and 29,616 cycles under the same periodic stall pattern.
Those stalls are test conditions, not a production simulator profile.

The packaged [timing evidence](neural_controller_timing.json) records the
interface assumptions, exact RTL hashes and hardware-run metadata/archive
hashes. New configurations include it. Simulator source identity hashes the
packaged record as well. Old configuration identities remain reproducible;
execution/source identities change with this code revision.

## Physical ownership and validation limits

The full neural core's flattened Yosys output has 13,564 reported generic
cells, including five scope-metadata cells, and 1,851 flip-flop bits. These
counts are structural evidence, not physical area, energy or clock closure.
The service model's old register budget is still labeled as an abstract
budget; it is not this integrated netlist's census.

If characterizing `imc_neural_core`, do not add the separately characterized
sequencer, accumulator, scale, divider or its node router again. The core
already contains them. The child router, SRAM macros, analog peripherals,
full MCTS/cache/CAM/UCB logic and physical implementation remain separate.
The DC template includes the new tops and a combinational constraint for the
scale lane, but DC and a valid 65 nm library were unavailable. Its updated
flow is unexecuted and must be reviewed in the actual library environment.

Retain native 65 nm digital reports and apply one documented conversion to
22 nm. Native 22 nm CACTI values are never rescaled. Whole-chip mapped PPA
remains null; only partial SRAM dynamic energy and full-duration leakage are
reported. The longer neural schedule raises SRAM leakage energy while
preserving access counts and dynamic energy. See the
[Round 11 evidence](../../p03_experiments/p10_neural_sequence/README.md).
