# Neural mapping and service schedule

Round 8, 2026-09-09 UTC. Implemented by
[`NeuralMapping`](neural_mapping.py), with validation in the
[experiment report](../../p03_experiments/p07_neural_mapping/README.md).
Model: `differential_w8_cell4_a8_adc8_serial_v1`.

This is a candidate finite-precision implementation with ideal cell-code
arithmetic and serialized service times. It establishes a reproducible mapping,
resource census, and execution schedule. Device accuracy, physical timing,
power, energy, area, and application strength are not established.

## Interface and version boundary

```python
from core.architecture.accelerator_api import Accelerator

result = Accelerator(
    board_size=9, iterations=5000, seed=0,
    neural_mode='mapped', capture_memory_trace=False,
).analyze('simulate')
print(result.latency_us)
print(result.simulation['neural']['resources'])
assert result.energy_uj is None
```

`neural_mode='reference'` remains the default for reproduction. It executes
the existing float64 evaluator and legacy neural delay. `mapped` executes
integer inference, reserves neural SRAM, and bills its complete schedule.
Mapped mode requires `simulate`; it cannot use the analytical phase estimate
or old converter power overrides. Mapped area, power, energy, and energy
efficiency are `None` (JSON `null`), with empty cost breakdowns. The old costs
describe another geometry and cannot price this one. SRAM capacities remain
available in `simulation.memory.config`; the old area-bearing `memory_sizing`
object is not returned in mapped mode.

Round 9 optionally selects `memory_profile='cacti_22nm_hp'` or
`'cacti_22nm_lstp'` for 9x9. The [SRAM contract](SRAM_SPEC.md) supplies two-cycle
word service to both the tree and neural schedule, with partial SRAM costs in
`accounting.sram`. The 96 neural SRAM words add 96 cycles per inference, making
24,910 cycles for these profiles. The Round 8 reference-memory figures below
remain reproducible. Neural arithmetic, arrays, and converter services are
unchanged; no complete chip cost is enabled.

Round 11 adds opt-in `neural_timing='rtl_serial_v1'` with either CACTI profile
for 9x9. Its complete neural controller takes 26,620 unstalled cycles and
matches the new schedule cycle by cycle. `neural_timing='service'` preserves
the figures above and below. See [NEURAL_RTL_SPEC.md](NEURAL_RTL_SPEC.md) for
handshake overhead, interface assumptions, evidence and remaining boundaries.

Both numerical modes remain seeded random-evaluator, empty-cell-placement diagnostics.
The API has no canonical trained paper case. Changing finite arithmetic can
change values, ties, and later search paths; identical trees between these two
modes are not a requirement. Repeatability within a mode is a requirement.
Board size alone does not identify a result. Configuration identity now records
the neural mode, mapping, precisions, services, coefficient hashes, and storage.

Supported event board sizes retain their current evaluator dimensions: hidden
32 for 2x2/3x3, hidden 96 for 5x5/9x9/13x13/19x19. The recovered supplement's
128-hidden 19x19 variant is not silently substituted; it needs its own explicit
case and checkpoint. The worked acceptance case in this round is 9x9.

## Arithmetic and arrays

The 9x9 network is `162 -> 96 -> 3`, without biases. Input features interleave
black/white occupancy. Hidden activation is ReLU; output order is white, draw,
black. Value is `p_black + p_draw/2`. The packed working board already contains
these binary features: empty `00`, black `01`, white `10`, least-significant bit
first. The simulator's decoded board uses -1 for white.

Each layer uses a power-of-two weight scale. If the largest absolute weight
is M, the fraction count is `floor(log2(127/M))`, or zero for an all-zero matrix.
Weights are rounded to nearest, ties to even, into -127..127. Supported fraction
counts are -16..30. Signed weights use separate positive/negative branches,
each with two 4-bit magnitude slices. A logical weight occupies four cells;
the high slice uses only three significant bits for this weight range.

| Resource | 9x9 candidate |
| --- | ---: |
| Logical weights, both layers | 15,840 |
| Mapped cells | 63,360 |
| Physical array geometry | 256 rows × 128 columns |
| Outputs per array tile | 32 (four columns per output) |
| Resident arrays | 3 for layer 1, 1 for layer 2 |
| Allocated cells | 131,072 |
| Active rows per pulse | Up to 16 |
| Shared ADC and sample/hold lanes | 3 of each |
| Binary input drivers | 16 |
| Signed shift/add lanes | 1 |
| ADC readout bus | 32 bits |

Row tiles above 256 inputs and column tiles above 32 outputs are explicit.
Only one array is active at a time. Every sign/slice column is converted;
zero values do not skip conversions. Ideal unsigned column sums are bounded
by `16 * 15 = 240`, within an 8-bit code. Layer 1 uses one binary input bit;
layer 2 executes eight pulses per row group for its unsigned 8-bit inputs.
Sign, cell-slice, input-bit, and row-group contributions accumulate into
signed 32-bit values. This schedule assumes selected rows remain driven while
the shared bank multiplexes and converts their columns. The array pulse count
does not imply only three cycles of current flow; eventual energy integration
must include this hold interval.

The current model assumes exact baseline-cancelled cell-code currents. Actual
conductance range, nonzero off-current, subtraction before/after quantization,
gain/reference circuits, ADC error, noise, drift, IR drop, and variation need
device-level evaluation. The code bound of 240 alone does not prove that a
physical 8-bit ADC can resolve these sums. No analog power constants are used.

For the hidden scale, each neuron has a bound formed by choosing the largest
of zero, black, or white weight at every cell. Sum these choices, then select
the smallest right shift making every bound at most `255 << shift`.
This bound follows the placement encoding and does not depend on validation
samples. ReLU values are rounded, shifted, and saturated into u8 codes. The
second layer accumulates these codes and resizes logits to signed Q12/int32,
with explicit saturation. The seed-0 9x9 case uses weight fractions [8, 8] and
hidden right shift 3. The model reports clipping counts for a worked inference.

Output logic uses a 4,097-entry u32 Q30 LUT for `exp(-x)`, x from 0 through 16
at 1/256 spacing. After subtracting the maximum Q12 logit, indices round to
nearest even and clamp at 4,096. Three exponentials sum into a u32 denominator;
the maximum is `3 * 2**30`. A 48-bit numerator and restoring-divider schedule
produce each nearest-even Q16 probability. Probability codes are individually
rounded, so their sum can differ from 65,536 by one. The Black value is exactly
`(2 * p_black_code + p_draw_code) / 2**17`. The tree converts this to its existing
binary64 value format; fixed-point UCB and tree accumulation are still pending.

## Storage and transfers

Neural scratch follows the path/working/candidate/cache-header partitions
in node SRAM. These are packed backing bytes, used for functional intermediate
reads/writes as well as schedule accounting. No new SRAM capacity is assumed.

| Region | Offset from neural base | Bytes for 9x9 |
| --- | ---: | ---: |
| Hidden u8 activations | 0 | 96 |
| Three Q12/int32 logits | 96 | 12 |
| Three Q16/u32 probabilities | 108 | 12 |
| Q17/u32 value | 120 | 4 |
| Q30/u32 exponential LUT | 124 | 16,388 |
| Total | | 16,512 |

All regions are four-byte aligned. The 9x9 neural base is 16,752; node slots
now start at 33,264. The existing 1,572,864-byte node SRAM holds 32,075 node/board
slots in mapped mode, versus 32,419 in reference mode. Child capacity is
unchanged. Allocation quotas are checked after reserving neural scratch.

Bounded registers include 16×8 input bits, a 32-bit SRAM word register,
32×32-bit accumulators for one output tile, ADC codes, three logits, three
exponentials, coefficient words, and 48/32/33/48-bit numerator/denominator/
remainder/quotient divider registers. Controller, mux decoding, routing,
interfaces, and physical register implementation remain unsynthesized. The
census is not a complete transistor or flip-flop count.

Weights are assumed already programmed into resident arrays. The exponential
LUT is stored in SRAM and its 4,097 initialization word writes are billed once
per run. Their source/interface and external preload traffic are not modeled.
Weight programming, SRAM/CAM reset, and chip-level I/O remain outside the run
boundary. The board fetch already charged by tree memory remains separate;
the neural schedule rereads each needed word for its row group/output tile.

## Serialized timing and trace

Services assume the reference 500 MHz clock, 2 ns per cycle. SRAM word transfer,
binary drive, mux selection, sample/hold, each readout word, each shift/add, and
each digital operation take one cycle. Array settling takes three cycles,
rounding the old 5 ns placeholder upward. Each ADC group takes nine cycles:
one setup plus eight assumed one-cycle SAR decisions. Division costs one setup,
48 bit steps, then rounding. These are explicit design assumptions, not measured
macros, synthesized clock closure, or a proven physical latency bound.

For one 9x9 inference:

| Phase | Pulses | ADC conversions | ADC groups | Cycles |
| --- | ---: | ---: | ---: | ---: |
| Layer 1 | 33 | 4,224 | 1,419 | 21,540 |
| Layer 2 | 48 | 576 | 192 | 3,103 |
| Output LUT/division/value | 0 | 0 | 0 | 171 |
| Total | 81 | 4,800 | 1,611 | 24,814 |

This gives 49.628 µs under the stated services, excluding board loading,
one-time LUT initialization, and other MCTS work. It supersedes the legacy
14 ns neural placeholder only for mapped mode. Three ADC lanes serialize
much of this work; adding lanes is a measurable area/energy/timing tradeoff
once those circuits have calibrated costs.

`simulation.neural` contains resources, operations, phase cycles, profile,
coefficients, evaluation count, and cumulative counters. With capture enabled,
it also returns a relative template. The memory trace records one
`execute_template` event per inference, its start/end cycles, template hash,
and three actual LUT indices. Expansion uses that start cycle and the profile's
storage offsets; board accesses use `working_offset`, all other neural accesses
use `neural_base + region.offset`. LUT byte addresses are `index * 4`.
`NeuralMapping.inference_trace()` resolves addresses for the most recent call.
The aggregate schedule hash includes both template identity and LUT indices.

Functionally, effects are applied within a phase and completion is delayed
until its recorded services finish. Consumers run only after completion. This
is an ordered service model, not a per-word RTL simulation. All resources are
serialized; no banking, overlap, pipeline, or asynchronous request queue is
claimed. Internal SRAM words join the memory/activity counters without charging
the same template duration twice.

## Evidence and next calibration

The source of the differential/1-bit-DAC/8-bit-ADC intent is the submitted
supplement, archived in the [legacy review](../../p03_experiments/p05_legacy_design_review/README.md).
The old `crossbar_hardware.py` helper declares 8-bit weights and 4-bit cells;
its incompatible cost formulas were not reused. Array geometry, row grouping,
LUT arithmetic, and shared-bank scheduling here are new explicit candidates.

[NeuroSim's primary repository](https://github.com/neurosim/DNN_NeuroSim_V1.4)
was consulted for precision/partial-row modeling methodology;
[CrossSim's primary repository](https://github.com/sandialabs/cross-sim)
for the distinction between numerical mapping and device nonidealities
(accessed 2026-09-09 UTC). Neither tool was run, calibrated against, or copied
into this implementation. These references do not supply the service constants.

Directed tests check signed slicing, ADC limits, row/column tails, intermediate
precision, integer division, actual SRAM backing, storage bounds, ADC sharing,
trace identity, unsupported modes, and preservation of reference computation.
The experiment adds generated placement states, actual reference-search leaves,
independent dense integer products and hand counts, repeated mapped runs, and
full source/config/output snapshots. Accuracy targets are diagnostic only.

Next: run CACTI for the exact SRAM geometry/ports/banks at 22 nm, then obtain
compatible CIM/converter/digital costs and settle the single 65-to-22 nm digital
conversion. Native 22 nm SRAM records must not receive that conversion again.
Resolve omitted controls and boundaries, characterize analog error and timing,
then validate task rules/weights before creating canonical publication cases.
