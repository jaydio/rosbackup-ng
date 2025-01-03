"""
SSH utility functions for RouterOS backup operations.

This module provides secure SSH connection management for RouterOS devices,
handling authentication, command execution, and file operations with proper
error handling and logging.
"""

import paramiko
import logging
from pathlib import Path
from typing import Optional, Dict, Tuple, TypedDict, Union, Literal
import socket


class SSHConfig(TypedDict):
    """SSH configuration dictionary type definition."""
    timeout: int
    auth_timeout: int
    known_hosts_file: Optional[str]
    add_target_host_key: bool
    args: Dict[str, Union[bool, int, Dict[str, list]]]  # Updated to support more complex args


class CommandResult(TypedDict):
    """Command execution result type definition."""
    stdout: Optional[str]
    stderr: Optional[str]
    success: bool
    error_message: Optional[str]


class SSHManager:
    """
    Manages SSH connections to RouterOS devices.
    
    This class handles SSH connection lifecycle, command execution,
    and file operations with proper error handling and security measures.
    
    Attributes:
        ssh_args (SSHConfig): SSH configuration parameters
        logger (logging.Logger): Logger instance for this class
    """

    def __init__(self, ssh_args: SSHConfig, target_name: str = None) -> None:
        """
        Initialize SSH manager with configuration.

        Args:
            ssh_args: SSH configuration including:
                - timeout: Connection timeout in seconds
            target_name: Name of the target router for logging
        """
        self.ssh_args = ssh_args
        self.client = None
        if target_name:
            self.logger = logging.LoggerAdapter(logging.getLogger(__name__), {'target': target_name})
        else:
            self.logger = logging.getLogger(__name__)

    def create_client(
        self, 
        host: str,
        port: int,
        username: str,
        key_path: str
    ) -> Optional[paramiko.SSHClient]:
        """
        Create and return an SSH client connected to the specified host.

        Establishes a secure SSH connection with proper error handling for:
        - Authentication failures
        - Host key verification
        - Connection timeouts
        - Encrypted keys
        - Network issues

        Args:
            host: Target router's hostname or IP address
            port: SSH port number (usually 22)
            username: SSH username for authentication
            key_path: Path to SSH private key file

        Returns:
            Connected SSH client or None if connection fails
        """
        client = paramiko.SSHClient()

        if self.ssh_args['add_target_host_key']:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        elif self.ssh_args['known_hosts_file']:
            client.load_host_keys(self.ssh_args['known_hosts_file'])
        else:
            client.set_missing_host_key_policy(paramiko.RejectPolicy())

        try:
            # Set up SSH connection arguments
            connect_args = {
                'hostname': host,
                'port': port,
                'username': username,
                'key_filename': key_path,
                'timeout': self.ssh_args['timeout'],
                'auth_timeout': self.ssh_args['auth_timeout'],
                **self.ssh_args['args']  # Include all additional args
            }

            # Connect with the specified arguments
            client.connect(**connect_args)
            
            # Configure keepalive if specified
            if 'keepalive_interval' in self.ssh_args['args']:
                client.get_transport().set_keepalive(
                    self.ssh_args['args']['keepalive_interval'],
                    self.ssh_args['args'].get('keepalive_countmax', 3)
                )
                
            transport = client.get_transport()
            cipher = transport.remote_cipher
            mac = transport.remote_mac
            self.logger.info(f"SSH connection established with {host}:{port} using key-based authentication")
            self.logger.info(f"Connection secured with cipher {cipher} and MAC {mac}")
            return client

        except (paramiko.SSHException, socket.error) as e:
            self.logger.error(f"Failed to connect to {host}: {str(e)}")
            if client:
                client.close()
            return None

    def execute_command(
        self,
        ssh_client: paramiko.SSHClient,
        command: str,
        timeout: int = 30
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Execute a command on the remote device.

        Executes RouterOS commands with proper timeout handling and
        result processing. All commands are logged for debugging.

        Args:
            ssh_client: Connected SSH client to use
            command: RouterOS command to execute
            timeout: Command execution timeout in seconds

        Returns:
            Tuple containing:
            - stdout: Command output if successful, None on error
            - stderr: Error message if failed, None on success

        Error Handling:
            - Timeout handling
            - Connection loss detection
            - Command syntax errors
            - Execution permission issues

        Example:
            ```python
            stdout, stderr = ssh_manager.execute_command(
                client,
                '/system resource print',
                timeout=30
            )
            if stderr:
                print(f"Error: {stderr}")
            else:
                print(f"Output: {stdout}")
            ```
        """
        try:
            stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
            return stdout.read().decode().strip(), stderr.read().decode().strip()
        except Exception as e:
            self.logger.error(f"Failed to execute command: {command}. Error: {str(e)}")
            return None, str(e)

    def check_file_exists(self, ssh_client: paramiko.SSHClient, file_path: str) -> bool:
        """
        Check if a file exists on the remote device.

        Args:
            ssh_client: Connected SSH client
            file_path: Path to check

        Returns:
            bool: True if file exists, False otherwise
        """
        stdout, _ = self.execute_command(ssh_client, f":put [file exists {file_path}]")
        return stdout == "true" if stdout else False

    def close_client(self, ssh_client: paramiko.SSHClient) -> None:
        """
        Safely close an SSH client connection.

        Args:
            ssh_client: SSH client to close
        """
        try:
            if ssh_client:
                ssh_client.close()
                self.logger.debug("SSH connection closed")
        except Exception as e:
            self.logger.error(f"Error closing SSH connection: {str(e)}")
