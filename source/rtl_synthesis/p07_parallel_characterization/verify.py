# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
RUN=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else None
if RUN is None or RUN.exists():raise SystemExit("Supply a fresh external verification output directory")
RUN.mkdir(parents=True)
import json,subprocess,os
OUT=ROOT/'rtl_synthesis/p07_parallel_characterization'
logs=RUN/'rtl_checks';logs.mkdir(parents=True,exist_ok=True)
files=[str((OUT/line).resolve()) for line in (OUT/'filelist.f').read_text().splitlines()]
report=[]
def run(name,cmd):
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
    (logs/(name+'.log')).write_text(result.stdout+result.stderr)
    report.append({'name':name,'command':cmd,'exit_code':result.returncode,'log':str(logs/(name+'.log'))})
    (logs/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    if result.returncode:print((result.stdout+result.stderr)[-6000:]);raise SystemExit(result.returncode)

run('syntax',['/opt/homebrew/bin/iverilog','-g2012','-tnull']+files)
for top in ('imc_shift_add_lane','imc_parallel_accumulators','imc_parallel_result_banks','imc_candidate_banks','imc_ucb_batch16_overlap'):
    run('lint_'+top,['/opt/homebrew/bin/verilator','--lint-only','-Wall','--top-module',top]+files)
for source in (OUT/'p01_tests').glob('tb_*.sv'):
    binary=logs/source.stem
    run('compile_'+source.stem,['/opt/homebrew/bin/iverilog','-g2012','-s',source.stem,'-o',str(binary)]+files+[str(source)])
    run('run_'+source.stem,['/opt/homebrew/bin/vvp',str(binary)])
    assert source.stem+' PASS' in (logs/('run_'+source.stem+'.log')).read_text()
for top in ('imc_shift_add_lane','imc_parallel_accumulators','imc_parallel_result_banks','imc_candidate_banks'):
    # Structural cells only. No technology mapping or physical PPA adoption.
    commands='read_verilog -sv '+ ' '.join('"'+str(OUT/'p00_rtl'/p)+'"' for p in
        ('imc_shift_add_lane.sv','imc_accumulator_bank.sv','imc_parallel_accumulators.sv','imc_parallel_result_banks.sv','imc_candidate_banks.sv'))
    commands+='; hierarchy -check -top '+top+'; proc; opt; check -assert; stat -width; write_json "'+str(logs/(top+'.json'))+'"'
    run('structure_'+top,['/opt/homebrew/bin/yosys','-p',commands])
print('PASS: syntax, five zero-warning lint tops, five directed TBs and four generic structural syntheses')
