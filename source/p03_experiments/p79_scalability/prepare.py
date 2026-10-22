# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Freeze inputs and probe the pinned 12-bit SAR model locally.
# SPDX-License-Identifier: MIT
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess

from core.architecture.result_registry import ROOT, new_run, write_json
from core.architecture.digital_costs import load_digital_profile
from core.architecture.block_power import load_power_table
from core.architecture.crossbar_workbook import workbook_source
from core.architecture.peripheral_costs import peripheral_sources
from core.architecture.sram_costs import load_sram_profile
from core.architecture.cost_ledger import scaling_policy

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = new_run(HERE/'p00_runs'); print(out,flush=True)
    old = ROOT/'p03_experiments/p78_resource_figures/p00_runs/run_20260917_153641Z'
    protected = json.loads((old/'protected_sha256.json').read_text())
    for name,digest in protected.items(): assert sha(Path(name)) == digest,name
    for path in old.rglob('*'):
        if path.is_file(): protected[str(path)] = sha(path)
    write_json(out/'protected_sha256.json',protected)
    (out/'ARCH_MENTOR_before.md').write_bytes((ROOT/'ARCH_MENTOR.md').read_bytes())
    digital = load_digital_profile(); power = load_power_table(digital['profile_sha256'])
    policy,tools,sources = peripheral_sources()
    source = ROOT/'p03_experiments/p09_digital_periphery/p00_runs/run_20260909_030820Z/p00_source'
    adapter = ROOT/'p03_experiments/p09_digital_periphery/adc_probe.cpp'
    command = ['/usr/bin/clang++','-std=c++17','-O2','-I',str(source),str(adapter)]
    command += [str(source/(n+'.cpp')) for n in ('SarADC','Technology','FunctionUnit','formula','Param')]
    command += ['-o',str(out/'adc_probe')]
    build = subprocess.run(command,capture_output=True,timeout=60)
    (out/'adc_build.txt').write_bytes(build.stdout+build.stderr); build.check_returncode()
    args = ['22','1','12','1','25000000','500000000','0.4','360']
    probe = subprocess.run([str(out/'adc_probe'),*args],capture_output=True,timeout=10)
    probe.check_returncode(); (out/'adc.csv').write_bytes(probe.stdout)
    adc = {k:float(v) for k,v in next(csv.DictReader(io.StringIO(probe.stdout.decode()))).items()}
    assert adc['bits']==12 and adc['latency_ns']==13 and adc['reported_leakage_w']==0
    sources += [adapter]+[f for f in source.iterdir() if f.is_file()]
    sources += [ROOT/n for n in digital['source_files']]
    sources += list((ROOT/'core/architecture').glob('*.json'))
    sources += [ROOT/'p03_experiments/p15_workbook_models/p01_sources/workbook_cells.json',
                ROOT/'p03_experiments/p15_workbook_models/p01_sources/crossbar_reference.xlsx']
    source_hashes = {str(f.relative_to(ROOT)):sha(f) for f in sources}
    write_json(out/'source_sha256.json',source_hashes)
    write_json(out/'sources.json',{'digital':digital,'power':power,'peripheral':policy,
        'tools':tools,'workbook':workbook_source(),'sram':load_sram_profile('cacti_22nm_lstp'),
        'scaling':scaling_policy(),'neurosim_adc12':adc,'adc_build':command,'adc_argv':args})
    write_json(out/'published_adc.json',{
        'title':'A 12-bit 40 MS/s SAR ADC with Digital Foreground Self-calibration for Capacitor Mismatches',
        'authors':['Injune Yeo','Byung-Geun Lee'],'venue':'JSTS','year':2020,
        'doi':'10.5573/JSTS.2020.20.1.105','url':'https://jsts.org/jsts/XmlViewer/f391663',
        'source_node_nm':65,'supply_v':1.2,'bits':12,'sample_rate_msps':40,
        'area_mm2':0.098,'power_mw':1.96,'energy_pj':49.0,'enob_nyquist':10.9,
        'input_capacitance_ff':970,'cdac_mw':0.26,'comparator_mw':0.45,'sar_logic_mw':1.25,
        'area_note':'Abstract/body/Table 4 say .098 mm2; Table 3 says .097. Use .098.',
        'adoption':'Engineering ADC macro budget carried without analog node shrink; not measured 22 nm cost or guaranteed bound. Native power/area kept together.',
        'limits':'Different circuit/interface; measured ENOB does not establish ideal 12-bit code accuracy. References/front-end remain separately budgeted; startup calibration excluded.'})
    write_json(HERE/'latest.json',{'run':str(out.relative_to(ROOT))})


if __name__ == '__main__': main()
