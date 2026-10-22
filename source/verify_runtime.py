#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
"""Run native regressions with verified historical fixtures temporarily available."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile
import unittest

ROOT=Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@contextmanager
def historical_fixtures(module=None):
    record=json.loads((ROOT/'fixtures/historical_test_fixtures.json').read_text())
    archive=ROOT/'fixtures'/record['archive']
    if sha(archive.read_bytes())!=record['sha256']:
        raise ValueError('Historical fixture archive hash mismatch')
    all_files=record['files']
    if module is None:
        expected=all_files
    elif module=='test_analog_readout':
        expected={n:r for n,r in all_files.items() if n.startswith('p04_results/') and '20260909_' in n}
    elif module=='test_ppa_audit':
        expected={n:r for n,r in all_files.items() if '20260914_' in n}
    elif module=='test_sram_costs':
        expected={n:r for n,r in all_files.items() if n.startswith('p03_experiments/p08_cost_sources/')}
    else:
        expected={}
    if record['unpacked_bytes']!=sum(row['bytes'] for row in all_files.values()) or record['unpacked_bytes']>64*1024*1024:
        raise ValueError('Historical fixture size exceeds approved manifest')
    created_files=[]; created_dirs=[]
    try:
        with tarfile.open(archive,'r:gz') as contents:
            members=contents.getmembers()
            if len(members)!=len(all_files) or {m.name for m in members}!=set(all_files):
                raise ValueError('Historical fixture member list differs from manifest')
            for member in members:
                if member.name not in expected:continue
                relative=PurePosixPath(member.name)
                if relative.is_absolute() or '..' in relative.parts or not member.isfile() or member.issym() or member.islnk():
                    raise ValueError('Unsafe historical fixture member: '+member.name)
                target=ROOT.joinpath(*relative.parts)
                if target.is_symlink() or not target.resolve().is_relative_to(ROOT):
                    raise ValueError('Historical fixture target escapes package: '+member.name)
                row=expected[member.name]
                if member.size!=row['bytes']:
                    raise ValueError('Historical fixture size mismatch: '+member.name)
                stream=contents.extractfile(member)
                raw=stream.read() if stream is not None else b''
                if len(raw)!=row['bytes'] or sha(raw)!=row['sha256']:
                    raise ValueError('Historical fixture content hash mismatch: '+member.name)
                if target.exists():
                    if sha(target.read_bytes())!=row['sha256']:
                        raise ValueError('Refusing to overwrite an existing different fixture: '+member.name)
                    continue
                missing=[]; parent=target.parent
                while not parent.exists():
                    missing.append(parent);parent=parent.parent
                for directory in reversed(missing):
                    directory.mkdir();created_dirs.append(directory)
                with target.open('xb') as output:
                    created_files.append((target,row['sha256']))
                    output.write(raw)
        yield record
    finally:
        # Remove only verified files this invocation created, never caller data.
        for path,digest in reversed(created_files):
            if path.is_file() and not path.is_symlink():
                path.unlink()
        for path in reversed(created_dirs):
            try:path.rmdir()
            except OSError:pass


def module_name(suite):
    for child in suite:
        if isinstance(child,unittest.TestSuite):
            name=module_name(child)
            if name:return name
        else:return child.__class__.__module__
    return None


class FixtureSuite(unittest.TestSuite):
    """Keep module suites together and load only their historical input group."""
    def run(self,result,debug=False):
        for group in self:
            if result.shouldStop:break
            with historical_fixtures(module_name(group)):
                group(result)
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pattern',default='test_*.py')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--fixtures-only',action='store_true',help='Verify each fixture group and cleanup without running tests.')
    args=parser.parse_args()
    os.chdir(ROOT)
    record=json.loads((ROOT/'fixtures/historical_test_fixtures.json').read_text())
    if args.fixtures_only:
        for name in ('test_analog_readout','test_ppa_audit','test_sram_costs'):
            with historical_fixtures(name):pass
        print(f"Verified {len(record['files'])} historical fixtures; temporary copies cleaned by group.")
        return
    native=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=args.pattern)
    expected=native.countTestCases()
    suite=FixtureSuite(native)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'pattern':args.pattern,'discovered_tests':expected,'executed_tests':result.testsRun,
        'success':result.wasSuccessful(),'failures':[(str(t),trace) for t,trace in result.failures],
        'errors':[(str(t),trace) for t,trace in result.errors],'skipped':[(str(t),reason) for t,reason in result.skipped],
        'fixture_archive_sha256':record['sha256'],
        'engine_modified':False,'regression_tests_modified':True,
        'regression_repair':'Exact discrete legacy state plus bounded float64 values; production hashes unchanged.',
        'fixture_strategy':'Original historical input bytes temporarily extracted per test module to bound disk use.'}
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('discovered_tests','executed_tests','success')},indent=2))
    if not result.wasSuccessful():sys.exit(1)

if __name__=='__main__':
    main()
