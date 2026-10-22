# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Packed action bitmaps and growing child lists within the existing SRAM banks.
# SPDX-License-Identifier: MIT
import struct
from collections import deque

import numpy as np

from core.simulator.tree_memory import NODE, NO_NODE, TreeMemory

POLICY='evaluate_root_then_single_untried_child_v1'
TIMING='single_child_serial_services_v1'


def incremental_config(config):
    config=dict(config)
    actions=config['board_size']**2+1
    mask_bytes=((actions+31)//32)*4
    extension=8+mask_bytes
    old_nodes=(config['node_sram_bytes']-config['node_base'])//config['node_stride']
    config['node_stride']+=extension
    capacity=(config['node_sram_bytes']-config['node_base'])//config['node_stride']
    edges=config['child_sram_bytes']//8
    if config['node_capacity']==old_nodes: config['node_capacity']=capacity
    elif config['node_capacity']>capacity: raise ValueError('Node quota exceeds single-child physical capacity')
    if config['edge_capacity']==config['child_sram_bytes']//4: config['edge_capacity']=edges
    elif config['edge_capacity']>edges: raise ValueError('Edge quota exceeds single-child physical capacity')
    config.update(model='incremental_parent_link_cache_v1',policy=POLICY,
        node_extension_bytes=extension,action_mask_bytes=mask_bytes,action_slots=actions,
        child_record_bytes=8,child_format='<II child_id,next_edge; NO_NODE terminates list',
        expansion_state='After board: uint32 remaining (NO_NODE=uninitialized), uint32 tail edge, action bitmap',
        tree_update_timing_profile=TIMING,timing_status='architectural_service_estimate_not_RTL_validated',
        timing_source='SINGLE_CHILD_SPEC.md; serialized SRAM and explicit control steps',
            capacity_policy='stop_at_completed_boundary_when_nodes_edges_or_growable_path_reach_quota')
    return config


class IncrementalMemory(TreeMemory):
    def __init__(self, config, nodes, capture_trace=False):
        super().__init__(incremental_config(config),nodes,capture_trace)

    def transfer(self, resource, operation, address, size):
        super().transfer(resource,operation,address,size)
        self._record('controller','sram_request',address,size,size//4,size//4)

    def control(self, operation, cycles=1):
        self._record('controller',operation,0,0,0,cycles)

    def action_address(self, node_id):
        return self.node_address(node_id)+NODE.size+self.config['board_bytes']

    def allocate_node(self, node_id, node):
        if node_id!=self.nodes_used: raise ValueError('Node IDs must be allocated consecutively')
        address=self.node_address(node_id); board=np.asarray(node['board'])
        if board.shape!=(self.config['board_size'],self.config['board_size']) or not np.isin(board,[-1,0,1]).all():
            raise ValueError('Invalid node board')
        if node['children'] or node['player'] not in (-1,1) or node['visits']!=0 or node['value']!=0:
            raise ValueError('New nodes must have empty statistics and children')
        if (node_id==0 and node['parent']!=-1) or (node_id>0 and not 0<=node['parent']<node_id):
            raise ValueError('Invalid new-node parent')
        packed=NODE.pack(0,0.0,NO_NODE if node_id==0 else node['parent'],NO_NODE,0,int(node['player']==-1))
        bits=0
        for i,cell in enumerate(board.flat): bits|=(2 if cell==-1 else int(cell))<<(2*i)
        packed+=bits.to_bytes(self.config['board_bytes'],'little')
        packed+=struct.pack('<II',NO_NODE,NO_NODE)+bytes(self.config['action_mask_bytes'])
        self.transfer('node_sram','write',address,len(packed))
        self.node_sram[address:address+len(packed)]=packed
        self.nodes[node_id]=node; self.nodes_used+=1

    def remaining(self, node_id):
        address=self.action_address(node_id)
        self.transfer('node_sram','read',address,4)
        return struct.unpack_from('<I',self.node_sram,address)[0]

    def initialize_actions(self, node_id, actions):
        address=self.action_address(node_id)
        if struct.unpack_from('<I',self.node_sram,address)[0]!=NO_NODE:
            raise ValueError('Remaining actions are initialized once')
        if len(actions)!=len(set(actions)) or any(not 0<=a<self.config['action_slots'] for a in actions):
            raise ValueError('Invalid legal actions')
        mask=sum(1<<a for a in actions)
        self.transfer('node_sram','write',address+8,self.config['action_mask_bytes'])
        self.node_sram[address+8:address+8+self.config['action_mask_bytes']]=mask.to_bytes(self.config['action_mask_bytes'],'little')
        self.transfer('node_sram','write',address,4)
        struct.pack_into('<I',self.node_sram,address,len(actions))
        return len(actions)

    def action_mask(self, node_id):
        address=self.action_address(node_id)+8
        self.transfer('node_sram','read',address,self.config['action_mask_bytes'])
        return int.from_bytes(self.node_sram[address:address+self.config['action_mask_bytes']],'little')

    def consume_action(self, node_id, action, remaining, mask):
        address=self.action_address(node_id)
        if remaining<=0 or remaining!=mask.bit_count() or not mask&(1<<action):
            raise ValueError('Action must still be untried')
        word=action//32; value=(mask&~(1<<action))>>(word*32)&0xffffffff
        self.transfer('node_sram','write',address+8+4*word,4)
        struct.pack_into('<I',self.node_sram,address+8+4*word,value)
        self.transfer('node_sram','write',address,4)
        struct.pack_into('<I',self.node_sram,address,remaining-1)

    def reserve_children(self, count):
        if count!=1: raise ValueError('Incremental expansion allocates one child')
        super().reserve_children(count)

    def attach_children(self, parent_id, children):
        raise ValueError('Incremental memory requires append_child')

    def append_child(self, parent_id, child):
        node=self._node_fields(parent_id)
        if child!=self.edges_used+1 or self._node_fields(child)['parent']!=parent_id:
            raise ValueError('Append requires the next newly allocated child')
        if self.edges_used>=self.config['edge_capacity'] or node['children_count']>=self.config['cam_entries']:
            raise MemoryError('Child list capacity exceeded')
        if parent_id in self.cam:
            # Flush all groups to retain the FIFO's contiguous circular row order.
            for parent,(header,rows,_) in self.cam.items():
                address=self.config['cache_offset']+16*header
                self.transfer('node_sram','read',address,16)
                self.transfer('node_sram','write',address+12,4)
                struct.pack_into('<I',self.node_sram,address+12,0)
                for row in rows: self._record('cam','invalidate',row,0,0,self.config['cam_row_write_cycles'])
                self.count('cam_evicted_rows',len(rows))
            self.cam.clear(); self.cache_fifo.clear()
            self.free_rows=deque(range(self.config['cam_entries']))
            self.free_headers=deque(range(self.config['cam_entries']))
            self.count('cam_growth_flushes')
        tail_address=self.action_address(parent_id)+4
        self.transfer('node_sram','read',tail_address,4)
        tail=struct.unpack_from('<I',self.node_sram,tail_address)[0]
        edge=self.edges_used
        self.transfer('child_sram','write',8*edge,8)
        struct.pack_into('<II',self.child_sram,8*edge,child,NO_NODE)
        if node['children_count']:
            if not 0<=tail<edge: raise RuntimeError('Invalid child-list tail')
            self.transfer('child_sram','write',8*tail+4,4)
            struct.pack_into('<I',self.child_sram,8*tail+4,edge)
        start=edge if not node['children_count'] else node['children_start']
        address=self.node_address(parent_id)+16
        self.transfer('node_sram','write',address,8)
        struct.pack_into('<IHH',self.node_sram,address,start,node['children_count']+1,int(node['player']==-1))
        self.transfer('node_sram','write',tail_address,4)
        struct.pack_into('<I',self.node_sram,tail_address,edge)
        self.edges_used+=1; self.nodes[parent_id]['children'].append(child)
        self.control('append_child',3)

    def lookup_children(self, parent_id, node=None):
        node=self.read_node(parent_id) if node is None else node
        count=node['children_count']
        if not count: return []
        self.count('cam_searches')
        self._record('cam','search',parent_id,0,0,self.config['cam_search_cycles'])
        if parent_id in self.cam:
            self.count('cam_hits'); header=node['cache_header']
        else:
            self.count('cam_misses')
            while len(self.free_rows)<count:
                victim=self.cache_fifo.popleft(); header,rows,children=self.cam.pop(victim)
                self.transfer('node_sram','read',self.config['cache_offset']+header*16,16)
                for row in rows:
                    self._record('cam','invalidate',row,0,0,self.config['cam_row_write_cycles'])
                    self.free_rows.append(row)
                self.count('cam_evicted_rows',len(rows)); self.free_headers.append(header)
            rows=[]; children=[]; edge=node['children_start']
            for _ in range(count):
                if not 0<=edge<self.edges_used: raise RuntimeError('Invalid child-list link')
                self.transfer('child_sram','read',edge*8,8)
                child,edge=struct.unpack_from('<II',self.child_sram,edge*8)
                if self._node_fields(child)['parent']!=parent_id: raise RuntimeError('Child-list parent mismatch')
                self.control('follow_child_link')
                row=self.free_rows.popleft(); rows.append(row); children.append(child)
                self._record('cam','fill',row,8,0,self.config['cam_row_write_cycles'])
            if edge!=NO_NODE or len(set(children))!=count: raise RuntimeError('Child list is not terminated or contains duplicates')
            header=self.free_headers.popleft(); address=self.config['cache_offset']+header*16
            self.transfer('node_sram','write',address,16)
            struct.pack_into('<IIII',self.node_sram,address,parent_id,rows[0],count,1)
            address=self.node_address(parent_id)+20
            self.transfer('node_sram','write',address,4)
            struct.pack_into('<HH',self.node_sram,address,count,(header<<1)|int(node['player']==-1))
            self.cam[parent_id]=(header,rows,children); self.cache_fifo.append(parent_id)
            self.count('cam_filled_rows',count)
            self.cam_high_water=max(self.cam_high_water,self.config['cam_entries']-len(self.free_rows))
            self.count('cam_searches')
            self._record('cam','search_after_fill',parent_id,0,0,self.config['cam_search_cycles'])
        address=self.config['cache_offset']+header*16
        self.transfer('node_sram','read',address,16)
        parent,first,stored,valid=struct.unpack_from('<IIII',self.node_sram,address)
        if (parent,stored,valid)!=(parent_id,count,1): raise RuntimeError('Stale child-list cache header')
        if self.cam[parent_id][1]!=[(first+i)%self.config['cam_entries'] for i in range(count)]:
            raise RuntimeError('CAM rows are not in FIFO order')
        self.count('cam_output_ids',count)
        self._record('cam','output',parent_id,4*count,0,count*self.config['cam_output_cycles'])
        return list(self.cam[parent_id][2])

    def budget_reason(self):
        for resource,used,capacity in [('nodes',self.nodes_used,self.config['node_capacity']),
                ('edges',self.edges_used,self.config['edge_capacity']),
                ('path',self.path_high_water,self.config['path_entries'])]:
            if resource=='path' and capacity>=self.config.get('path_depth_bound',capacity+1): continue
            if used>=capacity: return {'resource':resource,'used':used,'capacity':capacity}
        return None

    def summary(self):
        result=super().summary()
        result.update(child_bytes_used=self.edges_used*8,
            action_state_bytes_used=self.nodes_used*self.config['node_extension_bytes'],
            functional_memory='Packed metadata, boards, remaining actions and linked child records; host dicts are observation mirrors',
            physical_status='Architectural SRAM/control service estimate; incremental controller RTL and physical timing not validated')
        return result
