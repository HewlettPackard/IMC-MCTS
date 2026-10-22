# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Complete-search SRAM/CAM traffic and independently evaluated neural responses.
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path

import numpy as np

from core.architecture.iteration_model import CompleteSimulation
from core.simulator.tree_memory import TreeMemory
from p03_experiments.p10_neural_sequence.fixtures import build_fixture
from p03_experiments.p11_cached_selection.fixtures import write_memory


class CompleteTrace(TreeMemory):
    def __init__(self, config, nodes):
        super().__init__(config,nodes)
        self.active=False; self.allocating=False; self.expected=[]; self.pending=[]; self.parent_id=0

    def flush(self):
        for row,memory in self.pending:
            row['data']=int.from_bytes(memory[row['address']:row['address']+4],'little')
        self.pending=[]

    def allocate_node(self, node_id, node):
        self.flush(); self.allocating=True
        try: super().allocate_node(node_id,node)
        finally: self.allocating=False; self.flush()

    def lookup_children(self, parent_id, node=None):
        self.parent_id=parent_id
        return super().lookup_children(parent_id,node)

    def _record(self, resource, operation, address, size, words, cycles):
        super()._record(resource,operation,address,size,words,cycles)
        if not self.active: return
        if not self.allocating: self.flush()
        if resource in ('node_sram','child_sram'):
            memory=self.node_sram if resource=='node_sram' else self.child_sram
            for offset in range(0,size,4):
                row={'target':int(resource=='child_sram'),'op':int(operation=='write'),'address':address+offset,
                    'data':int.from_bytes(memory[address+offset:address+offset+4],'little'),'child':0}
                self.expected.append(row)
                if operation=='write': self.pending.append((row,memory))
        elif resource=='cam':
            if operation.startswith('search'):
                self.expected.append({'target':2,'op':0,'address':address,'data':0,'child':0})
            elif operation=='invalidate':
                self.expected.append({'target':2,'op':2,'address':address,'data':0,'child':0})
            elif operation=='fill':
                child=self.expected[-1]['data']
                self.expected.append({'target':2,'op':1,'address':address,'data':self.parent_id,'child':child})
            elif operation=='output':
                _,rows,children=self.cam[self.parent_id]
                for row,child in zip(rows,children):
                    self.expected.append({'target':2,'op':3,'address':row,'data':self.parent_id,'child':child})


def make_complete(out, board_size, iterations, ragged=False, hidden=None, cam=None):
    out.mkdir(parents=True,exist_ok=False)
    board=np.zeros((board_size,board_size),dtype=np.int8)
    if ragged: board.flat[:]=[0 if i<3 else (1 if i%2 else -1) for i in range(board.size)]
    weights=None
    if hidden is not None:
        weights=(((np.arange(2*board_size**2*hidden).reshape(-1,hidden)%13)-6)/32,
            ((np.arange(hidden*3).reshape(hidden,3)%7)-3)/32)
    model=CompleteSimulation(board_size,iterations,initial_board=board,weights=weights,cam_entries=cam,memory_factory=CompleteTrace)
    memory=model.memory
    write_memory(out/'initial_node.hex',memory.node_sram); write_memory(out/'initial_child.hex',memory.child_sram)
    memory.active=True
    phases=[]; adc=[]; neural=[]
    for row in model.steps():
        memory.flush(); phases.append(row)
        if row['phase']=='neural':
            index=row['iteration']
            fixture=build_fixture(out/f'neural_{index:03d}',model.board(model.selected),*model.weights,
                memory.node_address(model.selected)+24,memory.config['neural_base'])
            if fixture['expected']['value_q17']!=model.value_q17: raise AssertionError('Neural dense value differs')
            neural.append(fixture)
            adc+=(out/f'neural_{index:03d}/adc.hex').read_text().splitlines()
    write_memory(out/'expected_node.hex',memory.node_sram); write_memory(out/'expected_child.hex',memory.child_sram)
    (out/'adc.hex').write_text('\n'.join(adc)+'\n')
    (out/'transactions.hex').write_text(''.join(f"{(r['target']<<316)|(r['op']<<312)|(r['address']<<280)|(r['data']<<248)|(r['child']<<216):080x}\n" for r in memory.expected))
    fields=[]
    for row in model.history:
        fields.append([row['iteration'],row['selected_node'],row['nodes'],row['edges'],row['value_q17'],row['random_state'],
            row['cycle_end']&0xffffffff,row['cycle_end']>>32])
    (out/'iterations.hex').write_text(''.join(f'{sum(v<<(32*i) for i,v in enumerate(row)):064x}\n' for row in fields))
    record={'board_size':board_size,'iterations':iterations,'hidden':model.neural.profile['hidden_size'],
        'cam_entries':memory.config['cam_entries'],'memory':memory.config,'transactions':len(memory.expected),
        'adc_groups':len(adc),'hidden_shift':model.neural.hidden_shift,
        'logit_shift':sum(model.neural.fractions)-model.neural.hidden_shift-12,
        'core_cycles':model.cycles,'phases':phases,'history':model.history,
        'operations':dict(memory.operations),'final_node_sha256':hashlib.sha256(memory.node_sram).hexdigest(),
        'final_child_sha256':hashlib.sha256(memory.child_sram).hexdigest(),
        'boundary':'Preloaded packed root and LUT, programmed ideal arrays, whole digital core; no physical timing claim'}
    (out/'fixture.json').write_text(json.dumps(record,indent=2)+'\n')
    return record
