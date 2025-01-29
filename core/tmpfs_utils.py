"""
RouterOS tmpfs management utilities.

This module provides functionality for managing temporary filesystems (tmpfs)
on RouterOS devices, helping to reduce flash storage wear during backup operations.

The tmpfs feature is used to store temporary backup files in RAM instead of flash
storage, which can significantly extend the life of the router's storage medium.
This is particularly important for devices that perform frequent backups.

Key Features:
- Automatic memory management and size calculation
- Safe mount point handling
- Fallback to flash storage when needed
- Target-specific configuration overrides

Requirements:
- RouterOS v7.7 or later
- Sufficient free memory (varies by configuration)
"""

import logging
import re
import paramiko
from typing import Dict, Optional, Tuple, TypedDict, Any
import time
from .logging_utils import LogManager
from .ssh_utils import SSHManager


class TmpfsError(Exception):
    """Base exception for tmpfs-related errors."""
    pass


class TmpfsVersionError(TmpfsError):
    """Raised when RouterOS version doesn't support tmpfs (< v7.7)."""
    pass


class TmpfsMemoryError(TmpfsError):
    """Raised when there isn't enough memory for tmpfs operations."""
    pass


class TmpfsMountError(TmpfsError):
    """Raised when tmpfs mount/unmount operations fail."""
    pass


class TmpfsFileError(TmpfsError):
    """Raised when file operations within tmpfs fail."""
    pass


class TmpfsConfig(TypedDict):
    """
    Global tmpfs configuration.

    This configuration type defines the global settings for tmpfs usage
    across all backup targets. These settings can be overridden on a
    per-target basis using TargetTmpfsConfig.

    Attributes:
        enabled: Global tmpfs enable/disable flag
        fallback_enabled: Whether to fall back to flash storage if tmpfs fails
        size_auto: Use automatic size calculation based on available memory
        size_mb: Fixed size in MB when size_auto is false
        min_size_mb: Minimum size (in MB) when using auto calculation
        max_size_mb: Maximum size (in MB) when using auto calculation
        mount_point: Name to use for the tmpfs mount point
    """
    enabled: bool = True
    fallback_enabled: bool = True
    size_auto: bool = True
    size_mb: int = 50
    min_size_mb: int = 1
    max_size_mb: int = 50
    mount_point: str = "rosbackup"


class TargetTmpfsConfig(TypedDict, total=False):
    """
    Target-specific tmpfs configuration overrides.

    This configuration allows overriding global tmpfs settings for specific
    backup targets. All fields are optional - any field not specified will
    use the global setting from TmpfsConfig.

    Attributes:
        enabled: Override global tmpfs enable/disable
        fallback_enabled: Override global fallback behavior
        size_mb: Override global size in MB
    """
    enabled: Optional[bool]
    fallback_enabled: Optional[bool]
    size_mb: Optional[int]


class TmpfsManager:
    """
    Manages tmpfs operations for RouterOS devices.

    This class handles all tmpfs-related operations including version checking,
    memory management, mount point operations, and file movement. It provides
    a safe and consistent interface for working with RouterOS tmpfs features.

    Key Features:
    - Automatic version compatibility checking
    - Memory availability verification
    - Dynamic size calculations
    - Safe mount point management
    - Atomic file operations

    All operations are performed via SSH using RouterOS commands. The class
    uses the existing logging infrastructure and provides detailed debug
    information for troubleshooting.

    Attributes:
        CREATE_COMMAND: RouterOS command template for creating tmpfs
        REMOVE_COMMAND: RouterOS command template for removing tmpfs
        MOVE_COMMAND: RouterOS command template for moving files
        LIST_COMMAND: RouterOS command template for listing disks
        SPACE_COMMAND: RouterOS command template for checking system resources
        DEFAULT_SIZE_MB: Default tmpfs size when memory is plentiful
        MIN_SIZE_MB: Minimum allowed tmpfs size
        MAX_SIZE_MB: Maximum allowed tmpfs size
        MEMORY_THRESHOLD_MB: Memory threshold for size calculation

    Example:
        ```python
        # Create manager instance
        tmpfs = TmpfsManager(ssh_manager)

        # Check support and setup tmpfs
        if tmpfs.check_router_support(ssh_client):
            has_memory, free_mb = tmpfs.check_memory_availability(ssh_client)
            if has_memory:
                size_mb = tmpfs.calculate_tmpfs_size(free_mb)
                tmpfs.setup_tmpfs(ssh_client, size_mb, "backup")
        ```
    """

    # RouterOS command templates for tmpfs operations
    CREATE_COMMAND = '/disk add type=tmpfs tmpfs-max-size={size}M slot={mount_point_name}'
    REMOVE_COMMAND = '/disk remove [find name={mount_point_name}]'
    MOVE_COMMAND = '/file set [find name={src}] name={dst}'
    LIST_COMMAND = "/disk print detail"
    SPACE_COMMAND = "/system resource print"
    
    # Memory management constants
    DEFAULT_SIZE_MB = 50  # Default size when memory is plentiful
    MIN_SIZE_MB = 1      # Minimum allowed size
    MAX_SIZE_MB = 50     # Maximum allowed size
    MEMORY_THRESHOLD_MB = 256  # Memory threshold for size calculation

    def __init__(self, ssh_manager: SSHManager, logger: Optional[logging.Logger] = None) -> None:
        """
        Initialize TmpfsManager.

        Creates a new TmpfsManager instance that will use the provided SSH manager
        for RouterOS communication. If no logger is provided, creates a new one
        using the existing LogManager infrastructure.

        Args:
            ssh_manager: SSH manager for executing RouterOS commands
            logger: Optional logger for tmpfs operations. If None, creates a new
                   logger with component='TMPFS' and the target name from ssh_manager
        """
        self.ssh_manager = ssh_manager
        self.logger = logger or LogManager().get_logger('TMPFS', ssh_manager.target_name)
        self.logger.debug("Initialized TmpfsManager")
        self.logger.debug(f"Create command template: {self.CREATE_COMMAND}")
        self.logger.debug(f"Remove command template: {self.REMOVE_COMMAND}")
        self.logger.debug(f"Move command template: {self.MOVE_COMMAND}")

    def execute_command(self, ssh_client, command: str, error_msg: str) -> Tuple[str, str, int]:
        """Execute a RouterOS command with proper error handling and logging."""
        try:
            self.logger.debug(f"Executing command: {command}")
            stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, command)
            self.logger.debug(f"Command stdout: {stdout}")
            self.logger.debug(f"Command stderr: {stderr}")
            self.logger.debug(f"Command exit status: {exit_status}")
            return stdout, stderr, exit_status
        except Exception as e:
            self.logger.error(f"{error_msg}: {str(e)}")
            raise

    def check_router_support(self, ssh_client) -> bool:
        """
        Check if router supports tmpfs (RouterOS >= v7.7).

        Verifies that the RouterOS version running on the target device supports
        tmpfs operations. This requires version 7.7 or later. The version is
        extracted from the system resource information.

        Args:
            ssh_client: Connected SSH client to use for command execution

        Returns:
            bool: True if tmpfs is supported

        Raises:
            TmpfsVersionError: If RouterOS version is not supported or cannot
                           be determined
        """
        try:
            self.logger.debug("Checking RouterOS version for tmpfs support")
            stdout, stderr, exit_status = self.execute_command(
                ssh_client,
                "/system resource print",
                "Failed to check RouterOS version"
            )

            if stderr or exit_status != 0:
                raise TmpfsVersionError(f"Failed to get RouterOS version: {stderr}")

            # Extract version from output
            version_match = re.search(r'version:\s+(\d+)\.(\d+)(?:\.(\d+))?', stdout)
            if not version_match:
                raise TmpfsVersionError("Could not find RouterOS version in system output")

            major = int(version_match.group(1))
            minor = int(version_match.group(2))
            patch = int(version_match.group(3) or 0)
            version = f"{major}.{minor}.{patch}"

            # Check if version meets minimum requirement (>= 7.7)
            supported = (major > 7) or (major == 7 and minor >= 7)
            if supported:
                self.logger.debug(f"RouterOS {version} supports tmpfs")
            else:
                self.logger.warning(f"RouterOS {version} does not support tmpfs (requires >= 7.7)")

            return supported

        except Exception as e:
            if not isinstance(e, TmpfsVersionError):
                self.logger.error(f"Failed to check RouterOS version: {str(e)}")
                raise TmpfsVersionError(f"Failed to check RouterOS version: {str(e)}")
            raise

    def check_memory_availability(self, ssh_client) -> Tuple[bool, int]:
        """
        Check if router has enough free memory for tmpfs.

        Queries the router's memory information and determines if there is
        sufficient free memory for tmpfs operations. The minimum required
        memory is defined by MEMORY_THRESHOLD_MB.

        Memory values are automatically converted to MB regardless of the
        unit reported by RouterOS (KiB, MiB, GiB).

        Args:
            ssh_client: Connected SSH client to use for command execution

        Returns:
            Tuple[bool, int]: A tuple containing:
                - has_enough_memory: True if memory meets requirements
                - free_memory_mb: Amount of free memory in MB

        Raises:
            TmpfsMemoryError: If memory information cannot be retrieved or
                            parsed from RouterOS output
        """
        try:
            self.logger.debug("Checking memory availability for tmpfs")
            stdout, stderr, exit_status = self.execute_command(
                ssh_client,
                self.SPACE_COMMAND,
                "Failed to check memory availability"
            )

            if stderr or exit_status != 0:
                raise TmpfsMemoryError(f"Failed to get memory information: {stderr}")

            # Extract free memory value
            memory_match = re.search(r'free-memory:\s+(\d+(?:\.\d+)?)(KiB|MiB|GiB)', stdout)
            if not memory_match:
                raise TmpfsMemoryError("Could not find free memory information")

            value = float(memory_match.group(1))
            unit = memory_match.group(2)

            # Convert to MB
            if unit == 'KiB':
                free_mb = int(value // 1024)
            elif unit == 'GiB':
                free_mb = int(value * 1024)
            else:  # MiB
                free_mb = int(value)

            self.logger.debug(f"Free memory: {free_mb}MB")
            has_enough = free_mb >= self.MEMORY_THRESHOLD_MB
            self.logger.debug(f"Has enough memory: {has_enough} (threshold: {self.MEMORY_THRESHOLD_MB}MB)")

            return has_enough, free_mb

        except Exception as e:
            if not isinstance(e, TmpfsMemoryError):
                self.logger.error(f"Failed to check memory availability: {str(e)}")
                raise TmpfsMemoryError(f"Failed to check memory availability: {str(e)}")
            raise

    def calculate_tmpfs_size(self, free_memory_mb: int) -> int:
        """
        Calculate appropriate tmpfs size based on available memory.

        Determines the optimal tmpfs size based on available memory:
        - If free memory >= MEMORY_THRESHOLD_MB: Uses DEFAULT_SIZE_MB
        - Otherwise: Uses 10% of free memory, capped between MIN_SIZE_MB
          and MAX_SIZE_MB

        Args:
            free_memory_mb: Available memory in MB

        Returns:
            int: Calculated tmpfs size in MB, guaranteed to be between
                 MIN_SIZE_MB and MAX_SIZE_MB
        """
        # For routers with plenty of memory, use default size
        if free_memory_mb >= self.MEMORY_THRESHOLD_MB:
            size_mb = self.DEFAULT_SIZE_MB
        else:
            # For routers with less memory, use 10% of free memory
            size_mb = max(self.MIN_SIZE_MB, min(self.MAX_SIZE_MB, free_memory_mb // 10))

        self.logger.debug(f"Calculated tmpfs size: {size_mb}MB (free memory: {free_memory_mb}MB)")
        return size_mb

    def check_mount_point_exists(self, ssh_client, mount_point: str) -> bool:
        """
        Check if a mount point exists in the disk list.

        Verifies whether a mount point exists at the specified
        mount point by querying RouterOS disk information.

        Args:
            ssh_client: Connected SSH client
            mount_point: Mount point name to check

        Returns:
            bool: True if mount point exists

        Raises:
            TmpfsMountError: If mount point check fails
        """
        try:
            self.logger.debug(f"Checking for existing mount point: {mount_point}")
            stdout, stderr, exit_status = self.execute_command(
                ssh_client,
                self.LIST_COMMAND,
                f"Failed to check mount point {mount_point}"
            )

            if stderr or exit_status != 0:
                raise TmpfsMountError(f"Failed to check mount point {mount_point}: {stderr}")

            # Look for a line that contains both 'type=tmpfs' and our mount point
            for line in stdout.splitlines():
                if 'type=tmpfs' in line and f'slot="{mount_point}"' in line:
                    return True
            return False

        except Exception as e:
            if not isinstance(e, TmpfsMountError):
                self.logger.error(f"Failed to check mount point: {str(e)}")
                raise TmpfsMountError(f"Failed to check mount point: {str(e)}")
            raise

    def setup_tmpfs(self, ssh_client, size_mb: int, mount_point: str) -> bool:
        """
        Create a new tmpfs mount.

        Creates a new tmpfs mount point with the specified size. If a mount
        already exists at the given point, it will be removed first. After
        creation, verifies that the mount point exists.

        Args:
            ssh_client: Connected SSH client
            size_mb: Size of tmpfs in MB
            mount_point: Mount point name for tmpfs

        Returns:
            bool: True if tmpfs was created successfully

        Raises:
            TmpfsMountError: If tmpfs creation fails
        """
        try:
            self.logger.debug(f"Setting up tmpfs: size={size_mb}MB, mount_point={mount_point}")

            # First check if mount point already exists
            if self.check_mount_point_exists(ssh_client, mount_point):
                self.logger.warning(f"Tmpfs already exists at {mount_point}, cleaning up first")
                if not self.cleanup_tmpfs(ssh_client, mount_point):
                    raise TmpfsMountError(f"Failed to clean up existing tmpfs at {mount_point}")

            # Create new tmpfs
            cmd = self.CREATE_COMMAND.format(size=size_mb, mount_point_name=mount_point)
            stdout, stderr, exit_status = self.execute_command(
                ssh_client,
                cmd,
                "Failed to create tmpfs"
            )

            if stderr or exit_status != 0:
                raise TmpfsMountError(f"Failed to create tmpfs: {stderr}")

            # Add a short delay to ensure disk is registered
            time.sleep(1)

            # Verify mount was created
            if not self.check_mount_point_exists(ssh_client, mount_point):
                raise TmpfsMountError(f"Tmpfs creation succeeded but mount point {mount_point} not found")

            self.logger.info(f"Created {size_mb}MB tmpfs at {mount_point}")
            return True

        except Exception as e:
            if not isinstance(e, TmpfsMountError):
                self.logger.error(f"Failed to setup tmpfs: {str(e)}")
                raise TmpfsMountError(f"Failed to setup tmpfs: {str(e)}")
            raise

    def cleanup_tmpfs(self, ssh_client, mount_point: str) -> bool:
        """
        Remove a tmpfs mount.

        Safely removes a tmpfs mount point if it exists. Does nothing if
        the mount point doesn't exist. After removal, verifies that the
        mount point is gone.

        Args:
            ssh_client: Connected SSH client
            mount_point: Mount point name to remove

        Returns:
            bool: True if tmpfs was removed successfully

        Raises:
            TmpfsMountError: If tmpfs removal fails
        """
        try:
            self.logger.debug(f"Cleaning up tmpfs at mount point: {mount_point}")

            # Check if mount exists first
            if not self.check_mount_point_exists(ssh_client, mount_point):
                self.logger.debug(f"No tmpfs found at {mount_point}, nothing to clean up")
                return True

            # Remove tmpfs
            cmd = self.REMOVE_COMMAND.format(mount_point_name=mount_point)
            stdout, stderr, exit_status = self.execute_command(
                ssh_client,
                cmd,
                "Failed to remove tmpfs"
            )

            if stderr or exit_status != 0:
                raise TmpfsMountError(f"Failed to remove tmpfs: {stderr}")

            # Add a short delay to ensure disk is unregistered
            time.sleep(1)

            # Verify mount was removed
            if self.check_mount_point_exists(ssh_client, mount_point):
                raise TmpfsMountError(f"Tmpfs removal succeeded but mount point {mount_point} still exists")

            self.logger.info(f"Removed tmpfs at {mount_point}")
            return True

        except Exception as e:
            if not isinstance(e, TmpfsMountError):
                self.logger.error(f"Failed to cleanup tmpfs: {str(e)}")
                raise TmpfsMountError(f"Failed to cleanup tmpfs: {str(e)}")
            raise

    def get_tmpfs_path(self, mount_point: str, filename: str) -> str:
        """Get the full path for a file in tmpfs.

        Args:
            mount_point: Tmpfs mount point
            filename: Name of the file

        Returns:
            str: Full path to file in tmpfs
        """
        return f"{mount_point}/{filename}"

    def move_file_from_tmpfs(self, ssh_client: paramiko.SSHClient, src_path: str, dst_path: str) -> bool:
        """Move a file from tmpfs to flash storage.

        Args:
            ssh_client: Connected SSH client
            src_path: Source path in tmpfs (e.g., 'rosbackup/file.backup')
            dst_path: Destination path in flash storage (e.g., 'file.backup')

        Returns:
            bool: True if file was moved successfully
        """
        try:
            # First, verify the source file exists
            verify_cmd = f"/file print detail where name={src_path}"
            self.logger.debug(f"Verifying source file: {verify_cmd}")
            stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, verify_cmd)
            if exit_status != 0 or src_path not in stdout:
                # Try without the mount point prefix
                if '/' in src_path:
                    base_name = src_path.split('/')[-1]
                    verify_cmd = f"/file print detail where name={base_name}"
                    self.logger.debug(f"Retrying source verification: {verify_cmd}")
                    stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, verify_cmd)
                    if exit_status != 0 or base_name not in stdout:
                        self.logger.error("Source file not found")
                        return False
                else:
                    self.logger.error("Source file not found")
                    return False

            # Then move the file
            move_cmd = self.MOVE_COMMAND.format(src=src_path, dst=dst_path)
            self.logger.debug(f"Moving file with command: {move_cmd}")
            stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, move_cmd)
            if exit_status != 0:
                self.logger.error(f"Failed to move file: {stderr}")
                return False
            
            # Verify the file was moved successfully
            verify_cmd = f"/file print detail where name={dst_path}"
            self.logger.debug(f"Verifying destination file: {verify_cmd}")
            stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, verify_cmd)
            if exit_status != 0 or dst_path not in stdout:
                self.logger.error("Destination file not found after move")
                return False

            return True
        except Exception as e:
            self.logger.error(f"Error moving file from tmpfs: {str(e)}")
            return False
