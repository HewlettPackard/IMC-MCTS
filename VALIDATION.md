# Validation records

The public source and wheel separate code/data from 34 optional checksum-bound raw inputs, including all trained checkpoint files. Full simulator checks use an explicitly installed external-input store. The packaged `validation/` directory preserves historical 19 October reference evidence.

Local verification of the model-excluding package on Python 3.12.11 and NumPy 2.3.5 observed:

| Check | Recorded outcome |
| --- | --- |
| Public release suite | 24 tests passed without private models. |
| Native source suite | 311 tests passed; no failures, errors or skips. |
| Native wheel suite | 311 tests passed; no failures, errors or skips. |
| 9×9 hero replay | Go-strong weights, seed 0 and 5,000 iterations matched the retained reference: 27,593,493 cycles, 55.186986 ms modeled latency and 3.7036957168173483 mJ per move. |
| Studio launchers | Installed and source launch paths passed health, static-asset, short-search and export checks. Installed runtime files remained unchanged. |

Earlier full verification passed all 18 diagnostic scaling cases and eight exact rendered-figure comparisons. These results are retained under byte-identical numerical source, configurations and scientific data/figures; scaling and figure regeneration were not rerun after the additional checkpoint files were excluded. The publication documentation changes do not alter those numerical inputs or implementations.

`make test` runs the self-contained public suite. `make test-full ARTIFACTS=/path/to/artifact-store` and the hero/scaling replay require the verified external inputs. Figure regeneration uses retained public CSVs and expected PDFs. These workflows do not run training, tournaments or new CPU/GPU benchmarks.

SPDX comment headers and license sidecars may change source-file identities. Numerical source ASTs, historical characterized input bytes and expected result values remain protected. Replays check state, trace and memory-operation hashes and modeled totals; they do not establish physical accuracy or playing strength.

The results above are local checks, distinct from hosted CI. See the repository [Actions page](https://github.com/HewlettPackard/IMC-MCTS/actions) for current workflow status. `MANIFEST.json` binds the public files, and `SBOM.cdx.json` records the minimal Python dependency scope. The completed original clearance and excluded-input scope are recorded in [APPROVALS.md](APPROVALS.md). Figure 3d remains excluded and Figure 4a is an archived-data replot only.
