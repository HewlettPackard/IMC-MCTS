# Third-Party Notices

The root `LICENSE` applies only to original project material released under
the MIT License. Full license texts are collected in the `LICENSES/`
directory. The following components retain separate upstream terms.

## MCTS-NC CUDA baseline

Files under `cpu-gpu-benchmarking/benchmark_gpu_traditional/` are adapted from
Przemyslaw Klesk's MCTS-NC project:

- Upstream: https://github.com/pklesk/mcts_numba_cuda
- Upstream license: Creative Commons Attribution 4.0 International
- License: https://creativecommons.org/licenses/by/4.0/legalcode
- Changes: Go mechanics, benchmark integration, paths, and local formatting

Attribution and upstream links are retained in the adapted source files.

## Michi

The C tournament baseline (`tournament/go_compiled/engine/michi_c.c`) is an
original reimplementation inspired by the random-rollout design of Michi by
Petr Baudis. It contains no upstream Michi source.

- Reference: https://github.com/pasky/michi (MIT)

## External engines

Pachi, KataGo, and GNU Go are optional external programs and are not distributed
in this repository. Users must obtain them from their official projects and
comply with their licenses:

- Pachi: https://github.com/pasky/pachi, GPL-2.0
- KataGo: https://github.com/lightvector/KataGo, MIT
- GNU Go: https://www.gnu.org/software/gnugo/, GPL-3.0-or-later

Python dependencies are governed by the licenses published by their respective
package maintainers.

## Public SBOM scope

The default public Python package is intended to be SBOM'd from a CPU-only
installation of `imc-mcts` (optionally with `.[test]`). CUDA benchmarking
dependencies, external Go engines, and self-trained model artifacts are outside
that default SBOM scope and must be reviewed separately before distribution.
