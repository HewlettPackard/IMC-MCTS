# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Opt-in arithmetic overlap, on the preserved two-array offset rollout.
# SPDX-License-Identifier: MIT
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from core.architecture.offset_encoding import OffsetGoSimulation
from core.architecture.parallel_selection import selection_spec

SPEC = Path(__file__).with_suffix('.json')


def overlap_spec():
    reference = selection_spec()
    raw = SPEC.read_bytes()
    update = json.loads(raw)
    fields = ('lanes','arithmetic_active_cycles','batch_accepted_to_valid_base_cycles',
              'batch_reduction_cycles_per_child','caller_request_and_capture_cycles')
    if tuple(update[k] for k in fields) != (4,169,169,1,2):
        raise ValueError('Unsupported overlapped UCB timing contract')
    spec = reference | update
    spec['reference_selection_sha256'] = reference['sha256']
    spec['sha256'] = hashlib.sha256(reference['sha256'].encode()+raw).hexdigest()
    return spec


class OverlappedUCBGoSimulation(OffsetGoSimulation):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reference_selection_spec = deepcopy(self.selection_spec)
        self.selection_spec = overlap_spec()
        # Do not publish the inherited single-scorer timing as this batch's cost.
        self.memory.config['reference_serial_ucb_cycles'] = self.memory.config.pop('ucb_cycles')
        self.memory.config.update(selection_profile=self.selection_spec['profile'],
            selection_spec_sha256=self.selection_spec['sha256'],
            selection_timing_source=self.selection_spec['timing_source'],
            ucb_batch_service_cycles='171 + valid_children (1..4)',
            execution_profile=self.memory.config['execution_profile']+'_ucb_overlap_v1',
            timing_status=self.selection_spec['timing_status'])

    def activity_record(self):
        result = super().activity_record()
        result['boundary'] = ('Four UCB parents reuse one divider and one square root each, with overlapping work. '
            'Parent busy cycles are not a calibrated power coefficient. No power gating.')
        result['arithmetic_work_per_score'] = self.selection_spec['per_score_arithmetic']
        return result
