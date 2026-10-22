# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
from pathlib import Path
import hashlib,json,time
from core.architecture.board_sizing import board_table,PROFILE
from core.architecture.sized_simulation import SizedSingleChildGoSimulation
from core.architecture.analog_readout import configure_readout
from core.architecture.run_identity import tree_sha256
from core.architecture.complete_costs import complete_costs
from core.architecture.result_registry import configuration
ROOT=Path.cwd();OUT=ROOT/json.loads((Path(__file__).parent/'latest.json').read_text())['run']
files=['core/architecture/sized_simulation.py','core/architecture/board_sizing.py','core/architecture/board_sizing.json',
 'core/architecture/board_memory_characterization.json','core/architecture/single_child.py','core/simulator/incremental_memory.py',
 'core/simulator/tree_memory.py','core/architecture/iteration_model.py','core/architecture/neural_mapping.py','core/architecture/go_simulation.py']
identity={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in files}
(OUT/'sweep_source_sha256.json').write_text(json.dumps(identity,indent=2)+'\n')
results=[]
for row in board_table()['boards']:
 board=row['board_size'];budget=row['iterations']['high'];started=time.monotonic()
 model=SizedSingleChildGoSimulation(board,budget);configure_readout(model,'sustained_drive_v1')
 for event in model.steps():
  if event['phase']=='iteration_commit' and model.completed%5000==0:print(board,model.completed,flush=True)
 memory=model.memory.config
 assert model.status=='complete' and model.completed==budget,(board,model.status,model.termination)
 assert model.memory.nodes[0]['visits']==budget
 assert sum(model.phase_cycles.values())==model.cycles
 assert model.memory.nodes_used<=memory['node_capacity']
 assert model.memory.path_high_water<=memory['path_storage_entries']
 assert model.memory.edges_used<=memory['edge_capacity']
 config=configuration({'board_size':board,'hardware_profile':PROFILE,'rules':'legacy_go'})
 costs=complete_costs(config['memory_profile'],model.memory.operations,model.cycles,model.neural.profile,memory,model.phase_cycles,model.block_active_cycles)
 r={'board_size':board,'iterations':budget,'status':model.status,'completed_iterations':model.completed,'memory':memory,
 'nodes_used':model.memory.nodes_used,'edges_used':model.memory.edges_used,'path_high_water':model.memory.path_high_water,
 'cycles':model.cycles,'phase_cycles':dict(model.phase_cycles),'tree_sha256':tree_sha256(model.memory.nodes),
 'node_sram_sha256':hashlib.sha256(model.memory.node_sram).hexdigest(),'child_sram_sha256':hashlib.sha256(model.memory.child_sram).hexdigest(),
 'operations':dict(model.memory.operations),'evaluator':model.evaluator,'costs':costs,'wall_seconds':time.monotonic()-started}
 results.append(r);(OUT/'high_budget_results.json').write_text(json.dumps(results,indent=2)+'\n')
 print(board,'PASS',model.completed,'nodes',model.memory.nodes_used,'path',model.memory.path_high_water,'seconds',round(r['wall_seconds'],2),flush=True)
assert identity=={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in files}
print('PASS: all six high budgets, stable execution sources',flush=True)
