#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
MCTS SST Components - True SST Discrete-Event Simulation
==========================================================

Proper SST Component implementation for MCTS acceleration.
Uses py_sst_cpp's discrete-event simulation engine with:
- Component-based architecture
- Event-driven communication
- Clock-based timing
- Link-based connections
"""

from py_sst_cpp.core.component import Component, ComponentId
from py_sst_cpp.core.event import Event
from py_sst_cpp.core.config import Params
from py_sst_cpp.core.output import Output, OutputLevel
from py_sst_cpp.components.board_config import BoardSize, get_board_config
from py_sst_cpp.components.performance_config import PerformanceLevel, get_performance_config
from typing import List, Optional
import random
import math
import numpy as np
from core.algorithm.evaluator import load_evaluator_checkpoint, effective_weights, encode_board
import hashlib


# ============================================================================
# Clock helper — single source of truth for ns → cycle conversion.
# Replaces the 8 occurrences of `int(delay_ns / 2)  # 500 MHz` scattered
# through the original file.
# ============================================================================

CLOCK_PERIOD_NS = 2.0  # 500 MHz design point (must match metrics_calculator.py)


def _ns_to_cycles(delay_ns: float) -> int:
    """Quantize a continuous-time delay to integer SST cycles.

    Sub-cycle delays round up to 1 cycle (a real synchronous unit cannot
    fire in less than one clock period).
    """
    return max(1, math.ceil(delay_ns / CLOCK_PERIOD_NS))


# ============================================================================
# MCTS Event Types
# ============================================================================

class MCTSEvent(Event):
    """Base class for MCTS events"""
    def __init__(self, iteration: int = 0):
        super().__init__()
        self.iteration = iteration

    def _serialize_data(self):
        return {'iteration': self.iteration}

    def _deserialize_data(self, data):
        self.iteration = data.get('iteration', 0)


class SelectionCompleteEvent(MCTSEvent):
    """Event: Selection phase complete"""
    def __init__(self, iteration: int = 0, path: List[int] = None, node_id: int = 0):
        super().__init__(iteration)
        self.path = path if path is not None else []
        self.node_id = node_id

    def _serialize_data(self):
        data = super()._serialize_data()
        data['path'] = self.path
        data['node_id'] = self.node_id
        return data

    def _deserialize_data(self, data):
        super()._deserialize_data(data)
        self.path = data.get('path', [])
        self.node_id = data.get('node_id', 0)


class ExpansionCompleteEvent(MCTSEvent):
    """Event: Expansion phase complete"""
    def __init__(self, iteration: int = 0, node_id: int = 0, children: List[int] = None):
        super().__init__(iteration)
        self.node_id = node_id
        self.children = children if children is not None else []

    def _serialize_data(self):
        data = super()._serialize_data()
        data['node_id'] = self.node_id
        data['children'] = self.children
        return data

    def _deserialize_data(self, data):
        super()._deserialize_data(data)
        self.node_id = data.get('node_id', 0)
        self.children = data.get('children', [])


class RolloutCompleteEvent(MCTSEvent):
    """Event: Rollout phase complete"""
    def __init__(self, iteration: int = 0, value: float = 0.0, moves: int = 0):
        super().__init__(iteration)
        self.value = value
        self.moves = moves

    def _serialize_data(self):
        data = super()._serialize_data()
        data['value'] = self.value
        data['moves'] = self.moves
        return data

    def _deserialize_data(self, data):
        super()._deserialize_data(data)
        self.value = data.get('value', 0.0)
        self.moves = data.get('moves', 0)


class BackpropCompleteEvent(MCTSEvent):
    """Event: Backpropagation phase complete"""
    def __init__(self, iteration: int = 0, nodes_updated: int = 0):
        super().__init__(iteration)
        self.nodes_updated = nodes_updated

    def _serialize_data(self):
        data = super()._serialize_data()
        data['nodes_updated'] = self.nodes_updated
        return data

    def _deserialize_data(self, data):
        super()._deserialize_data(data)
        self.nodes_updated = data.get('nodes_updated', 0)


class IterationStartEvent(MCTSEvent):
    """Event: Start new MCTS iteration"""
    pass


# ============================================================================
# MCTS System Component (Orchestrator)
# ============================================================================

class MCTSSystemComponent(Component):
    """
    Main MCTS system component that orchestrates the algorithm.

    This component coordinates the MCTS phases and tracks global state.
    """

    def __init__(self, component_id: ComponentId, params: Params):
        super().__init__(component_id, params)

        # Get parameters
        self.board_size = self.get_param_int('board_size', 5)
        perf_level_str = self.get_param_string('performance_level', 'medium')
        self.performance_level = PerformanceLevel(perf_level_str)

        # Get configurations
        board_size_map = {
            2: BoardSize.BOARD_2X2, 3: BoardSize.BOARD_3X3,
            5: BoardSize.BOARD_5X5, 9: BoardSize.BOARD_9X9,
            13: BoardSize.BOARD_13X13, 19: BoardSize.BOARD_19X19
        }
        self.board_config = get_board_config(board_size_map.get(self.board_size, BoardSize.BOARD_5X5))
        self.perf_config = get_performance_config(self.board_size, self.performance_level)

        # MCTS state
        self.current_iteration = 0
        self.total_iterations = self.get_param_int('iterations', self.perf_config['iterations'])
        seed = params.get('seed')
        self.random = random if seed is None else random.Random(seed)
        # node_id -> {visits, value, parent, children, board, player}
        self.node_storage = {}
        self.memory = None
        self.next_node_id = 1
        self.root_node = 0

        # Current iteration state
        self.current_path = []
        self.current_node = 0
        self.current_value = 0.0

        # Statistics
        self.total_selections = 0
        self.total_expansions = 0
        self.total_rollouts = 0
        self.total_backprops = 0
        self.total_nodes_created = 0
        self.total_backprop_updates = 0

        # Track measured tree depth per iteration so we can
        # replace activity_tracker.py's hardcoded `avg_path_depth = 3`. Selection
        # and backprop now charge per-node delays — these stats expose what the
        # actual tree shape was, decoupling the simulator from the analytical
        # model's assumed depth.
        self.path_depths: List[int] = []

        # Output
        self._output = Output("MCTSSystem", level=OutputLevel.INFO)

    def _setup_impl(self):
        """Initialize MCTS tree"""
        self._output.info("Initializing MCTS tree...")

        # Create root node with empty board state
        initial_board = np.zeros((self.board_size, self.board_size), dtype=int)
        self.node_storage[self.root_node] = {
            'visits': 0,
            'value': 0.0,
            'parent': -1,
            'children': [],
            'board': initial_board,
            'player': 1,  # Black to play first
        }

        self._output.info(f"Root node created: node_id={self.root_node}")
        if self.memory is not None:
            self.memory.begin('initialize', 0, self._simulation.get_current_time())
            self.memory.allocate_node(self.root_node, self.node_storage[self.root_node])
            if self.memory.neural is not None:
                lut = self.memory.neural.profile['storage']['exp_lut']
                self.memory.transfer('node_sram', 'write', self.memory.config['neural_base'] + lut['offset'], lut['bytes'])

        # Register clock for periodic updates
        clock_freq = 500e6  # 500 MHz = 2ns period (matches board_config specs)
        self.register_clock(clock_freq, self.clock_tick)

        # Schedule first iteration
        self.schedule_iteration_start()

    def clock_tick(self, cycle):
        """Clock handler - called each clock cycle"""
        # Most work is event-driven, not clock-driven
        # This is mainly for periodic status updates
        return True  # Continue

    def schedule_iteration_start(self):
        """Schedule next MCTS iteration to start"""
        if self.current_iteration < self.total_iterations:
            self.current_iteration += 1

            event = IterationStartEvent(self.current_iteration)
            delay_cycles = _ns_to_cycles(self.board_config.fsm_transition_delay_ns)
            if self.memory is not None:
                delay_cycles += max(0, self.memory.cursor - self._simulation.get_current_time())
            link = self.get_link("to_selection")
            if link:
                link.send(event, delay_cycles)

    def handle_selection_complete(self, event: SelectionCompleteEvent):
        """Handle selection completion"""
        self.total_selections += 1
        self.current_path = event.path
        self.current_node = event.node_id

        # Record the depth of this iteration's selected path.
        # Expansion may append a child before backprop, so this is selection
        # depth only. Captured here so the analytical model can be replaced with an
        # empirical fit from real runs instead of `avg_path_depth = 3`.
        self.path_depths.append(len(event.path))

        delay_cycles = _ns_to_cycles(self.board_config.fsm_transition_delay_ns)
        link = self.get_link("to_expansion")
        if link:
            link.send(event, delay_cycles)

    def handle_expansion_complete(self, event: ExpansionCompleteEvent):
        """Handle expansion completion"""
        start_cycle = self._simulation.get_current_time() if self.memory is not None else 0
        if self.memory is not None:
            self.memory.begin('expansion_commit', event.iteration, start_cycle)
        self.total_expansions += 1
        self.total_nodes_created += len(event.children)

        # Update node storage if children were created
        if event.children:
            self.node_storage[event.node_id]['children'] = event.children

            # Select random child for rollout (paper Algo 1 line 12: RandomChoice)
            random_child = self.random.choice(event.children)
            self.current_node = random_child
            self.current_path.append(self.current_node)
            if self.memory is not None:
                self.memory.push_path(self.current_node)

        delay_cycles = _ns_to_cycles(self.board_config.fsm_transition_delay_ns)
        link = self.get_link("to_rollout")
        if link:
            if self.memory is not None:
                delay_cycles += self.memory.cursor - start_cycle
            link.send(event, delay_cycles)

    def handle_rollout_complete(self, event: RolloutCompleteEvent):
        """Handle rollout completion"""
        self.total_rollouts += 1
        self.current_value = event.value

        delay_cycles = _ns_to_cycles(self.board_config.fsm_transition_delay_ns)
        link = self.get_link("to_backprop")
        if link:
            backprop_event = MCTSEvent(event.iteration)
            link.send(backprop_event, delay_cycles)

    def handle_backprop_complete(self, event: BackpropCompleteEvent):
        """Handle backpropagation completion"""
        self.total_backprops += 1
        self.total_backprop_updates += event.nodes_updated

        # Progress logging
        if self.current_iteration % max(1, self.total_iterations // 10) == 0:
            progress = self.current_iteration / self.total_iterations * 100
            self._output.info(f"Progress: {self.current_iteration}/{self.total_iterations} ({progress:.1f}%)")

        # Schedule next iteration
        self.schedule_iteration_start()

    @property
    def mean_path_depth(self) -> float:
        """Average selection-path depth across all completed iterations.
        Returns 0 if no iterations have run. Used by ActivityTracker to replace
        the hardcoded `avg_path_depth = 3` baseline.
        """
        return sum(self.path_depths) / len(self.path_depths) if self.path_depths else 0.0

    @property
    def max_path_depth(self) -> int:
        return max(self.path_depths) if self.path_depths else 0

    def _finish_impl(self):
        """Print final statistics"""
        self._output.info("="*80)
        self._output.info("FINAL STATISTICS")
        self._output.info("="*80)
        self._output.info(f"Total iterations: {self.current_iteration}")
        self._output.info(f"Total selections: {self.total_selections}")
        self._output.info(f"Total expansions: {self.total_expansions}")
        self._output.info(f"Total rollouts: {self.total_rollouts}")
        self._output.info(f"Total backprops: {self.total_backprops}")
        self._output.info(f"Tree size: {len(self.node_storage)} nodes")
        # Report measured tree depth so the analytical
        # model's assumption is checkable against ground truth.
        self._output.info(
            f"Path depth — mean: {self.mean_path_depth:.2f}, "
            f"max: {self.max_path_depth}, samples: {len(self.path_depths)}"
        )


# ============================================================================
# Selection Unit Component
# ============================================================================

class SelectionUnitComponent(Component):
    """
    Selection unit that performs UCB1-based tree traversal.

    Receives: IterationStartEvent
    Sends: SelectionCompleteEvent
    """

    def __init__(self, component_id: ComponentId, params: Params):
        super().__init__(component_id, params)

        self.board_size = self.get_param_int('board_size', 5)
        self.exploration_constant = self.get_param_float('exploration_constant', 1.414)

        # Get board config for timing parameters
        board_size_map = {
            2: BoardSize.BOARD_2X2, 3: BoardSize.BOARD_3X3,
            5: BoardSize.BOARD_5X5, 9: BoardSize.BOARD_9X9,
            13: BoardSize.BOARD_13X13, 19: BoardSize.BOARD_19X19
        }
        self.board_config = get_board_config(board_size_map.get(self.board_size, BoardSize.BOARD_5X5))

        # Reference to shared tree storage (will be set by system)
        self.node_storage = None
        self.memory = None

        self._output = Output("SelectionUnit", level=OutputLevel.INFO)

    def _setup_impl(self):
        """Initialize selection unit"""
        self._output.info("Selection unit initialized")

    def handle_iteration_start(self, event: IterationStartEvent):
        """Handle iteration start - perform selection (paper Algo 1 lines 4-7)"""
        if self.node_storage is None:
            self._output.fatal("Node storage not set!")
            return

        start_cycle = self._simulation.get_current_time() if self.memory is not None else 0
        if self.memory is not None:
            self.memory.begin('selection', event.iteration, start_cycle)
            self.memory.reset_path()
        path = []
        current_node = 0  # Root

        # Traverse tree using UCB1 (paper: "while node has children and node not terminal")
        while current_node in self.node_storage:
            node = self.memory.read_node(current_node) if self.memory is not None else self.node_storage[current_node]
            path.append(current_node)
            if self.memory is not None:
                self.memory.push_path(current_node)

            child_count = node['children_count'] if self.memory is not None else len(node['children'])
            if not child_count or node['visits'] == 0:
                break

            # Select best child using UCB1
            children = self.memory.lookup_children(current_node, node) if self.memory is not None else node['children']
            best_child = self.select_best_child_ucb1(current_node, children, parent_visits=node['visits'])
            if best_child is None:
                break

            current_node = best_child

        # Send selection complete event
        response = SelectionCompleteEvent(event.iteration, path, current_node)

        # Depth-aware selection delay.
        # Real selection performs ONE CAM lookup per node descended (the path
        # has len(path) entries), plus the fixed selection-unit overhead. The
        # previous flat fee `selection_delay + cam_lookup` was the bug that
        # made the analytical model agree with the simulator — both ignored
        # tree shape. Now the simulator scales with actual tree depth.
        #
        # Edge case: empty path (root node, no traversal yet) still pays at
        # least one CAM lookup to read the root.
        traversal_depth = max(1, len(path))
        delay_ns = (
            self.board_config.selection_delay_ns
            + self.board_config.cam_lookup_delay_ns * traversal_depth
        )
        delay_cycles = _ns_to_cycles(delay_ns)

        if self.memory is not None:
            delay_cycles = self.memory.cursor - start_cycle

        link = self.get_link("to_system")
        if link:
            link.send(response, delay_cycles)

    def select_best_child_ucb1(self, parent_id: int, children: List[int], parent_visits=None) -> Optional[int]:
        """
        Select best child using UCB1 formula (paper Equation 1):
            UCB1(v_i) = w_i/n_i + C * sqrt(ln(N) / n_i)
        where w_i/n_i = wins/visits, N = parent visits, C = exploration constant

        Perspective handling:
        Each node stores its value from the perspective of the player about to
        move at that node (see backprop in MCTSSystemComponent.handle_backprop_*).
        Children alternate players, so a child's stored value is from the
        OPPOSITE player's perspective relative to the parent. To make the
        parent pick the move best for ITSELF, the exploitation term must be
        flipped: parent's reward = 1 - child's-stored-reward.

        Bug history: prior versions used `exploitation = value / visits`
        directly, which made the parent pick the move best for the OPPONENT.
        That bug only manifested when trained weights produced non-noise
        values (rollout was using random NN weights).
        """
        if not children:
            return None

        if parent_visits is None:
            parent = self.memory.read_node(parent_id) if self.memory is not None else self.node_storage[parent_id]
            parent_visits = parent['visits']
        if parent_visits == 0:
            return children[0]

        best_child = None
        best_ucb = float('-inf')

        for child_id in children:
            if child_id not in self.node_storage:
                continue

            child_node = self.memory.read_node(child_id) if self.memory is not None else self.node_storage[child_id]
            if self.memory is not None:
                self.memory.stage_candidate(child_id, child_node)
            visits = child_node['visits']
            value = child_node['value']

            if visits == 0:
                return child_id  # Unvisited nodes get priority (RTL: return 0xFFFF)
            if self.memory is not None:
                self.memory.compute('ucb')

            # Paper Eq. 1: UCB1 = w/n + C * sqrt(ln(N) / n)
            # Child stores value from the OPPOSITE player's perspective; flip
            # so we pick the move best for the parent (= worst for the child).
            exploitation = 1.0 - (value / visits)
            exploration = self.exploration_constant * math.sqrt(math.log(parent_visits) / visits)
            ucb = exploitation + exploration

            if ucb > best_ucb:
                best_ucb = ucb
                best_child = child_id

        return best_child


# ============================================================================
# Expansion Unit Component
# ============================================================================

class ExpansionUnitComponent(Component):
    """
    Expansion unit that generates child nodes.

    Receives: SelectionCompleteEvent
    Sends: ExpansionCompleteEvent
    """

    def __init__(self, component_id: ComponentId, params: Params):
        super().__init__(component_id, params)

        self.board_size = self.get_param_int('board_size', 5)

        # Get board config for timing parameters
        board_size_map = {
            2: BoardSize.BOARD_2X2, 3: BoardSize.BOARD_3X3,
            5: BoardSize.BOARD_5X5, 9: BoardSize.BOARD_9X9,
            13: BoardSize.BOARD_13X13, 19: BoardSize.BOARD_19X19
        }
        self.board_config = get_board_config(board_size_map.get(self.board_size, BoardSize.BOARD_5X5))

        # Reference to shared tree storage and next_node_id (will be set by system)
        self.node_storage = None
        self.memory = None
        self.next_node_id_ref = None

        self._output = Output("ExpansionUnit", level=OutputLevel.INFO)

    def _setup_impl(self):
        """Initialize expansion unit"""
        self._output.info("Expansion unit initialized")

    def handle_selection_complete(self, event: SelectionCompleteEvent):
        """
        Handle selection complete - perform expansion.

        Paper Algo 1 lines 10-13: If node visited and not terminal,
        generate legal moves and add a random child.
        Paper Section IV-B: Empty Position Detector identifies all
        unoccupied cells in one cycle via parallel comparators.
        """
        node_id = event.node_id
        children = []
        start_cycle = self._simulation.get_current_time() if self.memory is not None else 0
        if self.memory is not None:
            self.memory.begin('expansion', event.iteration, start_cycle)

        if node_id in self.node_storage:
            node = self.memory.read_node(node_id) if self.memory is not None else self.node_storage[node_id]

            # Expand if visited but has no children
            child_count = node['children_count'] if self.memory is not None else len(node['children'])
            if node['visits'] > 0 and not child_count:
                board = self.memory.read_board(node_id) if self.memory is not None else node['board']
                player = node['player']
                if self.memory is not None:
                    count = int(np.count_nonzero(board == 0))
                    self.memory.reserve_children(count)
                    if count:
                        self.memory.check_path_room()
                    self.memory.compute('expand')

                # Generate children only for empty positions
                # (paper: Empty Position Detector checks all N² cells in parallel)
                for row in range(self.board_size):
                    for col in range(self.board_size):
                        if board[row, col] == 0:
                            child_id = self.next_node_id_ref[0]
                            self.next_node_id_ref[0] += 1

                            # Create child board with move applied
                            child_board = board.copy()
                            child_board[row, col] = player

                            child_node = {
                                'visits': 0,
                                'value': 0.0,
                                'parent': node_id,
                                'children': [],
                                'board': child_board,
                                'player': -player,  # Alternate players
                            }
                            if self.memory is not None:
                                self.memory.transfer('node_sram', 'read', self.memory.config['working_offset'], self.memory.config['board_bytes'])
                                self.memory.compute('expand')
                                self.memory.allocate_node(child_id, child_node)
                            else:
                                self.node_storage[child_id] = child_node
                            children.append(child_id)

        if self.memory is not None and children:
            self.memory.attach_children(node_id, children)

        # Send expansion complete event
        response = ExpansionCompleteEvent(event.iteration, node_id, children)

        # Legacy fixed delay: the loop above can create all empty-position
        # children. SRAM width, ports, and board-storage scheduling have not
        # been mapped, so this does not yet bill those writes physically.
        delay_ns = self.board_config.expansion_delay_ns + self.board_config.sram_access_delay_ns
        delay_cycles = _ns_to_cycles(delay_ns)

        if self.memory is not None:
            delay_cycles = self.memory.cursor - start_cycle

        link = self.get_link("to_system")
        if link:
            link.send(response, delay_cycles)


# ============================================================================
# Rollout Unit Component
# ============================================================================

class RolloutUnitComponent(Component):
    """
    Rollout unit that performs a single NN forward pass.

    Paper Section IV-C: "single forward pass produces win/loss/draw
    probabilities that serve the same algorithmic role as Monte Carlo
    sampling in UCB1 calculations"

    Architecture (Supp Table 4): N²×2 inputs → hidden (ReLU) → 3 outputs (softmax)
    Hidden size: 32 for 2×2/3×3, 96 for 5×5+

    Receives: ExpansionCompleteEvent
    Sends: RolloutCompleteEvent
    """

    # Hidden layer sizes per board size (Supplementary Table 4)
    HIDDEN_SIZES = {2: 32, 3: 32, 5: 96, 9: 96, 13: 96, 19: 96}

    def __init__(self, component_id: ComponentId, params: Params):
        super().__init__(component_id, params)

        self.board_size = self.get_param_int('board_size', 5)

        # Get board config for timing parameters
        board_size_map = {
            2: BoardSize.BOARD_2X2, 3: BoardSize.BOARD_3X3,
            5: BoardSize.BOARD_5X5, 9: BoardSize.BOARD_9X9,
            13: BoardSize.BOARD_13X13, 19: BoardSize.BOARD_19X19
        }
        self.board_config = get_board_config(board_size_map.get(self.board_size, BoardSize.BOARD_5X5))

        # References to shared state (will be set by system)
        self.node_storage = None
        self.memory = None
        self.system_component = None
        self.neural_mapping = None

        # 2-layer crossbar NN matching paper architecture
        # (Supp Table 4: N²×2 → hidden → 3 outputs)
        input_size = self.board_size ** 2 * 2  # 2-channel encoding
        self.hidden_size = self.HIDDEN_SIZES.get(self.board_size, 96)
        output_size = 3  # win/draw/loss

        # Initialize weights (random by default, can load trained)
        seed = params.get('seed')
        rng = np.random if seed is None else np.random.RandomState(seed)
        self.weights1 = rng.randn(input_size, self.hidden_size) * np.sqrt(2.0 / input_size)
        self.weights2 = rng.randn(self.hidden_size, output_size) * np.sqrt(2.0 / self.hidden_size)
        self._weights_trained = False
        self.evaluator_info = {
            'mode': 'random_diagnostic',
            'input_size': input_size, 'hidden_size': self.hidden_size, 'output_size': output_size,
            'input_encoding': 'interleaved_black_white', 'turn_indicator': False,
            'weight_transform': 'identity', 'output_order': ['white', 'draw', 'black'],
            'value_perspective': 'black', 'arithmetic_dtype': 'float64',
            'weight_sha256': [
                hashlib.sha256(weights.tobytes()).hexdigest()
                for weights in (self.weights1, self.weights2)
            ],
        }

        self._output = Output("RolloutUnit", level=OutputLevel.INFO)

    def load_weights(self, weights_file, evaluator_spec=None):
        if self.neural_mapping is not None:
            raise RuntimeError('Load weights before creating the resident neural mapping')
        weights1, weights2, info = load_evaluator_checkpoint(
            weights_file, evaluator_spec, self.board_size, self.hidden_size
        )
        # Apply the declared transform once; assign state only after all checks.
        weights1 = effective_weights(weights1, info['spec']['weight_transform'])
        weights2 = effective_weights(weights2, info['spec']['weight_transform'])
        self.weights1, self.weights2 = weights1, weights2
        self.evaluator_info = info
        self._weights_trained = True
        self._output.info(f"Loaded checkpoint: {self.weights1.shape} → {self.weights2.shape}")

    def _setup_impl(self):
        """Initialize rollout unit"""
        status = self.evaluator_info['mode']
        self._output.info(
            f"Rollout unit initialized: {self.board_size**2 * 2}→"
            f"{self.hidden_size}→3 NN ({status} weights)"
        )

    def _board_to_features(self, board: np.ndarray) -> np.ndarray:
        """
        2-channel encoding (Supp Table 4: N²×2 inputs).
        Channel 0: black stone presence, Channel 1: white stone presence.
        """
        return encode_board(board, self.board_size)

    def _nn_forward(self, board: np.ndarray) -> float:
        """
        Single NN forward pass through 2-layer crossbar.

        Layer 1: DAC → Crossbar MVM (features × W1) → ADC → ReLU
        Layer 2: DAC → Crossbar MVM (hidden × W2) → ADC → Softmax

        Returns value from Black's perspective (0.0=white wins, 1.0=black wins).
        """
        if self.neural_mapping is not None:
            return self.neural_mapping.forward(board)
        features = self._board_to_features(board)

        # Layer 1: Crossbar + ReLU
        hidden = features @ self.weights1
        hidden = np.maximum(0, hidden)  # ReLU activation

        # Layer 2: Crossbar + Softmax
        logits = hidden @ self.weights2
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)

        # probs = [P(White), P(Draw), P(Black)]
        value = probs[2] * 1.0 + probs[1] * 0.5 + probs[0] * 0.0
        return value

    def handle_expansion_complete(self, event: ExpansionCompleteEvent):
        """
        Handle expansion complete - perform single NN evaluation.

        Paper Section IV-C / Algorithm 1 lines 15-20:
        The crossbar performs a single forward pass on the current board state.
        DAC converts board to voltages, crossbar computes I = G × V, ADC
        digitizes output. No random playout — just one NN inference.
        """
        start_cycle = self._simulation.get_current_time() if self.memory is not None else 0
        if self.memory is not None:
            self.memory.begin('rollout', event.iteration, start_cycle)
        # Get the actual board state from the node being evaluated
        if self.system_component is not None:
            current_node_id = self.system_component.current_node
            if current_node_id in self.node_storage:
                board = self.memory.read_board(current_node_id) if self.memory is not None else self.node_storage[current_node_id]['board']
            else:
                board = np.zeros((self.board_size, self.board_size), dtype=int)
        else:
            board = np.zeros((self.board_size, self.board_size), dtype=int)

        # Single NN forward pass (paper: "single forward pass produces
        # win/loss/draw probabilities")
        value = self._nn_forward(board)

        # Send rollout complete event
        response = RolloutCompleteEvent(event.iteration, value, 0)

        # Reference mode retains its legacy delay. Mapped mode charges the
        # complete neural service template through the shared memory timeline.
        delay_ns = self.board_config.rollout_total_latency_ns
        delay_cycles = _ns_to_cycles(delay_ns)

        if self.memory is not None:
            if self.neural_mapping is None:
                self.memory.compute('rollout')
            else:
                self.memory.complete_neural()
            delay_cycles = self.memory.cursor - start_cycle

        link = self.get_link("to_system")
        if link:
            link.send(response, delay_cycles)


# ============================================================================
# Backpropagation Unit Component
# ============================================================================

class BackpropagationUnitComponent(Component):
    """
    Backpropagation unit that updates node values.

    Receives: RolloutCompleteEvent (via system)
    Sends: BackpropCompleteEvent
    """

    def __init__(self, component_id: ComponentId, params: Params):
        super().__init__(component_id, params)

        self.board_size = self.get_param_int('board_size', 5)

        # Get board config for timing parameters
        board_size_map = {
            2: BoardSize.BOARD_2X2, 3: BoardSize.BOARD_3X3,
            5: BoardSize.BOARD_5X5, 9: BoardSize.BOARD_9X9,
            13: BoardSize.BOARD_13X13, 19: BoardSize.BOARD_19X19
        }
        self.board_config = get_board_config(board_size_map.get(self.board_size, BoardSize.BOARD_5X5))

        # Reference to shared tree storage and system component (will be set by system)
        self.node_storage = None
        self.memory = None
        self.system_component = None

        self._output = Output("BackpropUnit", level=OutputLevel.INFO)

    def _setup_impl(self):
        """Initialize backprop unit"""
        self._output.info("Backpropagation unit initialized")

    def handle_rollout_complete(self, event: MCTSEvent):
        """
        Handle rollout complete - perform backpropagation.

        Paper Algo 1 lines 23-26: Traverse path from leaf to root,
        incrementing visits and adding result to wins.
        Paper Section IV-D: Statistics Updater performs in-memory
        read-modify-write using saturating counters.
        """
        if self.system_component is None:
            self._output.error("System component reference not set!")
            return

        # Get current path and value from system component
        current_path = self.system_component.current_path
        current_value = self.system_component.current_value
        start_cycle = self._simulation.get_current_time() if self.memory is not None else 0
        if self.memory is not None:
            self.memory.begin('backprop', event.iteration, start_cycle)
            if self.memory.path_depth != len(current_path):
                raise RuntimeError('Selected path and memory stack disagree')
            current_path = list(reversed(current_path))

        nodes_updated = 0

        # Update all nodes in path (paper Algo 1 line 24: node.wins += result)
        # Flip value based on player perspective: NN evaluates from Black's
        # perspective (1.0 = Black wins), so White-to-play nodes accumulate
        # (1 - value) to ensure UCB1 maximizes correctly for each player.
        for node_id in current_path:
            if node_id in self.node_storage:
                if self.memory is not None and self.memory.pop_path() != node_id:
                    raise RuntimeError('Backpropagation path order mismatch')
                node = self.memory.read_node(node_id) if self.memory is not None else self.node_storage[node_id]
                node['visits'] += 1
                # Perspective-correct the value
                if node['player'] == 1:  # Black to play
                    node['value'] += current_value
                else:  # White to play
                    node['value'] += (1.0 - current_value)
                if self.memory is not None:
                    self.memory.compute('update')
                    self.memory.update_stats(node_id, node['visits'], node['value'])
                nodes_updated += 1

        # Send backprop complete event
        response = BackpropCompleteEvent(event.iteration, nodes_updated)

        # Depth-aware backprop delay.
        # Backprop walks the entire path from leaf to root, doing one
        # SRAM read-modify-write per node (paper Section IV-D: "Statistics
        # Updater performs in-memory read-modify-write using saturating
        # counters"). The previous flat fee was a bug — it priced an
        # unbounded-depth walk as if it were one access.
        #
        # If everything is fully pipelined the depth penalty is hidden, but
        # the back-edge in the dependency chain (each parent waits for child)
        # makes the path length the critical path. Charging per node is the
        # honest first-order approximation; can be refined to (depth +
        # pipeline_fill) later.
        path_depth = max(1, nodes_updated)
        delay_ns = (
            self.board_config.backprop_delay_ns
            + self.board_config.sram_access_delay_ns
        ) * path_depth
        delay_cycles = _ns_to_cycles(delay_ns)

        if self.memory is not None:
            delay_cycles = self.memory.cursor - start_cycle

        link = self.get_link("to_system")
        if link:
            link.send(response, delay_cycles)


# Export main classes
__all__ = [
    'MCTSSystemComponent',
    'SelectionUnitComponent',
    'ExpansionUnitComponent',
    'RolloutUnitComponent',
    'BackpropagationUnitComponent',
    'SelectionCompleteEvent',
    'ExpansionCompleteEvent',
    'RolloutCompleteEvent',
    'BackpropCompleteEvent',
    'IterationStartEvent'
]
