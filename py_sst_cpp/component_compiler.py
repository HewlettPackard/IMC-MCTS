# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Component Compiler for C++ SST Components

Automatically compiles C++ components (.cc/.cpp/.h files) into shared libraries
that can be used with Python SST.
"""

import os
import sys
import subprocess
import tempfile
import shutil
from typing import List, Dict, Optional
from pathlib import Path


class ComponentCompiler:
    """
    Compiles C++ SST components into Python-loadable shared libraries.
    """
    
    def __init__(self, sst_install_path: str = None, output_dir: str = None):
        """
        Initialize component compiler.
        
        Args:
            sst_install_path: Path to SST installation
            output_dir: Directory for compiled libraries
        """
        self.sst_install_path = sst_install_path or self._find_sst_installation()
        self.output_dir = output_dir or tempfile.mkdtemp(prefix="sst_components_")
        self.compiled_components = {}
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
    
    def _find_sst_installation(self) -> Optional[str]:
        """Find SST installation path"""
        candidate_paths = [
            "/usr/local/sst",
            "/opt/sst", 
            os.path.expanduser("~/sst"),
            os.path.expanduser("~/sst-core"),
            "/usr/local/sst-core",
        ]
        
        for candidate_path in candidate_paths:
            if os.path.exists(os.path.join(candidate_path, "bin", "sst")):
                return candidate_path
        
        return None
    
    def compile_component(self, component_name: str, source_files: List[str], 
                         header_files: List[str] = None, 
                         dependencies: List[str] = None) -> str:
        """
        Compile a C++ component into a shared library.
        
        Args:
            component_name: Name of the component
            source_files: List of .cc/.cpp files
            header_files: List of .h files (optional)
            dependencies: List of dependency libraries
            
        Returns:
            Path to compiled shared library
        """
        print(f"Compiling component: {component_name}")
        
        # Create component-specific directory
        component_build_dir = os.path.join(self.output_dir, component_name)
        os.makedirs(component_build_dir, exist_ok=True)
        
        # Copy source files to component directory
        for source_file in source_files:
            if os.path.exists(source_file):
                shutil.copy2(source_file, component_build_dir)
            else:
                print(f"Warning: Source file not found: {source_file}")
        
        # Copy header files if provided
        if header_files:
            for header_file in header_files:
                if os.path.exists(header_file):
                    shutil.copy2(header_file, component_build_dir)
                else:
                    print(f"Warning: Header file not found: {header_file}")
        
        # Generate compilation command
        shared_library_path = os.path.join(component_build_dir, f"lib{component_name}.so")
        
        # Base compilation flags
        compilation_command = [
            "g++", "-shared", "-fPIC", "-std=c++17",
            "-O2", "-Wall", "-Wextra", "-g"
        ]
        
        # Add SST include paths
        if self.sst_install_path:
            sst_include_dir = os.path.join(self.sst_install_path, "include")
            if os.path.exists(sst_include_dir):
                compilation_command.extend(["-I", sst_include_dir])
                print(f"Using SST include path: {sst_include_dir}")
        
        # Add component directory for local headers
        compilation_command.extend(["-I", component_build_dir])
        
        # Add current directory for relative includes
        compilation_command.extend(["-I", "."])
        
        # Add source files (only .cc/.cpp files)
        cpp_source_files = [source_file for source_file in source_files if source_file.endswith(('.cc', '.cpp'))]
        compilation_command.extend(cpp_source_files)
        
        # Output library
        compilation_command.extend(["-o", shared_library_path])
        
        # Add linking flags
        if self.sst_install_path:
            sst_library_dir = os.path.join(self.sst_install_path, "lib")
            if os.path.exists(sst_library_dir):
                compilation_command.extend(["-L", sst_library_dir])
                compilation_command.extend(["-lsst"])
                print(f"Using SST library path: {sst_library_dir}")
        
        # Add additional dependencies
        if dependencies:
            compilation_command.extend(dependencies)
        
        # Add common system libraries
        compilation_command.extend(["-lpthread", "-ldl"])
        
        # Compile the component
        print(f"Compilation command: {' '.join(compilation_command)}")
        
        try:
            compile_result = subprocess.run(
                compilation_command,
                cwd=component_build_dir,
                capture_output=True, 
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if compile_result.returncode != 0:
                print(f"Compilation failed for {component_name}")
                print(f"STDOUT: {compile_result.stdout}")
                print(f"STDERR: {compile_result.stderr}")
                raise RuntimeError(f"Compilation failed: {compile_result.stderr}")
            
            self.compiled_components[component_name] = shared_library_path
            print(f"Successfully compiled {component_name} to {shared_library_path}")
            return shared_library_path
            
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Compilation timeout for {component_name}")
        except FileNotFoundError:
            raise RuntimeError("g++ compiler not found. Please install build-essential.")
    
    def compile_from_directory(self, component_dir: str, component_name: str = None) -> str:
        """
        Compile all C++ files in a directory.
        
        Args:
            component_dir: Directory containing C++ files
            component_name: Name of component (defaults to directory name)
            
        Returns:
            Path to compiled shared library
        """
        if not component_name:
            component_name = os.path.basename(component_dir)
        
        # Find all C++ source files
        cpp_source_files = []
        header_files = []
        
        for filename in os.listdir(component_dir):
            component_file_path = os.path.join(component_dir, filename)
            if os.path.isfile(component_file_path):
                if filename.endswith(('.cc', '.cpp')):
                    cpp_source_files.append(component_file_path)
                elif filename.endswith('.h'):
                    header_files.append(component_file_path)
        
        if not cpp_source_files:
            raise RuntimeError(f"No C++ source files found in {component_dir}")
        
        print(f"Found {len(cpp_source_files)} source files and {len(header_files)} header files")
        
        return self.compile_component(component_name, cpp_source_files, header_files)
    
    def compile_sst_project(self, project_dir: str) -> Dict[str, str]:
        """
        Compile all components in an SST project directory.
        
        Args:
            project_dir: Root directory of SST project
            
        Returns:
            Dictionary mapping component names to library paths
        """
        compiled_libraries = {}
        
        # Look for component directories
        for directory_name in os.listdir(project_dir):
            component_path = os.path.join(project_dir, directory_name)
            if os.path.isdir(component_path):
                # Check if it contains C++ files
                contains_cpp_sources = any(filename.endswith(('.cc', '.cpp')) for filename in os.listdir(component_path))
                if contains_cpp_sources:
                    try:
                        shared_library_path = self.compile_from_directory(component_path, directory_name)
                        compiled_libraries[directory_name] = shared_library_path
                    except Exception as error:
                        print(f"Failed to compile {directory_name}: {error}")
        
        return compiled_libraries
    
    def get_compiled_component(self, component_name: str) -> Optional[str]:
        """Get path to compiled component"""
        return self.compiled_components.get(component_name)
    
    def list_compiled_components(self) -> List[str]:
        """List all compiled components"""
        return list(self.compiled_components.keys())
    
    def cleanup(self):
        """Clean up compiled components"""
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
            print(f"Cleaned up compiled components in {self.output_dir}")


def compile_accelerator_components(sst_project_dir: str, output_dir: str = None) -> Dict[str, str]:
    """
    Compile IMC-MCTS components.
    
    Args:
        sst_project_dir: Directory containing IMC-MCTS SST project
        output_dir: Output directory for compiled libraries
        
    Returns:
        Dictionary mapping component names to library paths
    """
    component_compiler = ComponentCompiler(output_dir=output_dir)
    
    # Define Accelerator components to compile
    accelerator_components = {
        "accelerator_5x5_system": [
            "accelerator_5x5_system.cc",
            "accelerator_5x5_system.h"
        ],
        "selection_unit": [
            "selection_unit.cc", 
            "selection_unit.h"
        ],
        "expansion_unit": [
            "expansion_unit.cc",
            "expansion_unit.h"
        ],
        "rollout_unit": [
            "rollout_unit.cc",
            "rollout_unit.h"
        ],
        "backpropagation_unit": [
            "backpropagation_unit.cc",
            "backpropagation_unit.h"
        ],
        "fsm_controller": [
            "fsm_controller.cc",
            "fsm_controller.h"
        ]
    }
    
    compiled_libraries = {}
    
    for component_name, component_files in accelerator_components.items():
        # Find actual file paths
        source_files = []
        header_files = []
        
        for filename in component_files:
            component_file_path = os.path.join(sst_project_dir, "src", filename)
            if os.path.exists(component_file_path):
                if filename.endswith(('.cc', '.cpp')):
                    source_files.append(component_file_path)
                elif filename.endswith('.h'):
                    header_files.append(component_file_path)
            else:
                print(f"Warning: File not found: {component_file_path}")
        
        if source_files:
            try:
                shared_library_path = component_compiler.compile_component(component_name, source_files, header_files)
                compiled_libraries[component_name] = shared_library_path
            except Exception as error:
                print(f"Failed to compile {component_name}: {error}")
        else:
            print(f"No source files found for {component_name}")
    
    return compiled_libraries


if __name__ == "__main__":
    # Example usage
    if len(sys.argv) < 2:
        print("Usage: python component_compiler.py <sst_project_directory>")
        sys.exit(1)
    
    project_dir = sys.argv[1]
    compiled_components = compile_accelerator_components(project_dir)
    
    print("\nCompiled components:")
    for name, path in compiled_components.items():
        print(f"  {name}: {path}")
