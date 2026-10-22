# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Instantiate the 13 game models used by the shared MCTS experiments."""

from .go import Go
from .hex_game import Hex
from .gomoku import Gomoku
from .havannah import Havannah
from .othello import Othello
from .connect_four import ConnectFour
from .pente import Pente
from .breakthrough import Breakthrough
from .protein_folding import ProteinFolding
from .nonograms import Nonograms
from .frozen_lake import FrozenLake
from .minigrid import MiniGrid
from .minesweeper import Minesweeper

GAME_REGISTRY = {
    "go": Go(),
    "hex": Hex(),
    "gomoku": Gomoku(),
    "havannah": Havannah(),
    "othello": Othello(),
    "connect_four": ConnectFour(),
    "pente": Pente(),
    "breakthrough": Breakthrough(),
    "protein_folding": ProteinFolding(),
    "nonograms": Nonograms(),
    "frozen_lake": FrozenLake(),
    "minigrid": MiniGrid(),
    "minesweeper": Minesweeper(),
}

# Physical play-area size used by hardware estimation.
APP_BOARD_SIZES = {
    "go": 9, "hex": 11, "gomoku": 15, "havannah": 15,
    "pente": 19, "othello": 8, "connect_four": 8,
    "breakthrough": 8, "protein_folding": 13, "nonograms": 9,
    "frozen_lake": 8, "minigrid": 8, "minesweeper": 9,
}

# MCTS iterations scaled by initial branching factor, normalized to Go=200.
GAME_ITERATIONS = {
    "go": 200, "hex": 300, "gomoku": 550, "havannah": 400,
    "othello": 50, "connect_four": 50, "pente": 900,
    "breakthrough": 50, "protein_folding": 50, "nonograms": 400,
    "frozen_lake": 50, "minigrid": 50, "minesweeper": 200,
}
