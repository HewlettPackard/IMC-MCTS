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
        self.nodes_created = 0
        self.backprop_updates = 0

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
        self.nodes_created = self.system_component.total_nodes_created
        self.backprop_updates = self.system_component.total_backprop_updates

        # Prefer measured tree depth over the legacy
        # hardcoded `avg_path_depth = 3`. The system component records every
        # iteration's path length (added in mcts_sst_components.py), so we
        # know what the tree actually looked like during this run instead
        # of guessing.
        measured_depth = getattr(self.system_component, "mean_path_depth", 0.0)
        self.mean_path_depth = measured_depth if measured_depth > 0 else 3.0
        self.max_path_depth = getattr(self.system_component, "max_path_depth", 0)

        # Count logical entries. Physical bank accesses require a memory map.
        self._estimate_component_operations()

    def _estimate_component_operations(self):
        """Read transaction counters, or retain proxies for legacy callers."""
        memory = getattr(self.system_component, 'memory', None)
        if memory is not None:
            counts = memory.operations
            self.cam_lookups = counts['cam_searches']
            self.ucb1_computations = counts['ucb_operations']
            self.sram_reads = counts['node_sram_read_words'] + counts['child_sram_read_words']
            self.sram_writes = counts['node_sram_write_words'] + counts['child_sram_write_words']
            self.crossbar_inferences = self.total_rollouts
            return
        # CAM lookups follow the timing model's one-lookup-per-path-node rule.
        # UCB1 remains a proxy, not the count of candidate-score arithmetic.
        self.cam_lookups = sum(self.system_component.path_depths)
        self.ucb1_computations = self.cam_lookups

        # Node creation and backprop touch actual logical metadata entries.
        # Child-pointer writes, board transfers, and selection reads are outside
        # these legacy SRAM counters; do not use them as complete bus traffic.
        self.sram_writes = self.nodes_created

        # Rollout: each rollout runs crossbar inference.
        self.crossbar_inferences = self.total_rollouts

        # Backpropagation: updates nodes along path (SRAM read + write).
        self.sram_reads = self.backprop_updates
        self.sram_writes += self.backprop_updates

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
        memory = getattr(self.system_component, 'memory', None)
        if memory is not None:
            result = {}
            phases = [('selection_unit', ['selection'], self.total_selections),
                      ('expansion_unit', ['expansion', 'expansion_commit'], self.total_expansions),
                      ('rollout_unit', ['rollout'], self.total_rollouts),
                      ('backprop_unit', ['backprop'], self.total_backprops),
                      ('initialization', ['initialize'], 1)]
            for name, phase_names, invocations in phases:
                row = {'invocations': invocations, 'sram_reads': 0, 'sram_writes': 0,
                       'cam_lookups': 0, 'ucb1_computations': 0, 'crossbar_inferences': 0}
                for phase in phase_names:
                    counts = memory.phase_operations.get(phase, {})
                    row['sram_reads'] += counts.get('node_sram_read_words', 0) + counts.get('child_sram_read_words', 0)
                    row['sram_writes'] += counts.get('node_sram_write_words', 0) + counts.get('child_sram_write_words', 0)
                    row['cam_lookups'] += counts.get('cam_searches', 0)
                    row['ucb1_computations'] += counts.get('ucb_operations', 0)
                    row['crossbar_inferences'] += counts.get('rollout_operations', 0)
                result[name] = row
            return result
        return {
            'selection_unit': {
                'invocations': self.total_selections,
                'cam_lookups': self.cam_lookups,
                'ucb1_computations': self.ucb1_computations
            },
            'expansion_unit': {
                'invocations': self.total_expansions,
                'sram_writes': self.nodes_created
            },
            'rollout_unit': {
                'invocations': self.total_rollouts,
                'crossbar_inferences': self.crossbar_inferences
            },
            'backprop_unit': {
                'invocations': self.total_backprops,
                'sram_reads': self.backprop_updates,
                'sram_writes': self.backprop_updates,
            },
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get complete activity summary"""
        if getattr(self.system_component, 'memory', None) is not None:
            excluded = ['host/chip-level traffic', 'physical bit transitions']
            if self.system_component.memory.neural is None:
                excluded.insert(0, 'neural internal transfers')
            else:
                excluded.append('nonvolatile weight programming')
            return {
                'iterations': self.get_iteration_statistics(),
                'operations': self.get_operation_counts(),
                'components': self.get_component_activity(),
                'operation_count_basis': {
                    'cam_lookups': 'executed parent-key searches including retry after fill',
                    'ucb1_computations': 'executed visited-candidate scores; zero-visit checks counted separately in memory',
                    'sram_reads': '32-bit words across node, board, scratch, cache metadata, and child SRAM',
                    'sram_writes': '32-bit words across node, board, scratch, cache metadata, and child SRAM',
                    'excluded': excluded,
                },
            }
        return {
            'iterations': self.get_iteration_statistics(),
            'operations': self.get_operation_counts(),
            'components': self.get_component_activity(),
            'operation_count_basis': {
                'cam_lookups': 'modeled lookup per selected path node, not measured CAM activity',
                'ucb1_computations': 'legacy path-node proxy; candidate arithmetic not counted',
                'sram_reads': 'logical backprop metadata entries only',
                'sram_writes': 'logical created-node plus backprop metadata entries only',
                'excluded': ['selection reads', 'child-pointer writes', 'parent child-list updates',
                             'board transfers', 'bank-port transactions'],
            },
        }

    def __str__(self) -> str:
        return (f"ActivityTracker({self.total_iterations} iterations, "
                f"{self.total_selections} selections, "
                f"{self.tree_size} nodes)")
