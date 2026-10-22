# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HARDWARE = ROOT/'rtl_synthesis/p01_mapped_core'
sys.path.insert(0, str(ROOT))
from p03_experiments.p09_digital_periphery.make_vectors import make_vectors


def verify(out):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands = []
    tools = {name: shutil.which(name) for name in ('iverilog', 'vvp', 'verilator', 'yosys')}
    if not all(tools.values()):
        raise RuntimeError(f'Required tools: {tools}')

    def run(label, args):
        result = subprocess.run(args, cwd=HARDWARE, capture_output=True, text=True, timeout=120)
        with gzip.open(out/f'{label}.log.gz', 'wt') as log:
            log.write(result.stdout + result.stderr)
        commands.append({'check': label, 'argv': args, 'returncode': result.returncode})
        (out/'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
        if result.returncode:
            raise RuntimeError(f'{label} failed; see {out/label}.log.gz')
        return result.stdout + result.stderr

    versions = {name: run(f'version_{name}', [exe, '-V' if name == 'yosys' else
                '--version' if name == 'verilator' else '-V']) for name, exe in tools.items()}
    (out/'tools.json').write_text(json.dumps({'paths': tools, 'versions': versions}, indent=2)+'\n')
    vectors = make_vectors(out)
    run('syntax', [tools['iverilog'], '-g2012', '-tnull', '-c', 'filelist.f'])
    lint_cases = [('accumulator', 'imc_shift_accumulator', {}),
                  ('accumulator_five', 'imc_shift_accumulator', {'ENTRIES': 5}),
                  ('divider', 'imc_round_divider', {}),
                  ('node_router', 'imc_sram_router', {}),
                  ('child_router', 'imc_sram_router', {'BANKS': 1}),
                  ('small_router', 'imc_sram_router', {'BANKS': 3, 'BANK_BYTE_W': 8, 'ADDR_W': 10})]
    for label, module, params in lint_cases:
        run(f'{label}_lint', [tools['verilator'], '--lint-only', '-Wall',
            *[f'-G{key}={value}' for key, value in params.items()], f'p00_rtl/{module}.sv'])

    def simulate(label, source, bench, params=None, plusargs=None, post_synth=False):
        params, plusargs = params or {}, plusargs or []
        executable = out/f'{label}.vvp'
        run(f'{label}_compile', [tools['iverilog'], '-g2012', '-s', bench,
            *(['-DIMC_POST_SYNTH'] if post_synth else []),
            *[f'-P{bench}.{key}={value}' for key, value in params.items()],
            '-o', str(executable), str(source), f'p01_tests/{bench}.sv'])
        output = run(f'{label}_test', [tools['vvp'], str(executable), *plusargs])
        if f'{bench} PASS' not in output:
            raise AssertionError(f'{label}: no completion marker')

    trace_params = {'COMMANDS': vectors['accumulator_commands']}
    trace_args = [f'+ACCUMULATOR_VECTORS={out}/accumulator.hex']
    division_args = [f'+DIVISION_VECTORS={out}/divider.hex']
    simulate('accumulator', HARDWARE/'p00_rtl/imc_shift_accumulator.sv', 'tb_imc_shift_accumulator')
    simulate('trace', HARDWARE/'p00_rtl/imc_shift_accumulator.sv', 'tb_imc_accumulator_trace',
             trace_params, trace_args+[f'+VCD={out}/arithmetic_only.vcd'])
    simulate('divider', HARDWARE/'p00_rtl/imc_round_divider.sv', 'tb_imc_round_divider', plusargs=division_args)
    for label, params in [('node_router', {}), ('child_router', {'BANKS': 1}),
                           ('small_router', {'BANKS': 3, 'BANK_BYTE_W': 8, 'ADDR_W': 10})]:
        simulate(label, HARDWARE/'p00_rtl/imc_sram_router.sv', 'tb_imc_sram_router', params)
    with gzip.open(out/'arithmetic_only.vcd.gz', 'wb') as compressed:
        compressed.write((out/'arithmetic_only.vcd').read_bytes())
    (out/'arithmetic_only.vcd').unlink()

    synthesis = []
    for label, module, params, bench, bench_params, plusargs in [
        ('accumulator', 'imc_shift_accumulator', {}, 'tb_imc_accumulator_trace', trace_params, trace_args),
        ('divider', 'imc_round_divider', {}, 'tb_imc_round_divider', {}, division_args),
        ('node_router', 'imc_sram_router', {}, 'tb_imc_sram_router', {}, []),
        ('child_router', 'imc_sram_router', {'BANKS': 1}, 'tb_imc_sram_router', {'BANKS': 1}, [])]:
        netlist = out/f'{label}.gates.v'
        stats_file = out/f'{label}.stats.json'
        script = '\n'.join([
            f'read_verilog -sv -noautowire p00_rtl/{module}.sv',
            *[f'chparam -set {key} {value} {module}' for key, value in params.items()],
            f'hierarchy -check -top {module}', 'proc', 'check -assert',
            'select -assert-none t:$dlatch t:$adlatch',
            f'synth -top {module}', 'check -assert',
            'select -assert-none t:$_DLATCH* t:$_SR_*',
            f'tee -o {json.dumps(str(stats_file))} stat -json',
            f'write_verilog -noattr {json.dumps(str(netlist))}', ''])
        script_file = out/f'{label}.ys'
        script_file.write_text(script)
        run(f'{label}_synth', [tools['yosys'], '-Q', '-T', '-s', str(script_file)])
        stats = json.loads(stats_file.read_text())
        module_stats = stats['modules'][f'\\{module}']
        cell_types = module_stats['num_cells_by_type']
        flops = sum(count for name, count in cell_types.items() if 'DFF' in name)
        if flops <= 0 or (label == 'accumulator' and flops < 32*32):
            raise AssertionError(f'{label}: required state optimized away')
        synthesis.append({'configuration': label, 'top': module, 'parameters': params,
                          'generic_cells': module_stats['num_cells'], 'flip_flop_bits': flops,
                          'physical_area_um2': None, 'physical_power_mw': None,
                          'timing_closure': 'not characterized'})
        simulate(f'{label}_gates', netlist, bench, bench_params, plusargs, post_synth=True)
        with gzip.open(out/f'{label}.gates.v.gz', 'wb') as compressed:
            compressed.write(netlist.read_bytes())
        netlist.unlink()

    sources = sorted(HARDWARE.rglob('*.sv')) + [HARDWARE/'filelist.f', Path(__file__).resolve(),
        HARDWARE/'p01_tests/run_syntax.sh', ROOT/'p03_experiments/p09_digital_periphery/make_vectors.py']
    result = {'checks_passed': len(commands)-len(versions), 'commands': len(commands),
        'synthesis': synthesis, 'accumulator_commands_per_replay': vectors['accumulator_commands'],
        'mapped_divisions_per_replay': vectors['divider_cases'],
        'source_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources},
        'tool_limitations': ['Icarus broadens always_comb sensitivity for constant selects',
                            'Icarus ignores unique-case simulation qualifiers; Verilator lint has no waivers',
                            'Yosys generic gates and zero-delay replay do not establish 65 nm timing or power'],
        'activity_boundary': 'arithmetic_only.vcd.gz omits SRAM/analog idle cycles; never use as workload SAIF'}
    (out/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(f"{result['checks_passed']} RTL/lint/synthesis checks passed; 4 generic netlists replayed")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    verify(args.out)
