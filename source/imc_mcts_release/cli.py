# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile

from . import __version__
from .artifacts import install_archive, overlay_artifacts, verify_store


import tarfile

def copy_runtime(output, source_root=None, manifest=None):
    source_root = Path(source_root) if source_root is not None else Path(__file__).resolve().parents[1]
    if manifest is None:
        manifest = json.loads(Path(__file__).with_name("runtime_files.json").read_text())
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}. Choose a new Studio workspace.")
    files = []
    for row in manifest["files"]:
        relative = PurePosixPath(row["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"Unsafe runtime path: {relative}")
        original = source_root.joinpath(*relative.parts)
        if original.is_symlink() or not original.resolve().is_relative_to(source_root.resolve()):
            raise ValueError(f"Runtime file is outside the installed package: {relative}")
        raw = original.read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError(f"Runtime integrity check failed: {relative}")
        files.append((original, relative))
    output.mkdir(parents=True, exist_ok=False)
    runtime = output / "runtime"
    runtime.mkdir()
    for original, relative in files:
        target = runtime.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
    return runtime


def execution_environment():
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["OMP_NUM_THREADS"] = "1"
    return env


def run_simulator(args):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--output", type=Path)
    options, forwarded = parser.parse_known_args(args)
    if "--help" in forwarded or "-h" in forwarded:
        print("Release option: --artifacts STORE selects approved checksum-verified external inputs.")
        import reproduce_runtime
        previous = sys.argv
        try:
            sys.argv = ["imc-mcts run", *forwarded]
            return reproduce_runtime.main()
        finally:
            sys.argv = previous
    if options.output is None:
        raise ValueError("--output is required")
    output = options.output.resolve()
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    verify_store(options.artifacts)
    forwarded += ["--output", str(output)]
    with tempfile.TemporaryDirectory(prefix="imc_mcts_runtime_") as folder:
        runtime = copy_runtime(Path(folder) / "workspace")
        overlay_artifacts(options.artifacts, runtime)
        return subprocess.call([sys.executable, "-B", "reproduce_runtime.py", *forwarded], cwd=runtime, env=execution_environment())


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "run":
        try:
            return run_simulator(args[1:])
        except (ValueError, OSError) as error:
            print(str(error), file=sys.stderr)
            return 2
    parser = argparse.ArgumentParser(description="IMC-MCTS research simulator and local Studio")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run", help="run the simulator with approved inputs; use run --help")
    studio = commands.add_parser("studio", help="launch Studio in a new writable workspace")
    studio.add_argument("--output", type=Path, required=True)
    studio.add_argument("--port", type=int, default=4784)
    studio.add_argument("--artifacts", type=Path, required=True)
    artifacts = commands.add_parser("artifacts", help="install a locally supplied optional input packet")
    artifact_commands = artifacts.add_subparsers(dest="artifact_command", required=True)
    install = artifact_commands.add_parser("install")
    install.add_argument("--archive", type=Path, required=True)
    install.add_argument("--output", type=Path, required=True)
    options = parser.parse_args(args)
    try:
        if options.command == "artifacts":
            location = install_archive(options.archive, options.output)
            print(f"Verified local artifact store: {location}")
            print("Installation does not grant redistribution permission.")
            return 0
        if not 1 <= options.port <= 65535:
            parser.error("--port must be between 1 and 65535")
        verify_store(options.artifacts)
        runtime = copy_runtime(options.output.resolve())
        overlay_artifacts(options.artifacts, runtime)
    except (ValueError, OSError, tarfile.TarError) as error:
        parser.error(str(error))
    print(f"Studio workspace: {runtime.parent}", flush=True)
    print(f"Local URL: http://127.0.0.1:{options.port}/", flush=True)
    try:
        return subprocess.call([sys.executable, "-B", "-m", "p05_studio.p00_app.server", "--port", str(options.port)], cwd=runtime, env=execution_environment())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
