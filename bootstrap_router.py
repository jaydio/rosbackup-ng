#!/usr/bin/env python3
"""
bootstrap_router.py - A script to create a backup user on a RouterOS device and install an SSH public key for authentication.

Usage:
    python3 bootstrap_router.py [--ip <ROUTER_IP>] [--ssh-user <SSH_USERNAME>] [--ssh-user-password <SSH_PASSWORD>]
                              [--ssh-user-private-key <SSH_PRIVATE_KEY_PATH>] [--ssh-port <SSH_PORT>] 
                              [--backup-user <BACKUP_USERNAME>] [--backup-user-password <BACKUP_USER_PASSWORD>]
                              [--backup-user-public-key <PUBLIC_KEY_PATH>] [--show-backup-credentials]
                              [--backup-user-group <USER_GROUP>]
                              
                              [--log-file <LOG_FILE_PATH>] [--no-color]

Examples:
    # Using SSH password authentication and specifying all parameters
    python3 bootstrap_router.py --ip 192.168.100.225 --ssh-user admin --ssh-user-password adminpass \
        --backup-user backup --backup-user-password backuppass123 --backup-user-public-key /path/to/backup_user_key.pub \
        --ssh-port 2222 --log-file /var/log/bootstrap_router.log

    # Using SSH key-based authentication and generating a random password for the backup user
    python3 bootstrap_router.py --ip 192.168.100.225 --ssh-user admin --ssh-user-private-key /path/to/admin_private_key \
        --backup-user-public-key /path/to/backup_user_key.pub --ssh-port 2200

    # Using interactive password prompt and showing backup credentials without file logging
    python3 bootstrap_router.py --ip 192.168.100.225 --backup-user-public-key /path/to/backup_user_key.pub \
        --show-backup-credentials --ssh-port 2222
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

# ANSI color codes
COLOR_RESET = "\033[0m"
COLOR_INFO = "\033[92m"     # Green
COLOR_WARNING = "\033[93m"  # Yellow
COLOR_ERROR = "\033[91m"    # Red

class ColoredFormatter(logging.Formatter):
    """
    Custom logging formatter to add colors based on log level.
    """
    def __init__(self, use_colors=True):
        """Initialize the formatter with color option."""
        super().__init__('%(asctime)s [%(levelname)s] %(message)s')
        self.use_colors = use_colors

    def format(self, record):
        message = super().format(record)
        if not self.use_colors:
            return message

        if record.levelno == logging.ERROR:
            message = f"{COLOR_ERROR}{message}{COLOR_RESET}"
        elif record.levelno == logging.WARNING:
            message = f"{COLOR_WARNING}{message}{COLOR_RESET}"
        elif record.levelno == logging.INFO:
            message = f"{COLOR_INFO}{message}{COLOR_RESET}"
        return message

def parse_arguments():
    """Parse command-line arguments with renamed parameters and default values."""
    parser = argparse.ArgumentParser(description="Bootstrap a backup user on a RouterOS device.")

    parser.add_argument('--ip', required=True, help='IP address of the target RouterOS device.')
    parser.add_argument('--ssh-user', default='admin', help='Existing SSH username with privileges to create users and manage SSH keys. Default: admin')
    parser.add_argument('--ssh-port', type=int, default=22, help='SSH port to connect to. Default: 22')

    auth_group = parser.add_mutually_exclusive_group()
    auth_group.add_argument('--ssh-user-password', help='Password for the existing SSH user.')
    auth_group.add_argument('--ssh-user-private-key', help='Path to the private SSH key for the existing SSH user.')

    
    parser.add_argument('--backup-user', default='rosbackup', help='Username to be created for backups. Default: rosbackup')
    parser.add_argument('--backup-user-password', help='Password for the backup user. If not specified, a random 24-character alphanumeric password will be generated.')
    parser.add_argument('--backup-user-public-key', required=True, help='Path to the SSH public key to install for the backup user.')
    parser.add_argument('--show-backup-credentials', action='store_true', default=False, help='Show the backup user credentials after setup. Default: False')
    parser.add_argument('--backup-user-group', default='full', help="User group to assign to the backup user on the router. Must have 'write' policy enabled. Default: 'full'")

    parser.add_argument('--log-file', default='', help='Path to log file. Default: empty (no file logging).')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')

    return parser.parse_args()

def setup_logging(log_file='', use_colors=True):
    """Configure logging with colored console output and optional file logging.
    
    Args:
        log_file (str): Path to log file. If empty, file logging is disabled.
        use_colors (bool): Whether to use colored output in console.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove any existing handlers
    logger.handlers = []

    # Console handler with optional colored output
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch_formatter = ColoredFormatter(use_colors=use_colors)
    ch.setFormatter(ch_formatter)
    logger.addHandler(ch)

    # File handler with plain text, added only if log_file is specified
    if log_file:
        try:
            fh = logging.FileHandler(log_file)
            fh.setLevel(logging.DEBUG)
            fh_formatter = ColoredFormatter(use_colors=False)  # Never use colors in file
            fh.setFormatter(fh_formatter)
            logger.addHandler(fh)
            logging.info(f"Logging to file '{log_file}' enabled.")
        except Exception as e:
            logging.error(f"Failed to set up file logging at '{log_file}': {e}")
            sys.exit(1)
    else:
        logging.debug("File logging not enabled.")

def generate_random_password(length=24):
    """Generate a random alphanumeric password of specified length."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def read_public_key(public_key_path):
    """Read the SSH public key from the specified file."""
    try:
        with open(public_key_path, 'r') as f:
            public_key = f.read().strip()
        return public_key
    except Exception as e:
        logging.error(f"Failed to read public key from {public_key_path}: {e}")
        sys.exit(1)

def create_ssh_client(ip, ssh_port, username, password=None, key_filepath=None):
    """
    Establish an SSH connection to the RouterOS device.

    Args:
        ip (str): IP address of the router.
        ssh_port (int): SSH port number (default: 22).
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
            client.connect(hostname=ip, port=ssh_port, username=username, pkey=key, timeout=10,
                           allow_agent=True, look_for_keys=True)
            auth_method = "key-based authentication"
        else:
            # When using password-based auth, disable agent and look for keys
            client.connect(hostname=ip, port=ssh_port, username=username, password=password, timeout=10,
                           allow_agent=False, look_for_keys=False)
            auth_method = "password-based authentication"

        # Retrieve cipher and MAC details directly from Transport
        transport = client.get_transport()
        if transport is None or not transport.is_active():
            logging.error(f"Transport is not active for {ip}:{ssh_port}")
            sys.exit(1)
        cipher = transport.remote_cipher
        mac = transport.remote_mac
        logging.info(f"SSH connection established with {ip}:{ssh_port} using {auth_method}, cipher {cipher}, and MAC {mac}")

        return client
    except Exception as e:
        logging.error(f"SSH connection failed for {ip}:{ssh_port} - {e}")
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

def create_backup_user(ssh_client, backup_username, backup_password, backup_group):
    """
    Create a new backup user on the RouterOS device.

    Args:
        ssh_client (paramiko.SSHClient): Established SSH client.
        backup_username (str): Username to create.
        backup_password (str): Password for the backup user.
        backup_group (str): User group to assign to the backup user.

    Returns:
        bool: True if successful, False otherwise.
    """
    # Check if user already exists
    check_command = f"/user/print where name=\"{backup_username}\""
    output = execute_command(ssh_client, check_command)
    if output:
        logging.warning(f"User '{backup_username}' already exists on the router.")
        return False  # User already exists

    # Create the user with specified password and group
    create_command = f"/user/add name=\"{backup_username}\" group={backup_group} password=\"{backup_password}\""
    output = execute_command(ssh_client, create_command)
    if output is not None:
        logging.info(f"User '{backup_username}' created successfully with group '{backup_group}'.")
        return True
    else:
        logging.error(f"Failed to create user '{backup_username}'.")
        return False

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

    if args.ssh_user_password:
        ssh_password = args.ssh_user_password
    elif args.ssh_user_private_key:
        ssh_key_filepath = args.ssh_user_private_key
        if not Path(ssh_key_filepath).is_file():
            logging.error(f"SSH user private key file '{ssh_key_filepath}' does not exist.")
            sys.exit(1)
    else:
        # Prompt for SSH user password
        ssh_password = getpass.getpass(prompt=f"Enter password for SSH user '{args.ssh_user}': ")

    # Establish SSH connection
    ssh_client = create_ssh_client(
        ip=args.ip,
        ssh_port=args.ssh_port,  
        username=args.ssh_user,
        password=ssh_password,
        key_filepath=ssh_key_filepath
    )

    # Retrieve router identity
    router_identity = get_router_identity(ssh_client, args.ip)
    logging.info(f"Attempting to create backup user on router '{router_identity}' at {args.ip}")

    # Determine backup user password
    if args.backup_user_password:
        backup_user_password = args.backup_user_password
        logging.info("Using provided backup user password.")
    else:
        backup_user_password = generate_random_password()
        logging.info("No backup user password provided. A random password has been generated.")

    # Create backup user
    user_created = create_backup_user(ssh_client, args.backup_user, backup_user_password, args.backup_user_group)

    if user_created:
        # Install public key for the backup user
        key_installed = install_public_key(ssh_client, args.backup_user, backup_public_key)
        if key_installed:
            logging.info(f"Backup user '{args.backup_user}' is set up successfully on router {args.ip}.")
            if args.show_backup_credentials:
                print("\nBackup User Credentials:")
                print(f"Username: {args.backup_user}")
                print(f"Password: {backup_user_password}\n")
        else:
            logging.error(f"Failed to install SSH public key for user '{args.backup_user}' on router {args.ip}.")
    else:
        logging.warning(f"Skipping SSH key installation for user '{args.backup_user}' as user creation failed or user already exists.")

    # Close SSH connection
    ssh_client.close()
    logging.info("SSH connection closed.")

if __name__ == "__main__":
    main()
