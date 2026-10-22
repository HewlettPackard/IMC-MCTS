# Column storage before shared ADCs, separate from the validated driven array.
# SPDX-License-Identifier: MIT
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math

import numpy as np

from core.algorithm.evaluator import encode_board
from core.architecture.neural_mapping import NeuralMapping, round_shift, round_divide

DRIVEN='sustained_drive_v1'
BUFFERED='column_hold_v1'
CAPTURE_CYCLES=1


def readout_spec(mode=DRIVEN):
    if mode not in (DRIVEN,BUFFERED): raise ValueError('Unknown analog readout profile')
    return {'profile':mode,'capture_cycles':CAPTURE_CYCLES if mode==BUFFERED else 0,
        'capture_timing_status':'One assumed 2 ns capture cycle; acquisition and settling require circuit characterization',
        'array_drive':'through_capture_only' if mode==BUFFERED else 'through_all_column_groups',
        'storage':'one analog sample per physical column per array' if mode==BUFFERED else 'shared ADC input S/H lanes only',
        'overlap':False,'adc_request_cycles':1,
        'adc_request_source':'NEURAL_RTL_SPEC.md and imc_neural_sequencer.sv: ST_ADC_REQ handshake',
        'analog_model':'Ideal voltage samples in ADC-code units; no droop, noise, offset, charge injection or wire drop',
        'physical_status':'Uncharacterized analog interface',
        'precedent':'https://nlp.cs.utah.edu/assets/pdfs/shafiee2016isaac.pdf, section V, column S/H before shared ADC; no PPA copied',
        'circuit_requirements_source':'https://www.analog.com/mt-090'}


def readout_inventory(profile):
    spec=profile.get('readout',readout_spec())
    cols=profile['array_columns']; rows=profile['array_rows']
    per_output=profile['weight_slices']*profile['sign_branches']
    arrays=math.ceil(profile['input_size']/rows)*math.ceil(profile['hidden_size']/(cols//per_output))+math.ceil(profile['hidden_size']/rows)*math.ceil(profile['outputs']/(cols//per_output))
    buffered=spec['profile']==BUFFERED
    return spec | {'installed_arrays':arrays,'column_banks':arrays if buffered else 0,
        'samples_per_bank':cols if buffered else 0,'installed_analog_samples':arrays*cols if buffered else 0,
        'peak_live_column_samples':cols if buffered else 0,'shared_adc_lanes':profile['adc_lanes'],
        'adc_input_sample_hold_lanes':profile['adc_lanes'],
        'digital_adc_result_bits':profile['adc_lanes']*profile['adc_bits'],
        'neural_sram_bytes':profile['storage_bytes'],
        'sample_storage_is_sram':False,
        'front_end':'Per-column current-to-voltage conditioning and capture switches; shared downstream mux, buffered drive and ADC references need characterization'}


def column_groups(columns, profile):
    s=profile['service_cycles']; cursor=0; result=[]
    # Times are relative to the completed parallel capture, or to array settle.
    for column in range(0,columns,profile['adc_lanes']):
        count=min(profile['adc_lanes'],columns-column)
        sample=cursor+s['mux']+s['sample_hold']
        end=sample+1+s['adc_group']+math.ceil(count/4)*s['readout_word']+count*s['shift_add']
        result.append({'column':column,'count':count,'sample_cycle':sample,'end_cycle':end})
        cursor=end
    return result


def readout_activity(model):
    profile=model.profile; s=profile['service_cycles']; spec=profile.get('readout',readout_spec())
    buffered=spec['profile']==BUFFERED
    captures=conversions=groups=driven_cycles=max_hold=0
    burst_rows=[]
    for layer,tiles in enumerate(model.tiles):
        bits=1 if layer==0 else 8
        for index,tile in enumerate(tiles):
            columns=tile['cells'].shape[1]; sequence=column_groups(columns,profile)
            bursts=math.ceil((tile['row_end']-tile['row_start'])/profile['active_rows'])*bits
            on=s['drive']+s['array_settle']+(spec['capture_cycles'] if buffered else sequence[-1]['end_cycle'])
            hold=sequence[-1]['sample_cycle'] if buffered else 0
            captures+=bursts; conversions+=bursts*columns; groups+=bursts*len(sequence)
            driven_cycles+=bursts*on; max_hold=max(max_hold,hold)
            burst_rows.append({'layer':layer+1,'array_id':index+(0 if layer==0 else len(model.tiles[0])),
                'bursts':bursts,'mapped_columns':columns,'groups_per_burst':len(sequence),
                'array_on_cycles_per_burst':on,'maximum_hold_cycles':hold})
    return {'profile':spec['profile'],'array_read_bursts':captures,'adc_conversions':conversions,
        'adc_groups':groups,'column_capture_events':captures if buffered else 0,
        'column_samples_captured':conversions if buffered else 0,
        'additional_capture_cycles':captures*spec['capture_cycles'],
        'array_active_cycles':driven_cycles,'array_active_ns':driven_cycles*1000/profile['clock_mhz'],
        'maximum_column_hold_cycles':max_hold,'maximum_column_hold_ns':max_hold*1000/profile['clock_mhz'],
        'timing_boundary':'Unstalled serial readout including one ADC request cycle per group; excludes preloading and host work',
        'energy_status':'Activity only; array/front-end/hold/ADC energy is not characterized',
        'arrays':burst_rows}


class ColumnHoldBank:
    def __init__(self, capacity):
        if type(capacity) is not int or capacity<=0: raise ValueError('Positive analog sample capacity required')
        self.capacity=capacity; self.values=np.zeros(capacity); self.valid=np.zeros(capacity,dtype=bool)
        self.captured_at=0; self.last_cycle=0

    def capture(self, values, cycle):
        values=np.asarray(values,dtype=np.float64)
        if self.valid.any(): raise RuntimeError('Column bank still owns unread samples')
        if values.ndim!=1 or not 0<len(values)<=self.capacity: raise ValueError('Column sample capacity exceeded')
        if not np.isfinite(values).all() or np.any(values<0) or np.any(values>255): raise ValueError('Analog sample outside ADC range')
        if type(cycle) is not int or cycle<self.last_cycle: raise ValueError('Capture time goes backwards')
        self.values[:len(values)]=values
        self.valid[:len(values)]=True; self.captured_at=cycle; self.last_cycle=cycle

    def sample(self, column, count, cycle):
        if type(column) is not int or type(count) is not int or column<0 or count<=0 or column+count>self.capacity:
            raise ValueError('Column selection exceeds bank')
        if type(cycle) is not int or cycle<self.last_cycle: raise ValueError('Sample time goes backwards')
        if not self.valid[column:column+count].all(): raise RuntimeError('Column sample missing or already consumed')
        self.valid[column:column+count]=False; self.last_cycle=cycle
        # Continuous samples are rounded only at the ideal ADC boundary.
        return np.rint(self.values[column:column+count]).astype(np.int64)


class BufferedNeuralMapping(NeuralMapping):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.profile['readout']=readout_spec(BUFFERED)
        self.profile['timing_status']='column_hold_architecture_schedule_not_RTL_validated'
        self.banks=[ColumnHoldBank(self.profile['array_columns']) for tiles in self.tiles for tile in tiles]
        self.schedule=deepcopy(self.schedule)
        trace=[]; extra=0
        operations=Counter(self.schedule['operations']); phases=Counter(self.schedule['phase_cycles'])
        for row in self.schedule['trace']:
            row['start']+=extra; row['end']+=extra; trace.append(row)
            if row['operation']=='array_pulses':
                tile=[t for tiles in self.tiles for t in tiles][row['array_id']]
                capture=row | {'resource':'column_hold','operation':'column_samples_captured',
                    'count':tile['cells'].shape[1],'start':row['end'],'end':row['end']+CAPTURE_CYCLES}
                trace.append(capture); extra+=CAPTURE_CYCLES
                operations['column_samples_captured']+=capture['count']; operations['column_capture_events']+=1
                phases[row['phase']]+=CAPTURE_CYCLES
        self.schedule.update(trace=trace,cycles=self.schedule['cycles']+extra,
            operations=dict(operations),phase_cycles=dict(phases),
            schedule_sha256=hashlib.sha256(json.dumps(trace,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        self.schedule['resources']['column_hold']=readout_inventory(self.profile)
        self.activity=readout_activity(self)

    def apply_buffered(self, inputs, layer):
        inputs=np.asarray(inputs)
        if inputs.dtype.kind not in 'iu': raise ValueError('Integer input codes required')
        inputs=inputs.astype(np.int64)
        bits=1 if layer==0 else 8
        if np.any(inputs<0) or np.any(inputs>=2**bits): raise ValueError('Input codes outside unsigned range')
        result=np.zeros(self.profile['hidden_size'] if layer==0 else 3,dtype=np.int64)
        for index,tile in enumerate(self.tiles[layer]):
            bank=self.banks[index+(0 if layer==0 else len(self.tiles[0]))]
            groups=column_groups(tile['cells'].shape[1],self.profile)
            for start in range(tile['row_start'],tile['row_end'],self.profile['active_rows']):
                end=min(start+self.profile['active_rows'],tile['row_end'])
                cells=tile['cells'][start-tile['row_start']:end-tile['row_start']]
                for bit in range(bits):
                    analog=((inputs[start:end]>>bit)&1)@cells
                    captured_at=bank.last_cycle+CAPTURE_CYCLES
                    bank.capture(analog,captured_at)
                    adc=np.empty(len(analog),dtype=np.int64)
                    for group in groups:
                        column=group['column']; count=group['count']
                        adc[column:column+count]=bank.sample(column,count,captured_at+group['sample_cycle'])
                    if bank.valid.any(): raise AssertionError('Unread column samples at end of burst')
                    bank.last_cycle=captured_at+groups[-1]['end_cycle']
                    adc=adc.reshape(-1,2,2)
                    signed=adc[:,0,0]+16*adc[:,0,1]-adc[:,1,0]-16*adc[:,1,1]
                    result[tile['output_start']:tile['output_end']]+=signed<<bit
        if np.any(result<-(2**31)) or np.any(result>=2**31): raise OverflowError('Accumulator exceeds signed 32-bit range')
        return result

    def forward(self, board, player=None):
        # Keep the original checked implementation intact as the differential oracle.
        # This candidate owns both buffered dot products and its integer output path.
        features=self.features(board,player)
        hidden_acc=self.apply_buffered(features,0)
        hidden=np.array([max(0,round_shift(value,self.hidden_shift)) for value in hidden_acc],dtype=np.int64)
        hidden_clipped=int(np.count_nonzero(hidden>255)); hidden=np.clip(hidden,0,255)
        self._write('hidden',hidden,'u1')
        hidden=self._read('hidden',self.profile['hidden_size'],'u1').astype(np.int64)
        logits_acc=self.apply_buffered(hidden,1)
        shift=self.fractions[0]+self.fractions[1]-self.hidden_shift-12
        logits=[round_shift(value,shift) for value in logits_acc]
        logit_clipped=sum(value<-(2**31) or value>=2**31 for value in logits)
        logits=[max(-(2**31),min(2**31-1,value)) for value in logits]
        self._write('logits',logits,'<i4'); logits=self._read('logits',3,'<i4').tolist()
        maximum=max(logits); indices=[min(4096,round_shift(maximum-value,4)) for value in logits]
        exponentials=[int(self._read('exp_lut',1,'<u4',index=index)[0]) for index in indices]
        denominator=sum(exponentials)
        probabilities=[round_divide(value<<16,denominator) for value in exponentials]
        self._write('probabilities',probabilities,'<u4')
        draw,black=self._read('probabilities',2,'<u4',index=1); value_code=2*int(black)+int(draw)
        self._write('value',[value_code],'<u4')
        self.last_state={'hidden_acc':hidden_acc.tolist(),'hidden_codes':hidden.tolist(),
            'logits_acc':logits_acc.tolist(),'logits_q12':logits,'lut_indices':indices,
            'probabilities_q16':probabilities,'value_q17':value_code,
            'hidden_saturations':hidden_clipped,'logit_saturations':logit_clipped}
        if self.profile.get('turn_indicator'): self.last_state['black_to_play']=int(player==1)
        self.evaluations+=1
        return value_code/2**17


def controller_profile(profile, mode):
    if mode!=BUFFERED: return profile
    base,version=profile.rsplit('_v',1)
    return base+'_column_hold_v'+version


def configure_readout(model, mode):
    spec=readout_spec(mode)
    if mode==BUFFERED:
        model.neural=BufferedNeuralMapping(*model.weights,model.board_size,sram_word_cycles=2,
            turn_indicator=model.neural.profile.get('turn_indicator',False))
        model.neural.bind_memory(model.memory)
        model.memory.config['execution_profile']=controller_profile(model.memory.config['execution_profile'],mode)
        model.memory.config['timing_status']='column_hold_architecture_schedule_not_RTL_validated'
    else: model.neural.profile['readout']=spec
    model.neural.profile['readout_activity']=readout_activity(model.neural)
