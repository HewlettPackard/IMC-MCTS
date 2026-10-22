# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Independent scalar ADC-lane and padded-word replay of an offset layer.
# SPDX-License-Identifier: MIT


def replay_layer(inputs, signed_weights, input_bits):
    inputs = [int(x) for x in inputs]
    rows = [[int(x) for x in row] for row in signed_weights]
    outputs = len(rows[0])
    sums = [0]*outputs
    counts = {'adc_groups':0,'adc_conversions':0,'readout_words':0,'shift_adds':0,
              'offset_input_adds':len(inputs),'offset_subtracts':outputs,'array_pulses':0}
    peak = 0
    for start in range(0,len(inputs),16):
        stop = min(start+16,len(inputs))
        for bit in range(input_bits):
            counts['array_pulses'] += 1
            for column in range(0,outputs,8):
                valid = min(8,outputs-column)
                lanes = [0]*8
                for lane in range(valid):
                    for row in range(start,stop):
                        if (inputs[row] >> bit) & 1:
                            lanes[lane] += rows[row][column+lane]+128
                    assert 0 <= lanes[lane] <= 4095
                    peak = max(peak,lanes[lane])
                words = []
                for lane in range(0,valid,2):
                    words.append(lanes[lane] | (lanes[lane+1] << 16))
                for lane in range(valid):
                    recovered = (words[lane//2] >> (16*(lane%2))) & 65535
                    assert recovered == lanes[lane] and recovered < 4096
                    sums[column+lane] += recovered << bit
                counts['adc_groups'] += 1
                counts['adc_conversions'] += valid
                counts['readout_words'] += len(words)
                counts['shift_adds'] += valid
    correction = sum(inputs)*128
    result = [v-correction for v in sums]
    return result, counts, peak
