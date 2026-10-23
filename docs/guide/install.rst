Installation
============

Install IMC-MCTS from its `public source repository
<https://github.com/HewlettPackard/IMC-MCTS>`_. The current code version is
``0.2.0rc1``.

Requirements
------------

* Python 3.11 or later. Python 3.12 is the locally tested version.
* Git and a terminal.
* A browser for Studio.

The default installation is CPU-only and uses NumPy. Use a virtual environment
to keep its dependencies separate from other projects.

Install from source
-------------------

macOS / Linux
~~~~~~~~~~~~~

.. code-block:: bash

   git clone https://github.com/HewlettPackard/IMC-MCTS.git
   cd IMC-MCTS
   python3.12 -m venv .venv
   source .venv/bin/activate
   python -m pip install -e ".[test]"

If your Python executable has another name, use it to create the environment.

Windows PowerShell
~~~~~~~~~~~~~~~~~~

.. code-block:: powershell

   git clone https://github.com/HewlettPackard/IMC-MCTS.git
   cd IMC-MCTS
   py -3.12 -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install -e ".[test]"

These commands use the standard Windows Python launcher. The recorded release
validation used Python 3.12 on macOS; native Windows runtime validation is not
claimed.

Check the installation
----------------------

With the environment active, check the command-line help:

.. code-block:: console

   imc-mcts --help

From the repository root, run the self-contained public release tests:

.. code-block:: console

   python -B -m unittest discover -s release_tests -v

Help and public tests work without the external artifact packet. They are
separate from full simulator replay.

Runtime artifacts
-----------------

The public repository includes code, configurations, retained data and figure
scripts. It excludes trained checkpoints, supplied hardware inputs and selected
licensed validation inputs. Simulator and Studio execution require these inputs
in a separately approved local artifact packet.

Obtain the packet from the maintainers, then install it into a **new** directory:

.. code-block:: console

   imc-mcts artifacts install --archive /path/to/approved-artifacts.tar.gz --output /path/to/artifact-store

Replace both example paths with your local paths. The installer verifies the
packet contents. No public artifact download is currently provided; installation
does not grant redistribution permission.

See `DISTRIBUTION.md
<https://github.com/HewlettPackard/IMC-MCTS/blob/main/DISTRIBUTION.md>`_ for the
excluded-input scope and `CITATION.cff
<https://github.com/HewlettPackard/IMC-MCTS/blob/main/CITATION.cff>`_ for the
maintainer contact. Continue to :doc:`usage` after installation.
