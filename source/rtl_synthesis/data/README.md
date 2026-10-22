# RTL Synthesis Data

This directory contains the public data used by the accelerator RTL and
hardware-analysis scripts.

## Contents

```text
data/
├── CAM_cell_choices.csv
└── memory_characterization/
    └── cacti_integration/
```

`CAM_cell_choices.csv` collects published CAM-cell measurements across SRAM,
DRAM, ReRAM, MTJ, FeFET, and Flash designs. The CACTI directory contains memory
configuration files, characterization scripts, and the resulting public
summary.

Non-public measurement workbooks are not distributed in this repository. Any
analysis that uses non-public measurements must receive those values through an
explicit user-provided input rather than assuming they are present here.

## Regenerating CACTI Data

Run the characterization scripts from their own directory so relative paths
resolve consistently:

```sh
cd rtl_synthesis/data/memory_characterization/cacti_integration
python characterize_memories.py
python accelerator_complete_hardware.py
```

CACTI itself is an external dependency and is not vendored. Record the CACTI
version, process settings, and host environment when publishing regenerated
numbers.
