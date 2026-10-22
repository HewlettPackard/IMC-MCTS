# Studio test workspace

This directory is retained in installed wheels so native Studio regression tests
can create temporary run directories beneath it. The tests remove those temporary
directories when they finish. Launch the interactive Studio with a separate new
workspace using `imc-mcts studio --output NEW_DIR`.
