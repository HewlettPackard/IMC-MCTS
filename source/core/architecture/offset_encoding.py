# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Two custom 8-bit-cell arrays with exact digital offset subtraction.
# SPDX-License-Identifier: MIT
from collections import Counter
from copy import deepcopy
import hashlib
import json
from numbers import Integral
from pathlib import Path

import numpy as np

from core.architecture.neural_mapping import NeuralMapping, round_shift, round_divide
from core.architecture.parallel_selection import FourLaneGoSimulation

SPEC = Path(__file__).with_suffix('.json')


def offset_spec():
    raw = SPEC.read_bytes()
    spec = json.loads(raw)
    fields = ('weight_bits', 'cell_bits', 'offset', 'active_rows', 'adc_lanes', 'adc_bits',
              'adc_slot_bits', 'readout_bus_bits', 'shift_add_lanes', 'accumulator_words')
    if tuple(spec[k] for k in fields) != (8, 8, 128, 16, 8, 12, 16, 32, 1, 96):
        raise ValueError('Unsupported offset hardware contract')
    return spec | {'sha256': hashlib.sha256(raw).hexdigest()}


def offset_dot(inputs, cells, input_bits, active_rows=16, adc_bits=12):
    inputs = np.asarray(inputs)
    cells = np.asarray(cells)
    if inputs.ndim != 1 or inputs.dtype.kind not in 'iu' or np.any(inputs < 0) or np.any(inputs >= 2**input_bits):
        raise ValueError('Input codes must fit the declared unsigned precision')
    if cells.ndim != 2 or len(cells) != len(inputs) or cells.dtype.kind not in 'iu' or np.any(cells < 0) or np.any(cells > 255):
        raise ValueError('One unsigned 8-bit cell code is required per weight')
    if isinstance(active_rows, bool) or not isinstance(active_rows, Integral) or active_rows <= 0:
        raise ValueError('Positive active-row count required')
    if isinstance(adc_bits, bool) or not isinstance(adc_bits, Integral) or adc_bits <= 0:
        raise ValueError('Positive ADC precision required')
    if active_rows * 255 > 2**adc_bits - 1:
        raise ValueError('ADC cannot represent the full active-row sum exactly')
    raw = np.zeros(cells.shape[1], dtype=np.int64)
    peak = 0
    for start in range(0, len(inputs), active_rows):
        end = min(start + active_rows, len(inputs))
        for bit in range(input_bits):
            driven = (inputs[start:end].astype(np.int64) >> bit) & 1
            adc = driven @ cells[start:end].astype(np.int64)
            peak = max(peak, int(adc.max()))
            if np.any(adc > 2**adc_bits - 1):
                raise OverflowError('ADC conversion exceeds declared range')
            raw += adc << bit
    correction = 128 * int(inputs.astype(np.int64).sum())
    result = raw - correction
    if np.any(raw >= 2**31) or np.any(result < -(2**31)) or np.any(result >= 2**31):
        raise OverflowError('Offset accumulation exceeds signed 32-bit storage')
    return result, {'input_sum': correction // 128, 'correction': correction,
                    'peak_adc_code': peak, 'raw_sums': raw.tolist()}


class OffsetNeuralMapping(NeuralMapping):
    def __init__(self, weights1, weights2, board_size=9, turn_indicator=True, adc_service_cycles=None):
        if board_size not in (2,3,5,9,13,19) or not turn_indicator:
            raise ValueError('Offset mapping requires an approved board size and turn-aware H96 model')
        spec = offset_spec()
        cycles = spec['adc_service_cycles'] if adc_service_cycles is None else adc_service_cycles
        if type(cycles) is not int or cycles not in spec['adc_service_scenarios']:
            raise ValueError('Unreviewed ADC service scenario')
        # Reuse the exact quantizer, hidden scaling, LUT and scratch layout.
        # Keep the original implementation intact as an independent oracle.
        super().__init__(weights1, weights2, board_size, adc_lanes=8, active_rows=16,
                         sram_word_cycles=2, turn_indicator=True)
        if self.profile['hidden_size'] != 96:
            raise ValueError('The offset accumulator bank has 96 output slots')
        self.spec = spec
        self.reference_profile = deepcopy(self.profile)
        self.cells = [(q + spec['offset']).astype(np.uint8) for q in self.weight_codes]
        arrays = [{'layer': i + 1, 'rows': c.shape[0], 'columns': c.shape[1],
                   'count': 1, 'cells': int(c.size), 'cell': '1T1M', 'cell_bits': 8}
                  for i, c in enumerate(self.cells)]
        self.tiles = [[{'row_start': 0, 'row_end': len(c), 'output_start': 0,
                       'output_end': c.shape[1], 'cells': c}] for c in self.cells]
        self.profile.pop('array_rows')
        self.profile.pop('array_columns')
        self.profile.update(model=spec['profile'], rollout_profile=spec['profile'],
            rollout_spec_sha256=spec['sha256'], cell_bits=8, weight_slices=1, sign_branches=1,
            weight_encoding='q_plus_128_with_digital_input_sum_correction', weight_offset=128,
            arrays=arrays, adc_bits=12, adc_slot_bits=16, timing_status=spec['timing_status'],
            ppa_status=spec['ppa_status'], analog_model=spec['device_status'],
            readout={'profile':'sustained_drive_v1', 'overlap':False,
                     'array_drive':'through_all_column_groups', 'storage':'eight shared ADC input S/H lanes'})
        self.profile['service_cycles']['adc_group'] = cycles
        self.profile['provenance'] = {
            'contract': 'offset_encoding.json and explicit user choice of 8-bit 1T1M cells',
            'weight_codes': 'Identical signed q, scales and LUT to the differential reference',
            'geometry': 'One physical cell per encoded weight, no fixed-tile padding',
            'adc_range': '16 * 255 = 4080 <= 4095; ideal integer-code conversion, no physical ENOB proof',
            'adc_service': spec['adc_service_basis'],
            'other_services': 'Retained one-cycle digital operations, two-cycle SRAM and three-cycle array settling; assumptions, not new physical evidence',
            'correction': spec['correction_schedule']}
        self.last_offset = None
        self.schedule = self._offset_schedule()
        self.profile['readout_activity'] = self._readout_activity()

    def forward(self, board, player=None):
        features = self.features(board, player)
        hidden_acc, first = offset_dot(features, self.cells[0], 1)
        hidden = np.array([max(0, round_shift(v, self.hidden_shift)) for v in hidden_acc], dtype=np.int64)
        hidden_clipped = int(np.count_nonzero(hidden > 255))
        hidden = np.clip(hidden, 0, 255)
        self._write('hidden', hidden, 'u1')
        hidden = self._read('hidden', 96, 'u1').astype(np.int64)
        logits_acc, second = offset_dot(hidden, self.cells[1], 8)
        shift = self.fractions[0] + self.fractions[1] - self.hidden_shift - 12
        logits = [round_shift(v, shift) for v in logits_acc]
        logit_clipped = sum(v < -(2**31) or v >= 2**31 for v in logits)
        logits = [max(-(2**31), min(2**31 - 1, v)) for v in logits]
        self._write('logits', logits, '<i4')
        logits = self._read('logits', 3, '<i4').tolist()
        maximum = max(logits)
        indices = [min(4096, round_shift(maximum - v, 4)) for v in logits]
        exponentials = [int(self._read('exp_lut', 1, '<u4', index=i)[0]) for i in indices]
        denominator = sum(exponentials)
        probabilities = [round_divide(v << 16, denominator) for v in exponentials]
        self._write('probabilities', probabilities, '<u4')
        draw, black = self._read('probabilities', 2, '<u4', index=1)
        value_code = 2 * int(black) + int(draw)
        self._write('value', [value_code], '<u4')
        self.last_state = {'hidden_acc': hidden_acc.tolist(), 'hidden_codes': hidden.tolist(),
            'logits_acc': logits_acc.tolist(), 'logits_q12': logits, 'lut_indices': indices,
            'probabilities_q16': probabilities, 'value_q17': value_code,
            'hidden_saturations': hidden_clipped, 'logit_saturations': logit_clipped,
            'black_to_play': int(player == 1)}
        self.last_offset = [first, second]
        self.evaluations += 1
        return value_code / 2**17

    def _offset_schedule(self):
        s = self.profile['service_cycles']
        trace = []
        operations = Counter()
        phases = Counter()
        cursor = 0
        phase = 'layer1'
        context = {}

        def emit(resource, operation, count=1, cycles=1, region=None, address=None, size=0):
            nonlocal cursor
            trace.append({'phase':phase, 'resource':resource, 'operation':operation, 'count':count,
                'region':region, 'address':address, 'bytes':size, 'start':cursor, 'end':cursor+cycles, **context})
            operations[operation] += count
            phases[phase] += cycles
            cursor += cycles

        def transfer(operation, region, address, size):
            if address % 4 or size % 4 or size <= 0:
                raise ValueError('Neural SRAM transfers must be word-aligned')
            for word in range(size // 4):
                emit('neural_controller', 'sram_request_handshakes', region=region, address=address+word*4, size=4)
                emit('node_sram', 'node_sram_'+operation+'_words', cycles=s['sram_word'],
                     region=region, address=address+word*4, size=4)

        emit('neural_controller', 'neural_start')
        transfer('read', 'player', 0, 4)
        emit('neural_controller', 'turn_input_latches')
        for layer, cells in enumerate(self.cells):
            phase = 'layer'+str(layer+1)
            inputs, outputs = cells.shape
            bits = 1 if layer == 0 else 8
            context = {'array_id':layer, 'outputs':[0,outputs]}
            emit('accumulator_registers', 'accumulator_clears', outputs, outputs)
            emit('offset_alu', 'offset_sum_clears')
            for start in range(0, inputs, 16):
                end = min(start+16, inputs)
                context = {'array_id':layer, 'outputs':[0,outputs], 'active_rows':[start,end]}
                if layer == 0:
                    transfer('read', 'board', (start//32)*4, 4)
                else:
                    transfer('read', 'hidden', start, 4*((end-start+3)//4))
                # Sum original inputs once, not once per bit plane or output.
                emit('offset_alu', 'offset_input_adds', end-start, end-start)
                for bit in range(bits):
                    context.pop('columns', None)
                    context['input_bit'] = bit
                    emit('binary_drivers', 'dac_bit_drives', end-start, s['drive'])
                    emit('array', 'array_pulses', cycles=s['array_settle'])
                    for column in range(0, outputs, 8):
                        count = min(8, outputs-column)
                        context['columns'] = [column,column+count]
                        emit('column_mux', 'mux_groups', cycles=s['mux'])
                        emit('sample_hold', 'samples', count, s['sample_hold'])
                        emit('neural_controller', 'adc_request_handshakes')
                        emit('adc_bank', 'adc_groups', cycles=s['adc_group'])
                        trace[-1]['conversions'] = count
                        operations['adc_conversions'] += count
                        words = (count+1)//2
                        emit('readout_bus', 'readout_words', words, words*s['readout_word'])
                        emit('shift_add_lane', 'shift_adds', count, count*s['shift_add'])
            context = {'array_id':layer, 'outputs':[0,outputs]}
            emit('offset_alu', 'offset_shifts')
            emit('offset_alu', 'offset_subtracts', outputs, outputs)
            if layer == 0:
                emit('activation_lane', 'hidden_activations', outputs, outputs)
                transfer('write', 'hidden', 0, outputs)
            else:
                emit('scale_lane', 'logit_rescales', outputs, outputs)
                transfer('write', 'logits', 0, outputs*4)

        phase = 'output'
        context = {}
        transfer('read', 'logits', 0, 12)
        emit('output_alu', 'max_comparisons', 2, 2)
        for output in range(3):
            emit('output_alu', 'lut_addresses')
            begin = len(trace)
            transfer('read', 'exp_lut', 0, 4)
            for row in trace[begin:]:
                row.update(address_source=f'last_state.lut_indices[{output}] * 4', lut_output=output)
        emit('output_alu', 'exponential_sums', 3, 3)
        for output in range(3):
            emit('divider', 'divide_setups')
            emit('divider', 'divide_bits', 48, 48*s['divide_bit'])
            emit('output_alu', 'probability_rounds')
            emit('neural_controller', 'divider_completion_handshakes')
            transfer('write', 'probabilities', output*4, 4)
        transfer('read', 'probabilities', 4, 8)
        emit('output_alu', 'value_formations')
        transfer('write', 'value', 0, 4)
        emit('neural_controller', 'neural_result_capture')
        resources = deepcopy(self.schedule['resources'])
        for key in ('control_status', 'resource_basis'):
            resources.pop(key, None)
        resources.update(array_count=2, array_dimensions=self.profile['arrays'],
            logical_weights=sum(c.size for c in self.cells), mapped_cells=sum(c.size for c in self.cells),
            allocated_cells=sum(c.size for c in self.cells), installed_row_drivers=sum(len(c) for c in self.cells),
            installed_column_routes=sum(c.shape[1] for c in self.cells), adc_bits=12,
            adc_register_bits=8*16, adc_payload_bits=8*12, adc_slot_bits=16,
            accumulator_register_bits=96*32, offset_sum_register_bits=32,
            offset_correction_register_bits=32, control_status='New neural controller and correction logic not synthesized')
        digest = hashlib.sha256(json.dumps(trace,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return {'resources':resources, 'operations':dict(operations), 'phase_cycles':dict(phases),
            'cycles':cursor, 'storage_bytes':self.profile['storage_bytes'],
            'coefficient_initialization_words':len(self.exp_lut), 'schedule_sha256':digest, 'trace':trace}

    def _readout_activity(self):
        rows = []
        for layer in range(2):
            sequence = [r for r in self.schedule['trace'] if r.get('array_id') == layer]
            starts = [i for i,r in enumerate(sequence) if r['operation'] == 'dac_bit_drives']
            spans = []
            for i in starts:
                last = i
                for j in range(i+1,len(sequence)):
                    if sequence[j]['operation'] == 'dac_bit_drives': break
                    if sequence[j]['operation'] == 'shift_adds': last = j
                spans.append(sequence[last]['end']-sequence[i]['start'])
            rows.append({'layer':layer+1, 'array_id':layer, 'bursts':len(spans),
                         'mapped_columns':self.cells[layer].shape[1], 'array_active_cycles':sum(spans)})
        active = sum(r['array_active_cycles'] for r in rows)
        ops = self.schedule['operations']
        return {'profile':'sustained_drive_v1', 'arrays':rows, 'array_read_bursts':ops['array_pulses'],
            'adc_conversions':ops['adc_conversions'], 'adc_groups':ops['adc_groups'],
            'array_active_cycles':active, 'array_active_ns':active*2,
            'energy_status':'8-bit cell currents, 12-bit analog chain and physical timing uncharacterized'}


class OffsetGoSimulation(FourLaneGoSimulation):
    def __init__(self, *args, adc_service_cycles=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.reference_neural_profile = deepcopy(self.neural.profile)
        coefficients = deepcopy(self.neural.coefficients)
        self.neural = OffsetNeuralMapping(*self.weights, self.board_size,
            turn_indicator=self.neural.profile.get('turn_indicator',False), adc_service_cycles=adc_service_cycles)
        self.neural.bind_memory(self.memory)
        if self.neural.coefficients != coefficients:
            raise ValueError('Offset encoding changed the reference coefficients')
        self.rollout_spec = self.neural.spec
        self.memory.config.update(execution_profile=self.memory.config['execution_profile']+'_offset_cell8_v1',
            rollout_profile=self.rollout_spec['profile'], rollout_spec_sha256=self.rollout_spec['sha256'],
            adc_service_cycles=self.neural.profile['service_cycles']['adc_group'],
            timing_status=self.rollout_spec['timing_status'])

    def _evaluate(self):
        cycles = super()._evaluate()
        ops = self.neural.schedule['operations']
        # All caller handshakes already appear at their locations in this trace.
        return cycles-ops['node_sram_read_words']-ops['node_sram_write_words']-ops['adc_groups']-5
