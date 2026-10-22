# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
# Independent clock-stepped producer/consumer reference, not event equations.

def pipeline_ticks(produce_durations,consume_durations,banks):
    states=['free']*banks
    queue=[]; produced=0; finished=0; tick=0
    producer=None; consumer=None
    while finished<len(produce_durations):
        if producer is not None and producer[1]==0:
            group=producer[0]; states[group%banks]='ready'; queue.append(group); producer=None
        if consumer is not None and consumer[1]==0:
            group=consumer[0]; states[group%banks]='free'; finished+=1; consumer=None
        if consumer is None and queue:
            group=queue.pop(0)
            duration=consume_durations[group]
            if duration:
                states[group%banks]='draining'; consumer=[group,duration]
            else:
                states[group%banks]='free'; finished+=1
        if producer is None and produced<len(produce_durations) and states[produced%banks]=='free':
            states[produced%banks]='producing'
            producer=[produced,produce_durations[produced]]; produced+=1
        if finished==len(produce_durations):return tick
        if producer is not None:producer[1]-=1
        if consumer is not None:consumer[1]-=1
        tick+=1
        if tick>1000000:raise AssertionError('Reference pipeline did not make bounded progress')
    return tick
