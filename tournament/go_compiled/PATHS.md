# Path config

Tournament entry points import paths from `paths.py`. Commands available on
`PATH` are detected automatically; environment variables override them:

```sh
export GNUGO_BIN=path/to/gnugo
export PACHI_BIN=path/to/pachi
export KATAGO_BIN=path/to/katago
export KATAGO_MODEL=path/to/model.bin.gz
export KATAGO_CFG=path/to/tournament.cfg
```

## Binaries you need to provide

These third-party artifacts are intentionally excluded:

- Pachi and KataGo executables and KataGo model files
- `tournament/go_compiled/engine/imc_mcts.so` and `michi_c.so`, built from `engine/*.c`
- GnuGo — install via package manager (`brew install gnugo` / `apt install gnugo`)

See `.env.example` for local override examples.
