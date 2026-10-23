# Third-Party Notices

The root `LICENSE` applies only to original project material released under
the MIT License. Full license texts are collected in the `LICENSES/`
directory. The following components retain separate upstream terms.

## MCTS-NC CUDA baseline

Files under `baselines/source_context/benchmark_gpu_traditional/` are adapted from
Przemyslaw Klesk's MCTS-NC project:

- Upstream: https://github.com/pklesk/mcts_numba_cuda
- Upstream license: Creative Commons Attribution 4.0 International
- License: https://creativecommons.org/licenses/by/4.0/legalcode
- Changes: Go mechanics, benchmark integration, paths, and local formatting

Attribution and upstream links are retained in the adapted source files.

## Michi

Michi by Petr Baudis is a design reference for the historical C tournament
baseline. Neither that baseline C file nor upstream Michi source is bundled
in this release.

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

## Optional inputs excluded from the public package

The public source and wheel exclude 34 raw inputs: seven NPZ, seven PKL and two BIN checkpoint files; the historical test-fixture archive (which embeds additional model weights); the supplied Super-T workbook; two historical mapped netlists; and 14 NeuroSim C++/header files. For these inputs, only a checksum manifest and an offline installer are included. The files remain in a separate local packet; no public download URL or redistribution permission is implied.

The excluded NeuroSim files retain their upstream Creative Commons Attribution-NonCommercial 4.0 notices, including the original Arizona State University / Shimeng Yu attribution. They are not relicensed under MIT. Review the intended use and obtain any necessary permission before distributing or using that optional code beyond its license terms. The license is described at https://creativecommons.org/licenses/by-nc/4.0/.

The project owner confirms that the original repository security clearance is complete. This code update keeps the raw inputs listed above excluded and does not reopen that clearance. Python dependency metadata, the project MIT license and technical tests do not grant separate rights to redistribute excluded supplied data or third-party inputs. The two attribution-context files recorded in LICENSE_EXCEPTIONS.json were already in the first public commit and their Python ASTs are unchanged; only SPDX comments differ. Existing individual-holder notes and upstream CC-BY-4.0 attribution remain preserved, without a new approval requirement.

## Python runtime dependencies

The default runtime and public test extra require NumPy only (BSD-3-Clause metadata; its wheel may contain separately licensed bundled components). The fresh SBOM inventories actual installed Python distributions; it does not replace wheel-level native-library or corporate license review. Plotting and PDF-render dependencies remain optional. Their licenses remain with their respective upstream projects.

## Documentation build and theme dependencies

The documentation uses Sphinx 9.1.0 and PyData Sphinx Theme 0.16.1 under their
BSD licenses. The theme bundles Bootstrap 5.3.3 (MIT) and Font Awesome Free 6.5.2
(CC-BY-4.0 for icons, SIL-OFL-1.1 for fonts and MIT for code). Complete matching
license texts are retained in docs/_static/licenses/ and in the published site.
Their generated attribution notices are preserved. These dependencies are
installed to build the documentation; they are not relicensed by the project.
