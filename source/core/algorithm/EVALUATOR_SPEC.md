# Python evaluator specification, version 1

The event and functional evaluators require an explicit specification when
loading a checkpoint. The specification is a plain dictionary, suitable for
storage as JSON. It identifies a chosen interpretation of one exact file.
It does not establish that file's training provenance or playing strength.

```json
{
  "schema_version": 1,
  "checkpoint_sha256": "ff6d96aec78cf4447fb093d6e9fcc80dc9532dcd4ccd7e0840e6ce65dd7fd5eb",
  "board_size": 9,
  "input_size": 162,
  "hidden_size": 96,
  "output_size": 3,
  "input_encoding": "interleaved_black_white",
  "turn_indicator": false,
  "weight_transform": "centered_50",
  "output_order": ["white", "draw", "black"],
  "value_perspective": "black",
  "arithmetic_dtype": "float64"
}
```

This concrete example identifies the archived
`models/weights_9x9/model_at_66.00percent.pkl` inspected in Round 2. It declares
the current trainer's centered computation for diagnostic comparisons.
The saved percentage is not a newly validated accuracy. This file is not a
canonical model for the paper, the CPU/GPU benchmarks, or the tournament engine.

Version 1 describes two bias-free matrix layers, ReLU after the first layer,
then softmax. Board cells are `1` for Black, `-1` for White, and `0` for empty.
Rows are flattened in row-major order, with `[Black, White]` for each cell.
There is no turn input or player-relative channel swap. The returned value is
`P(Black) + 0.5 * P(draw)`, in [0, 1].

| Weight transform | Numerical matrix used |
| --- | --- |
| `identity` | Stored values, unchanged except conversion to float64 |
| `centered_50` | `(G - 50) / 50`, with stored conductances required in [0, 100] |

Choose the transform from the intended inference contract. Do not infer it
from a filename, saved accuracy, matrix range, or a newer checkpoint.
Centering is a numerical convention here, without a validated physical
signed-weight implementation. The functional evaluator rejects `centered_50`
with `adc_bits > 0` because its existing ADC implementation is unsigned.

## Loading

```python
import json
from pathlib import Path

from core.architecture.hardware_functional_model import CrossbarNNFunctional

spec = json.loads(Path("chosen_model_spec.json").read_text())
nn = CrossbarNNFunctional(
    "chosen_model.pkl", board_size=9, evaluator_spec=spec
)
value, probabilities = nn.forward(board)
print(nn.evaluator_info)
```

An existing event component uses
`rollout.load_weights(weights_path, evaluator_spec=spec)`. The specification's
hidden size must match the component's configured size. For example, a 9x9
event component rejects a 32-hidden model because it is configured for 96.
The standalone functional evaluator can use an explicitly specified 32-hidden
model, because it has no event timing configuration to silently invalidate.

For a complete event run, the shared factory accepts the same pair:

```python
from core.simulator.runs.run_5x5_hardware_metrics import create_simulation
from py_sst_cpp.components.performance_config import PerformanceLevel

simulation, system = create_simulation(
    9, PerformanceLevel.MEDIUM,
    weights_file="chosen_model.pkl", evaluator_spec=spec,
)
```

The factory already serves multiple board sizes despite its historical module
name. The 5x5 command-line entry point also accepts `--weights FILE` and
`--evaluator-spec JSON_FILE`. Existing per-board wrappers continue to run their
default diagnostic configuration; they do not gain these CLI options in this round.

## Failure and result semantics

- Missing or unsupported specifications fail before checkpoint decoding.
- The SHA-256 is checked against the exact bytes being decoded. Use trusted
  local pickle artifacts; a hash pins identity but does not make pickle safe.
- Both layer shapes, real finite values, and any saved dimensional/contract
  metadata must agree. A failed event load preserves the previous evaluator.
- Specified checkpoints must load successfully. The shared runner does not
  select by filename or fall back to random weights after a loading error.
- `evaluator_info.mode == "checkpoint"` records a loaded file, without asserting
  validated training or accuracy. The legacy `_weights_trained` flag means that
  a compatible checkpoint was loaded.
- Runs without a checkpoint report `random_diagnostic`, including input shape,
  encoding, and random matrix hashes. Analytical API results report
  `not_executed`. API result records include `hardware_mapping: unverified`.

Existing Python callers that supplied only a checkpoint path must now supply
the specification too. The functional MCTS and player wrappers forward this
argument. Old hardcoded tournament demos need their own reviewed specification;
they cannot select one automatically from an accuracy label. C++/CUDA benchmark
scripts and results remain unchanged under the user's [repair scope](../../SCOPE.md).
This specification applies to the repaired architecture-simulator Python surface;
it is not a requirement to migrate or rerun the CPU/GPU benchmarks.
