# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
# Native TSMC65 characterization settings for the tree-update candidate.
set TOP imc_tree_update
set PARAMETERS "BOARD_SIZE=9,CAM_ENTRIES=1024,NEURAL_BYTES=16512,ADDR_W=21"
set CLOCK_PERIOD_NS 2.0
set CLOCK_UNCERTAINTY_NS 0.05
set CLOCK_TRANSITION_NS 0.10
set IO_DELAY_NS 0.20
set OUTPUT_LOAD_PF 0.01
set INPUT_DRIVER "BUF_X1M_A12TR/Y"
set RESET_EXCEPTION "set_false_path -from rst_n"
set imc_rtl_root [file normalize [file join [file dirname [info script]] ..]]
set RTL_FILES [list \
    [file normalize [file join $imc_rtl_root ../p01_mapped_core/p00_rtl/imc_round_divider.sv]] \
    [file normalize [file join $imc_rtl_root ../p03_iteration_core/p00_rtl/imc_q17_codec.sv]] \
    [file join $imc_rtl_root p00_rtl/imc_tree_update.sv]]
