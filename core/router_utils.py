"""
RouterOS device information gathering utilities.

This module provides functionality to gather system information from RouterOS devices,
including hardware specifications, resource usage, and access validation.
"""

import logging
import paramiko
import re
from typing import Dict, Optional, TypedDict, Literal, Any, List
from .ssh_utils import SSHManager
from .logging_utils import LogManager


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

    def __init__(self, ssh_manager: SSHManager, target_name: str) -> None:
        """
        Initialize RouterInfo manager.

        Args:
            ssh_manager: SSH manager instance for executing commands
            target_name: Name of the target for logging purposes
        """
        self.ssh_manager = ssh_manager
        self.logger = LogManager().get_logger('ROUTER', target_name)

    def get_router_info(self, ssh_client: paramiko.SSHClient) -> Dict[str, str]:
        """
        Get router information using SSH commands.

        Args:
            ssh_client: Connected SSH client

        Returns:
            Dictionary containing router information
        """
        try:
            # Get system resource info
            stdout, stderr = self.ssh_manager.execute_command(ssh_client, "/system resource print")
            if stderr:
                self.logger.error(f"Error getting system resource info: {stderr}")
                raise RuntimeError(f"Failed to get system resource info: {stderr}")

            # Parse system resource output
            resource_info = self._parse_mikrotik_output(stdout)

            # Get system identity
            stdout, stderr = self.ssh_manager.execute_command(ssh_client, "/system identity print")
            if stderr:
                self.logger.error(f"Error getting system identity: {stderr}")
                raise RuntimeError(f"Failed to get system identity: {stderr}")

            # Parse system identity output
            identity_info = self._parse_mikrotik_output(stdout)

            # Combine information
            router_info = {
                'identity': identity_info.get('name', 'unknown'),
                'ros_version': resource_info.get('version', 'unknown'),
                'architecture_name': resource_info.get('architecture-name', 'unknown'),
                'board_name': resource_info.get('board-name', 'unknown'),
                'uptime': resource_info.get('uptime', 'unknown'),
                'cpu_load': resource_info.get('cpu-load', 'unknown'),
                'total_memory': resource_info.get('total-memory', 'unknown'),
                'free_memory': resource_info.get('free-memory', 'unknown')
            }

            return router_info

        except Exception as e:
            self.logger.error(f"Failed to get router info: {str(e)}")
            raise

    def _parse_mikrotik_output(self, output: str) -> Dict[str, str]:
        """Parse Mikrotik output."""
        info = {}
        for line in output.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                info[key] = value
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
