# Contributing

Reproducibility reports, bug reports, and documentation corrections are
welcome through GitHub Issues.

## Before opening an issue

1. Use a fresh checkout and the installation steps in `README.md`.
2. Run `make check`.
3. Include the commit SHA, Python version, operating system, command, complete
   traceback, and the smallest input that reproduces the problem.
4. For numerical differences, include hardware details, random seeds, and the
   expected and observed values.

## Code contributions

The project may include materials that need separate review before public
release. Do not submit code or data that is confidential, employer-owned,
export-controlled, patent sensitive, or incompatible with the repository
license.

Contact the maintainer in a GitHub Issue or at
[tergel.molom-ochir@hpe.com](mailto:tergel.molom-ochir@hpe.com) before preparing
a substantial pull request. By submitting a contribution, you represent that
you have the right to submit it and agree that it may be distributed under the
repository's current or future project license.

Pull requests should remain focused, preserve documented behavior, add tests
for behavioral changes, and pass `make check`.
