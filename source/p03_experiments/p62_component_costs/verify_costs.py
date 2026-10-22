# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Raw-source reconciliation and controller-cost sensitivity, without new synthesis.
# SPDX-License-Identifier: MIT
import csv
import hashlib
import json
from pathlib import Path

from core.architecture.result_registry import ROOT, new_run, run_case, verify_run, write_json
from p03_experiments.p62_component_costs.cost_oracle import Sources, compare, expected


def main():
    experiment=Path(__file__).parent; out=new_run(experiment/'p00_runs'); print(out,flush=True)
    source=Sources(); records=[]; sensitivity=[]; checks=[]
    previous=ROOT/'p03_experiments/p61_single_child/p00_runs/run_20260915_210124Z'
    old=list(csv.DictReader((previous/'summary.csv').open()))
    for model in ('go_strong_v1','go_weak_v1'):
        for memory in ('cacti_22nm_lstp','cacti_22nm_hp'):
            for readout in ('sustained_drive_v1','column_hold_v1'):
                label=model+'_'+memory+'_'+readout
                folder,result=run_case(custom={'board_size':9,'iterations':500,'rules':'legacy_go','model_id':model,
                    'memory_profile':memory,'readout_profile':readout},runs=out/'p01_results/p01_runs')
                assert verify_run(folder)==result
                _,comparisons=compare(result,source); checks.extend(comparisons)
                ledger=result['costs']['ledger']
                assert ledger['missing_area']==ledger['missing_energy']==[]
                assert len(ledger['controller_report_proxy_components'])==4
                if readout=='sustained_drive_v1' and memory=='cacti_22nm_lstp':
                    prior=ROOT/next(row['run'] for row in old if row['model']==model and row['iterations']=='500' and row['repeat']=='1')
                    before=verify_run(prior)
                    for key in ('tree_sha256','node_sram_sha256','child_sram_sha256','phase_cycles','memory','last_value_q17','random_state','block_activity'):
                        assert result[key]==before[key],key
                    for name in ('iterations.csv','phases.jsonl'):
                        assert (prior/name).read_bytes()==(folder/name).read_bytes(),name
                for factor in (1.0,1.25,2.0):
                    rows=expected(result,source,multiplier=factor)
                    area=sum(row['area_um2'] or 0 for row in rows.values())/1e6
                    energy=sum(row['energy_uj'] or 0 for row in rows.values())
                    sensitivity.append({'label':label,'controller_multiplier':factor,'area_mm2':area,
                        'energy_uj':energy,'average_power_mw':energy*500000/result['metrics']['core_cycles'],
                        'cycles':result['metrics']['core_cycles'],'basis':'engineering scenario, not confidence interval'})
                record={'label':label,'run':str(folder.relative_to(ROOT)),
                    'area_mm2':ledger['known_area_mm2'],'energy_uj':ledger['known_energy_uj'],
                    'power_mw':ledger['known_average_power_mw'],'comparisons':len(comparisons)}
                records.append(record); write_json(out/'progress.json',records); print(record,flush=True)
    for filename,rows in [('sensitivity.csv',sensitivity),('comparisons.csv',checks)]:
        with (out/filename).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write_json(out/'metadata.json',{'status':'passed','cases':records,'comparisons':len(checks),
        'source_sha256':source.hashes,'controller_policy_sha256':hashlib.sha256((ROOT/'core/architecture/controller_estimates.json').read_bytes()).hexdigest(),
        'behavior_matches_round61':True,'new_controller_characterization':False,'whole_chip_ppa':False})
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n' for p in sorted(out.rglob('*')) if p.is_file()))
    write_json(experiment/'latest.json',{'costs':str(out.relative_to(ROOT))})
    print('All eight configurations and raw-source accounting passed',flush=True)


if __name__=='__main__': main()
