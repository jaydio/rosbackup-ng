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
    # System Identity
    identity: str
    name: str
    
    # System Resource
    model: str
    board_name: str
    serial_number: str
    firmware_type: str
    factory_firmware: str
    current_firmware: str
    upgrade_firmware: str
    
    # System Resources
    uptime: str
    version: str
    build_time: str
    free_memory: str
    total_memory: str
    cpu_name: str
    cpu_count: str
    cpu_frequency: str
    cpu_load: str
    free_hdd_space: str
    total_hdd_space: str
    write_sect_since_reboot: str
    write_sect_total: str
    bad_blocks: str
    architecture_name: str
    platform: str
    
    # License
    software_id: str
    upgradable_to: str
    license: str
    features: str
    ros_version: str


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
            # Get system identity
            stdout, stderr = self.ssh_manager.execute_command(ssh_client, "/system identity print")
            if stderr:
                self.logger.error(f"Error getting system identity: {stderr}")
                raise RuntimeError(f"Failed to get system identity: {stderr}")
            identity_info = self._parse_mikrotik_output(stdout)

            # Get system resource info
            stdout, stderr = self.ssh_manager.execute_command(ssh_client, "/system resource print")
            if stderr:
                self.logger.error(f"Error getting system resource info: {stderr}")
                raise RuntimeError(f"Failed to get system resource info: {stderr}")
            resource_info = self._parse_mikrotik_output(stdout)

            # Get routerboard info
            stdout, stderr = self.ssh_manager.execute_command(ssh_client, "/system routerboard print")
            if stderr:
                self.logger.error(f"Error getting routerboard info: {stderr}")
                raise RuntimeError(f"Failed to get routerboard info: {stderr}")
            board_info = self._parse_mikrotik_output(stdout)

            # Get license info
            stdout, stderr = self.ssh_manager.execute_command(ssh_client, "/system license print")
            if stderr:
                self.logger.error(f"Error getting license info: {stderr}")
                raise RuntimeError(f"Failed to get license info: {stderr}")
            license_info = self._parse_mikrotik_output(stdout)

            # Combine all information
            router_info = {
                # System Identity
                'identity': identity_info.get('name', 'unknown'),
                'name': identity_info.get('name', 'unknown'),
                
                # System Resource
                'model': board_info.get('model', 'unknown'),
                'board_name': board_info.get('board-name', 'unknown'),
                'serial_number': board_info.get('serial-number', 'unknown'),
                'firmware_type': board_info.get('firmware-type', 'unknown'),
                'factory_firmware': board_info.get('factory-firmware', 'unknown'),
                'current_firmware': board_info.get('current-firmware', 'unknown'),
                'upgrade_firmware': board_info.get('upgrade-firmware', 'unknown'),
                
                # System Resources
                'uptime': resource_info.get('uptime', 'unknown'),
                'version': resource_info.get('version', 'unknown'),
                'build_time': resource_info.get('build-time', 'unknown'),
                'free_memory': resource_info.get('free-memory', 'unknown'),
                'total_memory': resource_info.get('total-memory', 'unknown'),
                'cpu_name': resource_info.get('cpu', 'unknown'),
                'cpu_count': resource_info.get('cpu-count', 'unknown'),
                'cpu_frequency': resource_info.get('cpu-frequency', 'unknown'),
                'cpu_load': resource_info.get('cpu-load', 'unknown'),
                'free_hdd_space': resource_info.get('free-hdd-space', 'unknown'),
                'total_hdd_space': resource_info.get('total-hdd-space', 'unknown'),
                'write_sect_since_reboot': resource_info.get('write-sect-since-reboot', 'unknown'),
                'write_sect_total': resource_info.get('write-sect-total', 'unknown'),
                'bad_blocks': resource_info.get('bad-blocks', 'unknown'),
                'architecture_name': resource_info.get('architecture-name', 'unknown'),
                'platform': resource_info.get('platform', 'unknown'),
                
                # License
                'software_id': license_info.get('software-id', 'unknown'),
                'upgradable_to': license_info.get('upgradable-to', 'unknown'),
                'license': license_info.get('nlevel', 'unknown'),
                'features': license_info.get('features', 'unknown'),
                
                # For compatibility
                'ros_version': resource_info.get('version', 'unknown'),
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
