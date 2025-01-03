"""
Terminal and shell utility functions.

This module contains utility functions and classes related to terminal/shell operations,
including colored output formatting, terminal control sequences, and other shell-related
functionality.
"""

import logging
import sys
from colorama import Fore, Back, Style


class BaseFormatter(logging.Formatter):
    """Base formatter for all log messages."""

    def __init__(self, target_name: str = 'SYSTEM'):
        """Initialize the formatter."""
        fmt = '%(asctime)s [%(levelname)s] [%(target_name)s] %(message)s'
        datefmt = '%Y-%m-%d %H:%M:%S'
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.target_name = target_name

    def format(self, record):
        """Format the log record."""
        if not hasattr(record, 'target_name'):
            record.target_name = self.target_name
        return super().format(record)


class ColoredFormatter(BaseFormatter):
    """Formatter that adds colors to log messages."""

    def format(self, record):
        """Format the log record with colors."""
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
                level_color = Fore.RED + Style.BRIGHT
            elif record.levelno == logging.CRITICAL:
                level_color = Fore.RED + Back.WHITE + Style.BRIGHT

            # Add colors to each component with explicit resets
            record.levelname = f"{level_color}{record.levelname}{Style.RESET_ALL}"
            record.target_name = f"{Fore.BLUE + Style.BRIGHT}{record.target_name}{Style.RESET_ALL}"
            record.msg = f"{level_color}{record.msg}{Style.RESET_ALL}"

            # Format with colors
            return super().format(record)

        finally:
            # Restore original values
            record.msg = original_msg
            record.levelname = original_levelname
            record.target_name = original_target_name
