# Buffered column readout RTL

These separate variants add a capture handshake before shared ADC readout.
The original driven-array RTL remains byte-identical. The generator checks
its source identity and applies explicit transformations; generated sources
are committed so synthesis does not require source rewriting.

| File | Block | Synthesis role |
| --- | --- | --- |
| `p00_rtl/imc_column_hold_control.sv` | One live bank, capture ownership, ordered sample consumption | `column_capture_and_ownership_control` |
| `p00_rtl/imc_buffered_neural_sequencer.sv` | Original sequencer plus capture state and drive gating | Buffered inference controller |
| `p00_rtl/imc_buffered_neural_core.sv` | Neural controller, datapath and SRAM router | Integrated inference, includes ownership control |
| `p00_rtl/imc_buffered_iteration_core.sv` | Complete placement-search controller and shared resources | Integrated digital core, includes both preceding subblocks |

Do not add standalone and integrated synthesis areas together. Generic gate
counts are structural checks, with no process-node area or delay claim.
Compatible 65 nm reports are still needed, followed by one documented
conversion to 22 nm. Native 22 nm CACTI SRAM and workbook CIM cells must not
be scaled again.

`column_capture_valid && column_capture_ready` accepts all mapped columns on
one clock edge. Array identity, row inputs and column count remain stable
under capture backpressure. The array stays enabled until that handshake,
then turns off. Mux/sample controls consume consecutive groups from the
external analog bank. Each final sample releases ownership; the three ADC
input S/H lanes retain their own samples through conversion. Clear/reset and
failed inference discard the external bank. Invalid ownership requests are
rejected and propagate neural error 8. No overwrite or compute overlap is
supported. The external responder must share reset and `column_bank_clear`.

The controller tracks one active owner, while the architecture installs one
128-slot analog bank per array. It does not implement those analog cells.
Current-to-voltage conversion, switches, capacitor leakage, reference drive,
ADC accuracy, wires and physical timing remain outside RTL. Ideal testbench
column values are frozen at capture, then sampled into ADC input registers;
they are not regenerated from a live array during conversion.

The Python constant `CAPTURE_CYCLES=1` means one nominal clock cycle at
500 MHz. The 9x9/H96 schedule has 81 captures, 26,701 inference cycles, 405
array-enable cycles, and a longest unstalled column hold of 674 cycles
(1,348 ns). Arbitrary ADC/memory stalls can extend retention without limit.
A real circuit needs a bounded service-stall contract or adequate retention;
the current 1,348 ns value is not a worst-case guarantee.

From the repair checkout:

```sh
python -B -m p03_experiments.p18_buffered_hardware.generate_rtl
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 sh rtl_synthesis/p04_column_hold/p01_tests/run_syntax.sh
```

The default runner checks syntax, warning-free RTL lint, directed ownership,
full/ragged inference, reset/errors/reuse, complete placement jobs, all SRAM
transactions and phase cycles, plus zero-delay generic gate replay. `--smoke`
runs a smaller subset. Set `IMC_PYTHON` if the Python with NumPy is not on PATH.

`p02_syn/config.tcl` and `run_dc.py` require the actual library/corner through
the same `IMC65_*` inputs as the prior complete-core flow. `IMC65_OUT` must be
a fresh UTC directory under the p18 experiment. These templates produce
native 65 nm area/timing reports and intentionally no unannotated power cost.
They have not been run in Design Compiler here: tool and cell library are
unavailable. Gate activity, annotation coverage, constraints and report units
must be reviewed before costs are adopted. Go rules and host interfaces are
outside this placement-search RTL validation.
