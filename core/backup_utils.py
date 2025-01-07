"""
RouterOS backup operations management.

This module handles both binary and plaintext backup operations for RouterOS devices.
It supports encrypted backups, parallel execution, and various backup retention options.
"""

import paramiko
from pathlib import Path
from typing import Dict, Optional, Tuple, TypedDict, Any, Callable
import logging
import os
import re
from scp import SCPClient
import time
from .ssh_utils import SSHManager
from .router_utils import RouterInfoManager
from .logging_utils import LogManager
import concurrent.futures
import datetime

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
        board_name: Board name
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
            timestamp: Timestamp string (format: MMDDYYYY-HHMMSS)
            keep_binary_backup: Whether to keep backup file on router
            dry_run: If True, only simulate the backup

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
        """
        if dry_run:
            self.logger.debug("[DRY RUN] Would perform binary backup")
            return True, None

        # Generate backup file name
        backup_name = self._generate_backup_name(router_info, timestamp, 'backup')
        remote_path = backup_name
        local_path = backup_dir / backup_name

        try:
            # Create backup command
            backup_cmd = "/system backup save"
            if encrypted:
                backup_cmd += f" password=\"{backup_password}\""
            backup_cmd += f" name=\"{remote_path}\""

            # Execute backup command
            stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, backup_cmd)
            self.logger.debug(f"Backup command: {backup_cmd}")
            self.logger.debug(f"Stdout: {stdout}")
            self.logger.debug(f"Stderr: {stderr}")
            if stderr or exit_status != 0:
                self.logger.error(f"Error creating backup: {stderr}")
                return False, None

            # Wait for backup to complete and verify file
            time.sleep(2)  # Give RouterOS time to create the file
            
            self.logger.debug(f"Checking for backup file: {remote_path}")
            # Use /file print to check for file existence
            check_cmd = f"/file print where name=\"{remote_path}\""
            stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, check_cmd)
            self.logger.debug(f"File check command: {check_cmd}")
            self.logger.debug(f"File check output: {stdout}")
            if not stdout or "no such item" in stdout.lower() or exit_status != 0:
                self.logger.error("Backup file was not created on router")
                return False, None

            self.logger.info(f"Successfully created backup file {os.path.basename(remote_path)} on router")

            # Download the backup file
            try:
                with SCPClient(ssh_client.get_transport()) as scp:
                    scp.get(remote_path, str(local_path))
                self.logger.info(f"Downloaded {os.path.basename(remote_path)}")
            except Exception as e:
                self.logger.error(f"Failed to download backup file: {str(e)}")
                return False, None

            # Remove the remote backup file
            if not keep_binary_backup:
                rm_cmd = f"/file remove \"{remote_path}\""
                stdout, stderr, exit_status = self.ssh_manager.execute_command(ssh_client, rm_cmd)
                if not stderr and exit_status == 0:
                    self.logger.info(f"Removed remote {os.path.basename(remote_path)}")
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

        Export Parameters:
            - terse: Produces single-line commands without wrapping, ideal for grep and automated processing
            - show-sensitive: Includes sensitive data like passwords and private keys

        Args:
            ssh_client: Connected SSH client to the router
            router_info: Dictionary containing router information
            backup_dir: Directory to store the backup
            timestamp: Timestamp string (format: MMDDYYYY-HHMMSS)
            keep_plaintext_backup: Whether to keep export on router
            dry_run: If True, only simulate the backup

        Returns:
            A tuple containing:
            - bool: True if backup was successful
            - Optional[Path]: Path to the backup file if successful, None otherwise

        File Naming:
            The plaintext export file follows the format:
            {identity}_{version}_{arch}_{timestamp}.rsc
            Example: MYR1_7.16.2_x86_64_01042025-164736.rsc

        Error Handling:
            - Verifies export command output
            - Handles SSH connection errors
            - Validates file writing operations
            - Manages router-side file operations
        """

        if dry_run:
            self.logger.debug("[DRY RUN] Would perform plaintext backup")
            return True, None

        # Export configuration to file
        try:
            # Execute export command and get output directly
            stdin, stdout, stderr = ssh_client.exec_command('/export terse show-sensitive')
            stdout = stdout.read().decode()
            stderr = stderr.read().decode()

            if stderr:
                self.logger.error(f"Export command failed: {stderr.strip()}")
                return False, None

            if not stdout:
                self.logger.error("Export command produced no output")
                return False, None

            # Generate backup file name
            backup_name = self._generate_backup_name(router_info, timestamp, 'rsc')
            backup_path = backup_dir / backup_name

            # Save the export on the router first if requested
            if keep_plaintext_backup:
                try:
                    save_command = f'/export terse show-sensitive file={backup_name}'
                    stdin, stdout2, stderr = ssh_client.exec_command(save_command)
                    stdout2 = stdout2.read().decode()
                    stderr = stderr.read().decode()
                    if stderr:
                        self.logger.error(f"Failed to save export on router: {stderr.strip()}")
                        return False, None
                    self.logger.info(f"Plaintext export saved on router as {backup_name}")
                except Exception as e:
                    self.logger.error(f"Error saving export on router: {str(e)}")
                    return False, None

            # Save local backup
            backup_path.write_text(stdout)
            self.logger.info(f"Plaintext backup saved as {backup_name}")

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
            self.logger.debug(f"[DRY RUN] Would save router info to {info_file_path}")
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
                   progress_callback: Optional[Callable[[str, int], None]] = None) -> int:
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
                progress_callback=progress_callback
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
                 progress_callback: Optional[Callable[[str, str], None]] = None) -> bool:
    """
    Perform backup of a single router.

    Args:
        target: Target configuration
        config: Global configuration
        backup_password: Password for encrypted backups
        backup_path: Path to store backups
        dry_run: If True, only simulate backup
        progress_callback: Optional callback for progress updates

    Returns:
        True if backup was successful
    """
    target_name = target['name']
    logger = LogManager().get_logger('BACKUP', target_name)

    try:
        # Initialize managers
        ssh_manager = SSHManager(config['ssh'], target_name)
        router_info_manager = RouterInfoManager(ssh_manager, logger)
        backup_manager = BackupManager(ssh_manager, router_info_manager, logger)

        # Update progress
        if progress_callback:
            progress_callback(target_name, "Starting")

        # Create SSH client
        ssh_client = ssh_manager.get_client(
            target_name,
            target['host'],
            target['port'],
            target['user'],
            target.get('key_file'),
            target.get('known_hosts_file'),
            target.get('add_host_key', True)
        )

        if not ssh_client:
            if progress_callback:
                progress_callback(target_name, "Failed")
            return False

        try:
            # Update progress
            if progress_callback:
                progress_callback(target_name, "Running")

            # Get router info
            router_info = router_info_manager.get_router_info(ssh_client)
            if not router_info:
                if progress_callback:
                    progress_callback(target_name, "Failed")
                return False

            # Create backup directory
            backup_dir = Path(backup_path) / target_name
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Get timestamp for filenames
            timestamp = datetime.datetime.now().strftime("%m%d%Y-%H%M%S")

            # Perform binary backup if enabled
            if target.get('enable_binary_backup', True):
                if progress_callback:
                    progress_callback(target_name, "Downloading")
                success, backup_path = backup_manager.perform_binary_backup(
                    ssh_client,
                    router_info,
                    backup_password,
                    target.get('encrypted', False),
                    backup_dir,
                    timestamp,
                    target.get('keep_binary_backup', False),
                    dry_run
                )
                if not success:
                    if progress_callback:
                        progress_callback(target_name, "Failed")
                    return False
                
                if progress_callback:
                    progress_callback(target_name, "Finished")
                
            else:
                if progress_callback:
                    progress_callback(target_name, "Finished")

            return True

        finally:
            ssh_client.close()

    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        if progress_callback:
            progress_callback(target_name, "Failed")
        return False
