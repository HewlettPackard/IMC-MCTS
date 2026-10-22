# IMC-MCTS module activity and glue characterization

This packet uses the returned TSMC65 modules from synthesis0909 `bf33a61`,
including tree-update v2. It characterizes the existing 9x9/H96/CAM1024 design.
The other board/model shapes need their own synthesis and activity records.
The complete controller is a simulation harness. Whole-core synthesis is
not required. Native power reports remain 65 nm until a separate, justified
22 nm process conversion is available.

## Contents

- `p00_rtl`: unchanged current digital sources and complete controller.
- `p01_tests`: existing self-checking SRAM/CAM/ADC workload responders,
  instrumented for a 2 ns clock and an exact core-cycle activity window.
- `p02_fixtures`: empty and nearly full 9x9 boards for both analog readouts.
  The latter exercises visited-child UCB work. These are seeded random-model
  diagnostics, not trained Go strength or the 5,000-iteration canonical case.
- `p03_native`: seven matching module DDCs, mapped netlists and constraints.
- `p04_glue`: standalone orchestration RTL for each readout plus reconstruction
  wrappers. Only one variant is installed. Child modules are boundary ports.
- `p05_flow`: portable replay, power analysis and glue-only synthesis scripts.

## Local replay

Requires Python 3.9+, Icarus Verilog and vvp. Run from this folder:

```sh
python3 p05_flow/replay.py rtl
python3 p05_flow/replay.py glue
```

Each command creates a new `p06_runs/run_...` directory. All final SRAM words,
ordered transactions, ADC outputs, iteration state and modeled cycles must
pass the original self-checking testbench. `glue` reconstructs the controller
from the projected glue and six unchanged child modules. This validates the
projection; no production RTL or scheduler is replaced.

## Server power analysis

Use the same TT, 1.00 V, 25 C library as the returned synthesis. Supply a text
file with one matching standard-cell Verilog/UDP model path per line. Paths
are relative to that file or absolute. Keep the cell model and .db on your
server; they are dependencies, not files to upload to the repository.

```sh
export IMC65_TARGET_DB=/home/PDK/TSMC65/ARM/core_fb/db/sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c.db
export IMC65_CELL_FILELIST=/absolute/path/to/tsmc65_cell_models.f
export DC_SHELL=/opt/synopsys/syn/U-2022.12-SP7-1/bin/dc_shell
export VCD2SAIF=/absolute/path/to/vcd2saif
python3 p05_flow/replay.py gate
```

Optional trailing fixture names select a subset, for example `gate driven_ragged`.
The runner replaces one installed parent at a time with its exact mapped
netlist. Prefixes distinguish gate module *types* from the remaining RTL;
instance/net names inside that parent stay unchanged for the DDC/SAIF binding.
Nested children already belong to that parent and are not separately billed.

This is functional zero-delay gate replay. It checks data and controller
cycles, not physical clock closure or delay-dependent glitches. No `specify`
timing is enabled. If the PDK models require vendor simulator options, retain
the failure log and use the same generated harness with the supported
simulator. Do not use behavioral guesses for unknown standard cells.

The captured interval starts after the job-accept edge at cycle_count=0 and
ends at the completed result. VCD timestamps are rebased to zero; duration
must equal exactly `core_cycles * 2 ns`. Reset, preload and display pauses
are excluded. Idle cycles *inside* the search and ungated module clocks are
included. The original final-state checks run after capture stops.

The flow reads the existing DDC and SDC without resynthesis and writes native
annotated power, area, timing, library/units and `report_saif` coverage.
Review annotation coverage at the correct hierarchy, including all clocks,
registers, known-zero/constant signals and any unexplained unannotated nets.
Require at least 99% annotated eligible nets with all remaining exclusions
listed and justified; this is a project acceptance criterion, not a vendor
accuracy guarantee. Unknown X/Z activity, unexplained unmapped nets, wrong
PVT or different area/source identities block admission.

`window.json` records duration and cycles. Native workload energy in pJ is
`dynamic_mW * duration_ns + leakage_mW * duration_ns`. Report both terms.
Do not multiply the resulting average power by active-phase cycles again.
The short fixtures establish calibration samples. Applying their average
power to an arbitrary longer search requires workload representativeness
checks; no automatic extrapolation or 22 nm power adoption is performed.

## Glue-only synthesis

These projected modules contain the existing controller FSM, shared registers,
arbitration muxes and request/response routing. They contain no selector,
tree-update, UCB, neural, SRAM router or analog macro instances. Fixed child
boundary widths restrict this packet to BOARD_SIZE=9, HIDDEN=96, CAM_ENTRIES=1024,
ADDR_W=21. Do not change those parameters for these generated modules.

For each of `imc_iteration_glue` and `imc_buffered_iteration_glue`:

```sh
export IMC_GLUE_TOP=imc_iteration_glue
export IMC_GLUE_OUT="$PWD/p06_runs/glue_driven_$(date -u +%Y%m%d_%H%M%SZ)"
"$DC_SHELL" -no_gui -f p05_flow/synth_glue.tcl
```

The output must be a fresh directory. Capture the terminal synthesis log too.
Return area/QoR/timing/constraints/check_design/units, mapped.v, mapped.ddc,
applied.sdc and vectorless power. Include the tool version, library SHA-256,
library/corner/voltage/temperature and packet manifest SHA-256. Vectorless
glue power is diagnostic only. A returned netlist also needs workload replay
before its energy can be used.

## Return and limits

Return new `p06_runs` results and their hashes through the private synthesis
repository. Retain all existing report folders. Do not upload PDK/library
contents. There is no local Design Compiler or foundry library in the repair
environment, so vendor execution and mapped-cell replay are pending the
server. Successful RTL/glue replay does not establish a server power result.

Analog CAM, row drivers, ADC/reference/mux and sample/hold costs require
matching circuit characterization separately. The mentor workbook's temporal
integrator/sequential-comparator reference is not the active binary/shared-ADC
circuit. Its already converted 22 nm driver terms must not be scaled again.
