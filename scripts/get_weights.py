#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Obtain the trained model weights for IMC-MCTS.

The trained Go position-evaluation networks are NOT committed to this
repository, for two reasons:

  1. They are self-trained model weights. Self-trained weights need a separate
     public-release review before they can be distributed.
  2. Several checkpoints are Python pickles, and unpickling executes arbitrary
     code. We do not want a cloned user to load an untrusted `.pkl`.

This helper documents where the weights belong and how to get them back. Two
paths are supported:

  --regenerate  Print the ordered commands that retrain the weights locally
                from the self-play scripts. Reproducible, needs no external host.
  --download    Fetch a pre-trained bundle from a hosted URL and unpack it into
                the expected directories. The bundle is not published yet.

With no flag, it reports which weight directories are currently present.
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Each entry: where a family of weights lives, and the command that regenerates
# it from scratch. Paths are relative to the repository root.
WEIGHT_TARGETS = [
    (
        "tournament/go_compiled/weights",
        "python -m tournament.go_compiled.training.selfplay_iterative",
    ),
    (
        "generalizability/weights/selfplay_weights_9x9",
        "python -m generalizability.training.train_improved",
    ),
    (
        "cpu-gpu-benchmarking/weights",
        "python cpu-gpu-benchmarking/weights/convert_weights_to_binary.py",
    ),
]

# Set this only after a public weights bundle has been reviewed and approved.
# It should point at a .tar.gz that unpacks into the directories listed above.
WEIGHTS_URL = ""


def _has_weights(directory: Path) -> bool:
    """True if the directory exists and holds at least one weight file."""
    if not directory.exists():
        return False
    return any(directory.rglob("*.pkl")) or any(directory.rglob("*.bin"))


def show_status() -> None:
    """Report where weights belong and whether they are currently present."""
    print("Trained weights are not shipped with this repository.\n")
    print("Expected locations:")
    for rel_dir, _regen_cmd in WEIGHT_TARGETS:
        present = _has_weights(REPO_ROOT / rel_dir)
        marker = "present" if present else "missing"
        print(f"  [{marker:>7}]  {rel_dir}")
    print("\nRun with --regenerate to retrain locally, or --download to fetch a")
    print("hosted bundle. See `--help` for details.")


def regenerate() -> None:
    """Print the ordered commands that retrain the weights from scratch."""
    print("Regenerate the weights by running these from the repository root:\n")
    for rel_dir, regen_cmd in WEIGHT_TARGETS:
        print(f"  # -> {rel_dir}")
        print(f"  {regen_cmd}\n")
    print("Training first needs the datasets built by the matching")
    print("`*/training/` data-generation scripts. See REPRODUCIBILITY.md for the")
    print("full order.")


def _safe_extract(archive: tarfile.TarFile, dest: Path) -> None:
    """Extract an archive, rejecting any member that escapes `dest`."""
    dest = dest.resolve()
    for member in archive.getmembers():
        target = (dest / member.name).resolve()
        if not str(target).startswith(str(dest)):
            raise RuntimeError(f"Unsafe path in archive: {member.name}")
    archive.extractall(dest)


def download() -> None:
    """Fetch and unpack a hosted weights bundle into the expected directories."""
    if not WEIGHTS_URL:
        print("No hosted weights bundle is published yet (WEIGHTS_URL is empty).")
        print("Use --regenerate to retrain locally instead.")
        raise SystemExit(1)

    print(f"Downloading weights bundle from {WEIGHTS_URL} ...")
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        urllib.request.urlretrieve(WEIGHTS_URL, tmp.name)
        bundle = Path(tmp.name)

    # NOTE: only point WEIGHTS_URL at a trusted, self-produced bundle.
    print(f"Unpacking into {REPO_ROOT} ...")
    with tarfile.open(bundle) as archive:
        _safe_extract(archive, REPO_ROOT)
    bundle.unlink()
    print("Done.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--regenerate",
        action="store_true",
        help="print the commands to retrain the weights locally",
    )
    group.add_argument(
        "--download",
        action="store_true",
        help="download a hosted weights bundle (URL pending)",
    )
    args = parser.parse_args()

    if args.regenerate:
        regenerate()
    elif args.download:
        download()
    else:
        show_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
