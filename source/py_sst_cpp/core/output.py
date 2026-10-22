# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
SST Output System

Output and logging system for simulation components.
"""

import sys
import time
from typing import Any, Optional
from enum import Enum
from dataclasses import dataclass


class OutputLevel(Enum):
    """Output verbosity levels"""
    FATAL = 0
    ERROR = 1
    WARN = 2
    INFO = 3
    DEBUG = 4
    TRACE = 5


class OutputTarget(Enum):
    """Output targets"""
    STDOUT = "stdout"
    STDERR = "stderr"
    FILE = "file"
    NULL = "null"


@dataclass
class OutputConfig:
    """Output configuration"""
    level: OutputLevel = OutputLevel.INFO
    target: OutputTarget = OutputTarget.STDOUT
    filename: Optional[str] = None
    timestamp: bool = False
    component_name: bool = True
    line_numbers: bool = False


class Output:
    """Format and route component messages by output level."""
    
    def __init__(self, component_name: str, rank: int = 0, thread: int = 0,
                 target: OutputTarget = OutputTarget.STDOUT,
                 filename: Optional[str] = None,
                 level: OutputLevel = OutputLevel.INFO):
        """
        Initialize output system.
        
        Args:
            component_name: Name of the component
            rank: MPI rank (for parallel simulations)
            thread: Thread ID
            target: Output target
            filename: Output filename (if target is FILE)
            level: Verbosity level
        """
        self._component_name = component_name
        self._rank = rank
        self._thread = thread
        self._config = OutputConfig(
            level=level,
            target=target,
            filename=filename
        )
        
        # Open output file if needed
        self._file_handle = None
        if target == OutputTarget.FILE and filename:
            try:
                self._file_handle = open(filename, 'w')
            except IOError as error:
                print(f"Error opening output file {filename}: {error}", file=sys.stderr)
                self._config.target = OutputTarget.STDERR
    
    def __del__(self):
        """Cleanup file handle"""
        if self._file_handle:
            self._file_handle.close()
    
    def set_level(self, level: OutputLevel) -> None:
        """Set output verbosity level"""
        self._config.level = level
    
    def set_target(self, target: OutputTarget, filename: Optional[str] = None) -> None:
        """Set output target"""
        self._config.target = target
        if target == OutputTarget.FILE and filename:
            self._config.filename = filename
            if self._file_handle:
                self._file_handle.close()
            try:
                self._file_handle = open(filename, 'w')
            except IOError as error:
                print(f"Error opening output file {filename}: {error}", file=sys.stderr)
                self._config.target = OutputTarget.STDERR
    
    def enable_timestamp(self, enable: bool = True) -> None:
        """Enable/disable timestamps"""
        self._config.timestamp = enable
    
    def enable_component_name(self, enable: bool = True) -> None:
        """Enable/disable component name in output"""
        self._config.component_name = enable
    
    def enable_line_numbers(self, enable: bool = True) -> None:
        """Enable/disable line numbers"""
        self._config.line_numbers = enable
    
    def _should_output(self, level: OutputLevel) -> bool:
        """Check if output should be generated for this level"""
        return level.value <= self._config.level.value
    
    def _format_message(self, level: OutputLevel, message: str, 
                       call_info: Optional[str] = None) -> str:
        """Format output message"""
        message_parts = []
        
        # Timestamp
        if self._config.timestamp:
            timestamp = time.strftime("%H:%M:%S")
            message_parts.append(f"[{timestamp}]")
        
        # Component name
        if self._config.component_name:
            message_parts.append(f"[{self._component_name}]")
        
        # Rank and thread
        if self._rank > 0 or self._thread > 0:
            message_parts.append(f"[R{self._rank}:T{self._thread}]")
        
        # Level
        message_parts.append(f"[{level.name}]")
        
        # Call info
        if call_info:
            message_parts.append(f"[{call_info}]")
        
        # Message
        message_parts.append(message)
        
        return " ".join(message_parts)
    
    def _write(self, message: str) -> None:
        """Write message to configured target"""
        if self._config.target == OutputTarget.STDOUT:
            print(message, file=sys.stdout)
        elif self._config.target == OutputTarget.STDERR:
            print(message, file=sys.stderr)
        elif self._config.target == OutputTarget.FILE and self._file_handle:
            print(message, file=self._file_handle)
            self._file_handle.flush()
        # NULL target does nothing
    
    def fatal(self, message: str, call_info: Optional[str] = None) -> None:
        """Output fatal error message"""
        if self._should_output(OutputLevel.FATAL):
            formatted_message = self._format_message(OutputLevel.FATAL, message, call_info)
            self._write(formatted_message)
    
    def error(self, message: str, call_info: Optional[str] = None) -> None:
        """Output error message"""
        if self._should_output(OutputLevel.ERROR):
            formatted_message = self._format_message(OutputLevel.ERROR, message, call_info)
            self._write(formatted_message)
    
    def warn(self, message: str, call_info: Optional[str] = None) -> None:
        """Output warning message"""
        if self._should_output(OutputLevel.WARN):
            formatted_message = self._format_message(OutputLevel.WARN, message, call_info)
            self._write(formatted_message)
    
    def info(self, message: str, call_info: Optional[str] = None) -> None:
        """Output info message"""
        if self._should_output(OutputLevel.INFO):
            formatted_message = self._format_message(OutputLevel.INFO, message, call_info)
            self._write(formatted_message)
    
    def debug(self, message: str, call_info: Optional[str] = None) -> None:
        """Output debug message"""
        if self._should_output(OutputLevel.DEBUG):
            formatted_message = self._format_message(OutputLevel.DEBUG, message, call_info)
            self._write(formatted_message)
    
    def trace(self, message: str, call_info: Optional[str] = None) -> None:
        """Output trace message"""
        if self._should_output(OutputLevel.TRACE):
            formatted_message = self._format_message(OutputLevel.TRACE, message, call_info)
            self._write(formatted_message)
    
    def verbose(self, message: str, call_info: Optional[str] = None) -> None:
        """Output verbose message (alias for info)"""
        self.info(message, call_info)
    
    def printf(self, level: OutputLevel, call_info: Optional[str], 
               format_string: str, *args) -> None:
        """Print formatted message"""
        if self._should_output(level):
            message = format_string % args
            formatted_message = self._format_message(level, message, call_info)
            self._write(formatted_message)
    
    def __str__(self) -> str:
        return f"Output({self._component_name}, level={self._config.level.name})"
    
    def __repr__(self) -> str:
        return self.__str__()
