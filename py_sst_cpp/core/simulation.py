# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
SST Simulation Engine

Main simulation engine that manages components, events, and time advancement.
"""

import heapq
import threading
from enum import Enum
from typing import Optional, Callable, Dict

from .event import Event
from .component import Component
from .clock import TimeConverter
from .statistics import Statistics
from .output import Output


class SimulationState(Enum):
    """Simulation execution states"""
    INIT = "init"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    ERROR = "error"


class ScheduledEvent:
    """Event scheduled for future execution"""
    def __init__(self, time, priority, event, component, handler):
        self.time = time  # Simulation time in cycles
        self.priority = priority  # Event priority (lower = higher priority)
        self.event = event
        self.component = component
        self.handler = handler
    
    def __lt__(self, other):
        """For heapq ordering: time first, then priority"""
        if self.time != other.time:
            return self.time < other.time
        return self.priority < other.priority


class Simulation:
    """Run component lifecycles and scheduled events in cycle order."""
    
    def __init__(self, name: str = "SST_Simulation"):
        self.name = name
        self.state = SimulationState.INIT
        
        # Core simulation data
        self._current_time = 0
        self._end_time = None
        self._event_queue = []  # Priority queue for scheduled events
        self._components: Dict[str, Component] = {}
        self._links: Dict[str, 'Link'] = {}
        
        # Statistics and output
        self._statistics = Statistics()
        self._output = Output("Simulation", 1, 0)
        
        # Threading
        self._lock = threading.RLock()
        
        # Simulation control
        self._running = False
        self._paused = False
        
    def add_component(self, name, component):
        """Add a component to the simulation"""
        with self._lock:
            if name in self._components:
                raise ValueError(f"Component '{name}' already exists")
            
            self._components[name] = component
            component._simulation = self
            component._name = name
            
            self._output.verbose(f"Added component: {name}")
            return component
    
    def get_component(self, name: str) -> Optional[Component]:
        """Get a component by name"""
        return self._components.get(name)
    
    def add_link(self, name: str, link: 'Link') -> 'Link':
        """Add a link to the simulation"""
        with self._lock:
            if name in self._links:
                raise ValueError(f"Link '{name}' already exists")
            
            self._links[name] = link
            link._simulation = self
            link._name = name
            
            self._output.verbose(f"Added link: {name}")
            return link
    
    def schedule_event(self, delay: int, event: Event, component: Component, 
                      handler: Callable, priority: int = 0) -> None:
        """
        Schedule an event for future execution.
        
        Args:
            delay: Delay in simulation cycles
            event: Event to schedule
            component: Target component
            handler: Handler function to call
            priority: Event priority (lower = higher priority)
        """
        with self._lock:
            delivery_cycle = self._current_time + delay
            scheduled_event = ScheduledEvent(
                time=delivery_cycle,
                priority=priority,
                event=event,
                component=component,
                handler=handler
            )
            
            heapq.heappush(self._event_queue, scheduled_event)
            self._output.verbose(f"Scheduled event for time {delivery_cycle}")
    
    def run(self, end_time: Optional[int] = None) -> None:
        """
        Run the simulation.
        
        Args:
            end_time: Maximum simulation time (None for unlimited)
        """
        with self._lock:
            if self.state != SimulationState.INIT:
                raise RuntimeError("Simulation can only be run once")
            
            self._end_time = end_time
            self.state = SimulationState.RUNNING
            self._running = True
            self._paused = False
            
            self._output.verbose(f"Starting simulation: {self.name}")
            
            # Initialize all components
            self._initialize_components()
            
            # Main simulation loop
            self._simulation_loop()
            
            # Finalize all components
            self._finalize_components()
            
            self.state = SimulationState.FINISHED
            self._running = False
            
            self._output.verbose(f"Simulation completed at time {self._current_time}")
    
    def pause(self) -> None:
        """Pause the simulation"""
        with self._lock:
            if self.state == SimulationState.RUNNING:
                self._paused = True
                self.state = SimulationState.PAUSED
                self._output.verbose("Simulation paused")
    
    def resume(self) -> None:
        """Resume the simulation"""
        with self._lock:
            if self.state == SimulationState.PAUSED:
                self._paused = False
                self.state = SimulationState.RUNNING
                self._output.verbose("Simulation resumed")
    
    def stop(self) -> None:
        """Stop the simulation"""
        with self._lock:
            self._running = False
            self.state = SimulationState.FINISHED
            self._output.verbose("Simulation stopped")
    
    def get_current_time(self) -> int:
        """Get current simulation time"""
        return self._current_time
    
    def get_statistics(self) -> Statistics:
        """Get statistics collector"""
        return self._statistics
    
    def get_output(self) -> Output:
        """Get output logger"""
        return self._output
    
    def _initialize_components(self) -> None:
        """Initialize all components"""
        for component in self._components.values():
            try:
                component.setup()
                self._output.verbose(f"Initialized component: {component._name}")
            except Exception as error:
                self._output.fatal(f"Failed to initialize component {component._name}: {error}")
                raise
    
    def _finalize_components(self) -> None:
        """Finalize all components"""
        for component in self._components.values():
            try:
                component.finish()
                self._output.verbose(f"Finalized component: {component._name}")
            except Exception as error:
                self._output.fatal(f"Failed to finalize component {component._name}: {error}")
    
    def _simulation_loop(self) -> None:
        """Main simulation event loop"""
        while self._running and self._event_queue:
            # Check if we've reached the end time
            if self._end_time is not None and self._current_time >= self._end_time:
                break
            
            next_event = heapq.heappop(self._event_queue)
            
            # Advance time
            self._current_time = next_event.time
            
            # Check for pause
            while self._paused and self._running:
                threading.Event().wait(0.001)  # Small delay
            
            if not self._running:
                break
            
            # Execute the event
            try:
                next_event.handler(next_event.event)
                self._output.verbose(f"Executed event at time {self._current_time}")
            except Exception as error:
                self._output.fatal(f"Error executing event: {error}")
                self.state = SimulationState.ERROR
                break
    
    def __str__(self) -> str:
        return f"Simulation({self.name}, state={self.state.value}, time={self._current_time})"
    
    def __repr__(self) -> str:
        return self.__str__()
