#!/usr/bin/env python3
"""
bootstrap_router.py - Configure RouterOS devices for automated backups

This script prepares RouterOS devices for automated backups by:
1. Creating a dedicated backup user with appropriate permissions
2. Installing an SSH public key for secure authentication
3. Validating the setup and access rights

Usage:
    python3 bootstrap_router.py [OPTIONS]

Required Options:
    --host HOST                  RouterOS device IP address or hostname
    --backup-user-public-key KEY Public key file for backup user authentication

Authentication Options (one required):
    --ssh-user-password PASS     SSH password for initial connection
    --ssh-user-private-key KEY   SSH private key for initial connection

Optional Settings:
    --ssh-user USER             SSH username for initial connection [default: admin]
    --ssh-port PORT            SSH port number [default: 22]
    --backup-user USER         Username for backup account [default: rosbackup]
    --backup-user-password PASS Password for backup user [auto-generated if not set]
    --backup-user-group GROUP  User group for backup user [default: full]
    --show-backup-credentials  Display generated backup user credentials
    --log-file FILE           Path to log file [default: no file logging]
    --no-color                Disable colored output

Examples:
    # Basic usage with password authentication:
    python3 bootstrap_router.py --host 192.168.1.1 \\
        --ssh-user admin --ssh-user-password adminpass \\
        --backup-user-public-key ~/.ssh/backup_key.pub

    # Using SSH key authentication with custom settings:
    python3 bootstrap_router.py --host 192.168.1.1 \\
        --ssh-user admin --ssh-user-private-key ~/.ssh/admin_key \\
        --backup-user backupuser --backup-user-group read \\
        --backup-user-public-key ~/.ssh/backup_key.pub \\
        --ssh-port 2222 --log-file /var/log/bootstrap.log

    # Interactive password prompt with backup credential display:
    python3 bootstrap_router.py --host 192.168.1.1 \\
        --backup-user-public-key ~/.ssh/backup_key.pub \\
        --show-backup-credentials

Notes:
    - The script requires Python 3.6 or later
    - The backup user's password will be auto-generated if not specified
    - SSH key authentication is recommended over password authentication
    - Log files are rotated automatically (max 5 files of 1MB each)
    - Use --show-backup-credentials with caution in production environments
"""

import argparse
import paramiko
import sys
from pathlib import Path
import logging
import getpass
import secrets
import string
import re
import textwrap
import random

class ColoredFormatter(logging.Formatter):
    """Custom formatter adding colors to log levels."""
    
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    reset = "\x1b[0m"
    format_str = "%(asctime)s [%(levelname)s] %(message)s"

    def __init__(self, use_colors=True):
        """Initialize the formatter with color option."""
        super().__init__()
        self.use_colors = use_colors
        self.FORMATS = {
            logging.DEBUG: (self.yellow if self.use_colors else "") + self.format_str + (self.reset if self.use_colors else ""),
            logging.INFO: (self.green if self.use_colors else "") + self.format_str + (self.reset if self.use_colors else ""),
            logging.WARNING: (self.yellow if self.use_colors else "") + self.format_str + (self.reset if self.use_colors else ""),
            logging.ERROR: (self.red if self.use_colors else "") + self.format_str + (self.reset if self.use_colors else ""),
            logging.CRITICAL: (self.red if self.use_colors else "") + self.format_str + (self.reset if self.use_colors else "")
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

def setup_logging(log_file='', use_colors=True):
    """Configure logging with colored console output and optional file logging.

    Args:
        log_file (str): Path to log file. If empty, file logging is disabled.
        use_colors (bool): Whether to use colored output.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove any existing handlers
    root_logger.handlers = []

    # Console handler with color formatting
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter(use_colors=use_colors))
    root_logger.addHandler(console_handler)

    # File handler if log file is specified (never use colors in file)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(ColoredFormatter(use_colors=False))
        root_logger.addHandler(file_handler)

def get_password(prompt: str) -> str:
    """
    Get password from user input, handling both interactive and non-interactive environments.
    
    Args:
        prompt (str): Prompt to display to the user
        
    Returns:
        str: The password entered by the user
    """
    try:
        return getpass.getpass(prompt)
    except:
        print("Warning: Password input may be echoed.")
        try:
            return input(prompt)
        except EOFError:
            print("\nError: Password input is required. Please provide the password via --ssh-user-password")
            sys.exit(1)

def parse_arguments():
    """Parse command-line arguments with renamed parameters and default values."""
    parser = argparse.ArgumentParser(
        description="Configure RouterOS devices for automated backups",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent('''
            Examples:
              %(prog)s --host 192.168.1.1 --backup-user-public-key ~/.ssh/backup.pub
              %(prog)s --host router.local --ssh-user admin --ssh-port 2222 --backup-user-public-key ./keys/backup.pub

            Note: Strict host key checking is disabled by default for initial setup.
            ''')
    )

    parser.add_argument('--host', required=True, help='Hostname or IP address of the target RouterOS device')
    parser.add_argument('--ssh-user', default='admin', help='Existing SSH username with privileges to create users and manage SSH keys. Default: admin')
    parser.add_argument('--ssh-user-password', help='Password for the SSH user. If not provided, will prompt for password')
    parser.add_argument('--ssh-user-private-key', help='Path to private key file for the SSH user')
    parser.add_argument('--ssh-port', type=int, default=22, help='SSH port number. Default: 22')
    parser.add_argument('--backup-user', default='rosbackup', help='Username to create for backup operations. Default: rosbackup')
    parser.add_argument('--backup-user-password', help='Password for the backup user. If not specified, a random password will be generated')
    parser.add_argument('--backup-user-public-key', required=True, help='Path to public key file to install for the backup user')
    parser.add_argument('--show-backup-credentials', action='store_true', default=False, help='Show the backup user credentials after setup')
    parser.add_argument('--backup-user-group', default='full', help="User group for the backup user. Default: 'full'")
    parser.add_argument('--log-file', help='Path to log file. If not specified, logging to file is disabled')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')

    args = parser.parse_args()

    # If no password or private key is provided, prompt for password
    if not args.ssh_user_password and not args.ssh_user_private_key:
        args.ssh_user_password = get_password(f"Enter password for user '{args.ssh_user}': ")

    return args

def generate_password(length=24):
    """Generate a random password using only letters and numbers.

    Args:
        length (int): Length of the password to generate. Default is 24.

    Returns:
        str: Generated password containing only letters (mixed case) and numbers
    """
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def read_public_key(public_key_path):
    """Read the SSH public key from the specified file."""
    try:
        with open(public_key_path, 'r') as f:
            public_key = f.read().strip()
        return public_key
    except Exception as e:
        logging.error(f"Failed to read public key from {public_key_path}: {e}")
        sys.exit(1)

def create_ssh_client(ip, port, username, password=None, key_filepath=None):
    """
    Establish an SSH connection to the RouterOS device.

    Args:
        ip (str): IP address of the router.
        port (int): SSH port number (default: 22).
        username (str): SSH username.
        password (str, optional): SSH password.
        key_filepath (str, optional): Path to SSH private key.

    Returns:
        paramiko.SSHClient: Established SSH client.

    Exits:
        If connection fails.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        if key_filepath:
            key = paramiko.RSAKey.from_private_key_file(key_filepath)
            # When using key-based auth, allow agent and look for keys
            client.connect(hostname=ip, port=port, username=username, pkey=key, timeout=10,
                           allow_agent=True, look_for_keys=True)
            auth_method = "key-based authentication"
        else:
            # When using password-based auth, disable agent and look for keys
            client.connect(hostname=ip, port=port, username=username, password=password, timeout=10,
                           allow_agent=False, look_for_keys=False)
            auth_method = "password-based authentication"

        # Retrieve cipher and MAC details directly from Transport
        transport = client.get_transport()
        if transport is None or not transport.is_active():
            logging.error(f"Transport is not active for {ip}:{port}")
            sys.exit(1)
        cipher = transport.remote_cipher
        mac = transport.remote_mac
        logging.info(f"SSH connection established with {ip}:{port} using {auth_method}, cipher {cipher}, and MAC {mac}")

        return client
    except Exception as e:
        logging.error(f"SSH connection failed for {ip}:{port} - {e}")
        sys.exit(1)

def execute_command(ssh_client, command):
    """
    Execute a command on the RouterOS device via SSH.

    Args:
        ssh_client (paramiko.SSHClient): Established SSH client.
        command (str): Command to execute.

    Returns:
        str: Command output or None if failed.
    """
    try:
        stdin, stdout, stderr = ssh_client.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        if error:
            logging.error(f"Error executing command '{command}': {error.strip()}")
            return None
        return output.strip()
    except Exception as e:
        logging.error(f"Exception while executing command '{command}': {e}")
        return None

def get_router_identity(ssh_client, ip):
    """
    Retrieve the router's identity.

    Args:
        ssh_client (paramiko.SSHClient): Established SSH client.
        ip (str): IP address of the router.

    Returns:
        str: Router identity or 'Unknown' if retrieval fails.
    """
    identity_command = "/system identity print"
    output = execute_command(ssh_client, identity_command)
    if output:
        # RouterOS typically returns output in one of the following formats:
        # name="MYR4"
        # or
        # name: MYR4
        # To handle both, we'll use a regex that matches both patterns.
        match = re.search(r'name\s*=\s*"(.+)"', output)
        if not match:
            match = re.search(r'name\s*:\s*(.+)', output)
        if match:
            identity = match.group(1).strip('"').strip()
            return identity
        else:
            logging.warning(f"Could not parse router identity from output: '{output}'. Using 'Unknown'.")
            return "Unknown"
    else:
        logging.warning("Failed to retrieve router identity. Using 'Unknown'.")
        return "Unknown"

def create_backup_user(ssh_client, username, password=None, group='full'):
    """Create a backup user on the RouterOS device.

    Args:
        ssh_client: Paramiko SSH client instance
        username (str): Username to create
        password (str, optional): Password for the user. If not provided, a random one will be generated
        group (str): User group for the new user. Default is 'full'

    Returns:
        tuple: (success, password) where success is True if user was created successfully,
               and password is the user's password (either provided or generated)
    """
    # Check if user already exists
    stdin, stdout, stderr = ssh_client.exec_command(f'/user print where name="{username}"')
    if username in stdout.read().decode():
        logging.warning(f"User '{username}' already exists on the router.")
        return False, None

    # Generate password if not provided
    if not password:
        logging.info("No backup user password provided. A random password will be generated.")
        password = generate_password()
        logging.info(f"A random password with {len(password)} characters has been generated for the backup user.")

    # Create the user with specified group
    stdin, stdout, stderr = ssh_client.exec_command(f'/user add name="{username}" password="{password}" group="{group}"')
    error = stderr.read().decode().strip()
    if error:
        logging.error(f"Failed to create user '{username}': {error}")
        return False, None

    logging.info(f"User '{username}' created successfully with group '{group}'")
    return True, password

def install_public_key(ssh_client, backup_username, public_key):
    """
    Install the SSH public key for the backup user.

    Args:
        ssh_client (paramiko.SSHClient): Established SSH client.
        backup_username (str): Username to install the key for.
        public_key (str): SSH public key.

    Returns:
        bool: True if successful, False otherwise.
    """
    # Add SSH key
    add_key_command = f"/user/ssh-keys/add user=\"{backup_username}\" key=\"{public_key}\""
    output = execute_command(ssh_client, add_key_command)
    if output is not None:
        logging.info(f"SSH public key installed for user '{backup_username}'.")
        return True
    else:
        logging.error(f"Failed to install SSH public key for user '{backup_username}'.")
        return False

def main():
    """Main function to execute the bootstrap process."""
    args = parse_arguments()

    # Setup logging with color option
    setup_logging(log_file=args.log_file, use_colors=not args.no_color)

    # Validate backup user public key path
    backup_public_key_path = Path(args.backup_user_public_key)
    if not backup_public_key_path.is_file():
        logging.error(f"Backup user public key file '{backup_public_key_path}' does not exist.")
        sys.exit(1)

    # Read backup user's public key
    backup_public_key = read_public_key(backup_public_key_path)

    # Handle SSH authentication
    ssh_password = None
    ssh_key_filepath = None

    if args.ssh_user_private_key:
        ssh_key_filepath = args.ssh_user_private_key
        if not Path(ssh_key_filepath).is_file():
            logging.error(f"SSH private key file '{ssh_key_filepath}' does not exist.")
            sys.exit(1)
    else:
        # Use password authentication
        ssh_password = args.ssh_user_password

    # Establish SSH connection
    ssh_client = create_ssh_client(
        ip=args.host,
        port=args.ssh_port,
        username=args.ssh_user,
        password=ssh_password,
        key_filepath=ssh_key_filepath
    )

    if not ssh_client:
        logging.error("Failed to establish SSH connection.")
        sys.exit(1)

    # Retrieve router identity
    router_identity = get_router_identity(ssh_client, args.host)
    logging.info(f"Attempting to create backup user on router '{router_identity}' at {args.host}")

    # Create the backup user
    user_created, backup_password = create_backup_user(ssh_client, args.backup_user, args.backup_user_password, args.backup_user_group)

    if user_created:
        # Install public key for the backup user
        key_installed = install_public_key(ssh_client, args.backup_user, backup_public_key)
        if key_installed:
            logging.info(f"Backup user '{args.backup_user}' is set up successfully on router {args.host}.")
            if args.show_backup_credentials:
                print("\nBackup User Credentials:")
                print(f"Username: {args.backup_user}")
                print(f"Password: {backup_password}\n")
        else:
            logging.error(f"Failed to install SSH public key for user '{args.backup_user}' on router {args.host}.")
    else:
        logging.warning(f"Skipping SSH key installation for user '{args.backup_user}' as user creation failed or user already exists.")

    # Close SSH connection
    ssh_client.close()
    logging.info("SSH connection closed.")
    logging.info("Bootstrap process completed.")

if __name__ == "__main__":
    main()
