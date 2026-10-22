# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Accelerator Event Definitions

Common event types used across all board sizes for MCTS components.
"""

from ...core.event import Event
from typing import List, Any, Dict, Optional


class SelectionRequestEvent(Event):
    """Request node selection for one MCTS tree."""

    def __init__(self, tree_id: int = 0):
        super().__init__()
        self.tree_id = tree_id

    def _serialize_data(self) -> Dict[str, Any]:
        event_data = {'tree_id': self.tree_id}
        return event_data

    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.tree_id = data.get('tree_id', 0)


class SelectionResponseEvent(Event):
    """Return the node selected by the selection unit."""

    def __init__(self, node_id: int = 0, ucb_value: float = 0.0,
                 board_state: Optional[List[List[int]]] = None):
        super().__init__()
        self.node_id = node_id
        self.ucb_value = ucb_value
        self.board_state = board_state or []

    def _serialize_data(self) -> Dict[str, Any]:
        event_data = {
            'node_id': self.node_id,
            'ucb_value': self.ucb_value,
            'board_state': self.board_state
        }
        return event_data

    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.node_id = data.get('node_id', 0)
        self.ucb_value = data.get('ucb_value', 0.0)
        self.board_state = data.get('board_state', [])


class ExpansionRequestEvent(Event):
    """Request expansion of one MCTS node."""

    def __init__(self, node_id: int = 0, board_state: Optional[List[List[int]]] = None):
        super().__init__()
        self.node_id = node_id
        self.board_state = board_state or []

    def _serialize_data(self) -> Dict[str, Any]:
        event_data = {
            'node_id': self.node_id,
            'board_state': self.board_state
        }
        return event_data

    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.node_id = data.get('node_id', 0)
        self.board_state = data.get('board_state', [])


class ExpansionResponseEvent(Event):
    """Return child nodes and moves created during expansion."""

    def __init__(self, parent_node_id: int = 0, child_node_ids: Optional[List[int]] = None,
                 valid_moves: Optional[List[tuple]] = None):
        super().__init__()
        self.parent_node_id = parent_node_id
        self.child_node_ids = child_node_ids or []
        self.valid_moves = valid_moves or []

    def _serialize_data(self) -> Dict[str, Any]:
        event_data = {
            'parent_node_id': self.parent_node_id,
            'child_node_ids': self.child_node_ids,
            'valid_moves': self.valid_moves
        }
        return event_data

    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.parent_node_id = data.get('parent_node_id', 0)
        self.child_node_ids = data.get('child_node_ids', [])
        self.valid_moves = data.get('valid_moves', [])


class RolloutRequestEvent(Event):
    """Request a rollout from one board state."""

    def __init__(self, node_id: int = 0, board_state: Optional[List[List[int]]] = None,
                 current_player: int = 1):
        super().__init__()
        self.node_id = node_id
        self.board_state = board_state or []
        self.current_player = current_player

    def _serialize_data(self) -> Dict[str, Any]:
        event_data = {
            'node_id': self.node_id,
            'board_state': self.board_state,
            'current_player': self.current_player
        }
        return event_data

    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.node_id = data.get('node_id', 0)
        self.board_state = data.get('board_state', [])
        self.current_player = data.get('current_player', 1)


class RolloutResponseEvent(Event):
    """Return the winner and value produced by a rollout."""

    def __init__(self, node_id: int = 0, winner: int = 0, value: float = 0.0):
        super().__init__()
        self.node_id = node_id
        self.winner = winner  # 0 = draw, 1 = player 1, -1 = player 2
        self.value = value

    def _serialize_data(self) -> Dict[str, Any]:
        event_data = {
            'node_id': self.node_id,
            'winner': self.winner,
            'value': self.value
        }
        return event_data

    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.node_id = data.get('node_id', 0)
        self.winner = data.get('winner', 0)
        self.value = data.get('value', 0.0)


class BackpropagationRequestEvent(Event):
    """Request value backpropagation along an MCTS path."""

    def __init__(self, leaf_node_id: int = 0, value: float = 0.0,
                 path: Optional[List[int]] = None):
        super().__init__()
        self.leaf_node_id = leaf_node_id
        self.value = value
        self.path = path or []

    def _serialize_data(self) -> Dict[str, Any]:
        event_data = {
            'leaf_node_id': self.leaf_node_id,
            'value': self.value,
            'path': self.path
        }
        return event_data

    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.leaf_node_id = data.get('leaf_node_id', 0)
        self.value = data.get('value', 0.0)
        self.path = data.get('path', [])


class BackpropagationResponseEvent(Event):
    """Report the result of a backpropagation update."""

    def __init__(self, nodes_updated: int = 0, success: bool = True):
        super().__init__()
        self.nodes_updated = nodes_updated
        self.success = success

    def _serialize_data(self) -> Dict[str, Any]:
        event_data = {
            'nodes_updated': self.nodes_updated,
            'success': self.success
        }
        return event_data

    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.nodes_updated = data.get('nodes_updated', 0)
        self.success = data.get('success', True)


class MCTSCompleteEvent(Event):
    """Report completion of an MCTS iteration."""

    def __init__(self, iteration: int = 0, best_move: Optional[tuple] = None,
                 total_iterations: int = 0):
        super().__init__()
        self.iteration = iteration
        self.best_move = best_move
        self.total_iterations = total_iterations

    def _serialize_data(self) -> Dict[str, Any]:
        event_data = {
            'iteration': self.iteration,
            'best_move': self.best_move,
            'total_iterations': self.total_iterations
        }
        return event_data

    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.iteration = data.get('iteration', 0)
        self.best_move = data.get('best_move')
        self.total_iterations = data.get('total_iterations', 0)


class ValueUpdateEvent(Event):
    """Update one tree node's visit count and value."""

    def __init__(self, node_id: int = 0, visits: int = 0, value: float = 0.0):
        super().__init__()
        self.node_id = node_id
        self.visits = visits
        self.value = value

    def _serialize_data(self) -> Dict[str, Any]:
        event_data = {
            'node_id': self.node_id,
            'visits': self.visits,
            'value': self.value
        }
        return event_data

    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.node_id = data.get('node_id', 0)
        self.visits = data.get('visits', 0)
        self.value = data.get('value', 0.0)
