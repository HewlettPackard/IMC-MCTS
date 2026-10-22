# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Base Component Templates

Template classes that all board-specific components inherit from.

Enhanced with CAM-based (Content-Addressable Memory) storage for transposition detection.
The CAM searches by board state CONTENT rather than node ID, enabling automatic
detection when different move sequences reach the same position.
"""

from abc import abstractmethod
from typing import List, Tuple, Optional, Dict
import random
import math

from ...core.component import Component, ComponentId
from ...core.config import Params
from ...core.statistics import CounterStatistic, AverageStatistic, AccumulatorStatistic
from .board_state_encoder import BoardStateEncoder


class SelectionUnitBase(Component):
    """
    Base class for selection units (all board sizes)

    Enhanced with CAM-based storage that enables content-addressable lookup
    by board state hash. This allows transposition detection: when different
    move sequences reach the same board position, the CAM automatically
    recognizes them as identical states.

    Storage Architecture:
    - node_storage: Primary node data indexed by node_id
    - board_state_storage: Maps node_id -> actual board state (2D list)
    - state_hash_to_node: CAM-like lookup: state_hash -> node_id
    - encoder: Zobrist hashing for efficient state comparison
    """

    def __init__(self, component_id: ComponentId, params: Params):
        super().__init__(component_id, params)

        # Parameters
        self.board_size = self.get_param_int("board_size", 9)
        self.cam_entries = self.get_param_int("cam_entries", 256)
        self.exploration_constant = self.get_param_float("exploration_constant", 1.414)
        self.enable_transposition_detection = self.get_param_bool("enable_transposition", True)
        self.use_canonical_states = self.get_param_bool("use_canonical_states", False)

        # CAM-based storage (content-addressable by board state)
        self.node_storage = {}  # node_id -> (visits, value, parent_id, children_list)
        self.board_state_storage = {}  # node_id -> board_state (2D list)
        self.state_hash_to_node: Dict[int, int] = {}  # state_hash -> node_id (CAM lookup)
        self.num_stored_nodes = 0

        # Board state encoder for CAM hashing
        self.encoder = BoardStateEncoder(self.board_size)

        # Statistics
        self.selections_completed = 0
        self.cam_hits = 0
        self.cam_misses = 0
        self.transpositions_detected = 0
        self.unique_states = 0

    def _setup_impl(self) -> None:
        """Setup selection unit"""
        # Add statistics
        self.add_statistic("selections_completed",
                          CounterStatistic("selections_completed", "Number of selections"))
        self.add_statistic("cam_hit_rate",
                          AverageStatistic("cam_hit_rate", "CAM hit rate", "%"))
        self.add_statistic("transpositions_detected",
                          CounterStatistic("transpositions_detected", "Transpositions detected"))
        self.add_statistic("unique_states",
                          CounterStatistic("unique_states", "Unique board states stored"))
        self.add_statistic("transposition_rate",
                          AverageStatistic("transposition_rate", "Transposition detection rate", "%"))

    def calculate_ucb1(self, visits: int, value: float, parent_visits: int) -> float:
        """Calculate UCB1 value for a node"""
        if visits == 0:
            return float('inf')

        exploitation_term = value / visits
        exploration_term = self.exploration_constant * math.sqrt(math.log(parent_visits) / visits)
        return exploitation_term + exploration_term

    def cam_lookup_by_state(self, board_state: List[List[int]]) -> Optional[int]:
        """
        CAM lookup: Search for node by board state CONTENT (not by ID).

        This is the core CAM functionality - content-addressable search.
        Computes Zobrist hash of the board and searches the CAM.

        Args:
            board_state: 2D list representing the board

        Returns:
            node_id if state found in CAM, None otherwise
        """
        if not self.enable_transposition_detection:
            return None

        # Compute board state hash (CAM search key)
        if self.use_canonical_states:
            canonical_state, _ = self.encoder.canonicalize_state(board_state)
            state_hash = self.encoder.zobrist_hash(canonical_state)
        else:
            state_hash = self.encoder.zobrist_hash(board_state)

        # CAM search: lookup by content (hash)
        if state_hash in self.state_hash_to_node:
            self.cam_hits += 1
            return self.state_hash_to_node[state_hash]
        else:
            self.cam_misses += 1
            return None

    def cam_insert_state(self, node_id: int, board_state: List[List[int]]) -> bool:
        """
        Insert node into CAM storage with its board state.

        Args:
            node_id: Node identifier
            board_state: 2D list representing the board

        Returns:
            True if inserted as new state, False if transposition detected
        """
        # Compute board state hash
        if self.use_canonical_states:
            canonical_state, _ = self.encoder.canonicalize_state(board_state)
            state_hash = self.encoder.zobrist_hash(canonical_state)
            board_state = canonical_state
        else:
            state_hash = self.encoder.zobrist_hash(board_state)

        # Check for transposition
        if state_hash in self.state_hash_to_node:
            self.transpositions_detected += 1
            return False  # Transposition detected

        # Insert into CAM
        self.state_hash_to_node[state_hash] = node_id
        self.board_state_storage[node_id] = board_state
        self.unique_states += 1

        return True  # New unique state

    def merge_transposition_nodes(self, existing_node_id: int, new_node_id: int) -> int:
        """
        Merge statistics from transposed nodes.

        When different move sequences reach the same board state,
        merge their statistics to get better value estimates.

        Args:
            existing_node_id: Node already in CAM
            new_node_id: New node with same board state

        Returns:
            The merged node_id (keeps existing_node_id)
        """
        if existing_node_id not in self.node_storage or new_node_id not in self.node_storage:
            return existing_node_id

        # Get statistics from both nodes
        existing_visits, existing_value, existing_parent, existing_children = self.node_storage[existing_node_id]
        new_visits, new_value, new_parent, new_children = self.node_storage[new_node_id]

        # Merge statistics (weighted average)
        merged_visits = existing_visits + new_visits
        merged_value = existing_value + new_value

        # Merge children lists (union, avoid duplicates)
        merged_children = list(set(existing_children + new_children))

        # Update existing node with merged statistics
        self.node_storage[existing_node_id] = (
            merged_visits,
            merged_value,
            existing_parent,  # Keep original parent
            merged_children
        )

        # Remove the redundant new node
        if new_node_id in self.node_storage:
            del self.node_storage[new_node_id]
        if new_node_id in self.board_state_storage:
            del self.board_state_storage[new_node_id]

        return existing_node_id

    def select_best_child(self, parent_id: int, children: List[int]) -> Tuple[int, float]:
        """Select best child using UCB1"""
        # Get parent node data (handle both old 3-tuple and new 4-tuple formats)
        parent_data = self.node_storage.get(parent_id, (0, 0.0, -1, []))
        parent_visits = parent_data[0]

        best_node_id = None
        best_ucb1 = float('-inf')

        for child_id in children:
            if child_id in self.node_storage:
                child_data = self.node_storage[child_id]
                child_visits = child_data[0]
                child_value = child_data[1]
                child_ucb1 = self.calculate_ucb1(child_visits, child_value, parent_visits)

                if child_ucb1 > best_ucb1:
                    best_ucb1 = child_ucb1
                    best_node_id = child_id
                    self.cam_hits += 1
            else:
                self.cam_misses += 1

        return best_node_id, best_ucb1

    @abstractmethod
    def handle_selection_request(self, event):
        """Handle selection request (board-specific)"""
        pass


class ExpansionUnitBase(Component):
    """Base class for expansion units (all board sizes)"""

    def __init__(self, component_id: ComponentId, params: Params):
        super().__init__(component_id, params)

        self.board_size = self.get_param_int("board_size", 9)
        self.max_children = self.board_size ** 2

        # Statistics
        self.expansions_completed = 0
        self.moves_generated = 0

    def _setup_impl(self) -> None:
        """Setup expansion unit"""
        self.add_statistic("expansions_completed",
                          CounterStatistic("expansions_completed", "Number of expansions"))
        self.add_statistic("moves_per_expansion",
                          AverageStatistic("moves_per_expansion", "Average moves per expansion"))

    def generate_valid_moves(self, board_state: List[List[int]]) -> List[Tuple[int, int]]:
        """Generate all valid moves for current board state"""
        valid_moves = []

        for row in range(self.board_size):
            for col in range(self.board_size):
                if board_state[row][col] == 0:  # Empty position
                    if self.is_legal_move(board_state, row, col):
                        valid_moves.append((row, col))

        return valid_moves

    def is_legal_move(self, board_state: List[List[int]], row: int, col: int) -> bool:
        """Check if a move is legal (basic Go rules)"""
        # For now, just check if position is empty
        # Full Go rules would check for ko, suicide, etc.
        return board_state[row][col] == 0

    @abstractmethod
    def handle_expansion_request(self, event):
        """Handle expansion request (board-specific)"""
        pass


class RolloutUnitBase(Component):
    """Base class for rollout units (all board sizes)"""

    def __init__(self, component_id: ComponentId, params: Params):
        super().__init__(component_id, params)

        self.board_size = self.get_param_int("board_size", 9)
        self.crossbar_size = self.get_param_int("crossbar_size", self.board_size ** 2)
        self.rollout_depth = self.get_param_int("rollout_depth", 50)

        # Statistics
        self.rollouts_completed = 0
        self.total_rollout_moves = 0

    def _setup_impl(self) -> None:
        """Setup rollout unit"""
        self.add_statistic("rollouts_completed",
                          CounterStatistic("rollouts_completed", "Number of rollouts"))
        self.add_statistic("avg_rollout_length",
                          AverageStatistic("avg_rollout_length", "Average rollout length"))

    def perform_rollout(self, board_state: List[List[int]], current_player: int) -> Tuple[int, float]:
        """
        Perform random rollout simulation.

        Returns:
            (winner, value) tuple
        """
        # Copy board state
        rollout_board = [row[:] for row in board_state]
        rollout_player = current_player
        num_moves = 0

        # Simulate random playout
        for _ in range(self.rollout_depth):
            # Find valid moves
            valid_moves = []
            for row in range(self.board_size):
                for col in range(self.board_size):
                    if rollout_board[row][col] == 0:
                        valid_moves.append((row, col))

            if not valid_moves:
                break  # Game over

            # Make random move
            row, col = random.choice(valid_moves)
            rollout_board[row][col] = rollout_player
            num_moves += 1

            # Switch player
            rollout_player = -rollout_player if rollout_player in (1, -1) else (2 if rollout_player == 1 else 1)

        # Determine winner (simple area counting)
        winner, value = self.evaluate_board(rollout_board)
        self.total_rollout_moves += num_moves

        return winner, value

    def evaluate_board(self, board: List[List[int]]) -> Tuple[int, float]:
        """
        Evaluate final board position.

        Returns:
            (winner, value) tuple
        """
        player1_stones = 0
        player2_stones = 0

        for row in board:
            for cell in row:
                if cell == 1:
                    player1_stones += 1
                elif cell == -1 or cell == 2:
                    player2_stones += 1

        if player1_stones > player2_stones:
            return 1, 1.0
        elif player2_stones > player1_stones:
            return -1, 0.0
        else:
            return 0, 0.5

    @abstractmethod
    def handle_rollout_request(self, event):
        """Handle rollout request (board-specific)"""
        pass


class BackpropagationUnitBase(Component):
    """Base class for backpropagation units (all board sizes)"""

    def __init__(self, component_id: ComponentId, params: Params):
        super().__init__(component_id, params)

        self.board_size = self.get_param_int("board_size", 9)
        self.sram_size_kb = self.get_param_int("sram_size_kb", 8)

        # Statistics
        self.backprops_completed = 0
        self.nodes_updated = 0

    def _setup_impl(self) -> None:
        """Setup backpropagation unit"""
        self.add_statistic("backprops_completed",
                          CounterStatistic("backprops_completed", "Number of backpropagations"))
        self.add_statistic("avg_path_length",
                          AverageStatistic("avg_path_length", "Average path length"))

    def backpropagate_value(self, path: List[int], value: float, node_storage: dict) -> int:
        """
        Backpropagate value through path.

        Args:
            path: List of node IDs from leaf to root
            value: Value to backpropagate
            node_storage: Reference to node storage dict

        Returns:
            Number of nodes updated
        """
        num_updated_nodes = 0

        for node_id in path:
            if node_id in node_storage:
                node_data = node_storage[node_id]
                node_visits = node_data[0]
                node_total_value = node_data[1]
                parent_id = node_data[2]

                # Handle both 3-tuple (old) and 4-tuple (new with children) formats
                if len(node_data) >= 4:
                    children = node_data[3]
                    node_storage[node_id] = (node_visits + 1, node_total_value + value, parent_id, children)
                else:
                    node_storage[node_id] = (node_visits + 1, node_total_value + value, parent_id)

                num_updated_nodes += 1

        self.nodes_updated += num_updated_nodes
        return num_updated_nodes

    @abstractmethod
    def handle_backpropagation_request(self, event):
        """Handle backpropagation request (board-specific)"""
        pass


class FSMControllerBase(Component):
    """
    Base class for FSM controllers (all board sizes)

    Supports two modes:
    1. String-based FSM (legacy, default)
    2. TCAM-based FSM (hardware-accelerated, optional)

    To enable TCAM mode, set parameter: use_tcam_fsm=True
    """

    def __init__(self, component_id: ComponentId, params: Params):
        super().__init__(component_id, params)

        self.board_size = self.get_param_int("board_size", 9)
        self.mcts_iterations = self.get_param_int("mcts_iterations", 1000)
        self.timeout_cycles = self.get_param_int("timeout_cycles", 100000)

        # TCAM FSM configuration
        self.use_tcam_fsm = self.get_param_bool("use_tcam_fsm", False)
        self.tcam_search_mode = self.get_param_str("tcam_search_mode", "state_partitioned")
        self.tcam_num_blocks = self.get_param_int("tcam_num_blocks", 4)

        # State machine (string-based for compatibility)
        self.state = "IDLE"
        self.current_iteration = 0

        # TCAM FSM controller (initialized if enabled)
        self.tcam_fsm = None
        if self.use_tcam_fsm:
            try:
                from ..tcam_fsm import TCAMFSMController
                self.tcam_fsm = TCAMFSMController(
                    num_tcam_blocks=self.tcam_num_blocks,
                    search_mode=self.tcam_search_mode,
                    enable_power_tracking=True
                )
                print(f"[{component_id.name}] TCAM FSM enabled (mode={self.tcam_search_mode})")
            except ImportError as e:
                print(f"[{component_id.name}] Warning: Could not import TCAM FSM: {e}")
                print(f"[{component_id.name}] Falling back to string-based FSM")
                self.use_tcam_fsm = False

        # Statistics
        self.iterations_completed = 0
        self.total_cycles = 0
        self.tcam_transitions = 0

    def _setup_impl(self) -> None:
        """Setup FSM controller"""
        self.add_statistic("iterations_completed",
                          CounterStatistic("iterations_completed", "MCTS iterations completed"))
        self.add_statistic("avg_cycles_per_iteration",
                          AverageStatistic("avg_cycles_per_iteration", "Average cycles per iteration"))

        if self.use_tcam_fsm:
            self.add_statistic("tcam_transitions",
                              CounterStatistic("tcam_transitions", "TCAM-based state transitions"))
            self.add_statistic("tcam_search_energy_nj",
                              AccumulatorStatistic("tcam_search_energy_nj", "Total TCAM search energy", "nJ"))

        # Start the FSM
        self.state = "IDLE"

    def update_state_tcam(self, input_signals: int) -> Optional[dict]:
        """
        Update state using TCAM FSM.

        Args:
            input_signals: 8-bit input signal byte

        Returns:
            Transition info dict if successful, None otherwise
        """
        if not self.use_tcam_fsm or self.tcam_fsm is None:
            return None

        # Perform TCAM search and state transition
        transition = self.tcam_fsm.update_state(input_signals)

        if transition:
            # Update string-based state for compatibility
            self.state = transition['new_state_name']
            self.tcam_transitions += 1

            # Update statistics
            if self.tcam_fsm.power_model:
                power_statistics = self.tcam_fsm.power_model.get_statistics()
                total_energy_nj = power_statistics['total_search_energy_nj']
                self.update_statistic("tcam_search_energy_nj", total_energy_nj)

            # Call board-specific handler
            self.handle_state_transition(transition['new_state_name'])

        return transition

    def get_current_tcam_state(self) -> str:
        """Get current state from TCAM FSM"""
        if self.tcam_fsm:
            return self.tcam_fsm.get_current_state_name()
        return self.state

    def reset_tcam_fsm(self):
        """Reset TCAM FSM to IDLE state"""
        if self.tcam_fsm:
            self.tcam_fsm.reset()
            self.state = "IDLE"

    def get_tcam_statistics(self) -> Optional[dict]:
        """Get TCAM FSM statistics"""
        if self.tcam_fsm:
            return self.tcam_fsm.get_statistics()
        return None

    @abstractmethod
    def handle_state_transition(self, new_state: str):
        """Handle state transition (board-specific)"""
        pass
