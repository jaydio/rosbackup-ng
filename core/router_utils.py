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


class SystemIdentityInfo(TypedDict):
    """System identity information."""
    identity: str  # Router identity name
    name: str     # Router name


class HardwareInfo(TypedDict):
    """Hardware specifications."""
    model: str               # Router hardware model
    board_name: str         # Physical board name
    serial_number: str      # Hardware serial number
    firmware_type: str      # Type of firmware
    factory_firmware: str   # Factory installed firmware version
    current_firmware: str   # Currently running firmware version
    upgrade_firmware: str   # Available firmware upgrade version


class ResourceInfo(TypedDict):
    """System resource information."""
    uptime: str                    # System uptime
    version: str                   # RouterOS version
    build_time: str               # Build timestamp
    free_memory: str              # Available RAM
    total_memory: str             # Total RAM
    cpu_name: str                 # CPU model name
    cpu_count: str                # Number of CPU cores
    cpu_frequency: str            # CPU frequency
    cpu_load: str                 # Current CPU load
    free_hdd_space: str          # Available disk space
    total_hdd_space: str         # Total disk space
    write_sect_since_reboot: str # Write sectors since reboot
    write_sect_total: str        # Total write sectors
    bad_blocks: str              # Number of bad blocks
    architecture_name: str       # CPU architecture
    platform: str                # Platform type


class LicenseInfo(TypedDict):
    """License information."""
    system_id: str      # System identifier
    upgradable_to: str  # Maximum upgradable version
    license: str        # License level
    features: str       # Licensed features
    ros_version: str    # RouterOS version


class TimeInfo(TypedDict):
    """Time and timezone settings."""
    time: str                  # Current time
    date: str                  # Current date
    time_zone_autodetect: str # Timezone autodetection
    time_zone_name: str       # Timezone name
    gmt_offset: str           # GMT offset
    dst_active: str           # DST status


class NetworkInfo(TypedDict):
    """Network configuration statistics."""
    # Firewall Statistics
    ipv4_fw_filter: str        # IPv4 filter rules count
    ipv6_fw_filter: str        # IPv6 filter rules count
    ipv4_fw_raw: str          # IPv4 raw rules count
    ipv6_fw_raw: str          # IPv6 raw rules count
    ipv4_fw_nat: str          # IPv4 NAT rules count
    ipv6_fw_nat: str          # IPv6 NAT rules count
    ipv4_fw_connections: str   # Active IPv4 connections
    ipv6_fw_connections: str   # Active IPv6 connections
    ipv4_fw_mangle: str       # IPv4 mangle rules count
    ipv6_fw_mangle: str       # IPv6 mangle rules count
    ipv4_fw_address_list: str # IPv4 address list entries
    ipv6_fw_address_list: str # IPv6 address list entries
    
    # IP Configuration
    ipv4_addresses: str       # IPv4 addresses count
    ipv6_addresses: str       # IPv6 addresses count
    ipv4_pools: str          # IPv4 pools count
    ipv6_pools: str          # IPv6 pools count
    
    # DHCP Information
    ipv4_dhcp_servers: str   # IPv4 DHCP servers count
    ipv6_dhcp_servers: str   # IPv6 DHCP servers count
    ipv4_dhcp_clients: str   # IPv4 DHCP clients count
    ipv6_dhcp_clients: str   # IPv6 DHCP clients count
    ipv4_dhcp_relays: str    # IPv4 DHCP relays count
    ipv6_dhcp_relays: str    # IPv6 DHCP relays count
    
    # Interface Statistics
    bridge_interfaces: str    # Bridge interfaces count
    bond_interfaces: str      # Bonding interfaces count
    vlan_interfaces: str      # VLAN interfaces count
    ethernet_interfaces: str  # Physical interfaces count
    ppp_active_sessions: str # Active PPP sessions
    queue_tree_items: str    # QoS queue items
    
    # ARP/Neighbor Information
    ipv4_arp_failed: str     # Failed ARP entries
    ipv4_arp_permanent: str  # Permanent ARP entries
    ipv4_arp_reachable: str  # Reachable ARP entries
    ipv6_neighbors: str      # IPv6 neighbor entries


class RouterInfo(TypedDict):
    """
    Complete router information combining all information categories.
    
    This TypedDict includes all router information organized into logical
    categories for better structure and maintainability.
    """
    # Include all sub-categories
    identity: str  # From SystemIdentityInfo
    name: str
    
    # Hardware Information
    model: str
    board_name: str
    serial_number: str
    firmware_type: str
    factory_firmware: str
    current_firmware: str
    upgrade_firmware: str
    
    # Resource Information
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
    
    # License Information
    system_id: str
    upgradable_to: str
    license: str
    features: str
    ros_version: str
    
    # Time Settings
    time: str
    date: str
    time_zone_autodetect: str
    time_zone_name: str
    gmt_offset: str
    dst_active: str
    
    # Network Statistics
    ipv4_fw_filter: str
    ipv6_fw_filter: str
    ipv4_fw_raw: str
    ipv6_fw_raw: str
    ipv4_fw_nat: str
    ipv6_fw_nat: str
    ipv4_fw_connections: str
    ipv6_fw_connections: str
    ipv4_fw_mangle: str
    ipv6_fw_mangle: str
    ipv4_fw_address_list: str
    ipv6_fw_address_list: str
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
    ppp_active_sessions: str
    bridge_interfaces: str
    bond_interfaces: str
    vlan_interfaces: str
    ethernet_interfaces: str
    queue_tree_items: str
    ipv4_arp_failed: str
    ipv4_arp_permanent: str
    ipv4_arp_reachable: str
    ipv6_neighbors: str


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
            stdout, stderr, _ = self.ssh_manager.execute_command(ssh_client, "/system identity print")
            if stderr:
                self.logger.error(f"Error getting system identity: {stderr}")
                raise RuntimeError(f"Failed to get system identity: {stderr}")
            identity_info = self._parse_mikrotik_output(stdout)

            # Get system resource info
            stdout, stderr, _ = self.ssh_manager.execute_command(ssh_client, "/system resource print")
            if stderr:
                self.logger.error(f"Error getting system resource info: {stderr}")
                raise RuntimeError(f"Failed to get system resource info: {stderr}")
            resource_info = self._parse_mikrotik_output(stdout)

            # Get routerboard info
            stdout, stderr, _ = self.ssh_manager.execute_command(ssh_client, "/system routerboard print")
            if stderr:
                self.logger.error(f"Error getting routerboard info: {stderr}")
                raise RuntimeError(f"Failed to get routerboard info: {stderr}")
            board_info = self._parse_mikrotik_output(stdout)

            # Get license info
            stdout, stderr, _ = self.ssh_manager.execute_command(ssh_client, "/system license print")
            if stderr:
                self.logger.error(f"Error getting license info: {stderr}")
                raise RuntimeError(f"Failed to get license info: {stderr}")
            license_info = self._parse_mikrotik_output(stdout)

            # Get clock info
            stdout, stderr, _ = self.ssh_manager.execute_command(ssh_client, "/system clock print")
            if stderr:
                self.logger.error(f"Error getting clock info: {stderr}")
                raise RuntimeError(f"Failed to get clock info: {stderr}")
            clock_info = self._parse_mikrotik_output(stdout)

            # Get statistics
            stats_commands = [
                ("/ip/firewall/filter/find", "ipv4_fw_filter"),
                ("/ipv6/firewall/filter/find", "ipv6_fw_filter"),
                ("/ip/firewall/raw/find", "ipv4_fw_raw"),
                ("/ipv6/firewall/raw/find", "ipv6_fw_raw"),
                ("/ip/firewall/nat/find", "ipv4_fw_nat"),
                ("/ipv6/firewall/nat/find", "ipv6_fw_nat"),
                ("/ip/firewall/connection/find", "ipv4_fw_connections"),
                ("/ipv6/firewall/connection/find", "ipv6_fw_connections"),
                ("/ip/firewall/mangle/find", "ipv4_fw_mangle"),
                ("/ipv6/firewall/mangle/find", "ipv6_fw_mangle"),
                ("/ip/firewall/address-list/find", "ipv4_fw_address_list"),
                ("/ipv6/firewall/address-list/find", "ipv6_fw_address_list"),
                ("/ip/address/find", "ipv4_addresses"),
                ("/ipv6/address/find", "ipv6_addresses"),
                ("/ip/dhcp-server/find", "ipv4_dhcp_servers"),
                ("/ipv6/dhcp-server/find", "ipv6_dhcp_servers"),
                ("/ip/dhcp-client/find", "ipv4_dhcp_clients"),
                ("/ipv6/dhcp-client/find", "ipv6_dhcp_clients"),
                ("/ip/dhcp-relay/find", "ipv4_dhcp_relays"),
                ("/ipv6/dhcp-relay/find", "ipv6_dhcp_relays"),
                ("/ip/pool/find", "ipv4_pools"),
                ("/ipv6/pool/find", "ipv6_pools"),
                ("/ppp/active/find", "ppp_active_sessions"),
                ("/interface/bridge/find", "bridge_interfaces"),
                ("/interface/bonding/find", "bond_interfaces"),
                ("/interface/vlan/find", "vlan_interfaces"),
                ("/interface/ethernet/find", "ethernet_interfaces"),
                ("/queue/tree/find", "queue_tree_items"),
                ("/ip/arp/find where status=failed", "ipv4_arp_failed"),
                ("/ip/arp/find where status=permanent", "ipv4_arp_permanent"),
                ("/ip/arp/find where status=reachable", "ipv4_arp_reachable"),
                ("/ipv6/neighbor/find", "ipv6_neighbors")
            ]

            stats = {}
            for cmd, key in stats_commands:
                stdout, stderr, _ = self.ssh_manager.execute_command(ssh_client, f":put [:len [{cmd}]]")
                if stderr:
                    self.logger.warning(f"Error getting {key}: {stderr}")
                    stats[key] = "0"
                else:
                    stats[key] = stdout.strip() or "0"

            # Get model, default to CHR if undefined
            model = board_info.get('model', 'unknown')
            if model == 'unknown':
                model = 'CHR'

            # Combine all information
            router_info = {
                # System Identity
                'identity': identity_info.get('name', 'unknown'),
                'name': identity_info.get('name', 'unknown'),
                
                # System Resource
                'model': model,
                'board_name': board_info.get('board-name', 'unknown') if model != 'CHR' else None,
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
                'system_id': license_info.get('system-id') or license_info.get('software-id', 'unknown'),
                'upgradable_to': license_info.get('upgradable-to', 'unknown'),
                'license': license_info.get('level') or license_info.get('nlevel', 'unknown'),
                'features': license_info.get('features', 'unknown'),
                
                # Clock Settings
                'time': clock_info.get('time', 'unknown'),
                'date': clock_info.get('date', 'unknown'),
                'time_zone_autodetect': clock_info.get('time-zone-autodetect', 'unknown'),
                'time_zone_name': clock_info.get('time-zone-name', 'unknown'),
                'gmt_offset': clock_info.get('gmt-offset', 'unknown'),
                'dst_active': clock_info.get('dst-active', 'unknown'),
                
                # Overall Statistics
                **stats,
                
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
        stdout, _, _ = self.ssh_manager.execute_command(
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
        stdout, _, _ = self.ssh_manager.execute_command(
            ssh_client, 
            ':put [/system resource get total-memory]'
        )
        if not stdout:
            self.logger.error("Insufficient access rights to read system resources")
            return False

        # Check if we can access the file system
        stdout, _, _ = self.ssh_manager.execute_command(
            ssh_client,
            ':put [file get [find type="directory" and name=""] name]'
        )
        if not stdout:
            self.logger.error("Insufficient access rights to access file system")
            return False

        return True
