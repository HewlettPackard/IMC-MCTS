#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Hybrid Python-C++ SST Simulation Example

This example shows how to use both Python and C++ components
in the same SST simulation.
"""

import sys
import os

# Add the py_sst_cpp directory to the path

from py_sst_cpp.core import Simulation, Component, Link, StringEvent
from py_sst_cpp.core.component import ComponentId
from py_sst_cpp.core.config import Params
from py_sst_cpp.cpp_bridge import CppComponent, CppBridge
from py_sst_cpp.component_compiler import ComponentCompiler, compile_accelerator_components


class PythonHost(Component):
    """Python host component that controls C++ components"""
    
    def __init__(self, component_id, params):
        super().__init__(component_id, params)
        self.cpp_components = {}
        self.message_count = 0
        self.max_messages = self.get_param_int("max_messages", 5)
        
    def _setup_impl(self):
        """Setup the Python host"""
        print("Setting up Python Host")
        self.register_clock(1.0, self._clock_tick)  # 1 Hz
        
    def _clock_tick(self, cycle):
        """Clock tick handler"""
        if self.message_count < self.max_messages:
            # Send message to C++ components
            message = StringEvent(f"Hello from Python at cycle {cycle}")
            
            for component_name, component_link in self.cpp_components.items():
                if component_link:
                    component_link.send(message)
                    print(f"Sent message to {component_name}")
            
            self.message_count += 1
        
        return self.message_count < self.max_messages
    
    def handle_response(self, event):
        """Handle response from C++ components"""
        if hasattr(event, 'message'):
            print(f"Received from C++: {event.message}")
    
    def add_cpp_component(self, name, link):
        """Add a C++ component link"""
        self.cpp_components[name] = link


def create_hybrid_simulation():
    """Create a hybrid Python-C++ simulation"""
    print("Creating hybrid Python-C++ simulation...")
    
    # Create simulation
    simulation = Simulation("HybridSimulation")
    
    # Create Python host
    python_host = PythonHost(ComponentId(1, "python_host"),
                            Params({"max_messages": 3}))
    simulation.add_component("python_host", python_host)
    
    # Try to compile and load C++ components
    cpp_bridge = CppBridge()
    compiled_cpp_components = {}
    
    # Look for existing compiled components
    sst_source_dir = os.path.join(os.path.dirname(__file__), "..", "..", "src")
    
    if os.path.exists(sst_source_dir):
        print(f"Found SST project directory: {sst_source_dir}")
        
        # Compile C++ components
        try:
            component_compiler = ComponentCompiler()
            compiled_cpp_components = compile_accelerator_components(sst_source_dir)
            print(f"Compiled {len(compiled_cpp_components)} C++ components")
        except Exception as error:
            print(f"Failed to compile C++ components: {error}")
            print("Continuing with Python-only simulation...")
    else:
        print("SST project directory not found, using Python-only simulation")
    
    # Create C++ components if available
    cpp_components = {}
    for component_name, library_path in compiled_cpp_components.items():
        try:
            cpp_component = CppComponent(
                ComponentId(len(cpp_components) + 2, component_name),
                library_path,
                component_name,
                Params({"clock": 1.0})
            )
            simulation.add_component(component_name, cpp_component)
            cpp_components[component_name] = cpp_component
            print(f"Added C++ component: {component_name}")
        except Exception as error:
            print(f"Failed to create C++ component {component_name}: {error}")
    
    # Create links between Python and C++ components
    component_links = {}
    for component_name, cpp_component in cpp_components.items():
        # Python to C++
        python_to_cpp_link = Link(f"py_to_{component_name}")
        python_to_cpp_link.connect((python_host, "output", 0), (cpp_component, "input", 0))
        simulation.add_link(f"py_to_{component_name}", python_to_cpp_link)
        
        # C++ to Python
        cpp_to_python_link = Link(f"{component_name}_to_py")
        cpp_to_python_link.connect((cpp_component, "output", 0), (python_host, "input", 0))
        simulation.add_link(f"{component_name}_to_py", cpp_to_python_link)
        
        # Set up links
        python_host.add_cpp_component(component_name, python_to_cpp_link)
        python_to_cpp_link.set_handler(cpp_component.handle_event)
        cpp_to_python_link.set_handler(python_host.handle_response)
        
        component_links[component_name] = (python_to_cpp_link, cpp_to_python_link)
    
    return simulation, cpp_components


def main():
    """Run the hybrid simulation"""
    print("=" * 60)
    print("Hybrid Python-C++ SST Simulation")
    print("=" * 60)
    print()
    print("This demo shows:")
    print("- Python SST simulation framework")
    print("- Integration with C++ components")
    print("- Automatic compilation of C++ components")
    print("- Cross-language communication")
    print()
    
    # Create and run simulation
    simulation, cpp_components = create_hybrid_simulation()
    
    print(f"Created simulation with {len(cpp_components)} C++ components")
    print()
    
    print("Starting simulation...")
    print("-" * 40)
    
    import time
    start_time = time.time()
    simulation.run(end_time=100)  # Run for 100 cycles
    end_time = time.time()
    
    print("-" * 40)
    print(f"Simulation completed in {end_time - start_time:.2f} seconds")
    print()
    
    # Print statistics
    simulation_statistics = simulation.get_statistics().get_summary()
    print("Simulation Statistics:")
    print("-" * 40)
    for statistic_name, statistic in simulation_statistics.items():
        print(f"  {statistic_name}: {statistic['value']} {statistic.get('unit', '')}")
    
    print()
    print("=" * 60)
    print("Hybrid simulation completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
