# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Readout wire scenarios are separate from register/ALU and analog costs.
# SPDX-License-Identifier: MIT
def interconnect_budget(operations,digital_dynamic_uj,fields=None,bus_bits=128):
    fields={} if fields is None else fields
    fraction=fields.get('dynamic_fraction',0.10)
    capacitance=fields.get('readout_capacitance_ff_per_bit',0)
    voltage=fields.get('readout_voltage_v',0.8)
    rise=fields.get('readout_rise_probability',0.25)
    if capacitance>0 and fraction!=0:
        raise ValueError('Set dynamic_fraction to zero before supplying readout capacitance; the allowance already covers routing')
    transfers=operations.get('neural_readout_words',0)
    # C in fF gives fJ. Source supply energy per 0-to-1 transition is C*V^2.
    wire=transfers*bus_bits*capacitance*voltage**2*rise/1e9
    allowance=fraction*digital_dynamic_uj
    return {'method':'user_capacitive_readout_wire_only' if capacitance>0 else 'global_dynamic_allowance',
        'readout_transfers':transfers,'readout_bus_bits':bus_bits,
        'readout_capacitance_ff_per_bit':capacitance,'readout_voltage_v':voltage,
        'readout_rise_probability':rise,'readout_wire_energy_uj':wire,
        'global_dynamic_allowance_uj':allowance,'dynamic_fraction':fraction,
        'dynamic_energy_uj':wire+allowance,
        'boundary':('User-supplied total capacitance per driven bit, including any chosen wire/repeater load. Full-width beats charged, including padding. Excludes register internal power, ALUs and analog conversion. Other physical clock/routing energy is uncharacterized in this scenario.' if capacitance>0 else
            'Global routing/clock-distribution allowance, not an extracted readout-bus model. Register clock-pin power remains in digital parents; no separate bus-wire estimate is added.'),
        'physical_validation':'unvalidated; capacitance and switching probability are assumptions, not extracted layout'}
