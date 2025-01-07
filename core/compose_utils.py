"""
Docker Compose style output utilities.

This module provides utilities for displaying backup progress in a Docker Compose style format.
"""

import sys
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from colorama import Fore, Style

class ComposeStyleHandler:
    """Handler for Docker Compose style output."""
    
    def __init__(self, targets: List[str], backup_dir: Optional[Path] = None):
        """
        Initialize the handler.
        
        Args:
            targets: List of target names
            backup_dir: Optional path to backup directory for size calculation
        """
        self.targets = targets
        self.backup_dir = backup_dir
        self.position = 0
        self.total_targets = len(targets)
        self.process_start_time = time.time()
        self.start_times: Dict[str, float] = {}
        self.end_times: Dict[str, float] = {}
        self.status: Dict[str, str] = {}
        self.completed = 0
        self.failed = 0
        self.last_update = time.time()
        self.lines_printed = 0
        self.lock = threading.Lock()
        self.done = False
        self.ticker = None
        self.spinner_idx = 0
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        # Get timestamp for this backup session
        self.timestamp = datetime.now().strftime("%m%d%Y")
        
        # Initialize status for all targets
        for target in targets:
            self.status[target] = "Waiting"
            self.start_times[target] = 0
            self.end_times[target] = 0
            
        # Clear screen and print initial header
        print("\033[2J\033[H", end="")  # Clear screen and move cursor to top
        self._start_ticker()
        
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
            
            # Determine status color and symbol
            if status == "Failed":
                symbol_color = Fore.RED
                status_color = Fore.RED + Style.BRIGHT
                symbol = "✘"
            elif status == "Finished":
                symbol_color = Fore.GREEN
                status_color = Fore.GREEN
                symbol = "✔"
            else:
                symbol = self.spinner_frames[self.spinner_idx]
                if status == "Starting":
                    symbol_color = status_color = Fore.CYAN
                elif status == "Running":
                    symbol_color = status_color = Fore.BLUE
                elif status == "Downloading":
                    symbol_color = status_color = Fore.MAGENTA
                else:  # Waiting
                    symbol_color = status_color = Fore.YELLOW
                
            # Format the line with colored status
            line = f"    {symbol_color}{symbol}{Style.RESET_ALL} {target:<20} {status_color}{status:<15}{Style.RESET_ALL} {elapsed:>10}"
            print(line)
            
        # Print summary statistics
        if self.done:
            total_elapsed = time.time() - self.process_start_time
            total_size = self._calculate_total_size()
            print(f"\n{Style.BRIGHT}Summary:{Style.NORMAL}")
            print(f"    Total time: {total_elapsed:.1f}s")
            print(f"    Total size: {self._format_size(total_size)}")
            print(f"    Success: {Fore.GREEN}{self.completed}{Style.RESET_ALL} | Failed: {Fore.RED}{self.failed}{Style.RESET_ALL} | Total: {self.total_targets}")
                
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
            
    def update(self, target: str, status: str):
        """
        Update the status of a target.
        
        Args:
            target: Target name
            status: New status (Starting/Running/Downloading/Finished/Failed)
        """
        if target not in self.status:
            return
            
        with self.lock:
            # Initialize start time if not set
            if self.start_times[target] == 0 and status != "Waiting":
                self.start_times[target] = time.time()
                
            # Don't overwrite terminal states
            if self.status[target] not in ["Finished", "Failed"]:
                self.status[target] = status
                # Record end time and update counters for terminal states
                if status in ["Finished", "Failed"]:
                    self.end_times[target] = time.time()
                    if status == "Finished":
                        self.completed += 1
                    else:
                        self.failed += 1
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
        # Header + newline + targets + blank + 4 summary lines
        sys.stdout.write(f"\033[{len(self.targets) + 6}B")
        sys.stdout.flush()
