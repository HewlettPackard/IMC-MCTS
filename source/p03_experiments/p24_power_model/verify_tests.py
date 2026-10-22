# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Record the full simulator suite and the exact source bytes it exercised.
# SPDX-License-Identifier: MIT
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from core.architecture.result_registry import new_run, write_json

ROOT=Path(__file__).resolve().parents[2]


def main():
    out=new_run(Path(__file__).parent/'p00_runs')
    paths=list((ROOT/'core').rglob('*.py'))+list((ROOT/'core/architecture').glob('*.json'))
    paths+=list((ROOT/'tests').glob('test_*.py'))+list((ROOT/'p05_studio/p00_app').glob('*.py'))
    paths.append(Path(__file__).with_name('replay.py'))
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    write_json(out/'source_sha256.json',sources)
    cmd=[sys.executable,'-B','-m','unittest','discover','-s','tests','-v']
    print(out.relative_to(ROOT),flush=True)
    with (out/'tests.txt').open('w') as log:
        result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    text=(out/'tests.txt').read_text()
    (out/'tests.txt.gz').write_bytes(gzip.compress(text.encode(),mtime=0));(out/'tests.txt').unlink()
    changed=[name for name,digest in sources.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
    write_json(out/'metadata.json',{'status':'passed' if result.returncode==0 and not changed else 'failed',
        'command':cmd,'exit_code':result.returncode,'changed_sources':changed,'benchmarks_executed':False})
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file()))
    print(text[-1800:],flush=True)
    if result.returncode or changed: raise RuntimeError('Suite failed or sources changed during verification')


if __name__=='__main__': main()
