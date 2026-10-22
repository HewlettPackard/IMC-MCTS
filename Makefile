# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

PYTHON ?= python3
ARTIFACTS ?=

.PHONY: install test test-full tests require-artifacts verify hero scaling figures all studio

install:
	$(PYTHON) -m pip install -e ".[test]"

test:
	$(PYTHON) -B -m unittest discover -s release_tests -v

require-artifacts:
	@test -n "$(ARTIFACTS)" || { printf '%s\n' 'Set ARTIFACTS=/path/to/approved-artifact-store for this target.'; exit 2; }

test-full: require-artifacts
	$(PYTHON) -B reproduce.py tests --artifacts "$(ARTIFACTS)"

# Preserve the previous plural command as the full native-suite alias.
tests: test-full

verify:
	$(PYTHON) -B reproduce.py verify

hero scaling all studio: require-artifacts
	$(PYTHON) -B reproduce.py $@ --artifacts "$(ARTIFACTS)"

figures:
	$(PYTHON) -B reproduce.py figures --verify-render
