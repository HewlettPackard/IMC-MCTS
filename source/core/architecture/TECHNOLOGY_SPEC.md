# 22 nm cost and conversion contract

The active policy is `technology_scaling.json`, profile `imc_22nm_costs_v2`.
It is included in run identities. `cost_ledger.py` joins source-tagged installed
components and workload costs; the registry, CSV snapshot and studio consume
that ledger. Unknown values remain null. A known subtotal is never a chip total.

Round 35 extends the ledger to `imc_22nm_components_v3` without changing this
digital conversion policy. Native22 CAM/SAR tools and workbook primitives
provide explicit analog proxies, plus physical area/energy allowances. Their
source voltages remain distinct and receive no second node scaling. See
[COMPONENT_PPA_SPEC.md](COMPONENT_PPA_SPEC.md) for formulas and boundaries.
Whole-chip totals remain null; host interfaces and programming are excluded.

## Recovered scaling and operating point

The historical audit reconstructs 102 area cells using `(22/65)^2` and 101
power cells using `0.09291133727810653`; one power cell is missing. The old
tables contain fitted/predicted values for older modules. A further bounded
search of nine script/notebook candidates under the old archive's synthesis
tree did not recover the power conversion implementation or its conditions.

The author-hosted Stillmaker and Baas paper models technology- and voltage-
dependent FO4 energy, delay and power. Its process table does not contain a
22 nm row, and the authors corrected their example's energy coefficients.
Its area-table method combines several geometric measures. Therefore the
project's squared node ratio is labeled a geometric estimate, and the old
power multiplier is not attributed to a verified implementation of that
paper. Using a neighboring process or interpolating would introduce a new
assumption. [Author paper and correction](https://vcl.ece.ucdavis.edu/pubs/2017.02.VLSIintegration.TechScale/).

| Quantity | Current rule | Evidence and limit |
| --- | --- | --- |
| Digital area | `A22 = A65 * (22/65)^2`, once | Native matched TSMC65 mapped standard cells; geometric 22 nm estimate |
| Native SRAM | No node conversion | CACTI 22 nm, 0.8 V, 360 K; HP and LSTP remain separate profiles |
| CIM cell area | No node conversion | Workbook New_Architecture!C14, 0.0424 µm² per physical cell |
| Digital dynamic energy | `E22 = E65 * (22/65) * (0.8/1.0)^2`, once | Assumed linear capacitance scaling and 0.8 V supply; factor 0.21661538461538468; not process characterization |
| Digital leakage | `P_leak_proxy = P_leak65`, factor 1 | Native65 power retained because target device flavor, temperature and state are unknown; not a measured 22 nm value or a guaranteed bound |
| Latency | Controller cycles / 500 MHz | No physical delay scaling or 22 nm clock-closure claim |

Returned digital sources use TT, 1.00 V and 25 C. This differs from the CACTI
temperature and voltage. A common node label does not resolve those operating
conditions. The target digital supply is provisionally 0.8 V to match CACTI,
explicitly an assumption pending the user's voltage/process information.
The target library and digital temperature are not characterized.

The Round 34 approximation uses
`E_dynamic22/E_dynamic65 = (C22/C65)*(V22/V65)^2` at equal switching activity,
and `P_dynamic22/P_dynamic65` additionally contains `f22/f65`. A capacitance
ratio is declared here as linear in feature length under uniform geometric
scaling. This is a simple scenario, not a fitted TSMC65-to-22 model. Neither
the area ratio nor this dynamic formula is a leakage factor. The new policy has its own identity
and must not be called calibrated 22 nm PPA.

The capacitance/voltage formula follows the dynamic-power model described in
[Texas Instruments, CMOS Power Consumption and Cpd Calculation](https://www.ti.com/lit/an/scaa035b/scaa035b.pdf).
That source supports the formula, not our cross-node capacitance assumption.
The Stillmaker paper above warns about classical scaling at small nodes;
we do not attribute this factor to its fitted coefficients. The unchanged
leakage proxy deliberately assumes no leakage-power saving, but may still
underestimate a leakier target process. Temperature scaling is not available.

## Workload energy and module ownership

For each installed parent, the current simple model uses its source report's
total dynamic power while busy, reported clock power while idle, and leakage
throughout the search. These are activity assumptions. Native dynamic and
leakage terms are also reported separately. In the optional detailed flow,
a waveform averages over
its entire time window, including idle cycles. `E_pJ = P_mW * duration_ns`.
For a component energy in µJ and search duration in µs,
`average_power_mW = 1000 * energy_µJ / duration_µs`.

The neural parent includes accumulation, scaling and division. UCB includes
its arithmetic children. Tree update includes its codec and remainder divider;
expansion and backpropagation share that one installed parent. The two SRAM
routers are separate installed instances. The glue-only packet exposes all
six parents through ports. Round 25 admits its returned standalone area for
matching 9x9/H96/CAM1024 designs: 12,600.000255 µm² driven or 12,598.080255 µm²
buffered at native 65 nm. Only one is installed and scaled once. Child areas
are excluded from these glue reports. Two capacitance violations per variant,
multiport constraints and interface aliases remain visible. Workload power
and physical clock/routing closure are still unvalidated. The report-based
approximation does not change this validation status.

RTL activity and mapped-gate activity are different evidence. The packet
replays each matched mapped parent in the existing complete testbench and
requires annotation coverage review before adoption. The flow is zero-delay;
it does not include delay-dependent glitches or physical clock distribution.
[Synopsys power-profile guidance](https://www.synopsys.com/articles/understanding-power-profile.html).

## Historical source boundary and current estimates

The mentor workbook is useful for the installed CIM cell area and its own
NxN reference circuit. Its temporal drivers, column integrators and sequential
comparators do not match the current binary drive and three shared 8-bit ADCs.
The workbook already applies a 16-to-22 conversion to its driver terms.
The prior C53/O53 converter correction and standby-split discrepancy remain
recorded; reference values are not relabeled as active-chip costs.

Round 35 separately adapts selected primitive budgets to the active topology,
with pinned SAR and CAM estimates. These are new declared approximations,
not a claim that the whole reference circuit matches the current chip.

The component closure table in `p03_experiments/p24_power_model` records each
missing circuit's required inputs, ownership and accepted source boundary.
The short activity fixtures are calibration workloads. They cannot establish
energy for 5,000 iterations, another board size, a trained model or host Go
without a checked workload transfer model or a matching longer replay.

Full-chip area/energy/power remain unavailable until all in-boundary components
have compatible evidence. The preloaded-core boundary continues to exclude
host rules, weight programming, preload and chip I/O services. Their exclusion
must remain visible when interpreting an application result.
