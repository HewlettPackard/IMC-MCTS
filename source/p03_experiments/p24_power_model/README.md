# Round 24: 22 nm policy, module activity and component closure

This round implements the user's five-step plan from local checkpoint
`b655a0d`. It extends the repair copy's estimation and verification workflow.
Native standard-cell power analysis still requires the user's server. No
unreturned server measurement or incompatible analog reference is invented.

## Conversion and component audit

[TECHNOLOGY_SPEC.md](../../core/architecture/TECHNOLOGY_SPEC.md) separates
area, dynamic energy, leakage and timing. The historical power multiplier is
reconciled but not adopted. The digital target supply is provisionally 0.8 V,
an explicit assumption to match CACTI, pending user process/voltage input.
Native digital reports remain TT/1 V/25 C; native CACTI is 22 nm/0.8 V/360 K.
Their common target-node label does not establish matched PVT or timing.

`audit.py` verifies the earlier source tables, checks the nine synthesis-script
candidates in the old archive, and writes a concrete component request CSV.
The accepted costs remain matched geometric digital area, native CACTI costs
and workbook CIM cell area. The workbook's other circuitry and capacitor-only
scenario stay separate. Digital workload energy, leakage conversion, CAM,
analog periphery and physical routing are pending compatible evidence.

## Power and glue packet

`prepare.py` reuses both complete testbenches and fixtures with the seven
returned parent-module cases. The driven and buffered variants each install
six parents, selecting one neural variant. `replay.py` can substitute each
parent's exact mapped netlist and record its entire counted workload window,
including idle clocks. The power flow binds SAIF to the original DDC and
retains coverage, units, library identity and native power reports.

The short empty/ragged fixtures exercise selection, expansion, neural work,
backpropagation and UCB. Their power must not be applied blindly to the full
canonical searches, other models or boards. The packet documents the required
representativeness check and the missing target process conversion.

`glue.py` projects the existing orchestration/arbitration logic into two
standalone alternatives at the returned 9x9/H96/CAM1024 shape. Their six child
modules become boundary ports, not internal instances. Reconstruction wrappers
reconnect those ports to the unchanged modules for complete-state replay.
Production RTL and controller schedules remain unchanged. Generic cell counts
are structure checks only; no gate-count-to-area factor is applied.

Read [PACKET.md](PACKET.md) for server requirements, returned artifacts and
the limits of zero-delay activity. Packet drafts and failed local checks are
retained under `p01_packets`; the verified portable release is under
`p02_release`. The server needs its existing .db, matching standard-cell
simulation models, Icarus/vvp, vcd2saif and Design Compiler. No PDK files are
included in the packet. Whole-core synthesis is optional.

## Integration and verification

`core/architecture/cost_ledger.py` is the common area/energy coverage ledger.
It preserves installed parent ownership, bills CACTI leakage over elapsed
time, derives average power from energy/time, and rejects duplicate parents
or an unreviewed power conversion. `technology_scaling.json` is hashed in
each run's source identity. The studio's live/saved costs and CSV exports
report the same ledger and retain null whole-chip totals.

Schema 6 snapshots add ledger identity and missing-component fields. Previous
snapshot schemas remain verifiable. New tables can include older records
with explicitly empty ledger fields rather than manufacturing new costs.

Commands from the repair checkout:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -B -m p03_experiments.p24_power_model.audit
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -B -m p03_experiments.p24_power_model.prepare
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -B -m unittest discover -s tests -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -B -m p03_experiments.p24_power_model.verify
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -B -m p03_experiments.p24_power_model.verify_browser
```

Use the pinned `/Users/tmolomochir/miniforge3/bin/python` environment locally.
All commands create fresh UTC runs. Original master files, frozen CPU/GPU
benchmarks and previous raw reports/results remain protected. Completion
evidence and the release/snapshot identifiers are recorded below after checks.

## Verified local results

| Evidence | Immutable run | Result |
| --- | --- | --- |
| Conversion audit | `p00_runs/run_20260910_023623Z` | Six checks pass; 102 area and 101 power cells reconciled. |
| Original RTL activity | `p01_packets/run_20260910_023011Z/p06_runs/run_20260910_023033Z` | Four fixtures pass; zero unknown activity events. |
| Reconstructed glue activity | `p01_packets/run_20260910_023235Z/p06_runs/run_20260910_023406Z` | Same four fixtures pass, preserving all cycles/state/traffic. |
| Glue compile/lint | `p00_runs/run_20260910_023900Z` | Four checks pass; zero Verilator warnings. |
| Generic glue structure | `p00_runs/run_20260910_024440Z` | Six checks pass; no latches or child module instances. |
| Full Python suite | `p00_runs/run_20260910_025655Z` | 136 tests pass; checked source hashes unchanged. |
| Canonical campaign | `p00_runs/run_20260910_024802Z` | 134 checks; six exact repeat pairs; eight older snapshots verify. |
| Browser/HTTP | `p00_runs/run_20260910_024810Z` | 27 checks pass; desktop/mobile and ledger exports agree. |
| Persistent studio | `p00_runs/run_20260910_025539Z` | 14 checks pass at 127.0.0.1:4781. |
| Final packet binding | `p00_runs/run_20260910_025902Z` | 25 checks pass, including all 12 parent substitutions. Mapped syntax uses unresolved-cell mode; this is not foundry functional replay. |

The driven empty/ragged fixtures take 114,074 / 332,459 cycles; buffered
fixtures take 114,398 / 333,431. These short diagnostic workloads validate
activity capture; their mean power is not automatically transferable to the
full canonical searches. Six canonical cases preserve all previous metrics,
state and traffic in [snapshot run_20260910_025251Z](../../p04_results/p04_snapshots/run_20260910_025251Z/summary.csv).

The verified portable release is
[p02_release/run_20260910_025901Z/power_activity](p02_release/run_20260910_025901Z/power_activity/README.md).
Its matching ZIP and generation-source archive sit beside it. All 242 packet
files were copied byte for byte to the private
[synthesis0909/p01_power_activity](https://github.com/tmo324/synthesis0909/tree/main/p01_power_activity),
commit `ab50db7`. Native libraries and cell models remain server dependencies.

Retained attempts document two glue-generation fixes, the mixed historical/new
CSV-field regression and an indented gate-module declaration parsing bug.
The earlier `p02_release/run_20260910_025429Z` is a superseded draft; use only
the later release above. Previous failed checks and immutable outputs were
not overwritten. Production RTL, schedules, native report catalogs and CPU/GPU
benchmarks are unchanged. Vendor gate replay, power and glue synthesis, target
power/leakage conversion and matching CAM/analog costs remain pending.

Protected-source verification: `p00_runs/run_20260910_030144Z` confirms all
3,444 original files/398 directories, 22 frozen benchmark files and 168
current implementation/test sources. No benchmarks or original Git commands
ran. The final staged-artifact audit is `p00_runs/run_20260910_030231Z`.
The independent repair repository remains local, separate from the private
synthesis handoff; a verified checkpoint records the final state.
