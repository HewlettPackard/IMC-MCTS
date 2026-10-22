# Characterized SRAM profiles

Round 9, 2026-09-09 UTC. These are opt-in **CACTI analytical SRAM estimates**
for the 9x9 mapped candidate. They do not establish foundry macro performance
or whole-chip PPA. The default `memory_profile='reference'` preserves the
Round 8 memory schedule and results.

```python
from core.architecture.accelerator_api import Accelerator

result = Accelerator(
    board_size=9, iterations=5000, seed=0, neural_mode='mapped',
    memory_profile='cacti_22nm_lstp',
).analyze('simulate')
print(result.latency_us)
print(result.accounting['sram'])
assert result.energy_uj is None  # Complete chip energy is still unavailable.
```

The alternative `cacti_22nm_hp` is a distinct technology-flavor sensitivity
case. Neither is selected as the canonical paper implementation. Both require
`board_size=9`, `neural_mode='mapped'`, and event simulation. Other board sizes
need their own exact characterization. Allocation quotas do not resize macros.

## Physical organization and services

The node pool contains three 512 KiB macros; the child pool contains one.
Total physical SRAM is exactly 2 MiB. Existing board/path/cache/neural scratch
partitions live inside the node pool, including its 16,512-byte neural region.
Each macro has one 32-bit read/write port, four-byte access size, no tags, no
ECC, and no power gating. One logical port per pool is exposed. The chip model
serializes all operations, including operations to different banks.

Within either pool, `bank = byte_address // 524288` and
`macro_offset = byte_address % 524288`. Every aligned 32-bit word accesses
exactly one macro. Multiword transactions are serialized word by word, including
those spanning a macro boundary. Global byte-address traces and the recorded
bank layout determine every physical word address. There is no bank parallelism
or unpriced spill. All installed macros leak throughout the modeled search.

At the fixed 500 MHz clock, macro service uses
`ceil(max(access_ns, cycle_ns) / 2)`. One additional serialized cycle per word
is an explicit **uncharacterized bank-selection/routing assumption**. Both
accepted profiles therefore use two cycles per word. Routing area/energy is
excluded. This rounding rule is not clock-closure evidence. CAM services,
binary64 tree arithmetic, neural converters, and other logic retain their
separately documented uncalibrated timing assumptions.

## Native 22 nm characterization

Both flavors use the pinned CACTI 22 nm technology file at its native 0.8 V,
360 K, matched cell/peripheral flavor, ED-squared optimization, conservative
wire projection, semiglobal internal/external wires, and Global_30 H-trees.
The input file contains inherited DDR/MemCAD settings that do not describe
on-chip SRAM. The executable prints those unrelated sections too; the parser
accepts only UCA SRAM metrics and their CSV record.

| One 512 KiB macro | HP | LSTP |
| --- | ---: | ---: |
| Area (mm²) | 0.382952 | 0.414262 |
| Access time (ns) | 0.771699 | 1.89215 |
| Cycle time (ns) | 0.393025 | 1.91559 |
| Read energy (nJ/32-bit access) | 0.00968358 | 0.0111329 |
| Write energy (nJ/32-bit access) | 0.00672363 | 0.00775607 |
| Subthreshold leakage (mW) | 138.441 | 0.110278 |
| Gate leakage (mW) | 0.269996 | 0.0630806 |

Values come directly from the clean-build raw outputs, with both leakage
components summed once. CACTI is already at 22 nm; its records specify zero
technology-conversion applications. Applying the digital 65-to-22 nm factor
again is rejected. The packaged [cost data](sram_characterization.json) and its
profile hashes are part of run identity and the exact source snapshot.

The tool accepts a requested 1.5 MiB macro, but returns a 96-row subarray.
Its source computes row/decoder address width using integer floor-log2. This
does not establish correct decoding for 96 rows. The accepted profiles use
power-of-two macros and subarray dimensions instead. No capacity is rounded
up or silently priced using a smaller macro. See the
[source audit and raw evidence](../../p03_experiments/p08_cost_sources/README.md).

## Accounting boundary

For each pool:

```text
dynamic_energy_nJ = read_words * read_energy_nJ + write_words * write_energy_nJ
leakage_energy_nJ = installed_banks * macro_leakage_mW * elapsed_time_us
area_mm2 = installed_banks * macro_area_mm2
```

Costs include root initialization, node/board/path/cache transfers, child
pointers, neural staging, and LUT initialization/lookups. They exclude Python
host work and do not multiply dynamic access energy by macro count again.
Read/write word counts include the resolved neural schedule exactly once.
Average SRAM power is SRAM energy divided by modeled elapsed time, never host
runtime. No duty-cycle factor or frequency factor is applied to leakage.

`accounting.sram.status` is `partial_sram_tool_estimate`. Complete chip energy,
power, area, and energy efficiency remain `None`. The excluded components are
listed in the result. This prevents SRAM-only values from being mistaken for
complete chip measurements.

CACTI's ITRS bitcell assumption is 146 F², or 0.070664 µm² at 22 nm.
Intel's published 22 nm test-chip cells are 0.092 and 0.108 µm². These are
different device/process conditions, so this comparison flags model optimism
without providing a correction factor or a foundry calibration.
[Intel's primary technology fact sheet](https://www.intel.com/content/dam/doc/fact-sheet/22nm-technology-idf2009-factsheet.pdf).

The next cost work is a compatible digital datapath/control implementation and
converter/device characterization, including loaded binary drivers, three
ADC/S&H lanes, references, array current during multiplexed conversion, and
chip routing. The historical fitted digital tables cannot price those blocks
until their interfaces, precision, activity, and technology assumptions match.
