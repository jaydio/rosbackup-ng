"""
Docker Compose style output utilities.

This module provides utilities for displaying backup progress in a Docker Compose style format.
"""

import sys
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional
from colorama import Fore, Style, Back

class ComposeStyleHandler:
    """Handler for Docker Compose style output."""
    
    # Status colors
    STATUS_COLORS = {
        "Waiting": Fore.YELLOW,
        "Starting": Fore.CYAN,
        "Running": Fore.BLUE,
        "Downloading": Fore.MAGENTA,
        "Finished": Fore.GREEN,
        "Failed": Fore.RED
    }
    
    # Progress bar characters
    PROGRESS_CHARS = {
        'full': '▓',
        'empty': '░'
    }
    
    def __init__(self, targets: List[str], position: int = 0):
        """
        Initialize the handler.
        
        Args:
            targets: List of target names
            position: Starting position for output
        """
        self.targets = targets
        self.position = position
        self.total_targets = len(targets)
        self.process_start_time = time.time()
        self.start_times: Dict[str, float] = {}
        self.end_times: Dict[str, float] = {}
        self.status: Dict[str, str] = {}
        self.backup_sizes: Dict[str, int] = {}  # Store backup sizes in bytes
        self.download_progress: Dict[str, float] = {}  # Store download progress (0-1)
        self.completed = 0
        self.failed = 0
        self.last_update = time.time()
        self.lines_printed = 0
        self.lock = threading.Lock()
        self.done = False
        self.ticker = None
        self.spinner_idx = 0
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        
        # Initialize status for all targets
        for target in targets:
            self.status[target] = "Waiting"
            self.start_times[target] = 0
            self.end_times[target] = 0
            self.backup_sizes[target] = 0
            self.download_progress[target] = 0
            
        # Clear screen and print initial header
        print("\033[2J\033[H", end="")  # Clear screen and move cursor to top
        self._start_ticker()
        
    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human readable format."""
        if size_bytes == 0:
            return "0B"
        units = ['B', 'KB', 'MB', 'GB']
        unit_idx = 0
        size = float(size_bytes)
        while size >= 1024 and unit_idx < len(units) - 1:
            size /= 1024
            unit_idx += 1
        return f"{size:.1f}{units[unit_idx]}"
        
    def _get_progress_bar(self, progress: float, width: int = 8) -> str:
        """Generate a progress bar string."""
        filled = int(width * progress)
        empty = width - filled
        return (self.PROGRESS_CHARS['full'] * filled +
                self.PROGRESS_CHARS['empty'] * empty)
            
    def _start_ticker(self):
        """Start the ticker thread for screen updates."""
        def ticker():
            while not self.done:
                with self.lock:
                    self._print_output()
                    self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_frames)
                time.sleep(0.1)  # Update every 100ms like Docker Compose
                
        self.ticker = threading.Thread(target=ticker)
        self.ticker.daemon = True
        self.ticker.start()
            
    def _print_output(self):
        """Print the current status."""
        # Move cursor to top
        sys.stdout.write("\033[H")
        
        # Print header
        print(f"{Style.BRIGHT}[+] Executing backup for {self.total_targets} targets ...{Style.NORMAL}\n")
        
        # Print each target
        for target in self.targets:
            status = self.status[target]
            elapsed = self._get_elapsed_time(target)
            
            # Get status color
            color = self.STATUS_COLORS.get(status, '')
            
            # Determine symbol
            if status == "Failed":
                symbol = "✘"
                status = "FAILED"
            elif status == "Finished":
                symbol = "✔"
            else:
                symbol = self.spinner_frames[self.spinner_idx]
                
            # Build progress/size information
            info = ""
            if status == "Downloading":
                progress = self.download_progress[target]
                info = f"[{self._get_progress_bar(progress)}] {progress*100:.0f}%"
            elif status == "Finished":
                size = self._format_size(self.backup_sizes[target])
                info = f"[{size}]"
            elif status == "Failed":
                info = "[ERROR]"
                
            # Format the line with proper spacing and colors
            line = (f"    {color}{symbol}{Style.RESET_ALL} "
                   f"{target:<20} "
                   f"{color}{status:<12}{Style.RESET_ALL} "
                   f"{info:<15} "
                   f"{elapsed:>8}")
            print(line)
            
        # Print summary statistics
        if self.done:
            total_elapsed = time.time() - self.process_start_time
            total_size = sum(self.backup_sizes.values())
            success_count = sum(1 for s in self.status.values() if s == "Finished")
            failed_count = sum(1 for s in self.status.values() if s == "Failed")
            waiting_count = self.total_targets - success_count - failed_count
            
            print(f"\n    {Style.BRIGHT}Summary:{Style.NORMAL}")
            print(f"    Total Time: {total_elapsed:.1f}s")
            print(f"    Total Size: {self._format_size(total_size)}")
            print(f"    Status: {Fore.GREEN}{success_count} Success{Style.RESET_ALL} | "
                  f"{Fore.RED}{failed_count} Failed{Style.RESET_ALL} | "
                  f"{Fore.YELLOW}{waiting_count} Waiting{Style.RESET_ALL}")
                
    def _get_elapsed_time(self, target: str) -> str:
        """Get elapsed time for a target."""
        if self.start_times[target] == 0:
            return "0.0s"
            
        # Use end time for finished targets, current time for running ones
        if self.end_times[target] > 0:
            elapsed = self.end_times[target] - self.start_times[target]
        else:
            elapsed = time.time() - self.start_times[target]
        return f"{elapsed:.1f}s"
            
    def update(self, target: str, status: str, backup_size: int = 0, progress: float = 0):
        """
        Update the status of a target.
        
        Args:
            target: Target name
            status: New status (Starting/Running/Finished/Failed)
            backup_size: Size of backup in bytes (for finished backups)
            progress: Download progress (0-1) for Downloading status
        """
        if target not in self.status:
            return
            
        # Initialize start time if not set
        if self.start_times[target] == 0 and status != "Waiting":
            self.start_times[target] = time.time()
            
        with self.lock:
            # Don't overwrite terminal states
            if self.status[target] not in ["Finished", "Failed"]:
                self.status[target] = status
                # Update backup size and progress
                if backup_size > 0:
                    self.backup_sizes[target] = backup_size
                if status == "Downloading":
                    self.download_progress[target] = progress
                # Record end time for terminal states
                if status in ["Finished", "Failed"]:
                    self.end_times[target] = time.time()
                    if status == "Failed":
                        self.failed += 1
                    else:
                        self.completed += 1
                # Force immediate update for state changes
                self._print_output()
                
    def close(self):
        """Clean up and restore cursor."""
        self.done = True
        if self.ticker:
            self.ticker.join(timeout=1.0)
            
        # Print final output with summary
        with self.lock:
            self._print_output()
            
        # Move cursor past the output
        # Header + newline + targets + 5 summary lines
        sys.stdout.write(f"\033[{len(self.targets) + 6}B")
        sys.stdout.flush()
