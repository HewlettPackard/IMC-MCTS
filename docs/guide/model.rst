Model and assumptions
=====================

IMC-MCTS is an architectural service model. It records the work performed during
a search and schedules that work against finite hardware resources.

Reference configuration
-----------------------

The default reference is an empty **9×9 Go board**, Go-strong weights, seed 0 and
**5,000 iterations per move**. It has 16 UCB scorers, 32 shared ADCs and 2 MiB of
installed SRAM, at an assumed 500 MHz clock.

The trained evaluators support 9×9. Other board sizes use diagnostic weights;
those searches assess modeled execution and capacity rather than playing strength.

Search phases
-------------

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Phase
     - Modeled services
   * - Selection
     - CAM cache, SRAM access, candidate buffering and UCB arithmetic
   * - Expansion
     - One-child allocation, action bookkeeping and tree-memory updates
   * - Neural evaluation
     - RRAM array operations, shared ADCs, result buffering and digital readout
   * - Backpropagation
     - Statistics updates along the selected path in SRAM

Game rules and legal actions are supplied by the host. Expansion and
backpropagation share a digital update controller.

Reported quantities
-------------------

* **Latency per move:** scheduled cycles divided by the assumed clock frequency.
  Python execution time is a separate quantity.
* **Energy per move:** modeled component energy over the complete search used to
  select one move, rather than an entire game.
* **Energy per iteration within a move:** search energy divided by the completed
  iteration count. This is a search average, not the energy of every iteration.
* **Average power:** search energy divided by search duration.
* **Area:** total area of installed components, including memory that a particular
  search may not occupy.

Changing component assumptions
------------------------------

Studio exposes supported component areas, dynamic event energies, standby power
and service durations. Selected values and source identities are retained with
run configurations and exports.

An edited value defines a modeling scenario. It is not a new physical
characterization. The default ADC standby allowance is 25% of published active
power during nonconverting intervals, rather than a measured standby value.

Scope of the estimates
----------------------

The model describes a preloaded core. Host game-rule processing and history,
chip I/O and weight programming are outside its cost boundary. Functional and
scheduling checks do not establish integrated RTL equivalence, analogue accuracy
or full-core physical timing closure.

See the repository's
`validation record <https://github.com/HewlettPackard/IMC-MCTS/blob/main/VALIDATION.md>`_
and `reproducibility guide <https://github.com/HewlettPackard/IMC-MCTS/blob/main/REPRODUCIBILITY.md>`_
for the recorded checks and their limits.
