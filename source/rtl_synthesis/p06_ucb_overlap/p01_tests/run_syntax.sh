#!/bin/sh
# Local syntax, lint and exact directed simulation only; no waveforms or DC.
set -eu
IMC_UCB_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
cd "$IMC_UCB_ROOT"
PYTHONPATH="$IMC_UCB_ROOT" "${IMC_PYTHON:-python3}" -B -m p03_experiments.p77_ucb_overlap.run_rtl
