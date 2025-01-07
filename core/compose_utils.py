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
        self.completed = 0
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
        print(f"[+] Executing backup for {self.total_targets} targets ...\n")
        
        # Print each target
        for target in self.targets:
            status = self.status[target]
            elapsed = self._get_elapsed_time(target)
            
            # Determine status color and symbol
            if status == "Failed":
                color = Fore.RED
                symbol = "✘"
                status = "FAILED"
            elif status == "Finished":
                color = Fore.GREEN
                symbol = "✔"
            else:
                color = Fore.BLUE
                symbol = self.spinner_frames[self.spinner_idx]
                
            # Format the line with proper spacing
            line = f"    {color}{symbol} {target:<20} {status:<15} {elapsed:>10}{Style.RESET_ALL}"
            print(line)
            
        # Print total elapsed time if done
        if self.done:
            total_elapsed = time.time() - self.process_start_time
            print(f"\n    Total time elapsed: {total_elapsed:.1f}s")
                
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
            status: New status (Starting/Running/Finished/Failed)
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
            
        # Move cursor past the output (header + newline + targets + blank line + total time)
        sys.stdout.write(f"\033[{len(self.targets) + 3}B")
        sys.stdout.flush()
