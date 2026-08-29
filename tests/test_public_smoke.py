# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Fast public-release smoke tests for the supported Python surface."""

import unittest

from core.architecture.accelerator_api import estimate, expected_path_depth
from generalizability.games.go import Go
from py_sst_cpp.components.common.board_state_encoder import BoardStateEncoder


class BoardStateEncoderTests(unittest.TestCase):
    def test_bit_encoding_round_trip(self):
        encoder = BoardStateEncoder(board_size=3)
        board = [
            [1, 0, 2],
            [0, 1, 0],
            [2, 0, 1],
        ]

        encoded = encoder.encode_to_bits(board)

        self.assertEqual(encoder.decode_from_bits(encoded), board)

    def test_incremental_hash_matches_full_hash(self):
        encoder = BoardStateEncoder(board_size=3)
        board = [[0] * 3 for _ in range(3)]
        board_hash = encoder.zobrist_hash(board)

        board_hash = encoder.incremental_hash_update(board_hash, 1, 1, 0, 1)
        board[1][1] = 1

        self.assertEqual(board_hash, encoder.zobrist_hash(board))


class AcceleratorTests(unittest.TestCase):
    def test_analytical_estimate_is_positive(self):
        result = estimate(board_size=3, play_strength="low", mode="analytical")

        self.assertEqual(result.iterations, 75)
        self.assertGreater(result.energy_uj, 0.0)
        self.assertGreater(result.area_mm2, 0.0)
        self.assertGreater(result.latency_us, 0.0)

    def test_expected_depth_grows_with_iterations(self):
        shallow = expected_path_depth(board_size=9, iterations=10)
        deep = expected_path_depth(board_size=9, iterations=1000)

        self.assertGreater(deep, shallow)


class GoTests(unittest.TestCase):
    def test_move_updates_board_without_mutating_input(self):
        game = Go()
        board = game.initial_state()

        updated = game.apply_move(board, (0, 0), player=1)

        self.assertEqual(board[0, 0], 0)
        self.assertEqual(updated[0, 0], 1)
        self.assertIn((-1, -1), game.get_legal_moves(updated, player=2))


if __name__ == "__main__":
    unittest.main()
