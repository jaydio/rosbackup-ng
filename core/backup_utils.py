"""
RouterOS backup operations management.

This module handles both binary and plaintext backup operations for RouterOS devices.
It supports encrypted backups, parallel execution, and various backup retention options.
"""

import paramiko
from pathlib import Path
from typing import Dict, Optional, Tuple, TypedDict, Any
import logging
from datetime import datetime
import os
from scp import SCPClient
import time
from .ssh_utils import SSHManager
from .router_utils import RouterInfoManager
from .logging_utils import LogManager


class RouterInfo(TypedDict):
    """
    Type definition for router information dictionary.

    Attributes:
        identity: Router identity name
        model: Router hardware model
        ros_version: RouterOS version
        architecture_name: CPU architecture name
        cpu_name: CPU model name
        cpu_count: Number of CPU cores
        cpu_frequency: CPU frequency
        total_memory: Total RAM
        free_memory: Available RAM
        free_hdd_space: Available disk space
        license: License level
    """
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


class BackupResult(TypedDict):
    """
    Type definition for backup operation result.

    Attributes:
        success: Whether the backup operation succeeded
        file_path: Path to the backup file if successful
        error_message: Error message if backup failed
    """
    success: bool
    file_path: Optional[Path]
    error_message: Optional[str]


class BackupManager:
    """
    Manages RouterOS backup operations.
    
    This class handles both binary (.backup) and plaintext (.rsc) backups,
    supporting features like encryption, parallel execution, and retention management.
    
    Attributes:
        ssh_manager (SSHManager): Manages SSH connections to routers
        router_info_manager (RouterInfoManager): Handles router information retrieval
        logger (logging.Logger): Logger instance for this class
    """

    def __init__(self, ssh_manager: SSHManager, router_info_manager: RouterInfoManager, logger: Optional[logging.Logger] = None) -> None:
        """
        Initialize backup manager.

        Args:
            ssh_manager: Manages SSH connections and command execution
            router_info_manager: Handles router information gathering
            logger: Optional logger for router-specific logging
        """
        self.ssh_manager = ssh_manager
        self.router_info_manager = router_info_manager
        self.logger = logger or LogManager().system

    def perform_binary_backup(
        self,
        ssh_client: paramiko.SSHClient,
        router_info: RouterInfo,
        backup_password: str,
        encrypted: bool,
        backup_dir: Path,
        timestamp: str,
        keep_binary_backup: bool,
        dry_run: bool = False
    ) -> Tuple[bool, Optional[Path]]:
        """
        Perform binary backup of RouterOS device.

        Creates a binary backup file (.backup) that can be used for full system restore.
        The backup can be optionally encrypted using the provided password.

        Args:
            ssh_client: Connected SSH client to the router
            router_info: Dictionary containing router information
            backup_password: Password for backup encryption
            encrypted: Whether to encrypt the backup
            backup_dir: Directory to store the backup
            timestamp: Timestamp string (format: DDMMYYYY-HHMMSS)
            keep_binary_backup: Whether to keep backup file on router
            dry_run: If True, only simulate the backup

        Returns:
            A tuple containing:
            - bool: True if backup was successful
            - Optional[Path]: Path to the backup file if successful, None otherwise

        File Naming:
            The binary backup file follows the format:
            {identity}-{version}-{arch}-{timestamp}.backup
            Example: MYR1-7.16.2-x86_64-02012025-164736.backup

        Error Handling:
            - Verifies backup file creation on router
            - Checks file size after download
            - Handles SSH and SCP errors
            - Cleans up remote file if needed
        """
        if dry_run:
            self.logger.info("[DRY RUN] Would perform binary backup")
            return True, Path(backup_dir) / f"dry_run_{timestamp}.backup"

        # Generate backup file name based on router info, removing spaces
        ros_version = router_info['ros_version'].replace(' ', '')
        router_name = f"{router_info['identity']}-{ros_version}-{router_info['architecture_name']}"
        backup_name = f"{router_name}-{timestamp}.backup"
        remote_path = backup_name
        local_path = backup_dir / backup_name

        try:
            # Create backup command
            backup_cmd = "/system backup save"
            if encrypted:
                backup_cmd += f" password=\"{backup_password}\""
            backup_cmd += f" name=\"{remote_path}\""

            # Execute backup command
            stdout, stderr = self.ssh_manager.execute_command(ssh_client, backup_cmd)
            self.logger.debug(f"Backup command: {backup_cmd}")
            self.logger.debug(f"Stdout: {stdout}")
            self.logger.debug(f"Stderr: {stderr}")
            if stderr:
                self.logger.error(f"Error creating backup: {stderr}")
                return False, None

            # Wait for backup to complete and verify file
            time.sleep(2)  # Give RouterOS time to create the file
            
            self.logger.debug(f"Checking for backup file: {remote_path}")
            # Use /file print to check for file existence
            check_cmd = f"/file print where name=\"{remote_path}\""
            stdout, stderr = self.ssh_manager.execute_command(ssh_client, check_cmd)
            self.logger.debug(f"File check command: {check_cmd}")
            self.logger.debug(f"File check output: {stdout}")
            if not stdout or "no such item" in stdout.lower():
                self.logger.error("Backup file was not created on router")
                return False, None

            self.logger.info(f"Binary backup file {remote_path} exists on the router.")

            # Download the backup file
            try:
                with SCPClient(ssh_client.get_transport()) as scp:
                    scp.get(remote_path, str(local_path))
                self.logger.info(f"Downloaded {remote_path}")
            except Exception as e:
                self.logger.error(f"Failed to download backup file: {str(e)}")
                return False, None

            # Remove the remote backup file
            if not keep_binary_backup:
                rm_cmd = f"/file remove \"{remote_path}\""
                stdout, stderr = self.ssh_manager.execute_command(ssh_client, rm_cmd)
                if not stderr:
                    self.logger.info(f"Removed remote {remote_path}")
                else:
                    self.logger.warning(f"Failed to remove remote backup file: {stderr}")

            # Verify local backup file exists and has size
            if not local_path.exists() or local_path.stat().st_size == 0:
                self.logger.error("Local backup file is missing or empty")
                return False, None

            return True, local_path

        except Exception as e:
            self.logger.error(f"Binary backup failed: {str(e)}")
            return False, None

    def perform_plaintext_backup(
        self,
        ssh_client: paramiko.SSHClient,
        router_info: RouterInfo,
        backup_dir: Path,
        timestamp: str,
        keep_plaintext_backup: bool = False,
        dry_run: bool = False
    ) -> Tuple[bool, Optional[Path]]:
        """
        Perform plaintext (export) backup of RouterOS device.

        Creates a plaintext backup file (.rsc) containing router configuration
        that can be used for partial restore or configuration review.

        Args:
            ssh_client: Connected SSH client to the router
            router_info: Dictionary containing router information
            backup_dir: Directory to store the backup
            timestamp: Timestamp string (format: DDMMYYYY-HHMMSS)
            keep_plaintext_backup: Whether to keep export on router
            dry_run: If True, only simulate the backup

        Returns:
            A tuple containing:
            - bool: True if backup was successful
            - Optional[Path]: Path to the backup file if successful, None otherwise

        File Naming:
            The plaintext export file follows the format:
            {identity}-{version}-{arch}-{timestamp}.rsc
            Example: MYR1-7.16.2-x86_64-02012025-164736.rsc

        Error Handling:
            - Verifies export command output
            - Handles SSH connection errors
            - Validates file writing operations
            - Manages router-side file operations
        """
        if dry_run:
            self.logger.info("[DRY RUN] Would perform plaintext backup")
            return True, Path(backup_dir) / f"dry_run_{timestamp}.rsc"

        # Export configuration to file
        try:
            # Execute export command and get output directly
            stdin, stdout, stderr = ssh_client.exec_command('/export')
            stdout = stdout.read().decode()
            stderr = stderr.read().decode()

            if stderr:
                self.logger.error(f"Export command failed: {stderr.strip()}")
                return False, None

            if not stdout:
                self.logger.error("Export command produced no output")
                return False, None

            # Save export to file with router info in name, removing spaces
            ros_version = router_info['ros_version'].replace(' ', '')
            router_name = f"{router_info['identity']}-{ros_version}-{router_info['architecture_name']}"
            backup_name = f"{router_name}-{timestamp}.rsc"
            backup_path = backup_dir / backup_name
            backup_path.write_text(stdout)
            self.logger.info(f"Plaintext backup saved as {backup_name}")

            # Optionally save the export on the router
            if keep_plaintext_backup:
                try:
                    # Save the export to a file on the router
                    save_command = f'/export file={backup_name}'
                    stdin, stdout, stderr = ssh_client.exec_command(save_command)
                    stderr = stderr.read().decode()
                    if stderr:
                        self.logger.error(f"Failed to save export on router: {stderr.strip()}")
                        return False, None
                    self.logger.info(f"Plaintext export saved on router as {backup_name}")
                except Exception as e:
                    self.logger.error(f"Error saving export on router: {str(e)}")
                    return False, None
            else:
                self.logger.debug("Not keeping plaintext export on router")

            return True, backup_path
        except Exception as e:
            self.logger.error(f"Error during plaintext backup: {str(e)}")
            return False, None

    def save_info_file(
        self,
        router_info: RouterInfo,
        info_file_path: Path,
        dry_run: bool = False
    ) -> bool:
        """
        Save router information to an INFO file.

        Args:
            router_info: Dictionary containing router information
            info_file_path: Path to save INFO file
            dry_run: If True, only simulate the save

        Returns:
            bool: True if successful, False otherwise

        File Naming:
            The info file will be named using the format:
            {identity}-{version}-{arch}-{timestamp}.INFO.txt
            Example: MYR1-7.16.2-x86_64-02012025-164736.INFO.txt

        File Format:
            The info file contains a header "Router Information:" followed by
            formatted key-value pairs of router information.
        """
        if dry_run:
            self.logger.info(f"[DRY RUN] Would save router info to {info_file_path}")
            return True

        try:
            with open(info_file_path, 'w') as f:
                f.write("Router Information:\n")
                f.write("==================\n\n")
                for key, value in router_info.items():
                    f.write(f"{key.replace('_', ' ').title()}: {value}\n")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save info file: {str(e)}")
            return False
