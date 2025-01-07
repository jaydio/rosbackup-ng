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
import random
import time
import datetime
from typing import Optional, List, Any, Dict
from colorama import Fore, Style, init as colorama_init
from tqdm import tqdm
import pathlib

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
    Fore.LIGHTMAGENTA_EX,
    Fore.LIGHTCYAN_EX,
    Fore.LIGHTYELLOW_EX,
    
    # Regular foreground colors
    Fore.BLUE,
    Fore.RED,
    Fore.MAGENTA,
    Fore.CYAN,
    Fore.YELLOW,
    
    # Mixed light and regular foregrounds
    Fore.LIGHTBLUE_EX,
    Fore.RED,
    Fore.MAGENTA,
    Fore.LIGHTCYAN_EX,
    Fore.YELLOW,
    
    # Additional light variations
    Fore.LIGHTRED_EX,
    Fore.LIGHTMAGENTA_EX,
    Fore.LIGHTYELLOW_EX,
    Fore.LIGHTCYAN_EX,
    
    # Additional regular variations
    Fore.BLUE,
    Fore.CYAN,
    Fore.YELLOW,
]

# Dictionary to store assigned colors
_assigned_colors: Dict[str, str] = {}
_available_colors = list(set(TARGET_COLORS))  # Remove duplicates from TARGET_COLORS
_message_counters: Dict[str, int] = {}  # Track message count per target

def get_target_color(target_name: str) -> str:
    """
    Get a consistent color for a target name.
    
    Args:
        target_name: Name of the target to get color for
        
    Returns:
        str: ANSI color code for the target
    """
    global _assigned_colors, _available_colors
    
    if target_name == 'SYSTEM':
        return Fore.WHITE
        
    # If target already has a color assigned, return it
    if target_name in _assigned_colors:
        return _assigned_colors[target_name]
        
    # If we've used all colors, reset the available colors
    if not _available_colors:
        _available_colors = list(set(TARGET_COLORS))
        
    # Randomly select a color from available colors
    color = random.choice(_available_colors)
    _available_colors.remove(color)
    _assigned_colors[target_name] = color
    
    return color

def get_and_increment_counter(target_name: str) -> int:
    """Get the current counter for a target and increment it."""
    global _message_counters
    if target_name not in _message_counters:
        _message_counters[target_name] = 0
    _message_counters[target_name] += 1
    return _message_counters[target_name]


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
        # Always set target_name if not present
        if not hasattr(record, 'target_name'):
            record.target_name = self.target_name
        # Handle paramiko logs
        if record.name == 'paramiko.transport' and record.msg in ['Connected (version 2.0, client ROSSSH)', 'Authentication (publickey) successful!']:
            return ''  # Skip these messages
        return super().format(record)


class ColoredFormatter(BaseFormatter):
    """
    Formatter that adds colors to log messages.
    
    Extends BaseFormatter to add color support for console output.
    """

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None,
                 target_name: str = 'SYSTEM', use_colors: bool = True) -> None:
        """
        Initialize the formatter with color support detection.
        
        Args:
            fmt: Log message format string
            datefmt: Date format string
            target_name: Name of the target for logging context
            use_colors: Whether to enable colored output
        """
        super().__init__(fmt=fmt, datefmt=datefmt, target_name=target_name)
        self.use_color = use_colors and supports_color()

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with colors.
        
        Args:
            record: Log record to format
            
        Returns:
            str: Formatted log message with color codes
        """

        # Store original values
        original_msg = record.msg
        original_levelname = record.levelname
        original_target_name = record.target_name

        try:
            # Format the parts separately
            formatted = super().format(record)
            
            if not self.use_color:
                # If colors are disabled, just add the counter without colors
                target_part = f"[{record.target_name}]"
                counter = get_and_increment_counter(record.target_name)
                no_color_target = f"[{record.target_name} #{counter}]"
                return formatted.replace(target_part, no_color_target)
            
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

            # Get target color and counter
            target_color = get_target_color(record.target_name)
            counter = get_and_increment_counter(record.target_name)
            
            # Find and color the target name in the formatted string, now including counter
            target_part = f"[{record.target_name}]"
            colored_target = f"{Style.RESET_ALL}{target_color}[{record.target_name} #{counter}]{Style.RESET_ALL}{level_color}"
            formatted = formatted.replace(target_part, colored_target)

            # Apply the level color to the entire line, but after target coloring
            return f"{level_color}{formatted}{Style.RESET_ALL}"

        finally:
            # Restore original values
            record.msg = original_msg
            record.levelname = original_levelname
            record.target_name = original_target_name


class ShellPbarHandler:
    """Shell progress bar handler."""

    def __init__(self, total: int, desc: str = "", position: int = 0,
                 leave: bool = True, ncols: int = 80,
                 bar_format: str = '{desc:<20} {percentage:3.0f}%|{bar:40}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'):
        """
        Initialize the progress bar handler.

        Args:
            total: Total number of items
            desc: Description
            position: Position of the progress bar
            leave: Whether to leave the progress bar after completion
            ncols: Number of columns
            bar_format: Progress bar format string
        """
        self.total = total
        self.desc = desc
        self.position = position
        self.leave = leave
        self.ncols = ncols
        self.bar_format = bar_format
        self.n = 0
        self.errors = 0
        self.start_time = time.time()
        self.last_print_n = 0
        self.last_print_t = 0
        self.print_count = 0
        self.backup_dir = None  # Will be set by main script
        self.timestamp = datetime.datetime.now().strftime("%m%d%Y")

    def _format_size(self, size: int) -> str:
        """Format file size in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def _calculate_total_size(self) -> int:
        """Calculate total size of all backup files from this session."""
        if not self.backup_dir:
            return 0

        total_size = 0
        # Search recursively for files containing today's timestamp
        for file in self.backup_dir.rglob(f"*{self.timestamp}*.backup"):
            total_size += file.stat().st_size
        for file in self.backup_dir.rglob(f"*{self.timestamp}*.rsc"):
            total_size += file.stat().st_size
        return total_size

    def advance(self):
        """Advance progress by one step."""
        self.n += 1
        self._print()

    def error(self):
        """Record an error."""
        self.n += 1
        self.errors += 1
        self._print()

    def _print(self):
        """Print the progress bar."""
        # Move cursor up if needed
        if self.print_count > 0:
            sys.stdout.write("\033[1A")
            sys.stdout.write("\033[K")

        # Calculate progress
        pct = self.n / float(self.total)
        filled_len = int(self.ncols * pct)
        bar = "█" * filled_len + "-" * (self.ncols - filled_len)

        # Calculate time estimates
        elapsed = time.time() - self.start_time
        rate = self.n / elapsed if elapsed > 0 else 0
        remaining = (self.total - self.n) / rate if rate > 0 else 0

        # Format times
        elapsed_str = str(datetime.timedelta(seconds=int(elapsed)))
        if remaining == float('inf'):
            remaining_str = "?"
        else:
            remaining_str = str(datetime.timedelta(seconds=int(remaining)))

        # Format counts
        n_fmt = str(self.n)
        total_fmt = str(self.total)

        # Build progress line
        line = self.bar_format.format(
            desc=self.desc,
            percentage=pct * 100,
            bar=bar,
            n_fmt=n_fmt,
            total_fmt=total_fmt,
            elapsed=elapsed_str,
            remaining=remaining_str
        )

        # Print progress
        print(line)
        self.print_count += 1

    def close(self):
        """Close the progress bar and print summary."""
        if not self.leave:
            if self.print_count > 0:
                sys.stdout.write("\033[1A")
                sys.stdout.write("\033[K")
        else:
            # Print newline
            print()

            # Print summary statistics
            total_elapsed = time.time() - self.start_time
            total_size = self._calculate_total_size()
            success_count = self.n - self.errors

            print(f"{Style.BRIGHT}Summary:{Style.NORMAL}")
            print(f"    Total time: {total_elapsed:.1f}s")
            print(f"    Total size: {self._format_size(total_size)}")
            print(f"    Success: {Fore.GREEN}{success_count}{Style.RESET_ALL} | Failed: {Fore.RED}{self.errors}{Style.RESET_ALL} | Total: {self.total}")

    @classmethod
    def create_multi_bar(cls, total: int, names: List[str], position: int = 0,
                        leave: bool = True, ncols: int = 80) -> List['ShellPbarHandler']:
        """
        Create multiple progress bars.
        
        Args:
            total: Total value for each progress bar
            names: List of names for the progress bars
            position: Starting position for the first bar
            leave: Whether to leave the progress bar after completion
            ncols: Number of columns for the progress bar
            
        Returns:
            List[ShellPbarHandler]: List of progress bar handlers
        """

        # Create main progress bar
        main_bar = cls(total=len(names), desc="", position=position, leave=leave, ncols=ncols)
        
        # Create individual progress bars for each target
        bars = []
        for i, name in enumerate(names):
            bar = cls(
                total=total,
                desc=name,
                position=position + i + 1,  # +1 to account for main bar
                leave=leave,
                ncols=ncols
            )
            bars.append(bar)
        
        # Return all bars with main bar first
        return [main_bar] + bars

    def set_complete(self) -> None:
        """Mark progress bar as complete."""
        if not self.pbar.n >= self.pbar.total:
            self.pbar.n = self.pbar.total
            self.pbar.refresh()
