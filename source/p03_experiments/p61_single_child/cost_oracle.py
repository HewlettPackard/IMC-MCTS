# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Round 51 independent raw-evidence oracle, extended for incremental controller exclusions.
# SPDX-License-Identifier: MIT
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
FROZEN = 'p04_results/p01_runs/run_20260914_020352Z/result.json'
TOOLS = 'p03_experiments/p35_component_ppa/p00_runs/run_20260910_202201Z'
WORKBOOK = 'p03_experiments/p15_workbook_models/p01_sources/crossbar_reference.xlsx'
AREA_FACTOR = (22 / 65) ** 2
ENERGY_FACTOR = (22 / 65) * (.8 / 1.) ** 2
NUM = r'([-+\d.eE]+)'


def check(actual, expected, label):
    if expected is None or isinstance(expected, (str, bool, int)):
        assert actual == expected, (label, actual, expected)
    else:
        assert actual is not None and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10), (label, actual, expected)


class Sources:
    def __init__(self):
        self.hashes = {}
        self.checks = []
        self.digital = self.json('core/architecture/digital_characterization.json')['cases']
        self.sram_catalog = self.json('core/architecture/sram_characterization.json')
        self.tools = self.json(TOOLS + '/characterization.json')
        self.policy = self.json('core/architecture/peripheral_assumptions.json')
        self.assumptions = {k: v['value'] for k, v in self.policy['assumptions'].items()}
        self.cells = self.workbook()
        self.adc = {k: float(v) for k, v in next(csv.DictReader(self.read(TOOLS + '/adc.csv').splitlines())).items()}
        for k, v in self.tools['adc'].items():
            check(self.adc[k], v, 'ADC raw CSV ' + k)
        r = self.adc['column_ohm'] * .5 / self.adc['read_v']
        adc_pj = ((.7213 * 8 + 3.3041) * 1e-6 + .084273 * math.exp(-2.311 * math.log10(r))) * (1 + .0013 * (360 - 300)) * 9e-9 * 1e12
        check(self.adc['energy_pj'], adc_pj, 'Independent pinned SAR fit')
        self.checks.append('Raw ADC CSV and independent 22 nm HP power-fit equation agree')

    def bytes(self, path):
        data = (ROOT / path).read_bytes()
        self.hashes[path] = hashlib.sha256(data).hexdigest()
        return data

    def read(self, path):
        data = self.bytes(path)
        return (gzip.decompress(data) if path.endswith('.gz') else data).decode()

    def json(self, path):
        return json.loads(self.read(path))

    def workbook(self):
        self.bytes(WORKBOOK)
        result = {}
        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        with zipfile.ZipFile(ROOT / WORKBOOK) as archive:
            book = ET.fromstring(archive.read('xl/workbook.xml'))
            rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
            targets = {x.attrib['Id']: x.attrib['Target'] for x in rels}
            for sheet in book.find('s:sheets', ns):
                name = sheet.attrib['name']
                if name not in ('New_Architecture', 'ADC'):
                    continue
                target = targets[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
                xml = ET.fromstring(archive.read(target.lstrip('/') if target.startswith('/') else 'xl/' + target))
                result[name] = {}
                for cell in xml.findall('.//s:sheetData/s:row/s:c', ns):
                    value = cell.find('s:v', ns)
                    if value is not None and cell.attrib.get('t') not in ('s', 'str', 'e'):
                        formula = cell.find('s:f', ns)
                        result[name][cell.attrib['r']] = {'value': float(value.text), 'formula': None if formula is None else formula.text}
        cached = self.json('p03_experiments/p15_workbook_models/p01_sources/workbook_cells.json')['cells']
        used = {'New_Architecture': 'C14 C26 C27 D28 O26 P31 C13 C5 C40 C41 C42 U40 L14 L15 O16 O17 D97 Q56', 'ADC': 'D9'}
        for sheet, keys in used.items():
            for key in keys.split():
                check(result[sheet][key]['value'], cached[sheet][key]['value'], sheet + '!' + key)
        self.checks.append('All 19 adopted workbook primitives match raw XLSX cached numeric cells; formulas retained, not recalculated by Excel')
        return result

    def cacti(self, folder):
        filename = 'stdout.txt.gz' if (ROOT / folder / 'stdout.txt.gz').exists() else 'stdout.txt'
        raw = self.read(folder + '/' + filename)
        raw = raw[raw.index('Cache Parameters:'):]
        def field(label):
            return float(re.search(re.escape(label) + r'\s*:\s*' + NUM, raw)[1])
        csvrow = next(csv.DictReader(self.read(folder + '/memory.cfg.out').splitlines(), skipinitialspace=True))
        row = {'area_um2': float(csvrow['Area (mm2)']) * 1e6,
            'read_energy_nj': field('Total dynamic read energy per access (nJ)'),
            'write_energy_nj': field('Total dynamic write energy per access (nJ)'),
            'leakage_mw': field('Total leakage power of a bank (mW)') + field('Total gate leakage power of a bank (mW)'),
            'access_ns': field('Access time (ns)'), 'cycle_ns': field('Cycle time (ns)')}
        if 'associative search energy' in raw:
            row['search_energy_nj'] = field('Total dynamic associative search energy per access (nJ)')
        self.read(folder + '/memory.cfg')
        return row

    def digital_report(self, case):
        catalog = self.digital[case]
        reports = catalog['reports']
        area = self.read(reports['area.rpt'])
        power = self.read(reports['power_vectorless.rpt'])
        details = dict(x.split('=', 1) for x in self.read(reports['run_details.txt']).splitlines() if '=' in x)
        params = dict((k, int(v)) for k, v in (x.split('=') for x in details['parameters'].split(',') if x))
        assert params == catalog['parameters'], case
        assert details['area_unit'] == 'square micrometers' and details['time_unit'] == '1 ns'
        units = {'W': 1000, 'mW': 1, 'uW': .001, 'nW': 1e-6, 'pW': 1e-9}
        def mw(label):
            match = re.search(re.escape(label) + r'\s*=\s*' + NUM + r'\s*([munp]?W)\b', power)
            return float(match[1]) * units[match[2]]
        native = float(re.search(r'Total cell area:\s*' + NUM, area)[1])
        active = mw('Total Dynamic Power')
        leakage = mw('Cell Leakage Power')
        scale = mw('Dynamic Power Units')
        clock = re.search(r'^clock_network\s+' + NUM + r'\s+' + NUM, power, re.M)
        idle = (float(clock[1]) + float(clock[2])) * scale
        children = {}
        if 'area_hier.rpt' in reports:
            for line in self.read(reports['area_hier.rpt']).splitlines():
                fields = line.split()
                if fields and fields[0].startswith('u_'):
                    children[fields[0]] = float(fields[1]) * AREA_FACTOR
        check(native, catalog['area']['cell_um2'], case + ' area source')
        check(active, catalog['power']['dynamic_mw'], case + ' power source')
        check(leakage, catalog['power']['leakage_mw'], case + ' leakage source')
        for name in ('qor.rpt', 'constraints.rpt'):
            self.read(reports[name])
        return {'area_um2': native * AREA_FACTOR, 'active_mw': active, 'idle_mw': idle,
            'leakage_mw': leakage, 'parameters': params, 'children': children, 'reports': reports}


def flatten(rows, owner=None):
    result = []
    for row in rows:
        result.append((row, owner or row['id']))
        result.extend(flatten(row.get('children', []), owner or row['id']))
    return result


def expected(result, source, overrides=None):
    p = source.assumptions | (overrides or {})
    profile = result['neural']['profile']
    assert (profile['clock_mhz'], profile['array_rows'], profile['array_columns'], profile['active_rows'], profile['adc_lanes'], profile['adc_bits']) == (500, 256, 128, 16, 3, 8), 'Extend the independent oracle for changed hardware'
    assert profile['service_cycles'] == {'sram_word': 2, 'drive': 1, 'array_settle': 3, 'mux': 1, 'sample_hold': 1, 'adc_group': 9, 'readout_word': 1, 'shift_add': 1, 'digital': 1, 'divide_bit': 1}, 'Extend the independent timing equations for changed services'
    memory = result['memory']['config']
    op = result['memory']['operations']
    elapsed = result['metrics']['core_cycles']
    iterations = result['metrics']['completed_iterations']
    phase = result['phase_cycles']
    period = 1000 / profile['clock_mhz']
    time_us = elapsed * period / 1000
    bits = profile['weight_slices'] * profile['sign_branches']
    per_array = profile['array_columns'] // bits
    arrays = math.ceil(profile['input_size'] / profile['array_rows']) * math.ceil(profile['hidden_size'] / per_array) + math.ceil(profile['hidden_size'] / profile['array_rows']) * math.ceil(profile['outputs'] / per_array)
    rows, cols, lanes = arrays * profile['array_rows'], arrays * profile['array_columns'], profile['adc_lanes']
    buffered = profile['readout']['profile'] == 'column_hold_v1'
    rowout = {}
    def add(key, count, area, dynamic=None, standby=None, cycles=None, service=None, sources=()):
        energy = None if dynamic is None else dynamic + standby
        rowout[key] = {'count': count, 'area_um2': area, 'energy_uj': energy,
            'dynamic_energy_uj': dynamic, 'standby_energy_uj': standby,
            'average_power_mw': None if energy is None else energy * 1000 / time_us,
            'active_cycles': cycles, 'service_cycles': service, 'sources': list(sources)}

    sram_name = result['costs']['sram']['profile']
    sram_source = source.sram_catalog[sram_name]['source']['evidence']
    macro = source.cacti(sram_source)
    for k, v in macro.items():
        check(v, source.sram_catalog[sram_name]['macro'][k] if k != 'area_um2' else source.sram_catalog[sram_name]['macro']['area_mm2'] * 1e6, sram_name + ' ' + k)
    for pool in ('node_sram', 'child_sram'):
        banks = memory[pool + '_bytes'] // 524288
        reads, writes = op.get(pool + '_read_words', 0), op.get(pool + '_write_words', 0)
        add(pool, banks, banks * macro['area_um2'], (reads * macro['read_energy_nj'] + writes * macro['write_energy_nj']) / 1000,
            banks * macro['leakage_mw'] * time_us / 1000, reads + writes, 1, [sram_source + '/stdout.txt.gz', sram_source + '/memory.cfg.out'])

    active = {'u_sel': phase['selection'] - iterations, 'u_ucb': 223 * op.get('ucb_operations', 0),
        'u_upd': phase['expansion'] + phase['backpropagation'] - 2 * iterations,
        'u_nn': phase['neural'] - op.get('rollout_operations', 0), 'top_level_glue': elapsed}
    for instance, pool in [('u_node_router', 'node_sram'), ('u_child_router', 'child_sram')]:
        active[instance] = 2 * (op.get(pool + '_read_words', 0) + op.get(pool + '_write_words', 0))
    tree = {'BOARD_SIZE': profile['board_size'], 'CAM_ENTRIES': memory['cam_entries'], 'NEURAL_BYTES': memory['neural_bytes'], 'ADDR_W': 21}
    cases = {'u_sel': ('imc_cached_selector', tree), 'u_ucb': ('imc_ucb_score', {}),
        'u_nn': ('imc_buffered_neural_sequencer' if buffered else 'imc_neural_sequencer', {'INPUTS': profile['input_size'], 'HIDDEN': profile['hidden_size'], 'ADDR_W': 21, 'SRAM_BYTES': memory['node_sram_bytes']}),
        'u_upd': ('imc_tree_update_v2', tree),
        'u_node_router': ('imc_sram_router_3bank', {'BANKS': memory['node_sram_bytes'] // 524288, 'BANK_BYTE_W': 19, 'ADDR_W': 21}),
        'u_child_router': ('imc_sram_router_1bank', {'BANKS': memory['child_sram_bytes'] // 524288, 'BANK_BYTE_W': 19, 'ADDR_W': 21}),
        'top_level_glue': ('imc_buffered_iteration_glue' if buffered else 'imc_iteration_glue', {'BOARD_SIZE': profile['board_size'], 'HIDDEN': profile['hidden_size'], 'CAM_ENTRIES': memory['cam_entries'], 'ADDR_W': 21})}
    for key, (case, params) in cases.items():
        raw = source.digital_report(case)
        compatible = raw['parameters'] == params
        if memory.get('policy')=='evaluate_root_then_single_untried_child_v1' and key in ('u_sel','u_upd','top_level_glue'):
            compatible = False
        if key == 'top_level_glue':
            compatible = compatible and memory['neural_bytes'] == 16512
        add(key, 1, raw['area_um2'] if compatible else None,
            ((raw['active_mw'] - raw['idle_mw']) * active[key] + raw['idle_mw'] * elapsed) * period / 1e6 * ENERGY_FACTOR * p.get('digital_dynamic_multiplier', 1) if compatible else None,
            raw['leakage_mw'] * time_us / 1000 * p.get('digital_leakage_multiplier', 1) if compatible else None,
            active[key], sources=raw['reports'].values())
        rowout[key]['children'] = raw['children'] if compatible else {}
        rowout[key]['parameters'] = params

    v = lambda k: source.cells['New_Architecture'][k]['value']
    sample_area = v('C42') / v('C41') + 2 * v('C26') + v('C40')
    sample_pj = v('C42') * v('L15') ** 2 / 1000
    frontend = p['frontend_bias_ua'] * p['analog_supply_v'] / 1000
    bursts = drive = hold_cycles = conversions = groups_total = 0
    driver_pj = array_pj = hold_pj = 0
    # Aggregate by logical row totals and output tiles, not the simulator's row/bit events.
    for n, outputs, input_bits in ((profile['input_size'], profile['hidden_size'], 1), (profile['hidden_size'], profile['outputs'], profile['hidden_bits'])):
        for start in range(0, outputs, per_array):
            columns = min(per_array, outputs - start) * bits
            groups = math.ceil(columns / lanes)
            counts = [min(lanes, columns - i * lanes) for i in range(groups)]
            cursor, weighted_hold, last_sample = 0, 0, 0
            for count in counts:
                last_sample = cursor + 2
                weighted_hold += count * (last_sample + 1)
                cursor += 12 + math.ceil(count / 4) + count
            on = 4 + (1 if buffered else cursor)
            repetitions = math.ceil(n / profile['active_rows']) * input_bits
            bursts += repetitions
            drive += repetitions * on
            hold_cycles += repetitions * (last_sample + 1)
            conversions += repetitions * columns
            groups_total += repetitions * groups
            driver_pj += n * input_bits * (2 * p['input_activity'] * v('O26') + v('P31') / v('C13') / v('C5'))
            array_pj += n * input_bits * p['input_activity'] * v('L15') ** 2 * (profile['array_columns'] * (v('O16') + v('O17')) / 1000 + columns * p['mean_conductance'] / (v('L14') * 1e6) * on * period * 1000)
            hold_pj += repetitions * (weighted_hold * period * frontend * (1 - v('U40')) + columns * sample_pj)
    infer = op.get('rollout_operations', 0)
    for key, value in [('neural_array_pulses', bursts), ('neural_adc_conversions', conversions), ('neural_adc_groups', groups_total)]:
        check(op.get(key, 0), infer * value, key + ' independent geometry')
    def analog(key, count, area, dynamic_pj, idle, cycles, service):
        add(key, count, area, dynamic_pj / 1e6, idle * time_us / 1000, cycles, service,
            [WORKBOOK, 'core/architecture/peripheral_assumptions.json'])
    analog('cim_arrays', arrays, arrays * profile['array_rows'] * profile['array_columns'] * v('C14'), array_pj * infer, 0, drive * infer, 3)
    analog('row_drivers', rows, rows * (v('C26') * v('C27') + v('D28') / v('C5')), driver_pj * infer,
        rows * p['driver_idle_fraction'] * (2 * p['input_activity'] * v('O26') + v('P31') / v('C13') / v('C5')) / period, drive * infer, 1)
    analog('sample_hold', lanes, lanes * sample_area, infer * conversions * (frontend * (1 - v('U40')) * 11 * period + sample_pj), lanes * frontend * v('U40'), infer * groups_total * 11, 1)
    adc = source.adc
    resistance = v('L14') * 1e6 / (profile['active_rows'] * p['input_activity'] * p['mean_conductance']) * .5 / v('L15')
    adc_pj = ((.7213 * 8 + 3.3041) * 1e-6 + .084273 * math.exp(-2.311 * math.log10(resistance))) * 1.078 * 9e-9 * 1e12 * p.get('adc_energy_multiplier', 1)
    analog('adc_lanes', lanes, lanes * adc['area_um2'], infer * conversions * adc_pj,
        lanes * p['adc_idle_fraction'] * adc_pj / adc['latency_ns'], infer * groups_total * 9, 9)
    rowout['adc_lanes']['sources'].append(TOOLS + '/adc.csv')
    analog('analog_mux', cols, cols * (2 * v('C26') + v('D28') / v('C5')) + (lanes + 1) * v('C40'), infer * conversions * 2 * v('O26'),
        (lanes * source.cells['ADC']['D9']['value'] + p['reference_bias_mw']) * p.get('reference_multiplier', 1), infer * groups_total, 1)
    if buffered:
        analog('column_hold', cols, cols * sample_area, hold_pj * infer, cols * frontend * v('U40'), hold_cycles * infer, 1)
    cam_entries = max(128, 2 ** math.ceil(math.log2(memory['cam_entries'])))
    cam_folder = TOOLS + '/cam_' + str(cam_entries) + ('_hp' if sram_name.endswith('_hp') else '_lstp')
    cam = source.cacti(cam_folder)
    for k, value in cam.items():
        check(value, source.tools['cam'][Path(cam_folder).name][k], 'CAM raw ' + k)
    requests = [op.get('cam_searches', 0), op.get('cam_output_ids', 0), op.get('cam_filled_rows', 0) + op.get('cam_evicted_rows', 0)]
    add('cam_macro', 1, cam['area_um2'], sum(n * cam[k] for n, k in zip(requests, ('search_energy_nj', 'read_energy_nj', 'write_energy_nj'))) / 1000,
        cam['leakage_mw'] * time_us / 1000, 3 * sum(requests), 3, [cam_folder + '/stdout.txt', cam_folder + '/memory.cfg.out'])
    area = sum(row['area_um2'] or 0 for row in rowout.values())
    digital_energy = sum(rowout[key]['energy_uj'] or 0 for key in cases)
    add('physical_overhead', 1, area * p['layout_area_fraction'], digital_energy * p['clock_wire_power_fraction'], 0, elapsed,
        sources=[WORKBOOK, 'core/architecture/peripheral_assumptions.json'])
    for key in ('chip_io', 'weight_programming'):
        add(key, None, None)
    return rowout


def compare(result, source):
    rows = expected(result, source)
    ledger = result['costs']['ledger']
    assert set(rows) == {r['id'] for r in ledger['components']}
    comparisons = []
    for actual in ledger['components']:
        target = rows[actual['id']]
        for field in ('count', 'area_um2', 'energy_uj', 'average_power_mw', 'active_cycles', 'service_cycles'):
            check(actual.get(field), target[field], actual['id'] + '.' + field)
            comparisons.append({'owner': actual['id'], 'metric': field, 'actual': actual.get(field), 'independent': target[field], 'status': 'pass'})
        if actual.get('id') in result.get('block_activity', {}).get('blocks', {}):
            occupancy = result['block_activity']['blocks'][actual['id']]
            check(occupancy['active_cycles'], target['active_cycles'], 'FSM ' + actual['id'])
            check(occupancy['idle_cycles'] + occupancy['active_cycles'], result['metrics']['core_cycles'], 'idle elapsed')
    tree = flatten(ledger['components'])
    assert len(tree) == len({r['id'] for r, _ in tree})
    for row, owner in tree:
        if row['id'] == owner:
            continue
        assert row['counted'] is False and row.get('energy_uj') is None and row.get('average_power_mw') is None, row['id']
        if row.get('rtl_instance'):
            check(row['area_um2'], rows[owner]['children'].get(row['rtl_instance']), row['id'] + ' raw hierarchical area')
        elif row.get('area_um2') is not None:
            ratio = row['count'] / rows[owner]['count'] if owner == 'cim_arrays' else 1
            check(row['area_um2'], rows[owner]['area_um2'] * ratio, row['id'] + ' included area')
    area = sum(r['area_um2'] or 0 for r in rows.values()) / 1e6
    energy = sum(r['energy_uj'] or 0 for r in rows.values())
    check(ledger['known_area_mm2'], area, 'area sum owners once')
    check(ledger['known_energy_uj'], energy, 'energy sum owners once')
    check(ledger['known_average_power_mw'], energy * 500000 / result['metrics']['core_cycles'], 'power energy/time')
    check(result['metrics']['core_latency_us'], result['metrics']['core_cycles'] / 500, 'latency clock')
    check(sum(result['phase_cycles'].values()), result['metrics']['core_cycles'], 'phase cycles elapsed')
    for key in ('whole_chip_area_mm2', 'whole_chip_energy_uj', 'whole_chip_power_mw'):
        check(ledger[key], None, key)
    return rows, comparisons
