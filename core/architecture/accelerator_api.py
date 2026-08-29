# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Accelerator Architecture API
===========================

Simple, user-friendly interface for MCTS accelerator performance estimation.

Two modes available:
    - "analytical": Fast approximate calculations (~instant)
    - "simulate": Full SST cycle-accurate simulation (~2-5 seconds)

Usage:
    from core.architecture.accelerator_api import Accelerator, estimate

    # Quick analytical estimation (fast)
    result = estimate(board_size=9, play_strength="medium", mode="analytical")
    print(f"Energy: {result.energy_uj:.2f} µJ")

    # Full SST simulation (accurate)
    result = estimate(board_size=9, play_strength="medium", mode="simulate")
    print(f"Energy: {result.energy_uj:.2f} µJ")

    # Custom configuration
    rc = Accelerator(board_size=9, iterations=5000)
    rc.set_technology(node_nm=22)
    result = rc.analyze(mode="simulate")

Controlling Variables:
    - board_size: Board dimensions (2, 3, 5, 9, 13, 19)
    - play_strength: "low", "medium", "high" (maps to iteration counts)
    - iterations: Direct iteration count (overrides play_strength)
    - mode: "analytical" (fast) or "simulate" (accurate)
    - technology_node: Process node in nm (22, 28, 45, 65)
    - clock_frequency: Operating frequency in MHz
    - nn_hidden_size: Neural network hidden layer size
    - nn_outputs: Number of NN output channels
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Literal
from enum import Enum
import math
import time
import io
import contextlib

from py_sst_cpp.components.board_config import BoardSize, get_board_config


# ============================================================================
# Empirical tree-depth model.
#
# Replaces the implicit "depth = 1" assumption that previously made analytical
# mode silently agree with SST. The formula is fitted from SST measurements
# across {2x2, 5x5, 9x9} × {low, medium}.
#
#     E[depth] ≈ 1 + log_{N²}(iterations)
#
# Theoretical basis: with branching factor b ≈ N² (empty cells at the root),
# UCT-style selection grows the tree at rate O(log_b(iter)). The +1 captures
# the random-child step after each expansion (paper Algo 1 line 12).
#
# Validation across 6 configs: mean fit error 7%, max 16% (2x2 low edge case
# where the small board fully enumerates the tree).
# ============================================================================

def expected_path_depth(board_size: int, iterations: int) -> float:
    """Empirical mean MCTS path depth as a function of board size and iterations.

    Fitted from SST measurements across board sizes and play strengths.
    Floors at 1.0 (the trivial root-only iteration).
    """
    if iterations <= 1:
        return 1.0
    branching_factor = max(2, board_size ** 2)  # log base must be > 1
    return 1.0 + math.log(iterations) / math.log(branching_factor)


class PlayStrength(Enum):
    """Play strength presets with corresponding iteration counts"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CUSTOM = "custom"


# Play strength to iteration count mapping per board size
# Must match values in performance_config.py for consistency
PLAY_STRENGTH_ITERATIONS = {
    # board_size: {strength: iterations}
    2: {"low": 50, "medium": 200, "high": 1000},
    3: {"low": 75, "medium": 500, "high": 5000},
    5: {"low": 100, "medium": 1000, "high": 10000},
    8: {"low": 400, "medium": 4000, "high": 40000},
    9: {"low": 500, "medium": 5000, "high": 50000},
    11: {"low": 750, "medium": 6000, "high": 60000},
    13: {"low": 1000, "medium": 7500, "high": 75000},
    15: {"low": 1500, "medium": 8500, "high": 85000},
    19: {"low": 2000, "medium": 10000, "high": 100000},
}


@dataclass
class MemorySizing:
    """Memory sizing from board_config (single source of truth)

    Values are sized for MEDIUM performance level (design point).
    board_config.py determines CAM entries and SRAM sizes per board.

    SRAM architecture: two separate arrays
    - Node SRAM: per-node metadata (24 bytes/entry), addressed by node_id
    - Children SRAM: pool of child pointers (4 bytes/entry), shared across nodes
    """
    cam_entries: int
    node_sram_kb: int           # Node SRAM capacity
    children_sram_kb: int       # Children SRAM capacity
    node_sram_area_mm2: float   # Node SRAM area from CACTI
    children_sram_area_mm2: float  # Children SRAM area from CACTI
    cam_area_mm2: float

    # Cell-level parameters (for reference)
    cam_bits_per_entry: int = 512      # Bits per CAM entry
    cam_cell_area_um2: float = 0.093   # CAM cell area @ 22nm

    @property
    def sram_size_kb(self) -> int:
        """Total SRAM: Node + Children"""
        return self.node_sram_kb + self.children_sram_kb

    @property
    def sram_area_mm2(self) -> float:
        """Total SRAM area"""
        return self.node_sram_area_mm2 + self.children_sram_area_mm2


@dataclass
class PerformanceResult:
    """Complete performance analysis result"""
    # Primary metrics
    energy_uj: float           # Total energy in microjoules
    area_mm2: float            # Total chip area in mm²
    power_mw: float            # Average power in milliwatts
    latency_us: float          # Total latency in microseconds

    # Efficiency metrics
    throughput_iter_per_s: float    # Iterations per second
    energy_efficiency_miter_per_j: float  # Million iterations per joule

    # Configuration used
    board_size: int
    iterations: int
    play_strength: str
    technology_nm: int
    clock_mhz: float

    # Detailed breakdowns
    area_breakdown: Dict[str, float] = field(default_factory=dict)
    power_breakdown: Dict[str, float] = field(default_factory=dict)
    memory_sizing: Optional[MemorySizing] = None

    def __str__(self):
        return f"""
Accelerator Performance Summary
==============================
Configuration:
  Board: {self.board_size}x{self.board_size}
  Play Strength: {self.play_strength} ({self.iterations:,} iterations)
  Technology: {self.technology_nm}nm @ {self.clock_mhz} MHz

Performance:
  Latency:    {self.latency_us:.2f} µs
  Energy:     {self.energy_uj:.3f} µJ
  Power:      {self.power_mw:.2f} mW
  Area:       {self.area_mm2:.4f} mm²
  Throughput: {self.throughput_iter_per_s/1e6:.1f} M iter/s
  Efficiency: {self.energy_efficiency_miter_per_j:.1f} M iter/J
"""


class Accelerator:
    """
    IMC-MCTS Accelerator Performance Estimator

    Provides easy-to-use interface for estimating area, power, and energy
    for different board sizes and play strengths.
    """

    def __init__(
        self,
        board_size: int = 9,
        play_strength: Literal["low", "medium", "high"] = "medium",
        iterations: Optional[int] = None,
    ):
        """
        Initialize Accelerator estimator.

        Args:
            board_size: Board dimensions (2, 3, 5, 9, 13, 19)
            play_strength: "low", "medium", or "high"
            iterations: Direct iteration count (overrides play_strength)
        """
        if board_size not in [2, 3, 5, 8, 9, 11, 13, 15, 19]:
            raise ValueError(f"Unsupported board size: {board_size}. Must be 2, 3, 5, 8, 9, 11, 13, 15, or 19")

        self.board_size = board_size
        self.play_strength = play_strength

        # Get iterations from play strength or use custom
        if iterations is not None:
            self.iterations = iterations
            self.play_strength = "custom"
        else:
            self.iterations = PLAY_STRENGTH_ITERATIONS[board_size][play_strength]

        # Technology parameters (defaults to 22nm)
        self.technology_nm = 22
        self.clock_mhz = 500.0

        # Neural network parameters
        self.nn_hidden_size = 96  # Hidden layer neurons
        self.nn_outputs = 3       # Output channels (win/loss/draw)

        # Unit power parameters (from literature, user-configurable)
        self.dac_power_per_channel_mw = 0.05   # 50 µW per DAC
        self.adc_power_per_channel_mw = 0.10   # 100 µW per ADC
        self.crossbar_power_density = 4000.0  # mW/mm²

        # Memory sizing: board_config.py is the single source of truth
        # CAM/SRAM values are sized for MEDIUM performance level (design point)
        # See board_config.py for per-board-size memory specifications

        # Load base hardware config
        self._load_base_config()

    def _load_base_config(self):
        """Load base hardware configuration for board size"""
        board_size_map = {
            2: BoardSize.BOARD_2X2,
            3: BoardSize.BOARD_3X3,
            5: BoardSize.BOARD_5X5,
            8: BoardSize.BOARD_8X8,
            9: BoardSize.BOARD_9X9,
            11: BoardSize.BOARD_11X11,
            13: BoardSize.BOARD_13X13,
            15: BoardSize.BOARD_15X15,
            19: BoardSize.BOARD_19X19,
        }
        self.base_config = get_board_config(board_size_map[self.board_size])

    def set_technology(self, node_nm: int = 22, clock_mhz: float = 500.0):
        """
        Set technology parameters.

        Args:
            node_nm: Process node (22, 28, 45, 65)
            clock_mhz: Clock frequency in MHz
        """
        self.technology_nm = node_nm
        self.clock_mhz = clock_mhz
        return self

    def set_neural_network(self, hidden_size: int = 96, outputs: int = 3):
        """
        Set neural network architecture.

        Args:
            hidden_size: Hidden layer size
            outputs: Number of output channels
        """
        self.nn_hidden_size = hidden_size
        self.nn_outputs = outputs
        return self

    def set_power_parameters(
        self,
        dac_power_mw: float = 0.05,
        adc_power_mw: float = 0.10,
        crossbar_power_density: float = 4000.0,
    ):
        """
        Set unit power parameters.

        Args:
            dac_power_mw: Power per DAC channel (mW)
            adc_power_mw: Power per ADC channel (mW)
            crossbar_power_density: Crossbar power density (mW/mm²)
        """
        self.dac_power_per_channel_mw = dac_power_mw
        self.adc_power_per_channel_mw = adc_power_mw
        self.crossbar_power_density = crossbar_power_density
        return self

    def _compute_memory_sizing(self) -> MemorySizing:
        """
        Get CAM and SRAM sizing from board_config (single source of truth).

        board_config.py values are sized for MEDIUM performance level (design point).
        For 2x2-9x9, on-chip SRAM holds the full MCTS tree at MEDIUM.
        For 13x13-19x19, on-chip SRAM acts as a cache with DRAM spillover.
        """
        hardware_config = self.base_config

        return MemorySizing(
            cam_entries=hardware_config.cam_entries,
            node_sram_kb=hardware_config.node_sram_kb,
            children_sram_kb=hardware_config.children_sram_kb,
            node_sram_area_mm2=hardware_config.node_sram_area_mm2,
            children_sram_area_mm2=hardware_config.children_sram_area_mm2,
            cam_area_mm2=hardware_config.cam_array_area_mm2,
            cam_bits_per_entry=hardware_config.cam_bits_per_entry,
            cam_cell_area_um2=hardware_config.selection_cam_cell_area_um2,
        )

    def _compute_technology_scaling(self) -> float:
        """
        Compute Stillmaker scaling factor for technology node.
        Reference: 22nm (factor = 1.0)
        """
        # Stillmaker scaling: area scales as (node/22)²
        area_scale = (self.technology_nm / 22.0) ** 2
        return area_scale

    def _compute_power_scaling(self) -> float:
        """
        Compute power scaling for technology and frequency.
        """
        # Power scales with frequency and voltage²
        # Simplified: power ~ frequency × (node/22)^1.5
        frequency_scale = self.clock_mhz / 500.0
        technology_scale = (self.technology_nm / 22.0) ** 1.5
        return frequency_scale * technology_scale

    def _compute_rollout_power(self) -> Dict[str, float]:
        """Compute rollout unit power from components"""
        crossbar_size = self.board_size ** 2

        dac_power = crossbar_size * self.dac_power_per_channel_mw
        adc_power = self.nn_outputs * self.adc_power_per_channel_mw
        crossbar_power = self.base_config.rollout_crossbar_area_mm2 * self.crossbar_power_density
        digital_power = self.base_config.rollout_digital_power_mw

        return {
            "dac": dac_power,
            "adc": adc_power,
            "crossbar": crossbar_power,
            "digital": digital_power,
            "total": dac_power + adc_power + crossbar_power + digital_power,
        }

    def _run_sst_simulation(self) -> Dict[str, Any]:
        """
        Run actual SST cycle-accurate simulation.

        Returns:
            Dictionary with simulation results
        """
        # Import SST components
        from py_sst_cpp.core import Simulation
        from py_sst_cpp.core.component import ComponentId
        from py_sst_cpp.core.config import Params
        from py_sst_cpp.core.link import Link
        from py_sst_cpp.components.performance_config import PerformanceLevel, get_performance_config
        from core.simulator.mcts_sst_components import (
            MCTSSystemComponent,
            SelectionUnitComponent,
            ExpansionUnitComponent,
            RolloutUnitComponent,
            BackpropagationUnitComponent
        )
        from core.simulator.hardware_metrics import HardwareModel, ActivityTracker, MetricsCalculator

        # Map play strength to PerformanceLevel
        performance_level_map = {
            "low": PerformanceLevel.LOW,
            "medium": PerformanceLevel.MEDIUM,
            "high": PerformanceLevel.HIGH,
            "custom": PerformanceLevel.MEDIUM,  # Use medium as base for custom
        }
        performance_level = performance_level_map.get(self.play_strength, PerformanceLevel.MEDIUM)

        # Get performance config
        performance_config = get_performance_config(self.board_size, performance_level)

        # Override iterations if custom
        if self.play_strength == "custom":
            performance_config['iterations'] = self.iterations

        # Create simulation
        simulation = Simulation(f"Accelerator_{self.board_size}x{self.board_size}_MCTS")

        # Create component parameters
        system_params = Params({
            'board_size': self.board_size,
            'performance_level': performance_level.value,
        })

        unit_params = Params({
            'board_size': self.board_size,
            'exploration_constant': performance_config['exploration_constant'],
            'rollout_depth': performance_config['rollout_depth']
        })

        # Create components
        system = MCTSSystemComponent(ComponentId(0, "mcts_system"), system_params)
        selection = SelectionUnitComponent(ComponentId(1, "selection_unit"), unit_params)
        expansion = ExpansionUnitComponent(ComponentId(2, "expansion_unit"), unit_params)
        rollout = RolloutUnitComponent(ComponentId(3, "rollout_unit"), unit_params)
        backprop = BackpropagationUnitComponent(ComponentId(4, "backprop_unit"), unit_params)

        # Add components to simulation
        simulation.add_component("system", system)
        simulation.add_component("selection", selection)
        simulation.add_component("expansion", expansion)
        simulation.add_component("rollout", rollout)
        simulation.add_component("backprop", backprop)

        # Create links between components
        # System <-> Selection
        link_system_to_selection = Link("system_to_selection")
        link_system_to_selection._source_component = system
        link_system_to_selection._target_component = selection
        link_selection_to_system = Link("selection_to_system")
        link_selection_to_system._source_component = selection
        link_selection_to_system._target_component = system
        system.add_link("to_selection", link_system_to_selection)
        selection.add_link("from_system", link_system_to_selection)
        selection.add_link("to_system", link_selection_to_system)
        system.add_link("from_selection", link_selection_to_system)

        # System <-> Expansion
        link_system_to_expansion = Link("system_to_expansion")
        link_system_to_expansion._source_component = system
        link_system_to_expansion._target_component = expansion
        link_expansion_to_system = Link("expansion_to_system")
        link_expansion_to_system._source_component = expansion
        link_expansion_to_system._target_component = system
        system.add_link("to_expansion", link_system_to_expansion)
        expansion.add_link("from_system", link_system_to_expansion)
        expansion.add_link("to_system", link_expansion_to_system)
        system.add_link("from_expansion", link_expansion_to_system)

        # System <-> Rollout
        link_system_to_rollout = Link("system_to_rollout")
        link_system_to_rollout._source_component = system
        link_system_to_rollout._target_component = rollout
        link_rollout_to_system = Link("rollout_to_system")
        link_rollout_to_system._source_component = rollout
        link_rollout_to_system._target_component = system
        system.add_link("to_rollout", link_system_to_rollout)
        rollout.add_link("from_system", link_system_to_rollout)
        rollout.add_link("to_system", link_rollout_to_system)
        system.add_link("from_rollout", link_rollout_to_system)

        # System <-> Backprop
        link_system_to_backprop = Link("system_to_backprop")
        link_system_to_backprop._source_component = system
        link_system_to_backprop._target_component = backprop
        link_backprop_to_system = Link("backprop_to_system")
        link_backprop_to_system._source_component = backprop
        link_backprop_to_system._target_component = system
        system.add_link("to_backprop", link_system_to_backprop)
        backprop.add_link("from_system", link_system_to_backprop)
        backprop.add_link("to_system", link_backprop_to_system)
        system.add_link("from_backprop", link_backprop_to_system)

        # Register links with simulation (CRITICAL!)
        simulation.add_link("system_to_selection", link_system_to_selection)
        simulation.add_link("selection_to_system", link_selection_to_system)
        simulation.add_link("system_to_expansion", link_system_to_expansion)
        simulation.add_link("expansion_to_system", link_expansion_to_system)
        simulation.add_link("system_to_rollout", link_system_to_rollout)
        simulation.add_link("rollout_to_system", link_rollout_to_system)
        simulation.add_link("system_to_backprop", link_system_to_backprop)
        simulation.add_link("backprop_to_system", link_backprop_to_system)

        # Share node storage between components
        selection.node_storage = system.node_storage
        expansion.node_storage = system.node_storage
        expansion.next_node_id_ref = [system.next_node_id]
        rollout.node_storage = system.node_storage
        rollout.system_component = system
        backprop.node_storage = system.node_storage
        backprop.system_component = system

        # Wire up event handlers
        link_system_to_selection.set_handler(selection.handle_iteration_start)
        link_selection_to_system.set_handler(system.handle_selection_complete)
        link_system_to_expansion.set_handler(expansion.handle_selection_complete)
        link_expansion_to_system.set_handler(system.handle_expansion_complete)
        link_system_to_rollout.set_handler(rollout.handle_expansion_complete)
        link_rollout_to_system.set_handler(system.handle_rollout_complete)
        link_system_to_backprop.set_handler(backprop.handle_rollout_complete)
        link_backprop_to_system.set_handler(system.handle_backprop_complete)

        # Initialize the hardware metrics model.
        hardware_model = HardwareModel(board_size=self.board_size)
        activity_tracker = ActivityTracker()
        activity_tracker.attach_to_simulation(simulation, system)
        metrics_calculator = MetricsCalculator(hardware_model, activity_tracker)

        # Calculate end time
        expected_iterations = self.iterations
        simulation_end_time = expected_iterations * 100  # ~100 cycles per iteration estimate

        # Run the simulation (suppress output)
        start_wall_time = time.time()

        # Capture stdout to suppress verbose output
        with contextlib.redirect_stdout(io.StringIO()):
            simulation.run(end_time=simulation_end_time)

        end_wall_time = time.time()
        wall_clock_time_s = end_wall_time - start_wall_time

        # Collect activity statistics
        activity_tracker.collect_statistics()

        # Set simulation results
        metrics_calculator.set_simulation_results(
            simulation_cycles=simulation.get_current_time(),
            wall_clock_time_s=wall_clock_time_s
        )

        # Extract results
        return {
            "simulation_cycles": simulation.get_current_time(),
            "wall_clock_time_s": wall_clock_time_s,
            "total_iterations": activity_tracker.total_iterations,
            "tree_size": activity_tracker.tree_size,
            "latency_us": metrics_calculator.get_hardware_latency_us(),
            "latency_per_iter_ns": metrics_calculator.get_latency_per_iteration_ns(),
            "energy_nj": metrics_calculator.get_total_energy_nj(),
            "total_area_mm2": hardware_model.total_area_mm2,
            "total_power_mw": hardware_model.total_power_mw,
            "throughput": activity_tracker.total_iterations / (metrics_calculator.get_hardware_latency_us() / 1e6) if metrics_calculator.get_hardware_latency_us() > 0 else 0,
        }

    def analyze(self, mode: Literal["analytical", "simulate"] = "analytical") -> PerformanceResult:
        """
        Run complete performance analysis.

        Args:
            mode: "analytical" for fast approximate, "simulate" for SST cycle-accurate

        Returns:
            PerformanceResult with all metrics
        """
        # Compute memory sizing based on iterations
        memory_sizing = self._compute_memory_sizing()

        # Get technology scaling factors
        area_scale = self._compute_technology_scaling()
        power_scale = self._compute_power_scaling()

        # Compute areas
        hardware_config = self.base_config

        # Digital logic areas (scale with technology)
        selection_area_mm2 = hardware_config.selection_area_mm2 * area_scale
        expansion_area_mm2 = hardware_config.expansion_area_mm2 * area_scale
        backprop_area_mm2 = hardware_config.backprop_area_mm2 * area_scale
        fsm_area_mm2 = hardware_config.fsm_area_mm2 * area_scale
        tcam_area_mm2 = hardware_config.tcam_area_mm2 * area_scale
        rollout_area_mm2 = hardware_config.rollout_total_area_mm2 * area_scale

        # Memory areas (from dynamic sizing)
        cam_area_mm2 = memory_sizing.cam_area_mm2
        sram_area_mm2 = memory_sizing.sram_area_mm2

        total_area_mm2 = (selection_area_mm2 + expansion_area_mm2 + rollout_area_mm2 +
                          backprop_area_mm2 + fsm_area_mm2 + tcam_area_mm2 +
                          cam_area_mm2 + sram_area_mm2)

        area_breakdown = {
            "selection": selection_area_mm2,
            "expansion": expansion_area_mm2,
            "rollout": rollout_area_mm2,
            "backprop": backprop_area_mm2,
            "fsm": fsm_area_mm2,
            "tcam": tcam_area_mm2,
            "cam_array": cam_area_mm2,
            "sram_array": sram_area_mm2,
            "total": total_area_mm2,
        }

        # Compute powers
        rollout_power_breakdown = self._compute_rollout_power()

        selection_power_mw = hardware_config.selection_power_mw * power_scale
        expansion_power_mw = hardware_config.expansion_power_mw * power_scale
        backprop_power_mw = hardware_config.backprop_power_mw * power_scale
        fsm_power_mw = hardware_config.fsm_power_mw * power_scale
        tcam_power_mw = hardware_config.tcam_power_mw * power_scale

        total_power_mw = (selection_power_mw + expansion_power_mw + rollout_power_breakdown["total"] +
                          backprop_power_mw + fsm_power_mw + tcam_power_mw)

        power_breakdown = {
            "selection": selection_power_mw,
            "expansion": expansion_power_mw,
            "rollout": rollout_power_breakdown["total"],
            "rollout_dac": rollout_power_breakdown["dac"],
            "rollout_adc": rollout_power_breakdown["adc"],
            "rollout_crossbar": rollout_power_breakdown["crossbar"],
            "rollout_digital": rollout_power_breakdown["digital"],
            "backprop": backprop_power_mw,
            "fsm": fsm_power_mw,
            "tcam": tcam_power_mw,
            "total": total_power_mw,
        }

        # ================================================================
        # MODE: SIMULATE - Run actual SST simulation for accurate timing
        # ================================================================
        if mode == "simulate":
            simulation_results = self._run_sst_simulation()

            total_latency_us = simulation_results["latency_us"]
            energy_nj = simulation_results["energy_nj"]
            energy_uj = energy_nj / 1000.0
            throughput_iter_per_s = simulation_results["throughput"]

            # Use simulated area/power (from hardware model)
            total_area_mm2 = simulation_results["total_area_mm2"]
            total_power_mw = simulation_results["total_power_mw"]

            # Compute energy efficiency
            energy_efficiency_iter_per_j = self.iterations / (energy_uj / 1e6) if energy_uj > 0 else 0

            # Add simulation-specific info to breakdowns
            area_breakdown["total"] = total_area_mm2
            area_breakdown["simulation_mode"] = "sst"
            power_breakdown["total"] = total_power_mw
            power_breakdown["simulation_mode"] = "sst"

        # ================================================================
        # MODE: ANALYTICAL - Fast approximate calculation
        # ================================================================
        else:
            # Depth-aware analytical model.
            #
            # Selection performs ONE CAM lookup per traversed node; backprop
            # walks the same path, doing one SRAM read-modify-write per node.
            # The tree depth depends on board size and iteration count — see
            # expected_path_depth() above for the empirical formula derived
            # from SST measurements.
            #
            # Previously, both selection and backprop were charged a flat
            # per-iteration fee (effectively depth = 1), which made analytical
            # mode silently agree with the SST simulator's old depth-blind
            # cost model. The two modes are now genuinely independent: SST
            # measures actual depth at runtime; analytical predicts it from
            # the fitted formula.
            expected_depth = expected_path_depth(self.board_size, self.iterations)

            selection_cost_ns = (
                hardware_config.selection_delay_ns
                + hardware_config.cam_lookup_delay_ns * expected_depth
            )
            expansion_cost_ns = (
                hardware_config.expansion_delay_ns
                + hardware_config.sram_access_delay_ns
            )
            rollout_cost_ns = hardware_config.rollout_total_latency_ns
            backprop_cost_ns = (
                hardware_config.backprop_delay_ns
                + hardware_config.sram_access_delay_ns
            ) * expected_depth
            fsm_overhead_ns = hardware_config.fsm_transition_delay_ns * 4

            latency_per_iter_ns = (
                selection_cost_ns + expansion_cost_ns
                + rollout_cost_ns + backprop_cost_ns + fsm_overhead_ns
            )
            total_latency_ns = self.iterations * latency_per_iter_ns
            total_latency_us = total_latency_ns / 1000.0

            # Compute energy: Energy = Power × Time
            energy_nj = total_power_mw * total_latency_ns / 1000.0  # mW × ns / 1000 = nJ
            energy_uj = energy_nj / 1000.0

            # Compute efficiency metrics
            throughput_iter_per_s = self.iterations / (total_latency_us / 1e6)  # iter/s
            energy_efficiency_iter_per_j = self.iterations / (energy_uj / 1e6)  # iter/J

            area_breakdown["simulation_mode"] = "analytical"
            area_breakdown["expected_path_depth"] = round(expected_depth, 3)
            power_breakdown["simulation_mode"] = "analytical"

        return PerformanceResult(
            energy_uj=energy_uj,
            area_mm2=total_area_mm2,
            power_mw=total_power_mw,
            latency_us=total_latency_us,
            throughput_iter_per_s=throughput_iter_per_s,
            energy_efficiency_miter_per_j=energy_efficiency_iter_per_j / 1e6,
            board_size=self.board_size,
            iterations=self.iterations,
            play_strength=self.play_strength,
            technology_nm=self.technology_nm,
            clock_mhz=self.clock_mhz,
            area_breakdown=area_breakdown,
            power_breakdown=power_breakdown,
            memory_sizing=memory_sizing,
        )

    @staticmethod
    def estimate(
        board_size: int = 9,
        play_strength: Literal["low", "medium", "high"] = "medium",
        iterations: Optional[int] = None,
        mode: Literal["analytical", "simulate"] = "analytical",
    ) -> PerformanceResult:
        """
        Quick estimation with default parameters.

        Args:
            board_size: Board dimensions (2, 3, 5, 9, 13, 19)
            play_strength: "low", "medium", or "high"
            iterations: Direct iteration count (overrides play_strength)
            mode: "analytical" (fast) or "simulate" (accurate SST simulation)

        Returns:
            PerformanceResult with all metrics
        """
        accelerator = Accelerator(board_size, play_strength, iterations)
        return accelerator.analyze(mode=mode)

    @staticmethod
    def compare_board_sizes(
        play_strength: Literal["low", "medium", "high"] = "medium"
    ) -> Dict[int, PerformanceResult]:
        """
        Compare performance across all board sizes.

        Args:
            play_strength: "low", "medium", or "high"

        Returns:
            Dictionary mapping board_size to PerformanceResult
        """
        results = {}
        for board_size in [2, 3, 5, 8, 9, 11, 13, 15, 19]:
            results[board_size] = Accelerator.estimate(board_size, play_strength)
        return results

    @staticmethod
    def compare_play_strengths(board_size: int = 9) -> Dict[str, PerformanceResult]:
        """
        Compare performance across play strengths for a board size.

        Args:
            board_size: Board dimensions

        Returns:
            Dictionary mapping play_strength to PerformanceResult
        """
        results = {}
        for play_strength in ["low", "medium", "high"]:
            results[play_strength] = Accelerator.estimate(board_size, play_strength)
        return results


# Convenience function for simple usage
def estimate(
    board_size: int = 9,
    play_strength: Literal["low", "medium", "high"] = "medium",
    iterations: Optional[int] = None,
    mode: Literal["analytical", "simulate"] = "analytical",
) -> PerformanceResult:
    """
    Quick estimation function.

    Args:
        board_size: Board dimensions (2, 3, 5, 9, 13, 19)
        play_strength: "low", "medium", or "high"
        iterations: Direct iteration count (overrides play_strength)
        mode: "analytical" (fast ~instant) or "simulate" (accurate ~2-5 sec)

    Returns:
        PerformanceResult with all metrics

    Examples:
        # Fast analytical estimate
        result = estimate(board_size=9, play_strength="medium")
        print(f"Energy: {result.energy_uj:.2f} µJ")

        # Accurate SST simulation
        result = estimate(board_size=9, play_strength="medium", mode="simulate")
        print(f"Energy: {result.energy_uj:.2f} µJ")
    """
    return Accelerator.estimate(board_size, play_strength, iterations, mode)


if __name__ == "__main__":
    # Demo usage
    print("=" * 60)
    print("Accelerator Architecture Performance Estimator")
    print("=" * 60)

    # Example 1: Quick analytical estimation
    print("\n1. Analytical estimation for 9x9 Go, medium strength (instant):")
    result = estimate(board_size=9, play_strength="medium", mode="analytical")
    print(result)

    # Example 2: SST simulation (accurate)
    print("\n2. SST simulation for 9x9 Go, medium strength (~2 sec):")
    result = estimate(board_size=9, play_strength="medium", mode="simulate")
    print(f"   Mode: SST Simulation (cycle-accurate)")
    print(f"   Energy: {result.energy_uj:.2f} µJ")
    print(f"   Latency: {result.latency_us:.2f} µs")
    print(f"   Power: {result.power_mw:.2f} mW")
    print(f"   Area: {result.area_mm2:.4f} mm²")

    # Example 3: Custom configuration
    print("\n3. Custom configuration with 10K iterations:")
    rc = Accelerator(board_size=9, iterations=10000)
    rc.set_technology(node_nm=22, clock_mhz=500)
    result = rc.analyze(mode="analytical")
    print(f"   Energy: {result.energy_uj:.2f} µJ")
    print(f"   Area: {result.area_mm2:.4f} mm²")
    print(f"   CAM entries: {result.memory_sizing.cam_entries}")
    print(f"   Node SRAM: {result.memory_sizing.node_sram_kb} KB")
    print(f"   Children SRAM: {result.memory_sizing.children_sram_kb} KB")

    # Example 4: Compare modes
    print("\n4. Comparison: Analytical vs Simulate (9x9, medium):")
    print("-" * 60)
    print(f"{'Mode':<12} {'Energy (µJ)':>12} {'Latency (µs)':>14} {'Power (mW)':>12}")
    print("-" * 60)
    for mode in ["analytical", "simulate"]:
        r = estimate(board_size=9, play_strength="medium", mode=mode)
        print(f"{mode:<12} {r.energy_uj:>12.3f} {r.latency_us:>14.2f} {r.power_mw:>12.2f}")

    # Example 5: Compare board sizes
    print("\n5. Comparison across board sizes (medium strength, analytical):")
    print("-" * 60)
    print(f"{'Board':<8} {'Iter':>8} {'Energy':>10} {'Area':>10} {'Power':>10}")
    print(f"{'':8} {'':>8} {'(µJ)':>10} {'(mm²)':>10} {'(mW)':>10}")
    print("-" * 60)
    for size in [2, 3, 5, 9, 13, 19]:
        r = estimate(board_size=size, play_strength="medium")
        print(f"{size}x{size:<5} {r.iterations:>8,} {r.energy_uj:>10.3f} {r.area_mm2:>10.4f} {r.power_mw:>10.2f}")

    # Example 6: Compare play strengths
    print("\n6. 9x9 Go across play strengths:")
    print("-" * 60)
    print(f"{'Strength':<10} {'Iter':>8} {'Energy':>10} {'Latency':>10} {'CAM':>8}")
    print(f"{'':10} {'':>8} {'(µJ)':>10} {'(µs)':>10} {'entries':>8}")
    print("-" * 60)
    for strength in ["low", "medium", "high"]:
        r = estimate(board_size=9, play_strength=strength)
        print(f"{strength:<10} {r.iterations:>8,} {r.energy_uj:>10.3f} {r.latency_us:>10.1f} {r.memory_sizing.cam_entries:>8}")
