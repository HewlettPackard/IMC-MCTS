# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Board Configuration System

Provides board-specific configuration and component loading for different board sizes.

Hardware Specifications:
- MCTS component specs (Selection, Expansion, Rollout, Backpropagation, FSM)
- Digital logic: 65nm synthesis → 22nm via Stillmaker (÷2.5 area, ×0.44 power)
- Memory arrays: Calculated separately from cell sizes at target node
- Clock frequency: 500 MHz (2 ns reference clock period)

TECHNOLOGY NODE SUMMARY:
========================
Component               | Native Node | Target | Scaling Method
------------------------|-------------|--------|------------------
Digital synthesis       | 65nm        | 22nm   | Stillmaker ÷2.5 area
CAM cells [31]          | 28nm        | 22nm   | (22/28)² = 0.617
TCAM cells [30]         | 65nm        | 22nm   | Stillmaker ÷2.5
SRAM cells              | CACTI 22nm  | 22nm   | Native (no scaling)
Crossbar calibration    | 22nm        | 22nm   | Native
ADC/DAC                 | 22nm        | 22nm   | Native

CAM Cell Specifications (from literature):
- Selection Unit CAM: 6T SRAM [31] scaled from 28nm to 22nm
  * Cell area: 0.093 μm²/cell @ 22nm (from 0.15 μm²/cell @ 28nm)
  * Search energy: 0.48 fJ/bit @ 22nm (from 0.60 fJ/bit @ 28nm)
  * Scaling: (22/28)² = 0.617 for area, (22/28)^2.5 = 0.492 for energy
- FSM TCAM: 16T NOR-type TCAM [30] scaled from 65nm to 22nm (Stillmaker)
  * Cell area: 0.676 μm²/cell @ 22nm (from 1.69 μm²/cell @ 65nm)
  * Search energy: 0.619 fJ/bit @ 22nm (from 1.98 fJ/bit @ 65nm)
  * Configuration: 11 rows × 16 bits = 176 bits
  * Total TCAM area: 119 μm² (0.000119 mm²)
  * Power: 249 μW @ 500 MHz + 1 nW leakage
  * Stillmaker scaling: 2.5× area reduction, 3.2× energy reduction (65nm→22nm)

SRAM Cell Specifications:
- 6T SRAM @ 22nm: 0.024 μm²/bit (from CACTI 6.5)
- Used for node storage and children pointers

All board sizes include the same TCAM FSM since the state machine is board-independent.

Power values are scaled for 500 MHz operation (5x multiplier from 100 MHz baseline).

ROLLOUT UNIT ARCHITECTURE:
===============================================
The rollout unit uses a hybrid architecture combining:
1. Digital control logic (from aggregate synthesis-derived results)
2. ADC circuits (from literature - Haraldstad & Nentwich)
3. DAC circuits (from literature - Eslahi & Hamilton)
4. Crossbar arrays (literature-calibrated; public link forthcoming)

ADC/DAC/CROSSBAR PARALLEL OPERATION (literature-calibrated model):
- All DACs operate in parallel → latency is constant: 3 ns
- Crossbar MVM (I=GV): constant 2.5 ns (from crossbar_hardware.py)
- All ADCs operate in parallel → latency is constant: 1-10 ns (depends on precision)
- Total rollout latency = DAC + Crossbar + ADC (all parallel, not sequential)

For 2-layer network (e.g., 162→96→3):
- Per layer: DAC (3 ns) + Crossbar (2.5 ns) + ADC (variable)
- With pipelining: ~10-15 ns total for 2 layers

AREA SCALING:
- DAC area scales linearly with N² (number of inputs): 0.000328 mm²/channel
  Source: Eslahi & Hamilton, "Ultra Compact and Linear 4-bit Digital-to-Analog
  Converter in 22nm FDSOI Technology," IEEE, 2022 (Xplore 9937686)
- ADC area is CONSTANT (only 3 outputs for value network): 0.035 mm² total
  Source: Haraldstad & Nentwich NTNU 2023 (~0.0117 mm²/channel × 3)
- Crossbar area from a 256×256 baseline at native 22nm
  Cell size: 0.0424 µm²/cell
  Formula: (input_layer + hidden_layer) devices × cell_size × 2.0 overhead
  2-layer NN: N²→hidden→3, where hidden=32 (small) or 96 (large boards)

References:
-----------
[31] 6T SRAM CAM cell (2015):
     Native: 28nm, 0.15 μm²/cell, 0.60 fJ/bit search energy
     Scaled to 22nm: 0.093 μm²/cell, 0.48 fJ/bit
     Scaling method: Direct node scaling (22/28)² for area, (22/28)^2.5 for energy

[30] 16T NOR-type TCAM cell (2013):
     Native: 65nm, 1.69 μm²/cell, 1.98 fJ/bit search energy
     Scaled to 22nm: 0.676 μm²/cell, 0.619 fJ/bit
     Scaling method: Stillmaker (2.5× area reduction, 3.2× energy reduction, 65nm→22nm)
"""

from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum


class BoardSize(Enum):
    """Supported board sizes"""
    BOARD_2X2 = 2
    BOARD_3X3 = 3
    BOARD_5X5 = 5
    BOARD_8X8 = 8
    BOARD_9X9 = 9
    BOARD_11X11 = 11
    BOARD_13X13 = 13
    BOARD_15X15 = 15
    BOARD_19X19 = 19


@dataclass
class BoardConfig:
    """Configuration for a specific board size

    SRAM Architecture (two separate arrays):
    - Node SRAM: stores per-node metadata (visits, value, parent, children_start, count, flags)
      Entry size: 24 bytes. Addressed by node_id.
    - Children SRAM: pool of 4-byte child node IDs, shared across all expanded nodes.
      Each node's children_start/count in Node SRAM points into this pool.
    Pool-based design is much more memory-efficient than fixed-size child arrays
    since most nodes are leaves with zero children.
    """
    board_size: int
    num_positions: int
    cam_entries: int
    node_sram_kb: int       # Node SRAM: per-node metadata (24 bytes/entry)
    children_sram_kb: int   # Children SRAM: pool of child pointers (4 bytes/entry)
    crossbar_size: int
    max_children: int
    rollout_depth: int

    # NOTE: exploration_constant USED to live here (always 1.414), but the
    # SST runner reads it from performance_config.py instead, where it
    # varies by play_strength (LOW=1.0, MEDIUM/HIGH=1.414). Having two
    # sources risked silent divergence. Source of truth is now
    # performance_config.PERFORMANCE_CONFIGS only.

    # Hardware specs
    selection_gates: int
    selection_area_mm2: float
    selection_power_mw: float

    rollout_gates: int
    # rollout area and power are computed from components — see rollout_total_area_mm2 and rollout_power_mw_computed properties

    expansion_gates: int
    expansion_area_mm2: float
    expansion_power_mw: float

    backprop_gates: int
    backprop_area_mm2: float
    backprop_power_mw: float

    fsm_gates: int
    fsm_area_mm2: float
    fsm_power_mw: float

    # Component timing delays @ 500 MHz (2ns clock period)
    # These are accumulated during simulation to calculate actual latency
    selection_delay_ns: float = 2.0      # Selection unit delay per step
    cam_lookup_delay_ns: float = 1.0     # CAM lookup (TCAM is fast)
    expansion_delay_ns: float = 2.0      # Expansion unit delay
    rollout_base_delay_ns: float = 2.0   # Rollout unit base delay
    crossbar_delay_ns: float = 5.0       # Crossbar neural network inference
    backprop_delay_ns: float = 2.0       # Backpropagation per node update
    fsm_transition_delay_ns: float = 1.0 # FSM state transition
    sram_access_delay_ns: float = 1.0    # SRAM read/write access

    # Selection Unit CAM specs (literature-based)
    # 6T SRAM CAM [31]: 28nm → 22nm scaling
    selection_cam_cell_area_um2: float = 0.093  # μm²/cell @ 22nm (from 0.15 μm² @ 28nm)
    selection_cam_cell_energy_fj: float = 0.48  # fJ/bit search @ 22nm (from 0.60 fJ/bit @ 28nm)

    # TCAM FSM specs (hardware-accelerated state machine)
    # 16T NOR-type TCAM [30]: 65nm → 22nm scaling (Stillmaker method)
    # Same for all boards: 11 rows × 16 bits @ 22nm
    tcam_rows: int = 11
    tcam_bits_per_row: int = 16
    tcam_cell_area_um2: float = 0.676  # μm²/cell @ 22nm (from 1.69 μm² @ 65nm, Stillmaker 2.5×)
    tcam_cell_energy_fj: float = 0.619  # fJ/bit search @ 22nm (from 1.98 fJ/bit @ 65nm, Stillmaker 3.2×)
    tcam_area_mm2: float = 0.000119  # 119 μm² (11 rows × 16 bits × 0.676 μm²/cell)
    tcam_power_mw: float = 0.249      # @ 500 MHz, state-partitioned mode (5x from 100 MHz)
    tcam_leakage_mw: float = 0.000001 # 1 nW static leakage @ 22nm

    # Memory array specs for area calculations
    # CAM: stores UCB1 scores for hot nodes (cam_entries × cam_bits_per_entry)
    # CAM entry format: node_id (32b) + parent_id (32b) + visits (32b) + wins (32b) + UCB1 (32b) = 160 bits minimum
    cam_bits_per_entry: int = 512  # Bits per CAM entry (including hash, scores, metadata)

    # SRAM: 6T SRAM @ 22nm from CACTI 6.5
    # NOTE: Using CACTI macro-level results, not cell-level calculation
    # CACTI 22nm results: 16KB=0.0137mm², 32KB=0.0261mm², 64KB=0.048mm²
    # Scaling: ~0.85 mm²/MB at 22nm for larger SRAMs
    sram_cell_area_um2: float = 0.024  # μm²/bit @ 22nm (6T SRAM from CACTI) - used for small calculations

    # SRAM areas from CACTI (split into node and children arrays)
    node_sram_area_mm2: float = 0.0      # Node SRAM area from CACTI
    children_sram_area_mm2: float = 0.0  # Children SRAM area from CACTI

    # Rollout unit complete specs (automated synthesis + literature ADC/DAC/crossbar)
    # These provide detailed breakdown for energy/latency analysis
    rollout_digital_area_mm2: float = 0.0      # Digital control logic (from automated synthesis)
    rollout_adc_area_mm2: float = 0.0          # ADC circuits (from literature)
    rollout_dac_area_mm2: float = 0.0          # DAC circuits (from literature)
    rollout_crossbar_area_mm2: float = 0.0     # Crossbar arrays (from literature)
    rollout_total_latency_ns: float = 5.0      # Complete NN inference latency (with ADC conversion)
    # rollout energy computed dynamically via rollout_energy_pj_computed property

    # ========================================================================
    # DYNAMIC ROLLOUT POWER PARAMETERS (from literature, user-configurable)
    # ========================================================================
    # These unit values are used to compute rollout power dynamically
    # based on crossbar_size (num inputs) and num_adc_outputs
    #
    # DAC: Digital-to-Analog Converter for crossbar inputs
    # Source: crossbar_hardware.py literature values
    dac_power_per_channel_mw: float = 0.05    # 50 µW per DAC channel (from Eslahi & Hamilton)

    # ADC: Analog-to-Digital Converter for crossbar outputs
    # Source: crossbar_hardware.py literature values
    adc_power_per_channel_mw: float = 0.10    # 100 µW per ADC channel (from Haraldstad & Nentwich)

    # Crossbar array power density
    # Source: memristor device physics models
    crossbar_power_density_mw_per_mm2: float = 4000.0  # ~4 W/mm² for active crossbar

    # Digital control power for rollout unit (from 65nm synthesis, Stillmaker-scaled)
    rollout_digital_power_mw: float = 0.0     # Set per board size

    # Number of ADC output channels (depends on NN architecture)
    # For MCTS: typically 3 outputs (win/loss/draw) or N² for policy head
    num_adc_outputs: int = 3                  # Default: 3 outputs for value network

    @property
    def sram_size_kb(self) -> int:
        """Total SRAM: Node SRAM + Children SRAM"""
        return self.node_sram_kb + self.children_sram_kb

    @property
    def sram_area_mm2_cacti(self) -> float:
        """Total SRAM area from CACTI (Node + Children)"""
        return self.node_sram_area_mm2 + self.children_sram_area_mm2

    @property
    def total_gates(self) -> int:
        """Total gate count (TCAM excluded, uses cells not gates)"""
        return (self.selection_gates + self.rollout_gates + self.expansion_gates +
                self.backprop_gates + self.fsm_gates)

    @property
    def cam_array_area_mm2(self) -> float:
        """
        CAM array area based on entries and cell size.
        CAM stores UCB1 scores for hot node lookup.
        Formula: cam_entries × cam_bits_per_entry × cam_cell_area
        """
        cam_area_um2 = self.cam_entries * self.cam_bits_per_entry * self.selection_cam_cell_area_um2
        return cam_area_um2 / 1e6  # Convert μm² to mm²

    @property
    def sram_array_area_mm2(self) -> float:
        """
        Total SRAM array area (Node SRAM + Children SRAM) from CACTI.
        Uses macro-level CACTI results which are more accurate than cell-level calculation.
        """
        cacti_sram_area_mm2 = self.sram_area_mm2_cacti
        if cacti_sram_area_mm2 > 0:
            return cacti_sram_area_mm2
        else:
            # Fallback to cell-level calculation if CACTI values not set
            total_sram_bits = self.sram_size_kb * 1024 * 8
            sram_area_um2 = total_sram_bits * self.sram_cell_area_um2
            return sram_area_um2 / 1e6

    @property
    def digital_logic_area_mm2(self) -> float:
        """Total area of digital logic (excluding memory arrays)"""
        return (self.selection_area_mm2 + self.rollout_total_area_mm2 + self.expansion_area_mm2 +
                self.backprop_area_mm2 + self.fsm_area_mm2 + self.tcam_area_mm2)

    @property
    def total_area_mm2(self) -> float:
        """Total chip area including digital logic, TCAM, CAM array, and SRAM"""
        return self.digital_logic_area_mm2 + self.cam_array_area_mm2 + self.sram_array_area_mm2

    # ========================================================================
    # COMPUTED ROLLOUT POWER PROPERTIES (dynamic calculation from parameters)
    # ========================================================================

    @property
    def dac_power_mw(self) -> float:
        """
        DAC power computed from crossbar_size (number of inputs).
        Formula: num_inputs × power_per_dac
        """
        return self.crossbar_size * self.dac_power_per_channel_mw

    @property
    def adc_power_mw(self) -> float:
        """
        ADC power computed from number of output channels.
        Formula: num_outputs × power_per_adc
        """
        return self.num_adc_outputs * self.adc_power_per_channel_mw

    @property
    def crossbar_power_mw(self) -> float:
        """
        Crossbar array power computed from area and power density.
        Formula: crossbar_area × power_density
        """
        return self.rollout_crossbar_area_mm2 * self.crossbar_power_density_mw_per_mm2

    @property
    def rollout_power_mw_computed(self) -> float:
        """
        Total rollout power computed dynamically from components.
        Components: digital_control + DACs + ADCs + crossbar
        """
        return (self.rollout_digital_power_mw +
                self.dac_power_mw +
                self.adc_power_mw +
                self.crossbar_power_mw)

    @property
    def rollout_total_area_mm2(self) -> float:
        """
        Total rollout area computed from components.
        Components: digital_control + ADCs + DACs + crossbar
        """
        return (self.rollout_digital_area_mm2 +
                self.rollout_adc_area_mm2 +
                self.rollout_dac_area_mm2 +
                self.rollout_crossbar_area_mm2)

    @property
    def rollout_energy_pj_computed(self) -> float:
        """
        Rollout energy computed from power and latency.
        Formula: power_mw × latency_ns = energy_pJ
        """
        return self.rollout_power_mw_computed * self.rollout_total_latency_ns

    @property
    def total_power_mw(self) -> float:
        """
        Total power consumption including TCAM FSM.
        Uses computed rollout power (dynamic) instead of hardcoded value.
        """
        return (self.selection_power_mw + self.rollout_power_mw_computed + self.expansion_power_mw +
                self.backprop_power_mw + self.fsm_power_mw + self.tcam_power_mw)

    @property
    def total_power_with_tcam_leakage_mw(self) -> float:
        """Total power including TCAM dynamic + leakage"""
        return self.total_power_mw + self.tcam_leakage_mw


# Board configurations based on architecture data
# DESIGN POINT: Memory (CAM/SRAM) is sized for MEDIUM performance level.
# For 2x2-9x9 at MEDIUM, the full MCTS tree fits on-chip.
# For 13x13-19x19 at MEDIUM, on-chip SRAM acts as cache with DRAM spillover.
BOARD_CONFIGS = {
    BoardSize.BOARD_2X2: BoardConfig(
        board_size=2,
        num_positions=4,
        cam_entries=128,  # Sized for MEDIUM (200 iter, ~65 nodes) — full tree on-chip
        node_sram_kb=192,       # Node metadata (24B/node): 65 nodes = 1.5 KB, generous margin
        children_sram_kb=64,    # Child pointer pool (4B/ptr): ~65 ptrs = 0.3 KB, generous margin
        crossbar_size=4,
        max_children=4,
        rollout_depth=20,
        # Hardware specs for 2x2 (PROPERLY Stillmaker-scaled @ 22nm from 65nm synthesis)
        # Applied ÷2.5 area, ×0.44 power (Stillmaker 65nm→22nm)
        selection_gates=0,
        selection_area_mm2=0.000129,  # 129 μm² @ 22nm (from 323 μm² @ 65nm, ÷2.5)
        selection_power_mw=0.14,      # @ 500 MHz (from 0.31 mW @ 65nm, ×0.44)

        rollout_gates=0,

        # Rollout breakdown for 2x2
        # ADC constant (3 outputs), calibrated crossbar
        # ADC: 0.035 mm² (constant, 3 outputs × 0.0117 mm²/channel)
        # DAC: 4 × 0.000328 mm² = 0.00131 mm² (from Eslahi & Hamilton)
        # Crossbar: 2-layer NN 4→32→3 = (4×32 + 32×3) = 224 devices
        #           224 × 0.0424 µm² × 2.0 overhead = 19.0 µm² = 0.000019 mm²
        rollout_digital_area_mm2=0.000040,  # Digital control
        rollout_digital_power_mw=0.038,     # @ 500 MHz (from 0.087 mW @ 65nm, ×0.44)
        rollout_adc_area_mm2=0.035,         # ADC (constant, 3 outputs, Haraldstad & Nentwich)
        rollout_dac_area_mm2=0.00131,       # DAC (4 × 0.000328 mm², Eslahi & Hamilton)
        rollout_crossbar_area_mm2=0.000019, # 224 devices × 0.0424 µm² × 2.0
        # Rollout latency: DAC + Crossbar + ADC (all parallel)
        # 2-layer network: DAC (3 ns) + 2×Crossbar (5 ns) + 2×ADC (6 ns) = 14 ns
        # Crossbar MVM = 2.5 ns constant (from crossbar_hardware.py)
        rollout_total_latency_ns=14.0,      # Constant for all boards (parallel ops)
        num_adc_outputs=3,                  # 3 outputs for value network

        expansion_gates=0,
        expansion_area_mm2=0.000041,  # 41 μm² @ 22nm (from 102 μm² @ 65nm, ÷2.5)
        expansion_power_mw=0.048,     # @ 500 MHz (from 0.11 mW @ 65nm, ×0.44)

        backprop_gates=0,
        backprop_area_mm2=0.000065,  # 65 μm² @ 22nm (from 162 μm² @ 65nm, ÷2.5)
        backprop_power_mw=0.071,     # @ 500 MHz (from 0.16 mW @ 65nm, ×0.44)

        fsm_gates=0,
        fsm_area_mm2=0.001200,   # ~1,200 μm² @ 22nm (from ~3,000 μm² @ 65nm, ÷2.5)
        fsm_power_mw=1.10,       # @ 500 MHz (from 2.5 mW @ 65nm, ×0.44)

        # SRAM from CACTI: 256 KB total @ 22nm ≈ 0.22 mm²
        node_sram_area_mm2=0.165,       # 192 KB node SRAM
        children_sram_area_mm2=0.055,   # 64 KB children SRAM
    ),

    BoardSize.BOARD_3X3: BoardConfig(
        board_size=3,
        num_positions=9,
        cam_entries=256,  # Sized for MEDIUM (500 iter, ~622 nodes) — full tree on-chip
        node_sram_kb=384,       # Node metadata: 622 nodes × 24B = 14.5 KB
        children_sram_kb=128,   # Child pointer pool: ~622 ptrs × 4B = 2.4 KB
        crossbar_size=9,
        max_children=9,
        rollout_depth=30,
        # Hardware specs for 3x3 (PROPERLY Stillmaker-scaled @ 22nm from 65nm synthesis)
        # Applied ÷2.5 area, ×0.44 power (Stillmaker 65nm→22nm)
        selection_gates=0,
        selection_area_mm2=0.000440,  # 440 μm² @ 22nm (from 1,099 μm² @ 65nm, ÷2.5)
        selection_power_mw=0.39,      # @ 500 MHz (from 0.88 mW @ 65nm, ×0.44)

        rollout_gates=0,

        # Rollout breakdown for 3x3
        # ADC constant (3 outputs), calibrated crossbar
        # ADC: 0.035 mm² (constant, 3 outputs × 0.0117 mm²/channel)
        # DAC: 9 × 0.000328 mm² = 0.00295 mm² (from Eslahi & Hamilton)
        # Crossbar: 2-layer NN 9→32→3 = (9×32 + 32×3) = 384 devices
        #           384 × 0.0424 µm² × 2.0 overhead = 32.6 µm² = 0.000033 mm²
        rollout_digital_area_mm2=0.000088,  # Digital control
        rollout_digital_power_mw=0.10,      # @ 500 MHz (from 0.23 mW @ 65nm, ×0.44)
        rollout_adc_area_mm2=0.035,         # ADC (constant, 3 outputs, Haraldstad & Nentwich)
        rollout_dac_area_mm2=0.00295,       # DAC (9 × 0.000328 mm², Eslahi & Hamilton)
        rollout_crossbar_area_mm2=0.000033, # 384 devices × 0.0424 µm² × 2.0
        # Rollout latency: DAC + Crossbar + ADC (all parallel)
        # 2-layer network: DAC (3 ns) + 2×Crossbar (5 ns) + 2×ADC (6 ns) = 14 ns
        # Crossbar MVM = 2.5 ns constant (from crossbar_hardware.py)
        rollout_total_latency_ns=14.0,      # Constant for all boards (parallel ops)
        num_adc_outputs=3,                  # 3 outputs for value network

        expansion_gates=0,
        expansion_area_mm2=0.000174,  # 174 μm² @ 22nm (from 436 μm² @ 65nm, ÷2.5)
        expansion_power_mw=0.21,      # @ 500 MHz (from 0.48 mW @ 65nm, ×0.44)

        backprop_gates=0,
        backprop_area_mm2=0.000108,  # 108 μm² @ 22nm (from 271 μm² @ 65nm, ÷2.5)
        backprop_power_mw=0.11,      # @ 500 MHz (from 0.26 mW @ 65nm, ×0.44)

        fsm_gates=0,
        fsm_area_mm2=0.001600,   # ~1,600 μm² @ 22nm (from ~4,000 μm² @ 65nm, ÷2.5)
        fsm_power_mw=1.65,       # @ 500 MHz (from 3.75 mW @ 65nm, ×0.44)

        # SRAM from CACTI: 512 KB total @ 22nm ≈ 0.43 mm²
        node_sram_area_mm2=0.3225,      # 384 KB node SRAM
        children_sram_area_mm2=0.1075,  # 128 KB children SRAM
    ),

    BoardSize.BOARD_5X5: BoardConfig(
        board_size=5,
        num_positions=25,
        cam_entries=512,  # Sized for MEDIUM (1000 iter, ~9,159 nodes) — full tree on-chip
        node_sram_kb=768,       # Node metadata: 9,160 nodes × 24B = 215 KB
        children_sram_kb=256,   # Child pointer pool: ~9,159 ptrs × 4B = 36 KB
        crossbar_size=25,
        max_children=25,
        rollout_depth=50,
        # Hardware specs for 5x5 (PROPERLY Stillmaker-scaled @ 22nm from 65nm synthesis)
        # Applied ÷2.5 area, ×0.44 power (Stillmaker 65nm→22nm)
        selection_gates=0,
        selection_area_mm2=0.001363,  # 1,363 μm² @ 22nm (from 3,408 μm² @ 65nm, ÷2.5)
        selection_power_mw=1.31,      # @ 500 MHz (from 2.99 mW @ 65nm, ×0.44)

        rollout_gates=0,

        # Rollout breakdown for 5x5
        # ADC constant (3 outputs), calibrated crossbar
        # ADC: 0.035 mm² (constant, 3 outputs × 0.0117 mm²/channel)
        # DAC: 25 × 0.000328 mm² = 0.0082 mm² (from Eslahi & Hamilton)
        # Crossbar: 2-layer NN 25→96→3 = (25×96 + 96×3) = 2,688 devices
        #           2,688 × 0.0424 µm² × 2.0 overhead = 228 µm² = 0.000228 mm²
        rollout_digital_area_mm2=0.000150,  # Digital control (corrected, ~1.7× of 3x3)
        rollout_digital_power_mw=0.15,      # @ 500 MHz (corrected to scale with area)
        rollout_adc_area_mm2=0.035,         # ADC (constant, 3 outputs, Haraldstad & Nentwich)
        rollout_dac_area_mm2=0.0082,        # DAC (25 × 0.000328 mm², Eslahi & Hamilton)
        rollout_crossbar_area_mm2=0.000228, # 2,688 devices × 0.0424 µm² × 2.0
        # Rollout latency: DAC + Crossbar + ADC (all parallel)
        # 2-layer network: DAC (3 ns) + 2×Crossbar (5 ns) + 2×ADC (6 ns) = 14 ns
        # Crossbar MVM = 2.5 ns constant (from crossbar_hardware.py)
        rollout_total_latency_ns=14.0,      # Constant for all boards (parallel ops)
        num_adc_outputs=3,                  # 3 outputs for value network
        expansion_gates=0,
        expansion_area_mm2=0.001139,  # 1,139 μm² @ 22nm (from 2,847 μm² @ 65nm, ÷2.5)
        expansion_power_mw=1.32,      # @ 500 MHz (from 2.99 mW @ 65nm, ×0.44)

        backprop_gates=0,
        backprop_area_mm2=0.000292,  # 292 μm² @ 22nm (from 729 μm² @ 65nm, ÷2.5)
        backprop_power_mw=0.32,      # @ 500 MHz (from 0.72 mW @ 65nm, ×0.44)

        fsm_gates=0,
        fsm_area_mm2=0.002000,   # ~2,000 μm² @ 22nm (from ~5,000 μm² @ 65nm, ÷2.5)
        fsm_power_mw=2.20,       # @ 500 MHz (from 5.0 mW @ 65nm, ×0.44)

        # SRAM from CACTI: 1024 KB total @ 22nm ≈ 0.85 mm²
        node_sram_area_mm2=0.6375,      # 768 KB node SRAM
        children_sram_area_mm2=0.2125,  # 256 KB children SRAM
    ),

    BoardSize.BOARD_8X8: BoardConfig(
        board_size=8,
        num_positions=64,
        cam_entries=1024,
        node_sram_kb=1024,
        children_sram_kb=384,
        crossbar_size=64,
        max_children=64,
        rollout_depth=50,
        # Hardware specs for 8x8 (interpolated between 5x5 and 9x9 on N²)
        selection_gates=0,
        selection_area_mm2=0.003972,
        selection_power_mw=3.85,

        rollout_gates=0,

        # Rollout breakdown for 8x8
        # DAC: 64 × 0.000328 mm² = 0.02099 mm²
        # Crossbar: 2-layer NN 64→96→3 = (64×96 + 96×3) = 6,432 devices
        #           6,432 × 0.0424 µm² × 2.0 overhead = 545.5 µm² = 0.000545 mm²
        # ADC: 0.035 mm² (constant, 3 outputs)
        rollout_digital_area_mm2=0.003331,
        rollout_digital_power_mw=1.06,
        rollout_adc_area_mm2=0.035,
        rollout_dac_area_mm2=0.02099,
        rollout_crossbar_area_mm2=0.000545,
        rollout_total_latency_ns=14.0,
        num_adc_outputs=3,

        expansion_gates=0,
        expansion_area_mm2=0.007393,
        expansion_power_mw=9.01,

        backprop_gates=0,
        backprop_area_mm2=0.000712,
        backprop_power_mw=0.80,

        fsm_gates=0,
        fsm_area_mm2=0.004784,
        fsm_power_mw=4.50,

        # SRAM from CACTI: 1408 KB total @ 22nm
        node_sram_area_mm2=0.850,
        children_sram_area_mm2=0.319,
    ),

    BoardSize.BOARD_9X9: BoardConfig(
        board_size=9,
        num_positions=81,
        cam_entries=1024,  # Sized for MEDIUM (5000 iter, ~6,562 nodes) — full tree on-chip
        node_sram_kb=1536,      # Node metadata: 6,562 nodes × 24B = 154 KB
        children_sram_kb=512,   # Child pointer pool: ~6,561 ptrs × 4B = 26 KB
        crossbar_size=81,
        max_children=81,
        rollout_depth=50,
        # Hardware specs for 9x9 (PROPERLY Stillmaker-scaled @ 22nm from 65nm synthesis)
        # Previously had 65nm values with incorrect "Stillmaker @ 22nm" comments
        # Scaling: ÷2.5 for area, ×0.44 for power (Stillmaker 65nm→22nm)
        # Target: 5,000 iterations, ~50K nodes on-chip
        selection_gates=0,
        selection_area_mm2=0.005112,  # 5,112 μm² @ 22nm (from 12,780 μm² @ 65nm, ÷2.5)
        selection_power_mw=4.96,      # @ 500 MHz (from 11.26 mW @ 65nm, ×0.44)

        rollout_gates=0,

        # Rollout breakdown for 9x9
        # ADC constant (3 outputs), calibrated crossbar
        # ADC: 0.035 mm² (constant, 3 outputs × 0.0117 mm²/channel)
        # DAC: 81 × 0.000328 mm² = 0.0266 mm² (from Eslahi & Hamilton)
        # Crossbar: 2-layer NN 81→96→3 = (81×96 + 96×3) = 8,064 devices
        #           8,064 × 0.0424 µm² × 2.0 overhead = 684 µm² = 0.000684 mm²
        rollout_digital_area_mm2=0.00472,  # Automated synthesis (DC): 11,800 μm² @ 65nm ÷2.5
        rollout_digital_power_mw=1.46,     # @ 500 MHz (from 3.32 mW @ 65nm, ×0.44)
        rollout_adc_area_mm2=0.035,        # ADC (constant, 3 outputs, Haraldstad & Nentwich)
        rollout_dac_area_mm2=0.0266,       # DAC (81 × 0.000328 mm², Eslahi & Hamilton)
        rollout_crossbar_area_mm2=0.000684, # 8,064 devices × 0.0424 µm² × 2.0
        # Rollout latency: DAC + Crossbar + ADC (all parallel)
        # 2-layer network: DAC (3 ns) + 2×Crossbar (5 ns) + 2×ADC (6 ns) = 14 ns
        # Crossbar MVM = 2.5 ns constant (from crossbar_hardware.py)
        rollout_total_latency_ns=14.0,      # Constant for all boards (parallel ops)
        num_adc_outputs=3,                 # 3 outputs for value network

        expansion_gates=0,
        expansion_area_mm2=0.010124,  # 10,124 μm² @ 22nm (from 25,309 μm² @ 65nm, ÷2.5)
        expansion_power_mw=12.37,     # @ 500 MHz (from 28.11 mW @ 65nm, ×0.44)

        backprop_gates=0,
        backprop_area_mm2=0.000896,  # 896 μm² @ 22nm (from 2,239 μm² @ 65nm, ÷2.5)
        backprop_power_mw=1.01,      # @ 500 MHz (from 2.31 mW @ 65nm, ×0.44)

        fsm_gates=0,
        fsm_area_mm2=0.006000,   # ~6,000 μm² @ 22nm (from ~15,000 μm² @ 65nm, ÷2.5)
        fsm_power_mw=5.50,       # @ 500 MHz (from 12.5 mW @ 65nm, ×0.44)

        # SRAM from CACTI: 2048 KB total @ 22nm ≈ 1.70 mm²
        node_sram_area_mm2=1.275,       # 1536 KB node SRAM
        children_sram_area_mm2=0.425,   # 512 KB children SRAM
    ),

    BoardSize.BOARD_11X11: BoardConfig(
        board_size=11,
        num_positions=121,
        cam_entries=1024,
        node_sram_kb=1536,
        children_sram_kb=512,
        crossbar_size=121,
        max_children=121,
        rollout_depth=55,
        # Hardware specs for 11x11 (interpolated between 9x9 and 13x13 on N²)
        selection_gates=0,
        selection_area_mm2=0.008123,
        selection_power_mw=8.04,

        rollout_gates=0,

        # Rollout breakdown for 11x11
        # DAC: 121 × 0.000328 mm² = 0.03969 mm²
        # Crossbar: 2-layer NN 121→96→3 = (121×96 + 96×3) = 11,904 devices
        #           11,904 × 0.0424 µm² × 2.0 overhead = 1,010 µm² = 0.001010 mm²
        # ADC: 0.035 mm² (constant, 3 outputs)
        rollout_digital_area_mm2=0.006211,
        rollout_digital_power_mw=1.93,
        rollout_adc_area_mm2=0.035,
        rollout_dac_area_mm2=0.03969,
        rollout_crossbar_area_mm2=0.001010,
        rollout_total_latency_ns=14.0,
        num_adc_outputs=3,

        expansion_gates=0,
        expansion_area_mm2=0.024919,
        expansion_power_mw=30.60,

        backprop_gates=0,
        backprop_area_mm2=0.001444,
        backprop_power_mw=1.63,

        fsm_gates=0,
        fsm_area_mm2=0.006909,
        fsm_power_mw=6.50,

        # SRAM from CACTI: 2048 KB total @ 22nm ≈ 1.70 mm²
        node_sram_area_mm2=1.275,
        children_sram_area_mm2=0.425,
    ),

    BoardSize.BOARD_13X13: BoardConfig(
        board_size=13,
        num_positions=169,
        cam_entries=1536,  # Sized for MEDIUM (7500 iter, ~28K nodes) — on-chip cache, DRAM spillover
        node_sram_kb=2048,      # Node metadata cache: 28K nodes × 24B = 670 KB (on-chip portion)
        children_sram_kb=1024,  # Child pointer pool cache: ~28K ptrs × 4B = 112 KB (on-chip portion)
        crossbar_size=169,
        max_children=169,
        rollout_depth=65,
        # Hardware specs for 13x13 (PROPERLY Stillmaker-scaled @ 22nm from 65nm synthesis)
        # Applied ÷2.5 area, ×0.44 power (Stillmaker 65nm→22nm)
        # Target: 7,500 iterations, ~75K nodes on-chip
        selection_gates=0,
        selection_area_mm2=0.011735,  # 11,735 μm² @ 22nm (from 29,337 μm² @ 65nm, ÷2.5)
        selection_power_mw=11.73,     # @ 500 MHz (from 26.65 mW @ 65nm, ×0.44)

        rollout_gates=0,

        # Rollout breakdown for 13x13
        # ADC constant (3 outputs), calibrated crossbar
        # ADC: 0.035 mm² (constant, 3 outputs × 0.0117 mm²/channel)
        # DAC: 169 × 0.000328 mm² = 0.0554 mm² (from Eslahi & Hamilton)
        # Crossbar: 2-layer NN 169→96→3 = (169×96 + 96×3) = 16,512 devices
        #           16,512 × 0.0424 µm² × 2.0 overhead = 1,400 µm² = 0.00140 mm²
        rollout_digital_area_mm2=0.0080,    # Digital control (corrected, ~1.7× of 9x9)
        rollout_digital_power_mw=2.50,      # @ 500 MHz (corrected to scale with area)
        rollout_adc_area_mm2=0.035,         # ADC (constant, 3 outputs, Haraldstad & Nentwich)
        rollout_dac_area_mm2=0.0554,        # DAC (169 × 0.000328 mm², Eslahi & Hamilton)
        rollout_crossbar_area_mm2=0.00140,  # 16,512 devices × 0.0424 µm² × 2.0
        # Rollout latency: DAC + Crossbar + ADC (all parallel)
        # 2-layer network: DAC (3 ns) + 2×Crossbar (5 ns) + 2×ADC (6 ns) = 14 ns
        # Crossbar MVM = 2.5 ns constant (from crossbar_hardware.py)
        rollout_total_latency_ns=14.0,      # Constant for all boards (parallel ops)
        num_adc_outputs=3,                  # 3 outputs for value network

        expansion_gates=0,
        expansion_area_mm2=0.042675,  # 42,675 μm² @ 22nm (from 106,688 μm² @ 65nm, ÷2.5)
        expansion_power_mw=52.47,     # @ 500 MHz (from 119.24 mW @ 65nm, ×0.44)

        backprop_gates=0,
        backprop_area_mm2=0.002102,  # 2,102 μm² @ 22nm (from 5,256 μm² @ 65nm, ÷2.5)
        backprop_power_mw=2.37,      # @ 500 MHz (from 5.38 mW @ 65nm, ×0.44)

        fsm_gates=0,
        fsm_area_mm2=0.008000,   # ~8,000 μm² @ 22nm (from ~20,000 μm² @ 65nm, ÷2.5)
        fsm_power_mw=7.70,       # @ 500 MHz (from 17.5 mW @ 65nm, ×0.44)

        # SRAM from CACTI: 3072 KB total @ 22nm ≈ 2.55 mm²
        node_sram_area_mm2=1.70,        # 2048 KB node SRAM
        children_sram_area_mm2=0.85,    # 1024 KB children SRAM
    ),

    BoardSize.BOARD_15X15: BoardConfig(
        board_size=15,
        num_positions=225,
        cam_entries=2048,
        node_sram_kb=2048,
        children_sram_kb=1024,
        crossbar_size=225,
        max_children=225,
        rollout_depth=70,
        # Hardware specs for 15x15 (interpolated between 13x13 and 19x19 on N²)
        selection_gates=0,
        selection_area_mm2=0.015271,
        selection_power_mw=16.53,

        rollout_gates=0,

        # Rollout breakdown for 15x15
        # DAC: 225 × 0.000328 mm² = 0.07380 mm²
        # Crossbar: 2-layer NN 225→96→3 = (225×96 + 96×3) = 21,888 devices
        #           21,888 × 0.0424 µm² × 2.0 overhead = 1,856 µm² = 0.001856 mm²
        # ADC: 0.035 mm² (constant, 3 outputs)
        rollout_digital_area_mm2=0.009167,
        rollout_digital_power_mw=3.38,
        rollout_adc_area_mm2=0.035,
        rollout_dac_area_mm2=0.07380,
        rollout_crossbar_area_mm2=0.001856,
        rollout_total_latency_ns=14.0,
        num_adc_outputs=3,

        expansion_gates=0,
        expansion_area_mm2=0.087806,
        expansion_power_mw=106.53,

        backprop_gates=0,
        backprop_area_mm2=0.003848,
        backprop_power_mw=3.96,

        fsm_gates=0,
        fsm_area_mm2=0.009167,
        fsm_power_mw=8.66,

        # SRAM from CACTI: 3072 KB total @ 22nm ≈ 2.55 mm²
        node_sram_area_mm2=1.700,
        children_sram_area_mm2=0.850,
    ),

    BoardSize.BOARD_19X19: BoardConfig(
        board_size=19,
        num_positions=361,
        cam_entries=2048,  # Sized for MEDIUM (10000 iter, ~130K nodes) — on-chip cache, DRAM spillover
        node_sram_kb=3072,      # Node metadata cache: 130K nodes × 24B = 3,054 KB (on-chip portion)
        children_sram_kb=1024,  # Child pointer pool cache: ~130K ptrs × 4B = 509 KB (on-chip portion)
        crossbar_size=361,
        max_children=361,
        rollout_depth=100,  # Deeper rollouts for larger board
        # Hardware specs for 19x19 (PROPERLY Stillmaker-scaled @ 22nm from 65nm synthesis)
        # Applied ÷2.5 area, ×0.44 power (Stillmaker 65nm→22nm)
        # Target: 1,000 iterations, ~100K nodes on-chip
        selection_gates=0,
        selection_area_mm2=0.023853,  # 23,853 μm² @ 22nm (from 59,632 μm² @ 65nm, ÷2.5)
        selection_power_mw=28.19,     # @ 500 MHz (from 64.07 mW @ 65nm, ×0.44)

        rollout_gates=0,

        # Rollout breakdown for 19x19
        # ADC constant (3 outputs), calibrated crossbar
        # ADC: 0.035 mm² (constant, 3 outputs × 0.0117 mm²/channel)
        # DAC: 361 × 0.000328 mm² = 0.1184 mm² (from Eslahi & Hamilton)
        # Crossbar: 2-layer NN 361→96→3 = (361×96 + 96×3) = 34,944 devices
        #           34,944 × 0.0424 µm² × 2.0 overhead = 2,963 µm² = 0.00296 mm²
        rollout_digital_area_mm2=0.012,     # Digital control (corrected, ~1.5× of 13x13)
        rollout_digital_power_mw=5.50,      # @ 500 MHz (corrected to scale with area)
        rollout_adc_area_mm2=0.035,         # ADC (constant, 3 outputs, Haraldstad & Nentwich)
        rollout_dac_area_mm2=0.1184,        # DAC (361 × 0.000328 mm², Eslahi & Hamilton)
        rollout_crossbar_area_mm2=0.00296,  # 34,944 devices × 0.0424 µm² × 2.0
        # Rollout latency: DAC + Crossbar + ADC (all parallel)
        # 2-layer network: DAC (3 ns) + 2×Crossbar (5 ns) + 2×ADC (6 ns) = 14 ns
        # Crossbar MVM = 2.5 ns constant (from crossbar_hardware.py)
        rollout_total_latency_ns=14.0,      # Constant for all boards (parallel ops)
        num_adc_outputs=3,                  # 3 outputs for value network

        expansion_gates=0,
        expansion_area_mm2=0.197428,  # 197,428 μm² @ 22nm (from 493,570 μm² @ 65nm, ÷2.5)
        expansion_power_mw=237.83,    # @ 500 MHz (from 540.52 mW @ 65nm, ×0.44)

        backprop_gates=0,
        backprop_area_mm2=0.008088,  # 8,088 μm² @ 22nm (from 20,221 μm² @ 65nm, ÷2.5)
        backprop_power_mw=7.81,      # @ 500 MHz (from 17.75 mW @ 65nm, ×0.44)

        fsm_gates=0,
        fsm_area_mm2=0.012000,   # ~12,000 μm² @ 22nm (from ~30,000 μm² @ 65nm, ÷2.5)
        fsm_power_mw=11.00,      # @ 500 MHz (from 25.0 mW @ 65nm, ×0.44)

        # SRAM from CACTI: 4096 KB total @ 22nm ≈ 3.40 mm²
        node_sram_area_mm2=2.55,        # 3072 KB node SRAM
        children_sram_area_mm2=0.85,    # 1024 KB children SRAM
    ),
}


class BoardConfigManager:
    """Manages board configurations and component loading"""

    def __init__(self):
        self._configs = BOARD_CONFIGS
        self._current_config: BoardConfig = None

    def get_config(self, board_size: BoardSize) -> BoardConfig:
        """Get configuration for a specific board size"""
        return self._configs.get(board_size)

    def set_current(self, board_size: BoardSize) -> None:
        """Set the current board configuration"""
        self._current_config = self._configs.get(board_size)
        if self._current_config is None:
            raise ValueError(f"Invalid board size: {board_size}")

    @property
    def current(self) -> BoardConfig:
        """Get current board configuration"""
        if self._current_config is None:
            raise ValueError("No board configuration set")
        return self._current_config

    def print_specs(self, board_size: BoardSize) -> None:
        """Print hardware specifications for a board size"""
        board_config = self.get_config(board_size)
        if board_config is None:
            print(f"Invalid board size: {board_size}")
            return

        print(f"\n{'='*60}")
        print(f"Accelerator {board_config.board_size}x{board_config.board_size} Hardware Specifications")
        print(f"{'='*60}")
        print(f"\nBoard Configuration:")
        print(f"  Board Size: {board_config.board_size}x{board_config.board_size}")
        print(f"  Positions: {board_config.num_positions}")
        print(f"  CAM Entries: {board_config.cam_entries}")
        print(f"  Node SRAM: {board_config.node_sram_kb} KB")
        print(f"  Children SRAM: {board_config.children_sram_kb} KB")
        print(f"  Total SRAM: {board_config.sram_size_kb} KB")
        print(f"  Crossbar Size: {board_config.crossbar_size}x{board_config.crossbar_size}")
        print(f"  Max Children: {board_config.max_children}")
        print(f"  Rollout Depth: {board_config.rollout_depth}")
        # exploration_constant moved to performance_config.py — see that module's
        # PERFORMANCE_CONFIGS dict for per-(board, perf_level) values.

        print(f"\nComponent Specifications:")
        print(f"  Selection Unit:       {board_config.selection_gates:4d} gates, "
              f"{board_config.selection_area_mm2:.8f} mm², {board_config.selection_power_mw:.2f} mW")
        print(f"  Expansion Unit:       {board_config.expansion_gates:4d} gates, "
              f"{board_config.expansion_area_mm2:.8f} mm², {board_config.expansion_power_mw:.2f} mW")
        print(f"  Rollout Unit:         {board_config.rollout_gates:4d} gates, "
              f"{board_config.rollout_total_area_mm2:.8f} mm², {board_config.rollout_power_mw_computed:.2f} mW")
        print(f"  Backpropagation Unit: {board_config.backprop_gates:4d} gates, "
              f"{board_config.backprop_area_mm2:.8f} mm², {board_config.backprop_power_mw:.2f} mW")
        print(f"  FSM Controller:       {board_config.fsm_gates:4d} gates, "
              f"{board_config.fsm_area_mm2:.8f} mm², {board_config.fsm_power_mw:.2f} mW")

        print(f"\nTCAM FSM Specifications:")
        print(f"  TCAM Rows:            {board_config.tcam_rows} rows × {board_config.tcam_bits_per_row} bits")
        print(f"  TCAM Area:            {board_config.tcam_area_mm2:.8f} mm² ({board_config.tcam_area_mm2*1e6:.1f} μm²)")
        print(f"  TCAM Dynamic Power:   {board_config.tcam_power_mw:.4f} mW @ 100 MHz (partitioned)")
        print(f"  TCAM Leakage Power:   {board_config.tcam_leakage_mw:.6f} mW ({board_config.tcam_leakage_mw*1e6:.1f} nW)")
        print(f"  Total TCAM Power:     {board_config.tcam_power_mw + board_config.tcam_leakage_mw:.4f} mW")

        print(f"\nMemory Arrays:")
        print(f"  CAM Array:            {board_config.cam_array_area_mm2:.6f} mm² ({board_config.cam_entries} entries × {board_config.cam_bits_per_entry} bits)")
        print(f"  Node SRAM:            {board_config.node_sram_area_mm2:.4f} mm² ({board_config.node_sram_kb} KB)")
        print(f"  Children SRAM:        {board_config.children_sram_area_mm2:.4f} mm² ({board_config.children_sram_kb} KB)")
        print(f"  Total SRAM:           {board_config.sram_array_area_mm2:.4f} mm² ({board_config.sram_size_kb} KB)")

        print(f"\nTotal System:")
        print(f"  Total Gates:          {board_config.total_gates} (TCAM uses cells, not gates)")
        print(f"  Digital Logic Area:   {board_config.digital_logic_area_mm2:.6f} mm²")
        print(f"  Memory Array Area:    {board_config.cam_array_area_mm2 + board_config.sram_array_area_mm2:.4f} mm²")
        print(f"  Total Area:           {board_config.total_area_mm2:.4f} mm² (digital + memory)")
        print(f"  Total Power:          {board_config.total_power_mw:.2f} mW (includes TCAM)")
        print(f"  Total with Leakage:   {board_config.total_power_with_tcam_leakage_mw:.2f} mW")
        print(f"{'='*60}\n")


# Global configuration manager
_config_manager = BoardConfigManager()


def get_board_config(board_size: BoardSize) -> BoardConfig:
    """Get board configuration (convenience function)"""
    return _config_manager.get_config(board_size)


def print_board_specs(board_size: BoardSize) -> None:
    """Print board specifications (convenience function)"""
    _config_manager.print_specs(board_size)
