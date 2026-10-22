# Reusable digital block power, report-based approximation

`block_power_coefficients.json` is the single coefficient table. It is tied to
the SHA-256 of the existing digital synthesis catalog, exact block parameters,
native65 TT/1.00 V/25 C, and 500 MHz. Nine native cases cover seven installed
blocks in either readout. Round 34 uses the existing vectorless reports under
the explicitly approximate `vectorless_clock_floor_v1` method. This supersedes
the pending-calibration requirement for this model only. The detailed server
calibration packet and previous null-coefficient results remain historical.

`active_dynamic_mw` is the report's total dynamic power. `idle_dynamic_mw` is
the sum of internal and switching power in its `clock_network` group, using
the report's dynamic units. `leakage_mw` is its separately unit-tagged cell
leakage summary. The clock group includes register clock-pin power; it is
not a physically implemented chip clock tree. All nine configurations are
listed in [the extracted table](../../p03_experiments/p34_simple_power/native_power.csv).

The reported activity is assumed by the synthesis tool. Treating its dynamic
power as active power and its clock group as idle power is a modeling choice,
not an active/idle measurement. Nonclock idle switching is omitted, and real
active data switching can differ. Idle is not reset or power-gated. No
quantitative accuracy or guaranteed upper/lower bound is claimed.

## Activity definition

`digital_fsm_nonidle_v1` counts cycles with the relevant FSM outside ST_IDLE,
within the existing accepted-search to completed-result interval. Service waits
and result states count as active. Idle is clocked; this model assumes no power
gating. Reset, preload, host work and display pauses remain outside core time.

| Installed block | Active cycles in the nominal serialized schedule |
| --- | --- |
| Selector | Selection phase duration minus its one IDLE start cycle |
| Tree update | Expansion/backpropagation phase duration minus one start cycle per invocation |
| Neural sequencer | Neural phase duration minus its one IDLE start cycle |
| UCB | 223 per successful visited-child request, inside its 225-cycle selector service |
| Node/child router | Two non-IDLE cycles per completed 32-bit word transaction |
| Top-level glue | Entire counted core interval, including iteration commit |

These equations match the retained original-RTL state waveforms for all four
9x9 power fixtures: both readouts, empty and ragged boards. The router equation
assumes the existing unstalled ideal-memory service; arbitrary external stalls
would require counting actual occupancy. Other configured sizes reuse the
same FSM contract; waveform comparison here covers 9x9/H96/CAM1024. Host Go
retains its existing component-schedule scope, not a complete Go RTL claim.

`CompleteSimulation.block_active_cycles` is separate from memory operations.
Every completed phase updates the counters without changing its duration or
transactions. `activity_record` requires all seven instances and checks
0 <= active <= elapsed. Idle is elapsed minus active for each block. Active
times can overlap and must not be summed to derive workload latency.

## Energy and coefficient admission

Each table entry holds `active_dynamic_mw`, `idle_dynamic_mw` and `leakage_mw`.
Dynamic includes the clock activity present in that state, excluding leakage.
Leakage is a constant approximation for the specified operating point.

```text
dynamic_nJ = active_dynamic_mW * active_us + idle_dynamic_mW * idle_us
leakage_nJ = leakage_mW * elapsed_us
energy_nJ = dynamic_nJ + leakage_nJ
average_power_mW = energy_nJ / elapsed_us
```

Each entry's `evidence` object names the approximation and the original
report path and SHA-256. The loader verifies the catalog, exact parameters,
source hash and values parsed from the report. Changing a coefficient without
changing its source is rejected. Active and idle counters retain their verified
state definition; these counters do not validate the assumed switching power.

An unsupported block configuration or missing coefficient stays unpriced.
Summation counts each installed parent once, with its internal children
included. Node/child router logic is separate from the SRAM macros it serves.
Native65 digital energy stays separately visible. `technology_scaling.json`
converts dynamic energy once by `(22/65)*(0.8/1.0)^2`. It carries leakage power
unchanged as an explicit native65 proxy. The ledger adds these target-scenario
digital estimates to unchanged native22 CACTI SRAM energy. This does not
establish a common physical operating point. Read [TECHNOLOGY_SPEC.md](TECHNOLOGY_SPEC.md).

## Saved and live results

Search and play JSON contain `block_activity` and `costs.block_power`.
`block_power.csv` contains seven rows with configuration, active/idle time,
native node, nullable coefficients/energies and coefficient-table identity.
The table and calibration sources are included in the search source archive.
The shared ledger attaches each block's activity/native estimate without
adding native65 energy to the 22 nm subtotal. Historical records remain valid.

Studio component rows show active/idle cycles and the report-based estimate. The
Block power CSV download is the exact saved file. Successive moves sum the
underlying block counters and energy windows while reusing one chip.

Original counter validation: [Round 29](../../p03_experiments/p29_block_power/README.md).
Current model and verification: [Round 34](../../p03_experiments/p34_simple_power/README.md).
