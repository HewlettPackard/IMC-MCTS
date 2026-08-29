# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
SST Clock System

Clock and time management for discrete-event simulation.
"""

import re
from typing import Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum


class TimeUnit(Enum):
    """Time units for simulation"""
    CYCLE = "cycle"
    SECOND = "s"
    MILLISECOND = "ms"
    MICROSECOND = "us"
    NANOSECOND = "ns"
    PICOSECOND = "ps"
    FEMTOSECOND = "fs"
    HERTZ = "Hz"
    KILOHERTZ = "kHz"
    MEGAHERTZ = "MHz"
    GIGAHERTZ = "GHz"
    TERAHERTZ = "THz"


@dataclass
class TimeValue:
    """Time value with unit"""
    value: float
    unit: TimeUnit
    
    def __str__(self) -> str:
        return f"{self.value}{self.unit.value}"


class TimeConverter:
    """Convert physical time values to and from simulation cycles."""
    
    # Base time unit is picoseconds
    UNIT_FACTORS = {
        TimeUnit.FEMTOSECOND: 1e-3,
        TimeUnit.PICOSECOND: 1.0,
        TimeUnit.NANOSECOND: 1e3,
        TimeUnit.MICROSECOND: 1e6,
        TimeUnit.MILLISECOND: 1e9,
        TimeUnit.SECOND: 1e12,
        TimeUnit.CYCLE: 0,  # Special case - depends on frequency
    }
    
    def __init__(self, frequency: float = 1e9):  # Default 1 GHz
        """
        Initialize time converter.
        
        Args:
            frequency: Base frequency in Hz for cycle conversion
        """
        self._frequency = frequency
        self._cycle_time_ps = 1e12 / frequency  # Picoseconds per cycle
    
    @property
    def frequency(self) -> float:
        """Get base frequency in Hz"""
        return self._frequency
    
    @frequency.setter
    def frequency(self, value: float) -> None:
        """Set base frequency in Hz"""
        self._frequency = value
        self._cycle_time_ps = 1e12 / value
    
    def convert_to_cycles(self, time_value: TimeValue) -> int:
        """
        Convert time value to simulation cycles.
        
        Args:
            time_value: Time value to convert
            
        Returns:
            Number of simulation cycles
        """
        if time_value.unit == TimeUnit.CYCLE:
            return int(time_value.value)
        
        time_ps = time_value.value * self.UNIT_FACTORS[time_value.unit]
        cycle_count = time_ps / self._cycle_time_ps
        return int(round(cycle_count))
    
    def convert_to_core_time(self, time_value: TimeValue) -> int:
        """Alias for convert_to_cycles"""
        return self.convert_to_cycles(time_value)
    
    def convert_from_cycles(self, cycles: int, unit: TimeUnit) -> float:
        """
        Convert simulation cycles to time value.
        
        Args:
            cycles: Number of simulation cycles
            unit: Target time unit
            
        Returns:
            Time value in specified unit
        """
        if unit == TimeUnit.CYCLE:
            return float(cycles)
        
        time_ps = cycles * self._cycle_time_ps
        return time_ps / self.UNIT_FACTORS[unit]
    
    def parse_time_string(self, time_str: str) -> TimeValue:
        """
        Parse time string (e.g., "1.5ns", "2GHz", "100cycles").
        
        Args:
            time_str: Time string to parse
            
        Returns:
            TimeValue object
        """
        time_str = time_str.strip()

        pattern = r'^([+-]?\d*\.?\d+)\s*([a-zA-Z]+)$'
        match = re.match(pattern, time_str)
        
        if not match:
            raise ValueError(f"Invalid time string: {time_str}")
        
        value_str, unit_str = match.groups()
        value = float(value_str)
        
        unit_map = {
            'cycle': TimeUnit.CYCLE,
            'cycles': TimeUnit.CYCLE,
            's': TimeUnit.SECOND,
            'sec': TimeUnit.SECOND,
            'second': TimeUnit.SECOND,
            'ms': TimeUnit.MILLISECOND,
            'msec': TimeUnit.MILLISECOND,
            'millisecond': TimeUnit.MILLISECOND,
            'us': TimeUnit.MICROSECOND,
            'usec': TimeUnit.MICROSECOND,
            'microsecond': TimeUnit.MICROSECOND,
            'ns': TimeUnit.NANOSECOND,
            'nsec': TimeUnit.NANOSECOND,
            'nanosecond': TimeUnit.NANOSECOND,
            'ps': TimeUnit.PICOSECOND,
            'psec': TimeUnit.PICOSECOND,
            'picosecond': TimeUnit.PICOSECOND,
            'fs': TimeUnit.FEMTOSECOND,
            'fsec': TimeUnit.FEMTOSECOND,
            'femtosecond': TimeUnit.FEMTOSECOND,
            'Hz': TimeUnit.HERTZ,
            'kHz': TimeUnit.KILOHERTZ,
            'MHz': TimeUnit.MEGAHERTZ,
            'GHz': TimeUnit.GIGAHERTZ,
            'THz': TimeUnit.TERAHERTZ,
        }
        
        unit = unit_map.get(unit_str.lower())
        if unit is None:
            raise ValueError(f"Unknown time unit: {unit_str}")
        
        return TimeValue(value, unit)
    
    def __str__(self) -> str:
        return f"TimeConverter({self._frequency}Hz)"
    
    def __repr__(self) -> str:
        return self.__str__()


class Clock:
    """
    Clock for component timing.
    
    Provides periodic timing events for components.
    """
    
    def __init__(self, frequency: float, handler: Callable[[int], bool], 
                 component: Any):
        """
        Initialize clock.
        
        Args:
            frequency: Clock frequency in Hz
            handler: Handler function (cycle) -> bool (continue)
            component: Owning component
        """
        self._frequency = frequency
        self._handler = handler
        self._component = component
        self._time_converter = TimeConverter(frequency)
        self._enabled = True
    
    @property
    def frequency(self) -> float:
        """Get clock frequency"""
        return self._frequency
    
    @property
    def time_converter(self) -> TimeConverter:
        """Get time converter for this clock"""
        return self._time_converter
    
    @property
    def enabled(self) -> bool:
        """Check if clock is enabled"""
        return self._enabled
    
    def enable(self) -> None:
        """Enable clock"""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable clock"""
        self._enabled = False
    
    def tick(self, cycle: int) -> bool:
        """
        Process clock tick.
        
        Args:
            cycle: Current simulation cycle
            
        Returns:
            True if clock should continue, False to stop
        """
        if not self._enabled:
            return True
        
        try:
            return self._handler(cycle)
        except Exception as error:
            print(f"Error in clock handler: {error}")
            return False
    
    def __str__(self) -> str:
        return f"Clock({self._frequency}Hz, enabled={self._enabled})"
    
    def __repr__(self) -> str:
        return self.__str__()
