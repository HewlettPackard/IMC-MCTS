# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

SHELL := /bin/bash
PYTHON ?= python3

.PHONY: install install-test test check paper sim cross-domain bench-cpu bench tour clean

install:
	$(PYTHON) -m pip install -e .

install-test:
	$(PYTHON) -m pip install -e ".[test]"

install-paper:
	$(PYTHON) -m pip install -e ".[paper]"

install-bench-cpu:
	$(PYTHON) -m pip install -e ".[benchmark-cpu]"

install-train:
	$(PYTHON) -m pip install -e ".[train]"

install-gpu:
	$(PYTHON) -m pip install -e ".[gpu]"

test:
	$(PYTHON) -m unittest discover -s tests -v

check:
	$(PYTHON) -m compileall -q core generalizability py_sst_cpp tournament paper
	$(MAKE) test

# Regenerate paper figures after locally reproducing paper/results/.
paper:
	@for f in paper/figure/plot_*.py; do echo "=> $$f"; MPLBACKEND=Agg $(PYTHON) "$$f"; done

# Run one event-driven hardware simulation per supported board size.
sim:
	@for f in core/simulator/runs/run_*x*_hardware_metrics.py; do echo "=> $$f"; $(PYTHON) "$$f"; done

cross-domain:
	$(PYTHON) generalizability/sweeps/run_cross_domain.py

bench-cpu:
	$(MAKE) -C cpu-gpu-benchmarking cpu-trad cpu-nn

# Requires nvcc and an NVIDIA GPU compatible with the configured CUDA target.
bench:
	$(MAKE) -C cpu-gpu-benchmarking all

# Requires external engines and the compiled IMC-MCTS shared library.
tour:
	cd tournament/go_compiled && $(PYTHON) tournament_main.py

clean:
	$(MAKE) -C cpu-gpu-benchmarking clean
