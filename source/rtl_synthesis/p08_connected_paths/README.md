# Connected digital paths

| File | Block | Synthesis role |
|---|---|---|
| `p00_rtl/imc_selection_path.sv` | Six-word serial header loader, two candidate banks, UCB16 and ordered reduction | Complete connected selection region |
| `p00_rtl/imc_readout_path.sv` | Two ADC result banks, four-beat staging, eight accumulation banks | Complete connected digital readout region |

Selection consumes the little-endian `<IdIIHH` node header: visits, value low, value high, parent, child-list start, count/flags. Child ID arrives from the separate child-pointer interface with header word 0. Six accepted words per child publish the bank; IDs/visits/values connect directly to all sixteen lanes. The caller supplies parent visits and exploration at dispatch. The loader can fill the other bank while scoring. A bank stays owned through response backpressure. The header-ready handshake permits arbitrary SRAM stalls. Reset aborts loading and scoring.

Readout accepts padded 12-bit codes in 16-bit slots. One shared 512-bit staging register retains up to four 128-bit result-bank reads before up to four eight-lane add cycles. Result-bank count must equal consumed count, base must be eight-aligned, base+count <=96. Each column uses lane `column % 8`, register `column / 8`. Release occurs on the final add edge. `advance` stalls the consumer without releasing ownership. Invalid request metadata leaves the bank available for retry. Overflow reports error and preserves the affected accumulator word; already committed earlier words are not rolled back. Reset or clear flushes result/staging/accumulation state.

The 512-bit staging replaces the older cost model's 96-bit wider-bus-latch allowance. Physical storage is 4096 candidate bits, 1024 result bits, 512 staging bits, and 3072 accumulator bits, plus bounded metadata and the scorer's existing internal state. No separate full candidate gather or second bus latch is installed. Readout metadata is 35 bits; selection metadata including its error pulse is 26 bits. Existing 64-bit controller allowances remain engineering proxies. Current costs keep older inclusive parents and source-linked DFF/logic allocations; connected native-node PPA is pending.

Tests compare stored operands, integer outputs, bus masks, edge intervals, ownership, every partial count 1..32, stalled reads/adds/responses, invalid metadata and reset/clear during work. Digital replay uses three retained trained-search windows. Readout events are checked at the END edge of each modeled interval; ADC captures occur at conversion completion. RTL clock stimulus at 2 ns does not establish setup/hold closure, ADC ENOB or full-core correctness.

Run `tests/run_syntax.sh` (Icarus). Lint both tops with `verilator --lint-only -Wall`. For synthesis use `TARGET_DB=/path/to/native65_corner.db dc_shell -f syn/run.tcl`, from this directory. Preserve library/corner/tool/clock/IO details, RTL hashes, all check/timing/DRC reports and netlists. Vectorless power is provisional. Replay these same port-level tests against gate netlists, annotate workload activity and record coverage before adopting power. Never sum the inclusive selection top and its UCB children, or readout top and its banks, as separate area owners.

Boundary: RTL starts at digital SRAM header responses and ADC result codes. It does not synthesize the analog Super-T array, ADC, host Go rules, whole MCTS controller or memory macros. All existing historical slices and reports remain unchanged.
