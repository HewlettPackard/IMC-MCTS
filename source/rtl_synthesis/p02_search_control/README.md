# Packed selection and neural control

`p00_rtl/imc_cached_selector.sv` implements bounded packed-SRAM selection,
FIFO parent-list CAM caching and ordered candidate control. The external
score interface preserves binary64 UCB semantics; arithmetic is not yet
implemented here. `imc_search_core.sv` serializes selection and the unchanged
neural sequencer through one node SRAM router, with a separate child router.

The [interface/storage contract](../../core/architecture/SEARCH_RTL_SPEC.md)
defines the memory map, added buffers, handshakes, reset and error behavior.
The [Round 12 experiment](../../p03_experiments/p11_cached_selection/README.md)
records reference traffic, verification and remaining limits.

- `p00_rtl/`: selector and explicit structural wrapper.
- `p01_tests/`: full SRAM/CAM/score/ADC integration and logical SRAM error tests.
- `p02_syn/`: separate, unexecuted 65 nm Design Compiler flow.
- `filelist.f`: new RTL and exact existing neural/peripheral dependencies.

Run from the repository root, with NumPy, Icarus, Verilator and Yosys:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -B \
  -m p03_experiments.p11_cached_selection.run \
  --out p03_experiments/p11_cached_selection/p00_runs/run_<UTC>
```

Use a fresh output directory. The runner archives exact sources, commands,
fixtures, compressed logs, events and generic netlists, including failures.
Two parameter sets exercise non-power-of-two seven-row caching and the
1,024-row 9x9 configuration. These are diagnostic placement trees, not trained
application results. The wrapper generator is a development helper; ordinary
simulation/synthesis uses the checked-in explicit SV file directly.

The 65 nm flow requires the same explicit library/corner/voltage/temperature,
driver/load variables as the [neural flow](../p01_mapped_core/README.md).
`IMC65_OUT` must be a new path inside this experiment's `p00_runs/` directory.
`python3 -B rtl_synthesis/p02_search_control/p02_syn/run_dc.py` hashes every
filelist dependency, including reused modules outside this RTL directory.
Targets are the standalone selector and integrated search core; their costs
are alternative boundaries and must not be summed. Constraints remain 2 ns,
0.05 ns uncertainty, 0.1 ns clock transition and 0.2 ns I/O delay, subject to
library/corner review. The script emits no power estimate or scaling.

No DC/library run or physical timing closure has been established. The
existing Round 11 filelist and RTL remain byte-identical so its named Python
neural timing and prior evidence keep their original identity.
