# Complete iteration core

The checked top is `imc_iteration_core`, with `imc_tree_update` and
`imc_ucb_score` also available independently. It reuses the unchanged
`p01_mapped_core` neural/primitive RTL and `p02_search_control` selector.
Read [the contract](../../core/architecture/COMPLETE_CORE_SPEC.md) for interfaces,
finite memory, exact arithmetic, reset/error behavior and cost boundaries.

From this directory, run `iverilog -g2012 -tnull -c filelist.f` or
`verilator --lint-only -Wall --top-module imc_iteration_core -f filelist.f`.
From the repository root, verify the active revision with:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -B -m p03_experiments.p23_tree_update_integration.verify_complete
```

The tree-update source is the accepted Round 22 candidate, with an exact
iterative remainder and 35 extra cycles per successful nonempty expansion.
The unchanged selector, neural, UCB, routers and iteration owner are reused.
The old p12 update testbench and experiment scripts describe revision 1;
replay them from checkpoint `52f94d6` or their preserved source snapshots.
Round 22 module/generic-gate evidence and the unchanged candidate-specific
testbenches live in `p05_tree_update_timing` and the p22 experiment.

The separate `p02_syn/` DC template requires the actual 65 nm library/corner
and explicit environment settings. The returned standalone module reports supply native 65 nm area.
The complete-core report is optional. Do not add separately synthesized
children to their inclusive parent, or a whole-core area to its module sum.
