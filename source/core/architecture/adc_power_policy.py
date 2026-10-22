# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Shared ADC standby assumption; conversion and external bias remain separate.
# SPDX-License-Identifier: MIT
import json,math
from pathlib import Path

def adc_power_policy():
    path=Path(__file__).with_name('peripheral_assumptions.json')
    row=json.loads(path.read_text())['assumptions']['adc_idle_fraction']
    value=row['value']
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:
        raise ValueError('ADC idle fraction must be finite and between zero and one')
    return row
