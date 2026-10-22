#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DC_SHELL="/opt/synopsys/syn/U-2022.12-SP7-1/bin/dc_shell"
TCL_SCRIPT="$PROJECT_DIR/synth/run_dc.tcl"

run_one() {
    local run_name="$1"
    local top="$2"
    local params="$3"
    local sequential="$4"
    local result_dir="$PROJECT_DIR/results/$run_name"

    if [[ $# -gt 4 ]]; then
        shift 4
    fi
    if [[ $# -gt 0 ]]; then
        local selected=0
        local requested
        for requested in "$@"; do
            if [[ "$requested" == "$run_name" ]]; then
                selected=1
            fi
        done
        if [[ "$selected" -eq 0 ]]; then
            return
        fi
    fi

    mkdir -p "$result_dir"
    printf 'Starting %s (top=%s, parameters=%s)\n' "$run_name" "$top" "${params:-defaults}"
    (
        cd "$result_dir"
        PROJECT_DIR="$PROJECT_DIR" RUN_NAME="$run_name" TOP="$top" \
            PARAMS="$params" SEQUENTIAL="$sequential" \
            "$DC_SHELL" -no_gui -f "$TCL_SCRIPT" \
            >"$result_dir/synthesis.log" 2>&1
    )
    printf 'Finished %s\n' "$run_name"
}

requested=("$@")

run_one imc_cached_selector imc_cached_selector \
    "BOARD_SIZE=9,CAM_ENTRIES=1024,NEURAL_BYTES=16512,ADDR_W=21" 1 "${requested[@]}"
run_one imc_tree_update imc_tree_update \
    "BOARD_SIZE=9,CAM_ENTRIES=1024,NEURAL_BYTES=16512,ADDR_W=21" 1 "${requested[@]}"
run_one imc_ucb_score imc_ucb_score "" 1 "${requested[@]}"
run_one imc_neural_sequencer imc_neural_sequencer \
    "INPUTS=162,HIDDEN=96,ADDR_W=21,SRAM_BYTES=1572864" 1 "${requested[@]}"
run_one imc_buffered_neural_sequencer imc_buffered_neural_sequencer \
    "INPUTS=162,HIDDEN=96,ADDR_W=21,SRAM_BYTES=1572864" 1 "${requested[@]}"
run_one imc_column_hold_control imc_column_hold_control \
    "COLUMNS=128,ARRAYS=4" 1 "${requested[@]}"
run_one imc_shift_accumulator_32x32 imc_shift_accumulator \
    "ENTRIES=32,ADDR_W=5" 1 "${requested[@]}"
run_one imc_round_divider_48x32 imc_round_divider \
    "NUM_W=48,DEN_W=32" 1 "${requested[@]}"
run_one imc_round_divider_80x32 imc_round_divider \
    "NUM_W=80,DEN_W=32" 1 "${requested[@]}"
run_one imc_sram_router_3bank imc_sram_router \
    "BANKS=3,BANK_BYTE_W=19,ADDR_W=21" 1 "${requested[@]}"
run_one imc_sram_router_1bank imc_sram_router \
    "BANKS=1,BANK_BYTE_W=19,ADDR_W=21" 1 "${requested[@]}"
run_one imc_fixed_scale imc_fixed_scale "" 0 "${requested[@]}"
run_one imc_q17_codec imc_q17_codec "" 0 "${requested[@]}"
run_one imc_ln_table imc_ln_table "" 0 "${requested[@]}"
run_one imc_isqrt imc_isqrt "" 1 "${requested[@]}"
