# Execute and schedule a finite-precision, differential, bit-sliced evaluator.
# SPDX-License-Identifier: MIT
import hashlib
import json
import math
from collections import Counter
from numbers import Integral
from pathlib import Path

import numpy as np

from core.algorithm.evaluator import encode_board


# --- explicit candidate profile ---

def neural_profile(board_size, hidden_size, adc_lanes=3, active_rows=16, sram_word_cycles=1,
                   neural_timing='service', turn_indicator=False):
    if type(turn_indicator) is not bool: raise ValueError('turn_indicator must be a boolean')
    if turn_indicator and (board_size not in (2,3,5,9,13,19) or hidden_size!=96 or neural_timing!='service'):
        raise ValueError('Turn-aware mapping requires an approved board size and H96 service model')
    for name, value in [('board_size', board_size), ('hidden_size', hidden_size),
                        ('adc_lanes', adc_lanes), ('active_rows', active_rows),
                        ('sram_word_cycles', sram_word_cycles)]:
        if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
            raise ValueError(f'{name} must be a positive integer')
    if active_rows * 15 > 255:
        raise ValueError('The 8-bit ADC cannot cover active_rows * 15 cell-code units')
    if 256 % active_rows or adc_lanes > 128:
        raise ValueError('Unsupported active-row grouping or ADC lane count')
    if neural_timing not in ('service', 'rtl_serial_v1'):
        raise ValueError('neural_timing must be service or rtl_serial_v1')
    if neural_timing == 'rtl_serial_v1' and (board_size, hidden_size, adc_lanes, active_rows, sram_word_cycles) != (9, 96, 3, 16, 2):
        raise ValueError('rtl_serial_v1 requires board_size=9, hidden_size=96, adc_lanes=3, active_rows=16 and sram_word_cycles=2')
    storage = {}
    offset = 0
    for name, size in [('hidden', hidden_size), ('logits', 12),
                       ('probabilities', 12), ('value', 4), ('exp_lut', 4097 * 4)]:
        size = 4 * ((size + 3) // 4)
        storage[name] = {'offset': offset, 'bytes': size}
        offset += size
    profile = {
        'model': 'differential_w8_cell4_a8_adc8_serial_v1',
        'board_size': int(board_size), 'input_size': 2 * board_size**2,
        'hidden_size': int(hidden_size), 'outputs': 3,
        'array_rows': 256, 'array_columns': 128, 'active_rows': int(active_rows),
        'adc_lanes': int(adc_lanes), 'adc_bits': 8, 'dac_bits': 1,
        'weight_bits': 8, 'weight_magnitude_bits': 7, 'cell_bits': 4,
        'weight_slices': 2, 'sign_branches': 2, 'hidden_bits': 8,
        'accumulator_bits': 32, 'logit_fraction_bits': 12,
        'probability_fraction_bits': 16, 'value_fraction_bits': 17,
        'lut_fraction_bits': 30, 'lut_index_fraction_bits': 8,
        'lut_max_argument': 16, 'divider_numerator_bits': 48,
        'storage': storage, 'storage_bytes': offset,
        'clock_mhz': 500,
        'service_cycles': {'sram_word': int(sram_word_cycles), 'drive': 1, 'array_settle': 3,
            'mux': 1, 'sample_hold': 1, 'adc_group': 9, 'readout_word': 1,
            'shift_add': 1, 'digital': 1, 'divide_bit': 1},
        'provenance': {
            'differential_dac_adc': 'submitted supplement Note 4.3: differential pairs, 1-bit DAC, 8-bit ADC',
            'weight_cell_bits': 'legacy crossbar_hardware.py supert_specs: 8-bit weight, 4-bit cell; candidate only',
            'geometry_and_sharing': 'proposed 256x128 arrays, one active array and shared ADC bank; three lanes retains legacy lane count',
            'active_rows': 'derived ideal bound: 16 * (2**4-1) = 240 <= 2**8-1',
            'array_service': 'ceil(legacy board_config.crossbar_delay_ns=5 / 2)=3; uncalibrated',
            'adc_service': 'proposed SAR: one setup plus eight one-cycle decisions; uncalibrated',
            'other_services': ('one-cycle serialized digital/SRAM/link assumptions at reference 500 MHz; uncalibrated'
                if sram_word_cycles == 1 else 'SRAM service from selected memory profile; other digital/link services remain one-cycle assumptions'),
            'precision': 'proposed power-of-two quantization and integer LUT/divider; not paper-validated accuracy',
        },
        'analog_model': 'ideal baseline-cancelled cell-code currents; no off-current, noise, drift, or wire effects',
        'timing_status': 'serialized_service_model_uncalibrated',
        'ppa_status': 'unavailable_for_new_neural_geometry',
    }
    if neural_timing == 'rtl_serial_v1':
        profile['neural_timing'] = neural_timing
        profile['controller_timing'] = json.loads(Path(__file__).with_name('neural_controller_timing.json').read_text())
        profile['timing_status'] = 'rtl_cycle_checked_ideal_interfaces_unvalidated_physical_timing'
    if turn_indicator:
        profile.update(model='differential_w8_cell4_a8_adc8_turn_serial_v1',
            input_size=2*board_size**2+1,turn_indicator=True,
            timing_status='turn_input_component_schedule_not_RTL_validated',
            ppa_status='no_matching_163_input_neural_synthesis')
        profile['provenance']['turn_input']='Black to play = 1; node player word read once, one-cycle latch, extra active input row in each first-layer tile'
    return profile


# --- integer arithmetic and resident cell mapping ---

def round_shift(value, shift):
    value = int(value)
    if shift <= 0:
        return value << -shift
    quotient, remainder = divmod(abs(value), 1 << shift)
    half = 1 << (shift - 1)
    if remainder > half or (remainder == half and quotient % 2):
        quotient += 1
    return -quotient if value < 0 else quotient


def round_divide(numerator, denominator):
    if not 0 <= numerator < 2**48 or not 0 < denominator < 2**32:
        raise OverflowError('Softmax divider requires a 48-bit numerator and 32-bit denominator')
    quotient, remainder = divmod(int(numerator), int(denominator))
    if 2 * remainder > denominator or (2 * remainder == denominator and quotient % 2):
        quotient += 1
    return quotient


def quantize_weights(weights):
    if not np.isfinite(weights).all():
        raise ValueError('Weights must be finite')
    maximum = float(np.max(np.abs(weights)))
    fraction = math.floor(math.log2(127 / maximum)) if maximum else 0
    if not -16 <= fraction <= 30:
        raise ValueError('Weight exponent is outside the supported fixed-point profile')
    codes = np.rint(np.ldexp(weights, fraction)).astype(np.int64)
    if np.max(np.abs(codes)) > 127:
        raise OverflowError('Weight codes exceed symmetric signed eight-bit range')
    return codes, fraction


def map_tiles(weights, profile):
    columns_per_output = profile['weight_slices'] * profile['sign_branches']
    outputs_per_tile = profile['array_columns'] // columns_per_output
    tiles = []
    for output_start in range(0, weights.shape[1], outputs_per_tile):
        output_end = min(output_start + outputs_per_tile, weights.shape[1])
        for row_start in range(0, weights.shape[0], profile['array_rows']):
            row_end = min(row_start + profile['array_rows'], weights.shape[0])
            part = weights[row_start:row_end, output_start:output_end]
            cells = np.zeros((len(part), part.shape[1], 2, 2), dtype=np.uint8)
            for sign in range(2):
                magnitude = np.maximum(part if sign == 0 else -part, 0)
                for cell_slice in range(2):
                    cells[:, :, sign, cell_slice] = (magnitude >> (4 * cell_slice)) & 15
            tiles.append({'row_start': row_start, 'row_end': row_end,
                'output_start': output_start, 'output_end': output_end,
                'cells': cells.reshape(len(part), -1)})
    return tiles


def apply_tiles(inputs, tiles, outputs, input_bits, profile):
    inputs = np.asarray(inputs)
    if inputs.dtype.kind not in 'iu' or np.any(inputs < 0) or np.any(inputs >= 2**input_bits):
        raise ValueError('Input codes do not fit their unsigned precision')
    result = np.zeros(outputs, dtype=np.int64)
    for tile in tiles:
        for start in range(tile['row_start'], tile['row_end'], profile['active_rows']):
            end = min(start + profile['active_rows'], tile['row_end'])
            cells = tile['cells'][start - tile['row_start']:end - tile['row_start']]
            for bit in range(input_bits):
                driven = (inputs[start:end].astype(np.int64) >> bit) & 1
                adc = driven @ cells
                if np.any(adc > 255):
                    raise OverflowError('ADC column sum exceeds eight bits')
                # Ideal integer-unit ADC. Physical current/noise calibration is pending.
                adc = adc.reshape(-1, 2, 2)
                positive = adc[:, 0, 0] + 16 * adc[:, 0, 1]
                negative = adc[:, 1, 0] + 16 * adc[:, 1, 1]
                result[tile['output_start']:tile['output_end']] += (positive - negative) << bit
    if np.any(result < -(2**31)) or np.any(result >= 2**31):
        raise OverflowError('Neural accumulator exceeds signed 32-bit range')
    return result


def sliced_dot(inputs, weights, input_bits=1, profile=None):
    profile = neural_profile(board_size=9, hidden_size=96) if profile is None else profile
    weights = np.asarray(weights)
    if weights.ndim != 2 or weights.shape[0] != len(inputs) or weights.dtype.kind not in 'iu':
        raise ValueError('Expected an integer weight matrix matching the input vector')
    if np.any(weights < -127) or np.any(weights > 127):
        raise ValueError('Weights must be symmetric signed eight-bit codes')
    return apply_tiles(inputs, map_tiles(weights, profile), weights.shape[1], input_bits, profile)


# --- evaluator and its compiled service schedule ---

class NeuralMapping:
    def __init__(self, weights1, weights2, board_size, adc_lanes=3, active_rows=16, sram_word_cycles=1,
                 neural_timing='service', turn_indicator=False):
        if any(np.asarray(weights).dtype.kind not in 'fiu' for weights in (weights1, weights2)):
            raise ValueError('Weights must be real numeric matrices')
        weights1 = np.asarray(weights1, dtype=np.float64)
        weights2 = np.asarray(weights2, dtype=np.float64)
        if (weights1.ndim != 2 or weights1.shape[0] != 2 * board_size**2+int(turn_indicator)
                or weights1.shape[1] == 0 or weights2.shape != (weights1.shape[1], 3)):
            raise ValueError('Expected two-layer weights matching board inputs, declared turn bit and three outputs')
        self.profile = neural_profile(board_size, weights1.shape[1], adc_lanes, active_rows, sram_word_cycles, neural_timing, turn_indicator)
        first, fraction1 = quantize_weights(weights1)
        second, fraction2 = quantize_weights(weights2)
        bound = np.maximum(first[:2*board_size**2].reshape(-1, 2, first.shape[1]).max(axis=1), 0).sum(axis=0)
        if turn_indicator: bound+=np.maximum(first[-1],0)
        shift = 0
        while int(bound.max()) > (255 << shift):
            shift += 1
        self.weight_codes = [first, second]
        self.fractions = [fraction1, fraction2]
        self.hidden_shift = shift
        self.tiles = [map_tiles(first, self.profile), map_tiles(second, self.profile)]
        self.exp_lut = np.rint(np.exp(-np.arange(4097) / 256) * 2**30).astype('<u4')
        self.storage = bytearray(self.profile['storage_bytes'])
        self._write('exp_lut', self.exp_lut, '<u4')
        self.coefficients = {'weight_fraction_bits': self.fractions, 'hidden_right_shift': shift,
            'hidden_scale': 2.0**(shift - fraction1),
            'logit_scale': 2.0**(shift - fraction1 - fraction2),
            'hidden_integer_upper_bound': bound.tolist(),
            'quantized_weight_sha256': [hashlib.sha256(w.astype('<i2').tobytes()).hexdigest() for w in self.weight_codes],
            'exp_lut_sha256': hashlib.sha256(self.exp_lut.tobytes()).hexdigest()}
        self.evaluations = 0
        self.last_state = None
        self.schedule = self._schedule()

    def _write(self, name, values, dtype):
        region = self.profile['storage'][name]
        encoded = np.asarray(values, dtype=dtype).tobytes()
        if len(encoded) > region['bytes']:
            raise MemoryError(f'Neural {name} storage exceeded')
        self.storage[region['offset']:region['offset'] + len(encoded)] = encoded

    def _read(self, name, count, dtype, index=0):
        if index < 0 or count < 0 or (index + count) * np.dtype(dtype).itemsize > self.profile['storage'][name]['bytes']:
            raise MemoryError(f'Neural {name} read exceeds its SRAM region')
        return np.frombuffer(self.storage, dtype=dtype, count=count,
            offset=self.profile['storage'][name]['offset'] + index * np.dtype(dtype).itemsize).copy()

    def bind_memory(self, memory):
        config = memory.config
        if config.get('neural_bytes') != len(self.storage):
            raise MemoryError('Neural scratch does not match the allocated SRAM partition')
        if config['sram_word_cycles'] != self.profile['service_cycles']['sram_word']:
            raise ValueError('Neural and tree SRAM service times disagree')
        start = config['neural_base']
        self.storage = memoryview(memory.node_sram)[start:start + len(self.storage)]
        self._write('exp_lut', self.exp_lut, '<u4')

    def features(self, board, player=None):
        features = encode_board(board, self.profile['board_size']).astype(np.int64)
        if self.profile.get('turn_indicator'):
            if isinstance(player,bool) or not isinstance(player,Integral) or player not in (-1,1):
                raise ValueError('Turn-aware inference requires the current player, black=1 or white=-1')
            features=np.append(features,int(player==1))
        return features

    def forward(self, board, player=None):
        features = self.features(board,player)
        hidden_acc = apply_tiles(features, self.tiles[0], self.profile['hidden_size'], 1, self.profile)
        hidden = np.array([max(0, round_shift(value, self.hidden_shift)) for value in hidden_acc], dtype=np.int64)
        hidden_clipped = int(np.count_nonzero(hidden > 255))
        hidden = np.clip(hidden, 0, 255)
        self._write('hidden', hidden, 'u1')
        hidden = self._read('hidden', self.profile['hidden_size'], 'u1').astype(np.int64)
        logits_acc = apply_tiles(hidden, self.tiles[1], 3, 8, self.profile)
        logit_shift = self.fractions[0] + self.fractions[1] - self.hidden_shift - 12
        logits = [round_shift(value, logit_shift) for value in logits_acc]
        logit_clipped = sum(value < -(2**31) or value >= 2**31 for value in logits)
        logits = [max(-(2**31), min(2**31 - 1, value)) for value in logits]
        self._write('logits', logits, '<i4')
        logits = self._read('logits', 3, '<i4').tolist()
        maximum = max(logits)
        indices = [min(4096, round_shift(maximum - value, 4)) for value in logits]
        exponentials = [int(self._read('exp_lut', 1, '<u4', index=index)[0]) for index in indices]
        denominator = sum(exponentials)
        probabilities = [round_divide(value << 16, denominator) for value in exponentials]
        self._write('probabilities', probabilities, '<u4')
        draw, black = self._read('probabilities', 2, '<u4', index=1)
        value_code = 2 * int(black) + int(draw)
        self._write('value', [value_code], '<u4')
        value = value_code / 2**17
        self.last_state = {'hidden_acc': hidden_acc.tolist(), 'hidden_codes': hidden.tolist(),
            'logits_acc': logits_acc.tolist(), 'logits_q12': logits,
            'lut_indices': indices, 'probabilities_q16': probabilities,
            'value_q17': value_code, 'hidden_saturations': hidden_clipped,
            'logit_saturations': logit_clipped}
        if self.profile.get('turn_indicator'): self.last_state['black_to_play']=int(player==1)
        self.evaluations += 1
        return value

    def _schedule(self):
        profile = self.profile
        services = profile['service_cycles']
        controller = profile.get('controller_timing')
        trace = []
        operations = Counter()
        phases = Counter()
        cursor = 0
        phase = 'layer1'
        context = {}

        def emit(resource, operation, count, cycles, region=None, address=None, size=0):
            nonlocal cursor
            trace.append({'phase': phase, 'resource': resource, 'operation': operation,
                'count': count, 'region': region, 'address': address, 'bytes': size,
                'start': cursor, 'end': cursor + cycles, **context})
            operations[operation] += count
            phases[phase] += cycles
            cursor += cycles

        def transfer(operation, region, address, size):
            if address % 4 or size % 4 or size <= 0:
                raise ValueError('Neural SRAM transfers must be word-aligned')
            words = size // 4
            if controller:
                for word in range(words):
                    emit('neural_controller', 'sram_request_handshakes', 1,
                         controller['cycles']['sram_request'], region, address + 4 * word, 4)
                    emit('node_sram', 'node_sram_' + operation + '_words', 1,
                         services['sram_word'], region, address + 4 * word, 4)
            else:
                emit('node_sram', 'node_sram_' + operation + '_words', words,
                     words * services['sram_word'], region, address, size)

        if profile.get('turn_indicator'):
            transfer('read','player',0,4)
            emit('neural_controller','turn_input_latches',1,services['digital'])
        for layer, tiles in enumerate(self.tiles):
            phase = 'layer' + str(layer + 1)
            input_bits = 1 if layer == 0 else 8
            previous_output = None
            for index, tile in enumerate(tiles):
                outputs = tile['output_end'] - tile['output_start']
                columns = tile['cells'].shape[1]
                context = {'array_id': index + (0 if layer == 0 else len(self.tiles[0])),
                    'outputs': [tile['output_start'], tile['output_end']]}
                if tile['output_start'] != previous_output:
                    emit('accumulator_registers', 'accumulator_clears', 1, services['digital'])
                    previous_output = tile['output_start']
                for start in range(tile['row_start'], tile['row_end'], profile['active_rows']):
                    end = min(start + profile['active_rows'], tile['row_end'])
                    context = {'array_id': index + (0 if layer == 0 else len(self.tiles[0])),
                        'outputs': [tile['output_start'], tile['output_end']], 'active_rows': [start, end]}
                    if layer == 0:
                        transfer('read', 'board', (start // 32) * 4, 4)
                    else:
                        address = (start // 4) * 4
                        transfer('read', 'hidden', address, 4 * ((end - address + 3) // 4))
                    for bit in range(input_bits):
                        context.pop('columns', None)
                        context['input_bit'] = bit
                        emit('binary_drivers', 'dac_bit_drives', end - start, services['drive'])
                        emit('array', 'array_pulses', 1, services['array_settle'])
                        for column in range(0, columns, profile['adc_lanes']):
                            count = min(profile['adc_lanes'], columns - column)
                            context['columns'] = [column, column + count]
                            emit('column_mux', 'mux_groups', 1, services['mux'])
                            emit('sample_hold', 'samples', count, services['sample_hold'])
                            if controller:
                                emit('neural_controller', 'adc_request_handshakes', 1,
                                     controller['cycles']['adc_request'])
                            emit('adc_bank', 'adc_groups', 1, services['adc_group'])
                            trace[-1]['conversions'] = count
                            operations['adc_conversions'] += count
                            words = (count + 3) // 4
                            emit('readout_bus', 'readout_words', words, words * services['readout_word'])
                            emit('shift_add_lane', 'shift_adds', count, count * services['shift_add'])
                last_row_tile = index + 1 == len(tiles) or tiles[index + 1]['output_start'] != tile['output_start']
                if last_row_tile:
                    context = {'outputs': [tile['output_start'], tile['output_end']]}
                    if controller:
                        step = 4 if layer == 0 else 1
                        for output in range(0, outputs, step):
                            count = min(step, outputs - output)
                            if layer == 0:
                                emit('activation_lane', 'hidden_activations', count, count * services['digital'])
                                transfer('write', 'hidden', tile['output_start'] + output, 4)
                            else:
                                emit('scale_lane', 'logit_rescales', 1, services['digital'])
                                transfer('write', 'logits', 4 * (tile['output_start'] + output), 4)
                    elif layer == 0:
                        emit('activation_lane', 'hidden_activations', outputs, outputs * services['digital'])
                        transfer('write', 'hidden', tile['output_start'], 4 * ((outputs + 3) // 4))
                    else:
                        emit('scale_lane', 'logit_rescales', outputs, outputs * services['digital'])
                        transfer('write', 'logits', 4 * tile['output_start'], 4 * outputs)

        phase = 'output'
        context = {}
        transfer('read', 'logits', 0, 12)
        emit('output_alu', 'max_comparisons', 2, 2 * services['digital'])
        for output in range(3):
            emit('output_alu', 'lut_addresses', 1, services['digital'])
            # Data-dependent LUT address is supplied by the execution state.
            begin = len(trace)
            transfer('read', 'exp_lut', 0, 4)
            for row in trace[begin:]:
                row['address_source'] = f'last_state.lut_indices[{output}] * 4'
                row['lut_output'] = output
        emit('output_alu', 'exponential_sums', 3, 3 * services['digital'])
        for output in range(3):
            emit('divider', 'divide_setups', 1, services['digital'])
            emit('divider', 'divide_bits', 48, 48 * services['divide_bit'])
            emit('output_alu', 'probability_rounds', 1, services['digital'])
            if controller:
                emit('neural_controller', 'divider_completion_handshakes', 1,
                     controller['cycles']['divider_completion'])
            transfer('write', 'probabilities', 4 * output, 4)
        transfer('read', 'probabilities', 4, 8)
        emit('output_alu', 'value_formations', 1, services['digital'])
        transfer('write', 'value', 0, 4)
        arrays = sum(len(tiles) for tiles in self.tiles)
        weights = sum(w.size for w in self.weight_codes)
        encoded = json.dumps(trace, sort_keys=True, separators=(',', ':')).encode()
        resources = {'logical_weights': weights, 'mapped_cells': weights * 4,
            'array_count': arrays, 'allocated_cells': arrays * 256 * 128,
            'adc_lanes': profile['adc_lanes'], 'sample_hold_lanes': profile['adc_lanes'],
            'binary_driver_lanes': profile['active_rows'], 'shift_add_lanes': 1,
            'input_register_bits': profile['active_rows'] * 8,
            'sram_word_register_bits': 32,
            'accumulator_register_bits': 32 * 32, 'adc_register_bits': profile['adc_lanes'] * 8,
            'readout_bus_bits': 32, 'logit_register_bits': 3 * 32,
            'exponential_register_bits': 3 * 32,
            'divider_register_bits': {'numerator': 48, 'denominator': 32, 'remainder': 33, 'quotient': 48},
            'coefficient_register_bits': 3 * 32,
            'control_status': 'sequencer, routing, decode, and power-state circuitry not synthesized'}
        if profile.get('turn_indicator'): resources['turn_input_register_bits']=1
        if controller:
            resources['resource_basis'] = 'service-model storage budget; exact synthesized state is recorded separately in controller_timing evidence'
            resources['control_status'] = 'neural sequencer and node router pass generic synthesis; full MCTS control and physical costs remain open'
        return {'resources': resources, 'operations': dict(operations), 'phase_cycles': dict(phases),
            'cycles': cursor, 'storage_bytes': profile['storage_bytes'],
            'coefficient_initialization_words': len(self.exp_lut),
            'schedule_sha256': hashlib.sha256(encoded).hexdigest(), 'trace': trace}

    def estimate(self, capture_trace=False):
        result = {name: value for name, value in self.schedule.items() if name != 'trace'}
        result['profile'] = self.profile
        result['coefficients'] = self.coefficients
        if capture_trace:
            result['trace'] = self.schedule['trace']
        return result

    def inference_trace(self, resource=None):
        if self.last_state is None:
            raise RuntimeError('Run an inference before requesting its resolved trace')
        result = []
        for row in self.schedule['trace']:
            if resource is not None and row['resource'] != resource:
                continue
            row = dict(row)
            if 'lut_output' in row:
                row['address'] = self.last_state['lut_indices'][row['lut_output']] * 4
            result.append(row)
        return result
