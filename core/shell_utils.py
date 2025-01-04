"""
Terminal and shell utility functions.

This module contains utility functions and classes related to terminal/shell operations,
including colored output formatting, terminal control sequences, and other shell-related
functionality.
"""

import logging
import os
import sys
import hashlib
from colorama import Fore, Style, init as colorama_init

def supports_color():
    """Check if the terminal supports color output."""
    if os.environ.get('NO_COLOR'):
        return False
    return os.environ.get('FORCE_COLOR', '1') != '0' and sys.stdout.isatty()

# Initialize colorama based on color support
colorama_init(strip=not supports_color(), wrap=True)


# Available colors for target names, excluding those used for log levels
TARGET_COLORS = [
    # Light foreground colors
    Fore.LIGHTBLUE_EX,
    Fore.LIGHTRED_EX,
    Fore.LIGHTGREEN_EX,
    Fore.LIGHTMAGENTA_EX,
    Fore.LIGHTCYAN_EX,
    Fore.LIGHTYELLOW_EX,
    Fore.LIGHTWHITE_EX,
    
    # Regular foreground colors
    Fore.BLUE,
    Fore.RED,
    Fore.GREEN,
    Fore.MAGENTA,
    Fore.CYAN,
    Fore.YELLOW,
    Fore.WHITE,
    
    # Mixed light and regular foregrounds
    Fore.LIGHTBLUE_EX,
    Fore.RED,
    Fore.LIGHTGREEN_EX,
    Fore.MAGENTA,
    Fore.LIGHTCYAN_EX,
    Fore.YELLOW,
    
    # Additional light variations
    Fore.LIGHTRED_EX,
    Fore.LIGHTMAGENTA_EX,
    Fore.LIGHTWHITE_EX,
    Fore.LIGHTYELLOW_EX,
    Fore.LIGHTCYAN_EX,
    
    # Additional regular variations
    Fore.BLUE,
    Fore.GREEN,
    Fore.CYAN,
    Fore.WHITE,
    Fore.YELLOW,
]


def get_target_color(target_name: str) -> str:
    """Get a consistent color for a target name."""
    if target_name == 'SYSTEM':
        return Fore.WHITE
    # Use a more deterministic hash based on the target name
    # We only use the first 8 characters of the hash to make it more consistent
    hash_value = int(hashlib.sha256(target_name.encode()).hexdigest()[:8], 16)
    return TARGET_COLORS[hash_value % len(TARGET_COLORS)]


class BaseFormatter(logging.Formatter):
    """Base formatter for all log messages."""

    def __init__(self, fmt: str = None, datefmt: str = None, target_name: str = 'SYSTEM'):
        """Initialize the formatter."""
        if fmt is None:
            fmt = '%(asctime)s [%(levelname)s] [%(target_name)s] %(message)s'
        if datefmt is None:
            datefmt = '%m-%d-%Y %H:%M:%S'
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.target_name = target_name

    def format(self, record):
        """Format the log record."""
        if not hasattr(record, 'target_name'):
            record.target_name = self.target_name
        return super().format(record)


class ColoredFormatter(BaseFormatter):
    """Formatter that adds colors to log messages."""

    def __init__(self, fmt: str = None, datefmt: str = None, target_name: str = 'SYSTEM', use_colors: bool = True):
        """Initialize the formatter with color support detection."""
        super().__init__(fmt=fmt, datefmt=datefmt, target_name=target_name)
        self.use_color = use_colors and supports_color()

    def format(self, record):
        """Format the log record with colors."""
        if not self.use_color:
            return super().format(record)

        # Store original values
        original_msg = record.msg
        original_levelname = record.levelname
        original_target_name = record.target_name

        try:
            # Color the level name based on level
            level_color = Fore.CYAN  # Default color
            if record.levelno == logging.INFO:
                level_color = Fore.GREEN
            elif record.levelno == logging.WARNING:
                level_color = Fore.YELLOW
            elif record.levelno == logging.ERROR:
                level_color = Fore.RED
            elif record.levelno == logging.CRITICAL:
                level_color = Fore.RED 

            # Get target color
            target_color = get_target_color(record.target_name)
            
            # Format the parts separately
            formatted = super().format(record)
            
            # Find and color the target name in the formatted string
            target_part = f"[{record.target_name}]"
            colored_target = f"{Style.RESET_ALL}{target_color}{target_part}{Style.RESET_ALL}{level_color}"
            formatted = formatted.replace(target_part, colored_target)

            # Apply the level color to the entire line, but after target coloring
            return f"{level_color}{formatted}{Style.RESET_ALL}"

        finally:
            # Restore original values
            record.msg = original_msg
            record.levelname = original_levelname
            record.target_name = original_target_name
