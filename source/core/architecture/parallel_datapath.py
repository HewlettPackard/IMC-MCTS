# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Buffered UCB16 and ADC32 execution, preserving the scalar integer contract.
# SPDX-License-Identifier: MIT
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from numbers import Integral

import numpy as np

from core.architecture.block_activity import BLOCKS, phase_activity
from core.architecture.neural_mapping import round_shift, round_divide
from core.architecture.offset_encoding import OffsetNeuralMapping
from core.architecture.ucb_arithmetic import score
from core.architecture.ucb_overlap import OverlappedUCBGoSimulation
from core.simulator.tree_memory import NO_NODE

SPEC = Path(__file__).with_suffix('.json')
LANES = tuple('u_ucb_'+str(i).zfill(2) for i in range(16))


def datapath_spec():
    raw = SPEC.read_bytes()
    result = json.loads(raw)
    expected = {'ucb_lanes':16,'candidate_banks':2,'adc_lanes':32,'adc_bits':12,
        'adc_slot_bits':16,'adc_service_cycles':13,'adc_result_banks':2,'readout_staging_bits':512,
        'readout_bus_bits':128,'accumulator_lanes':8,'active_rows':16}
    if any(result[k] != v for k,v in expected.items()):
        raise ValueError('Unreviewed parallel datapath configuration')
    return result | {'sha256':hashlib.sha256(raw).hexdigest()}


def check_intervals(events, groups):
    for resource in {r['resource'] for r in events}:
        spans = sorted((r['start'],r['end']) for r in events if r['resource']==resource)
        if any(a < 0 or b <= a for a,b in spans): raise AssertionError('Invalid interval')
        if any(a[1] > b[0] for a,b in zip(spans,spans[1:])):
            raise AssertionError('Concurrent use of '+resource)
    for bank in {g['bank'] for g in groups}:
        spans = sorted((g['start'],g['end']) for g in groups if g['bank']==bank)
        if any(a[1] > b[0] for a,b in zip(spans,spans[1:])):
            raise AssertionError('Result bank overwritten before release')
    for g in groups:
        if not g['start'] <= g['ready'] <= g['consume'] <= g['end']:
            raise AssertionError('Consumer preceded producer')


def column_pipeline(outputs, lanes=32, bus_bits=128, accumulators=8, adc_cycles=13, banks=2):
    values=(outputs,lanes,bus_bits,accumulators,adc_cycles,banks)
    if any(isinstance(v,bool) or not isinstance(v,Integral) or v<=0 for v in values) or bus_bits<16 or bus_bits%16:
        raise ValueError('Readout resources must be positive integers with a 16-bit-aligned bus')
    producer = consumer = 0
    free = [0]*banks
    events = []; groups = []
    for index,column in enumerate(range(0,outputs,lanes)):
        count = min(lanes,outputs-column); bank = index % banks
        start = cursor = max(producer,free[bank])
        for resource,operation,n,duration in [('column_mux','mux_groups',1,1),
            ('sample_hold','samples',count,1),('neural_controller','adc_request_handshakes',1,1),
            ('adc_bank','adc_groups',1,adc_cycles)]:
            events.append({'resource':resource,'operation':operation,'count':n,
                'start':cursor,'end':cursor+duration,'columns':[column,column+count],
                'group':index,'bank':bank})
            if resource=='adc_bank': events[-1]['conversions'] = count
            cursor += duration
        ready = producer = cursor
        consume = max(ready,consumer)
        words = (count+bus_bits//16-1)//(bus_bits//16)
        adds = (count+accumulators-1)//accumulators
        events.append({'resource':'readout_bus','operation':'readout_words','count':words,
            'start':consume,'end':consume+words,'columns':[column,column+count],
            'group':index,'bank':bank})
        end = consume+words+adds
        events.append({'resource':'shift_add_lanes','operation':'shift_adds','count':count,
            'start':consume+words,'end':end,'columns':[column,column+count],
            'group':index,'bank':bank})
        consumer = free[bank] = end
        groups.append({'group':index,'column':column,'count':count,'bank':bank,
            'start':start,'ready':ready,'consume':consume,'end':end,'words':words,'add_cycles':adds})
    events.sort(key=lambda r:(r['start'],r['end'],r['resource']))
    check_intervals(events,groups)
    return {'cycles':max(producer,consumer),'groups':groups,'trace':events,
        'bus_bits':bus_bits,'accumulator_lanes':accumulators,'lanes':lanes,'banks':banks}


def candidate_pipeline(visited, lanes=16, banks=2, busy_cycles=169, word_cycles=2):
    values=(lanes,banks,busy_cycles,word_cycles)
    if not isinstance(visited,(tuple,list)) or not visited or any(type(v) is not bool for v in visited):
        raise ValueError('A nonempty list of Boolean candidate flags is required')
    if any(isinstance(v,bool) or not isinstance(v,Integral) or v<=0 for v in values):
        raise ValueError('Candidate resource counts and service cycles must be positive integers')
    if any(not v for v in visited[:-1]): raise ValueError('Stop loading at the first unvisited child')
    producer = consumer = 0
    free = [0]*banks
    events = []; groups = []
    for index,first in enumerate(range(0,len(visited),lanes)):
        count = min(lanes,len(visited)-first); bank = index % banks
        valid = sum(visited[first:first+count])
        start = cursor = max(producer,free[bank])
        for child in range(first,first+count):
            for word in range(6):
                events.append({'resource':'selection_loader','operation':'sram_request',
                    'start':cursor,'end':cursor+1,'candidate':child,'word':word,'group':index})
                cursor += 1
                events.append({'resource':'node_sram','operation':'candidate_read',
                    'start':cursor,'end':cursor+word_cycles,'candidate':child,'word':word,'group':index})
                cursor += word_cycles
            events.append({'resource':'selection_loader','operation':'candidate_control',
                'start':cursor,'end':cursor+4,'candidate':child,'group':index})
            cursor += 4
        ready = producer = cursor
        consume = cursor = max(ready,consumer)
        if valid:
            for resource,operation,duration in [('score_controller','dispatch',1),
                ('ucb_bank','score',busy_cycles),('score_controller','ordered_reduce',valid),
                ('score_controller','capture',1)]:
                events.append({'resource':resource,'operation':operation,'start':cursor,
                    'end':cursor+duration,'group':index,'valid_lanes':valid})
                cursor += duration
        consumer = free[bank] = cursor
        groups.append({'group':index,'first':first,'count':count,'valid_lanes':valid,'bank':bank,
            'start':start,'ready':ready,'consume':consume,'end':cursor})
    events.sort(key=lambda r:(r['start'],r['end'],r['resource']))
    check_intervals(events,groups)
    return {'cycles':max(producer,consumer),'groups':groups,'trace':events}


def parallel_dot(inputs, cells, input_bits, kernel):
    x = np.asarray(inputs); cells = np.asarray(cells)
    if x.ndim!=1 or x.dtype.kind not in 'iu' or np.any(x<0) or np.any(x>=2**input_bits):
        raise ValueError('Input code outside declared precision')
    if cells.ndim!=2 or len(cells)!=len(x) or cells.dtype.kind not in 'iu' or np.any(cells<0) or np.any(cells>255):
        raise ValueError('Expected one unsigned 8-bit cell per weight')
    raw = np.zeros(cells.shape[1],dtype=np.int64); peak = 0
    slots = kernel['bus_bits']//16
    for start in range(0,len(x),16):
        end = min(start+16,len(x))
        for bit in range(input_bits):
            adc = ((x[start:end].astype(np.int64)>>bit)&1) @ cells[start:end].astype(np.int64)
            peak = max(peak,int(adc.max()))
            if np.any(adc>=4096): raise OverflowError('ADC code overflow')
            banks = {}; actions = []
            for group in kernel['groups']:
                actions.extend([(group['ready'],0,group),(group['end'],1,group)])
            for _,operation,group in sorted(actions,key=lambda e:(e[0],e[1],e[2]['group'])):
                bank = group['bank']; column = group['column']; count = group['count']
                if operation==0:
                    if bank in banks: raise AssertionError('ADC overwrote unread result')
                    words = []
                    for first in range(0,count,slots):
                        words.append(sum(int(adc[column+i]) << (16*(i-first))
                            for i in range(first,min(first+slots,count))))
                    banks[bank] = (group['group'],words)
                else:
                    owner,words = banks.pop(bank)
                    if owner != group['group']: raise AssertionError('Wrong ADC buffer tag')
                    for first in range(0,count,kernel['accumulator_lanes']):
                        columns = range(column+first,column+min(first+kernel['accumulator_lanes'],count))
                        if len({c%kernel['accumulator_lanes'] for c in columns}) != len(columns):
                            raise AssertionError('Accumulator register-bank conflict')
                        for c in columns:
                            i = c-column
                            raw[c] += ((words[i//slots] >> (16*(i%slots))) & 65535) << bit
            if banks: raise AssertionError('Undrained ADC buffer')
    correction = 128*int(x.astype(np.int64).sum()); result = raw-correction
    if np.any(raw>=2**31) or np.any(result<-(2**31)) or np.any(result>=2**31):
        raise OverflowError('Accumulator overflow')
    return result,{'input_sum':correction//128,'correction':correction,
        'peak_adc_code':peak,'raw_sums':raw.tolist()}


class ParallelNeuralMapping(OffsetNeuralMapping):
    def __init__(self,*args,**kwargs):
        adc_cycles = kwargs.pop("service_cycles",13)
        super().__init__(*args,**kwargs)
        self.serial_schedule = deepcopy(self.schedule)
        self.spec = datapath_spec()
        self.kernels = [column_pipeline(c.shape[1],adc_cycles=adc_cycles) for c in self.cells]
        self.schedule = self._parallel_schedule()
        self.profile.update(model=self.spec['profile'],rollout_profile=self.spec['profile'],
            rollout_spec_sha256=self.spec['sha256'],adc_lanes=32,readout_bus_bits=128,
            shift_add_lanes=8,timing_status=self.spec['timing_status'],
            readout={'profile':'sustained_drive_v1','overlap':True,'array_drive':'through_all_column_groups',
                'storage':'two 32-by-16-bit result banks; one 512-bit staging register; eight banked accumulator ALUs'},
            ppa_status='Connected digital readout uses native65 synthesis estimates; analog parts and residual controls retain source-linked engineering assumptions')
        self.profile['adc_service_cycles'] = adc_cycles
        self.profile['readout_activity'] = self._readout_activity()

    def _parallel_schedule(self):
        old = self.serial_schedule['trace']; rows = []; ops = Counter(); phases = Counter()
        cursor = i = 0
        group_ops = {'mux_groups','samples','adc_request_handshakes','adc_groups','readout_words','shift_adds'}
        while i < len(old):
            row = old[i]
            if row['operation']=='mux_groups':
                kernel = self.kernels[row['array_id']]
                context = {k:v for k,v in row.items() if k not in
                    ('resource','operation','count','start','end','columns','conversions')}
                for event in kernel['trace']:
                    event = context | event | {'start':cursor+event['start'],'end':cursor+event['end']}
                    rows.append(event); ops[event['operation']] += event['count']
                    if 'conversions' in event: ops['adc_conversions'] += event['conversions']
                phases[row['phase']] += kernel['cycles']; cursor += kernel['cycles']
                while i<len(old) and old[i]['operation'] in group_ops: i+=1
            else:
                duration = row['end']-row['start']
                rows.append(row | {'start':cursor,'end':cursor+duration})
                ops[row['operation']] += row['count']; phases[row['phase']] += duration
                cursor += duration; i += 1
        rows.sort(key=lambda r:(r['start'],r['end'],r['resource']))
        check_intervals(rows,[])
        resources = deepcopy(self.serial_schedule['resources'])
        resources.update(adc_lanes=32,sample_hold_lanes=32,adc_payload_bits=384,
            adc_register_bits=1024,adc_result_banks=2,readout_bus_bits=128,readout_staging_bits=512,
            shift_add_lanes=8,accumulator_banks=8,accumulator_words_per_bank=12,
            control_status='Connected digital paths tested; full-core RTL and physical timing unvalidated')
        return {'resources':resources,'operations':dict(ops),'phase_cycles':dict(phases),
            'cycles':cursor,'storage_bytes':self.profile['storage_bytes'],
            'coefficient_initialization_words':len(self.exp_lut),
            'schedule_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
            'resource_busy_cycles':{key:sum(r['end']-r['start'] for r in rows if r['resource']==key)
                for key in sorted({r['resource'] for r in rows})},'trace':rows}

    def forward(self,board,player=None):
        features = self.features(board,player)
        hidden_acc,first = parallel_dot(features,self.cells[0],1,self.kernels[0])
        hidden = np.array([max(0,round_shift(v,self.hidden_shift)) for v in hidden_acc],dtype=np.int64)
        hidden_clipped = int(np.count_nonzero(hidden>255)); hidden = np.clip(hidden,0,255)
        self._write('hidden',hidden,'u1'); hidden = self._read('hidden',96,'u1').astype(np.int64)
        logits_acc,second = parallel_dot(hidden,self.cells[1],8,self.kernels[1])
        shift = self.fractions[0]+self.fractions[1]-self.hidden_shift-12
        logits = [round_shift(v,shift) for v in logits_acc]
        logit_clipped = sum(v<-(2**31) or v>=2**31 for v in logits)
        logits = [max(-(2**31),min(2**31-1,v)) for v in logits]
        self._write('logits',logits,'<i4'); logits = self._read('logits',3,'<i4').tolist()
        maximum = max(logits); indices = [min(4096,round_shift(maximum-v,4)) for v in logits]
        exponentials = [int(self._read('exp_lut',1,'<u4',index=i)[0]) for i in indices]
        denominator = sum(exponentials)
        probabilities = [round_divide(v<<16,denominator) for v in exponentials]
        self._write('probabilities',probabilities,'<u4')
        draw,black = self._read('probabilities',2,'<u4',index=1)
        value_code = 2*int(black)+int(draw); self._write('value',[value_code],'<u4')
        self.last_state = {'hidden_acc':hidden_acc.tolist(),'hidden_codes':hidden.tolist(),
            'logits_acc':logits_acc.tolist(),'logits_q12':logits,'lut_indices':indices,
            'probabilities_q16':probabilities,'value_q17':value_code,
            'hidden_saturations':hidden_clipped,'logit_saturations':logit_clipped,
            'black_to_play':int(player==1)}
        self.last_offset = [first,second]; self.evaluations += 1
        return value_code/2**17


class ParallelDatapathGoSimulation(OverlappedUCBGoSimulation):
    def __init__(self,*args,**kwargs):
        from core.architecture.component_parameters import validate_parameters
        self.component_parameters = validate_parameters(kwargs.pop("component_parameters",None))
        super().__init__(*args,**kwargs)
        self.datapath = datapath_spec()
        self.datapath["ucb_busy_cycles"] = self.component_parameters.get("u_ucb",{}).get("service_cycles",169)
        adc_cycles = self.component_parameters.get("adc_lanes",{}).get("service_cycles",13)
        coefficients = deepcopy(self.neural.coefficients)
        self.neural = ParallelNeuralMapping(*self.weights,self.board_size,turn_indicator=True,service_cycles=adc_cycles)
        self.neural.bind_memory(self.memory)
        if self.neural.coefficients!=coefficients: raise AssertionError('Changed evaluator coefficients')
        self.selection_spec = self.selection_spec | {'profile':self.datapath['profile'],'lanes':16,
            'sha256':self.datapath['sha256'],'timing_status':self.datapath['timing_status']}
        self.rollout_spec = self.datapath
        for key in list(self.block_active_cycles):
            if key.startswith('u_ucb_'): del self.block_active_cycles[key]
        self.block_active_cycles.update(dict.fromkeys(LANES,0))
        self.memory.config.update(execution_profile=self.datapath['profile'],ucb_lanes=16,
            selection_profile=self.datapath['profile'],selection_spec_sha256=self.datapath['sha256'],
            rollout_profile=self.datapath['profile'],rollout_spec_sha256=self.datapath['sha256'],
            timing_status=self.datapath['timing_status'],ucb_batch_service_cycles='171 + valid_children (1..16)',
            candidate_register_bits=2*16*128,adc_result_register_bits=2*32*16,readout_staging_bits=512,
            internal_readout_bus_bits=128,accumulator_lanes=8,
            trace_timing='Explicit resource schedules inside buffered regions; serial services elsewhere')
        self.memory.config.update(adc_service_cycles=adc_cycles,ucb_busy_cycles=self.datapath["ucb_busy_cycles"])
        if "service_cycles" in self.component_parameters.get("cam_macro",{}):
            service = self.component_parameters["cam_macro"]["service_cycles"]
            self.memory.config.update(cam_search_cycles=service,cam_row_write_cycles=service,cam_output_cycles=service)
        self.pipeline_cache = {}; self.parent_histogram = Counter(); self.selection_region_cycles = 0
        self.last_selection_region = None
        self.selection_trace = []

    def _children(self,node,children):
        candidates = []
        for child in children:
            candidate = self.memory._node_fields(child)
            candidates.append((child,candidate))
            if not candidate['visits']: break
        visited = tuple(bool(n['visits']) for _,n in candidates)
        if visited not in self.pipeline_cache:
            self.pipeline_cache[visited] = candidate_pipeline(visited,word_cycles=self.memory.config['sram_word_cycles'],busy_cycles=self.datapath['ucb_busy_cycles'])
        schedule = self.pipeline_cache[visited]
        memory = self.memory
        memory.count('node_sram_read_words',6*len(candidates))
        memory.count('candidate_checks',len(candidates))
        start = memory.cursor
        memory._record('parallel_selection','prefetch_and_score',0,24*len(candidates),
            6*len(candidates),schedule['cycles'])
        if memory.capture_trace:
            self.selection_trace.extend(row | {'start':start+row['start'],'end':start+row['end'],'phase':'selection'} for row in schedule['trace'])
        self.selection_region_cycles += schedule['cycles']
        self.parent_histogram[len(candidates),sum(visited)] += 1
        best = None; best_score = float('-inf'); banks = {}; actions = []
        for group in schedule['groups']:
            actions.extend([(group['ready'],0,group),(group['end'],1,group)])
        for _,operation,group in sorted(actions,key=lambda e:(e[0],e[1],e[2]['group'])):
            bank = group['bank']
            if operation==0:
                if bank in banks: raise AssertionError('Candidate bank overwritten while scoring')
                batch = candidates[group['first']:group['first']+group['count']]
                banks[bank] = (group['group'],batch)
                if sum(len(b[1]) for b in banks.values())>32:
                    raise AssertionError('Candidate register capacity exceeded')
                continue
            owner,batch = banks.pop(bank)
            if owner!=group['group']: raise AssertionError('Wrong candidate buffer tag')
            count = group['valid_lanes']
            if count:
                memory.count('ucb_operations',count); memory.count('ucb_batches')
                self.batch_counts[count] += 1
            for lane,(child,candidate) in enumerate(batch):
                if not candidate['visits']: best = child; break
                value = score(node['visits'],candidate['visits'],candidate['value'],self.exploration)
                self.block_active_cycles[LANES[lane]] += self.datapath["ucb_busy_cycles"]
                if value>best_score: best = child; best_score = value
        if banks: raise AssertionError('Undrained candidate bank')
        self.last_selection_region = {'start':start,'end':memory.cursor,'children':[c for c,_ in candidates],
            'winner':best,'schedule_key':[len(candidates),sum(visited)]}
        if best is None: raise RuntimeError('No winner for a nonempty child list')
        return best

    def _select(self):
        self.selection_trace = []
        memory = self.memory; memory.reset_path(); current = 0
        memory.control('selection_start',2)
        while True:
            node = memory.read_node(current); memory.push_path(current)
            memory.control('decode_node_and_branch',3)
            if not node['visits']: break
            remaining = memory.remaining(current)
            if remaining==NO_NODE: remaining = self._actions(current)
            memory.control('check_remaining_actions')
            if remaining or not node['children_count']: break
            current = self._children(node,memory.lookup_children(current,node))
        self.selected = current
        return memory.cursor-self.cycles

    def _phase(self,name,action):
        self.memory.begin(name,self.completed+1,self.cycles)
        before = self.memory.operations.copy()
        lane_before = [self.block_active_cycles[lane] for lane in LANES]
        duration = action()
        remainder = self.cycles+duration-self.memory.cursor
        if remainder<0: raise AssertionError('Scheduled interval shorter than serial services')
        self.memory._record('controller','aggregated_control_and_compute',0,0,0,remainder)
        operations = self.memory.operations-before; operations['ucb_operations'] = 0
        active = phase_activity(name,duration,operations); active.pop('u_ucb')
        self.block_active_cycles.update(active)
        if any(not 0<=self.block_active_cycles[lane]-old<=duration for lane,old in zip(LANES,lane_before)):
            raise AssertionError('Lane occupancy exceeds elapsed time')
        self.cycles += duration; self.phase_cycles[name] += duration
        return {'phase':name,'iteration':self.completed+1,'cycles':duration,'cycle_end':self.cycles,
            'selected_node':self.selected,'path_depth':self.memory.path_depth,
            'nodes':self.memory.nodes_used,'edges':self.memory.edges_used,
            'cam_rows':sum(len(v[1]) for v in self.memory.cam.values())}

    def activity_record(self):
        if set(self.block_active_cycles) != set(BLOCKS)-{'u_ucb'} | set(LANES):
            raise AssertionError('Wrong installed digital inventory')
        if any(type(v) is not int or not 0<=v<=self.cycles for v in self.block_active_cycles.values()):
            raise AssertionError('Invalid physical occupancy')
        return {'profile':self.datapath['profile'],'elapsed_cycles':self.cycles,
            'blocks':{k:{'active_cycles':v,'idle_cycles':self.cycles-v} for k,v in self.block_active_cycles.items()},
            'boundary':self.datapath['boundary'],'timing_status':self.datapath['timing_status']}


# The sized initializer enters through the existing cooperative Go/policy MRO.
# All arithmetic and pipeline execution above stay shared with the saved 9x9.
from core.architecture.sized_simulation import SizedSingleChildGoSimulation
from core.architecture.board_sizing import board_hardware


class SizedParallelDatapathGoSimulation(ParallelDatapathGoSimulation, SizedSingleChildGoSimulation):
    def __init__(self, board_size=9, iterations=5000, seed=0, **kwargs):
        board_hardware(board_size)
        generated = kwargs.get('weights') is None
        if generated:
            if type(seed) is not int or not 0 <= seed < 2**32:
                raise ValueError('Seed must be an unsigned 32-bit integer')
            rng = np.random.RandomState(seed)
            inputs = 2*board_size**2+1
            kwargs['weights'] = [rng.randn(inputs,96)*np.sqrt(2/inputs),
                rng.randn(96,3)*np.sqrt(2/96)]
        if kwargs.get('turn_indicator', True) is not True:
            raise ValueError('Current sized architecture requires the turn input')
        kwargs['turn_indicator'] = True
        super().__init__(board_size,iterations,seed=seed,**kwargs)
        if generated:
            self.evaluator['mode'] = 'seeded_random_hardware_diagnostic'
        self.memory.config['timing_status'] = 'Board-sized parallel architectural services; physical timing unvalidated'
