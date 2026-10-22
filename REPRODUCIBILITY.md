# Reproducibility and model scope

## Release form and entry points

This public-repository 0.2.0rc1 code update starts from the verified 19 October 2026 package. Its numerical implementations, schedules and component-cost equations are retained. Release wrappers, license headers and packaging change source-file identities without changing the intended numerical model. [RELEASE_STATUS.json](RELEASE_STATUS.json) records the version and distribution scope; [DISTRIBUTION.md](DISTRIBUTION.md) records the excluded-input scope. The project owner confirms the original repository security clearance is complete; this update does not impose a new blanket clearance workflow.

The supported install is from this artifact's root, using `python -m pip install .` or `make install` for the minimal review/test environment. The self-contained public suite is `make test`; it is not the full native simulator suite. The installed command `imc-mcts run --artifacts STORE --output NEW_DIRECTORY` executes the current runtime; `imc-mcts studio --artifacts STORE --output NEW_DIRECTORY --port 4784` starts a loopback-only Studio from a new writable copy. No runtime output is intentionally written into the installed package. Trained models support 9×9; use `--model random_diagnostic` for other supported boards.

The wheel contains the selected public runtime and Studio. The full source artifact additionally carries `reproduce.py`, frozen configurations, reference ledgers, archived comparison data and figure scripts. Both default distributions exclude 34 raw inputs: 16 standalone checkpoints (seven NPZ, seven PKL and two BIN), the model-containing historical fixture archive, one supplied workbook, two mapped netlists and 14 NeuroSim reference files. Required external file identities remain declared in the installer's manifest. Obtain an approved artifact packet separately, then run `imc-mcts artifacts install --archive /path/to/approved-artifacts.tar.gz --output /path/to/artifact-store`. Use that store with `--artifacts`; the input packet remains separate and no public download URL is offered. Source-artifact reproduction commands are run from its root. `.[paper]` installs plotting dependencies and `.[render]` adds optional PDF raster comparison. `requirements-lock.txt` records the resolved validation environment, while the project metadata specifies supported dependencies. Install the lock before the reproduction workflow to use those exact versions. The recorded environment supports the reproduction check; supported Python metadata alone is not evidence that every platform has passed it.

`python -B reproduce.py verify` checks bundled frozen files and retained data. `figures --verify-render` replots retained inputs without the external packet. `hero`, `scaling --jobs 2`, `tests`, `studio` and `all` require `--artifacts /path/to/artifact-store` and fail if required inputs are missing or changed. `make test-full ARTIFACTS=/path/to/artifact-store` runs the full native regression suite; `make test` and GitHub CI run the separate public suite. Use new output directories; frozen inputs are never output targets. Supported installation, execution and test checks are documented in [VALIDATION.md](VALIDATION.md), separately from the historical reference below. Full manuscript compilation, training and CPU/GPU benchmark reruns are not supported release targets.


## Current reference

The primary configuration is an empty 9×9 board with Go-strong weights, seed 0 and 5,000 iterations per move. Execution profile: `ucb16_adc32_buffered_v2`; cost profile: `ucb16_adc32_buffered_estimate_v6`. Hardware uses 16 UCB scorers, 32 shared ADCs, a 128-bit bus, two result banks, eight accumulation lanes and 2 MiB installed SRAM at an assumed 500 MHz.

| Metric | Retained value |
| --- | ---: |
| Cycles per move | 27,593,493 |
| Latency per move | 55.186986 ms |
| Energy per move | 3.7036957168173483 mJ |
| Search-average energy per iteration within a move | 0.7407391433634697 microjoules |
| Average core power during the move | 67.11175922557808 mW |
| Installed core area | 5.7975690837052705 mm2 |

Search-average energy is total move energy divided by its completed iteration count. It is not the energy of a uniform standalone iteration. Average power is energy divided by modeled search duration. Host wall time is a diagnostic and never substitutes for modeled hardware time.

configs/hero.json selects the exact trained cost replay. data/primary/hero.json preserves the accepted result. Current costs reaccount saved activity; historical execution-profile labels remain in the original records. Fresh package execution compares tree, SRAM, event and neural-trace hashes, phases, cycles and cost totals. The Go-strong NPZ SHA-256 is 6e5a9ecb967a5dfe704d74dc6526f1cc8bbd8ed45f34cbb9c108e6a895606906.

data/original_inputs_manifest.json records original copied data hashes. figures/inputs_manifest.json records plot input and adapted-script hashes. MANIFEST.json covers bundled package files. The external-artifact manifest separately binds required optional inputs by size and SHA-256. Source hashes reflect the release file set; execution state, timing, activity and cost checks remain separate. Original absolute paths retained in provenance are metadata, not runtime locations.

## Scaling

configs/scaling.json defines the diagnostic sweep:

| Board | Low | Medium | High |
| --- | ---: | ---: | ---: |
| 2x2 | 50 | 200 | 400 |
| 3x3 | 75 | 500 | 1,000 |
| 5x5 | 100 | 1,000 | 2,000 |
| 9x9 | 500 | 5,000 | 10,000 |
| 13x13 | 1,000 | 7,500 | 15,000 |
| 19x19 | 2,000 | 10,000 | 20,000 |

All 18 cases use random_diagnostic with seed 0 and the frozen NumPy generator. They test execution and accounting, not playing strength. diagnostic_results.json preserves original activity records plus current reaccounted costs. schedule_equivalence.json, schedule_source.diff and reaccounting_validation.json retain the scheduling/reaccounting chain. display_totals.csv substitutes the trained primary result only at 9x9-medium.

## Processor comparisons

data/baselines/index.json maps original trial CSVs to comparison columns. Current 9x9, 5,000-iteration rows average five trials. Original total_energy_uj is divided by 1,000 for mJ; total_latency_ms remains milliseconds.

gpu_fair supplies the traditional GPU comparison; gpu_max is context only. Batch64/256 rows contain neural results only. Missing traditional batched records are not inferred.

Traditional GPU reported energy covers an archived benchmark-wrapper interval extending beyond internally reported search duration. Raw traces and the monitor implementation are unavailable. Platform summaries do not supply device identifiers for every traditional trial. Neural CPU/GPU energy follows the paper's stated measured/rated-power methods. Arithmetic checks do not independently establish validity of these methods.

data/baselines/context/historical_summary.md retains historical numeric context; an obsolete internal codename is genericized in this public copy. Its old 256 mJ prose conflicts with the trial data's approximately 255.7 J mean. That prose is not a calculation input. Current CSVs preserve original units.

baselines/source_context/ contains historical code and attribution for inspection, not an exact executed-binary binding or supported CPU/GPU benchmark rerun.

## Figures and tables

The figure launcher executes only six fixed plotting scripts. It never runs training, benchmarks or tournaments. Figure 3c retains orange/blue steps and thick red final-ratio caps, with arithmetic checked against frozen ratios.

Conceptual diagrams are supplied PDFs, not regenerated schematics. Table files preserve the approved LaTeX extracts from the 19 October base package; they are not regenerated numerical experiments, an independent literature audit or a claim to contain later editorial caption changes. figures/coverage.json maps each paper item. Paper source compilation is not provided.

Figure 3d stays excluded. Figure 4a is an archived-data replot; exact trained application models and encoders remain unrecovered. Figure 4b reuses accepted diagnostic projections and component ledgers. Root verify checks their sums and units; it does not re-execute the non-Go application searches or independently reprice their censuses.

## Model and hardware limits

Super-T values and provenance remain in the retained records. Full execution requires the approved external workbook and historical mapped netlists at their original hash-bound runtime locations. The artifact installer verifies those identities before populating a writable runtime copy. Excluding them from the default distribution does not weaken the native source checks or establish permission to redistribute them. Selected licensed third-party validation code is also external and retains its own terms.

Native65 connected-path reports support scoped timing/electrical checks. Original-RTL equivalence and original-packet formal acceptance are not established. The 2 ns clock is an architectural/synthesis assumption, not a measured end-to-end silicon guarantee. Digital power is vectorless unless explicitly labelled otherwise. ADC standby is assumed. Analog non-idealities, programming, calibration and system I/O are not validated by deterministic tests.

## Native regression suite

With the approved external artifacts supplied, source/verify_runtime.py runs the full native regression suite, including the corrected legacy reference check and its focused negative tests. Its 208 historical fixtures are in the external hash-verified archive, temporarily extracted by test module with traversal/symlink rejection. Only created copies are removed. The source-artifact launcher makes a separate writable runtime/test copy; do not run multiple fixture launchers against the same copy. The public release suite does not silently substitute for these artifact-dependent checks.

The legacy placement failure came from treating a floating-point tree digest as a universal cross-runtime reference. With unchanged production engine source and the same seed, Python 3.10.4 / NumPy 1.26.4 / OpenBLAS and Python 3.12.11 / NumPy 2.3.5 / Accelerate produced identical discrete state: 6,562 nodes, 5,000 visited nodes, 5,000 completed iterations and 10,987,522 cycles. Runtime-specific random-normal initialization also changed weight bytes; the difference was not limited to BLAS matrix arithmetic. The largest observed accumulated-node-value difference was three ULPs, or 1.0658141036401503e-14.

The revised reference requires exact node identities, parent/child relationships, boards, players, visits and completion/timing, while checking every visited accumulated value with rtol=1e-14 and atol=2e-14. Unvisited values must remain zero and all values must be finite. Focused negative tests check that structural drift and values outside this envelope are rejected. Same-runtime raw tree hashes, evaluator hashes and run identities remain byte-exact. Production hashing is unchanged.

Both historical raw tree digests are retained with runtime metadata: 98522bb7a6031ddf375a84bcf63bdb86a9bd64a3b01a6513254d02969255a96d for the recorded Python 3.10 environment, and b2994c9396c2123ead4669b820b48ebfe40e86e7c69581a0a291801d9e4a5b05 for the recorded Python 3.12 environment. Neither is labelled stale or substituted as a new universal expected digest. The numerical envelope is supported by these two environments, not a claim of universal platform equivalence. Strict commands still exit nonzero on regression failures. The current integer hero and scaling replays retain their separate exact checks. See VALIDATION.md for observed suite outcomes.

## Provenance and distribution scope

The 0.2.0rc1 wrapper packages the retained runtime separately from the research working tree. Packaging, documentation and CLI changes are recorded alongside source identities. The public code update does not include or grant rights to the excluded raw inputs.

The 16 October package preserved 908 selected native files from the active repair checkout. Relative to that baseline, this refresh corrects one existing legacy test and its reference fixture, and adds three test/helper/value-fixture files. These changes define and exercise the numerical contract above; production simulator arithmetic, scheduling, cost equations and raw hashing are unchanged. Package orchestration and documentation record the refresh separately from original source provenance. Final file identities and verification outcomes are recorded in the manifest and validation records.

The protected original checkout, canonical paper and original numerical results are preserved. The previous package and its failure evidence remain historical records; the refresh does not relabel those older checks as passes.

The base package did not perform new physical validation, synthesis, training, tournaments or CPU/GPU benchmarks. The validation workflow replays the supported frozen cases; VALIDATION.md distinguishes fresh local checks from retained results.

## Writable Studio state

Native result saving requires outputs to stay within its runtime checkout. Both the installed Studio command and source-artifact launcher preserve this guard by copying the selected runtime into a fresh output directory and starting Studio there with a new result registry. Numerical engine bodies are unchanged. Approved external inputs are verified and copied into that workspace before execution. Search/play saves and registry updates affect only that writable copy. Historical experiment scripts are retained for native imports and provenance, not advertised as standalone reviewer commands.
