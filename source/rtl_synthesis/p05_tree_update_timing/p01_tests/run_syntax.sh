#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
set -euo pipefail
imc_root="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$imc_root"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 "${PYTHON:-python3}" -B -m p03_experiments.p22_tree_update_timing.verify_updates "$@"
