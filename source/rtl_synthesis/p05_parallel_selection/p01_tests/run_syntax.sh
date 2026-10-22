#!/bin/sh
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
# Fresh logs and binaries only; no waveforms or foundry synthesis.
set -eu
IMC_BATCH_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$IMC_BATCH_DIR"
IMC_BATCH_OUT="$IMC_BATCH_DIR/p03_checks/run_$(date -u +%Y%m%d_%H%M%SZ)"
mkdir -p "$IMC_BATCH_DIR/p03_checks"
mkdir "$IMC_BATCH_OUT"
printf '%s\n' "$IMC_BATCH_OUT"
iverilog -V > "$IMC_BATCH_OUT/iverilog_version.log" 2>&1
verilator --version > "$IMC_BATCH_OUT/verilator_version.log"
iverilog -g2012 -s imc_ucb_batch -tnull -f filelist.f > "$IMC_BATCH_OUT/syntax.log" 2>&1
verilator --lint-only -Wall --top-module imc_ucb_batch -f filelist.f > "$IMC_BATCH_OUT/lint.log" 2>&1
iverilog -g2012 -s tb_imc_ucb_batch -o "$IMC_BATCH_OUT/test.vvp" -f filelist.f p01_tests/tb_imc_ucb_batch.sv > "$IMC_BATCH_OUT/test_compile.log" 2>&1
vvp "$IMC_BATCH_OUT/test.vvp" > "$IMC_BATCH_OUT/test.log" 2>&1
cat "$IMC_BATCH_OUT/test.log"
shasum -a 256 filelist.f p00_rtl/*.sv p01_tests/* > "$IMC_BATCH_OUT/source_sha256.txt"
while IFS= read -r IMC_BATCH_SOURCE; do
    test -z "$IMC_BATCH_SOURCE" || shasum -a 256 "$IMC_BATCH_SOURCE" >> "$IMC_BATCH_OUT/source_sha256.txt"
done < filelist.f
printf '%s\n' 'PASS: syntax, warning-free Verilator lint, directed batch tests' > "$IMC_BATCH_OUT/STATUS.txt"
