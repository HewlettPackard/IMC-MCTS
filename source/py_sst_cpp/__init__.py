# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Lightweight discrete-event simulation framework (SST-style)

An independent, lightweight discrete-event simulation framework written in the
style of the SST component/link/event model. It is not derived from or affiliated
with Sandia National Labs' SST and contains no SST source code. An optional
bridge can call user-provided C++ components.
"""

# Import core classes (note: these are the actual classes)
from .core import Simulation
from .core.component import Component, BaseComponent, ComponentId
from .core.link import Link, SelfLink
from .core.event import Event, StringEvent, EmptyEvent, DataEvent
from .core.config import Params, Config
from .cpp_bridge import CppComponent, CppBridge
from . import examples

__version__ = "1.0.0"
__author__ = "IMC-MCTS contributors"
__description__ = "SST-style discrete-event simulation with an optional C++ component bridge"

# Global simulation instance
_simulation = None

def setSimulation(sim):
    """Set the global simulation instance"""
    global _simulation
    _simulation = sim

def getSimulation():
    """Get the global simulation instance"""
    return _simulation

# Convenience factory functions (note: different names to avoid shadowing)
def create_component(name, component_type, **params):
    """Create a component (convenience factory function)"""
    if not _simulation:
        raise RuntimeError("No simulation instance set")

    component_id = ComponentId(0, name)
    component_params = Params(params)

    return Component(component_id, component_params)

def create_cpp_component(name, cpp_lib_path, component_type, **params):
    """Create a C++ component wrapper (convenience factory function)"""
    if not _simulation:
        raise RuntimeError("No simulation instance set")

    component_id = ComponentId(0, name)
    component_params = Params(params)

    return CppComponent(component_id, cpp_lib_path, component_type, component_params)

def create_link(name=""):
    """Create a link (convenience factory function)"""
    return Link(name)
