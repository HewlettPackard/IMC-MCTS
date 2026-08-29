# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
C++ Bridge for the SST-style simulation framework

Provides an optional bridge so the Python discrete-event framework can call
user-provided C++ components. This is an independent implementation and is not
affiliated with Sandia National Labs' SST.
"""

import os
import sys
import ctypes
import subprocess
import tempfile
from typing import Dict, Any, Optional

from .core.component import Component, ComponentId
from .core.config import Params
from .core.event import Event


class CppBridge:
    """
    Bridge between Python SST and C++ components.
    
    Handles:
    - Compiling C++ components into shared libraries
    - Loading C++ libraries via ctypes
    - Marshalling data between Python and C++
    - Managing C++ component lifecycle
    """
    
    def __init__(self, sst_install_path: str = None):
        """
        Initialize C++ bridge.
        
        Args:
            sst_install_path: Path to SST installation (if available)
        """
        self.sst_install_path = sst_install_path
        self.compiled_libs = {}
        self.loaded_libs = {}
        
        # Try to find SST installation
        if not sst_install_path:
            self.sst_install_path = self._find_sst_installation()
    
    def _find_sst_installation(self) -> Optional[str]:
        """Try to find SST installation path"""
        candidate_paths = [
            "/usr/local/sst",
            "/opt/sst",
            os.path.expanduser("~/sst"),
            os.path.expanduser("~/sst-core"),
        ]
        
        for candidate_path in candidate_paths:
            if os.path.exists(os.path.join(candidate_path, "bin", "sst")):
                return candidate_path
        
        return None
    
    def compile_cpp_component(self, cpp_files: list, header_files: list, 
                            component_name: str, output_dir: str = None) -> str:
        """
        Compile C++ component into shared library.
        
        Args:
            cpp_files: List of .cc/.cpp files
            header_files: List of .h files  
            component_name: Name of the component
            output_dir: Output directory for compiled library
            
        Returns:
            Path to compiled shared library
        """
        if not output_dir:
            output_dir = tempfile.mkdtemp(prefix="sst_cpp_")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate compilation command
        shared_library_path = os.path.join(output_dir, f"lib{component_name}.so")
        
        # Base compilation flags
        compilation_command = [
            "g++", "-shared", "-fPIC", "-std=c++17",
            "-O2", "-Wall", "-Wextra"
        ]
        
        # Add SST include paths if available
        if self.sst_install_path:
            sst_include_dir = os.path.join(self.sst_install_path, "include")
            if os.path.exists(sst_include_dir):
                compilation_command.extend(["-I", sst_include_dir])
        
        # Add current directory for local headers
        compilation_command.extend(["-I", "."])
        
        # Add source files
        compilation_command.extend(cpp_files)
        
        # Output library
        compilation_command.extend(["-o", shared_library_path])
        
        # Add linking flags
        if self.sst_install_path:
            sst_library_dir = os.path.join(self.sst_install_path, "lib")
            if os.path.exists(sst_library_dir):
                compilation_command.extend(["-L", sst_library_dir, "-lsst"])
        
        # Compile the component
        try:
            compile_result = subprocess.run(compilation_command, capture_output=True, text=True)
            if compile_result.returncode != 0:
                raise RuntimeError(f"Compilation failed: {compile_result.stderr}")
            
            self.compiled_libs[component_name] = shared_library_path
            print(f"Compiled {component_name} to {shared_library_path}")
            return shared_library_path
            
        except FileNotFoundError:
            raise RuntimeError("g++ compiler not found. Please install build-essential.")
    
    def load_cpp_library(self, lib_path: str) -> ctypes.CDLL:
        """Load compiled C++ library"""
        if lib_path in self.loaded_libs:
            return self.loaded_libs[lib_path]
        
        try:
            cpp_library = ctypes.CDLL(lib_path)
            self.loaded_libs[lib_path] = cpp_library
            return cpp_library
        except OSError as error:
            raise RuntimeError(f"Failed to load library {lib_path}: {error}")
    
    def create_cpp_wrapper(self, lib_path: str, component_name: str) -> type:
        """Create Python wrapper class for C++ component"""
        
        cpp_library = self.load_cpp_library(lib_path)
        
        # Define C++ function signatures
        # These would need to be customized based on your C++ component interface
        cpp_library.create_component.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        cpp_library.create_component.restype = ctypes.c_void_p
        
        cpp_library.destroy_component.argtypes = [ctypes.c_void_p]
        cpp_library.destroy_component.restype = None
        
        cpp_library.setup_component.argtypes = [ctypes.c_void_p]
        cpp_library.setup_component.restype = None
        
        cpp_library.finish_component.argtypes = [ctypes.c_void_p]
        cpp_library.finish_component.restype = None
        
        cpp_library.clock_tick.argtypes = [ctypes.c_void_p, ctypes.c_longlong]
        cpp_library.clock_tick.restype = ctypes.c_bool
        
        cpp_library.handle_event.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cpp_library.handle_event.restype = None
        
        class CppComponentWrapper(Component):
            """Wrapper for C++ component"""
            
            def __init__(self, component_id, params):
                super().__init__(component_id, params)
                self.cpp_lib = cpp_library
                self.cpp_instance = None
                self.component_name = component_name
            
            def _setup_impl(self):
                """Setup C++ component"""
                # Convert params to C++ compatible format
                parameter_values = self.params.to_dict()
                
                # Create C++ component instance
                self.cpp_instance = self.cpp_lib.create_component(
                    self.component_name.encode('utf-8'),
                    ctypes.c_void_p(id(parameter_values))
                )
                
                if not self.cpp_instance:
                    raise RuntimeError(f"Failed to create C++ component {self.component_name}")
                
                # Call C++ setup
                self.cpp_lib.setup_component(self.cpp_instance)
                print(f"Setup C++ component: {self.component_name}")
            
            def _finish_impl(self):
                """Finish C++ component"""
                if self.cpp_instance:
                    self.cpp_lib.finish_component(self.cpp_instance)
                    self.cpp_lib.destroy_component(self.cpp_instance)
                    self.cpp_instance = None
                    print(f"Finished C++ component: {self.component_name}")
            
            def _clock_tick(self, cycle):
                """Clock tick handler"""
                if self.cpp_instance:
                    return self.cpp_lib.clock_tick(self.cpp_instance, cycle)
                return True
            
            def handle_event(self, event):
                """Handle event"""
                if self.cpp_instance:
                    # Convert Python event to C++ format
                    cpp_event_data = self._event_to_cpp(event)
                    self.cpp_lib.handle_event(self.cpp_instance, cpp_event_data)
            
            def _event_to_cpp(self, event):
                """Convert Python event to C++ compatible format"""
                # This would need to be customized based on your event structure
                return ctypes.c_void_p(id(event))
        
        return CppComponentWrapper


class CppComponent(Component):
    """
    Python wrapper for C++ SST components.
    
    This class provides a Python interface to C++ components,
    handling the marshalling between Python and C++.
    """
    
    def __init__(self, component_id: ComponentId, cpp_lib_path: str, 
                 component_type: str, params: Params):
        super().__init__(component_id, params)
        self.cpp_lib_path = cpp_lib_path
        self.component_type = component_type
        self.cpp_instance = None
        self.cpp_lib = None
        
        # Load C++ library
        self._load_cpp_library()
    
    def _load_cpp_library(self):
        """Load the C++ library for this component"""
        try:
            self.cpp_lib = ctypes.CDLL(self.cpp_lib_path)
            self._setup_cpp_functions()
        except OSError as error:
            raise RuntimeError(f"Failed to load C++ library {self.cpp_lib_path}: {error}")
    
    def _setup_cpp_functions(self):
        """Setup C++ function signatures"""
        # These would need to be customized based on your C++ component interface
        if hasattr(self.cpp_lib, 'create_component'):
            self.cpp_lib.create_component.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
            self.cpp_lib.create_component.restype = ctypes.c_void_p
        
        if hasattr(self.cpp_lib, 'destroy_component'):
            self.cpp_lib.destroy_component.argtypes = [ctypes.c_void_p]
            self.cpp_lib.destroy_component.restype = None
        
        if hasattr(self.cpp_lib, 'setup_component'):
            self.cpp_lib.setup_component.argtypes = [ctypes.c_void_p]
            self.cpp_lib.setup_component.restype = None
        
        if hasattr(self.cpp_lib, 'finish_component'):
            self.cpp_lib.finish_component.argtypes = [ctypes.c_void_p]
            self.cpp_lib.finish_component.restype = None
        
        if hasattr(self.cpp_lib, 'clock_tick'):
            self.cpp_lib.clock_tick.argtypes = [ctypes.c_void_p, ctypes.c_longlong]
            self.cpp_lib.clock_tick.restype = ctypes.c_bool
        
        if hasattr(self.cpp_lib, 'handle_event'):
            self.cpp_lib.handle_event.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            self.cpp_lib.handle_event.restype = None
    
    def _setup_impl(self):
        """Setup the C++ component"""
        if hasattr(self.cpp_lib, 'create_component'):
            # Convert params to C++ compatible format
            parameter_values = self.params.to_dict()
            
            # Create C++ component instance
            self.cpp_instance = self.cpp_lib.create_component(
                self.component_type.encode('utf-8'),
                ctypes.c_void_p(id(parameter_values))
            )
            
            if not self.cpp_instance:
                raise RuntimeError(f"Failed to create C++ component {self.component_type}")
        
        # Call C++ setup
        if hasattr(self.cpp_lib, 'setup_component') and self.cpp_instance:
            self.cpp_lib.setup_component(self.cpp_instance)
        
        print(f"Setup C++ component: {self.component_type}")
    
    def _finish_impl(self):
        """Finish the C++ component"""
        if hasattr(self.cpp_lib, 'finish_component') and self.cpp_instance:
            self.cpp_lib.finish_component(self.cpp_instance)
        
        if hasattr(self.cpp_lib, 'destroy_component') and self.cpp_instance:
            self.cpp_lib.destroy_component(self.cpp_instance)
            self.cpp_instance = None
        
        print(f"Finished C++ component: {self.component_type}")
    
    def _clock_tick(self, cycle):
        """Clock tick handler"""
        if hasattr(self.cpp_lib, 'clock_tick') and self.cpp_instance:
            return self.cpp_lib.clock_tick(self.cpp_instance, cycle)
        return True
    
    def handle_event(self, event):
        """Handle event"""
        if hasattr(self.cpp_lib, 'handle_event') and self.cpp_instance:
            # Convert Python event to C++ format
            cpp_event_data = self._event_to_cpp(event)
            self.cpp_lib.handle_event(self.cpp_instance, cpp_event_data)
    
    def _event_to_cpp(self, event):
        """Convert Python event to C++ compatible format"""
        # This would need to be customized based on your event structure
        return ctypes.c_void_p(id(event))
    
    def __del__(self):
        """Cleanup C++ instance"""
        if self.cpp_instance and hasattr(self.cpp_lib, 'destroy_component'):
            self.cpp_lib.destroy_component(self.cpp_instance)
