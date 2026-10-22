# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Bounded, observation-only cycle intervals for the studio.
# SPDX-License-Identifier: MIT
from collections import deque


def service_intervals(records):
    intervals = []
    for row in records:
        if row['end'] <= row['start']:
            continue
        item = [row['resource'], row['operation'], row['start'], row['end'], row['phase']]
        if intervals and intervals[-1][:2] == item[:2] and intervals[-1][3] == item[2] and intervals[-1][4] == item[4]:
            intervals[-1][3] = item[3]
        else:
            intervals.append(item)
    return intervals


class Pipeline:
    def __init__(self):
        self.key = None
        self.revision = 0
        self.phases = deque()
        self.keep_iterations = 12

    def observe(self, event, model):
        if self.key != event['run']:
            self.key = event['run']
            self.phases.clear()
            self.revision += 1
        phase = event['phase']
        if phase == 'ready':
            return
        end = event['cycle_end']
        start = end - event.get('cycles',1)
        row = {'phase': phase, 'iteration': event['iteration'], 'start': start, 'end': end}
        if phase == 'neural':
            # Reuse the program's local service trace. Outer-controller gaps
            # are aggregated at the end, not presented as exact RTL positions.
            row['services'] = [['controller', 'aggregated_control_and_compute',
                start + model.neural.schedule['cycles'], end, phase]]
        elif phase == 'iteration_commit':
            row['services'] = [['controller', 'iteration_finish', start, end, phase]]
        else:
            records=[r for r in model.memory.transactions if r['resource']!='parallel_selection']+getattr(model,'selection_trace',[]) if phase=='selection' else model.memory.transactions
            row['services'] = service_intervals(sorted(records,key=lambda r:r['start']))
        self.phases.append(row)
        while self.phases and self.phases[0]['iteration'] <= event['iteration'] - self.keep_iterations:
            self.phases.popleft()
        self.revision += 1

    def payload(self, after=0, key=None):
        return {'key': self.key, 'revision': self.revision, 'keep_iterations': self.keep_iterations,
            'phases': None if key == self.key and after == self.revision else list(self.phases)}
