# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
SST Event System

Event classes for inter-component communication.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class EventPriority(Enum):
    """Event priority levels"""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


@dataclass
class EventId:
    """Unique event identifier"""
    id: int
    component_id: int
    
    def __str__(self) -> str:
        return f"EventId({self.id}, {self.component_id})"


class Event(ABC):
    """Carry data and delivery metadata between simulation components."""
    
    _next_id = 0
    
    def __init__(self):
        self._id = EventId(Event._next_id, 0)  # Component ID set by sender
        Event._next_id += 1
        
        self._priority = EventPriority.NORMAL
        self._delivery_info = None
        self._sender = None
        self._receiver = None
    
    @property
    def id(self) -> EventId:
        """Get event ID"""
        return self._id
    
    @property
    def priority(self) -> EventPriority:
        """Get event priority"""
        return self._priority
    
    @priority.setter
    def priority(self, value: EventPriority) -> None:
        """Set event priority"""
        self._priority = value
    
    @property
    def delivery_info(self) -> Any:
        """Get delivery information (internal use)"""
        return self._delivery_info
    
    @delivery_info.setter
    def delivery_info(self, value: Any) -> None:
        """Set delivery information (internal use)"""
        self._delivery_info = value
    
    @property
    def sender(self) -> Optional[Any]:
        """Get sender component"""
        return self._sender
    
    @sender.setter
    def sender(self, value: Any) -> None:
        """Set sender component"""
        self._sender = value
    
    @property
    def receiver(self) -> Optional[Any]:
        """Get receiver component"""
        return self._receiver
    
    @receiver.setter
    def receiver(self, value: Any) -> None:
        """Set receiver component"""
        self._receiver = value
    
    def clone(self) -> 'Event':
        """Create a copy of this event"""
        import copy
        return copy.deepcopy(self)
    
    def serialize(self) -> Dict[str, Any]:
        """Serialize event to dictionary"""
        return {
            'type': self.__class__.__name__,
            'id': self._id.id,
            'priority': self._priority.value,
            'data': self._serialize_data()
        }
    
    @abstractmethod
    def _serialize_data(self) -> Dict[str, Any]:
        """Serialize event-specific data"""
        pass
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'Event':
        """Deserialize event from dictionary"""
        deserialized_event = cls()
        deserialized_event._id = EventId(data['id'], 0)
        deserialized_event._priority = EventPriority(data['priority'])
        deserialized_event._deserialize_data(data['data'])
        return deserialized_event
    
    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        """Deserialize event-specific data"""
        pass
    
    def __str__(self) -> str:
        return f"Event({self.__class__.__name__}, id={self._id.id})"
    
    def __repr__(self) -> str:
        return self.__str__()


class EmptyEvent(Event):
    """Empty event that carries no data"""
    
    def _serialize_data(self) -> Dict[str, Any]:
        return {}
    
    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        pass


class StringEvent(Event):
    """Event that carries a string message"""
    
    def __init__(self, message: str = ""):
        super().__init__()
        self.message = message
    
    def _serialize_data(self) -> Dict[str, Any]:
        return {'message': self.message}
    
    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.message = data.get('message', '')


class DataEvent(Event):
    """Event that carries arbitrary data"""
    
    def __init__(self, data: Any = None):
        super().__init__()
        self.data = data
    
    def _serialize_data(self) -> Dict[str, Any]:
        return {'data': self.data}
    
    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.data = data.get('data')


class RequestEvent(Event):
    """Event for making requests between components"""
    
    def __init__(self, request_type: str, data: Any = None):
        super().__init__()
        self.request_type = request_type
        self.data = data
    
    def _serialize_data(self) -> Dict[str, Any]:
        return {
            'request_type': self.request_type,
            'data': self.data
        }
    
    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.request_type = data.get('request_type', '')
        self.data = data.get('data')


class ResponseEvent(Event):
    """Event for responding to requests"""
    
    def __init__(self, success: bool = True, data: Any = None, error: str = ""):
        super().__init__()
        self.success = success
        self.data = data
        self.error = error
    
    def _serialize_data(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error
        }
    
    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        self.success = data.get('success', True)
        self.data = data.get('data')
        self.error = data.get('error', '')
