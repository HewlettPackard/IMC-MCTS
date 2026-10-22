# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Scalar column/lane/word replay, independent of the vectorized matrix executor.
# SPDX-License-Identifier: MIT
from collections import Counter


def replay_layer(inputs,weights,bits,lanes=8):
    if lanes not in (3,8): raise ValueError('Only the compared lane counts are supported')
    outputs=[0]*weights.shape[1]; counts=Counter(); groups=[]
    for output_base in range(0,len(outputs),32):
        columns=4*min(32,len(outputs)-output_base)
        for row_base in range(0,len(inputs),16):
            for bit in range(bits):
                counts['array_pulses']+=1
                for first in range(0,columns,lanes):
                    valid=min(lanes,columns-first); register=0
                    for lane in range(valid):
                        column=first+lane; output=output_base+column//4
                        negative=(column%4)//2; nibble=column%2; sample=0
                        for row in range(row_base,min(len(inputs),row_base+16)):
                            weight=int(weights[row,output])
                            magnitude=max(-weight if negative else weight,0)
                            cell=(magnitude>>(4*nibble))&15
                            sample+=((int(inputs[row])>>bit)&1)*cell
                        if not 0<=sample<=255: raise OverflowError('Eight-bit ADC saturation')
                        register|=sample<<(8*lane)
                    words=[(register>>(32*word))&0xffffffff for word in range((valid+3)//4)]
                    for lane in range(valid):
                        sample=(words[lane//4]>>(8*(lane%4)))&255
                        column=first+lane; output=output_base+column//4
                        sign=-1 if column%4>=2 else 1
                        outputs[output]+=sign*(sample<<(bit+4*(column%2)))
                        if not -(2**31)<=outputs[output]<2**31: raise OverflowError('32-bit accumulator overflow')
                    counts['adc_groups']+=1; counts['adc_conversions']+=valid
                    counts['readout_words']+=len(words); counts['shift_adds']+=valid
                    groups.append({'columns':(first,first+valid),'valid_lanes':valid,'bus_words':len(words)})
    return outputs,dict(counts),groups
