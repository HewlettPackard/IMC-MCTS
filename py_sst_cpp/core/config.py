# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
SST Configuration System

Configuration and parameter management for simulation components.
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import json
import os


@dataclass
class ConfigOption:
    """Configuration option definition"""
    name: str
    value: Any
    description: str = ""
    required: bool = False
    type: type = str


class Params:
    """Store component parameters with direct typed access by callers."""
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """
        Initialize parameters.
        
        Args:
            params: Dictionary of parameter values
        """
        self._params = params or {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get parameter value with default"""
        return self._params.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set parameter value"""
        self._params[key] = value
    
    def has(self, key: str) -> bool:
        """Check if parameter exists"""
        return key in self._params
    
    def keys(self) -> List[str]:
        """Get all parameter keys"""
        return list(self._params.keys())
    
    def values(self) -> List[Any]:
        """Get all parameter values"""
        return list(self._params.values())
    
    def items(self) -> List[tuple]:
        """Get all parameter items"""
        return list(self._params.items())
    
    def update(self, other: Union['Params', Dict[str, Any]]) -> None:
        """Update parameters from another Params or dict"""
        if isinstance(other, Params):
            self._params.update(other._params)
        else:
            self._params.update(other)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self._params.copy()
    
    def __getitem__(self, key: str) -> Any:
        """Get parameter value"""
        return self._params[key]
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Set parameter value"""
        self._params[key] = value
    
    def __contains__(self, key: str) -> bool:
        """Check if parameter exists"""
        return key in self._params
    
    def __len__(self) -> int:
        """Get number of parameters"""
        return len(self._params)
    
    def __str__(self) -> str:
        return f"Params({self._params})"
    
    def __repr__(self) -> str:
        return self.__str__()


class Config:
    """Load and validate simulation configuration values."""
    
    def __init__(self, config_file: Optional[str] = None, 
                 config_dict: Optional[Dict[str, Any]] = None):
        """
        Initialize configuration.
        
        Args:
            config_file: Path to configuration file (JSON)
            config_dict: Configuration dictionary
        """
        self._config = {}
        self._options: Dict[str, ConfigOption] = {}
        
        if config_file:
            self.load_from_file(config_file)
        elif config_dict:
            self.load_from_dict(config_dict)
    
    def load_from_file(self, filename: str) -> None:
        """Load configuration from JSON file"""
        try:
            with open(filename, 'r') as config_file:
                config_data = json.load(config_file)
            self.load_from_dict(config_data)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {filename}")
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON in configuration file: {error}")
    
    def load_from_dict(self, config_dict: Dict[str, Any]) -> None:
        """Load configuration from dictionary"""
        self._config.update(config_dict)
    
    def load_from_env(self, prefix: str = "SST_") -> None:
        """Load configuration from environment variables"""
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                self._config[config_key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self._config[key] = value
    
    def has(self, key: str) -> bool:
        """Check if configuration key exists"""
        return key in self._config
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get configuration section"""
        return self._config.get(section, {})
    
    def set_section(self, section: str, values: Dict[str, Any]) -> None:
        """Set configuration section"""
        self._config[section] = values
    
    def add_option(self, option: ConfigOption) -> None:
        """Add configuration option definition"""
        self._options[option.name] = option
    
    def validate(self) -> List[str]:
        """Validate configuration against defined options"""
        validation_errors = []
        
        for option_name, option in self._options.items():
            if option.required and option_name not in self._config:
                validation_errors.append(f"Required parameter '{option_name}' not found")
            elif option_name in self._config:
                configured_value = self._config[option_name]
                if not isinstance(configured_value, option.type):
                    try:
                        self._config[option_name] = option.type(configured_value)
                    except (ValueError, TypeError):
                        validation_errors.append(f"Parameter '{option_name}' must be of type {option.type.__name__}")
        
        return validation_errors
    
    def get_component_params(self, component_name: str) -> Params:
        """Get parameters for a specific component"""
        component_config = self._config.get(component_name, {})
        return Params(component_config)
    
    def get_global_params(self) -> Params:
        """Get global parameters"""
        global_config = self._config.get('global', {})
        return Params(global_config)
    
    def save_to_file(self, filename: str) -> None:
        """Save configuration to JSON file"""
        with open(filename, 'w') as config_file:
            json.dump(self._config, config_file, indent=2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self._config.copy()
    
    def __str__(self) -> str:
        return f"Config({self._config})"
    
    def __repr__(self) -> str:
        return self.__str__()


class ComponentConfig:
    """Configuration for a specific component type"""
    
    def __init__(self, component_type: str, config: Config):
        self._component_type = component_type
        self._config = config
        self._default_params = {}
        self._required_params = set()
    
    def add_param(self, name: str, default: Any = None, required: bool = False) -> None:
        """Add a parameter definition"""
        self._default_params[name] = default
        if required:
            self._required_params.add(name)
    
    def get_params(self, instance_name: str) -> Params:
        """Get parameters for a component instance"""
        component_params = Params(self._default_params.copy())
        
        # Override with instance-specific parameters
        instance_config = self._config.get(instance_name, {})
        component_params.update(instance_config)
        
        # Override with component type parameters
        type_config = self._config.get(self._component_type, {})
        component_params.update(type_config)
        
        return component_params
    
    def validate_params(self, params: Params) -> List[str]:
        """Validate parameters for this component type"""
        validation_errors = []
        
        # Check required parameters
        for param_name in self._required_params:
            if not params.has(param_name):
                validation_errors.append(f"Required parameter '{param_name}' not found for {self._component_type}")
        
        return validation_errors
