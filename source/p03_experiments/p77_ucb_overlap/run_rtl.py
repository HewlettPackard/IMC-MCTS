# Exact score vectors, old/new RTL comparison and measured batch latency.
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from core.architecture.result_registry import ROOT, new_run, write_json
from core.architecture.ucb_arithmetic import score_q32

HERE = Path(__file__).resolve().parent
HARDWARE = ROOT/'rtl_synthesis/p06_ucb_overlap'


def ieee(value):
    return struct.unpack('>Q',struct.pack('>d',float(value)))[0]


def vectors():
    rows = []
    for parent in (1,2,3,31,256,5000,65535,2**31,2**32-1):
        for child in sorted({1,max(1,parent//3),parent}):
            for value_q17 in sorted({0,1,child*65536,child*131072-1,child*131072}):
                for coefficient in (0,1.414,8):
                    value = value_q17/131072
                    expected = score_q32(parent,child,value,coefficient)/2**32
                    rows.append((parent,child,ieee(value),ieee(coefficient),ieee(expected),0))
    invalid = [(0,0,0,1),(10,0,0,1),(10,11,0,1),(10,3,-1,1),
        (10,3,-0.,1),(10,3,4,1),(10,3,.1,1),(10,3,float('nan'),1),
        (10,3,float('inf'),1),(10,3,1,-1),(10,3,1,9),
        (10,3,1,float('nan')),(10,3,1,float('inf'))]
    for parent,child,value,coefficient in invalid:
        rows.append((parent,child,ieee(value),ieee(coefficient),0,1))
    return rows


def main():
    out = new_run(HARDWARE/'p03_checks')
    rows = vectors()
    (out/'vectors.hex').write_text(''.join(f'{p:08x}{c:08x}{v:016x}{a:016x}{s:016x}{e:08x}\n'
        for p,c,v,a,s,e in rows))
    write_json(out/'metadata.json',{'status':'running','vectors':len(rows),'waveforms':False,'synthesis':False})
    def run(name,args):
        result = subprocess.run(args,cwd=HARDWARE,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
        (out/(name+'.log')).write_text(result.stdout)
        if result.returncode:
            raise RuntimeError(name+' failed: '+result.stdout[-4000:])
    try:
        run('iverilog_version',['iverilog','-V'])
        run('verilator_version',['verilator','--version'])
        run('syntax',['iverilog','-g2012','-s','imc_ucb_batch_overlap','-tnull','-f','filelist.f'])
        run('lint',['verilator','--lint-only','-Wall','--top-module','imc_ucb_batch_overlap','-f','filelist.f'])
        old = '../p03_iteration_core/p00_rtl/imc_ucb_score.sv'
        top = 'tb_imc_ucb_score_overlap'
        run('score_compile',['iverilog','-g2012','-s',top,'-o',str(out/'score.vvp'),
            '-P'+top+'.VECTOR_COUNT='+str(len(rows)),'-P'+top+'.VECTORS="'+str(out/'vectors.hex')+'"',
            '-f','filelist.f',old,'p01_tests/'+top+'.sv'])
        run('score_test',['vvp',str(out/'score.vvp')])
        top = 'tb_imc_ucb_batch_overlap'
        run('batch_compile',['iverilog','-g2012','-s',top,'-o',str(out/'batch.vvp'),
            '-f','filelist.f','p01_tests/'+top+'.sv'])
        run('batch_test',['vvp',str(out/'batch.vvp')])
        score_log = (out/'score_test.log').read_text()
        batch_log = (out/'batch_test.log').read_text()
        assert 'old=222 new=168 saved=54' in score_log and 'PASS' in score_log
        assert 'PASS' in batch_log
        files = [HARDWARE/line for line in (HARDWARE/'filelist.f').read_text().splitlines()]
        files += [HARDWARE/old,Path(__file__),HARDWARE/'filelist.f']
        files += list((HARDWARE/'p01_tests').glob('*'))+list((HARDWARE/'p02_syn').glob('*'))
        identities = {str(p.resolve().relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        write_json(out/'source_sha256.json',identities)
        timing = {'status':'passed','vectors':len(rows),'single_accept_to_valid_cycles':168,
            'reference_single_accept_to_valid_cycles':222,'arithmetic_active_cycles':169,
            'batch_accepted_to_valid_base_cycles':169,'batch_reduction_cycles_per_child':1,
            'caller_request_and_capture_cycles':2,'saved_cycles_per_batch':54,
            'limits':'RTL cycles with ideal interfaces; no physical clock closure or power characterization'}
        write_json(out/'timing.json',timing)
        write_json(out/'metadata.json',{'status':'complete','vectors':len(rows),'waveforms':False,'synthesis':False})
        (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n'
            for p in sorted(out.iterdir()) if p.is_file()))
        write_json(HERE/'latest_rtl.json',{'run':str(out.relative_to(ROOT))})
        print(out,flush=True); print(score_log,flush=True); print(batch_log,flush=True)
    except Exception as error:
        write_json(out/'metadata.json',{'status':'failed','error':str(error),'vectors':len(rows)})
        raise


if __name__ == '__main__': main()
