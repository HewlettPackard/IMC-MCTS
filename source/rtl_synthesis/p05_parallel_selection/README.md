# Four-lane selection batch

This is an opt-in arithmetic batch for the repaired single-child search. The
serial reference and its RTL remain unchanged. The new wrapper instantiates
four unchanged, source-matched `imc_ucb_score` units. It does not yet replace
the complete selection/SRAM controller in the older RTL top.

| File | Block | Synthesis role |
| --- | --- | --- |
| `p00_rtl/imc_ucb_batch.sv` | Four scorers, IDs/results, ordered reduction and held result | `four_UCB_parents_plus_selection_dispatch_and_result_registers` |
| `../p03_iteration_core/p00_rtl/imc_ucb_score.sv` | Reused correct Q32 UCB primitive | Four separately priced UCB parents |

One request contains one to four **visited** children in original list order.
The caller loads operands serially using the existing single 32-bit SRAM port,
then drives the four register slots together. Child ID, visit count and value
need 512 caller-side register bits. That register buffer is outside this batch
wrapper and included in the explicit selector cost proxy. Parent visits and
exploration are shared. There is no extra SRAM and no loading/scoring overlap.

Equal scores retain the first child; batches must also be merged in their
original order with a strict greater-than comparison. Unvisited-child priority
belongs to the caller. Any active-lane arithmetic error invalidates the whole
batch. Inactive lanes are ignored. Inputs may change after acceptance. Outputs
remain stable until accepted, and asynchronous reset aborts all work.

## Checked schedule

For a valid batch of `N` children, acceptance to registered result takes
`223 + N` cycles. Each used arithmetic unit has 223 active cycles. The model
adds two caller request/capture cycles, for **`225 + N` service cycles**.
Thus four scores cost 229 service cycles, rather than four serial 225-cycle
services. Operand SRAM reads, CAM work, candidate control and tree traversal
are charged separately. The serial scratch round trip (four writes plus four
reads per candidate) disappears, but its 16-byte allocation remains reserved.

These constants are in `core/architecture/parallel_selection.json`.
The directed test covers all batch sizes, ties, winners in different lanes,
nonzero log/exploration, held outputs, changed inputs, errors and reset. Its
port observations also check latency and per-lane occupancy.

Run from the project root:

```sh
sh rtl_synthesis/p05_parallel_selection/p01_tests/run_syntax.sh
```

Fresh UTC logs go into `p03_checks`. The script runs Icarus syntax, Verilator
lint and the self-checking simulation, without waveform output. Icarus reports
its existing dependency warnings about constant-select sensitivity and ignored
`unique` qualifiers; these are not waived Verilator warnings. Verilator must
exit with zero warnings.

`p02_syn/config.tcl` names the top, dependency list, intended 2 ns constraint
and required external library inputs for possible later characterization.
No foundry synthesis is run or required for this experiment. The wrapper's
inclusive area would include all four scorers; it must never be added to four
separately charged scorer areas. The complete incremental selector, caller
registers and full SRAM integration are still architectural service estimates.

The current cost model reuses four matching arithmetic reports, scales each
once from 65 to 22 nm, and retains the disclosed native65 leakage proxy.
Changed selector/control/storage costs use the full closest selector report
with an explicit 25% reserve and 0%/100% reserve sensitivity. That allowance
is not a measured bound. Logic checks establish neither 500 MHz physical
closure nor analog accuracy, complete-chip PPA or playing strength.
