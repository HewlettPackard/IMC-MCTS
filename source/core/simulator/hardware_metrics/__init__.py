# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Hardware metrics for Accelerator event-driven simulations.

The modules combine simulated activity and timing with analytical hardware
models to estimate area, power, energy, latency, and throughput.

Inspired by the separation of concerns in real SST workflows where:
- SST provides cycle-accurate timing
- External tools (McPAT, CACTI, etc.) provide hardware metrics

Modules:
- hardware_model: Area and power specifications from board_config
- activity_tracker: Operation counting during simulation
- metrics_calculator: Energy, latency, and throughput from cycles and activity
"""

from .hardware_model import HardwareModel
from .activity_tracker import ActivityTracker
from .metrics_calculator import MetricsCalculator

__all__ = ['HardwareModel', 'ActivityTracker', 'MetricsCalculator']
__version__ = '1.0.0'
