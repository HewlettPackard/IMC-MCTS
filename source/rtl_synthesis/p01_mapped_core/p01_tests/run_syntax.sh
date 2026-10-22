#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "${PYTHON:-python3}" -B "$script_dir/verify.py" "$@"
