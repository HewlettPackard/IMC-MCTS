# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'p03_experiments/p03_hardware_accounting/p00_runs/run_20260908_234752Z_e0aeaf/p01_source_evidence'


def audit():
    files = {'area65': 'DC_synthesis_area.txt', 'power65': 'DC_synthesis_power.txt',
             'area22': 'DC_synthesis_area_22nm_stillmaker.csv',
             'power22': 'DC_synthesis_power_22nm_stillmaker.csv'}
    tables = {name: {row['Component Name']: row for row in csv.DictReader((EVIDENCE/file).read_text().splitlines())}
              for name, file in files.items()}
    if any(set(rows) != set(tables['area65']) for rows in tables.values()):
        raise ValueError('Source/derived synthesis components do not match')
    boards = [key for key in next(iter(tables['area65'].values())) if 'squares' in key]
    area_factor = (22 / 65)**2
    rows = []
    totals = defaultdict(lambda: defaultdict(float))
    ratios = []
    for component, source in tables['area65'].items():
        for board in boards:
            area65 = float(source[board])
            area22 = float(tables['area22'][component][board])
            if not math.isclose(area65 * area_factor, area22, rel_tol=1e-12):
                raise ValueError(f'Area scaling mismatch: {component}, {board}')
            power65 = tables['power65'][component][board]
            power22 = tables['power22'][component][board]
            if power65 in ('N/A', ''):
                if power22 not in ('N/A', ''):
                    raise ValueError('Derived power exists without a source')
                power65 = power22 = None
            else:
                power65, power22 = float(power65), float(power22)
                ratios.append(power22 / power65)
            record = {'component': component, 'category': source['Category'], 'board': board,
                'source_area_um2': area65, 'derived_area_um2': area22,
                'source_power_mw': power65, 'derived_power_mw': power22,
                'source_node_nm': 65, 'target_node_nm': 22, 'area_factor': area_factor,
                'conversion_applications': 1,
                'area_fit': {name: source[name] for name in ('R2_Value', 'Fit_Degree', 'Notes')},
                'power_fit': {name: tables['power65'][component][name] for name in ('R2_Value', 'Fit_Degree', 'Notes')},
                'usable_for_current_chip': False}
            rows.append(record)
            if board == '9x9 (81 squares)':
                for name in ('source_area_um2', 'derived_area_um2', 'source_power_mw', 'derived_power_mw'):
                    if record[name] is not None:
                        totals[source['Category']][name] += record[name]
    factor = ratios[0]
    if not all(math.isclose(ratio, factor, rel_tol=1e-12) for ratio in ratios):
        raise ValueError('Archived power table is not one global transformation')
    return {
        'source_files': {name: {'path': str((EVIDENCE/file).relative_to(ROOT)),
            'sha256': hashlib.sha256((EVIDENCE/file).read_bytes()).hexdigest()} for name, file in files.items()},
        'source_node_basis': 'User confirmed original synthesis at 65 nm; raw reports were not recovered',
        'source_quality': 'fitted/predicted component tables, not raw DC reports',
        'area': {'verified_cells': len(rows), 'factor': area_factor,
            'method': 'geometric squared node ratio reconstructed numerically; not a verified Stillmaker implementation',
            'applications': 1, 'additional_scaling_allowed': False},
        'power': {'verified_cells': len(ratios), 'missing_cells': len(rows) - len(ratios),
            'factor': factor, 'applications': 1, 'additional_scaling_allowed': False,
            'method': 'empirically reconstructed global factor; voltage/frequency/activity basis unrecovered',
            'dynamic_leakage_split': None},
        'nine_by_nine_totals': dict(totals), 'rows': rows,
        'current_chip_compatibility': {
            'selection': 'one binary64 UCB lane and parent-link cache need matching implementation; old fitted parallel blocks are unverified',
            'expansion': 'serialized packed node/board writes differ from old child-state generator and record layout',
            'backprop': 'bounded path and packed binary64 statistics require matching arithmetic and ports',
            'rollout': 'old DAC/ADC-named RTL is digital mock/control; not analog converter area or the mapped two-layer datapath',
            'missing': ['main controller provenance', 'bank selection/routing',
                '32-bit shift/add and tile accumulators', 'fixed-point ReLU/scaling',
                'integer softmax/LUT/divider', 'device-array and converter physical costs']},
        'status': 'archival_conversion_reconciled_not_adopted_for_current_chip'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.write_text(json.dumps(audit(), indent=2, sort_keys=True, allow_nan=False) + '\n')
