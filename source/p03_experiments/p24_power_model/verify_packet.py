# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Check every returned netlist binding and portable packet preflight without a PDK.
# SPDX-License-Identifier: MIT
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from core.architecture.result_registry import new_run, write_json
from p03_experiments.p24_power_model.glue import INSTANCES

ROOT=Path(__file__).resolve().parents[2]


def verify_packet(packet):
    packet=Path(packet).resolve()
    spec=importlib.util.spec_from_file_location('packet_replay',packet/'p05_flow/replay.py')
    replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)
    out=new_run(Path(__file__).parent/'p00_runs');manifest=json.loads((packet/'manifest.json').read_text());checks={}
    try:
        for variant in manifest['variants'].values():
            source=(packet/'p00_rtl'/(variant['top']+'.sv')).read_text()
            before={match[3]:match[0] for match in INSTANCES.finditer(source)}
            for instance,case in variant['owners'].items():
                new,gate=replay.gate_top(source,(packet/'p03_native'/case/'mapped.v').read_text(),instance,manifest['modules'][case]['design'])
                label=variant['top']+'_'+instance
                checks[label+'_binding']=sum('activity__'+manifest['modules'][case]['design']+' '+instance in line for line in new.splitlines())==1 and all(value in new for name,value in before.items() if name!=instance)
                top=out/(label+'.sv');top.write_text(new)
                netlist=out/(label+'_mapped.v');netlist.write_text(gate)
                sources=[str(packet/p) for p in variant['filelist'] if Path(p).name!=variant['top']+'.sv']
                command=['iverilog','-g2012','-i','-tnull','-s',variant['top'],*sources,str(top),str(netlist)]
                result=subprocess.run(command,capture_output=True,text=True)
                (out/(label+'_syntax.txt.gz')).write_bytes(gzip.compress((result.stdout+result.stderr).encode(),mtime=0))
                checks[label+'_mixed_syntax_only']=result.returncode==0
        settings={k:v for k,v in os.environ.items() if k not in ('IMC65_TARGET_DB','IMC65_CELL_FILELIST','VCD2SAIF','DC_SHELL')}
        result=subprocess.run([sys.executable,'-B',str(packet/'p05_flow/replay.py'),'gate'],env=settings,capture_output=True,text=True)
        (out/'missing_server_inputs.txt').write_text(result.stdout+result.stderr)
        checks['missing_library_fails_before_power']=result.returncode!=0 and 'Set IMC65_TARGET_DB' in result.stderr
        if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
        write_json(out/'metadata.json',{'status':'passed','checks':checks,'packet':str(packet.relative_to(ROOT)),
            'scope':'Parent binding and mixed RTL/netlist syntax only; -i allows unresolved foundry cells. No gate functional or vendor power claim.'})
    except Exception as error:
        write_json(out/'metadata.json',{'status':'failed','checks':checks,'error':str(error),'packet':str(packet.relative_to(ROOT))})
        raise
    finally:
        (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file()))
    print(out.relative_to(ROOT),len(checks),'packet checks passed',flush=True)
    return out


if __name__=='__main__': verify_packet(sys.argv[1])
