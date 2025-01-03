"""
RouterOS device information gathering utilities.

This module provides functionality to gather system information from RouterOS devices,
including hardware specifications, resource usage, and access validation.
"""

import paramiko
from typing import Dict, Optional, TypedDict, Literal, Any
import logging
from .ssh_utils import SSHManager
import re


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

    def __init__(self, ssh_manager: SSHManager, logger: Optional[logging.LoggerAdapter] = None) -> None:
        """
        Initialize RouterInfo manager.

        Args:
            ssh_manager: SSH manager instance for executing commands
            logger: Optional logger adapter for router-specific logging
        """
        self.ssh_manager = ssh_manager
        self.logger = logger or logging.getLogger(__name__)

    def get_router_info(self, ssh_client: paramiko.SSHClient) -> Optional[Dict[str, Any]]:
        """
        Get router information.

        Args:
            ssh_client: Connected SSH client to the router

        Returns:
            Dict containing router information or None on error
        """
        try:
            router_info = {}

            # Get system resource info
            stdout, stderr = self.ssh_manager.execute_command(ssh_client, "/system resource print")
            if stderr:
                self.logger.error(f"Failed to get system resource info: {stderr}")
                return None
            router_info.update(self._parse_system_resource(stdout))

            # Get system identity
            stdout, stderr = self.ssh_manager.execute_command(ssh_client, "/system identity print")
            if stderr:
                self.logger.error(f"Failed to get system identity: {stderr}")
                return None
            router_info.update(self._parse_system_identity(stdout))

            # Get system routerboard info
            stdout, stderr = self.ssh_manager.execute_command(ssh_client, "/system routerboard print")
            if stderr:
                self.logger.error(f"Failed to get routerboard info: {stderr}")
                return None
            router_info.update(self._parse_routerboard_info(stdout))

            return router_info

        except Exception as e:
            self.logger.error(f"Failed to get router info: {str(e)}")
            return None

    def _parse_system_resource(self, output: str) -> Dict[str, Any]:
        """Parse system resource output."""
        info = {}
        for line in output.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                info[key] = value

        # Extract version components
        if "version" in info:
            version_match = re.match(r"(\d+\.\d+\.\d+)(?:-(\w+))?", info["version"])
            if version_match:
                info["ros_version"] = version_match.group(1)
                info["ros_channel"] = version_match.group(2) or "stable"

        # Set architecture name based on architecture field
        if "architecture" in info:
            arch = info["architecture"].lower()
            if "arm" in arch:
                info["architecture_name"] = "arm64" if "64" in arch else "arm"
            elif "mips" in arch:
                info["architecture_name"] = "mipsbe"
            elif "x86" in arch:
                info["architecture_name"] = "x86_64" if "64" in arch else "x86"
            elif "tile" in arch:
                info["architecture_name"] = "tile"
            else:
                info["architecture_name"] = "x86_64"  # Default to most common

        return info

    def _parse_system_identity(self, output: str) -> Dict[str, Any]:
        """Parse system identity output."""
        info = {}
        for line in output.splitlines():
            if "name:" in line.lower():
                info["identity"] = line.split(":", 1)[1].strip()
                break
        return info

    def _parse_routerboard_info(self, output: str) -> Dict[str, Any]:
        """Parse routerboard info output."""
        info = {}
        for line in output.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                info[key] = value

        # Map model-specific info
        if "model" in info:
            info["architecture_name"] = self._get_architecture_name(info["model"])

        return info

    def _get_architecture_name(self, model: str) -> str:
        """Get architecture name based on model."""
        model = model.lower()
        
        # Cloud Core Router series
        if "ccr" in model:
            if any(x in model for x in ["1009", "1016", "1036"]):
                return "arm64"
            return "tile"
            
        # Cloud Router Switch series
        if "crs" in model:
            if "crs3" in model:
                return "arm64"
            return "mipsbe"
            
        # hAP series
        if "hap" in model:
            if "ac" in model or "ax" in model:
                return "arm"
            return "mipsbe"
            
        # Default to most common architecture
        return "x86_64"

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
