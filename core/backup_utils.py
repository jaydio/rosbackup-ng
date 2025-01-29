"""
RouterOS backup operations management.

This module handles both binary and plaintext backup operations for RouterOS devices.
It supports encrypted backups, parallel execution, and various backup retention options.
"""

import paramiko
import socket
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TypedDict, Any, Callable
from zoneinfo import ZoneInfo
import logging
import os
import re
from scp import SCPClient
import time
from .ssh_utils import SSHManager
from .router_utils import RouterInfoManager
from .logging_utils import LogManager
from .time_utils import get_timestamp
from .tmpfs_utils import TmpfsManager, TmpfsConfig, TargetTmpfsConfig
import concurrent.futures

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
        uptime: Uptime
        factory_firmware: Factory firmware
        total_hdd_space: Total HDD space
        write_sect_since_reboot: Write sectors since reboot
        write_sect_total: Write sectors total
        board_name: Optional board name
        system_id: System ID
        time: Time
        date: Date
        time_zone_name: Time zone name
        gmt_offset: GMT offset
        dst_active: DST active
        time_zone_autodetect: Time zone autodetect
        ipv4_fw_filter: IPv4 firewall filter rules
        ipv6_fw_filter: IPv6 firewall filter rules
        ipv4_fw_raw: IPv4 firewall raw rules
        ipv6_fw_raw: IPv6 firewall raw rules
        ipv4_fw_nat: IPv4 firewall NAT rules
        ipv6_fw_nat: IPv6 firewall NAT rules
        ipv4_fw_mangle: IPv4 firewall mangle rules
        ipv6_fw_mangle: IPv6 firewall mangle rules
        ipv4_fw_address_list: IPv4 firewall address list entries
        ipv6_fw_address_list: IPv6 firewall address list entries
        ipv4_fw_connections: IPv4 firewall active connections
        ipv6_fw_connections: IPv6 firewall active connections
        ipv4_addresses: IPv4 addresses
        ipv6_addresses: IPv6 addresses
        ipv4_pools: IPv4 pools
        ipv6_pools: IPv6 pools
        ipv4_dhcp_servers: IPv4 DHCP servers
        ipv6_dhcp_servers: IPv6 DHCP servers
        ipv4_dhcp_clients: IPv4 DHCP clients
        ipv6_dhcp_clients: IPv6 DHCP clients
        ipv4_dhcp_relays: IPv4 DHCP relays
        ipv6_dhcp_relays: IPv6 DHCP relays
        bridge_interfaces: Bridge interfaces
        bond_interfaces: Bond interfaces
        vlan_interfaces: VLAN interfaces
        ppp_active_sessions: Active PPP sessions
        queue_tree_items: Queue tree items
        ipv4_arp_failed: IPv4 ARP failed
        ipv4_arp_permanent: IPv4 ARP permanent
        ipv4_arp_reachable: IPv4 ARP reachable
        ipv6_neighbors: IPv6 neighbors
        ethernet_interfaces: Ethernet interfaces
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
    uptime: str
    factory_firmware: str
    total_hdd_space: str
    write_sect_since_reboot: str
    write_sect_total: str
    board_name: Optional[str]
    system_id: str
    time: str
    date: str
    time_zone_name: str
    gmt_offset: str
    dst_active: str
    time_zone_autodetect: str
    ipv4_fw_filter: str
    ipv6_fw_filter: str
    ipv4_fw_raw: str
    ipv6_fw_raw: str
    ipv4_fw_nat: str
    ipv6_fw_nat: str
    ipv4_fw_mangle: str
    ipv6_fw_mangle: str
    ipv4_fw_address_list: str
    ipv6_fw_address_list: str
    ipv4_fw_connections: str
    ipv6_fw_connections: str
    ipv4_addresses: str
    ipv6_addresses: str
    ipv4_pools: str
    ipv6_pools: str
    ipv4_dhcp_servers: str
    ipv6_dhcp_servers: str
    ipv4_dhcp_clients: str
    ipv6_dhcp_clients: str
    ipv4_dhcp_relays: str
    ipv6_dhcp_relays: str
    bridge_interfaces: str
    bond_interfaces: str
    vlan_interfaces: str
    ppp_active_sessions: str
    queue_tree_items: str
    ipv4_arp_failed: str
    ipv4_arp_permanent: str
    ipv4_arp_reachable: str
    ipv6_neighbors: str
    ethernet_interfaces: str


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


class BackupConfig(TypedDict):
    """Backup configuration type definition."""
    backup_path_parent: str
    backup_retention_days: Optional[int]
    backup_password: Optional[str]
    timezone: Optional[str]
    parallel_execution: Optional[bool]
    max_parallel_backups: Optional[int]
    log_file_enabled: Optional[bool]
    log_file: Optional[str]
    log_level: Optional[str]
    log_retention_days: Optional[int]
    tmpfs: Optional[TmpfsConfig]  # Global tmpfs settings


class TargetConfig(TypedDict):
    """Target configuration type definition.

    Required Fields:
        host: Hostname or IP address
        port: SSH port number (default: 22)
        user: SSH username (default: 'rosbackup')

    Optional Fields:
        key_file: Path to SSH private key
        known_hosts_file: Path to known hosts file
        add_target_host_key: Whether to add target host key (default: True)
        keep_binary_backup: Keep binary backup on router (default: False)
        keep_plaintext_backup: Keep plaintext backup on router (default: False)
        encrypted: Enable backup encryption (default: False)
        enable_binary_backup: Enable binary backup creation (default: True)
        enable_plaintext_backup: Enable plaintext backup creation (default: True)
        backup_password: Target-specific backup password
        backup_retention_days: Target-specific retention period (default: 90)
        tmpfs: Target-specific tmpfs settings
    """
    host: str
    port: int
    user: str
    key_file: Optional[str]
    known_hosts_file: Optional[str]
    add_target_host_key: Optional[bool]
    keep_binary_backup: Optional[bool]
    keep_plaintext_backup: Optional[bool]
    encrypted: Optional[bool]
    enable_binary_backup: Optional[bool]
    enable_plaintext_backup: Optional[bool]
    backup_password: Optional[str]
    backup_retention_days: Optional[int]
    tmpfs: Optional[TargetTmpfsConfig]  # Target-specific tmpfs settings


class BackupManager:
    """
    Manages RouterOS backup operations.
    
    This class handles both binary (.backup) and plaintext (.rsc) backups,
    supporting features like encryption, parallel execution, retention management,
    and tmpfs-based temporary storage to reduce flash wear.
    
    Attributes:
        ssh_manager (SSHManager): Manages SSH connections to routers
        router_info_manager (RouterInfoManager): Handles router information retrieval
        tmpfs_manager (TmpfsManager): Manages temporary filesystem operations
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
        self.tmpfs_manager = TmpfsManager(ssh_manager, logger)
        self.logger = logger or LogManager().system

    def _clean_version_string(self, version: str) -> str:
        """
        Clean RouterOS version string by removing (stable) suffix.
        
        Args:
            version: The version string to clean
            
        Returns:
            str: The cleaned version string without the (stable) suffix
        """
        return re.sub(r'\s*\(stable\)\s*$', '', version)

    def _generate_backup_name(self, router_info: RouterInfo, timestamp: str, extension: str) -> str:
        """
        Generate backup filename from router info.

        Args:
            router_info: Router information dictionary
            timestamp: Timestamp string
            extension: File extension (e.g., 'backup' or 'rsc')

        Returns:
            Formatted backup filename
        """
        # Clean up version string
        ros_version = self._clean_version_string(router_info['ros_version'])
        # Generate name
        router_name = f"{router_info['identity']}_{ros_version}_{router_info['architecture_name']}"
        return f"{router_name}_{timestamp}.{extension}"

    def perform_binary_backup(
        self,
        ssh_client: paramiko.SSHClient,
        router_info: RouterInfo,
        backup_password: str,
        encrypted: bool,
        backup_dir: Path,
        timestamp: str,
        keep_binary_backup: bool,
        dry_run: bool = False,
        use_tmpfs: bool = False,
        tmpfs_config: Optional[TmpfsConfig] = None
    ) -> Tuple[bool, Optional[Path]]:
        """
        Perform binary backup of RouterOS device.

        Creates a binary backup file (.backup) that can be used for full system restore.
        The backup can be optionally encrypted using the provided password.

        If tmpfs is enabled and available, the backup will be created in RAM first
        and then moved to flash storage, reducing wear on the router's storage.

        Args:
            ssh_client: Connected SSH client to the router
            router_info: Dictionary containing router information
            backup_password: Password for backup encryption
            encrypted: Whether to encrypt the backup
            backup_dir: Directory to store the backup
            timestamp: Timestamp string (format: MMDDYYYY-HHMMSS)
            keep_binary_backup: Whether to keep backup file on router
            dry_run: If True, only simulate the backup
            use_tmpfs: Whether to attempt using tmpfs
            tmpfs_config: Optional tmpfs configuration

        Returns:
            A tuple containing:
            - bool: True if backup was successful
            - Optional[Path]: Path to the backup file if successful, None otherwise

        File Naming:
            The binary backup file follows the format:
            {identity}-{version}-{arch}-{timestamp}.backup
            Example: MYR1-7.16.2-x86_64-01042025-164736.backup

        Error Handling:
            - Verifies backup file creation on router
            - Checks file size after download
            - Handles SSH and SCP errors
            - Cleans up remote file if needed
            - Falls back to direct flash storage if tmpfs fails
        """
        try:
            # Generate backup filename
            backup_name = self._generate_backup_name(router_info, timestamp, 'backup')
            backup_path = backup_dir / backup_name
            
            # Determine where to create the backup
            target_path = backup_name  # Default to flash storage
            using_tmpfs = False
            if use_tmpfs and tmpfs_config and tmpfs_config.get('enabled', False):
                self.logger.debug(f"Initializing tmpfs with config: {tmpfs_config}")
                try:
                    if self.tmpfs_manager.check_router_support(ssh_client):
                        self.logger.debug("Router supports tmpfs")
                        has_memory, free_mb = self.tmpfs_manager.check_memory_availability(ssh_client)
                        if has_memory:
                            self.logger.debug(f"Memory available for tmpfs: {free_mb}MB")
                            size_mb = self.tmpfs_manager.calculate_tmpfs_size(free_mb)
                            if self.tmpfs_manager.setup_tmpfs(ssh_client, size_mb, tmpfs_config['mount_point']):
                                target_path = f"{tmpfs_config['mount_point']}/{backup_name}"
                                using_tmpfs = True
                                self.logger.debug(f"Will create backup in tmpfs at: {target_path}")
                            else:
                                self.logger.warning("Failed to setup tmpfs, falling back to flash storage")
                        else:
                            self.logger.warning(f"Not enough memory for tmpfs (free: {free_mb}MB), falling back to flash storage")
                    else:
                        self.logger.warning("Router does not support tmpfs, falling back to flash storage")
                except Exception as e:
                    self.logger.error(f"Tmpfs setup failed: {str(e)}, falling back to flash storage")

            # Create the backup
            if not dry_run:
                cmd = f"/system backup save name={target_path}"
                if encrypted:
                    cmd += f" password={backup_password}"
                self.logger.debug(f"Creating backup with command: {cmd}")
                try:
                    stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, cmd, timeout=60)  # 60 second timeout
                    if exit_status != 0:
                        self.logger.error(f"Failed to create backup: {stderr}")
                        return False, None
                except socket.timeout:
                    self.logger.error("Backup command timed out after 60 seconds")
                    return False, None
                except Exception as e:
                    self.logger.error(f"Failed to create backup: {str(e)}")
                    return False, None

                # Give RouterOS time to finish writing the backup
                time.sleep(1)

                # Verify backup file exists and check its size
                verify_cmd = f"/file print detail where name={target_path}"
                self.logger.debug(f"Verifying backup with command: {verify_cmd}")
                stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, verify_cmd)
                
                if exit_status != 0:
                    self.logger.error(f"Failed to verify backup: {stderr}")
                    return False, None
                    
                if target_path not in stdout:
                    # Try without the mount point prefix if it's a tmpfs path
                    if using_tmpfs:
                        verify_cmd = f"/file print detail where name={backup_name}"
                        self.logger.debug(f"Retrying verification with command: {verify_cmd}")
                        stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, verify_cmd)
                        
                        if exit_status != 0 or backup_name not in stdout:
                            self.logger.error("Backup file not found on router")
                            return False, None
                    else:
                        self.logger.error("Backup file not found on router")
                        return False, None
                    
                size_match = re.search(r'size=(\d+)', stdout.lower())
                if not size_match:
                    self.logger.error("Could not determine backup file size")
                    return False, None
                    
                size = int(size_match.group(1))
                if size == 0:
                    self.logger.error("Backup file is empty")
                    return False, None

                # Download directly from tmpfs if using it
                if using_tmpfs:
                    try:
                        self.logger.debug(f"Downloading backup file from tmpfs to {backup_path}")
                        with SCPClient(ssh_client.get_transport()) as scp:
                            scp.get(target_path, str(backup_path))
                        self.logger.debug(f"Backup file downloaded successfully (size: {backup_path.stat().st_size} bytes)")
                        
                        # If we want to keep the backup, move it from tmpfs to flash storage
                        if keep_binary_backup:
                            self.logger.debug(f"Moving backup from tmpfs to flash storage: {backup_name}")
                            try:
                                move_command = f'/file set [find name="{target_path}"] name="{backup_name}"'
                                stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, move_command)
                                if exit_status != 0:
                                    self.logger.warning(f"Failed to move backup to flash storage: {stderr}")
                            except Exception as e:
                                self.logger.warning(f"Failed to move backup to flash storage: {str(e)}")
                        else:
                            # Clean up the file in tmpfs
                            self.logger.debug(f"Cleaning up remote file in tmpfs: /file remove {target_path}")
                            stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, f"/file remove {target_path}")
                            if exit_status != 0:
                                self.logger.warning(f"Failed to clean up file in tmpfs: {stderr}")
                        
                        # Cleanup tmpfs
                        if not self.tmpfs_manager.cleanup_tmpfs(ssh_client, tmpfs_config['mount_point']):
                            self.logger.warning("Failed to cleanup tmpfs")
                            
                        return True, backup_path
                    except Exception as e:
                        self.logger.error(f"Failed to download backup from tmpfs: {str(e)}")
                        return False, None
                else:
                    # If not using tmpfs, verify and download from flash storage
                    verify_cmd = f"/file print detail where name={backup_name}"
                    self.logger.debug(f"Verifying backup in flash storage: {verify_cmd}")
                    stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, verify_cmd)
                    if exit_status != 0 or backup_name not in stdout:
                        self.logger.error("Backup file not found in flash storage")
                        return False, None

                    # Download the backup file
                    try:
                        self.logger.debug(f"Downloading backup file from flash to {backup_path}")
                        with SCPClient(ssh_client.get_transport()) as scp:
                            scp.get(backup_name, str(backup_path))
                        self.logger.debug(f"Backup file downloaded successfully (size: {backup_path.stat().st_size} bytes)")
                        
                        # Clean up the file in flash storage if not keeping it
                        if not keep_binary_backup:
                            self.logger.debug(f"Cleaning up remote file in flash: /file remove {backup_name}")
                            stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, f"/file remove {backup_name}")
                            if exit_status != 0:
                                self.logger.warning(f"Failed to remove remote file: {stderr}")
                            
                        return True, backup_path
                    except Exception as e:
                        self.logger.error(f"Failed to download backup from flash: {str(e)}")
                        return False, None

        except Exception as e:
            self.logger.error(f"Binary backup failed: {str(e)}")
            return False, None

    def perform_plaintext_backup(
        self,
        ssh_client: paramiko.SSHClient,
        router_info: RouterInfo,
        backup_dir: Path,
        timestamp: str,
        keep_plaintext_backup: bool,
        dry_run: bool = False,
        use_tmpfs: bool = False,  # This will be ignored
        tmpfs_config: Optional[TmpfsConfig] = None  # This will be ignored
    ) -> Tuple[bool, Optional[Path]]:
        """
        Perform plaintext backup of RouterOS device.

        Creates a plaintext backup file (.rsc) containing router configuration.
        Plaintext backups are streamed directly to flash storage and never use tmpfs.

        Args:
            ssh_client: Connected SSH client to the router
            router_info: Dictionary containing router information
            backup_dir: Directory to store the backup
            timestamp: Timestamp string (format: MMDDYYYY-HHMMSS)
            keep_plaintext_backup: Whether to keep backup file on router
            dry_run: If True, only simulate the backup
            use_tmpfs: Ignored - plaintext backups never use tmpfs
            tmpfs_config: Ignored - plaintext backups never use tmpfs

        Returns:
            A tuple containing:
            - bool: True if backup was successful
            - Optional[Path]: Path to the backup file if successful, None otherwise
        """
        try:
            # Generate backup filename
            backup_name = self._generate_backup_name(router_info, timestamp, 'rsc')
            backup_path = backup_dir / backup_name

            # For plaintext backups, we want to stream directly to the client
            # If we need to keep the backup on the router, use /export file=
            if keep_plaintext_backup:
                cmd = f"/export file={backup_name}"
                self.logger.debug(f"Creating export with command: {cmd}")
                stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, cmd)
                if exit_status != 0:
                    self.logger.error(f"Failed to create export: {stderr}")
                    return False, None
                    
                # Wait for the file to be written
                time.sleep(1)
                
                # Verify the file exists and download it
                verify_cmd = f"/file print detail where name={backup_name}"
                self.logger.debug(f"Verifying export with command: {verify_cmd}")
                stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, verify_cmd)
                
                if exit_status != 0 or backup_name not in stdout:
                    self.logger.error("Export file not found on router")
                    return False, None
                    
                # Download the file
                try:
                    self.logger.debug(f"Downloading export file to {backup_path}")
                    with SCPClient(ssh_client.get_transport()) as scp:
                        scp.get(backup_name, str(backup_path))
                except Exception as e:
                    self.logger.error(f"Failed to download export: {str(e)}")
                    return False, None
            else:
                # Stream directly without saving on router
                cmd = "/export"
                self.logger.debug(f"Creating export with command: {cmd}")
                
                # Execute the export command and capture output directly
                stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=60)  # 60 second timeout
                
                if not dry_run:
                    try:
                        self.logger.debug(f"Streaming export directly to {backup_path}")
                        with open(backup_path, 'wb') as f:
                            # Stream the export data directly to local file
                            for line in stdout:
                                f.write(line.encode('utf-8'))
                    except socket.timeout:
                        self.logger.error("Export command timed out after 60 seconds")
                        return False, None
                    except Exception as e:
                        self.logger.error(f"Failed to download export: {str(e)}")
                        return False, None

            # Verify local file exists and is not empty
            if not backup_path.exists():
                self.logger.error("Local export file was not created")
                return False, None
                
            local_size = backup_path.stat().st_size
            if local_size == 0:
                self.logger.error("Local export file is empty")
                return False, None
                
            self.logger.debug(f"Export file downloaded successfully (size: {local_size} bytes)")
            return True, backup_path

        except Exception as e:
            self.logger.error(f"Plaintext backup failed: {str(e)}")
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

        File Format:
            The info file contains sections for different types of information:
            - System Information
            - Hardware Information
            - System Resources
            - System Status
            - License Information
            - Time Settings
            - Overall Statistics
        """
        if dry_run:
            return True

        try:
            with open(info_file_path, 'w') as f:
                # System Information
                f.write("System Information\n")
                f.write("=================\n")
                f.write(f"Name: {router_info['identity']}\n")
                f.write(f"Version: {router_info['ros_version']}\n")
                f.write(f"License: Level {router_info['license']}\n")
                f.write(f"System ID: {router_info['system_id']}\n")
                f.write(f"Uptime: {router_info['uptime']}\n\n")

                # Hardware Information
                f.write("Hardware Information\n")
                f.write("===================\n")
                f.write(f"Model: {router_info['model']}\n")
                f.write(f"Arch: {router_info['architecture_name']}\n")
                f.write(f"CPU: {router_info['cpu_name']}\n")
                f.write(f"CPU Count: {router_info['cpu_count']}\n")
                f.write(f"CPU Frequency: {router_info['cpu_frequency']}\n\n")

                # System Resources
                f.write("System Resources\n")
                f.write("===============\n")
                f.write(f"Total Memory: {router_info['total_memory']}\n")
                f.write(f"Free Memory: {router_info['free_memory']}\n")
                f.write(f"Total HDD Space: {router_info['total_hdd_space']}\n")
                f.write(f"Free HDD Space: {router_info['free_hdd_space']}\n")
                f.write(f"Write Sectors Since Reboot: {router_info['write_sect_since_reboot']}\n")
                f.write(f"Write Sectors Total: {router_info['write_sect_total']}\n")

                # Time Settings
                f.write("\nTime Settings\n")
                f.write("=============\n")
                f.write(f"Time: {router_info['time']}\n")
                f.write(f"Date: {router_info['date']}\n")
                f.write(f"Time Zone: {router_info['time_zone_name']}\n")
                f.write(f"GMT Offset: {router_info['gmt_offset']}\n")
                f.write(f"DST Active: {router_info['dst_active']}\n")
                f.write(f"Auto-detect Time Zone: {router_info['time_zone_autodetect']}\n")

                # Overall Statistics
                f.write("\nOverall Statistics\n")
                f.write("=================\n")

                f.write("\nIP Addressing\n")
                f.write("-------------\n")
                f.write(f"IPv4 Addresses: {router_info['ipv4_addresses']}\n")
                f.write(f"IPv6 Addresses: {router_info['ipv6_addresses']}\n")
                f.write(f"IPv4 Pools: {router_info['ipv4_pools']}\n")
                f.write(f"IPv6 Pools: {router_info['ipv6_pools']}\n")

                f.write("\nInterfaces\n")
                f.write("----------\n")
                f.write(f"Ethernet Interfaces: {router_info['ethernet_interfaces']}\n")
                f.write(f"VLAN Interfaces: {router_info['vlan_interfaces']}\n")
                f.write(f"Bridge Interfaces: {router_info['bridge_interfaces']}\n")
                f.write(f"Bond Interfaces: {router_info['bond_interfaces']}\n")
                f.write(f"PPP Sessions: {router_info['ppp_active_sessions']}\n")

                f.write("\nFirewall\n")
                f.write("---------\n")
                f.write(f"IPv4 Filter Rules: {router_info['ipv4_fw_filter']}\n")
                f.write(f"IPv6 Filter Rules: {router_info['ipv6_fw_filter']}\n")
                f.write(f"IPv4 Raw Rules: {router_info['ipv4_fw_raw']}\n")
                f.write(f"IPv6 Raw Rules: {router_info['ipv6_fw_raw']}\n")
                f.write(f"IPv4 NAT Rules: {router_info['ipv4_fw_nat']}\n")
                f.write(f"IPv6 NAT Rules: {router_info['ipv6_fw_nat']}\n")
                f.write(f"IPv4 Mangle Rules: {router_info['ipv4_fw_mangle']}\n")
                f.write(f"IPv6 Mangle Rules: {router_info['ipv6_fw_mangle']}\n")
                f.write(f"IPv4 Address List Entries: {router_info['ipv4_fw_address_list']}\n")
                f.write(f"IPv6 Address List Entries: {router_info['ipv6_fw_address_list']}\n")
                f.write(f"IPv4 Active Connections: {router_info['ipv4_fw_connections']}\n")
                f.write(f"IPv6 Active Connections: {router_info['ipv6_fw_connections']}\n")

                f.write("\nDHCP Services\n")
                f.write("-------------\n")
                f.write(f"IPv4 DHCP Servers: {router_info['ipv4_dhcp_servers']}\n")
                f.write(f"IPv6 DHCP Servers: {router_info['ipv6_dhcp_servers']}\n")
                f.write(f"IPv4 DHCP Clients: {router_info['ipv4_dhcp_clients']}\n")
                f.write(f"IPv6 DHCP Clients: {router_info['ipv6_dhcp_clients']}\n")
                f.write(f"IPv4 DHCP Relays: {router_info['ipv4_dhcp_relays']}\n")
                f.write(f"IPv6 DHCP Relays: {router_info['ipv6_dhcp_relays']}\n")

                f.write("\nQoS and ARP/ND\n")
                f.write("-------------\n")
                f.write(f"Queue Tree Items: {router_info['queue_tree_items']}\n")
                f.write(f"IPv4 ARP Failed: {router_info['ipv4_arp_failed']}\n")
                f.write(f"IPv4 ARP Permanent: {router_info['ipv4_arp_permanent']}\n")
                f.write(f"IPv4 ARP Reachable: {router_info['ipv4_arp_reachable']}\n")
                f.write(f"IPv6 Neighbors: {router_info['ipv6_neighbors']}\n")

                return True
        except Exception as e:
            self.logger.error(f"Failed to save info file: {str(e)}")
            return False

def backup_parallel(targets: Dict[str, TargetConfig], config: BackupConfig,
                   backup_password: str, backup_path: str,
                   max_workers: int = 5, dry_run: bool = False,
                   progress_callback: Optional[Callable[[str, int], None]] = None,
                   no_tmpfs: bool = False) -> int:
    """
    Perform parallel backup of multiple routers.

    Args:
        targets: List of target configurations
        config: Global configuration
        backup_password: Password for encrypted backups
        backup_path: Path to store backups
        max_workers: Maximum number of parallel workers
        dry_run: If True, only simulate backup
        progress_callback: Optional callback for progress updates
        no_tmpfs: Disable tmpfs usage

    Returns:
        int: Number of successful backups

    Error Handling:
        - Handles SSH connection failures for individual targets
        - Manages worker pool lifecycle
        - Aggregates and reports individual backup failures
        - Ensures proper cleanup of resources on failure
    """
    success_count = 0
    futures = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for i, target in enumerate(targets):
            future = executor.submit(
                backup_router,
                target=target,
                config=config,
                backup_password=backup_password,
                backup_path=backup_path,
                dry_run=dry_run,
                progress_callback=progress_callback,
                no_tmpfs=no_tmpfs
            )
            futures.append(future)

        # Wait for all futures to complete
        for future in concurrent.futures.as_completed(futures):
            try:
                if future.result():
                    success_count += 1
            except Exception as e:
                logger.error(f"Backup failed: {str(e)}")

    return success_count

def backup_router(target: TargetConfig, config: BackupConfig,
                 backup_password: str, backup_path: str,
                 dry_run: bool = False,
                 progress_callback: Optional[Callable[[str, str], None]] = None,
                 no_tmpfs: bool = False) -> bool:
    """
    Perform backup of a single router.

    Args:
        target: Target configuration
        config: Global configuration
        backup_password: Password for encrypted backups
        backup_path: Path to store backups
        dry_run: If True, only simulate backup
        progress_callback: Optional callback for progress updates
        no_tmpfs: Disable tmpfs usage

    Returns:
        True if backup was successful

    The backup process follows these steps:
    1. Connect to router via SSH
    2. Gather router information
    3. Create backup directory structure
    4. Perform binary backup (if enabled)
    5. Perform plaintext backup (if enabled)
    6. Save router information file
    7. Clean up temporary files

    Tmpfs Usage:
    - If enabled globally or per-target, attempts to use tmpfs for backups
    - Falls back to direct flash storage if tmpfs is not available or fails
    - Target-specific tmpfs settings override global settings
    """
    try:
        # Create backup directory
        backup_dir = Path(backup_path)
        if not dry_run:
            backup_dir.mkdir(parents=True, exist_ok=True)

        # Get target-specific settings
        enable_binary = getattr(target, 'enable_binary_backup', True)
        enable_plaintext = getattr(target, 'enable_plaintext_backup', True)
        keep_binary = getattr(target, 'keep_binary_backup', False)
        keep_plaintext = getattr(target, 'keep_plaintext_backup', False)
        encrypted = getattr(target, 'encrypted', False)

        # Get tmpfs configuration 
        global_tmpfs = config.tmpfs if hasattr(config, 'tmpfs') else {}
        target_tmpfs = getattr(target, 'tmpfs', {}) or {}
        
        # For binary backups
        use_tmpfs = not no_tmpfs and target_tmpfs.get('enabled', global_tmpfs.get('enabled', True))
        tmpfs_config = {
            'enabled': use_tmpfs,
            'fallback_enabled': target_tmpfs.get('fallback_enabled', global_tmpfs.get('fallback_enabled', True)),
            'size_auto': target_tmpfs.get('size_auto', global_tmpfs.get('size_auto', True)),
            'size_mb': target_tmpfs.get('size_mb', global_tmpfs.get('size_mb', 50)),
            'min_size_mb': target_tmpfs.get('min_size_mb', global_tmpfs.get('min_size_mb', 1)),
            'max_size_mb': target_tmpfs.get('max_size_mb', global_tmpfs.get('max_size_mb', 50)),
            'mount_point': target_tmpfs.get('mount_point', global_tmpfs.get('mount_point', 'rosbackup'))
        } if use_tmpfs else None

        # Explicitly disable tmpfs for plaintext backups
        plaintext_tmpfs_config = None  # Never use tmpfs for plaintext

        # Debug logging for tmpfs configuration
        logger = LogManager().get_logger(target.host)
        logger.debug("Tmpfs Configuration:")
        logger.debug(f"Global tmpfs config: {global_tmpfs}")
        logger.debug(f"Target tmpfs config: {target_tmpfs}")
        logger.debug(f"Use tmpfs: {use_tmpfs}")
        logger.debug(f"Final tmpfs config: {tmpfs_config}")

        # Initialize managers
        ssh_manager = SSHManager(target)
        router_info_manager = RouterInfoManager(ssh_manager)
        backup_manager = BackupManager(ssh_manager, router_info_manager, logger)

        # Connect and get router info
        with ssh_manager.get_client() as ssh_client:
            # Get router information
            router_info = router_info_manager.get_router_info(ssh_client)
            if not router_info:
                raise Exception("Failed to get router information")

            # Generate timestamp
            timestamp = get_timestamp()

            # Create target-specific directory
            target_dir = backup_dir / router_info['identity']
            if not dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)

            # Save router information
            if not dry_run:
                info_file = target_dir / f"{router_info['identity']}_{timestamp}.info"
                backup_manager.save_info_file(router_info, info_file)

            # Perform binary backup if enabled
            if enable_binary:
                binary_success, binary_file = backup_manager.perform_binary_backup(
                    ssh_client=ssh_client,
                    router_info=router_info,
                    backup_password=getattr(target, 'backup_password', backup_password),
                    encrypted=encrypted,
                    backup_dir=target_dir,
                    timestamp=timestamp,
                    keep_binary_backup=keep_binary,
                    dry_run=dry_run,
                    use_tmpfs=use_tmpfs,
                    tmpfs_config=tmpfs_config
                )
                if not binary_success:
                    raise Exception("Binary backup failed")

            # Perform plaintext backup if enabled
            if enable_plaintext:
                plaintext_success, plaintext_file = backup_manager.perform_plaintext_backup(
                    ssh_client=ssh_client,
                    router_info=router_info,
                    backup_dir=target_dir,
                    timestamp=timestamp,
                    keep_plaintext_backup=keep_plaintext,
                    dry_run=dry_run,
                    use_tmpfs=False,  # Never use tmpfs for plaintext
                    tmpfs_config=plaintext_tmpfs_config  # Always None for plaintext
                )
                if not plaintext_success:
                    raise Exception("Plaintext backup failed")

            if progress_callback:
                progress_callback(target.host, "Backup completed successfully")
            return True

    except Exception as e:
        if progress_callback:
            progress_callback(target.host, f"Backup failed: {str(e)}")
        return False
