"""
SSH utilities for RouterOS devices.

This module provides SSH connection management and command execution
functionality for RouterOS devices, with support for key-based authentication
and connection pooling.
"""

import paramiko
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
import logging
import socket
from .logging_utils import LogManager
from .shell_utils import BaseFormatter


class ParamikoFilter(logging.Filter):
    """Filter that adds target_name to paramiko log records."""
    def __init__(self, target_name: str):
        super().__init__()
        self.target_name = target_name

    def filter(self, record):
        """Add target_name to the log record."""
        # Always set target_name
        record.target_name = self.target_name
        # Skip "Connected" messages for transport
        if record.name == 'paramiko.transport':
            if 'Connected' in record.msg:
                return False
            # Skip authentication messages since they'll be logged by our own code
            if 'Authentication' in record.msg:
                return False
        return True


class ParamikoFormatter(BaseFormatter):
    """Formatter for paramiko log messages."""

    def __init__(self, target_name: str):
        super().__init__(target_name=target_name)

    def format(self, record):
        """Format the log record."""
        # Always set target_name
        record.target_name = self.target_name
        return super().format(record)


class SSHManager:
    """
    Manages SSH connections to RouterOS devices.

    This class handles SSH connection creation, command execution, and connection
    cleanup with proper error handling and logging.

    Attributes:
        ssh_args (Dict[str, Any]): SSH connection arguments
        target_name (str): Name of the target for logging purposes
        logger (logging.Logger): Logger instance for this class
    """

    def __init__(self, ssh_args: Dict[str, Any], target_name: str) -> None:
        """
        Initialize SSH manager.

        Args:
            ssh_args: SSH connection arguments
            target_name: Name of the target for logging purposes
        """
        self.ssh_args = ssh_args
        self.target_name = target_name
        self.logger = LogManager().get_logger('SSH', target_name)

    def create_client(
        self,
        host: str,
        port: int,
        username: str,
        key_path: str,
        timeout: int = 30
    ) -> Optional[paramiko.SSHClient]:
        """
        Create a new SSH client connection.

        Creates and configures a new SSH client with the specified parameters,
        using key-based authentication.

        Args:
            host: Target hostname or IP address
            port: Target SSH port
            username: SSH username
            key_path: Path to SSH private key file
            timeout: Connection timeout in seconds

        Returns:
            Connected SSHClient instance or None if connection fails

        Error Handling:
            - Logs authentication failures
            - Handles connection timeouts
            - Manages key loading errors
            - Reports network connectivity issues
        """
        try:
            # Log connection attempt
            self.logger.debug(f"Connecting to {host}:{port} as {username}")

            # Create SSH client
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Configure paramiko logging
            paramiko_logger = logging.getLogger('paramiko')
            paramiko_logger.setLevel(logging.WARNING)  # Only show warnings and errors
            paramiko_logger.addFilter(ParamikoFilter(self.target_name))
            for handler in paramiko_logger.handlers:
                handler.setFormatter(ParamikoFormatter(self.target_name))

            # Load private key
            try:
                key = paramiko.RSAKey.from_private_key_file(key_path)
            except Exception as e:
                self.logger.error(f"Failed to load private key: {str(e)}")
                return None

            # Connect to host
            client.connect(
                hostname=host,
                port=port,
                username=username,
                pkey=key,
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False
            )

            # Log success
            cipher = client.get_transport().local_cipher
            mac = client.get_transport().local_mac
            self.logger.debug(f"SSH connection established with {host}:{port} using key-based authentication")
            self.logger.debug(f"Connection secured with cipher {cipher} and MAC {mac}")

            return client

        except paramiko.AuthenticationException:
            self.logger.error(f"Authentication failed for {username}@{host}")
            return None

        except paramiko.SSHException as e:
            self.logger.error(f"SSH error: {str(e)}")
            return None

        except socket.error as e:
            self.logger.error(f"Socket error: {str(e)}")
            return None

        except Exception as e:
            self.logger.error(f"Connection failed: {str(e)}")
            return None

    def execute_command(
        self,
        ssh_client: paramiko.SSHClient,
        command: str,
        timeout: int = 10
    ) -> Tuple[str, str]:
        """
        Execute a command on the remote host.

        Args:
            ssh_client: Connected SSH client
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            Tuple of (stdout, stderr) strings

        Raises:
            RuntimeError: If command execution fails
        """
        try:
            stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
            stdout_str = stdout.read().decode('utf-8').strip()
            stderr_str = stderr.read().decode('utf-8').strip()
            
            if stderr_str:
                self.logger.debug(f"Command '{command}' returned error: {stderr_str}")
            
            return stdout_str, stderr_str

        except Exception as e:
            self.logger.error(f"Error executing command '{command}': {str(e)}")
            raise RuntimeError(f"Command execution failed: {str(e)}")

    def check_file_exists(self, ssh_client: paramiko.SSHClient, file_path: str) -> bool:
        """
        Check if a file exists on the remote host.

        Args:
            ssh_client: Connected SSH client
            file_path: Path to check

        Returns:
            True if file exists, False otherwise
        """
        try:
            stdout, stderr = self.execute_command(ssh_client, f"/file print where name=\"{file_path}\"")
            return bool(stdout and "no such item" not in stdout.lower())
        except Exception as e:
            self.logger.error(f"Error checking file existence: {str(e)}")
            return False
