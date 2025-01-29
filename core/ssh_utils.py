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

    def filter(self, record) -> bool:
        """
        Add target_name to the log record and filter certain messages.
        
        Args:
            record: The log record to filter
            
        Returns:
            bool: True if the record should be logged, False if it should be filtered out
        """
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

    def format(self, record) -> str:
        """
        Format the log record with target information.
        
        Args:
            record: The log record to format
            
        Returns:
            str: The formatted log message
        """
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

    def __init__(self, ssh_args: Dict[str, Any], target_name: str = 'SYSTEM'):
        """
        Initialize SSH manager.

        Args:
            ssh_args: SSH connection arguments
            target_name: Name of the target for logging purposes
        """
        self.ssh_args = ssh_args
        self.target_name = target_name
        self.logger = LogManager().get_logger('SSH', target_name)

        # Configure paramiko logging
        paramiko_logger = logging.getLogger('paramiko')
        paramiko_logger.setLevel(logging.WARNING)  # Only show warnings and errors

        # Add our custom formatter to paramiko's logger
        for handler in paramiko_logger.handlers:
            handler.setFormatter(BaseFormatter(target_name=target_name))

    def create_client(
        self,
        host: str,
        port: int = 22,
        username: str = 'rosbackup',
        key_path: Optional[str] = None,
        suppress_logs: bool = False
    ) -> Optional[paramiko.SSHClient]:
        """
        Create a new SSH client connection.

        Args:
            host: Target hostname or IP
            port: SSH port number
            username: SSH username
            key_path: Path to SSH private key
            suppress_logs: If True, suppress log messages during compose-style output

        Returns:
            Connected SSH client or None if connection fails
        """
        try:
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Load private key
            if not key_path:
                if not suppress_logs:
                    self.logger.error("No private key specified")
                return None
            try:
                pkey = paramiko.RSAKey.from_private_key_file(key_path)
            except Exception as e:
                if not suppress_logs:
                    self.logger.error(f"Failed to load private key: {str(e)}")
                return None

            # Connect to the router
            try:
                # Map our config parameters to paramiko's expected arguments
                connect_args = {
                    'hostname': host,
                    'port': port,
                    'username': username,
                    'pkey': pkey,
                    'timeout': self.ssh_args.get('timeout', 30),
                    'allow_agent': self.ssh_args.get('allow_agent', False),
                    'look_for_keys': self.ssh_args.get('look_for_keys', False),
                    'compress': self.ssh_args.get('compress', True),
                    'auth_timeout': self.ssh_args.get('auth_timeout', 5),
                    'banner_timeout': self.ssh_args.get('banner_timeout', 5),
                    'disabled_algorithms': self.ssh_args.get('disabled_algorithms', {})
                }
                
                client.connect(**connect_args)
            except paramiko.AuthenticationException:
                if not suppress_logs:
                    self.logger.error("Authentication failed")
                return None
            except paramiko.SSHException as e:
                if not suppress_logs:
                    self.logger.error(f"SSH error: {str(e)}")
                return None
            except socket.error as e:
                if not suppress_logs:
                    self.logger.error(f"Socket error: {str(e)}")
                return None
            except Exception as e:
                if not suppress_logs:
                    self.logger.error(f"Connection failed: {str(e)}")
                return None

            return client

        except Exception as e:
            if not suppress_logs:
                self.logger.error(f"Failed to create SSH client: {str(e)}")
            return None

    def execute_command(
        self,
        ssh_client: paramiko.SSHClient,
        command: str,
        timeout: Optional[int] = 60,  # Default 60 second timeout
        get_pty: bool = False
    ) -> Tuple[str, str, int]:
        """
        Execute command on remote host.
        
        Args:
            ssh_client: Connected SSH client
            command: Command to execute
            timeout: Command execution timeout in seconds (default: 60)
            get_pty: Whether to request a PTY
            
        Returns:
            Tuple containing:
            - stdout output
            - stderr output
            - exit status
        """
        try:
            stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout, get_pty=get_pty)
            stdout_str = stdout.read().decode('utf-8').strip()
            stderr_str = stderr.read().decode('utf-8').strip()
            exit_status = stdout.channel.recv_exit_status()
            
            if stderr_str:
                self.logger.debug(f"Command '{command}' returned error: {stderr_str}")
            
            return stdout_str, stderr_str, exit_status

        except socket.timeout:
            self.logger.error(f"Command '{command}' timed out after {timeout} seconds")
            raise TimeoutError(f"Command execution timed out after {timeout} seconds")
            
        except Exception as e:
            self.logger.error(f"Error executing command '{command}': {str(e)}")
            raise RuntimeError(f"Command execution failed: {str(e)}")

    def get_client(
        self,
        target: str,
        host: str,
        port: int,
        username: str,
        key_file: Optional[str] = None,
        known_hosts_file: Optional[str] = None,
        add_host_key: bool = True,
        timeout: int = 5
    ) -> paramiko.SSHClient:
        """
        Get SSH client for target.
        
        Args:
            target: Target name for logging
            host: Hostname to connect to
            port: Port to connect to
            username: Username for authentication
            key_file: Path to SSH private key file
            known_hosts_file: Path to known hosts file
            add_host_key: Whether to add unknown host keys
            timeout: Connection timeout
            
        Returns:
            Connected SSH client
            
        Raises:
            paramiko.SSHException: If connection fails
            paramiko.AuthenticationException: If authentication fails
        """
        try:
            # Create SSH client
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Configure paramiko logging
            paramiko_logger = logging.getLogger('paramiko')
            paramiko_logger.setLevel(logging.WARNING)  # Only show warnings and errors
            paramiko_logger.addFilter(ParamikoFilter(target))
            for handler in paramiko_logger.handlers:
                handler.setFormatter(ParamikoFormatter(target))

            # Load private key
            if key_file:
                try:
                    key = paramiko.RSAKey.from_private_key_file(key_file)
                except Exception as e:
                    self.logger.error(f"Failed to load private key: {str(e)}")
                    raise paramiko.AuthenticationException(f"Failed to load private key: {str(e)}")
            else:
                key = None

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

        except paramiko.AuthenticationException as e:
            self.logger.error(f"Authentication failed for {username}@{host}: {str(e)}")
            raise paramiko.AuthenticationException(f"Authentication failed for {username}@{host}: {str(e)}")

        except paramiko.SSHException as e:
            self.logger.error(f"SSH error: {str(e)}")
            raise paramiko.SSHException(f"SSH error: {str(e)}")

        except socket.error as e:
            self.logger.error(f"Socket error: {str(e)}")
            raise paramiko.SSHException(f"Socket error: {str(e)}")

        except Exception as e:
            self.logger.error(f"Connection failed: {str(e)}")
            raise paramiko.SSHException(f"Connection failed: {str(e)}")

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
            stdout, stderr, _ = self.execute_command(ssh_client, f"/file print where name=\"{file_path}\"")
            return bool(stdout and "no such item" not in stdout.lower())
        except Exception as e:
            self.logger.error(f"Error checking file existence: {str(e)}")
            return False
