# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Hardware Model - Area and Power Specifications
===============================================

Provides hardware specifications for MCTS accelerator components.
Uses board_config as the source of truth for hardware parameters.

Similar to how McPAT provides area/power models for CPUs,
this module provides specifications for MCTS accelerator units.
"""

from py_sst_cpp.components.board_config import BoardSize, get_board_config
from typing import Dict, Any


class HardwareModel:
    """
    Hardware model providing area and power specifications.

    This class wraps board_config and provides convenient access
    to hardware specifications for performance analysis.
    """

    def __init__(self, board_size: int):
        """
        Initialize hardware model for specific board size.

        Args:
            board_size: Board size (2, 3, 5, 9, 13, 19)
        """
        self.board_size = board_size

        # Map board size to BoardSize enum
        board_size_map = {
            2: BoardSize.BOARD_2X2,
            3: BoardSize.BOARD_3X3,
            5: BoardSize.BOARD_5X5,
            9: BoardSize.BOARD_9X9,
            13: BoardSize.BOARD_13X13,
            19: BoardSize.BOARD_19X19
        }

        self.board_config = get_board_config(board_size_map[board_size])

    # ========================================================================
    # Area specifications from board_config attributes.
    # ========================================================================

    @property
    def total_area_mm2(self) -> float:
        """Total chip area in mm² (digital logic + memory arrays)"""
        return self.board_config.total_area_mm2

    @property
    def digital_logic_area_mm2(self) -> float:
        """Digital logic area in mm² (excluding memory arrays)"""
        return self.board_config.digital_logic_area_mm2

    @property
    def selection_area_mm2(self) -> float:
        """Selection unit area (digital logic only, CAM array is separate)"""
        return self.board_config.selection_area_mm2

    @property
    def cam_array_area_mm2(self) -> float:
        """CAM array area in mm²"""
        return self.board_config.cam_array_area_mm2

    @property
    def expansion_area_mm2(self) -> float:
        """Expansion unit area (digital logic)"""
        return self.board_config.expansion_area_mm2

    @property
    def rollout_area_mm2(self) -> float:
        """Rollout unit area (crossbar + ADC + DAC + digital control)"""
        return self.board_config.rollout_total_area_mm2

    @property
    def backprop_area_mm2(self) -> float:
        """Backpropagation unit area (digital logic)"""
        return self.board_config.backprop_area_mm2

    @property
    def sram_array_area_mm2(self) -> float:
        """SRAM array area in mm²"""
        return self.board_config.sram_array_area_mm2

    # ========================================================================
    # Power Specifications
    # ========================================================================

    @property
    def total_power_mw(self) -> float:
        """Total power consumption in mW"""
        return self.board_config.total_power_mw

    @property
    def selection_power_mw(self) -> float:
        """Selection unit power (CAM + compute)"""
        return self.board_config.selection_power_mw

    @property
    def expansion_power_mw(self) -> float:
        """Expansion unit power (SRAM writes)"""
        return self.board_config.expansion_power_mw

    @property
    def rollout_power_mw(self) -> float:
        """Rollout unit power (crossbar + ADC + DAC + digital control)"""
        return self.board_config.rollout_power_mw_computed

    @property
    def backprop_power_mw(self) -> float:
        """Backpropagation unit power (SRAM updates + compute)"""
        return self.board_config.backprop_power_mw

    # ========================================================================
    # Timing specifications from board_config attributes.
    # ========================================================================

    @property
    def cam_lookup_delay_ns(self) -> float:
        """CAM lookup delay in ns"""
        return self.board_config.cam_lookup_delay_ns

    @property
    def selection_delay_ns(self) -> float:
        """Selection unit delay (includes UCB1 compute) in ns"""
        return self.board_config.selection_delay_ns

    @property
    def sram_access_delay_ns(self) -> float:
        """SRAM access (read/write) delay in ns"""
        return self.board_config.sram_access_delay_ns

    @property
    def crossbar_delay_ns(self) -> float:
        """Crossbar inference delay in ns"""
        return self.board_config.crossbar_delay_ns

    @property
    def rollout_total_latency_ns(self) -> float:
        """Complete rollout latency (ADC + crossbar + DAC) in ns"""
        return self.board_config.rollout_total_latency_ns

    @property
    def expansion_delay_ns(self) -> float:
        """Expansion unit delay in ns"""
        return self.board_config.expansion_delay_ns

    @property
    def backprop_delay_ns(self) -> float:
        """Backpropagation delay per node update in ns"""
        return self.board_config.backprop_delay_ns

    @property
    def fsm_transition_delay_ns(self) -> float:
        """FSM state transition delay in ns"""
        return self.board_config.fsm_transition_delay_ns

    # ========================================================================
    # Memory Specifications
    # ========================================================================

    @property
    def sram_size_kb(self) -> float:
        """SRAM size in KB"""
        return self.board_config.sram_size_kb

    @property
    def cam_entries(self) -> int:
        """Number of CAM entries"""
        return self.board_config.cam_entries

    # ========================================================================
    # Summary Methods
    # ========================================================================

    def get_area_breakdown(self) -> Dict[str, float]:
        """Get area breakdown by component."""
        return {
            'selection_unit': self.selection_area_mm2,
            'expansion_unit': self.expansion_area_mm2,
            'rollout_unit': self.rollout_area_mm2,
            'backprop_unit': self.backprop_area_mm2,
            'fsm_unit': self.board_config.fsm_area_mm2,
            'tcam_fsm': self.board_config.tcam_area_mm2,
            'cam_array': self.cam_array_area_mm2,
            'sram_array': self.sram_array_area_mm2,
            'digital_logic_total': self.digital_logic_area_mm2,
            'memory_total': self.cam_array_area_mm2 + self.sram_array_area_mm2,
            'total': self.total_area_mm2
        }

    def get_power_breakdown(self) -> Dict[str, float]:
        """Get power breakdown by component."""
        return {
            'selection_unit': self.selection_power_mw,
            'expansion_unit': self.expansion_power_mw,
            'rollout_unit': self.rollout_power_mw,
            'backprop_unit': self.backprop_power_mw,
            'fsm_unit': self.board_config.fsm_power_mw,
            'tcam_fsm': self.board_config.tcam_power_mw,
            'total': self.total_power_mw
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get complete hardware summary."""
        return {
            'board_size': f"{self.board_size}x{self.board_size}",
            'positions': self.board_size * self.board_size,
            'technology': '22nm (Stillmaker-scaled from 65nm synthesis)',
            'total_area_mm2': self.total_area_mm2,
            'digital_logic_area_mm2': self.digital_logic_area_mm2,
            'memory_area_mm2': self.cam_array_area_mm2 + self.sram_array_area_mm2,
            'total_power_mw': self.total_power_mw,
            'sram_size_mb': self.sram_size_kb / 1024,
            'cam_entries': self.cam_entries,
            'area_breakdown': self.get_area_breakdown(),
            'power_breakdown': self.get_power_breakdown()
        }

    def __str__(self) -> str:
        return (f"HardwareModel({self.board_size}x{self.board_size}, "
                f"{self.total_area_mm2:.2f} mm², {self.total_power_mw:.2f} mW)")
