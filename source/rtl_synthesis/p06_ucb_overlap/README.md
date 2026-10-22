# Four UCB scorers with overlapping arithmetic

This isolated candidate preserves the UCB formula and arithmetic modules.
It first divides the exploration ratio, then runs its square root alongside
the mean division. Two completion flags per scorer retain pulses until both
results are available. The square-root result stays in its existing output
register; no extra square-root or divider is instantiated. Score formatting,
rounding, input validation and the ordered batch reduction are unchanged.

| File | Role | Cost owner |
| --- | --- | --- |
| p00_rtl/imc_ucb_score_overlap.sv | Reordered scorer and completion tracking | Each UCB parent, uncharacterized |
| p00_rtl/imc_ucb_batch_overlap.sv | Four scorers and preserved batch control | Inclusive wrapper; do not add child area again |
| p01_tests/tb_imc_ucb_score_overlap.sv | Old/new/Python score agreement and interface checks | Verification only |
| p01_tests/tb_imc_ucb_batch_overlap.sv | Partial batches, ties, errors, reset and cycles | Verification only |
| p02_syn/config.tcl | Explicit optional characterization contract | No synthesis executed |

Shared codec, log ROM, divider and square-root sources are referenced from the
preserved RTL folders. No original source is edited. No waveform is generated.

Run from the checkout: `IMC_PYTHON=/path/to/python sh rtl_synthesis/p06_ucb_overlap/p01_tests/run_syntax.sh`.
The Python environment needs the existing project dependencies. The command
runs syntax, zero-warning Verilator lint and directed Icarus simulations.
Fresh evidence is saved in p03_checks. No server or foundry tool is invoked.

The checked standalone response takes 168 cycles after acceptance, versus
222 originally. The unchanged batch wrapper adds capture/reduction service:
`169 + valid_children` cycles. Including the two caller cycles gives
`171 + valid_children`; a full four-child batch is 175 modeled service cycles.
Per-lane parent busy occupancy is 169 cycles. These constants are in
core/architecture/ucb_overlap.json and must match the RTL tests.

The divider still executes two 80-bit divisions and the square-root unit
still executes 52 bit-pair steps. Reduced parent busy time must not be used
to claim proportionally reduced energy. Existing serial active-power reports
do not characterize simultaneous switching. Changed UCB costs are excluded
from known totals. Physical 500 MHz closure and PPA are not established.
