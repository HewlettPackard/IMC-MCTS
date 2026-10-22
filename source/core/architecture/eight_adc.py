# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Eight shared converters, serial 32-bit drain and one shift/add lane.
# SPDX-License-Identifier: MIT
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from core.architecture.analog_readout import configure_readout, DRIVEN
from core.architecture.neural_mapping import NeuralMapping
from core.architecture.parallel_selection import FourLaneSimulation, FourLaneGoSimulation

SPEC=Path(__file__).with_suffix('.json')


def rollout_spec():
    raw=SPEC.read_bytes(); spec=json.loads(raw)
    if (spec['adc_lanes'],spec['adc_bits'],spec['readout_bus_bits'],spec['shift_add_lanes'],
            spec['active_rows'],spec['overlap'])!=(8,8,32,1,16,False):
        raise ValueError('Unsupported eight-ADC rollout contract')
    return spec|{'sha256':hashlib.sha256(raw).hexdigest()}


class EightADCRollout:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.rollout_spec=rollout_spec()
        configure_readout(self,DRIVEN)
        self.reference_neural_profile=deepcopy(self.neural.profile)
        reference_coefficients=deepcopy(self.neural.coefficients)
        self.neural=NeuralMapping(*self.weights,self.board_size,adc_lanes=8,active_rows=16,
            sram_word_cycles=2,turn_indicator=self.reference_neural_profile.get('turn_indicator',False))
        self.neural.bind_memory(self.memory)
        configure_readout(self,DRIVEN)
        if self.neural.coefficients!=reference_coefficients:
            raise ValueError('ADC sharing must not change quantization or evaluator coefficients')
        self.neural.profile.update(rollout_profile=self.rollout_spec['profile'],
            rollout_spec_sha256=self.rollout_spec['sha256'],
            timing_status=self.rollout_spec['timing_status'],ppa_status='explicit_neural_controller_report_proxy_required')
        self.neural.profile['provenance']['geometry_and_sharing']='256x128 arrays, one active array and eight shared 8-bit ADCs; two 32-bit readout words per full group; one serial shift/add lane'
        self.memory.config.update(execution_profile=self.memory.config['execution_profile']+'_adc8_serial_v1',
            rollout_profile=self.rollout_spec['profile'],rollout_spec_sha256=self.rollout_spec['sha256'],
            timing_status=self.rollout_spec['timing_status'])


class EightADCSimulation(EightADCRollout,FourLaneSimulation):
    pass


class EightADCGoSimulation(EightADCRollout,FourLaneGoSimulation):
    pass
