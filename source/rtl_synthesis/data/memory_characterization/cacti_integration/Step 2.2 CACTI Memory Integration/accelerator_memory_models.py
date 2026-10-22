# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

# Accelerator Memory Hardware Models
# Generated from CACTI characterization


class NODE_SRAMHardwareModel:
    """Hardware characteristics for NODE_SRAM from CACTI analysis"""
    
    def __init__(self):
        # Memory specifications
        self.capacity_kb = 14.0
        self.technology_nm = 28
        
        # Area and timing (from CACTI)
        self.area_mm2 = 0.125
        self.access_time_ns = 0.8
        self.cycle_time_ns = 1.2
        
        # Power characteristics (from CACTI)
        self.dynamic_energy_pj = 5.2
        self.leakage_power_mw = 0.8
        self.bank_count = 1
        
    def get_access_energy(self, num_accesses: int) -> float:
        """Calculate total energy for given number of accesses"""
        return num_accesses * self.dynamic_energy_pj / 1000  # Convert to nJ
        
    def get_total_power(self, access_frequency_mhz: float) -> float:
        """Calculate total power consumption"""
        dynamic_power = (access_frequency_mhz * self.dynamic_energy_pj) / 1000
        return dynamic_power + self.leakage_power_mw  # mW
        
    def get_area_breakdown(self) -> dict:
        """Return area breakdown by component"""
        return {
            "total_mm2": self.area_mm2,
            "memory_array_mm2": self.area_mm2 * 0.7,  # Estimated
            "peripheral_mm2": self.area_mm2 * 0.3,    # Estimated
        }


class CAM_16ENTRYHardwareModel:
    """Hardware characteristics for CAM_16ENTRY from CACTI analysis"""
    
    def __init__(self):
        # Memory specifications
        self.capacity_kb = 0.44
        self.technology_nm = 28
        
        # Area and timing (from CACTI)
        self.area_mm2 = 0.032
        self.access_time_ns = 0.3
        self.cycle_time_ns = 0.5
        
        # Power characteristics (from CACTI)
        self.dynamic_energy_pj = 3.8
        self.leakage_power_mw = 0.2
        self.bank_count = 1
        
    def get_access_energy(self, num_accesses: int) -> float:
        """Calculate total energy for given number of accesses"""
        return num_accesses * self.dynamic_energy_pj / 1000  # Convert to nJ
        
    def get_total_power(self, access_frequency_mhz: float) -> float:
        """Calculate total power consumption"""
        dynamic_power = (access_frequency_mhz * self.dynamic_energy_pj) / 1000
        return dynamic_power + self.leakage_power_mw  # mW
        
    def get_area_breakdown(self) -> dict:
        """Return area breakdown by component"""
        return {
            "total_mm2": self.area_mm2,
            "memory_array_mm2": self.area_mm2 * 0.7,  # Estimated
            "peripheral_mm2": self.area_mm2 * 0.3,    # Estimated
        }


class INSTRUCTION_MEMHardwareModel:
    """Hardware characteristics for INSTRUCTION_MEM from CACTI analysis"""
    
    def __init__(self):
        # Memory specifications
        self.capacity_kb = 2.0
        self.technology_nm = 28
        
        # Area and timing (from CACTI)
        self.area_mm2 = 0.018
        self.access_time_ns = 1.2
        self.cycle_time_ns = 1.5
        
        # Power characteristics (from CACTI)
        self.dynamic_energy_pj = 1.5
        self.leakage_power_mw = 0.1
        self.bank_count = 1
        
    def get_access_energy(self, num_accesses: int) -> float:
        """Calculate total energy for given number of accesses"""
        return num_accesses * self.dynamic_energy_pj / 1000  # Convert to nJ
        
    def get_total_power(self, access_frequency_mhz: float) -> float:
        """Calculate total power consumption"""
        dynamic_power = (access_frequency_mhz * self.dynamic_energy_pj) / 1000
        return dynamic_power + self.leakage_power_mw  # mW
        
    def get_area_breakdown(self) -> dict:
        """Return area breakdown by component"""
        return {
            "total_mm2": self.area_mm2,
            "memory_array_mm2": self.area_mm2 * 0.7,  # Estimated
            "peripheral_mm2": self.area_mm2 * 0.3,    # Estimated
        }

