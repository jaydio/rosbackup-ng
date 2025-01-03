"""
RouterOS device information gathering utilities.

This module provides functionality to gather system information from RouterOS devices,
including hardware specifications, resource usage, and access validation.
"""

import paramiko
from typing import Dict, Optional, TypedDict, Literal
import logging
from .ssh_utils import SSHManager


class RouterInfo(TypedDict):
    """Router information dictionary type definition."""
    identity: str
    model: str
    ros_version: str
    architecture_name: str
    cpu_name: str
    cpu_count: str
    cpu_frequency: str
    total_memory: str
    free_memory: str
    free_hdd_space: str
    license: str


class RouterInfoManager:
    """
    Manages RouterOS device information gathering operations.
    
    This class provides methods to retrieve system information,
    validate access permissions, and check file sizes on RouterOS devices.
    
    Attributes:
        ssh_manager (SSHManager): SSH manager for command execution
        logger (logging.Logger): Logger instance for this class
    """

    def __init__(self, ssh_manager: SSHManager) -> None:
        """
        Initialize RouterInfo manager.

        Args:
            ssh_manager: SSH manager instance for executing commands
        """
        self.ssh_manager = ssh_manager
        self.logger = logging.getLogger(__name__)

    def get_router_info(self, ssh_client: paramiko.SSHClient) -> RouterInfo:
        """
        Retrieve comprehensive router information.

        Gathers system information including hardware specifications,
        resource usage, and license details using RouterOS commands.

        Args:
            ssh_client: Connected SSH client to the router

        Returns:
            Dictionary containing router information with keys:
                - identity: Router's identity name
                - model: Router's model name
                - ros_version: RouterOS version (no "stable" suffix)
                - architecture_name: Router's architecture
                - cpu_name: CPU model name
                - cpu_count: Number of CPU cores
                - cpu_frequency: CPU frequency in MHz
                - total_memory: Total memory in bytes
                - free_memory: Free memory in bytes
                - free_hdd_space: Free disk space in bytes
                - license: RouterOS license level

        Note:
            Version string is cleaned by removing "(stable)" suffix.
            Example: "7.16.2 (stable)" becomes "7.16.2"

        Error Handling:
            - Returns "Unknown" for failed command executions
            - Logs debug information for troubleshooting
            - Handles empty or invalid command outputs
        """
        info = {}
        commands = {
            'identity': ':put [/system identity get name]',
            'model': ':put [/system resource get board-name]',
            'ros_version': ':put [/system resource get version]',
            'architecture_name': ':put [/system resource get architecture-name]',
            'cpu_name': ':put [/system resource get cpu-name]',
            'cpu_count': ':put [/system resource get cpu-count]',
            'cpu_frequency': ':put [/system resource get cpu-frequency]',
            'total_memory': ':put [/system resource get total-memory]',
            'free_memory': ':put [/system resource get free-memory]',
            'free_hdd_space': ':put [/system resource get free-hdd-space]',
            'license': ':put [/system license get level]'
        }

        for key, command in commands.items():
            stdout, _ = self.ssh_manager.execute_command(ssh_client, command)
            if key == 'ros_version' and stdout:
                # Strip the (stable) part from version
                stdout = stdout.split(' ')[0]
            info[key] = stdout if stdout else 'Unknown'

        self.logger.debug(f"Retrieved router information: {info}")
        return info

    def get_backup_size(self, ssh_client: paramiko.SSHClient, backup_file: str) -> Optional[int]:
        """
        Get the size of a backup file on the router.

        Uses RouterOS file system commands to retrieve the size
        of a specified backup file.

        Args:
            ssh_client: Connected SSH client to the router
            backup_file: Name or path of the backup file

        Returns:
            File size in bytes if found and readable, None otherwise

        Error Handling:
            - Returns None if file not found
            - Handles invalid size values
            - Logs errors for troubleshooting
        """
        stdout, _ = self.ssh_manager.execute_command(
            ssh_client, 
            f':put [file get [find name="{backup_file}"] size]'
        )
        try:
            return int(stdout) if stdout else None
        except (ValueError, TypeError):
            self.logger.error(f"Could not determine size of backup file: {backup_file}")
            return None

    def validate_router_access(self, ssh_client: paramiko.SSHClient) -> bool:
        """
        Validate that we have sufficient access rights on the router.

        Checks if the current user has necessary permissions for:
        - Reading system resources
        - Accessing the file system
        - Creating and reading backup files

        Args:
            ssh_client: Connected SSH client to the router

        Returns:
            True if we have sufficient access, False otherwise

        Error Handling:
            - Logs specific permission issues
            - Verifies multiple access types
            - Returns False on any permission failure
        """
        # Check if we can read system resources
        stdout, _ = self.ssh_manager.execute_command(
            ssh_client, 
            ':put [/system resource get total-memory]'
        )
        if not stdout:
            self.logger.error("Insufficient access rights to read system resources")
            return False

        # Check if we can access the file system
        stdout, _ = self.ssh_manager.execute_command(
            ssh_client,
            ':put [file get [find type="directory" and name=""] name]'
        )
        if not stdout:
            self.logger.error("Insufficient access rights to access file system")
            return False

        return True
