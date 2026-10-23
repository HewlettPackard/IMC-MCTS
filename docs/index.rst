IMC-MCTS
========

.. rst-class:: version-note

   Documentation for version |release|

.. rst-class:: intro

   A research simulator for Monte Carlo tree search mapped to in-memory computing.

IMC-MCTS models CAM-assisted selection, child allocation, crossbar neural
evaluation and SRAM statistics updates. The interactive Studio lets you inspect
execution schedules, memory use and component assumptions in a browser.

Getting started
---------------

1. :doc:`Install the software <guide/install>` and check the command-line interface.
2. :doc:`Run a search or open Studio <guide/usage>` with approved runtime inputs.
3. :doc:`Follow the visual tutorial <guide/tutorial>` to connect the search to the hardware.
4. :doc:`Understand the model <guide/model>` and the quantities it reports.

What is included?
-----------------

The public repository contains the simulator and Studio source, reference
configurations, retained result data, tests and figure-generation scripts.

.. note::

   Trained weights and selected restricted hardware or validation inputs are
   supplied separately. Installing the public code does not install these inputs.
   The :doc:`installation guide <guide/install>` explains the artifact requirement.

Source and research
-------------------

* `Source code and issues <https://github.com/HewlettPackard/IMC-MCTS>`_
* `Reproducibility instructions <https://github.com/HewlettPackard/IMC-MCTS/blob/main/REPRODUCIBILITY.md>`_
* `Accompanying preprint <https://arxiv.org/abs/2607.22869>`_
* `Citation metadata <https://github.com/HewlettPackard/IMC-MCTS/blob/main/CITATION.cff>`_

The repository documents the current software and its verification scope. The
preprint introduces the research approach. Simulator outputs are architectural
and engineering estimates, rather than measurements of a fabricated processor.

.. toctree::
   :maxdepth: 1
   :caption: User guide
   :hidden:

   Overview <self>
   guide/install
   guide/usage
   guide/tutorial
   guide/model
