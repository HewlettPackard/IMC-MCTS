# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
SST Statistics System

Statistics collection and reporting for simulation components.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import time


class StatisticType(Enum):
    """Types of statistics"""
    COUNTER = "counter"
    ACCUMULATOR = "accumulator"
    HISTOGRAM = "histogram"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    RATE = "rate"


@dataclass
class StatisticInfo:
    """Information about a statistic"""
    name: str
    type: StatisticType
    description: str
    unit: str = ""
    enabled: bool = True


class Statistic(ABC):
    """Base class for all statistics"""
    
    def __init__(self, name: str, description: str = "", unit: str = ""):
        self.name = name
        self.description = description
        self.unit = unit
        self.enabled = True
        self._data_points = 0
    
    @property
    def data_points(self) -> int:
        """Get number of data points"""
        return self._data_points
    
    @abstractmethod
    def add_data(self, value: Any) -> None:
        """Add a data point"""
        pass
    
    @abstractmethod
    def get_value(self) -> Any:
        """Get current statistic value"""
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset statistic to initial state"""
        pass
    
    def enable(self) -> None:
        """Enable statistic collection"""
        self.enabled = True
    
    def disable(self) -> None:
        """Disable statistic collection"""
        self.enabled = False
    
    def get_info(self) -> StatisticInfo:
        """Get statistic information"""
        return StatisticInfo(
            name=self.name,
            type=self._get_type(),
            description=self.description,
            unit=self.unit,
            enabled=self.enabled
        )
    
    @abstractmethod
    def _get_type(self) -> StatisticType:
        """Get statistic type"""
        pass


class CounterStatistic(Statistic):
    """Counter statistic - counts occurrences"""
    
    def __init__(self, name: str, description: str = "", unit: str = ""):
        super().__init__(name, description, unit)
        self._count = 0
    
    def add_data(self, value: Union[int, float] = 1) -> None:
        """Add to counter"""
        if self.enabled:
            self._count += value
            self._data_points += 1
    
    def get_value(self) -> Union[int, float]:
        """Get current count"""
        return self._count
    
    def reset(self) -> None:
        """Reset counter"""
        self._count = 0
        self._data_points = 0
    
    def _get_type(self) -> StatisticType:
        return StatisticType.COUNTER


class AccumulatorStatistic(Statistic):
    """Accumulator statistic - sums values"""
    
    def __init__(self, name: str, description: str = "", unit: str = ""):
        super().__init__(name, description, unit)
        self._sum = 0.0
        self._count = 0
    
    def add_data(self, value: Union[int, float]) -> None:
        """Add value to accumulator"""
        if self.enabled:
            self._sum += value
            self._count += 1
            self._data_points += 1
    
    def get_value(self) -> float:
        """Get current sum"""
        return self._sum
    
    def get_average(self) -> float:
        """Get average value"""
        return self._sum / max(1, self._count)
    
    def reset(self) -> None:
        """Reset accumulator"""
        self._sum = 0.0
        self._count = 0
        self._data_points = 0
    
    def _get_type(self) -> StatisticType:
        return StatisticType.ACCUMULATOR


class HistogramStatistic(Statistic):
    """Histogram statistic - distribution of values"""
    
    def __init__(self, name: str, description: str = "", unit: str = "", 
                 bins: int = 10, min_val: float = 0.0, max_val: float = 100.0):
        super().__init__(name, description, unit)
        self._bins = bins
        self._min_val = min_val
        self._max_val = max_val
        self._bin_counts = [0] * bins
        self._values = []
        self._count = 0
    
    def add_data(self, value: Union[int, float]) -> None:
        """Add value to histogram"""
        if self.enabled:
            self._values.append(value)
            self._count += 1
            self._data_points += 1
            
            # Determine bin
            if value < self._min_val:
                bin_index = 0
            elif value >= self._max_val:
                bin_index = self._bins - 1
            else:
                bin_index = int((value - self._min_val) / (self._max_val - self._min_val) * self._bins)
                bin_index = min(bin_index, self._bins - 1)
            
            self._bin_counts[bin_index] += 1
    
    def get_value(self) -> Dict[str, Any]:
        """Get histogram data"""
        return {
            'bins': self._bin_counts,
            'min': self._min_val,
            'max': self._max_val,
            'count': self._count,
            'values': self._values.copy()
        }
    
    def get_bin_counts(self) -> List[int]:
        """Get bin counts"""
        return self._bin_counts.copy()
    
    def reset(self) -> None:
        """Reset histogram"""
        self._bin_counts = [0] * self._bins
        self._values = []
        self._count = 0
        self._data_points = 0
    
    def _get_type(self) -> StatisticType:
        return StatisticType.HISTOGRAM


class AverageStatistic(Statistic):
    """Average statistic - running average of values"""
    
    def __init__(self, name: str, description: str = "", unit: str = ""):
        super().__init__(name, description, unit)
        self._sum = 0.0
        self._count = 0
    
    def add_data(self, value: Union[int, float]) -> None:
        """Add value to average"""
        if self.enabled:
            self._sum += value
            self._count += 1
            self._data_points += 1
    
    def get_value(self) -> float:
        """Get current average"""
        return self._sum / max(1, self._count)
    
    def reset(self) -> None:
        """Reset average"""
        self._sum = 0.0
        self._count = 0
        self._data_points = 0
    
    def _get_type(self) -> StatisticType:
        return StatisticType.AVERAGE


class MinMaxStatistic(Statistic):
    """Min/Max statistic - tracks minimum and maximum values"""
    
    def __init__(self, name: str, description: str = "", unit: str = "", 
                 track_min: bool = True, track_max: bool = True):
        super().__init__(name, description, unit)
        self._track_min = track_min
        self._track_max = track_max
        self._min_val = float('inf') if track_min else None
        self._max_val = float('-inf') if track_max else None
        self._count = 0
    
    def add_data(self, value: Union[int, float]) -> None:
        """Add value to min/max"""
        if self.enabled:
            self._count += 1
            self._data_points += 1
            
            if self._track_min:
                self._min_val = min(self._min_val, value)
            if self._track_max:
                self._max_val = max(self._max_val, value)
    
    def get_value(self) -> Dict[str, Any]:
        """Get min/max values"""
        min_max_values = {}
        if self._track_min:
            min_max_values['min'] = self._min_val if self._min_val != float('inf') else None
        if self._track_max:
            min_max_values['max'] = self._max_val if self._max_val != float('-inf') else None
        return min_max_values
    
    def get_min(self) -> Optional[float]:
        """Get minimum value"""
        return self._min_val if self._min_val != float('inf') else None
    
    def get_max(self) -> Optional[float]:
        """Get maximum value"""
        return self._max_val if self._max_val != float('-inf') else None
    
    def reset(self) -> None:
        """Reset min/max"""
        self._min_val = float('inf') if self._track_min else None
        self._max_val = float('-inf') if self._track_max else None
        self._count = 0
        self._data_points = 0
    
    def _get_type(self) -> StatisticType:
        return StatisticType.MIN if self._track_min else StatisticType.MAX


class RateStatistic(Statistic):
    """Rate statistic - events per unit time"""
    
    def __init__(self, name: str, description: str = "", unit: str = "Hz"):
        super().__init__(name, description, unit)
        self._count = 0
        self._start_time = time.time()
        self._last_time = self._start_time
    
    def add_data(self, value: Union[int, float] = 1) -> None:
        """Add event to rate calculation"""
        if self.enabled:
            self._count += value
            self._data_points += 1
            self._last_time = time.time()
    
    def get_value(self) -> float:
        """Get current rate"""
        if self._count == 0:
            return 0.0
        
        elapsed_seconds = self._last_time - self._start_time
        return self._count / max(elapsed_seconds, 1e-6)  # Avoid division by zero
    
    def reset(self) -> None:
        """Reset rate calculation"""
        self._count = 0
        self._start_time = time.time()
        self._last_time = self._start_time
        self._data_points = 0
    
    def _get_type(self) -> StatisticType:
        return StatisticType.RATE


class Statistics:
    """Statistics collection manager"""
    
    def __init__(self):
        self._statistics: Dict[str, Statistic] = {}
        self._enabled = True
    
    def add_statistic(self, name: str, stat: Statistic) -> Statistic:
        """Add a statistic"""
        self._statistics[name] = stat
        return stat
    
    def get_statistic(self, name: str) -> Optional[Statistic]:
        """Get a statistic by name"""
        return self._statistics.get(name)
    
    def get_all_statistics(self) -> Dict[str, Statistic]:
        """Get all statistics"""
        return self._statistics.copy()
    
    def enable_all(self) -> None:
        """Enable all statistics"""
        self._enabled = True
        for statistic in self._statistics.values():
            statistic.enable()
    
    def disable_all(self) -> None:
        """Disable all statistics"""
        self._enabled = False
        for statistic in self._statistics.values():
            statistic.disable()
    
    def reset_all(self) -> None:
        """Reset all statistics"""
        for statistic in self._statistics.values():
            statistic.reset()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all statistics"""
        summary = {}
        for name, statistic in self._statistics.items():
            if statistic.enabled:
                summary[name] = {
                    'type': statistic._get_type().value,
                    'value': statistic.get_value(),
                    'data_points': statistic.data_points,
                    'unit': statistic.unit
                }
        return summary
