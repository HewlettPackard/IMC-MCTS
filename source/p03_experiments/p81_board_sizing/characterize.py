# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
from pathlib import Path
from copy import deepcopy
import csv,gzip,hashlib,io,json,math,re,shutil,subprocess
from p03_experiments.p08_cost_sources.characterize import build_cacti,run_case,sha,write_json
ROOT=Path.cwd()
OUT=ROOT/json.loads((Path(__file__).parent/'latest.json').read_text())['run']
source,build=build_cacti(OUT,'/usr/bin/clang++')
old=json.loads((ROOT/'core/architecture/sram_characterization.json').read_text())
macros={};cam={};files={}
for flavor in ('hp','lstp'):
 for kib in (64,128,256,512):
  template=old['cacti_22nm_'+flavor]
  if kib==512:
   macros[(kib,flavor)]=template
   continue
  folder=OUT/'p01_cacti'/f'sram_{kib}_{flavor}'
  base=(ROOT/template['source']['evidence']/'memory.cfg').read_text()
  config,n=re.subn(r'^-size .*',f'-size (bytes) {kib*1024}',base,flags=re.M);assert n==1
  requested=OUT/f'sram_{kib}_{flavor}.cfg';requested.write_text(config)
  parsed=run_case(source,requested,folder,build)
  execution=json.loads((folder/'execution.json').read_text())
  p=deepcopy(template);p.update(macro=parsed|{'voltage_v':template['macro']['voltage_v']},bank_bytes=kib*1024,
      macro_service_cycles=math.ceil(max(parsed['access_ns'],parsed['cycle_ns'])/2))
  p['source'].update(evidence=str(folder.relative_to(ROOT)),binary_sha256=build['binary_sha256'],
      cache_key=execution['cache_key'],config_sha256=execution['config_sha256'],raw_output_sha256=execution['output_sha256'])
  macros[(kib,flavor)]=p
  for name,digest in execution['output_sha256'].items():files[str((folder/name).relative_to(ROOT))]=digest
  print(kib,flavor,parsed['area_mm2'],p['macro_service_cycles'],flush=True)
 folder=OUT/'p01_cacti'/f'cam_2048_{flavor}';folder.mkdir()
 base=(ROOT/old['cacti_22nm_'+flavor]['source']['evidence']/'memory.cfg').read_text()
 edits=[(r'^-size .*','-size (bytes) 8192'),(r'^-associativity .*','-associativity 0'),
     (r'^-cache type .*','-cache type "cache"'),(r'^-tag size .*','-tag size (b) 33'),(r'^-search port .*','-search port 1')]
 for category in ('Data array cell','Data array peripheral','Tag array cell','Tag array peripheral'):
  edits.append(('^-'+category+r' type .*','-'+category+' type - "itrs-'+flavor+'"'))
 for pattern,value in edits:
  base,n=re.subn(pattern,value,base,flags=re.M);assert n==1
 (folder/'memory.cfg').write_text(base);shutil.copytree(source/'tech_params',folder/'tech_params')
 r=subprocess.run([str(source/'cacti'),'-infile','memory.cfg'],cwd=folder,capture_output=True,timeout=60);r.check_returncode()
 (folder/'stdout.txt').write_bytes(r.stdout);(folder/'stderr.txt').write_bytes(r.stderr)
 raw=r.stdout.decode();data=list(csv.DictReader(io.StringIO((folder/'memory.cfg.out').read_text()),skipinitialspace=True));assert len(data)==1
 def number(label):
  values=re.findall(r'^    '+re.escape(label)+r':\s*(\S+)\s*$',raw,re.M);assert len(values)==1
  value=float(values[0]);assert math.isfinite(value) and value>0;return value
 p={'entries':2048,'key_bits':32,'valid_bits':1,'payload_bits':32,'physical_tag_bits':36,'technology_nm':22,
   'voltage_v':.9 if flavor=='hp' else .8,'temperature_k':360,'flavor':flavor,'area_um2':float(data[0]['Area (mm2)'])*1e6,
   'access_ns':number('Access time (ns)'),'cycle_ns':number('Cycle time (ns)'),
   'search_energy_nj':number('Total dynamic associative search energy per access (nJ)'),
   'read_energy_nj':number('Total dynamic read energy per access (nJ)'),'write_energy_nj':number('Total dynamic write energy per access (nJ)'),
   'leakage_mw':number('Total leakage power of a bank (mW)')+number('Total gate leakage power of a bank (mW)'),
   'source':str((folder/'stdout.txt').relative_to(ROOT)),'status':'native22_CACTI_fully_associative_cache_proxy'}
 assert 'Associativity: fully associative' in raw and 'Tag size                      : 33' in raw
 assert math.isclose(p['read_energy_nj'],float(data[0]['Dynamic read energy (nJ)']),rel_tol=2e-5)
 assert math.isclose(p['leakage_mw'],float(data[0]['Standby leakage per bank(mW)']),rel_tol=2e-5)
 cam['cam_2048_'+flavor]=p
 for name in ('stdout.txt','stderr.txt','memory.cfg','memory.cfg.out'):files[str((folder/name).relative_to(ROOT))]=sha(folder/name)
 print('cam',flavor,p['access_ns'],p['cycle_ns'],flush=True)
sizes={2:(64,3,1),3:(128,3,1),5:(256,3,1),9:(512,3,1),13:(512,4,2),19:(512,7,2)}
profiles={}
for board,(kib,node,child) in sizes.items():
 for flavor in ('hp','lstp'):
  p=deepcopy(macros[(kib,flavor)]);p.update(banks={'node_sram':node,'child_sram':child},board_size=board,hardware_profile='board_sized_s1_v1')
  profiles[f'cacti_22nm_s1_b{board}_{flavor}']=p
write_json(OUT/'characterization.json',{'sram':profiles,'cam':cam,'source_files':files,'build':build})
print('DONE',flush=True)
