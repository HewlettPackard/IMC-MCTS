# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Activity Tracker - Operation Counting for Performance Analysis
==============================================================

Tracks hardware operations during SST simulation to enable
energy and performance analysis.

Works by extracting statistics from SST components after simulation.
"""

from typing import Dict, Any


class ActivityTracker:
    """
    Tracks hardware activity during SST simulation.

    Extracts operation counts from SST components for performance analysis.
    Similar to how performance counters track CPU operations.
    """

    def __init__(self):
        """Initialize activity tracker"""
        self.system_component = None
        self.simulation = None

        # Activity counters (will be populated from SST components)
        self.total_iterations = 0
        self.total_selections = 0
        self.total_expansions = 0
        self.total_rollouts = 0
        self.total_backprops = 0
        self.tree_size = 0

        # Tree-shape stats. Default 3.0 retained as
        # legacy fallback — overwritten by measured value in collect_statistics.
        self.mean_path_depth: float = 3.0
        self.max_path_depth: int = 0

        # Component-level activity
        self.cam_lookups = 0
        self.ucb1_computations = 0
        self.sram_reads = 0
        self.sram_writes = 0
        self.crossbar_inferences = 0

    def attach_to_simulation(self, simulation, system_component):
        """
        Attach tracker to SST simulation.

        Args:
            simulation: The SST Simulation object
            system_component: The MCTSSystemComponent to track
        """
        self.simulation = simulation
        self.system_component = system_component

    def collect_statistics(self):
        """
        Collect statistics from SST components after simulation.

        This should be called after sim.run() completes.
        """
        if self.system_component is None:
            raise RuntimeError("ActivityTracker not attached to simulation")

        # Extract high-level statistics from MCTSSystemComponent
        self.total_iterations = self.system_component.current_iteration
        self.total_selections = self.system_component.total_selections
        self.total_expansions = self.system_component.total_expansions
        self.total_rollouts = self.system_component.total_rollouts
        self.total_backprops = self.system_component.total_backprops
        self.tree_size = len(self.system_component.node_storage)

        # Prefer measured tree depth over the legacy
        # hardcoded `avg_path_depth = 3`. The system component records every
        # iteration's path length (added in mcts_sst_components.py), so we
        # know what the tree actually looked like during this run instead
        # of guessing.
        measured_depth = getattr(self.system_component, "mean_path_depth", 0.0)
        self.mean_path_depth = measured_depth if measured_depth > 0 else 3.0
        self.max_path_depth = getattr(self.system_component, "max_path_depth", 0)

        # Estimate component-level operations
        self._estimate_component_operations()

    def _estimate_component_operations(self):
        """Estimate low-level hardware operations from high-level counts.

        Uses self.mean_path_depth (set by collect_statistics) — measured from
        the SST run when available, fallback constant otherwise.
        """
        depth = self.mean_path_depth

        # Selection: one CAM lookup + UCB1 compute per node traversed.
        self.cam_lookups = int(self.total_selections * depth)
        self.ucb1_computations = int(self.total_selections * depth)

        # Expansion: each expansion creates new nodes (SRAM writes).
        # Average children per expansion ~10-25 (board dependent)
        avg_children = 10
        self.sram_writes = self.total_expansions * avg_children

        # Rollout: each rollout runs crossbar inference.
        self.crossbar_inferences = self.total_rollouts

        # Backpropagation: updates nodes along path (SRAM read + write).
        self.sram_reads = int(self.total_backprops * depth)
        self.sram_writes += int(self.total_backprops * depth)

    # ========================================================================
    # Query Methods
    # ========================================================================

    def get_iteration_statistics(self) -> Dict[str, int]:
        """Get high-level iteration statistics"""
        return {
            'total_iterations': self.total_iterations,
            'total_selections': self.total_selections,
            'total_expansions': self.total_expansions,
            'total_rollouts': self.total_rollouts,
            'total_backprops': self.total_backprops,
            'tree_size': self.tree_size
        }

    def get_operation_counts(self) -> Dict[str, int]:
        """Get low-level hardware operation counts"""
        return {
            'cam_lookups': self.cam_lookups,
            'ucb1_computations': self.ucb1_computations,
            'sram_reads': self.sram_reads,
            'sram_writes': self.sram_writes,
            'crossbar_inferences': self.crossbar_inferences
        }

    def get_component_activity(self) -> Dict[str, Dict[str, int]]:
        """Get activity breakdown by component"""
        return {
            'selection_unit': {
                'invocations': self.total_selections,
                'cam_lookups': self.cam_lookups,
                'ucb1_computations': self.ucb1_computations
            },
            'expansion_unit': {
                'invocations': self.total_expansions,
                'sram_writes': self.total_expansions * 10  # Approximate
            },
            'rollout_unit': {
                'invocations': self.total_rollouts,
                'crossbar_inferences': self.crossbar_inferences
            },
            'backprop_unit': {
                'invocations': self.total_backprops,
                'sram_reads': int(self.total_backprops * self.mean_path_depth),
                'sram_writes': int(self.total_backprops * self.mean_path_depth),
            },
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get complete activity summary"""
        return {
            'iterations': self.get_iteration_statistics(),
            'operations': self.get_operation_counts(),
            'components': self.get_component_activity()
        }

    def __str__(self) -> str:
        return (f"ActivityTracker({self.total_iterations} iterations, "
                f"{self.total_selections} selections, "
                f"{self.tree_size} nodes)")
