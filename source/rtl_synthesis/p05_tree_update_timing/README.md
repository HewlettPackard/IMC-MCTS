# Tree-update timing candidate

This revision breaks the board-count / variable-remainder / address-addition
path reported at -1.84 ns slack in the native 65 nm synthesis of the earlier
tree-update implementation. It is a separate candidate for characterization.
The active simulator, original RTL file and all old physical reports remain
bound to their existing revision until new matching reports are returned.

| File | Role |
| --- | --- |
| `p00_rtl/imc_tree_update.sv` | Revised parent: balanced count tree, registered count/mask, iterative choice and registered selected-child address |
| `../p01_mapped_core/p00_rtl/imc_round_divider.sv` | Unchanged divider source; instantiated as NUM_W=32, DEN_W=7 for 9x9; exact remainder is used, rounded quotient is unused |
| `../p03_iteration_core/p00_rtl/imc_q17_codec.sv` | Unchanged backpropagation value codec |

The top module and ports are unchanged. Default characterization parameters
are BOARD_SIZE=9, CAM_ENTRIES=1024, NEURAL_BYTES=16512 and ADDR_W=21.
NODE_BYTES=1572864 and CHILD_BYTES=524288 retain their defaults.
One instance serves expansion and backpropagation. The parent area includes
both `u_choice` and `u_codec`; do not add their standalone areas again.

## Timing and behavioral contract

A balanced count feeds the existing count/mask registers in ST_COUNT. The
new ST_CHOICE_START (debug value 23) and ST_CHOICE_WAIT (24) run the exact
32-bit remainder calculation. Earlier debug-state encodings are unchanged.
The 9x9 divisor is bounded by 81 and uses seven bits. The shared source
derives this width from BOARD_SIZE for other configurations.

A successful nonempty expansion adds **35 controller cycles**. Skipped
expansion, full boards and backpropagation keep their previous schedules.
There are no additional SRAM transactions. At the simulator's assumed
2 ns cycle, the added time is 70 ns per actual expansion; physical clock
closure still requires synthesis. Child choices, valid result counters,
tree/SRAM contents, transaction order, error codes, poisoning and handshake
behavior are checked against the prior implementation. Result payloads are
not meaningful when result_error is nonzero, as in the existing core.

The candidate simulator adapter is
`p03_experiments/p22_tree_update_timing/candidate_model.py`. It charges the
additional cycles only when expansion creates children. It is used for
candidate validation and does not borrow the previous revision's area.

## Verification

From the repair checkout, using the existing Python environment:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -B -m p03_experiments.p22_tree_update_timing.verify_updates
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -B -m p03_experiments.p22_tree_update_timing.verify_updates --gates
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -B -m p03_experiments.p22_tree_update_timing.verify_complete
```

`p01_tests/run_syntax.sh` runs the compile/lint/remainder/module checks.
`filelist.f` selects the standalone candidate and its two dependencies.
`complete.f` and `buffered.f` replace only the update module inside the
existing complete cores for integration tests. Do not read both old and
new tree-update source files into the same design library.

Icarus emits known notices about conservative always_comb sensitivity and
ignored unique-case qualities. Verilator checks must have zero warnings.
Generic Yosys checks reject latches and remaining `$mod`/`$div` cells and
replay mapped Boolean logic. They do not establish TSMC area or delay.
Returned DC timing, constraints and capacitance checks remain required.
Native power reports remain vectorless diagnostics until matched gate
activity is supplied.

Verification evidence and the portable synthesis packet are owned by
`p03_experiments/p22_tree_update_timing/`, following the numbered folder and
UTC run conventions. This adds a candidate without reorganizing the repository.
