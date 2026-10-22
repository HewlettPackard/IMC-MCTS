#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
imc_root=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
cd "$imc_root"
exec "${IMC_PYTHON:-python3}" -B -m p03_experiments.p18_buffered_hardware.verify "$@"
