# Current parallel-digital characterization blocks

These separable RTL slices match current lane counts/storage widths and are for characterization. They do not replace the Python execution engine or constitute the complete integrated MCTS sequencer. Original RTL/reports remain unchanged. Super-T arrays and analog ADC behavior are outside RTL.

| File | Block | Cost role |
| --- | --- | --- |
| imc_shift_add_lane.sv | 12-bit ADC code, signed 32-bit shift/add, checked overflow | Bare arithmetic only, no bank mux/storage |
| imc_accumulator_bank.sv | 12-word bank plus one arithmetic child | Register/mux/control local cost separate from arithmetic child |
| imc_parallel_accumulators.sv | Eight banks, 96 partial sums | Inclusive once; do not add the eight children again |
| imc_parallel_result_banks.sv | Two 32x16 banks and 128-bit read mux | Result storage and ownership; explicit release after accumulation |
| imc_candidate_banks.sv | Two 16x128 banks | Operand storage only; SRAM loading/reduction control external |
| imc_ucb_batch16_overlap.sv | Sixteen reused overlap scorers and ordered reduction | Exclusive wrapper plus 16 children, or inclusive wrapper once |

Run `sh p01_tests/run_syntax.sh /absolute/fresh/output`. Icarus, Verilator and Yosys are required. The verification driver compiles the filelist, lints each top, runs the five directed TBs, and synthesizes four portable structural tops. Generic register/operator counts establish structure only; no foundry area, power, slack or full-system equivalence is implied. Parent bank storage is not a bare-ALU area.

Default bank ownership holds until explicit release. Same-edge release/capture of an occupied bank is rejected; the executable scheduler waits for bank availability. The external producer supplies a complete converted group. Conversion service (13 cycles), SRAM word loading, correction/division and full neural scheduling are external to these slices. Holding a group after readout permits the specified readout-then-accumulate schedule.

Foundry flow: set all IMC65 variables required in p02_syn/config.tcl, use a fresh IMC65_OUT, then run `dc_shell -f p02_syn/synth.tcl`. The config fails before creating output when library/context is missing. Supply actual library identity/corner/voltage/temperature/drive/load; do not guess a technology. Preserve a sha256sum of the filelist sources and library with reports. Pure arithmetic gets a 2 ns max delay; clocked tops get a 2 ns clock. Review check_design, constraints, hierarchy and operating point before adoption.

Matching gate-level workload VCD/SAIF, annotation coverage, clock-pin/internal versus physical-distribution power and target-process conversion remain separate acceptance gates. Vectorless reports are retained as provisional only. Existing p01_mapped_core synthesis and p25 power-activity workflows provide the next-stage report/coverage conventions. No generic structural result is loaded into the production cost model.
