# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
from pathlib import Path
import json
from core.architecture.iteration_model import CompleteSimulation
from core.architecture.single_child import SingleChildSimulation, SingleChildGoSimulation
from core.architecture.analog_readout import configure_readout
from core.architecture.complete_costs import complete_costs
from core.architecture.crossbar_workbook import component_estimates
from core.architecture.run_identity import tree_sha256
from core.algorithm.model_catalog import load_model

def reference():
 rows={}
 for board in (2,3,5,9):
  for kind in ('full','single'):
   for readout in ('sustained_drive_v1','column_hold_v1'):
    model=(CompleteSimulation if kind=='full' else SingleChildSimulation)(board_size=board,iterations=10)
    configure_readout(model,readout)
    list(model.steps())
    for flavor in ('hp','lstp'):
     profile='cacti_22nm_'+flavor
     rows[f'{board}_{kind}_{readout}_{flavor}']={'cycles':model.cycles,'tree':tree_sha256(model.memory.nodes),
       'costs':complete_costs(profile,model.memory.operations,model.cycles,model.neural.profile,model.memory.config,model.phase_cycles,model.block_active_cycles),
       'components':component_estimates(model.neural.profile,profile,model.memory.config)}
 return rows
if __name__=='__main__':
 import sys
 Path(sys.argv[1]).write_text(json.dumps(reference(),indent=2)+'\n')
