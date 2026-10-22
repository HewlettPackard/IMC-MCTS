# Component inventory and approximate PPA

Round 35, 2026-09-10. Inventory `component_ppa_inventory_v5`, ledger
`imc_22nm_components_v3`, peripheral policy `peripheral_22nm_estimate_v1`.
The digital conversion policy remains `imc_22nm_costs_v2`.

The studio, saved JSON and `components.csv` use the same installed-component
ledger. A matching default 9×9 design has 16 core cost owners and two excluded
interface groups. Its expandable inventory has 196 entries, including physical
modules, RTL instances and internal functional groups. This is a functional
inventory, not 196 independently characterized circuits or a transistor netlist.

## Ownership and timing

Selection owns its cache buffers and path/control logic. UCB owns both log
lookups, value codec, divider and square root. Rollout owns the neural
sequencer, accumulator, scale/rounding unit and divider. Expansion and Backprop
share one tree-update parent, including its codec and remainder unit. FSM
glue owns iteration orchestration and arbitration; its report excludes those
six child parents. Each SRAM router is an installed parent. The optional
column-hold controller is inside the buffered neural parent.

Nested synthesis areas are displayed but already included in the parent's
area. Functional groups without independent reports show `Included`.
Independent child power and latency are not fabricated. SRAM scratch regions,
hidden vectors, logits, probabilities and the exponential LUT are allocations
inside the existing banks. They are not extra SRAM macros. Legacy controllers,
mock ADC interfaces and testbench blocks are not installed physical resources.

Power is the component's energy divided by the same elapsed search/session
duration: `P_mW = 1000 * E_uJ / t_us`. Digital active time includes service
waits. SRAM time counts macro accesses; routers separately include the routed
service. CAM time counts the three-cycle search/read/write services. Analog
time follows the serialized array and ADC-group schedule. Concurrent lanes
share group time, so their lane count does not multiply latency. Cycles overlap
between modules and inclusive children; summing the rows is not chip latency.
All displayed times assume 500 MHz, with no physical delay scaling.

## Sources and installed physical parts

| Owner | Area and energy basis | Important condition |
| --- | --- | --- |
| Node/child SRAM | Unchanged pinned CACTI 22 nm bank costs, access counters and all-bank leakage | Three node banks and one child bank, 512 KiB each; HP/LSTP remain separate |
| Seven digital parents | Matching returned synthesis reports and Round 34 active/idle model | Native65 area and dynamic energy converted once; native65 leakage proxy |
| CIM cells | Workbook cell area, cell/wire capacitance and read conductance | Four 256×128 physical arrays in the default design; includes signed/sliced mapping |
| Parent-key CAM | Local CACTI fully associative cache estimate | Cost proxy for all-match search, not a matching physical CAM implementation |
| Binary row drivers | Workbook analog switch budget plus one-bit digital drive | One driver per installed row terminal, 1,024 in the default design |
| Shared S/H | Workbook amplifier, switches and 85 fF capacitor | Three lanes, including current-to-voltage conditioning; analog accuracy unvalidated |
| Shared 8-bit ADC | Pinned NeuroSim SAR model | Three lanes, comparator, internal DAC, SAR logic and local clock included |
| Analog selection/references | Workbook switch, digital select and bias budgets | 512 physical column routes, three reference buffers and one shared bias |
| Optional column hold | One amplifier/switch/capacitor front end per physical column | 512 holding cells; digital controller included in Rollout |
| Physical distribution | 15% installed-area allowance and 10% available digital-energy allowance | Engineering budgets, not extracted clock trees or routing |

Source record and every consumed file are hashed into each result and archived
with its source snapshot. [Tool evidence](../../p03_experiments/p35_component_ppa/p00_runs/run_20260910_202201Z/characterization.json)
retains raw outputs, configurations and build identity. The workbook SHA-256 is
`bce447d0a6f2e74a2b51062bfc4e5683061479814ff417171f887ea75615f3d0`.

### CAM proxy

CACTI revision `1ffd8dfb10303d306ecd8d215320aea07651e878` was rebuilt from the
existing pinned archive and portability patch. Its binary matches the earlier
SRAM build. Eight configurations cover 128/256/512/1024 rows at HP and LSTP,
22 nm and 360 K. Each has a 32-bit key plus valid, a 32-bit child payload,
one search port and one read/write port. CACTI pads the requested 33-bit tag to
36 physical bits. Capacities round upward to a supported physical row count;
unsupported larger capacities remain unpriced.

At 1,024 LSTP rows: 25,267.9 µm², 0.0229657 nJ/search,
0.00226152 nJ/payload read, 0.00313174 nJ/write and 0.01389747 mW
leakage. Fill and invalidation each conservatively charge a full row write.
Search energy and payload reads are charged separately using real counters.
Access delay 1.79438 ns and cycle time 1.4795 ns fit inside the existing 6 ns
service, but do not validate multi-hit output routing. CACTI's unrelated DRAM
I/O and MemCAD outputs are excluded, including their nonfinite fields.

### Analog estimates

The active binary-drive/shared-SAR topology is built from workbook primitives,
not its whole temporal-converter total. `C14` is 0.0424 µm²/cell. `L14/L15`
give 100 MΩ on-resistance and 0.4 V read voltage. Input activity and mean
conductance are each assumed to be 0.5. CIM dynamic energy adds switched
cell/wire `C*V²` and mean `V²/R` integrated over the existing scheduled drive
duration. Idle read bias is assumed off; off-state device current is unmodeled.
This is an analytical average, not weight-specific or waveform activity.

Driver area per physical row is `20*0.35 + 12.90946/8` µm², from
`C26:C28/D28`. The 8-bit digital budget is reduced to one bit; the analog
switch budget is retained. Driver transitions use `O26/P31`, with a 5% of
full-rate power standby allowance for all installed rows. That allowance is
not measured leakage. Level shifting and isolation are within the driver
budget, with no separate characterized design.

A front end is `85/15 + 2*0.35 + 6.398` µm²: capacitor, two switches and
amplifier (`C26,C40:C43`). The amplifier proxy is 12 µA at the workbook's
1.8 V, with 5% standby (`O40/U40`). Shared lanes retain active bias through
sample, request and conversion. Optional column front ends retain active bias
until their own sample, plus standby over elapsed time. Their capacitor-only
reference is not an additional area charge. The workbook does not establish
85 fF acquisition, retention or noise accuracy for this implementation.

NeuroSim revision `8a88abf85844c0e1ba17cc771ea535fff6040456`, 2D inference
v1.4, estimates a native22 HP SAR at 0.85 V and 360 K. The mean column is
25 MΩ from `100 MΩ/(16*0.5*0.5)`. One 8-bit lane is 180.4475904 µm²,
0.0880653635841444 pJ/conversion and 9 ns in that model. The existing
controller reserves 18 ns; this does not double energy. Its zero leakage
output means leakage is unmodeled. A separate 25% of native active-power
standby allowance is added, borrowing the workbook `U52` scale. Three
`ADC!D9` reference buffers contribute 0.6 mW; the `Q56` shared bias adds
0.52 mW once per core. These terms are outside the SAR estimate.

The tiny converter energy at this high input resistance comes from the source
model; it is not evidence of a characterized 8-bit converter. Shared converters
need not dominate this core's cost, which also includes large SRAM banks,
idle digital clock power and analog bias. No ENOB, noise, settling or circuit
accuracy claim follows from the cost numbers. The original workbook's
converter inconsistencies remain recorded in its separate reference model.

## Process conversion and limits

Only native65 digital area uses `(22/65)^2`. Only digital dynamic energy uses
`(22/65)*(0.8/1)^2`. Native65 leakage is retained unchanged as a proxy. CACTI,
CIM and adopted native22 workbook/NeuroSim quantities receive no second node
conversion. The workbook's digital driver term already contains its own
16-to-22 conversion. The SAR uses 0.85 V, the workbook bias uses 1.8 V and
CACTI uses source-specific HP/LSTP voltages. These are source conditions,
not a validated common physical operating point.

Host I/O, pads, ESD, package, external memory and weight programming/preload
remain visible as excluded groups. Their implementation is unspecified; their
cost is not zero. Host Go rules and metadata are also outside timed core work.
Complete-chip totals remain null. A 9×9 modeled-core estimate can be complete
within this stated boundary without becoming a full-chip measurement.
Smaller boards still lack four matching digital parent reports, so their
core subtotals remain incomplete. The 10% physical-energy allowance then
covers only available digital energy. Missing source configurations are never
filled by borrowing the 9×9 report.

Uncertainty is not quantified. This model is useful for a simple, traceable
component budget and workload comparison under fixed assumptions. Circuit
calibration, analog accuracy and physical implementation are still needed for
a measured or signoff-quality PPA claim. No synthesis or server waveform run
was performed for this update.
