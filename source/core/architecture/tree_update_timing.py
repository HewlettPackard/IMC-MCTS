# Timing revision shared by placement, host-assisted Go, and area admission.
# SPDX-License-Identifier: MIT
PROFILE='registered_count_iterative_remainder_v2'
EXTRA_EXPANSION_CYCLES=35


def expansion_cycles(words, children):
    if not children: return 26+9*words
    return 38+9*words+children*(26+6*words)+EXTRA_EXPANSION_CYCLES
