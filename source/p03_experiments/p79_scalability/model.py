# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Parameterized diagnostic harness; shared execution methods remain unchanged.
# SPDX-License-Identifier: MIT
from collections import Counter
from copy import deepcopy
import hashlib
from types import SimpleNamespace

import numpy as np

from core.architecture.block_activity import BLOCKS
from core.architecture.go_simulation import LegacyGo, initial_state
from core.architecture.neural_mapping import neural_profile, quantize_weights, map_tiles
from core.architecture.offset_encoding import OffsetNeuralMapping, offset_spec
from core.architecture.parallel_selection import LANES, selection_spec
from core.architecture.ucb_overlap import OverlappedUCBGoSimulation, overlap_spec
from core.simulator.incremental_memory import IncrementalMemory, POLICY, TIMING
from core.simulator.tree_memory import memory_config
from py_sst_cpp.components.board_config import BoardSize, get_board_config

BOARDS = {2:(50,200,1000),3:(75,500,5000),5:(100,1000,10000),
          9:(500,5000,50000),13:(1000,7500,75000),19:(2000,10000,100000)}


class DiagnosticNeural(OffsetNeuralMapping):
    def __init__(self, weights, board):
        first, second = (np.asarray(w,dtype=np.float64) for w in weights)
        if first.shape != (2*board*board+1,96) or second.shape != (96,3):
            raise ValueError('Scaling experiment requires a turn-aware H96 network')
        # The generic profile is used only to establish the unchanged scratch
        # and service fields. Enable the real turn input before quantization.
        self.profile = neural_profile(board,96,8,16,2)
        self.profile.update(input_size=2*board*board+1,turn_indicator=True)
        q1,f1 = quantize_weights(first); q2,f2 = quantize_weights(second)
        bound = np.maximum(q1[:-1].reshape(-1,2,96).max(axis=1),0).sum(axis=0)
        bound += np.maximum(q1[-1],0)
        shift = 0
        while int(bound.max()) > (255 << shift): shift += 1
        self.weight_codes = [q1,q2]; self.fractions = [f1,f2]; self.hidden_shift = shift
        self.tiles = [map_tiles(q,self.profile) for q in self.weight_codes]
        self.exp_lut = np.rint(np.exp(-np.arange(4097)/256)*2**30).astype('<u4')
        self.storage = bytearray(self.profile['storage_bytes'])
        self._write('exp_lut',self.exp_lut,'<u4')
        self.coefficients = {'weight_fraction_bits':self.fractions,'hidden_right_shift':shift,
            'hidden_scale':2.0**(shift-f1),'logit_scale':2.0**(shift-f1-f2),
            'hidden_integer_upper_bound':bound.tolist(),
            'quantized_weight_sha256':[hashlib.sha256(q.astype('<i2').tobytes()).hexdigest() for q in self.weight_codes],
            'exp_lut_sha256':hashlib.sha256(self.exp_lut.tobytes()).hexdigest()}
        self.evaluations = 0; self.last_state = None
        self.schedule = self._schedule()
        self.spec = offset_spec(); self.reference_profile = deepcopy(self.profile)
        self.cells = [(q+128).astype(np.uint8) for q in self.weight_codes]
        arrays = [{'layer':i+1,'rows':c.shape[0],'columns':c.shape[1],
                   'count':1,'cells':int(c.size),'cell':'1T1M','cell_bits':8} for i,c in enumerate(self.cells)]
        self.tiles = [[{'row_start':0,'row_end':len(c),'output_start':0,
                       'output_end':c.shape[1],'cells':c}] for c in self.cells]
        self.profile.pop('array_rows'); self.profile.pop('array_columns')
        self.profile.update(model='diagnostic_offset_scaling_v1',rollout_profile=self.spec['profile'],
            rollout_spec_sha256=self.spec['sha256'],cell_bits=8,weight_slices=1,sign_branches=1,
            weight_encoding='q_plus_128_with_digital_input_sum_correction',weight_offset=128,
            arrays=arrays,adc_bits=12,adc_slot_bits=16,
            timing_status='Parameterized architectural services; physical timing unvalidated',
            ppa_status='Separate engineering estimator; no new synthesis',
            readout={'profile':'sustained_drive_v1','overlap':False,
                     'array_drive':'through_all_column_groups','storage':'eight shared ADC input S/H lanes'})
        self.profile['service_cycles']['adc_group'] = self.spec['adc_service_cycles']
        self.last_offset = None
        self.schedule = self._offset_schedule()
        self.profile['readout_activity'] = self._readout_activity()


class DiagnosticSearch(OverlappedUCBGoSimulation):
    def __init__(self, board, iterations, seed=0, weights=None):
        if type(board) is not int or board not in BOARDS: raise ValueError('Unsupported board')
        if type(iterations) is not int or not 1 <= iterations < 2**32: raise ValueError('Invalid budget')
        if type(seed) is not int or not 0 <= seed < 2**32: raise ValueError('Invalid seed')
        self.board_size = board; self.iterations = iterations; self.seed = seed
        self.exploration = 1.414; self.random_state = seed or 0x6d2b79f5
        self.completed = 0; self.cycles = 0; self.phase_cycles = Counter(); self.history = []
        self.block_active_cycles = Counter(dict.fromkeys(BLOCKS,0))
        self.selected = 0; self.value_q17 = 0; self.status = 'ready'
        self.initial_board = np.zeros((board,board),dtype=np.int8)
        generated = weights is None
        if generated:
            rng = np.random.RandomState(seed)
            inputs = 2*board*board+1
            weights = [rng.randn(inputs,96)*np.sqrt(2/inputs),rng.randn(96,3)*np.sqrt(2/96)]
        self.weights = [np.asarray(w,dtype=np.float64) for w in weights]
        self.neural = DiagnosticNeural(self.weights,board)
        shape = SimpleNamespace(**vars(get_board_config(BoardSize(board))))
        shape.node_sram_kb = 1536; shape.children_sram_kb = 512; shape.cam_entries = 1024
        config = memory_config(shape,neural_scratch_bytes=self.neural.profile['storage_bytes'])
        config.update(sram_word_cycles=2,cam_search_cycles=3,cam_row_write_cycles=3,cam_output_cycles=3,
            ucb_cycles=225,arithmetic='ucb_q32_ln256_v1',cam_row_bits=65,cam_payload_bits=64,
            trace_timing='ordered service costs with controller gaps aggregated at phase end')
        for name in ('expand_cycles','update_cycles','rollout_cycles'): config.pop(name)
        self.memory = IncrementalMemory(config,{})
        self.neural.bind_memory(self.memory)
        self.memory.allocate_node(0,{'visits':0,'value':0.0,'parent':-1,'children':[],
            'board':self.initial_board,'player':1})
        lut = self.neural.profile['storage']['exp_lut']
        self.memory.transfer('node_sram','write',config['neural_base']+lut['offset'],lut['bytes'])
        self.preload_operations = dict(self.memory.operations)
        self.memory.cursor = 0; self.memory.operations.clear(); self.memory.phase_operations.clear()
        self.memory.phase_cycles.clear(); self.memory.transactions.clear()
        self.memory.schedule_hash = hashlib.sha256()
        self.game = LegacyGo(board)
        self.states = {0:initial_state(self.game,self.initial_board)}
        self.moves = {}; self.terminal_evaluations = 0; self.termination = None
        self.workload = 'legacy_go_captures_ko_pass_chinese_area_v1'
        self.memory.config.update(policy=POLICY,path_depth_bound=self.game._max_moves+1,
            tree_update_timing_profile=TIMING,node_value_perspective='player_to_move',
            host_rules='Legacy captures, suicide, simple ko, passes and Chinese area scoring with 6.5 komi',
            host_state='Ko/pass/capture/move metadata and legal successors excluded from chip storage/timing')
        self.serial_memory_config = deepcopy(self.memory.config)
        self.reference_selection_spec = selection_spec(); self.selection_spec = overlap_spec()
        self.reference_neural_profile = deepcopy(self.neural.reference_profile)
        self.rollout_spec = self.neural.spec
        self.memory.config['reference_serial_ucb_cycles'] = self.memory.config.pop('ucb_cycles')
        self.memory.config.update(ucb_lanes=4,selection_profile=self.selection_spec['profile'],
            selection_spec_sha256=self.selection_spec['sha256'],rollout_profile=self.rollout_spec['profile'],
            rollout_spec_sha256=self.rollout_spec['sha256'],
            execution_profile='diagnostic_go_offset_ucb_overlap_scaling_v1',
            adc_service_cycles=13,timing_status='Architectural scaling scenario; not physical closure')
        self.block_active_cycles.pop('u_ucb'); self.block_active_cycles.update(dict.fromkeys(LANES,0))
        self.batch_counts = Counter(); self.capture_selection_batches = False; self.selection_batches = []
        self.evaluator = {'mode':'seeded_random_hardware_diagnostic' if generated else 'trained_9x9_validation',
            'weight_sha256':[hashlib.sha256(w.tobytes()).hexdigest() for w in self.weights],
            'coefficients':self.neural.coefficients,'input_encoding':'interleaved_black_white_then_black_to_play',
            'output_order':['white','draw','black'],'value_perspective':'black','task_accuracy':'unvalidated'}
