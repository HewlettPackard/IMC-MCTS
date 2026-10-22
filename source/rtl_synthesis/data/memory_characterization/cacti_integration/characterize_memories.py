#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Accelerator Memory Characterization using CACTI
Automates CACTI runs and processes results for hardware modeling
"""

import os
import subprocess
import json
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

@dataclass
class MemoryCharacteristics:
    """Memory characterization results from CACTI"""
    capacity_kb: float
    area_mm2: float
    access_time_ns: float
    cycle_time_ns: float
    dynamic_power_mw: float
    leakage_power_mw: float
    dynamic_energy_pj: float
    bank_count: int

class CACTIRunner:
    """Automates CACTI execution and result parsing"""

    def __init__(self, cacti_path: str = "./cacti"):
        self.cacti_path = cacti_path
        self.results = {}

    def run_cacti_config(self, config_file: str, memory_name: str) -> MemoryCharacteristics:
        """Run CACTI with given configuration and parse results"""

        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Configuration file {config_file} not found")

        # Execute CACTI
        cacti_command = [self.cacti_path, "-infile", config_file]
        try:
            completed_process = subprocess.run(cacti_command, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"CACTI timeout for {memory_name}")

        if completed_process.returncode != 0:
            raise RuntimeError(f"CACTI failed for {memory_name}: {completed_process.stderr}")

        cacti_output = completed_process.stdout

        # Parse CACTI output
        characteristics = self._parse_cacti_output(cacti_output)
        characteristics.capacity_kb = self._extract_capacity(config_file)

        self.results[memory_name] = characteristics
        return characteristics

    def _parse_cacti_output(self, output: str) -> MemoryCharacteristics:
        """Parse CACTI text output to extract key metrics"""

        # Regular expressions for key metrics
        patterns = {
            'area': r'Total area \(mm2\): ([\d.]+)',
            'access_time': r'Access time \(ns\): ([\d.]+)',
            'cycle_time': r'Cycle time \(ns\): ([\d.]+)',
            'dynamic_energy': r'Total dynamic read energy per access \(nJ\): ([\d.]+)',
            'leakage_power': r'Total leakage power of a bank \(mW\): ([\d.]+)',
            'banks': r'Number of banks: (\d+)'
        }

        parsed_metrics = {}
        for metric_name, metric_pattern in patterns.items():
            metric_match = re.search(metric_pattern, output)
            if metric_match:
                parsed_metrics[metric_name] = float(metric_match.group(1))
            else:
                # Try alternative patterns
                alternative_patterns = {
                    'area': r'Cache height x width \(mm\): [\d.]+ x ([\d.]+)',
                    'dynamic_energy': r'Total dynamic power consumption of the cache \(mW\): ([\d.]+)',
                    'leakage_power': r'Cache leakage power \(mW\): ([\d.]+)'
                }
                if metric_name in alternative_patterns:
                    alternative_match = re.search(alternative_patterns[metric_name], output)
                    if alternative_match:
                        parsed_metrics[metric_name] = float(alternative_match.group(1))
                    else:
                        parsed_metrics[metric_name] = 0.0
                else:
                    parsed_metrics[metric_name] = 0.0

        # Handle area calculation if not directly found
        if parsed_metrics['area'] == 0.0:
            dimensions_match = re.search(r'Cache height x width \(mm\): ([\d.]+) x ([\d.]+)', output)
            if dimensions_match:
                cache_height_mm = float(dimensions_match.group(1))
                cache_width_mm = float(dimensions_match.group(2))
                parsed_metrics['area'] = cache_height_mm * cache_width_mm

        # Convert energy per access to power (assuming 1GHz operation)
        dynamic_power_mw = parsed_metrics['dynamic_energy'] * 1000  # nJ to mW at 1GHz
        dynamic_energy_pj = parsed_metrics['dynamic_energy'] * 1000  # nJ to pJ

        return MemoryCharacteristics(
            capacity_kb=0,  # Will be filled in later
            area_mm2=parsed_metrics['area'],
            access_time_ns=parsed_metrics['access_time'],
            cycle_time_ns=parsed_metrics['cycle_time'],
            dynamic_power_mw=dynamic_power_mw,
            leakage_power_mw=parsed_metrics['leakage_power'],
            dynamic_energy_pj=dynamic_energy_pj,
            bank_count=int(parsed_metrics.get('banks', 1))
        )

    def _extract_capacity(self, config_file: str) -> float:
        """Extract memory capacity from config file"""
        with open(config_file, 'r') as config_file_handle:
            for config_line in config_file_handle:
                if config_line.startswith('-size (bytes)'):
                    capacity_bytes = int(config_line.split()[-1])
                    return capacity_bytes / 1024  # Convert to KB
        return 0.0

    def characterize_all_memories(self) -> Dict[str, MemoryCharacteristics]:
        """Run characterization for all Accelerator memories"""

        memory_configs = {
            'NODE_SRAM': 'node_sram_14kb.cfg',
            'CAM_16ENTRY': 'cam_16entry.cfg',
            'INSTRUCTION_MEM': 'instruction_mem_2kb.cfg'
        }

        print("🚀 Starting Accelerator Memory Characterization")
        print("=" * 55)

        for memory_name, config_file in memory_configs.items():
            print(f"📊 Characterizing {memory_name}...")
            try:
                characteristics = self.run_cacti_config(config_file, memory_name)
                print(f"✅ {memory_name}: {characteristics.area_mm2:.3f} mm², {characteristics.access_time_ns:.2f} ns")
            except Exception as error:
                print(f"❌ {memory_name}: {error}")

        return self.results

    def generate_hardware_models(self) -> str:
        """Generate Python hardware model code from CACTI results"""

        model_template = '''
class {memory_name}HardwareModel:
    """Hardware characteristics for {memory_name} from CACTI analysis"""

    def __init__(self):
        # Memory specifications
        self.capacity_kb = {capacity_kb}
        self.technology_nm = 28

        # Area and timing (from CACTI)
        self.area_mm2 = {area_mm2}
        self.access_time_ns = {access_time_ns}
        self.cycle_time_ns = {cycle_time_ns}

        # Power characteristics (from CACTI)
        self.dynamic_energy_pj = {dynamic_energy_pj}
        self.leakage_power_mw = {leakage_power_mw}
        self.bank_count = {bank_count}

    def get_access_energy(self, num_accesses: int) -> float:
        """Calculate total energy for given number of accesses"""
        return num_accesses * self.dynamic_energy_pj / 1000  # Convert to nJ

    def get_total_power(self, access_frequency_mhz: float) -> float:
        """Calculate total power consumption"""
        dynamic_power = (access_frequency_mhz * self.dynamic_energy_pj) / 1000
        return dynamic_power + self.leakage_power_mw  # mW

    def get_area_breakdown(self) -> dict:
        """Return area breakdown by component"""
        return {{
            "total_mm2": self.area_mm2,
            "memory_array_mm2": self.area_mm2 * 0.7,  # Estimated
            "peripheral_mm2": self.area_mm2 * 0.3,    # Estimated
        }}
'''

        generated_models_code = "# Accelerator Memory Hardware Models\n# Generated from CACTI characterization\n\n"

        for memory_name, characteristics in self.results.items():
            generated_model = model_template.format(
                memory_name=memory_name,
                capacity_kb=characteristics.capacity_kb,
                area_mm2=characteristics.area_mm2,
                access_time_ns=characteristics.access_time_ns,
                cycle_time_ns=characteristics.cycle_time_ns,
                dynamic_energy_pj=characteristics.dynamic_energy_pj,
                leakage_power_mw=characteristics.leakage_power_mw,
                bank_count=characteristics.bank_count
            )
            generated_models_code += generated_model + "\n"

        return generated_models_code

    def generate_scaling_configs(self):
        """Generate CACTI configs for different board sizes"""

        # Board size scaling parameters
        scaling_configs = [
            {"name": "2x2", "size_kb": 1.4, "entries": 50},
            {"name": "3x3", "size_kb": 5.6, "entries": 200},
            {"name": "5x5", "size_kb": 28, "entries": 1000},
            {"name": "9x9", "size_kb": 280, "entries": 10000},
            {"name": "13x13", "size_kb": 1400, "entries": 50000},
            {"name": "19x19", "size_kb": 5600, "entries": 200000}
        ]

        base_config = """# Accelerator NODE_SRAM Configuration - {board_size}
# {size_kb}KB SRAM for {entries} tree nodes

-size (bytes) {size_bytes}
-block size (bytes) 28
-associativity 1
-read-write port 1
-exclusive read port 0
-exclusive write port 0
-single ended read ports 0
-search port 0

# Technology parameters
-technology (u) 0.028
-page size (bits) 8192

# Access characteristics
-burst length 1
-internal prefetch width 8
-Data array cell type - "itrs-hp"
-Data array peripheral type - "itrs-hp"
-Tag array cell type - "itrs-hp"
-Tag array peripheral type - "itrs-hp"

# Optimization target
-design objective (weight delay, dynamic power, leakage power, cycle time, area) 10:10:10:40:30
-deviate (delay, dynamic power, leakage power, cycle time, area) 60:100000:100000:100000:1000000
-Optimize ED or ED^2 (ED, ED^2, NONE): ED
-Cache model (NUCA, UCA)  - "UCA"

# Wire type
-Wire inside mat - "global"
-Wire outside mat - "global"

# Output options
-print level (DETAILED, CONCISE) - DETAILED
-print input parameters - 1
"""

        for scaling_config in scaling_configs:
            config_filename = f"node_sram_{scaling_config['name']}.cfg"
            config_content = base_config.format(
                board_size=scaling_config['name'],
                size_kb=scaling_config['size_kb'],
                entries=scaling_config['entries'],
                size_bytes=int(scaling_config['size_kb'] * 1024)
            )

            with open(config_filename, 'w') as config_file_handle:
                config_file_handle.write(config_content)

            print(f"📄 Generated {config_filename}")

def mock_cacti_results():
    """Generate mock CACTI results for testing when CACTI is not available"""

    mock_results = {
        'NODE_SRAM': MemoryCharacteristics(
            capacity_kb=14.0,
            area_mm2=0.125,
            access_time_ns=0.8,
            cycle_time_ns=1.2,
            dynamic_power_mw=5.2,
            leakage_power_mw=0.8,
            dynamic_energy_pj=5.2,
            bank_count=1
        ),
        'CAM_16ENTRY': MemoryCharacteristics(
            capacity_kb=0.44,
            area_mm2=0.032,
            access_time_ns=0.3,
            cycle_time_ns=0.5,
            dynamic_power_mw=3.8,
            leakage_power_mw=0.2,
            dynamic_energy_pj=3.8,
            bank_count=1
        ),
        'INSTRUCTION_MEM': MemoryCharacteristics(
            capacity_kb=2.0,
            area_mm2=0.018,
            access_time_ns=1.2,
            cycle_time_ns=1.5,
            dynamic_power_mw=1.5,
            leakage_power_mw=0.1,
            dynamic_energy_pj=1.5,
            bank_count=1
        )
    }

    return mock_results

if __name__ == "__main__":
    print("Accelerator Memory Characterization Tool")
    print("=" * 45)

    # Check if CACTI is available
    runner = CACTIRunner()

    try:
        # Try to run actual CACTI characterization
        results = runner.characterize_all_memories()
        if not results:  # If no results were generated
            raise RuntimeError("No CACTI results generated")
    except (FileNotFoundError, RuntimeError, subprocess.SubprocessError) as e:
        print(f"⚠️  CACTI not available: {e}")
        print("🔧 Using mock results for demonstration")
        results = mock_cacti_results()
        runner.results = results

    # Generate summary report
    print("\n📋 CHARACTERIZATION SUMMARY")
    print("=" * 40)

    total_area = 0
    total_leakage = 0

    for name, char in results.items():
        print(f"{name}:")
        print(f"  Capacity: {char.capacity_kb:.1f} KB")
        print(f"  Area: {char.area_mm2:.3f} mm²")
        print(f"  Access Time: {char.access_time_ns:.2f} ns")
        print(f"  Dynamic Energy: {char.dynamic_energy_pj:.1f} pJ/access")
        print(f"  Leakage Power: {char.leakage_power_mw:.2f} mW")
        print()

        total_area += char.area_mm2
        total_leakage += char.leakage_power_mw

    print(f"TOTAL MEMORY SYSTEM:")
    print(f"  Area: {total_area:.3f} mm²")
    print(f"  Leakage Power: {total_leakage:.2f} mW")

    # Generate hardware model code
    model_code = runner.generate_hardware_models()
    with open("accelerator_memory_models.py", "w") as f:
        f.write(model_code)

    print(f"\n✅ Hardware models saved to accelerator_memory_models.py")

    # Generate scaling configuration files
    print("\n📊 Generating scaling configurations...")
    runner.generate_scaling_configs()
    print("✅ Scaling configurations generated")

    # Save results to JSON
    results_json = {}
    for name, char in results.items():
        results_json[name] = {
            'capacity_kb': char.capacity_kb,
            'area_mm2': char.area_mm2,
            'access_time_ns': char.access_time_ns,
            'cycle_time_ns': char.cycle_time_ns,
            'dynamic_energy_pj': char.dynamic_energy_pj,
            'leakage_power_mw': char.leakage_power_mw,
            'bank_count': char.bank_count
        }

    with open("memory_characterization_results.json", "w") as f:
        json.dump(results_json, f, indent=2)

    print("💾 Results saved to memory_characterization_results.json")
