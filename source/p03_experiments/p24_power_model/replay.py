# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Replay portable workload fixtures and collect matched module switching activity.
# SPDX-License-Identifier: MIT
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

PACKET = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''): value.update(chunk)
    return value.hexdigest()


def command(args, cwd, name, env=None):
    result = subprocess.run(args,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (cwd/(name+'.txt.gz')).write_bytes(gzip.compress(result.stdout.encode(),mtime=0))
    if result.returncode or re.search(r'^Error:',result.stdout,re.M):
        raise RuntimeError(f'{name} failed ({result.returncode}); see {cwd}/{name}.txt.gz\n'+result.stdout[-2500:])
    return result.stdout


def normalize_vcd(raw, target, start_ns, end_ns, cycles):
    header = []
    with raw.open() as stream, target.open('w') as output:
        for line in stream:
            header.append(line)
            if '$enddefinitions' in line: break
        text = ''.join(header)
        scale = re.search(r'\$timescale\s+(\d+)\s*(fs|ps|ns)\s+\$end',text)
        if scale is None: raise ValueError('Unknown VCD timescale')
        unit = Decimal(scale[1])*{'fs':Decimal('.000001'),'ps':Decimal('.001'),'ns':Decimal(1)}[scale[2]]
        start = int(Decimal(start_ns)/unit); end = int(Decimal(end_ns)/unit)
        if Decimal(end-start)*unit != Decimal(cycles)*2:
            raise ValueError('Activity window does not match the counted 2 ns cycles')
        output.write(text)
        stamp = None; unknown = 0; declarations = text.count('$var ')
        for line in stream:
            if line.startswith('#'):
                stamp = int(line[1:])
                if stamp >= end: break
                if stamp < start: raise ValueError('Activity includes time before the defined window')
                output.write('#'+str(stamp-start)+'\n')
            elif stamp is not None:
                if line.startswith('$dumpoff'): break
                if line[0] in 'xz' or (line[0] in 'bB' and re.search('[xz]',line.split()[0],re.I)): unknown += 1
                output.write(line)
        output.write('#'+str(end-start)+'\n')
    return {'start_ns':start_ns,'end_ns':end_ns,'duration_ns':cycles*2,'cycles':cycles,
        'timescale_ns':str(unit),'declared_signals':declarations,'unknown_value_events':unknown,
        'status':'Functional zero-delay waveform; no SDF/glitch or post-layout timing claim'}


def gate_top(source, netlist, instance, design):
    # Prefix module definitions/types only. Internal instance/net names remain
    # identical to the DDC, which preserves the SAIF hierarchy binding.
    names = re.findall(r'^\s*module\s+(\w+)',netlist,re.M)
    if design not in names: raise ValueError('Mapped top absent: '+design)
    gate = netlist
    for name in sorted(names,key=len,reverse=True):
        gate = re.sub(r'\b'+re.escape(name)+r'\b','activity__'+name,gate)
    pattern = r'^    imc_\w+[ \t]*(?:#\([^\n]*\)[ \t]*)?'+instance+r'[ \t]*\('
    updated, count = re.subn(pattern,'    activity__'+design+' '+instance+' (',source,flags=re.M)
    if count != 1: raise ValueError('Mapped parent replacement count differs')
    return updated, gate


def main():
    mode = sys.argv[1] if len(sys.argv)>1 else 'rtl'
    if mode not in ('rtl','glue','gate'): raise ValueError('Use rtl, glue or gate')
    manifest = json.loads((PACKET/'manifest.json').read_text())
    for line in (PACKET/'SHA256SUMS').read_text().splitlines():
        wanted,name = line.split('  ',1); path = (PACKET/name).resolve()
        if not path.is_relative_to(PACKET) or digest(path)!=wanted: raise ValueError('Packet bytes changed: '+name)
    selected = sys.argv[2:] or list(manifest['cases'])
    if set(selected)-set(manifest['cases']): raise ValueError('Unknown fixture')
    env = dict(os.environ)
    tools = {name:shutil.which(env.get(name.upper(),name)) for name in ('iverilog','vvp')}
    if not all(tools.values()): raise RuntimeError('iverilog and vvp are required')
    cells = []
    if mode == 'gate':
        for name in ('IMC65_TARGET_DB','IMC65_CELL_FILELIST','VCD2SAIF','DC_SHELL'):
            if not env.get(name): raise RuntimeError('Set '+name+' as described in README.md')
        if not Path(env['IMC65_TARGET_DB']).is_file(): raise RuntimeError('Target .db is missing')
        filelist = Path(env['IMC65_CELL_FILELIST']).resolve()
        for line in filelist.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                path = (filelist.parent/line.strip()).resolve()
                if not path.is_file(): raise RuntimeError('Missing cell model: '+str(path))
                cells.append(path)
        if not cells: raise RuntimeError('Cell filelist is empty')
    out = PACKET/'p06_runs'/datetime.now(timezone.utc).strftime('run_%Y%m%d_%H%M%SZ')
    out.mkdir(parents=True,exist_ok=False)
    record = {'mode':mode,'status':'running','packet_manifest_sha256':digest(PACKET/'manifest.json'),
        'synthesis_commit':manifest['synthesis_commit'],'results':[],
        'cell_model_sha256':{str(p):digest(p) for p in cells},
        'target_db_sha256':digest(Path(env['IMC65_TARGET_DB'])) if mode=='gate' else None}
    try:
        for name in selected:
            spec = manifest['cases'][name]; variant = manifest['variants'][spec['variant']]
            top = variant['top']; fixture = PACKET/spec['fixture']
            cfg = json.loads((fixture/'fixture.json').read_text())
            parents = variant['owners'] if mode=='gate' else {mode:None}
            for instance,case in parents.items():
                work = out/(name+'_'+instance); work.mkdir()
                source = (PACKET/'p00_rtl'/(top+'.sv')).read_text()
                extra = []
                scope = 'dut'
                if mode=='glue':
                    source = (PACKET/'p04_glue'/(top+'.sv')).read_text()
                    extra.append(str(PACKET/'p04_glue'/(variant['glue_top']+'.sv')))
                elif mode=='gate':
                    native = PACKET/'p03_native'/case
                    source, gate = gate_top(source,(native/'mapped.v').read_text(),instance,manifest['modules'][case]['design'])
                    (work/'mapped_activity.v').write_text(gate)
                    extra = [str(work/'mapped_activity.v')]+[str(p) for p in cells]
                    scope += '.'+instance
                (work/(top+'.sv')).write_text(source)
                template = (PACKET/'p01_tests'/('tb_'+top+'.sv.in')).read_text()
                bench = work/('tb_'+top+'.sv'); bench.write_text(template.replace('@@SCOPE@@',scope))
                sources = [str(PACKET/p) for p in variant['filelist'] if Path(p).name!=top+'.sv']
                settings = {'BOARD_SIZE':9,'CAM_ENTRIES':1024,'HIDDEN':96}
                command([tools['iverilog'],'-g2012','-s','tb_'+top,'-I',str(PACKET),'-o',str(work/'sim.vvp'),
                    *[f'-Ptb_{top}.{k}={v}' for k,v in settings.items()],*sources,*extra,str(work/(top+'.sv')),str(bench)],work,'compile')
                args = {'FIXTURE':fixture,'EVENTS':work/'events.csv','ACTIVITY':work/'raw.vcd',
                    'COUNT':cfg['transactions'],'ADC':cfg['adc_groups'],'ITERATIONS':cfg['iterations'],
                    'HIDDEN_SHIFT':cfg['hidden_shift'],'LOGIT_SHIFT':cfg['logit_shift'],
                    'NODES':cfg['memory']['node_capacity'],'EDGES':cfg['memory']['edge_capacity'],'PATH':cfg['memory']['path_entries']}
                log = command([tools['vvp'],str(work/'sim.vvp'),*[f'+{k}={v}' for k,v in args.items()]],work,'replay')
                if 'tb_'+top+' PASS' not in log: raise ValueError('Missing complete-state PASS')
                match = re.search(r'ACTIVITY_WINDOW start_ns=([\d.]+) end_ns=([\d.]+) cycles=(\d+)',log)
                if match is None or int(match[3])!=cfg['core_cycles']: raise ValueError('Activity cycle count differs')
                window = normalize_vcd(work/'raw.vcd',work/'activity.vcd',match[1],match[2],int(match[3]))
                if mode=='gate':
                    command([env['VCD2SAIF'],'-input',str(work/'activity.vcd'),'-output',str(work/'activity.saif')],work,'vcd2saif')
                    power_env = env | {'IMC_POWER_NATIVE':str(native),'IMC_POWER_OUT':str(work),
                        'IMC_POWER_DESIGN':manifest['modules'][case]['design'],
                        'IMC_POWER_SCOPE':'tb_'+top+'/'+scope.replace('.','/')}
                    command([env['DC_SHELL'],'-no_gui','-f',str(PACKET/'p05_flow/power.tcl')],work,'power',env=power_env)
                for filename in ('activity.vcd','events.csv'):
                    path = work/filename
                    with path.open('rb') as src, gzip.open(str(path)+'.gz','wb') as dest: shutil.copyfileobj(src,dest)
                    path.unlink()
                (work/'raw.vcd').unlink(); (work/'sim.vvp').unlink()
                result = {'fixture':name,'instance':instance,'case':case,'window':window,
                    'golden_state_and_transactions':'passed','activity_sha256':digest(work/'activity.vcd.gz'),
                    'physical_power_adopted':False}
                record['results'].append(result)
                (work/'window.json').write_text(json.dumps(result,indent=2)+'\n')
                (out/'metadata.json').write_text(json.dumps(record,indent=2)+'\n')
                print(name,instance,'PASS',cfg['core_cycles'],'cycles',flush=True)
        record['status']='passed'
    finally:
        if record['status']=='running': record['status']='failed'
        (out/'metadata.json').write_text(json.dumps(record,indent=2)+'\n')
        (out/'SHA256SUMS').write_text(''.join(digest(p)+'  '+str(p.relative_to(out))+'\n' for p in sorted(out.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
        print(out,flush=True)


if __name__ == '__main__': main()
