# Contributing

Contributions should make the simulator easier to understand, run or verify while preserving the distinction between measured, modeled and assumed quantities. Follow the [code of conduct](CODE_OF_CONDUCT.md).

## Set up and test

Use a virtual environment with Python 3.12, then run:

```sh
make install
make test
```

The public suite covers release interfaces, artifact handling and packaging policies without private inputs. It is distinct from the full native simulator suite. With an approved external artifact store:

```sh
make test-full ARTIFACTS=/path/to/artifact-store
```

For changes affecting numerical results, also run the relevant hero/scaling replay described in [REPRODUCIBILITY.md](REPRODUCIBILITY.md). Preserve seeds, configuration, units, accounting boundaries and source identities in the evidence. Never replace a failed result with a passing label or remove an integrity check to make a test pass.

## Propose a change

Open an issue for a substantial design change before implementing it. Keep pull requests focused and explain the problem, resulting behavior, tests run and limitations. Include a small regression test for a bug when it protects meaningful behavior. Avoid unrelated formatting or generated-output changes.

Do not commit credentials, local environments, personal configuration, private weights or supplied artifacts awaiting distribution approval. Keep external inputs outside the source tree and use the checksum-checked artifact installer. Do not attach restricted material to a public issue or pull request.

Original contributions use the repository's MIT license. Preserve existing attribution and third-party license terms; flag uncertain ownership or distribution rights for maintainer review. Use the established SPDX headers on original project source. Do not relabel third-party code as project-owned.

## Architecture and documentation

The Studio's current profile, architecture diagram, resource values, timing, energy and exports must agree. Keep old results labeled with their original profiles. Update relevant documentation when changing a public command, default or model assumption.

`make figures` replots retained data with optional paper/render dependencies. It does not train models or rerun CPU/GPU benchmarks. Figure 3d remains outside this release's supported targets.

GitHub CI runs the public release checks. Passing that workflow does not establish the full private-artifact replay or physical hardware accuracy. Include the full checks separately when they are relevant to a change.
