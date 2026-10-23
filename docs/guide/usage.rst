Basic usage
===========

Follow :doc:`install` first and keep the virtual environment active. Simulator
and Studio commands require the verified artifact store described there.

Run a search
------------

.. code-block:: console

   imc-mcts run --artifacts /path/to/artifact-store --output runs/first-search

The default reference uses an empty **9×9 board**, Go-strong weights, seed 0 and
**5,000 iterations per move**. Each output directory must be new, so choose a
different name for subsequent runs.

Inspect the available search options with:

.. code-block:: console

   imc-mcts run --help

The trained evaluators support 9×9. Other supported board sizes use the
``random_diagnostic`` model setting; those runs test execution and accounting,
not playing strength.

Open Studio
-----------

Start the browser interface in its own new output directory:

.. code-block:: console

   imc-mcts studio --artifacts /path/to/artifact-store --output runs/studio --port 4784

Keep the terminal running and open http://127.0.0.1:4784/ in a browser on the
same machine. Stop Studio with **Ctrl+C**. If the port is already occupied,
choose another with ``--port 4785`` and use the corresponding browser address.

Studio exposes dataflow, scheduled services and component assumptions. Supported
per-run component values and service durations can be changed to explore
modeling scenarios. Runtime files and saved results use the writable workspace,
leaving the installation unchanged.

.. note::

   Studio requires the separately supplied artifact packet. The local address
   above is not a publicly hosted service.

Replot retained figures
-----------------------

Figure replotting uses public retained data and does not require the excluded
checkpoints. From the source repository root, install the optional plotting and
rendering dependencies:

.. code-block:: console

   python -m pip install ".[paper,render]"
   python -B reproduce.py figures --verify-render

This workflow runs the supported figure scripts, not training, tournaments or
new CPU/GPU benchmarks. The `reproducibility guide
<https://github.com/HewlettPackard/IMC-MCTS/blob/main/REPRODUCIBILITY.md>`_
describes the retained inputs, configurations and replay commands.

Interpret the outputs
---------------------

Hardware latency, energy, power and area are architectural estimates. Python
execution time is a separate host measurement. The preloaded-core boundary
excludes host rule processing, chip I/O and weight programming; changing
component assumptions does not constitute physical characterization.

See `VALIDATION.md
<https://github.com/HewlettPackard/IMC-MCTS/blob/main/VALIDATION.md>`_ for the
observed checks and their limits. For a software problem, open a `GitHub issue
<https://github.com/HewlettPackard/IMC-MCTS/issues>`_ with the version, command and
error message. Do not attach private inputs or trained checkpoints.
