"""
Docker Compose style output utilities.

This module provides utilities for displaying backup progress in a Docker Compose style format.
"""

import sys
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional
from colorama import Fore, Style

class ComposeStyleHandler:
    """Handler for Docker Compose style output."""
    
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
        self.end_times: Dict[str, float] = {}  # Track when targets finish
        self.status: Dict[str, str] = {}
        self.sizes: Dict[str, int] = {}  # Track backup sizes in bytes
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
            self.sizes[target] = 0
            
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
            
    def _print_output(self):
        """Print the current status."""
        # Move cursor to top
        sys.stdout.write("\033[H")
        
        # Print header
        print(f"{Fore.WHITE}[+] Executing backup for {self.total_targets} targets ...\n{Style.RESET_ALL}")
        
        # Print each target
        for target in self.targets:
            status = self.status[target]
            elapsed = self._get_elapsed_time(target)
            size_info = self._format_size(self.sizes[target]) if self.sizes[target] > 0 else ""
            
            # Determine status color and symbol
            if status == "Failed":
                color = Fore.RED
                symbol = "✘"
                status_color = Fore.RED
                status = "FAILED"
            elif status == "Finished":
                color = Fore.GREEN
                symbol = "✔"
                status_color = Fore.GREEN
            elif status == "Waiting":
                color = Fore.YELLOW
                symbol = self.spinner_frames[self.spinner_idx]
                status_color = Fore.YELLOW
            elif status == "Starting":
                color = Fore.CYAN
                symbol = self.spinner_frames[self.spinner_idx]
                status_color = Fore.CYAN
            elif status == "Downloading":
                color = Fore.MAGENTA
                symbol = self.spinner_frames[self.spinner_idx]
                status_color = Fore.MAGENTA
            else:  # Running
                color = Fore.BLUE
                symbol = self.spinner_frames[self.spinner_idx]
                status_color = Fore.BLUE
                
            # Format the line with proper spacing and colors
            size_part = f" [{size_info}]" if size_info else ""
            line = f"    {color}{symbol}{Fore.WHITE} {target:<20} {status_color}{status:<15}{Fore.WHITE}{size_part} {elapsed:>10}{Style.RESET_ALL}"
            print(line)
            
        # Print summary statistics if done or if we have any completed/failed targets
        if self.done or self.completed > 0 or self.failed > 0:
            total_elapsed = time.time() - self.process_start_time
            in_progress = self.total_targets - (self.completed + self.failed)
            
            print(f"\n    {Fore.WHITE}Summary:{Style.RESET_ALL}")
            print(f"    {Fore.WHITE}Total: {self.total_targets} | "
                  f"{Fore.GREEN}Success: {self.completed} | "
                  f"{Fore.RED}Failed: {self.failed} | "
                  f"{Fore.BLUE}In Progress: {in_progress}{Style.RESET_ALL}")
            
            if self.completed > 0:
                total_size = sum(self.sizes.values())
                print(f"    {Fore.WHITE}Total Size: {self._format_size(total_size)}{Style.RESET_ALL}")
            
            print(f"    {Fore.WHITE}Time Elapsed: {total_elapsed:.1f}s{Style.RESET_ALL}")
                
    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"
            
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
            
    def update(self, target: str, status: str, size: int = 0):
        """
        Update the status of a target.
        
        Args:
            target: Target name
            status: New status (Starting/Running/Downloading/Finished/Failed)
            size: Size of backup in bytes (optional)
        """
        if target not in self.status:
            return
            
        # Initialize start time if not set
        if self.start_times[target] == 0 and status != "Waiting":
            self.start_times[target] = time.time()
            
        with self.lock:
            # Update size if provided
            if size > 0:
                self.sizes[target] = size
                
            # Don't overwrite terminal states
            if self.status[target] not in ["Finished", "Failed"]:
                old_status = self.status[target]
                self.status[target] = status
                
                # Update counters for terminal states
                if status == "Finished" and old_status != "Finished":
                    self.completed += 1
                elif status == "Failed" and old_status != "Failed":
                    self.failed += 1
                    
                # Record end time for terminal states
                if status in ["Finished", "Failed"]:
                    self.end_times[target] = time.time()
                    
                # Force immediate update for state changes
                self._print_output()
                
    def close(self):
        """Clean up and restore cursor."""
        self.done = True
        if self.ticker:
            self.ticker.join(timeout=1.0)
            
        # Print final output with total time
        with self.lock:
            self._print_output()
            
        # Move cursor past the output (header + newline + targets + summary section)
        summary_lines = 4 if self.completed > 0 else 3
        sys.stdout.write(f"\033[{len(self.targets) + summary_lines + 2}B")
        sys.stdout.flush()
