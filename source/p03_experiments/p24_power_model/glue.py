# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Project the existing controller into one standalone glue block at 9x9/H96.
# SPDX-License-Identifier: MIT
import re

INSTANCES = re.compile(r'^    (imc_\w+)\s*(?:#\((.*?)\)\s*)?(u_\w+)\s*\((.*?)\n    \);', re.M | re.S)
PORTS = re.compile(r'^\s*(input|output)\s+logic\s+(signed\s+)?(\[[^\]]+\]\s+)?(\w+)\s*[,\n]', re.M)
VALUES = {'BOARD_SIZE': 9, 'CAM_ENTRIES': 1024, 'HIDDEN': 96, 'ADDR_W': 21,
    'ROW_W': 10, 'ROW_COUNT_W': 11, 'BANK_BYTE_W': 19, 'BANK_WORD_W': 17}


def literal_width(width, instance):
    values = VALUES | {'BANKS': 1 if instance == 'u_child_router' else 3}
    width = width or ''
    for name, value in values.items():
        width = re.sub(r'\b'+name+r'\b', str(value), width)
    if re.search(r'[A-Za-z_$]', width):
        raise ValueError('Unresolved glue boundary width: '+width)
    return width


def project_glue(source, rtl):
    header, body = source.split(');', 1)
    top = re.search(r'module\s+(\w+)', header)[1]
    glue = top.replace('iteration_core', 'iteration_glue')
    ports = list(PORTS.finditer(header+'\n'))
    public = {match[4] for match in ports}
    instances = list(INSTANCES.finditer(body))
    if len(instances) != 6:
        raise ValueError('Expected six nonoverlapping installed parents')
    boundaries = []; assignments = []; connections = []; declarations = []; children = []
    for match in instances:
        child, _, instance, mapping = match.groups()
        child_header = rtl[child].split(');', 1)[0]+'\n'
        directions = {port[4]: port for port in PORTS.finditer(child_header)}
        links = re.findall(r'\.(\w+)\(([^()]*)\)', mapping)
        if len(links) != len(directions):
            raise ValueError('Incomplete child port map: '+instance)
        child_instance = match[0]
        for pin, signal in links:
            signal = signal.strip()
            if not re.fullmatch(r'\w+', signal):
                raise ValueError('Glue projection expects explicit scalar/bus nets: '+signal)
            port = directions[pin]
            direction = 'output' if port[1] == 'input' else 'input'
            boundary = instance+'__'+pin
            boundaries.append(f'    {direction} logic {port[2] or ""}{literal_width(port[3], instance)}{boundary}')
            assignments.append(f'    assign {boundary} = {signal};' if direction == 'output' else f'    assign {signal} = {boundary};')
            connections.append(f'        .{boundary}({boundary})')
            declarations.append(f'    logic {port[2] or ""}{literal_width(port[3], instance)}{boundary};')
            child_instance = child_instance.replace('.'+pin+'('+signal+')', '.'+pin+'('+boundary+')')
        children.append(child_instance)
    logic = INSTANCES.sub('', body)
    new_header = header.rstrip()+',\n'+',\n'.join(boundaries)+'\n'
    # Fixed boundary widths are intentional: this handoff characterizes only
    # the already returned 9x9/H96/CAM1024 implementation.
    new_header = new_header.replace('module '+top, 'module '+glue)
    new_header = new_header.replace('PPA role: complete_digital_core_including_selection_update_UCB_neural_and_routers',
        'PPA role: top_level_glue_only_children_excluded_fixed_9x9_H96_CAM1024')
    glue_source = new_header+');'+logic.replace('endmodule', '\n'+'\n'.join(assignments)+'\nendmodule')
    local = '    localparam int NEURAL_BYTES = 4 * ((HIDDEN + 3) / 4) + 16416;'
    original_links = [f'        .{name}({name})' for name in sorted(public)]
    wrapper = header+');\n'+local+'\n'+'\n'.join(declarations)+'\n'
    wrapper += f'    {glue} u_glue (\n'+',\n'.join(original_links+connections)+'\n    );\n'
    wrapper += '\n'.join(children)+'\nendmodule\n'
    return glue, glue_source, wrapper
