# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Portable paths for the compiled Go tournament suite.

Override any default by exporting the matching environment variable before
running. Defaults assume this repo is checked out at IMC_MCTS_ROOT and
external tools (GnuGo) are installed on PATH or at standard locations.

Env vars:
  IMC_MCTS_ROOT  Root of the merged repo (default: auto-detected from this file's location)
  GNUGO_BIN      GnuGo executable (default: resolve ``gnugo`` from PATH)
  PACHI_BIN      Pachi executable (default: resolve ``pachi`` from PATH)
  KATAGO_BIN     KataGo executable (default: resolve ``katago`` from PATH)
  KATAGO_MODEL   KataGo model file
  KATAGO_CFG     KataGo GTP configuration file
"""
import os
import shutil

# Resolve the repository root first, then derive each experiment path from it.
ROOT = os.environ.get("IMC_MCTS_ROOT") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

def _executable(env_name, command, local_path):
    """Resolve an executable without assuming a developer-specific path."""
    return os.environ.get(env_name) or shutil.which(command) or local_path


# External Go engines. Environment variables can override these local defaults.
PACHI_DIR = os.environ.get("PACHI_DIR") or os.path.join(ROOT, "tools", "pachi")
PACHI_BIN = _executable("PACHI_BIN", "pachi", os.path.join(PACHI_DIR, "pachi"))

KATAGO_DIR = os.environ.get("KATAGO_DIR") or os.path.join(ROOT, "tools", "katago_bin")
KATAGO_BIN = _executable("KATAGO_BIN", "katago", os.path.join(KATAGO_DIR, "katago"))
KATAGO_MODEL = os.environ.get("KATAGO_MODEL") or os.path.join(KATAGO_DIR, "model.bin.gz")
KATAGO_CFG = os.environ.get("KATAGO_CFG") or os.path.join(KATAGO_DIR, "tournament.cfg")

GNUGO_BIN = _executable("GNUGO_BIN", "gnugo", "gnugo")

# Default dataset used by the compiled self-play experiments.
SELFPLAY_DATA = os.path.join(ROOT, "generalizability", "data", "selfplay_9x9_1000games.json")
