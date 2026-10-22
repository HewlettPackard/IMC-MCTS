# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Independent raw-report reconstruction with explicit controller allowance scenarios.
# SPDX-License-Identifier: MIT
from p03_experiments.p61_single_child.cost_oracle import Sources, expected as excluded_expected, check, flatten


def expected(result, source, multiplier=1.25):
    rows=excluded_expected(result,source)
    elapsed=result['metrics']['core_cycles']; time_us=elapsed/500
    # This experiment is deliberately restricted to reviewed 9x9/H96/163 geometry.
    p=result['neural']['profile']; memory=result['memory']['config']
    assert (p['board_size'],p['hidden_size'],p['input_size'],memory['cam_entries'])==(9,96,163,1024)
    assert (memory['node_sram_bytes'],memory['child_sram_bytes'],memory['neural_bytes'])==(1572864,524288,16512)
    buffered=p['readout']['profile']=='column_hold_v1'
    cases={'u_sel':'imc_cached_selector','u_upd':'imc_tree_update_v2',
        'u_nn':'imc_buffered_neural_sequencer' if buffered else 'imc_neural_sequencer',
        'top_level_glue':'imc_buffered_iteration_glue' if buffered else 'imc_iteration_glue'}
    digital_ids=set(result['block_activity']['blocks'])
    for key,case in cases.items():
        raw=source.digital_report(case); row=rows[key]; active=row['active_cycles']
        dynamic=multiplier*(raw['active_mw']*active+raw['idle_mw']*(elapsed-active))/500/1000*(22/65)*.8**2
        leakage=multiplier*raw['leakage_mw']*time_us/1000
        row.update(area_um2=raw['area_um2']*multiplier,dynamic_energy_uj=dynamic,
            standby_energy_uj=leakage,energy_uj=dynamic+leakage,average_power_mw=(dynamic+leakage)*1000/time_us,
            children={},sources=list(raw['reports'].values())+['core/architecture/controller_estimates.json'])
    area=sum(row['area_um2'] or 0 for key,row in rows.items() if key!='physical_overhead')
    energy=sum(rows[key]['energy_uj'] or 0 for key in digital_ids)
    physical=rows['physical_overhead']; energy*=source.assumptions['clock_wire_power_fraction']
    physical.update(area_um2=area*source.assumptions['layout_area_fraction'],
        dynamic_energy_uj=energy,energy_uj=energy,average_power_mw=energy*1000/time_us)
    return rows


def compare(result, source):
    rows = expected(result, source)
    ledger = result['costs']['ledger']
    assert set(rows) == {r['id'] for r in ledger['components']}
    comparisons = []
    for actual in ledger['components']:
        target = rows[actual['id']]
        for field in ('count', 'area_um2', 'energy_uj', 'average_power_mw', 'active_cycles', 'service_cycles'):
            check(actual.get(field), target[field], actual['id'] + '.' + field)
            comparisons.append({'owner': actual['id'], 'metric': field, 'actual': actual.get(field), 'independent': target[field], 'status': 'pass'})
        if actual.get('id') in result.get('block_activity', {}).get('blocks', {}):
            occupancy = result['block_activity']['blocks'][actual['id']]
            check(occupancy['active_cycles'], target['active_cycles'], 'FSM ' + actual['id'])
            check(occupancy['idle_cycles'] + occupancy['active_cycles'], result['metrics']['core_cycles'], 'idle elapsed')
    tree = flatten(ledger['components'])
    assert len(tree) == len({r['id'] for r, _ in tree})
    for row, owner in tree:
        if row['id'] == owner:
            continue
        assert row['counted'] is False and row.get('energy_uj') is None and row.get('average_power_mw') is None, row['id']
        if row.get('rtl_instance'):
            check(row['area_um2'], rows[owner]['children'].get(row['rtl_instance']), row['id'] + ' raw hierarchical area')
        elif row.get('area_um2') is not None:
            ratio = row['count'] / rows[owner]['count'] if owner == 'cim_arrays' else 1
            check(row['area_um2'], rows[owner]['area_um2'] * ratio, row['id'] + ' included area')
    area = sum(r['area_um2'] or 0 for r in rows.values()) / 1e6
    energy = sum(r['energy_uj'] or 0 for r in rows.values())
    check(ledger['known_area_mm2'], area, 'area sum owners once')
    check(ledger['known_energy_uj'], energy, 'energy sum owners once')
    check(ledger['known_average_power_mw'], energy * 500000 / result['metrics']['core_cycles'], 'power energy/time')
    check(result['metrics']['core_latency_us'], result['metrics']['core_cycles'] / 500, 'latency clock')
    check(sum(result['phase_cycles'].values()), result['metrics']['core_cycles'], 'phase cycles elapsed')
    for key in ('whole_chip_area_mm2', 'whole_chip_energy_uj', 'whole_chip_power_mw'):
        check(ledger[key], None, key)
    return rows, comparisons
