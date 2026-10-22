# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Overlapping parent activity changes power; do not reuse a serial coefficient.
# SPDX-License-Identifier: MIT
import hashlib
import json

from core.architecture.offset_costs import offset_costs
from core.architecture.parallel_selection import LANES


def overlap_costs(model):
    if model.selection_spec['profile'] != 'ucb4_ratio_first_overlap_v1':
        raise ValueError('Overlap costs require the matching selection profile')
    result = offset_costs(model)
    rows = [r for r in result['components'] if r['id'] not in LANES]
    for lane in LANES:
        rows.append({'id':lane,'component':'UCB arithmetic lane '+lane[-1].upper(),
            'count':1,'scope':'core','counted':True,'area_um2':None,'energy_uj':None,
            'average_power_mw':None,'dynamic_energy_uj':None,'leakage_energy_uj':None,
            'active_cycles':model.block_active_cycles[lane],
            'status':'changed_controller_and_overlapping_activity_uncharacterized',
            'source':'ucb_overlap.json and rtl_synthesis/p06_ucb_overlap',
            'assumptions':'Same arithmetic work; two added completion flags and changed FSM. Serial parent power is not a valid per-cycle coefficient for overlapped activity.',
            'children':[{'id':lane+'/'+str(i),'component':name,'count':1,'counted':False,'area_um2':None,'energy_uj':None,
                'status':'Part of unestimated parent; excluded from known totals'}
                for i,name in enumerate(('Mean/ratio divider','Integer square root','Log tables and interpolation',
                             'Q17 codec and score arithmetic','Completion flags and control'))]})
    result.update(profile=model.memory.config['execution_profile'],
        selection_profile=model.selection_spec['profile'],rollout_profile=model.rollout_spec['profile'],
        components=rows,known_area_mm2=sum(r['area_um2'] or 0 for r in rows)/1e6,
        known_energy_uj=sum(r['energy_uj'] or 0 for r in rows),
        missing_area=[r['component'] for r in rows if r['area_um2'] is None],
        missing_energy=[r['component'] for r in rows if r['energy_uj'] is None])
    result['known_average_power_mw'] = result['known_energy_uj']/(model.cycles/500000) if model.cycles else None
    result['source_identities']['overlapped_ucb'] = model.selection_spec['sha256']
    result['sha256'] = hashlib.sha256(json.dumps(result['source_identities'],sort_keys=True).encode()).hexdigest()
    result['reuse_policy'] += '; Changed UCB parents excluded, including their unchanged arithmetic children.'
    return result
