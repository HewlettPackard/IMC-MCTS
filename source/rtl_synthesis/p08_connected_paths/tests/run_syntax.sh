#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
set -euo pipefail
flow=$(cd "$(dirname "$0")/.." && pwd)
output=${1:-$(mktemp -d)}
mkdir -p "$output"
cd "$flow"
files=()
while IFS= read -r file; do [[ -z "$file" ]] || files+=("$file"); done < filelist.f
iverilog -g2012 -tnull "${files[@]}" 2> "$output/syntax.log"
for top in imc_selection_path imc_readout_path; do
    verilator --lint-only -Wall --top-module "$top" "${files[@]}" > "$output/lint_$top.log" 2>&1
done
for top in tb_connected_ucb tb_connected_neural tb_selection_protocol tb_readout_protocol; do
    iverilog -g2012 -s "$top" -o "$output/$top" "${files[@]}" "p01_tests/$top.sv" 2> "$output/compile_$top.log"
    if [[ "$top" == tb_connected_ucb || "$top" == tb_connected_neural ]]; then
        kind=${top#tb_connected_}
        for window in 110 2500 5000; do
            vvp "$output/$top" "+INPUT=$flow/p02_inputs/${kind}_${window}.txt" "+VCD=$output/${kind}_${window}.vcd" > "$output/${kind}_${window}.log"
        done
    else
        vvp "$output/$top" > "$output/$top.log"
    fi
done
printf 'PASS: connected RTL syntax, zero-warning lint, six workload windows and two protocol tests\n'
