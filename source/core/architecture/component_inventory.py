# Physical owners, synthesized children and internal functions, counted once.
# SPDX-License-Identifier: MIT
import csv
import math
from pathlib import Path

GROUPS = {
    'u_sel': [('Request and path control', ['Node metadata buffer (192 bits)', 'Path writer', 'Memory request and response state']),
        ('Child-list cache', ['Match-vector register', 'Child-ID buffer', 'FIFO head/tail and occupancy', 'Cache header and row registers']),
        ('Candidate selection', ['First-unvisited and first-tie priority', 'Visits, value and exploration registers', 'Best score and child registers'])],
    'u_ucb': [('Score datapath and control', ['Visit and exploration registers', 'Log interpolation', 'Mean and exploration products', 'Q32 rounding and score encoding', 'Local FSM and result handshake'])],
    'u_nn': [('Neural sequencing', ['Layer, tile, input-bit and row/column counters', 'Input-bit buffer and row mask', 'SRAM and ADC handshakes', 'ADC result registers and readout bus']),
        ('Activation and output logic', ['ReLU and hidden writeback', 'Maximum-logit subtraction', 'Exponential LUT addressing and sum', 'Probability and Q17 value reduction', 'Error and result registers'])],
    'u_upd': [('Expansion', ['Node and edge allocator', 'Empty-cell scan and child-board construction', 'Packed record and child-pointer writer', 'Parent list descriptor update', 'Xorshift32 seeded choice and path append']),
        ('Backprop', ['Path reader and ancestor addresses', 'Visit increment', 'White-player complement', 'Q17 value accumulation and writeback']),
        ('Shared update control', ['Board and node metadata buffers', 'Capacity checks', 'SRAM handshakes', 'Local FSM and error registers'])],
    'u_node_router': [('Bank interface', ['Bank decode and bounds/alignment check', 'Request address/data registers', 'Response data and valid/error holding', 'Backpressure control'])],
    'u_child_router': [('Bank interface', ['Bank decode and bounds/alignment check', 'Request address/data registers', 'Response data and valid/error holding', 'Backpressure control'])],
    'top_level_glue': [('Global FSM', ['Selection, Expansion, Rollout and Backprop start/wait states', 'Iteration budget, completion and cycle counters', 'One-cycle iteration finish']),
        ('Shared interconnect', ['Node request arbitration and response routing', 'Child request arbitration and response routing', 'Start/ready, result/acknowledge and error propagation', 'Random-state and evaluator configuration registers'])],
}

CHILDREN = {
    'u_accumulator': ('Shift/add accumulator', ['Signed shift/add lane', '32 × 32-bit register bank', 'Read/write selection and clear', 'Overflow and command checks']),
    'u_scale': ('Fixed-point scaling', ['Signed shift', 'Nearest-even rounding', '32-bit saturation']),
    'u_divider': ('Integer divider', ['Numerator and denominator registers', 'Restoring divide and remainder', 'Quotient and bit counter', 'Nearest-even rounding and result control']),
    'u_low': ('Lower log lookup', ['Combinational logarithm lookup table']),
    'u_high': ('Upper log lookup', ['Combinational logarithm lookup table']),
    'u_sqrt': ('Integer square root', ['Radicand', 'Root and remainder', 'Bit counter and result control']),
    'u_value': ('Q17 value codec', ['Packed value decode', 'Fixed-point conversion', 'Value encode']),
    'u_codec': ('Q17 value codec', ['Packed value decode', 'Fixed-point conversion', 'Value encode']),
    'u_choice': ('Child-choice remainder', ['32-bit numerator', 'Child-count denominator', 'Iterative remainder', 'Start/result control']),
    'u_column_hold': ('Column-hold controller', ['Capture strobe', 'Array/bank and valid ownership', 'Read count and release', 'Error checks']),
}


def included(name, parent, index, parts=(), area=None, source=None, count=1):
    row = {'id':parent+'/'+str(index), 'component':name, 'count':count,
        'area_um2':area, 'source':source, 'counted':False, 'included_in':parent,
        'status':'Included in parent; independent power and timing are not characterized', 'children':[]}
    row['children'] = [included(part, row['id'], i) for i,part in enumerate(parts)]
    return row


def attach_inventory(components, profile, memory, area_factor):
    incremental=(memory or {}).get('policy')=='evaluate_root_then_single_untried_child_v1'
    for row in components:
        row['counted'] = row.get('scope','core') == 'core'
        row.setdefault('children', [])
        parent = row['id']
        for i,(name,parts) in enumerate(GROUPS.get(parent, [])):
            row['children'].append(included(name, parent, 'functions_'+str(i), parts, source=row.get('source')))
        if incremental and parent in ('u_sel','u_upd','top_level_glue'):
            parts={'u_sel':['Remaining-action count check','Linked-list walk and cache fill'],
                'u_upd':['Remaining-action bitmap scan and clear','Single-child allocation','Child-list tail append and cache invalidation'],
                'top_level_glue':['Completed-iteration memory-budget checks']}[parent]
            row['children'].append(included('Single-child control',parent,'incremental',parts))
            if parent=='top_level_glue':
                row['children'][0]['children'][-1]['component']='Four-cycle iteration finish and budget checks'
        if parent in GROUPS:
            # Native hierarchical areas belong inside the parent, never beside it.
            keys = {'u_ucb':['u_value','u_low','u_high','u_divider','u_sqrt'],
                'u_nn':['u_accumulator','u_divider','u_scale'], 'u_upd':['u_choice','u_codec']}.get(parent, [])
            if parent == 'u_nn' and profile.get('readout',{}).get('profile') == 'column_hold_v1':
                keys = keys + ['u_column_hold']
            for key in keys:
                child = next((item for item in row.get('includes', []) if item['instance'] == key), None)
                name,parts = CHILDREN[key]
                sub = included(name, parent, key, parts,
                    area=None if child is None else child['inclusive_area_um2']*area_factor, source=row.get('source'))
                sub.update(rtl_instance=key, rtl_design=None if child is None else child['design'])
                if child is not None: sub['status'] = 'Native hierarchical synthesis area, scaled once; included in parent'
                row['children'].append(sub)
        if parent in ('node_sram','child_sram'):
            row['children'].append(included('512 KiB SRAM banks', parent, 'banks',
                ['Cell arrays', 'Address decoder and wordline drivers', 'Bitline read/write circuits', 'Sense amplifiers and output drivers', 'Internal bank wiring'],
                count=row['count'], source=row['source'], area=row['area_um2']))
        if parent == 'node_sram':
            names = ['Packed node records and boards', 'Selected-path buffer', 'Working-board scratch',
                'Candidate statistics scratch', 'CAM parent-list headers', 'Hidden vector', 'Logits',
                'Exponential LUT (4,097 words)', 'Probabilities and value']
            if incremental: names+=['Remaining-action count and bitmap per node','Child-list tail index per node']
            row['children'].append(included('Reserved SRAM regions', parent, 'regions', names))
        if parent == 'child_sram':
            row['children'].append(included('Linked child records (32-bit child ID + 32-bit next index)' if incremental else 'Ordered 32-bit child pointers', parent, 'pointers'))
        if parent == 'cim_arrays':
            columns_per_output = profile['weight_slices']*profile['sign_branches']
            outputs_per_array = profile['array_columns']//columns_per_output
            counts = [math.ceil(profile['input_size']/profile['array_rows'])*math.ceil(profile['hidden_size']/outputs_per_array),
                math.ceil(profile['hidden_size']/profile['array_rows'])*math.ceil(profile['outputs']/outputs_per_array)]
            for layer,count in enumerate(counts):
                row['children'].append(included('Layer '+str(layer+1)+' arrays', parent, 'layer_'+str(layer+1),
                    ['Positive and negative branches', 'Low and high 4-bit weight slices', 'Cell and local-wire capacitance'],
                    count=count, area=count*row['area_um2']/row['count'], source=row['source']))
        if parent == 'physical_overhead':
            row['children'].append(included('Physical implementation budget',parent,'distribution',
                ['Clock-tree buffers and wires', 'Reset distribution', 'Inter-module wiring', 'Floorplan spacing and routing reserve']))
        if parent in ('chip_io','weight_programming'):
            parts = ['Host request/response interface', 'Pads and ESD', 'External clock input and package', 'Host Go rules and metadata'] if parent=='chip_io' else [
                'Write-voltage and programming drivers', 'Weight addressing and write/verify control', 'Model/LUT and SRAM preload interface']
            for i,name in enumerate(parts):
                child = included(name,parent,i)
                child.update(scope='outside_core',count=None,status='Required outside the timed-core cost boundary; implementation unspecified')
                row['children'].append(child)
    return components


def inventory_rows(components, parent=None):
    rows = []
    for row in components:
        rows.append(row | {'parent_id':parent})
        rows.extend(inventory_rows(row.get('children', []), row['id']))
    return rows


def write_component_csv(path, ledger):
    fields = ['id','parent_id','component','count','counted','included_in','area_um2',
        'average_power_mw','energy_uj','active_cycles','active_us','service_cycles','service_unit',
        'status','energy_status','source','scope','cost_model_profile','cost_model_sha256',
        'controller_estimate_profile','controller_estimate_multiplier','reference_parameters']
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for row in inventory_rows(ledger['components']):
            value = {name:row.get(name) for name in fields}
            proxy=row.get('report_proxy',{})
            value.update(controller_estimate_profile=proxy.get('profile'),
                controller_estimate_multiplier=proxy.get('multiplier'),reference_parameters=proxy.get('reference_parameters'))
            value.update(cost_model_profile=ledger['profile'], cost_model_sha256=ledger['sha256'])
            writer.writerow(value)
