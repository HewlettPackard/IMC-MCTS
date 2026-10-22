# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Release the verified portable packet without copying local simulation build products.
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import zipfile

from core.architecture.result_registry import new_run, write_json
from p03_experiments.p24_power_model.verify_packet import verify_packet

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
BASE=HERE/'p01_packets/run_20260910_023235Z'
RTL=HERE/'p01_packets/run_20260910_023011Z/p06_runs/run_20260910_023033Z'
GLUE=BASE/'p06_runs/run_20260910_023406Z'
PROOFS={'rtl':RTL,'glue':GLUE,'syntax_lint':HERE/'p00_runs/run_20260910_023900Z',
    'generic_structure':HERE/'p00_runs/run_20260910_024440Z',
    'python_tests':HERE/'p00_runs/run_20260910_025655Z','browser':HERE/'p00_runs/run_20260910_024810Z'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_files(folder):
    for line in (folder/'SHA256SUMS').read_text().splitlines():
        wanted,name=line.split('  ',1);path=(folder/name).resolve()
        if not path.is_relative_to(folder.resolve()) or digest(path)!=wanted:
            raise ValueError('Evidence bytes changed: '+name)


def main():
    metadata={}
    for name,path in PROOFS.items():
        verify_files(path)
        metadata[name]=json.loads((path/'metadata.json').read_text())
        if metadata[name]['status']!='passed': raise ValueError('Incomplete verification: '+name)
    for name in ('rtl','glue'):
        if len(metadata[name]['results'])!=4: raise ValueError('Expected four complete fixtures')
        for row in metadata[name]['results']:
            if row['window']['unknown_value_events']!=0: raise ValueError('Unknown activity remains')
    verify_files(BASE)
    original=RTL.parents[1]
    shared={}
    for folder in ('p00_rtl','p01_tests','p02_fixtures'):
        for path in (BASE/folder).rglob('*'):
            if path.is_file():
                name=str(path.relative_to(BASE))
                if digest(path)!=digest(original/name): raise ValueError('RTL and glue replay inputs differ: '+name)
                shared[name]=digest(path)
    release=new_run(HERE/'p02_release');out=release/'power_activity'
    shutil.copytree(BASE,out,ignore=shutil.ignore_patterns('p06_runs','SHA256SUMS'))
    for name in ('replay.py','power.tcl','synth_glue.tcl'):
        shutil.copyfile(HERE/name,out/'p05_flow'/name)
    shutil.copyfile(HERE/'PACKET.md',out/'README.md')
    shutil.copyfile(ROOT/'LICENSE',out/'LICENSE')
    (out/'22NM_SPEC.md').write_text((ROOT/'core/architecture/TECHNOLOGY_SPEC.md').read_text().replace('technology_scaling.json','22NM_POLICY.json'))
    shutil.copyfile(ROOT/'core/architecture/technology_scaling.json',out/'22NM_POLICY.json')
    shutil.copyfile(HERE/'p00_runs/run_20260910_023623Z/component_requests.csv',out/'COMPONENT_REQUESTS.csv')
    (out/'p07_validation').mkdir()
    for name,record in metadata.items(): write_json(out/'p07_validation'/(name+'.json'),record)
    write_json(out/'VALIDATION.json',{'status':'local_validation_passed','shared_rtl_fixture_sha256':shared,
        'proofs':{name:{'run':str(path.relative_to(ROOT)),'metadata_sha256':digest(path/'metadata.json')} for name,path in PROOFS.items()},
        'scope':'Four original RTL and four reconstructed glue workload replays; syntax/lint and generic structure checks. Exact cycles, all SRAM and ordered traffic checked.',
        'server_gate_replay':'pending; requires matching foundry cell models',
        'server_power':'pending; requires Design Compiler and coverage/PVT review',
        'physical_22nm_ppa':'incomplete',
        'flow_note':'Final Tcl adds exact native-library/corner guards; vendor commands are not executed locally.'})
    manifest=json.loads((out/'manifest.json').read_text())
    manifest['starting_checkpoint']=manifest.pop('checkpoint')
    manifest['release_source_sha256']={str(p.relative_to(ROOT)):digest(p) for p in HERE.glob('*') if p.is_file()}
    with tarfile.open(release/'generation_sources.tar.gz','w:gz') as archive:
        for name in manifest['release_source_sha256']: archive.add(ROOT/name,arcname=name,recursive=False)
    manifest['generation_archive_sha256']=digest(release/'generation_sources.tar.gz')
    manifest['source_sha256']['core/architecture/technology_scaling.json']=digest(ROOT/'core/architecture/technology_scaling.json')
    write_json(out/'manifest.json',manifest)
    tcl='''foreach path $argv {
    set stream [open $path r]
    set source [read $stream]
    close $stream
    if {![info complete $source]} {error "Incomplete Tcl source: $path"}
    puts "$path: Tcl syntax complete (vendor commands not executed)"
}
'''
    (release/'check_tcl.tcl').write_text(tcl)
    subprocess.run(['tclsh',str(release/'check_tcl.tcl'),str(out/'p05_flow/power.tcl'),str(out/'p05_flow/synth_glue.tcl')],check=True)
    (out/'SHA256SUMS').write_text(''.join(digest(p)+'  '+str(p.relative_to(out))+'\n' for p in sorted(out.rglob('*')) if p.is_file()))
    verify_files(out)
    packet_check=verify_packet(out)
    with zipfile.ZipFile(release/'power_activity.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out.rglob('*')):
            if path.is_file():archive.write(path,str(path.relative_to(release)))
    write_json(release/'release.json',{'packet':str(out.relative_to(ROOT)),
        'files':sum(p.is_file() for p in out.rglob('*')),'packet_manifest_sha256':digest(out/'manifest.json'),
        'archive_sha256':digest(release/'power_activity.zip'),'packet_checks':str(packet_check.relative_to(ROOT)),
        'status':'local_rtl_and_packet_verified_vendor_pending'})
    (release/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.name+'\n' for p in sorted(release.iterdir()) if p.is_file()))
    print(out.relative_to(ROOT),flush=True)


if __name__=='__main__': main()
