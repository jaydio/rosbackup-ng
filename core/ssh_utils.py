"""
SSH utility functions for RouterOS backup operations.
"""

import paramiko
import logging
from pathlib import Path
from typing import Optional, Dict, Tuple

class SSHManager:
    """Manages SSH connections to RouterOS devices."""

    def __init__(self, ssh_args: Dict):
        """
        Initialize SSH manager.

        Args:
            ssh_args (Dict): SSH connection arguments
        """
        self.ssh_args = ssh_args
        self.logger = logging.getLogger(__name__)

    def create_client(self, host: str, port: int, username: str, key_path: str) -> Optional[paramiko.SSHClient]:
        """
        Create and return an SSH client connected to the specified host.

        Args:
            host (str): Hostname or IP address
            port (int): SSH port number
            username (str): SSH username
            key_path (str): Path to SSH private key

        Returns:
            Optional[paramiko.SSHClient]: Connected SSH client or None if connection fails
        """
        self.logger.debug(f"Attempting SSH connection to {host}:{port}")
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(
                    hostname=host,
                    port=port,
                    username=username,
                    key_filename=key_path,
                    timeout=self.ssh_args.get('timeout', 30),
                    auth_timeout=self.ssh_args.get('auth_timeout', 30)
                )
            except paramiko.AuthenticationException:
                self.logger.error(f"Authentication failed for user '{username}'. Please verify the username and SSH key.")
                return None
            except paramiko.SSHException as e:
                if "private key file is encrypted" in str(e).lower():
                    self.logger.error(f"SSH key at {key_path} is encrypted. Please provide an unencrypted key.")
                else:
                    self.logger.error(f"SSH connection failed: {str(e)}")
                return None
            transport = ssh.get_transport()
            cipher = transport.remote_cipher
            mac = transport.remote_mac
            self.logger.info(f"SSH connection established with {host}:{port} using key-based authentication")
            self.logger.info(f"Connection secured with cipher {cipher} and MAC {mac}")
            return ssh
        except Exception as e:
            self.logger.error(f"Failed to establish SSH connection to {host}:{port}: {str(e)}")
            return None

    def execute_command(self, ssh_client: paramiko.SSHClient, command: str, 
                       timeout: int = 30) -> Tuple[Optional[str], Optional[str]]:
        """
        Execute a command on the remote device.

        Args:
            ssh_client (paramiko.SSHClient): Connected SSH client
            command (str): Command to execute
            timeout (int): Command timeout in seconds

        Returns:
            Tuple[Optional[str], Optional[str]]: Tuple of (stdout, stderr)
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
            ssh_client (paramiko.SSHClient): Connected SSH client
            file_path (str): Path to check

        Returns:
            bool: True if file exists, False otherwise
        """
        stdout, _ = self.execute_command(ssh_client, f":put [file exists {file_path}]")
        return stdout == "true" if stdout else False

    def close_client(self, ssh_client: paramiko.SSHClient) -> None:
        """
        Safely close an SSH client connection.

        Args:
            ssh_client (paramiko.SSHClient): SSH client to close
        """
        try:
            if ssh_client:
                ssh_client.close()
                self.logger.debug("SSH connection closed")
        except Exception as e:
            self.logger.error(f"Error closing SSH connection: {str(e)}")
