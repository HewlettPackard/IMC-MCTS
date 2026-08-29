# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Python SST (Structural Simulation Toolkit) - Core Module

A Python implementation of SST for macOS compatibility.
Provides discrete-event simulation capabilities for hardware modeling.
"""

from .simulation import Simulation
from .component import Component
from .event import Event, EmptyEvent, StringEvent
from .link import Link, SelfLink
from .clock import Clock, TimeConverter
from .statistics import Statistics, Statistic
from .config import Config, Params
from .output import Output

# Import BaseComponent separately to avoid circular import
from .component import BaseComponent

__version__ = "1.0.0"
__all__ = [
    'Simulation',
    'Component', 
    'BaseComponent',
    'Event',
    'EmptyEvent',
    'StringEvent', 
    'Link',
    'SelfLink',
    'Clock',
    'TimeConverter',
    'Statistics',
    'Statistic',
    'Config',
    'Params',
    'Output'
]
