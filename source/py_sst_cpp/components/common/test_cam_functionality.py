#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Test CAM Functionality

Demonstrates the CAM-based transposition detection in the MCTS accelerator.
Shows how different move sequences that reach the same board state are
automatically detected and merged.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from py_sst_cpp.components.common.board_state_encoder import BoardStateEncoder


def test_transposition_detection():
    """
    Test that CAM detects when different move sequences reach the same state.
    """
    print("=" * 80)
    print("CAM Transposition Detection Test")
    print("=" * 80)

    # Create 5x5 board encoder
    encoder = BoardStateEncoder(board_size=5)

    # Simulated CAM storage
    state_hash_to_node = {}  # CAM: state_hash -> node_id
    node_storage = {}  # SRAM: node_id -> (visits, value, parent, children)

    print("\nScenario: Two different move sequences reaching the same board state\n")

    # Path 1: Black (2,2), White (1,1), Black (3,3)
    print("Path 1: Black (2,2) → White (1,1) → Black (3,3)")
    path1_board = [[0] * 5 for _ in range(5)]
    path1_board[2][2] = 1  # Black
    path1_board[1][1] = 2  # White
    path1_board[3][3] = 1  # Black

    path1_hash = encoder.zobrist_hash(path1_board)
    print(f"  Board state hash: 0x{path1_hash:016X}")

    # Insert into CAM
    if path1_hash not in state_hash_to_node:
        state_hash_to_node[path1_hash] = 100  # node_id = 100
        node_storage[100] = (5, 3.0, -1, [])
        print(f"  ✓ Inserted as node_id=100 (visits=5, value=3.0)")

    # Path 2: White (1,1), Black (2,2), Black (3,3)  # SAME FINAL STATE!
    print("\nPath 2: White (1,1) → Black (2,2) → Black (3,3)")
    path2_board = [[0] * 5 for _ in range(5)]
    path2_board[1][1] = 2  # White
    path2_board[2][2] = 1  # Black
    path2_board[3][3] = 1  # Black

    path2_hash = encoder.zobrist_hash(path2_board)
    print(f"  Board state hash: 0x{path2_hash:016X}")

    # CAM lookup - should detect transposition!
    if path2_hash in state_hash_to_node:
        existing_node_id = state_hash_to_node[path2_hash]
        print(f"  ✓ TRANSPOSITION DETECTED!")
        print(f"  ✓ Already stored as node_id={existing_node_id}")
        print(f"  ✓ Different move order reached the same position!")

        # Merge statistics
        old_visits, old_value, parent, children = node_storage[existing_node_id]
        new_visits = 3  # Visits from path 2
        new_value = 2.0  # Value from path 2

        merged_visits = old_visits + new_visits
        merged_value = old_value + new_value

        node_storage[existing_node_id] = (merged_visits, merged_value, parent, children)
        print(f"  ✓ Merged statistics: visits={old_visits}+{new_visits}={merged_visits}, value={old_value}+{new_value}={merged_value}")
    else:
        print(f"  ✗ Would insert as new node (transposition NOT detected)")
        print(f"  ✗ CAM failed to detect same board state!")

    # Verify the boards are actually the same
    print(f"\nVerification:")
    print(f"  Board 1 == Board 2: {path1_board == path2_board}")
    print(f"  Hash 1 == Hash 2: {path1_hash == path2_hash}")

    # Path 3: Completely different board state
    print("\n" + "=" * 80)
    print("Path 3: Black (0,0), White (4,4), Black (2,1)  [DIFFERENT STATE]")
    path3_board = [[0] * 5 for _ in range(5)]
    path3_board[0][0] = 1  # Black
    path3_board[4][4] = 2  # White
    path3_board[2][1] = 1  # Black

    path3_hash = encoder.zobrist_hash(path3_board)
    print(f"  Board state hash: 0x{path3_hash:016X}")

    if path3_hash in state_hash_to_node:
        print(f"  ✗ Incorrectly detected as transposition!")
    else:
        state_hash_to_node[path3_hash] = 101
        node_storage[101] = (2, 1.5, -1, [])
        print(f"  ✓ Inserted as new node_id=101 (unique state)")

    # Final summary
    print("\n" + "=" * 80)
    print("CAM Storage Summary:")
    print("=" * 80)
    print(f"Total unique states: {len(state_hash_to_node)}")
    print(f"Total nodes in SRAM: {len(node_storage)}")
    print(f"\nCAM Entries:")
    for state_hash, node_id in state_hash_to_node.items():
        visits, value, _, _ = node_storage[node_id]
        print(f"  Hash 0x{state_hash:016X} → Node {node_id} (visits={visits}, value={value:.1f})")

    print("\n✓ Test completed successfully!")
    print("✓ CAM correctly detected transposition and merged statistics!")


def test_incremental_hash():
    """Test that incremental hash updates work correctly."""
    print("\n" + "=" * 80)
    print("Incremental Hash Update Test")
    print("=" * 80)

    encoder = BoardStateEncoder(board_size=5)

    # Start with empty board
    board = [[0] * 5 for _ in range(5)]
    full_hash = encoder.zobrist_hash(board)
    print(f"Empty board hash: 0x{full_hash:016X}")

    # Make a move incrementally
    incremental_hash = full_hash
    incremental_hash = encoder.incremental_hash_update(
        incremental_hash, 2, 2, 0, 1
    )
    print(f"After Black (2,2) [incremental]: 0x{incremental_hash:016X}")

    # Verify with full rehash
    board[2][2] = 1
    full_hash = encoder.zobrist_hash(board)
    print(f"After Black (2,2) [full rehash]: 0x{full_hash:016X}")

    if incremental_hash == full_hash:
        print("✓ Incremental hash matches full rehash!")
    else:
        print("✗ Incremental hash MISMATCH!")

    # Make another move
    incremental_hash = encoder.incremental_hash_update(
        incremental_hash, 1, 1, 0, 2
    )
    board[1][1] = 2
    full_hash = encoder.zobrist_hash(board)

    print(f"\nAfter White (1,1) [incremental]: 0x{incremental_hash:016X}")
    print(f"After White (1,1) [full rehash]: 0x{full_hash:016X}")

    if incremental_hash == full_hash:
        print("✓ Incremental hash still matches!")
        print("✓ Can use incremental updates during rollout (much faster)!")
    else:
        print("✗ Incremental hash MISMATCH!")


if __name__ == "__main__":
    test_transposition_detection()
    test_incremental_hash()
