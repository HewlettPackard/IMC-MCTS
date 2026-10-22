#!/bin/sh
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
set -eu
hardware_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 "$hardware_dir/verify.py" "$@"
