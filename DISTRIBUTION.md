# Distribution scope and optional inputs

This public code update excludes trained weights and the optional raw inputs listed below. The project owner confirms that the original repository security clearance is complete.

Original project code remains MIT. CC-BY-4.0 baseline attribution is preserved. Immutable historical source files may use adjacent SPDX .license sidecars so their exact source-hash gates remain intact. No historical synthesis manifest or source checksum is silently rewritten.

The public source and wheel exclude 34 raw inputs: 16 standalone model files (seven NPZ, seven PKL and two BIN), one model-containing historical fixture archive, one supplied workbook, two mapped netlists and 14 NeuroSim C++/header files. For those inputs, the public package contains names, sizes and checksums. A separately supplied local packet can be installed explicitly with `imc-mcts artifacts install --archive FILE --output NEW_STORE`; numerical runs then require `--artifacts NEW_STORE`. The installer rejects mismatched, incomplete, extra, duplicate, linked and unsafe members. No network download occurs.

Keep the private input packet and populated artifact store out of the public repository. Their exclusion does not require reopening the existing code repository's clearance. Sharing any excluded model, supplied hardware input or separately licensed NeuroSim source later requires a separate decision under its applicable terms. See [APPROVALS.md](APPROVALS.md) for the clearance record and scope.

Figure 3d remains excluded. Figure 4a is an archived-data replot only. The retained table extracts and figure inputs are reproduction evidence, not a compilation or replacement of current manuscript PDFs.
