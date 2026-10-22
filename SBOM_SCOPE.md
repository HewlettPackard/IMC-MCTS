<!-- SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP -->
<!-- SPDX-License-Identifier: MIT -->
# SBOM scope and generation

[SBOM.cdx.json](SBOM.cdx.json) is a schema-validated CycloneDX 1.6 inventory of the **minimal Python review environment** for IMC-MCTS 0.2.0rc1. It is not an institutional approval or a full inventory of every source/data file.

## Observed review scope

A fresh Python 3.12.11 virtual environment was created without system site packages. A disposable source copy was installed with `python -m pip install -e ".[test]"`; the public source tree was not modified by that editable installation.

| Installed distribution | Version | License recorded by the generator |
| --- | --- | --- |
| imc-mcts | 0.2.0rc1 | MIT |
| numpy | 2.3.5 | BSD License classifier from installed metadata |
| pip | 25.0.1 | MIT |

The SBOM also contains an application root generated from `pyproject.toml`; its separate installed-distribution component has the same project name/version. This is the generator's application-versus-installed-package representation, not a second installation.

The `test` extra uses standard-library `unittest` and adds no distributions. There are no GPU, CUDA, NVIDIA, model-training or plotting packages in this scope. The environment was created on macOS arm64; it does not inventory dependencies resolved on every other platform.

## Method and transformation

CycloneDX Python 7.5.0 (`cyclonedx-bom==7.5.0`) ran from a **separate generator environment**, using:

```sh
/path/to/generator/bin/cyclonedx-py environment /path/to/review/bin/python \
  --pyproject pyproject.toml --spec-version 1.6 --output-format JSON \
  --validate --output-reproducible --output-file SBOM.generated.cdx.json
```

The output was validated by the generator. One machine-local `file://` origin reference identifying the disposable editable checkout was omitted from the public copy. No package, version, dependency or license was added, replaced or removed. No substitute URL was invented. The public JSON was validated again with the official CycloneDX Python library's strict 1.6 schema validator. Raw output, the exact command, environment freeze and transformation receipt are preserved in the external local validation record.

The full `pyproject.toml` snapshot used for generation had SHA-256 `2b602eddaabcbd15d86b70ece3fb3fe2d7fb23f11ea926a416cf4f46218363af`. Later packaging exclusions remove additional checkpoint formats without changing the `[project]` metadata or dependencies. The reviewed `[project]` fingerprint is `aff8c0ca65e13d210cbfa80632a58b771486accd14530b4a7ba8c8ef061acf70` (SHA-256 of its UTF-8 JSON with sorted keys and compact separators); current project metadata matches that snapshot. The existing SBOM therefore remains applicable without regenerating it for file-selection changes. The final release manifest binds the current packaging and SBOM bytes; the SBOM does not try to contain its own manifest hash.

## Limits and approval status

This is Python-distribution metadata, including the review installer `pip`. It does not exhaustively identify native libraries bundled inside dependency wheels. Vendored source, benchmark context and their licenses remain documented separately in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Optional private models, supplied hardware evidence and separately licensed reference inputs are excluded from the public package and from this installation scope; see [DISTRIBUTION.md](DISTRIBUTION.md).

License names are retained as reported by the generator. In particular, NumPy's legacy BSD classifier was not silently converted into a more specific SPDX expression. The project owner confirms that the original repository security clearance is complete; this dependency inventory does not reopen it. Excluded models and third-party inputs retain their separate terms, and SBOM creation does not grant rights to redistribute them.

Primary tool documentation: [CycloneDX Python usage](https://github.com/CycloneDX/cyclonedx-python/blob/main/docs/usage.rst), [pinned generator release](https://pypi.org/project/cyclonedx-bom/7.5.0/).
