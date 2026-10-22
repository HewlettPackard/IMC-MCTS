# Digital blocks and neural controller for IMC-MCTS

Six synthesizable modules implement the complete neural path and reusable
arithmetic and word interfaces from the
[neural](../../core/architecture/NEURAL_SPEC.md) and
[SRAM](../../core/architecture/SRAM_SPEC.md) contracts. Full MCTS control remains
separate. The Python simulator exposes verified neural controller timing as
`neural_timing='rtl_serial_v1'`; physical costs remain unavailable.

| Source in `p00_rtl/` | Ownership | Default configuration |
| --- | --- | --- |
| `imc_shift_accumulator.sv` | Shared signed shift/add lane, register bank, read mux, validation | 32 signed 32-bit entries, 8-bit ADC input, shifts 0 through 11 |
| `imc_round_divider.sv` | Unsigned restoring division and nearest-even rounding | 48-bit numerator, 32-bit denominator, 32-bit remainder |
| `imc_sram_router.sv` | Aligned word decode, bank request, response holding and backpressure | Three 512 KiB banks, 21-bit byte addresses, 32-bit words; one-bank child instance |
| `imc_fixed_scale.sv` | Signed nearest-even scaling and 32-bit saturation | Signed 32-bit input, signed eight-bit shift |
| `imc_neural_sequencer.sv` | Both neural layers, activation, LUT/probability/value sequencing and ADC/SRAM control | 162-96-3 network, one row tile per layer, 16 active rows and three ADC lanes |
| `imc_neural_core.sv` | Sequencer plus one node SRAM router | Three 512 KiB synchronous bank interfaces |

Detailed ports, service edges, reset behavior, unimplemented dependencies and
cost ownership are in [DIGITAL_SPEC.md](../../core/architecture/DIGITAL_SPEC.md).
The complete inference interface, timing and errors are in
[NEURAL_RTL_SPEC.md](../../core/architecture/NEURAL_RTL_SPEC.md).

## Structure

- `p00_rtl/`: one module per file, no simulator-only constructs.
- `p01_tests/`: directed testbenches and verification runner.
- `p02_syn/`: explicit 65 nm library configuration and an unexecuted DC template.
- `filelist.f`: all six RTL sources, relative to this directory.

Outputs belong to the requesting experiment. Run from the repository root,
using a new output directory and an environment with NumPy, Icarus, Verilator
and Yosys installed:

```sh
PYTHON=python3 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  rtl_synthesis/p01_mapped_core/p01_tests/run_syntax.sh \
  --out p03_experiments/p09_digital_periphery/p00_runs/run_<UTC>/p02_rtl
```

The runner checks filelist syntax; Verilator `-Wall` for the default, five-entry,
one-bank and small-bank configurations; six RTL test programs; and four Yosys
generic netlists. It replays the 9x9 evaluator's ADC command sequence through
the synthesized accumulator, checks the divider's 12 mapped probability
calculations and directed edge cases, and replays both SRAM router variants.
Failures retain logs and commands. Existing outputs are never overwritten.

Golden accumulator outputs come from dense integer products, independent of
the sequential RTL. Vectors cover four deterministic diagnostic boards and
both neural layers. They do not establish task accuracy or analog fidelity.
`arithmetic_only.vcd.gz` deliberately omits analog and SRAM idle intervals and
must not be used for workload power annotation.

Icarus reports its constant-select sensitivity expansion and ignored
`unique case` qualifiers. Verilator has no warning waivers. Yosys checks for
undriven/conflicting signals and latches; generic post-synthesis replay has no
cell delays. Tool versions, exact argv, source hashes, compressed logs and
netlists are archived in each run. The [Round 10 report](../../p03_experiments/p09_digital_periphery/README.md)
records the observed results and two corrected defects caught by these checks.
Yosys reports replacing the accumulator's arrays with registers. This is the
intended implementation of the 32-entry digital register bank, not a missing
SRAM macro; the synthesized state count and replay check it explicitly.

The complete neural verification runs separately from the primitive tests:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -B \
  -m p03_experiments.p10_neural_sequence.run \
  --out p03_experiments/p10_neural_sequence/p00_runs/run_<UTC>
```

It checks six numerical fixtures, saturation, cross-bank addresses, stalls,
repeated requests, held results, reset and error propagation, then replays
small and full generic synthesized cores. Every ADC request and ordered SRAM
transaction is checked. Its 39 tool checks and exact source archives are in
the [Round 11 report](../../p03_experiments/p10_neural_sequence/README.md).
The new named Python schedule also matches every unstalled RTL state cycle.
The ADC provider and SRAM timing are explicit ideal boundary models.

## Design Compiler inputs

`python3 -B rtl_synthesis/p01_mapped_core/p02_syn/run_dc.py` requires:

| Environment variable | Required value |
| --- | --- |
| `IMC65_TARGET_DB` | Readable, authorized compiled 65 nm standard-cell library |
| `IMC65_LIBRARY_NAME`, `IMC65_CORNER` | Exact library and operating-condition names |
| `IMC65_VOLTAGE_V`, `IMC65_TEMPERATURE_C` | Supply and temperature for that corner |
| `IMC65_DRIVING_CELL`, `IMC65_LOAD_PF` | Valid input driver and positive output load |
| `IMC65_OUT` | New experiment-owned directory, inside the repair checkout |

The template targets a 2 ns clock, 0.05 ns uncertainty, 0.1 ns clock transition,
and 0.2 ns input/output delays. These are declared constraints, not timing
closure evidence. Review library units and corner voltage/temperature against
the supplied labels before accepting any report. Standard-cell area excludes
SRAM macros, analog blocks, placement/routing and physical-only cells.
The scale lane receives a combinational maximum-delay constraint. The new
sequencer/core tops include their arithmetic children; do not add child costs
again when using an integrated top's area or power report. `run_dc.py` hashes
the filelist along with RTL and synthesis inputs.

DC and the required library are unavailable in the current session. Only the
missing-input/tool paths were exercised; the DC command flow is not validated.
It intentionally emits no power estimate. Gate-level activity from the actual
workload, source-to-instance correspondence, annotation coverage, leakage and
idle-state treatment must be established before power characterization.

Keep raw digital reports at 65 nm. Apply a documented conversion to 22 nm once
in a separate provenance record; this script performs no conversion. Native
22 nm CACTI SRAM and native NeuroSim probes do not receive that conversion.
