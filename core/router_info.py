"""
RouterOS device information gathering utilities.
"""

import paramiko
from typing import Dict, Optional
import logging
from .ssh_utils import SSHManager


class RouterInfoManager:
    """Manages RouterOS device information gathering operations."""

    def __init__(self, ssh_manager: SSHManager):
        """
        Initialize RouterInfo manager.

        Args:
            ssh_manager (SSHManager): SSH manager instance for executing commands
        """
        self.ssh_manager = ssh_manager
        self.logger = logging.getLogger(__name__)

    def get_router_info(self, ssh_client: paramiko.SSHClient) -> Dict[str, str]:
        """
        Retrieve comprehensive router information.

        Args:
            ssh_client (paramiko.SSHClient): Connected SSH client

        Returns:
            Dict[str, str]: Dictionary containing router information with the following keys:
                - identity: Router's identity name
                - model: Router's model name
                - ros_version: RouterOS version (stripped of "(stable)" suffix)
                - architecture_name: Router's architecture
                - cpu_name: CPU model name
                - cpu_count: Number of CPU cores
                - cpu_frequency: CPU frequency in MHz
                - total_memory: Total memory in bytes
                - free_memory: Free memory in bytes
                - free_hdd_space: Free disk space in bytes
                - license: RouterOS license level

        Note:
            The version string is cleaned by removing any "(stable)" suffix and spaces.
            Example: "7.16.2 (stable)" becomes "7.16.2"
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

        Args:
            ssh_client (paramiko.SSHClient): Connected SSH client
            backup_file (str): Backup file path

        Returns:
            Optional[int]: File size in bytes or None if not found
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

        Args:
            ssh_client (paramiko.SSHClient): Connected SSH client

        Returns:
            bool: True if we have sufficient access, False otherwise
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
