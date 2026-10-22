# Hardware accounting: 9x9 reference audit

Round 4, 2026-09-08. These are **uncalibrated diagnostic costs**, not replacement
publication numbers. The audit reconstructs the current code and identifies
missing physical decisions. It does not select a new trained model, reinterpret
CPU/GPU baselines, or establish a fabricated-chip implementation.

The [experiment report](../../p03_experiments/p03_hardware_accounting/README.md)
contains before/after runs, compressed event traces, archived source tables,
source hashes, and verification. [SCOPE.md](../../SCOPE.md) freezes CPU/GPU
artifacts and protects the original project.

Current boundary after Round 8: the audit below describes the legacy reference
cost path. The new opt-in `neural_mode='mapped'` uses the
[explicit neural geometry and schedule](NEURAL_SPEC.md), and returns no power,
energy, or area totals. Its four-array mapping, converter sharing, and scratch
must receive compatible physical costs before numerical PPA reporting. The
default reference retains these legacy constants for reproduction. Neither
mode is calibrated. Round 7's memory model and Round 8's neural model resolve
several scheduling gaps below without validating their physical cost sources.

Round 9 update: [SRAM_SPEC.md](SRAM_SPEC.md) adds exact native 22 nm CACTI
HP/LSTP evidence, three 512 KiB node macros and one child macro, counted access
energy, and full-duration leakage. These costs are explicitly partial. The
user confirms the original digital synthesis node was 65 nm. All archived
area/power conversion factors are now numerically reconciled in the
[Round 9 ledger](../../p03_experiments/p08_cost_sources/README.md), but source
reports, power conditions, and compatibility with the new datapaths remain
unresolved. Historical statements below describe the Round 4 audit state.

## What the configuration actually executes

The diagnostic is 9x9, seed 0, 5,000 completed MCTS iterations,
at a declared 22 nm / 500 MHz reference point. One complete
MCTS search contains those 5,000 iterations. The API uses random diagnostic
weights; trained-checkpoint selection remains explicit and separate.

| Quantity | Executed or configured value | Evidence and status |
| --- | --- | --- |
| Board encoder | 162 interleaved Black/White features, no turn bit | `core/algorithm/evaluator.py`; executed |
| Layer 1 | 162 x 96, followed by ReLU | `RolloutUnitComponent._nn_forward`; executed float64 |
| Layer 2 | 96 x 3, followed by softmax | Same function; executed float64 |
| Logical coefficients | 15,552 + 288 = 15,840 | Matrix shape product, not a count of physical cells |
| Stored weight representation | Signed random float64 for this diagnostic; checkpoint interpretation is separately declared | No demonstrated physical signed-weight or bit-slice mapping |
| Cost-table input dimension | 81 | `BoardConfig.crossbar_size`; inconsistent with executed features |
| Cost-table coefficient count | 81 x 96 + 96 x 3 = 8,064 | Comment underlying crossbar area; not executed matrix count |
| Cost-table DAC channels | 81 | `BoardConfig.dac_power_mw` |
| Cost-table ADC channels | 3 | `BoardConfig.adc_power_mw`; hidden layer conversion not mapped |
| Neural latency | 14 ns, quantized to 7 reference cycles | Fixed legacy composite, not calibrated two-layer timing |

The software dependency chain is:

```text
for each MCTS iteration:                       sequential, feedback-dependent
    for each node on the selected path:        sequential in the timing model
        select from its children
    for each empty board position:             physical write parallelism unknown
        create a child if this leaf is expanded
    for layer in [162 -> 96, 96 -> 3]:          dependent layers
        for output j:                          spatial/temporal placement unknown
            sum over input i of x[i] * W[i,j]  array tiling and slicing unknown
        apply ReLU or softmax
    for selected path plus any chosen child:   per-node delay in timing model
        update visits and accumulated value
```

The Python algorithm generates all empty-position children when expanding a
visited leaf. It does not implement full Go legality/capture in this component.
Neither a functional Go-strength claim nor a physical memory bandwidth claim
follows from completing this diagnostic.

## Two-layer physical mapping still required

| Boundary | Logical work in one forward pass | Physical decision still missing |
| --- | --- | --- |
| Board to layer 1 | 162 input feature values | Analog voltages, bit serialization, row tiling, or encoding multiplexing |
| Layer 1 output | 96 dot-product results | ADC count, sharing ratio, precision, reference/subtraction for signed weights |
| Hidden activation | 96 ReLU values | Digital/analog implementation, storage, interconnect, clipping/scale |
| Hidden to layer 2 | 96 input values | Second DAC bank or documented reuse/analog interface |
| Layer 2 output | 3 logits | Conversion, softmax/value logic, output storage |
| Coefficient storage | 15,840 logical coefficients | Cells per coefficient, precision, differential/reference scheme, array dimensions |

For the **digitized intermediate interface described by the current evaluator
comments**, a forward pass presents 162 + 96 = 258 input values and 96 + 3 = 99
output values to its converter stages. These are values per inference, not a
requirement for 258 physical DACs or 99 physical ADCs. Sharing changes both
resource counts and schedule. The existing 2x array-area overhead is not an
explicit sign/precision mapping.

The old timing comment computes `3 + 2*2.5 + 2*3 = 14 ns`. Using both stated DAC
stages without overlap would instead give `2*(3 + 2.5 + 3) = 17 ns`, even before
activation and transfer costs. **17 ns is a conditional arithmetic check, not
an adopted timing replacement.** An overlap claim requires a concrete schedule.

The archived RTL does not resolve this: `crossbar_control_7x7.sv` describes a
49x49 array with row scanning and multi-cycle pulse/settle states;
`position_to_voltage_dacs_7x7.sv` encodes one voltage per board cell; and
`current_to_digital_adcs_7x7.sv` has 49 one-bit mock analog inputs and a 32-cycle
conversion parameter. They do not establish a 162->96->3 implementation. This
was a source inspection, not an RTL compile, synthesis, or timing validation.

## Area ledger

Values below are read from [board_config.py](../../py_sst_cpp/components/board_config.py).
All areas are declared at 22 nm. The raw technology correspondence is unresolved.
The named component rows are disjoint at the current software table boundary;
physical overlap between synthesized control and separately added analog
periphery has not been established.

| Component | Area (mm2) | Current derivation/origin | Evidence status |
| --- | ---: | --- | --- |
| Selection logic | 0.005112 | Claimed 12,780 um2 at 65 nm / 2.5 | That numerator matches the archived **22 nm** fitted table |
| Expansion logic | 0.010124 | Claimed 25,309 um2 at 65 nm / 2.5 | Same source/scaling conflict |
| Backprop logic | 0.000896 | Claimed 2,239 um2 at 65 nm / 2.5 | Same source/scaling conflict |
| Rollout digital control | 0.004720 | Rounded 11,800 um2 / 2.5 | Matches the original fitted-table scale, unlike the three rows above |
| Rollout DAC bank | 0.026600 | Rounded 81 x 0.000328 mm2 | Count and cited per-channel specification unresolved |
| Rollout ADC bank | 0.035000 | Three output converters | No hidden-layer conversion allocation; primary source not recovered |
| Crossbar arrays | 0.000684 | Rounded 8,064 x 0.0424 um2 x 2 / 1e6 | Wrong logical shape; cell/sign/precision mapping unresolved |
| Main FSM logic | 0.006000 | Approximate 15,000 um2 / 2.5 | No matching FSM row in inspected fitted tables |
| TCAM controller array | 0.000119 | Rounded 11 x 16 x 0.676 um2 / 1e6 | Cell estimate; analog boundary not calibrated |
| Selection CAM cells | 0.048758784 | 1,024 x 512 x 0.093 um2 / 1e6 | Cell-only formula; macro periphery/cache policy unresolved |
| Node SRAM | 1.275000 | 1,536 KiB x 0.85 mm2/MiB | Capacity-based extrapolation, not an exact macro characterization |
| Children SRAM | 0.425000 | 512 KiB x 0.85 mm2/MiB | Same extrapolation |
| **Included total** | **1.838013784** | Sum of the rows above | Arithmetic consistent; physical total not validated |

For the three conflicting digital rows, dividing already labeled 22 nm values
by 2.5 again is consistent with the present constants. Their original fitted
table totals are 111,560.880652 um2 (selection), 220,928.805747 um2 (expansion),
and 19,543.390339 um2 (backprop). The table labeled 22 nm scales them by
`(22/65)^2`, while the board comments claim `/2.5` as the conversion.
The numeric match establishes inconsistent provenance; it does not establish
the true synthesis node or license adopting either result as ground truth.

The source rows contain polynomial/linear fits, including two-point fits.
Original tool reports, exact elaborated designs, libraries, corners, clock
constraints, and activity annotations were not recovered in this audit.

## Power, energy, and timing ledger

All powers below are fixed reference assumptions, declared at 22 nm / 500 MHz.
Every included power is multiplied by the full modeled run duration. The code
does not independently integrate dynamic accesses, idle states, or leakage.

| Component | Power (mW) | Formula/origin | Status |
| --- | ---: | --- | --- |
| Selection logic | 4.960 | Approximately archived 22 nm table total x 5 x 0.44 | Source/scaling conflict |
| Expansion logic | 12.370 | Same transformation | Source/scaling conflict |
| Backprop logic | 1.010 | Same transformation | Source/scaling conflict |
| Rollout digital | 1.460 | Approximately original fitted table x 0.44 | Different source scale and frequency treatment |
| DACs | 4.050 | 81 x 0.05 mW/channel | Legacy assumption; mapping and source unresolved |
| ADCs | 0.300 | 3 x 0.10 mW/channel | Legacy assumption; mapping and source unresolved |
| Crossbar | 2.736 | 0.000684 mm2 x 4,000 mW/mm2 | Assumed active power density, not an implemented device-energy model |
| Main FSM | 5.500 | Assumed 12.5 mW x 0.44 | Raw origin not recovered |
| TCAM | 0.249 | Fixed state-partitioned power claim | Not derived from counted transitions |
| **Included total** | **32.635** | Sum of included powers | Incomplete physical boundary |

The digital power table labeled 22 nm contains 2.2529181, 5.6224924,
0.4610428, and 0.3073414 mW for selection, expansion, backprop, and rollout.
The board's claimed 65 nm bases for the first three are approximately the
first three numbers multiplied by five. Rollout instead uses the original
table's 3.3079 mW. The audit records these relationships without claiming
that either frequency scaling is physically justified.

| Timing term | Declared continuous delay | Implemented reference schedule after repair |
| --- | --- | --- |
| Controller transitions | 1 ns each, four per iteration | 1 cycle each |
| Selection | 2 ns + 1 ns x selected path nodes | Ceiling of whole phase / 2 ns |
| Expansion | 2 ns + 1 ns | 2 cycles, still independent of generated-child count |
| Neural evaluation | Fixed 14 ns | 7 cycles; layer/peripheral schedule unresolved |
| Backprop | (2 ns + 1 ns) x actual updated nodes | Ceiling of whole phase / 2 ns |
| Clock period | 2 ns | Reference only; other clocks rejected |
| Energy | `power_mW * modeled_time_us` in nJ | No host-runtime input |

Round 4 corrects the earlier flooring of fractional cycles. It leaves the
stated phase delays intact. The analytical depth formula is still an empirical
approximation and uses continuous delays; it is not required to match the
event trace exactly. Its equal selection/backprop depth approximation also
omits the extra chosen child on productive expansions.

## Memory and unbilled work

The seed-0 trace creates 6,562 nodes and 6,561 child pointers. Using the board
comments' entry formats gives 157,488 bytes of node metadata (24 bytes/node)
and 26,244 bytes of child pointers (4 bytes/edge). These fit the configured
1,572,864-byte and 524,288-byte pools, respectively. This is an entry-count
capacity check, not an implemented bank allocation check.

A compact two-bit-per-cell board image would add 21 bytes per node, or 137,802
bytes for this trace. That storage is absent from the 24-byte metadata layout;
its location or reconstruction procedure is not specified. The functional
Python arrays are not a physical storage format.

| Missing or ambiguous item | Why it matters | Evidence needed before billing |
| --- | --- | --- |
| 1,024-row CAM occupancy, lookup/miss/update/eviction | Tree has more nodes than CAM rows; a hot-node cache is only a comment | Cache function and policy, trace of accesses/misses |
| SRAM ports, bank count, entry width | One expansion can generate 81 children but receives a fixed delay | Concrete write/transfer schedule |
| Board-state storage and movement | Evaluation consumes a full board | Physical home or reconstruction cost |
| SRAM read/write energy and leakage | Areas included, separate memory power absent | Exact macro configuration and parsed tool output |
| CAM search/write energy and peripheral area | Cell parameters exist but are not used for per-search billing | Macro boundary, driver/sense/priority costs, operation counts |
| TCAM leakage | 0.000001 mW field exists but total power omits it | Explicit leakage policy and reconciliation with dynamic power |
| Hidden converters, signed-weight logic, activation, staging | Needed by the stated two-layer computation | Mapping, precision, sharing, measured/synthesized costs |
| Interconnect, bias/reference, clock distribution | No separately identified costs | Explicit implementation boundary and estimates |
| Initial weight programming, off-chip traffic, spill policy | No observed cost contract | State whether amortized/excluded; implement traffic if required |

The archived CACTI CSV has nine configurations with empty metric fields. The
small-memory JSON values match fallback constants in its characterization
script. A prose summary supplies other values, including estimates. None of
those files validates the exact 1,536/512 KiB macros. Their hashes are recorded
as evidence; their strong validation labels are not adopted.

The CAM-cell table records 0.15 um2 and 0.60 fJ at 28 nm, and the code claims
node scaling to 0.093 um2 and 0.48 fJ at 22 nm. Its stated energy formula
`0.60*(22/28)^2.5` does not produce 0.48 fJ. These unused energy constants are
not a calibrated replacement for the missing search-energy model. Likewise,
`176 * 0.619 fJ * 500 MHz` is not the fixed 0.249 mW TCAM power.

## Primary-source checks

- Eslahi, Hamilton, and Khandelwal's ISCAS 2022 DAC record describes two shared
  resistor-string DACs occupying 70 um2, with static/dynamic power of
  0.12/0.155 mW for the pair. It does not substantiate this model's 328 um2 and
  0.05 mW per channel. Conditions and circuit boundaries must be reconciled
  before importing values. [University source record](https://researchers.mq.edu.au/en/publications/ultra-compact-and-linear-4-bit-digital-to-analog-converter-in-22n/)
- Stillmaker and Baas's 2017 work provides fitted, technology/voltage-dependent
  scaling models and a corrigendum. The project's mixed factors are not
  verified by naming that method. [Author-hosted source](https://vcl.ece.ucdavis.edu/pubs/2017.02.VLSIintegration.TechScale/)
- A primary ADC source could not be located from the supplied
  “Haraldstad & Nentwich, NTNU 2023” attribution in this round's bounded search.
  This is an unresolved citation, not proof that a source does not exist.

No bibliography or manuscript was changed. No new literature constants were
inserted into the simulator.

## Repairs and remaining decision

The code now rounds delays upward, honors power overrides in both modes,
rejects unsupported node/clock/network configurations and invalid modes, and
labels returned costs as uncalibrated. SRAM node-creation/backprop counters now
use completed events. Their metadata explicitly excludes child-pointer traffic,
board transfers, and physical bank accesses. The legacy moves-throughput field
now counts neural board evaluations, including the initial root, instead of
assuming twenty moves per iteration.

Before replacing physical totals, establish one evaluator-to-array mapping:
signed weight representation and precision, converter sharing at both layers,
intermediate storage, and the single-inference schedule. Pair it with the
memory layout/ports and a consistent digital-cost source. Those are the next
hardware-model decisions. A full sweep before those decisions would reproduce
the unresolved assumptions across more rows.
