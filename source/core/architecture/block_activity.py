# Non-IDLE FSM occupancy, including service waits and held results.
# SPDX-License-Identifier: MIT
from collections import Counter

PROFILE = 'digital_fsm_nonidle_v1'
BLOCKS = ('u_sel', 'u_ucb', 'u_nn', 'u_upd', 'u_node_router', 'u_child_router', 'top_level_glue')
UCB_ACTIVE_CYCLES = 223  # Non-IDLE part of the 225-cycle selector service; BLOCK_POWER_SPEC.md.


def phase_activity(phase, cycles, operations):
    active = Counter({'top_level_glue': cycles})
    owner = {'selection': 'u_sel', 'expansion': 'u_upd', 'neural': 'u_nn', 'backpropagation': 'u_upd'}[phase]
    # The top-level start cycle still sees the parent's IDLE state.
    active[owner] = cycles - 1
    active['u_ucb'] = UCB_ACTIVE_CYCLES * operations.get('ucb_operations', 0)
    for instance, pool in (('u_node_router', 'node_sram'), ('u_child_router', 'child_sram')):
        words = sum(operations.get(pool + '_' + op + '_words', 0) for op in ('read', 'write'))
        active[instance] = 2 * words
    if any(value < 0 or value > cycles for value in active.values()):
        raise ValueError('Block activity exceeds its phase interval')
    return active


def activity_record(active, cycles):
    if type(cycles) is not int or cycles < 0:
        raise ValueError('Elapsed cycles must be a nonnegative integer')
    if set(active) != set(BLOCKS):
        raise ValueError('Activity must identify every installed digital block once')
    rows = {}
    for instance in BLOCKS:
        count = active[instance]
        if type(count) is not int or not 0 <= count <= cycles:
            raise ValueError('Invalid active cycles for ' + instance)
        rows[instance] = {'active_cycles': count, 'idle_cycles': cycles - count}
    return {'profile': PROFILE, 'elapsed_cycles': cycles, 'blocks': rows,
        'boundary': 'Preloaded core execution; non-IDLE FSM includes waits/results. Idle is clocked, not power gated.'}
