# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
dc = shutil.which('dc_shell')
if dc is None:
    raise SystemExit('dc_shell unavailable; no 65 nm result generated')
config = subprocess.run(['tclsh', str(HERE/'config.tcl')], capture_output=True, text=True)
if config.returncode:
    raise SystemExit(config.stderr)

out = Path(os.environ['IMC65_OUT']).resolve()
library = Path(os.environ['IMC65_TARGET_DB']).resolve()
root = HERE.parents[2]
if not out.is_relative_to(root/'p03_experiments/p18_buffered_hardware/p00_runs'):
    raise SystemExit('IMC65_OUT must be inside the buffered-hardware experiment runs')
source_paths = [HERE.parent/'filelist.f'] + sorted(HERE.glob('*.*'))
source_paths += [(HERE.parent/line.strip()).resolve()
    for line in (HERE.parent/'filelist.f').read_text().splitlines() if line.strip()]
metadata = {'source_node_nm': 65, 'target_node_nm': 22, 'conversion_applied': False,
    'dc_shell': dc, 'library_path': str(library), 'library_sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
    'inputs': {key: os.environ[key] for key in ('IMC65_LIBRARY_NAME', 'IMC65_CORNER', 'IMC65_VOLTAGE_V',
        'IMC65_TEMPERATURE_C', 'IMC65_DRIVING_CELL', 'IMC65_LOAD_PF')},
    'source_sha256': {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths},
    'power_status': 'not characterized; gate-level workload activity and coverage required',
    'adopted_for_chip': False}
out.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='dc_launch_', dir=out.parent) as launch:
    result = subprocess.run([dc, '-f', str(HERE/'synth.tcl')], cwd=launch, capture_output=True, text=True)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(launch, out/'p00_launch')
(out/'dc.stdout.txt').write_text(result.stdout)
(out/'dc.stderr.txt').write_text(result.stderr)
metadata['returncode'] = result.returncode
(out/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
raise SystemExit(result.returncode)
