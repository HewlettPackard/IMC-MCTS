# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Task-shape projections reuse the current peripheral schedule and cost sources.
# SPDX-License-Identifier: MIT
from collections import Counter, OrderedDict
from copy import deepcopy
import hashlib
import json
import math
from types import SimpleNamespace

import numpy as np

from core.algorithm.mcts_engine import MCTSEngine
from core.architecture.neural_mapping import neural_profile
from core.architecture.offset_encoding import OffsetNeuralMapping
from core.architecture.parallel_datapath import column_pipeline, candidate_pipeline, parallel_dot, LANES
from core.architecture.parallel_selection import LANES as OLD_LANES
from core.architecture.board_sizing import board_hardware, memory_characterization, memory_profile_name
from core.architecture.sram_costs import load_sram_profile
from core.architecture.studio_current import SOURCES, activity
from core.architecture.parallel_datapath_costs import parallel_datapath_costs
from p03_experiments.p79_scalability.costs import estimate

PROFILE = 'application_shape_projection_ucb16_adc32_v1'
APPLICATIONS = [
    dict(key='connect_four', name='Connect Four', board=8, inputs=129, hidden=96, outputs=3, input_bits=1, tier=9, domain='Strategy'),
    dict(key='othello', name='Othello', board=8, inputs=129, hidden=96, outputs=3, input_bits=1, tier=9, domain='Strategy'),
    dict(key='hex', name='Hex', board=11, inputs=485, hidden=96, outputs=3, input_bits=8, tier=13, domain='Strategy'),
    dict(key='go', name='Go', board=9, inputs=163, hidden=96, outputs=3, input_bits=1, tier=9, domain='Strategy'),
    dict(key='frozen_lake', name='FrozenLake', board=8, inputs=129, hidden=96, outputs=3, input_bits=1, tier=9, domain='Navigation'),
    dict(key='minigrid', name='MiniGrid', board=8, inputs=129, hidden=96, outputs=3, input_bits=1, tier=9, domain='Navigation'),
    dict(key='protein_folding', name='HP Protein Folding', board=13, inputs=344, hidden=128, outputs=3, input_bits=8, tier=13, domain='Science'),
    dict(key='minesweeper', name='Minesweeper', board=9, inputs=244, hidden=96, outputs=3, input_bits=8, tier=9, domain='Puzzle'),
]


class NeuralProjection:
    def __init__(self, config, parallel=True):
        self.config = dict(config)
        h, o = config['hidden'], config['outputs']
        self.cells = [np.full((config['inputs'], h), 128, dtype=np.uint8), np.full((h, o), 128, dtype=np.uint8)]
        self.profile = neural_profile(9, h, sram_word_cycles=2)
        self.profile.update(board_size=config['board'], input_size=config['inputs'], hidden_size=h,
            outputs=o, model=PROFILE, cell_bits=8, weight_bits=8, adc_bits=12,
            layer_input_bits=[config['input_bits'], 8], input_packing='precomputed_feature_codes',
            arrays=[dict(layer=i+1, rows=c.shape[0], columns=c.shape[1], count=1, cells=c.size, cell='1T1M', cell_bits=8)
                for i,c in enumerate(self.cells)],
            shape_status='Declared application dimensions; exact archived checkpoint shapes unverified',
            input_status='Binary base features; enhanced features bounded by unsigned eight-bit codes',
            numerical_status='Integer dot-product checked; application value interpretation and trained quality unverified')
        self.profile['service_cycles']['adc_group'] = 13
        sizes = [('inputs', 4*math.ceil(config['inputs']*config['input_bits']/32)), ('hidden', 4*math.ceil(h/4)),
            ('logits', 4*o), ('probabilities', 4*o), ('value', 4), ('exp_lut', 4097*4)]
        offset = 0
        self.profile['storage'] = {}
        for name, size in sizes:
            self.profile['storage'][name] = dict(offset=offset, bytes=size)
            offset += size
        self.profile['storage_bytes'] = offset
        self.exp_lut = np.rint(np.exp(-np.arange(4097)/256)*2**30).astype('<u4')
        self.schedule = self._schedule(parallel)
        self.profile['readout_activity'] = OffsetNeuralMapping._readout_activity(self)

    def _schedule(self, parallel):
        cursor = 0; trace = []; operations = Counter(); phases = Counter()
        phase = 'layer1'; context = {}

        def emit(resource, operation, count=1, cycles=1):
            nonlocal cursor
            trace.append(dict(phase=phase, resource=resource, operation=operation, count=count,
                start=cursor, end=cursor+cycles, **context))
            cursor += cycles; operations[operation] += count; phases[phase] += cycles

        def transfer(operation, words):
            for _ in range(words):
                emit('neural_controller', 'sram_request_handshakes')
                emit('node_sram', 'node_sram_'+operation+'_words', cycles=2)

        emit('neural_controller', 'neural_start')
        transfer('read', 1); emit('neural_controller', 'turn_input_latches')
        lanes, bus, accum, banks = (32,128,8,2) if parallel else (8,32,1,1)
        for layer,cells in enumerate(self.cells):
            phase = 'layer'+str(layer+1)
            inputs, outputs = cells.shape; bits = self.profile['layer_input_bits'][layer]
            context = dict(array_id=layer, outputs=[0,outputs])
            emit('accumulator_registers','accumulator_clears',outputs,outputs)
            emit('offset_alu','offset_sum_clears')
            kernel = column_pipeline(outputs, lanes=lanes, bus_bits=bus, accumulators=accum, banks=banks)
            for first in range(0,inputs,16):
                last = min(first+16,inputs)
                context = dict(array_id=layer, outputs=[0,outputs], active_rows=[first,last])
                transfer('read', math.ceil((last-first)*bits/32))
                emit('offset_alu','offset_input_adds',last-first,last-first)
                for bit in range(bits):
                    context['input_bit'] = bit
                    emit('binary_drivers','dac_bit_drives',last-first)
                    emit('array','array_pulses',cycles=3)
                    for event in kernel['trace']:
                        trace.append(dict(phase=phase, **context) | event |
                            dict(start=cursor+event['start'], end=cursor+event['end']))
                        operations[event['operation']] += event['count']
                        operations['adc_conversions'] += event.get('conversions',0)
                    cursor += kernel['cycles']; phases[phase] += kernel['cycles']
            context = dict(array_id=layer, outputs=[0,outputs])
            emit('offset_alu','offset_shifts'); emit('offset_alu','offset_subtracts',outputs,outputs)
            emit('activation_lane' if layer==0 else 'scale_lane',
                'hidden_activations' if layer==0 else 'logit_rescales', outputs,outputs)
            transfer('write',math.ceil(outputs/4) if layer==0 else outputs)
        phase='output'; context={}
        transfer('read',self.config['outputs']); emit('output_alu','max_comparisons',2,2)
        for _ in range(3):
            emit('output_alu','lut_addresses'); transfer('read',1)
        emit('output_alu','exponential_sums',3,3)
        for _ in range(3):
            emit('divider','divide_setups'); emit('divider','divide_bits',48,48)
            emit('output_alu','probability_rounds'); emit('neural_controller','divider_completion_handshakes')
            transfer('write',1)
        transfer('read',2); emit('output_alu','value_formations'); transfer('write',1)
        emit('neural_controller','neural_result_capture')
        trace.sort(key=lambda r:(r['start'],r['end'],r['resource']))
        resources = dict(array_count=2, array_dimensions=self.profile['arrays'], adc_lanes=lanes,
            adc_bits=12, adc_slot_bits=16, adc_register_bits=banks*lanes*16,
            adc_result_banks=banks, readout_bus_bits=bus, shift_add_lanes=accum,
            accumulator_words=self.config['hidden'], accumulator_register_bits=32*self.config['hidden'],
            accumulator_words_per_bank=math.ceil(self.config['hidden']/accum),
            installed_row_drivers=sum(c.shape[0] for c in self.cells),
            installed_column_routes=sum(c.shape[1] for c in self.cells))
        return dict(resources=resources, trace=trace, operations=dict(operations), phase_cycles=dict(phases),
            cycles=cursor, storage_bytes=self.profile['storage_bytes'],
            schedule_sha256=hashlib.sha256(json.dumps(trace,sort_keys=True).encode()).hexdigest())

    def estimate(self):
        return dict(profile=self.profile, resources=self.schedule['resources'], operations=self.schedule['operations'],
            cycles=self.schedule['cycles'], storage_bytes=self.profile['storage_bytes'])

    def checked_dot(self, inputs, codes, bits):
        codes = np.asarray(codes, dtype=np.int64)
        if np.any(codes < -127) or np.any(codes > 127): raise ValueError('Signed weight outside eight-bit range')
        kernel = column_pipeline(codes.shape[1])
        result, details = parallel_dot(inputs,(codes+128).astype(np.uint8),bits,kernel)
        expected = np.asarray(inputs,dtype=np.int64) @ codes
        if not np.array_equal(result,expected): raise AssertionError('Offset arithmetic differs from signed dot product')
        return result,details


class ApplicationCensus(MCTSEngine):
    def __init__(self, game, iterations=5000):
        super().__init__(game,iterations=iterations,eval_fn=lambda board,player:0.5)
        self.census=Counter(); self.parents=Counter(); self.cache=OrderedDict(); self.cache_rows=0
        self.cam_entries=board_hardware(next(a['tier'] for a in APPLICATIONS if a['key']==game.key))['cam_entries']
        self.max_depth=0; self.nodes_used=0; self.state_bytes=game.initial_state().size

    def _select(self,nodes,root_idx):
        index=root_idx
        while True:
            node=nodes[index]; self.census['selected_headers']+=1
            if node['is_terminal'] is None: node['is_terminal']=self.game.is_terminal(node['board'])
            if node['is_terminal']: return index
            if node['untried_moves'] is None:
                node['untried_moves']=list(self.game.get_legal_moves(node['board'],node['player']))
                self.census['legal_mask_loads']+=1
            if node['untried_moves'] or not node['children']: return index
            count=len(node['children']); self.parents[count]+=1; self.census['cam_searches']+=1
            self.census['cam_output_ids']+=count
            if index in self.cache and self.cache[index]==count:
                self.census['cam_hits']+=1
            else:
                self.census['child_sram_read_words']+=count
                if index in self.cache: self.cache_rows-=self.cache.pop(index)
                while self.cache_rows+count>self.cam_entries:
                    _,old=self.cache.popitem(last=False); self.cache_rows-=old
                    self.census['cam_evicted_rows']+=old
                self.cache[index]=count; self.cache_rows+=count; self.census['cam_filled_rows']+=count
            index=max(node['children'],key=lambda child:self._ucb1(node,nodes[child]))

    def _expand(self,nodes,index):
        before=len(nodes); selected=super()._expand(nodes,index)
        self.census['expansion_attempts']+=1
        if len(nodes)>before:
            self.census['created_nodes']+=1
            self.state_bytes=max(self.state_bytes,nodes[selected]['board'].size)
        self.nodes_used=len(nodes)
        return selected

    def _rollout(self,board,player):
        if not self.game.is_terminal(board): self.census['neural_evaluations']+=1
        return super()._rollout(board,player)

    def _backpropagate(self,nodes,index,result):
        depth=0; current=index
        while current is not None:
            depth+=1; current=nodes[current]['parent']
        self.census['backprop_nodes']+=depth; self.max_depth=max(self.max_depth,depth)
        super()._backpropagate(nodes,index,result)


def project_costs(config,census):
    current=NeuralProjection(config); serial=NeuralProjection(config,parallel=False)
    sources=json.loads((SOURCES/'sources.json').read_text())
    published=json.loads((SOURCES/'published_adc.json').read_text())
    tier=board_hardware(config['tier'])
    sources['sram']=load_sram_profile(memory_profile_name(config['tier'],'cacti_22nm_lstp'))
    cams=sources['tools']['cam'] | memory_characterization()['cam']
    size=tier['cam_entries']; sources['selected_cam']=cams['cam_'+str(2048 if size==1536 else size)+'_lstp']
    state_words=math.ceil(census.state_bytes/4)
    scratch=current.profile['storage_bytes']
    node_base=4*(census.iterations+1)+4*state_words+32+16*size+scratch
    node_base=4*math.ceil(node_base/4)
    node_stride=24+4*state_words
    memory=dict(board_size=config['board'],node_sram_bytes=tier['node_sram_kib']*1024,
        child_sram_bytes=tier['child_sram_kib']*1024,cam_entries=size,node_base=node_base,
        node_stride=node_stride,path_entries=census.iterations+1,neural_bytes=scratch,
        execution_profile='ucb16_adc32_buffered_v2',sram_bank_bytes=tier['sram_bank_kib']*1024)
    memory['node_capacity']=(memory['node_sram_bytes']-node_base)//node_stride
    memory['edge_capacity']=memory['child_sram_bytes']//4
    if census.nodes_used>memory['node_capacity'] or census.nodes_used-1>memory['edge_capacity'] or census.max_depth>memory['path_entries']:
        raise MemoryError('Application workload exceeds installed capacity')
    c=census.census; evals=c['neural_evaluations']; iters=census.iterations
    total_candidates=sum(n*times for n,times in census.parents.items())
    select_words=7*c['selected_headers']+6*total_candidates+state_words*c['legal_mask_loads']
    expand_words=6*iters+(12+2*state_words)*c['created_nodes']
    back_words=10*c['backprop_nodes']
    input_words=current.profile['storage']['inputs']['bytes']//4
    ops=Counter(c)
    ops['node_sram_read_words']=select_words+6*iters+state_words*c['created_nodes']+7*c['backprop_nodes']
    ops['node_sram_write_words']=(6+state_words)*c['created_nodes']+3*c['backprop_nodes']
    ops['child_sram_write_words']=c['created_nodes']; ops['ucb_operations']=total_candidates
    ops['node_sram_write_words']+=evals*input_words
    for operation,count in current.schedule['operations'].items():
        ops[operation if operation.startswith('node_sram_') else 'neural_'+operation]+=count*evals
    serial_kernel={n:candidate_pipeline([True]*n,lanes=4) for n in census.parents}
    kernels={n:candidate_pipeline([True]*n) for n in census.parents}
    cam_cycles=3*(c['cam_searches']+c['cam_output_ids']+c['cam_filled_rows']+c['cam_evicted_rows'])
    # The candidate kernels already include their six-word header loads.
    select_common=3*(select_words-6*total_candidates+c['child_sram_read_words'])+cam_cycles+6*c['selected_headers']
    select=select_common+sum(kernels[n]['cycles']*times for n,times in census.parents.items())
    old_select=select_common+sum(serial_kernel[n]['cycles']*times for n,times in census.parents.items())
    expansion=3*(expand_words+c['created_nodes'])+4*iters+(config['board']**2+36)*c['created_nodes']
    backprop=3*back_words+4*c['backprop_nodes']; commit=4*iters
    neural=evals*(current.schedule['cycles']+3*input_words)
    old_neural=evals*(serial.schedule['cycles']+3*input_words)
    cycles=select+expansion+neural+backprop+commit
    old_cycles=old_select+expansion+old_neural+backprop+commit
    active=Counter(dict(u_sel=select,u_upd=expansion+backprop,u_nn=neural,
        u_node_router=2*(ops['node_sram_read_words']+ops['node_sram_write_words']),
        u_child_router=2*(ops['child_sram_read_words']+ops['child_sram_write_words']),top_level_glue=cycles))
    old_active=active.copy(); old_active.update(u_sel=old_select-select,u_nn=old_neural-neural,top_level_glue=old_cycles-cycles)
    for count,times in census.parents.items():
        for i,lane in enumerate(LANES): active[lane]+=169*(count//16+(i<count%16))*times
        for i,lane in enumerate(OLD_LANES): old_active[lane]+=169*(count//4+(i<count%4))*times
    for lane in LANES: active.setdefault(lane,0)
    for lane in OLD_LANES: old_active.setdefault(lane,0)
    old_model=SimpleNamespace(board_size=config['board'],cycles=old_cycles,block_active_cycles=old_active,
        memory=SimpleNamespace(config=memory,operations=ops),neural=serial)
    old_costs=estimate(old_model,sources,published)
    common=dict(iterations=iters,neural_evaluations=evals,
        installed_sram_bytes=memory['node_sram_bytes']+memory['child_sram_bytes'],memory=dict(config=memory,operations=dict(ops)))
    candidate=common | dict(cycles=cycles,latency_ms=cycles/500000,neural=current.estimate(),activity=activity(active,cycles))
    reference=common | dict(cycles=old_cycles,latency_ms=old_cycles/500000,neural=serial.estimate(),activity=activity(old_active,old_cycles))
    if any(v<0 or v>cycles for v in active.values()): raise AssertionError('Physical occupancy exceeds elapsed interval')
    report=parallel_datapath_costs(candidate,reference,old_costs,sources,published)
    report.update(projection_profile=PROFILE,application=config['name'],configuration=config,
        workload=dict(iterations=iters,value_policy='constant 0.5 diagnostic; terminal values from host rules',
            rule_source='generalizability.games',tree_selection='legacy functional floating-point UCB1',
            neural_evaluations=evals,nodes=census.nodes_used,max_depth=census.max_depth),
        memory_admission=memory,phase_cycles=dict(selection=select,expansion=expansion,neural=neural,backpropagation=backprop,commit=commit),
        operation_counts=dict(ops),parent_histogram=dict(census.parents),neural_schedule=current.estimate(),
        status='Task-specific diagnostic census and executable peripheral schedule; complete application hardware and trained quality unvalidated',
        excluded=['Host task rules, terminal checks, feature encoding and value calibration','Host I/O, pads and ESD',
            'Weight programming, preload and ADC startup calibration'],
        assumptions=['Declared matrix dimensions awaiting exact checkpoint recovery',
            'Eight-bit stored task-state cells; task metadata handled by host',
            'Next existing memory tier for 8x8 and 11x11; single-port service retained',
            'Three-output processing allowance, not a verified per-task value implementation',
            'Binary base features and eight-bit enhanced features; actual distributions unverified',
            'Mean analog activity and conductance, source digital power proxies, ideal 12-bit codes'])
    return report
