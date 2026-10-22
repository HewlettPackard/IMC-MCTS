# IMC-MCTS

[![CI](https://github.com/HewlettPackard/IMC-MCTS/actions/workflows/ci.yml/badge.svg)](https://github.com/HewlettPackard/IMC-MCTS/actions/workflows/ci.yml)
[![Secret scan](https://github.com/HewlettPackard/IMC-MCTS/actions/workflows/secret-scan.yml/badge.svg)](https://github.com/HewlettPackard/IMC-MCTS/actions/workflows/secret-scan.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Citation](https://img.shields.io/badge/citation-CFF-blue)](CITATION.cff)

A research simulator for mapping Monte Carlo tree search onto CAM selection, SRAM tree storage and crossbar neural evaluation, with an interactive Studio and scripts for reproducing retained results.

**Code version: 0.2.0rc1.** The workflow badges track public repository checks; the full replay with optional external inputs is documented separately. See [DISTRIBUTION.md](DISTRIBUTION.md) for the code and excluded-input scope.

## Quick start

Use Python 3.12, the locally tested version. From the source root:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
make install
make test
imc-mcts --help
```

The default install is CPU-only and requires NumPy. `make test` runs the self-contained public release suite; it does not certify the full simulator replay.

## Run the simulator and Studio

Trained weights in NPZ, PKL and BIN formats, supplied hardware evidence and selected licensed validation inputs are **not bundled**. Obtain an approved artifact packet from the project maintainers, then install its verified contents into a new local store:

```sh
imc-mcts artifacts install --archive /path/to/approved-artifacts.tar.gz --output /path/to/artifact-store
imc-mcts run --artifacts /path/to/artifact-store --output runs/hero
imc-mcts studio --artifacts /path/to/artifact-store --output runs/studio --port 4784
```

The excluded input packet is separate from this code update; no public artifact download is offered. Each output directory must be new. Visit <http://127.0.0.1:4784/> for Studio; stop it with Ctrl-C. Runtime files are copied into a writable workspace, leaving the installation untouched.

The default is an empty **9×9 board, Go-strong weights, seed 0 and 5,000 iterations per move**. Its retained reference is **55.186986 ms modeled latency and 3.703696 mJ per move**. Python execution time is separate. Trained models support 9×9; other boards use `--model random_diagnostic`. Studio exposes per-run component values and service assumptions.

## Reproduce results

The source artifact includes frozen data and figure scripts. Plotting dependencies are optional:

```sh
python -m pip install ".[paper,render]"
make figures
make test-full ARTIFACTS=/path/to/artifact-store
python -B reproduce.py all --artifacts /path/to/artifact-store --jobs 2 --verify-render
```

`make test-full` runs the native regression suite and fails if required artifacts are absent. Figure replotting uses retained data and does not require the external packet. See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for exact configurations, provenance and limits, and [VALIDATION.md](VALIDATION.md) for observed checks.

## File map

| Path | Contents |
| --- | --- |
| `source/` | Simulator, Studio, tests and public runtime resources |
| `configs/` | Frozen primary and scaling configurations |
| `data/`, `figures/` | Reference ledgers, plot inputs and scripts |
| `reproduce.py` | Source-artifact verification and replay commands |
| `release_tests/` | Self-contained public release tests |
| `MANIFEST.json` | Bundled file identities |

## Scope and contributing

Results estimate a preloaded core with 16 UCB scorers, 32 ADCs, 2 MiB SRAM and an assumed 500 MHz clock. Host rules, chip I/O and weight programming are excluded. ADC standby and several component costs are assumptions; diagnostic scaling does not establish playing strength.

Figure 3d remains excluded. Figure 4a supports archived-data replotting only. Original code is MIT-licensed; third-party terms are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Read [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) and [SECURITY.md](SECURITY.md) before contributing or reporting a vulnerability.
