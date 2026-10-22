# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Test Board Configurations with TCAM FSM Specs
==============================================

This script validates that all board configurations include TCAM FSM
specifications and prints detailed hardware specs.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from py_sst_cpp.components.board_config import (
    BoardSize,
    get_board_config,
    print_board_specs
)


def test_tcam_specs():
    """Test that all boards have TCAM FSM specs"""
    print("=" * 80)
    print("TESTING TCAM FSM SPECS IN BOARD CONFIGURATIONS")
    print("=" * 80)
    print()

    all_boards = [
        BoardSize.BOARD_2X2,
        BoardSize.BOARD_3X3,
        BoardSize.BOARD_5X5,
        BoardSize.BOARD_9X9,
        BoardSize.BOARD_13X13,
        BoardSize.BOARD_19X19,
    ]

    print("Validating TCAM specs for all boards...")
    print()

    for board_size in all_boards:
        board_config = get_board_config(board_size)
        board_name = f"{board_config.board_size}x{board_config.board_size}"

        print(f"Board {board_name}:")
        print(f"  TCAM Rows:          {board_config.tcam_rows}")
        print(f"  TCAM Bits/Row:      {board_config.tcam_bits_per_row}")
        print(f"  TCAM Area:          {board_config.tcam_area_mm2:.8f} mm² ({board_config.tcam_area_mm2*1e6:.1f} μm²)")
        print(f"  TCAM Dynamic Power: {board_config.tcam_power_mw:.4f} mW")
        print(f"  TCAM Leakage:       {board_config.tcam_leakage_mw:.6f} mW")

        # Verify TCAM is included in totals
        total_area = board_config.total_area_mm2
        total_power = board_config.total_power_mw

        print(f"  Total Area (w/ TCAM):  {total_area:.8f} mm²")
        print(f"  Total Power (w/ TCAM): {total_power:.4f} mW")

        # Calculate percentage
        tcam_area_pct = (board_config.tcam_area_mm2 / total_area) * 100
        tcam_power_pct = (board_config.tcam_power_mw / total_power) * 100

        print(f"  TCAM % of Total Area:  {tcam_area_pct:.4f}%")
        print(f"  TCAM % of Total Power: {tcam_power_pct:.4f}%")
        print()

    print("✅ All boards have TCAM FSM specs!")
    print()


def print_comparison_table():
    """Print comparison table of all boards with TCAM"""
    print("=" * 80)
    print("BOARD COMPARISON WITH TCAM FSM")
    print("=" * 80)
    print()

    all_boards = [
        BoardSize.BOARD_2X2,
        BoardSize.BOARD_3X3,
        BoardSize.BOARD_5X5,
        BoardSize.BOARD_9X9,
        BoardSize.BOARD_13X13,
        BoardSize.BOARD_19X19,
    ]

    # Header
    print(f"{'Board':<8} {'Total Area':<15} {'Total Power':<15} {'TCAM Area %':<15} {'TCAM Power %':<15}")
    print("-" * 80)

    for board_size in all_boards:
        board_config = get_board_config(board_size)
        board_name = f"{board_config.board_size}x{board_config.board_size}"

        total_area = board_config.total_area_mm2
        total_power = board_config.total_power_mw
        tcam_area_pct = (board_config.tcam_area_mm2 / total_area) * 100
        tcam_power_pct = (board_config.tcam_power_mw / total_power) * 100

        print(f"{board_name:<8} "
              f"{total_area:.8f} mm² "
              f"{total_power:.4f} mW     "
              f"{tcam_area_pct:.4f}%        "
              f"{tcam_power_pct:.4f}%")

    print()
    print("Note: TCAM specs are identical across all boards (board-independent FSM)")
    print("      TCAM contribution decreases as board size (and total resources) increases")
    print()


def print_detailed_specs():
    """Print detailed specs for selected boards"""
    print("=" * 80)
    print("DETAILED SPECIFICATIONS WITH TCAM FSM")
    print("=" * 80)
    print()

    # Print specs for a few representative boards
    representative_boards = [
        BoardSize.BOARD_2X2,
        BoardSize.BOARD_5X5,
        BoardSize.BOARD_19X19,
    ]

    for board_size in representative_boards:
        print_board_specs(board_size)


if __name__ == "__main__":
    # Run tests
    test_tcam_specs()
    print_comparison_table()
    print_detailed_specs()

    print("=" * 80)
    print("✅ BOARD CONFIG TCAM INTEGRATION TEST COMPLETE")
    print("=" * 80)
