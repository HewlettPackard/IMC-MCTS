# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
SST Link System

Link classes for inter-component communication.
"""

from typing import Optional, Callable, Any, List
from dataclasses import dataclass
from enum import Enum

from .event import Event
from .clock import TimeConverter
# from .component import BaseComponent  # Removed to avoid circular import


class LinkType(Enum):
    """Link connection types"""
    POLL = "poll"
    HANDLER = "handler"
    SYNC = "sync"
    UNINITIALIZED = "uninitialized"


@dataclass
class LinkId:
    """Unique link identifier"""
    id: int
    name: str
    
    def __str__(self) -> str:
        return f"LinkId({self.id}, {self.name})"


class Link:
    """Deliver events between two components with explicit cycle latency."""
    
    _next_id = 0
    
    def __init__(self, name: str = ""):
        self._id = LinkId(Link._next_id, name)
        Link._next_id += 1
        
        self._name = name
        self._simulation = None
        self._owner = None
        
        # Link configuration
        self._type = LinkType.UNINITIALIZED
        self._latency = 0  # Base latency in cycles
        self._send_latency = 0  # Additional send latency
        self._recv_latency = 0  # Additional receive latency
        
        # Connection info
        self._pair_link: Optional['Link'] = None
        self._source_component = None
        self._target_component = None
        self._source_port: str = ""
        self._target_port: str = ""
        
        # Event handling
        self._handler: Optional[Callable[[Event], None]] = None
        self._event_queue: List[Event] = []
        
        # Time management
        self._default_time_base: Optional[TimeConverter] = None
        
        # Statistics
        self._events_sent = 0
        self._events_received = 0
        self._total_latency = 0
    
    @property
    def id(self) -> LinkId:
        """Get link ID"""
        return self._id
    
    @property
    def name(self) -> str:
        """Get link name"""
        return self._name
    
    @property
    def latency(self) -> int:
        """Get base latency"""
        return self._latency
    
    @latency.setter
    def latency(self, value: int) -> None:
        """Set base latency"""
        self._latency = max(0, value)
    
    @property
    def is_configured(self) -> bool:
        """Check if link is configured"""
        return self._type != LinkType.UNINITIALIZED
    
    def connect(self, source, target, latency=0):
        """
        Connect this link between two components.
        
        Args:
            source: (component, port, latency) tuple
            target: (component, port, latency) tuple
            latency: Base latency for the link
            
        Returns:
            Self for chaining
        """
        if len(source) != 3 or len(target) != 3:
            raise ValueError("Source and target must be (component, port, latency) tuples")
        
        source_component, source_port, source_latency = source
        target_component, target_port, target_latency = target
        
        # Set connection info
        self._source_component = source_component
        self._target_component = target_component
        self._source_port = source_port
        self._target_port = target_port
        
        # Set latencies
        self._latency = latency
        self._send_latency = source_latency
        self._recv_latency = target_latency
        
        # Configure as handler link by default
        self._type = LinkType.HANDLER
        
        return self
    
    def set_handler(self, handler):
        """Set event handler for this link"""
        self._handler = handler
        self._type = LinkType.HANDLER
    
    def set_polling(self):
        """Configure link for polling (no handler)"""
        self._handler = None
        self._type = LinkType.POLL
    
    def send(self, event, delay=0):
        """
        Send an event over this link.
        
        Args:
            event: Event to send
            delay: Additional delay in cycles
        """
        if not self._simulation:
            raise RuntimeError("Link not attached to simulation")
        
        if not self._target_component:
            raise RuntimeError("Link not connected to target component")
        
        delivery_delay = self._latency + self._send_latency + delay
        
        # Set event metadata
        event.sender = self._source_component
        event.receiver = self._target_component
        
        # Schedule event delivery
        if self._handler:
            # Handler-based delivery
            self._simulation.schedule_event(
                delivery_delay, event, self._target_component, self._handler
            )
        else:
            # Polling-based delivery - add to queue
            self._event_queue.append(event)
        
        # Update statistics
        self._events_sent += 1
        self._total_latency += delivery_delay
    
    def recv(self):
        """
        Receive an event from this link (polling mode).
        
        Returns:
            Event if available, None otherwise
        """
        if self._type != LinkType.POLL:
            raise RuntimeError("Link not configured for polling")
        
        if self._event_queue:
            queued_event = self._event_queue.pop(0)
            self._events_received += 1
            return queued_event
        
        return None
    
    def send_untimed(self, event):
        """Send an event without timing (for initialization)"""
        if not self._target_component:
            raise RuntimeError("Link not connected to target component")
        
        event.sender = self._source_component
        event.receiver = self._target_component
        
        if self._handler:
            self._handler(event)
        else:
            self._event_queue.append(event)
    
    def recv_untimed(self):
        """Receive an event without timing (for initialization)"""
        return self.recv()
    
    def set_default_time_base(self, time_converter):
        """Set default time base for this link"""
        self._default_time_base = time_converter
    
    def get_default_time_base(self):
        """Get default time base for this link"""
        return self._default_time_base
    
    def add_send_latency(self, cycles, time_base="1Hz"):
        """Add additional send latency"""
        self._send_latency += cycles
    
    def add_recv_latency(self, cycles, time_base="1Hz"):
        """Add additional receive latency"""
        self._recv_latency += cycles
    
    def set_no_cut(self):
        """Mark link as not to be cut during partitioning"""
        # This is a placeholder for future partitioning support
        return self
    
    def get_statistics(self):
        """Get link statistics"""
        return {
            'events_sent': self._events_sent,
            'events_received': self._events_received,
            'total_latency': self._total_latency,
            'average_latency': self._total_latency / max(1, self._events_sent),
            'queue_size': len(self._event_queue)
        }
    
    def __str__(self) -> str:
        return f"Link({self._name}, type={self._type.value})"
    
    def __repr__(self) -> str:
        return self.__str__()


class SelfLink(Link):
    """Link from a component to itself"""
    
    def __init__(self, name: str = ""):
        super().__init__(name)
        self._pair_link = self
        self._latency = 0
