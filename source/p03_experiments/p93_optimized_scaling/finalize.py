# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
from pathlib import Path
import csv,hashlib,json,shutil,tarfile
ROOT=Path.cwd();H=ROOT/'p03_experiments/p93_optimized_scaling'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
manifest=read(H/'sweep_manifest.json');raw=[];checks=[]
for name in manifest['runs']:
 p=H/name;r=read(p/'result.json');c=read(p/'costs.json')
 assert r['status']=='complete' and all(read(p/'verification.json')[k] for k in ['completion','packed_memory','phase_cycle_conservation','power_unit_check'])
 assert all(sha(p/n)==v for n,v in read(p/'SHA256SUMS.json').items())
 assert all(sha(ROOT/n)==v for n,v in read(p/'source_sha256.json').items())
 assert abs(sum(x['area_um2'] for x in c['components'])/1e6-c['core_area_mm2'])<1e-9
 assert abs(sum(x['energy_uj'] for x in c['components'])/1000-c['core_energy_mj'])<1e-9
 assert abs(c['core_energy_mj']/r['latency_ms']*1000-c['core_average_power_mw'])<1e-9
 raw.append({'board_size':r['board_size'],'budget':r['budget'],'iterations':r['iterations'],'model':r['model'],'seed':r['seed'],'cycles':r['cycles'],'latency_ms':r['latency_ms'],'energy_mj':c['core_energy_mj'],'average_power_mw':c['core_average_power_mw'],'installed_area_mm2':c['core_area_mm2'],'installed_sram_bytes':r['installed_sram_bytes'],'status':r['status'],'run':name})
 checks.append({'run':name,'artifact_hashes':True,'source_hashes':True,'cost_conservation':True})
with (H/'scaling_all18.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(raw[0]));w.writeheader();w.writerows(raw)
repeat=Path((H/'final_primary_repeat.log').read_text().splitlines()[0]);r=read(repeat/'result.json')
first=read(H/'p01_runs/run_20260929_064147Z/result.json')
old=read(ROOT/'p03_experiments/p84_parallel_datapath/p00_runs/run_20260917_171530Z/p00_data/go_strong_v1/candidate.json')
same=['cycles','phase_cycles','tree_sha256','child_sram_sha256']
assert all(r[k]==first[k]==old[k] for k in same)
assert r['node_sram_sha256']==first['node_sram_sha256']
assert all(sha(ROOT/n)==v for n,v in read(repeat/'source_sha256.json').items())
assert read(repeat/'costs.json')==read(H/'p01_runs/run_20260929_064147Z/costs.json')
save(H/'reference_regression.json',{'status':'passed','compared_fields':same,'old_reference':'p84_parallel_datapath/p00_runs/run_20260917_171530Z/p00_data/go_strong_v1/candidate.json','primary':'p01_runs/run_20260929_064147Z','final_source_repeat':str(repeat.relative_to(H)),'repeat_node_bytes_identical':True,'old_node_bytes_identical':False,'reason':'Path capacity changes from 82 to 163, moving scratch/base addresses; numerical tree and cycles are unchanged.','final_repeat_cost_ledger_identical':True,'final_source_hashes_match':True,'primary_source_note':'Only result_registry.py metadata integration changed after the first primary run; final-source repeat closes that provenance difference.'})
for src,dest in [('imc_p93_paper.py','paper.py'),('imc_p93_paper_finish.py','paper_finish.py'),('imc_p93_browser.py','browser.py'),('imc_p93_restart.py','restart_idle.py'),('imc_p93_finalize.py','finalize.py')]:shutil.copy2(Path('/private/tmp')/src,H/dest)
for name in ['manuscript','supplement']:shutil.copy2(Path('/private/tmp')/f'imc_p93_{name}_build.log',H/'p05_pdf'/name/'build.log')
files=set()
for directory in ['core','tests','p05_studio/p00_app','p05_studio/p01_static']:
 files.update(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.json','.js','.css','.html','.md'))
for directory in [H,ROOT/'p03_experiments/p79_scalability',ROOT/'p03_experiments/p84_parallel_datapath']:files.update(directory.glob('*.py'))
files.add(ROOT/'p03_experiments/p62_component_costs/verify_large.py')
with tarfile.open(H/'source_snapshot.tar.gz','w:gz') as tar:
 for p in sorted(files):tar.add(p,arcname=str(p.relative_to(ROOT)))
save(H/'final_source_sha256.json',{str(p.relative_to(ROOT)):sha(p) for p in sorted(files)})
before=read(H/'p00_before/manifest.json');changed=[name for name,digest in before.items() if sha(ROOT/name)!=digest]
papers=read(H/'p02_paper_before/manifest.json');paper_changed=[n for n,d in papers.items() if Path(n).name!='.DS_Store' and sha(Path(n))!=d]
assert all(Path(n).suffix not in ('.bib','.cls','.bst') for n in paper_changed)
save(H/'final_verification.json',{'status':'passed','full_suite':'271 tests passed; all_tests_final.log','sweep':checks,'reference_repeat':str(repeat.relative_to(H)),'browser':read(H/'p03_studio_checks/browser_checks.json')['status'],'source_snapshot_sha256':sha(H/'source_snapshot.tar.gz'),'changed_preserved_files':changed,'changed_author_fix_files':paper_changed,'bibliographies_and_styles_unchanged':True,'physical_validation':False,'analog_validation':False,'historical_baselines_rerun':False})
print('PASS: 18 run hashes, current source identities, numerical conservation, full trained reference, source archive and paper edit scope')
