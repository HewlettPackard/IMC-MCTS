# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import argparse
import csv
import gzip
import hashlib
import json
import math
import re
import shutil
import subprocess
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROBE_RUN = ROOT / 'p03_experiments/p08_cost_sources/p00_runs/run_20260909_023818Z'
COMMIT = '1ffd8dfb10303d306ecd8d215320aea07651e878'
ARCHIVE_SHA = 'bfed924722bb8ebfa0b224741d3955034e1ced7bd1371fbb5472c81c509df9a3'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')


def parse_cacti(text, csv_text):
    # The upstream executable also prints unrelated DDR I/O and MemCAD output.
    # Accept only the UCA SRAM section and its separately emitted CSV record.
    lines = [line.strip() for line in csv_text.splitlines() if line.strip()]
    if len(lines) != 2:
        raise ValueError('Expected exactly one CACTI CSV header and data record')
    rows = list(csv.reader(lines, skipinitialspace=True))
    if len(rows[0]) != len(rows[1]) or len(set(rows[0])) != len(rows[0]):
        raise ValueError('Ambiguous CACTI CSV columns')
    row = dict(zip(rows[0], rows[1]))

    def number(pattern):
        matches = re.findall(pattern, text, flags=re.MULTILINE)
        if len(matches) != 1:
            raise ValueError(f'Missing or ambiguous CACTI field: {pattern}')
        value = float(matches[0])
        if not math.isfinite(value) or value < 0:
            raise ValueError('Nonfinite or negative CACTI result')
        return value

    def csv_number(name):
        if name not in row:
            raise ValueError(f'Missing CACTI CSV field: {name}')
        value = float(row[name])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f'Invalid CACTI CSV field: {name}')
        return value

    def agree(first, second):
        if not math.isclose(first, second, rel_tol=2e-5, abs_tol=1e-12):
            raise ValueError(f'CACTI text/CSV/input mismatch: {first} != {second}')

    fields = {
        'capacity_bytes': ('Total cache size (bytes)', 'Capacity (bytes)'),
        'banks': ('Number of banks', 'Number of banks'),
        'technology_nm': ('Technology size (nm)', 'Tech node (nm)'),
        'access_ns': ('Access time (ns)', 'Access time (ns)'),
        'cycle_ns': ('Cycle time (ns)', 'Random cycle time (ns)'),
        'read_energy_nj': ('Total dynamic read energy per access (nJ)', 'Dynamic read energy (nJ)'),
        'write_energy_nj': ('Total dynamic write energy per access (nJ)', 'Dynamic write energy (nJ)'),
    }
    result = {}
    for name, (label, column) in fields.items():
        value = number(r'^    ' + re.escape(label) + r':\s*(\S+)\s*$')
        agree(value, csv_number(column))
        result[name] = value
    result['word_bytes'] = number(r'^    Block size \(bytes\):\s*(\S+)\s*$')
    result['subthreshold_leakage_mw'] = number(r'^    Total leakage power of a bank \(mW\):\s*(\S+)\s*$')
    result['gate_leakage_mw'] = number(r'^    Total gate leakage power of a bank \(mW\):\s*(\S+)\s*$')
    result['leakage_mw'] = result['subthreshold_leakage_mw'] + result['gate_leakage_mw']
    agree(result['leakage_mw'], csv_number('Standby leakage per bank(mW)'))
    result['area_mm2'] = csv_number('Area (mm2)')
    height = number(r'^    Cache height x width \(mm\):\s*(\S+) x \S+\s*$')
    width = number(r'^    Cache height x width \(mm\):\s*\S+ x (\S+)\s*$')
    agree(result['area_mm2'], height * width)
    agree(result['area_mm2'], number(r'^  Data array: Area \(mm2\):\s*(\S+)\s*$'))
    result.update(height_mm=height, width_mm=width)
    for name, label in [('capacity_bytes', 'Cache size'), ('word_bytes', 'Block size'),
                        ('banks', 'Cache banks (UCA)')]:
        agree(result[name], number('^' + re.escape(label) + r'\s*:\s*(\S+)\s*$'))
    agree(result['technology_nm'], 1000 * number(r'^Technology\s*:\s*(\S+)\s*$'))
    for label, expected in [('Read only ports', 0), ('Write only ports', 0),
                            ('Read write ports', 1), ('Single ended read ports', 0),
                            ('ECC overhead', 0), ('Associativity', 1),
                            ('Model as 3D memory', 0), ('Cache model', 0),
                            ('Burst length', 1), ('Internal prefetch width', 1),
                            ('Optimization target', 2), ('Access mode', 0),
                            ('Wire inside mat', 1), ('Wire outside mat', 1),
                            ('Interconnect projection', 1), ('Wire signaling', 1)]:
        agree(number('^' + re.escape(label) + r'\s*:\s*(\S+)\s*$'), expected)
    if len(re.findall(r'^array type\s*:\s*Scratch RAM\s*$', text, re.MULTILINE)) != 1:
        raise ValueError('Expected untagged Scratch RAM')
    agree(csv_number('Associativity'), 1)
    agree(csv_number('Output width (bits)'), 8 * result['word_bytes'])
    for label, expected in [('Read/write Ports', 1), ('Read ports', 0), ('Write ports', 0)]:
        agree(number(r'^    ' + re.escape(label) + r':\s*(\S+)\s*$'), expected)
    for name in ('capacity_bytes', 'word_bytes', 'banks', 'technology_nm'):
        if result[name] != int(result[name]):
            raise ValueError(f'Noninteger {name}')
        result[name] = int(result[name])
    for name in ('capacity_bytes', 'word_bytes', 'banks'):
        value = result[name]
        if value < 1 or value & (value - 1):
            raise ValueError(f'{name} must be power-of-two for audited CACTI decoders')
    if result['banks'] != 1 or result['word_bytes'] != 4:
        raise ValueError('Only a single-bank, 32-bit macro is supported')
    tiling = {}
    for label, column in [('Ndwl', 'Ndwl'), ('Ndbl', 'Ndbl'), ('Nspd', 'Nspd'),
                          ('Ndcm', 'Ndcm'), ('Ndsam L1', 'Ndsam_level_1'), ('Ndsam L2', 'Ndsam_level_2')]:
        tiling[column] = number(r'^    Best ' + label + r' :\s*(\S+)\s*$')
        agree(tiling[column], csv_number(column))
        if tiling[column] <= 0:
            raise ValueError('Invalid CACTI tiling')
    shape = {'rows': result['capacity_bytes'] / (4 * tiling['Ndbl'] * tiling['Nspd']),
             'columns': 32 * tiling['Nspd'] / tiling['Ndwl']}
    for name, value in shape.items():
        integer = int(value)
        if value != integer or integer < 1 or integer & (integer - 1):
            raise ValueError(f'Subarray {name} must be power-of-two')
        shape[name] = integer
    cell = number(r'^Data array cell type\s*:\s*(\S+)\s*$')
    periphery = number(r'^Data array peripheral type\s*:\s*(\S+)\s*$')
    if cell not in (0, 1) or cell != periphery:
        raise ValueError('Only matched HP or LSTP cell/periphery supported')
    result.update(tiling=tiling, subarray=shape, flavor='hp' if cell == 0 else 'lstp',
                  temperature_k=number(r'^Temperature\s*:\s*(\S+)\s*$'),
                  port='one_read_write', ecc=False, tags=False)
    if any(result[name] <= 0 for name in ('area_mm2', 'access_ns', 'cycle_ns', 'read_energy_nj', 'write_energy_nj')):
        raise ValueError('CACTI metric must be strictly positive')
    return result


def build_cacti(out, compiler):
    archive = PROBE_RUN / 'p00_source/cacti_1ffd8df.tar.gz'
    patch = PROBE_RUN / 'p00_source/cacti_portability.patch'
    if sha(archive) != ARCHIVE_SHA:
        raise ValueError('Pinned CACTI archive hash mismatch')
    build_dir = out / 'p01_build'
    build_dir.mkdir()
    with tarfile.open(archive) as tar:
        tar.extractall(build_dir, filter='data')
    source = build_dir / ('cacti-' + COMMIT)
    subprocess.run(['patch', '-p1', '-i', str(patch)], cwd=source, check=True, capture_output=True)
    command = ['make', 'opt', 'CXX=' + compiler, 'CXXFLAGS=-O2 -std=gnu++98 -DNTHREADS=1']
    built = subprocess.run(command, cwd=source, capture_output=True, timeout=180)
    for stream in ('stdout', 'stderr'):
        (out / ('build.' + stream + '.gz')).write_bytes(gzip.compress(getattr(built, stream), mtime=0))
    metadata = {'commit': COMMIT, 'archive_sha256': sha(archive), 'patch_sha256': sha(patch),
        'command': command, 'returncode': built.returncode, 'clean_build': True,
        'compiler': subprocess.check_output([compiler, '--version'], text=True),
        'source_sha256': {str(p.relative_to(source)): sha(p) for p in sorted(source.rglob('*'))
                         if p.is_file() and 'obj_opt' not in p.parts and p.name != 'cacti'}}
    write_json(out / 'build.json', metadata)
    built.check_returncode()
    metadata['binary_sha256'] = sha(source / 'cacti')
    write_json(out / 'build.json', metadata)
    return source, metadata


def run_case(source, config_path, path, build):
    config = config_path.read_bytes()
    key_data = {'config_sha256': hashlib.sha256(config).hexdigest(),
        'binary_sha256': build['binary_sha256'], 'archive_sha256': ARCHIVE_SHA,
        'patch_sha256': build['patch_sha256'],
        'tech_sha256': {p.name: sha(p) for p in sorted((source / 'tech_params').glob('*.dat'))},
        'parser_sha256': sha(__file__)}
    key = hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    if path.exists():
        check_cache(path, key)
    else:
        path.mkdir(parents=True)
        (path / 'memory.cfg').write_bytes(config)
        shutil.copytree(source / 'tech_params', path / 'tech_params')
        process = subprocess.run([str(source / 'cacti'), '-infile', 'memory.cfg'],
                                 cwd=path, capture_output=True, timeout=60)
        for stream in ('stdout', 'stderr'):
            (path / (stream + '.txt.gz')).write_bytes(gzip.compress(getattr(process, stream), mtime=0))
        metadata = {**key_data, 'cache_key': key, 'returncode': process.returncode,
            'command': ['cacti', '-infile', 'memory.cfg'],
            'output_sha256': {p.name: sha(p) for p in path.iterdir() if p.is_file()}}
        write_json(path / 'execution.json', metadata)
        process.check_returncode()
    return parse_cacti(gzip.decompress((path / 'stdout.txt.gz').read_bytes()).decode(),
                       (path / 'memory.cfg.out').read_text())


def check_cache(path, key):
    old = json.loads((path / 'execution.json').read_text())
    if old['cache_key'] != key or old['returncode'] != 0:
        raise ValueError('CACTI cache identity mismatch or failed run')
    if set(old['output_sha256']) != {'memory.cfg', 'memory.cfg.out', 'stdout.txt.gz', 'stderr.txt.gz'}:
        raise ValueError('Incomplete CACTI cached outputs')
    for name, digest in old['output_sha256'].items():
        if sha(path / name) != digest:
            raise ValueError('CACTI cached output hash mismatch')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--compiler', default='/usr/bin/clang++')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source, build = build_cacti(out, args.compiler)
    profiles = {}
    checks = {}
    for name in ('control_8k_hp22', 'macro_512k_hp22', 'macro_512k_lstp22',
                 'macro_512k_hp65', 'macro_512k_hp22_repeat', 'requested_1536k_hp22'):
        path = out / 'p01_cacti' / name
        try:
            parsed = run_case(source, PROBE_RUN / 'p02_probes' / name / 'memory.cfg', path, build)
        except ValueError as error:
            if name != 'requested_1536k_hp22' or 'power-of-two' not in str(error):
                raise
            checks[name] = {'status': 'rejected', 'reason': str(error)}
            continue
        write_json(path / 'parsed.json', parsed)
        expected_size = 8192 if name.startswith('control') else 524288
        expected_node = 65 if name.endswith('hp65') else 22
        expected_flavor = 'lstp' if 'lstp' in name else 'hp'
        if (parsed['capacity_bytes'], parsed['technology_nm'], parsed['flavor'], parsed['temperature_k']) != (
                expected_size, expected_node, expected_flavor, 360):
            raise ValueError('CACTI result does not match requested experiment configuration')
        # Exercise cached reads, including output integrity checks.
        assert parsed == run_case(source, path / 'memory.cfg', path, build)
        checks[name] = parsed
        if name in ('macro_512k_hp22', 'macro_512k_lstp22'):
            execution = json.loads((path / 'execution.json').read_text())
            profiles['cacti_22nm_' + parsed['flavor']] = {
                'macro': {**parsed, 'voltage_v': 0.8},
                'banks': {'node_sram': 3, 'child_sram': 1}, 'bank_bytes': 524288,
                'clock_mhz': 500, 'macro_service_cycles': math.ceil(max(parsed['access_ns'], parsed['cycle_ns']) / 2),
                'routing_cycles': 1,
                'routing_status': 'one serialized cycle assumed; area and energy uncharacterized',
                'source': {'tool': 'CACTI', 'commit': COMMIT, 'archive_sha256': ARCHIVE_SHA,
                    'patch_sha256': build['patch_sha256'], 'binary_sha256': build['binary_sha256'],
                    'technology_sha256': sha(source / 'tech_params/22nm.dat'),
                    'config_sha256': execution['config_sha256'], 'cache_key': execution['cache_key'],
                    'raw_output_sha256': execution['output_sha256'],
                    'evidence': str(path.relative_to(ROOT))},
                'scaling': {'source_node_nm': 22, 'target_node_nm': 22, 'factor': 1, 'applications': 0},
                'status': 'partial_sram_tool_estimate',
            }
    assert checks['macro_512k_hp22'] == checks['macro_512k_hp22_repeat']
    write_json(out / 'cacti_checks.json', checks)
    write_json(out / 'sram_characterization.json', profiles)
    print('Clean CACTI build, five accepted runs, cache/repeat checks, one rejected decoder shape:', out)


if __name__ == '__main__':
    main()
