# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Reuse retained RTL traces and rebuild only the tiny pinned SAR estimator.
# SPDX-License-Identifier: MIT
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np

from core.architecture.analog_readout import configure_readout
from core.architecture.iteration_model import CompleteSimulation
from core.architecture.result_registry import new_run, write_json
from p03_experiments.p29_block_power.waveform import active_cycles
from p03_experiments.p51_ppa_audit.oracle import ROOT, Sources, check


def main():
    experiment = Path(__file__).parent
    out = new_run(experiment / 'p03_physical')
    print(out, flush=True)
    sources = Sources()
    packet = 'p03_experiments/p26_module_power/p01_packets/run_20260910_040245Z'
    records = []
    proof = sources.json('core/architecture/complete_controller_validation.json')['activity_extension']
    assert hashlib.sha256(sources.bytes(proof['path'] + '/metadata.json')).hexdigest() == proof['metadata_sha256']
    for mode in ('sustained_drive_v1', 'column_hold_v1'):
        for ragged in (False, True):
            name = ('buffered' if mode == 'column_hold_v1' else 'driven') + ('_ragged' if ragged else '_empty')
            fixture = sources.json(packet + '/p02_fixtures/' + name + '/fixture.json')
            wavepath = packet + '/p06_runs/run_20260910_040315Z/' + name + '_rtl/activity.vcd.gz'
            sources.bytes(wavepath)
            observed = active_cycles(ROOT / wavepath)
            board = np.zeros((9, 9), dtype=np.int8)
            if ragged:
                board.flat[:] = [0 if i < 3 else (1 if i % 2 else -1) for i in range(board.size)]
            model = CompleteSimulation(9, fixture['iterations'], seed=0, initial_board=board)
            configure_readout(model, mode)
            list(model.steps())
            assert observed == dict(model.block_active_cycles), name
            assert model.cycles == fixture['core_cycles'] and model.history == fixture['history'], name
            assert dict(model.memory.operations) == fixture['operations'], name
            records.append({'fixture': name, 'status': 'passed', 'core_cycles': model.cycles, 'waveform_active_cycles': observed,
                'current_model_active_cycles': dict(model.block_active_cycles), 'waveform_source': wavepath})
            print('PASS retained RTL', name, flush=True)

    base = ROOT / 'p03_experiments/p09_digital_periphery'
    include = base / 'p00_runs/run_20260909_030820Z/p00_source'
    inputs = [base / 'adc_probe.cpp'] + [include / name for name in ('SarADC.cpp', 'Technology.cpp', 'FunctionUnit.cpp', 'formula.cpp', 'Param.cpp')]
    for path in inputs + list(include.glob('*.h')):
        sources.bytes(str(path.relative_to(ROOT)))
    command = ['/usr/bin/clang++', '-std=c++17', '-O2', '-I', str(include)] + [str(p) for p in inputs] + ['-o', str(out / 'adc_probe')]
    build = subprocess.run(command, capture_output=True, text=True, timeout=60, check=True)
    (out / 'build.txt').write_text(build.stdout + build.stderr)
    probes = []
    for resistance, temperature in ((25e6, 360), (100e6, 360), (100e6 / 9, 360), (25e6, 300), (25e6, 400)):
        args = [str(out / 'adc_probe'), '22', '1', '8', '1', str(resistance), '500000000', '.4', str(temperature)]
        raw = subprocess.run(args, capture_output=True, text=True, timeout=10, check=True).stdout
        (out / ('adc_' + str(len(probes)) + '.csv')).write_text(raw)
        row = {k: float(v) for k, v in next(csv.DictReader(raw.splitlines())).items()}
        probes.append(row)
    for key, value in sources.adc.items():
        check(probes[0][key], value, 'fresh SAR executable ' + key)
    cap = sources.cells['New_Architecture']['C42']['value'] * 1e-15
    full_scale = .4  # Illustrative ADC input span only; read voltage is not a calibrated ADC transfer function.
    lsb = full_scale / 256
    hold_ns = 1348  # 43 serialized groups of three columns, last sample at cycle 674.
    limits = {'assumed_adc_full_scale_v': full_scale, 'full_scale_status': 'illustrative_not_established_by_read_voltage',
        'capacitance_f': cap, 'temperature_k': 360, 'thermal_noise_rms_v': math.sqrt(1.380649e-23 * 360 / cap),
        'lsb_v': lsb, 'half_lsb_v': lsb / 2, 'sample_acquisition_ns': 2,
        'max_single_pole_source_ohm_for_half_lsb': 2e-9 / (cap * math.log(512)),
        'max_shared_hold_leakage_a_at_22ns': cap * lsb / 2 / 22e-9,
        'max_column_hold_ns': hold_ns, 'max_column_hold_leakage_a': cap * lsb / 2 / (hold_ns * 1e-9),
        'assumed_column_current_a': .4 / 25e6,
        'status': 'necessary_illustrative_bounds_only_not_a_circuit_validation'}
    # Compare a published measured native65 SAR point only in its original units.
    literature = {'url': 'https://ieeexplore.ieee.org/document/9913787/', 'doi': '10.1109/TCSI.2022.3211461',
        'node_nm': 65, 'voltage_v': 1.2, 'nominal_bits': 8, 'enob': 7.17, 'sample_rate_msps': 350,
        'power_mw': 1.58, 'area_mm2': .0096, 'energy_pj': 1.58 / 350 * 1000,
        'model_to_measured_comparison_status': 'different_node_speed_ENOB_and_boundary; not a calibration or scaling factor'}
    write_json(out / 'metadata.json', {'status': 'passed', 'rtl_reanalysis': records, 'adc_build_command': command,
        'adc_probes': probes, 'illustrative_frontend_limits': limits, 'literature_point': literature,
        'source_sha256': sources.hashes, 'new_waveforms_or_synthesis': False, 'coefficients_changed': False,
        'physical_accuracy_validated': False})
    (out / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n'
        for p in sorted(out.iterdir()) if p.is_file()))
    print('PASS four retained RTL traces and five tiny SAR probes; physical accuracy remains unvalidated', flush=True)


if __name__ == '__main__':
    main()
