#!/usr/bin/env python3
"""
rosbackup.py - A Python3 script for backing up multiple RouterOS devices via SSH.
"""

import os
import json
import paramiko
import sys
import logging
from scp import SCPClient
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from notifications import Notifications  # Import the Notifications class

# Constants for file extensions
BACKUP_EXT = ".backup"
INFO_EXT = ".INFO.txt"
PLAINTEXT_EXT = ".rsc"  # Changed from .plaintext.txt to .rsc

# ANSI color codes for console output
COLOR_RESET = "\033[0m"
COLOR_INFO = "\033[92m"     # Green
COLOR_ERROR = "\033[91m"    # Red

class ColoredFormatter(logging.Formatter):
    """
    Custom logging formatter to add colors based on log level.
    """

    def format(self, record):
        message = super().format(record)
        if "ERROR" in message:
            message = f"{COLOR_ERROR}{message}{COLOR_RESET}"
        elif "INFO" in message:
            message = f"{COLOR_INFO}{message}{COLOR_RESET}"
        return message

def load_config(config_path: Path) -> Dict:
    """Load JSON configuration from the given path."""
    with open(config_path, 'r') as f:
        return json.load(f)

def create_ssh_client(host: str, port: int, user: str, key_path: Path, ssh_args: Dict) -> paramiko.SSHClient:
    """
    Create and return an SSH client connected to the specified host.

    Returns None if connection fails.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        if key_path:
            client.connect(
                hostname=host,
                port=port,
                username=user,
                key_filename=str(key_path),
                look_for_keys=ssh_args.get("look_for_keys", False),
                allow_agent=ssh_args.get("allow_agent", False),
                timeout=10
            )
            auth_method = "key-based authentication"
        else:
            # Assuming password-based authentication is handled elsewhere
            logging.error(f"No private key provided for SSH user '{user}' on {host}:{port}")
            return None

        # Retrieve cipher and MAC details directly from Transport
        transport = client.get_transport()
        if transport is None or not transport.is_active():
            logging.error(f"Transport is not active for {host}:{port}")
            return None
        cipher = transport.remote_cipher
        mac = transport.remote_mac
        logging.info(f"SSH connection established with {host}:{port} using {auth_method}, cipher {cipher}, and MAC {mac}")

    except Exception as e:
        logging.error(f"SSH connection failed for {host}:{port} - {e}")
        return None
    return client

def sanitize_ros_output(output: str) -> str:
    """Sanitize the output from RouterOS commands by stripping newlines and carriage returns."""
    return output.strip().replace('\r', '')

def get_router_info(ssh_client: paramiko.SSHClient) -> Dict:
    """
    Retrieve router information by executing specific RouterOS commands.

    Returns a dictionary with keys like 'identity', 'version', 'architecture_name', 'license', etc.
    """
    commands = [
        "/system identity print",
        "/system resource print",
        "/system routerboard print",
        "/system license print"  # Added to retrieve license information
    ]
    info = {}
    for command in commands:
        try:
            stdin, stdout, stderr = ssh_client.exec_command(command)
            output = stdout.read().decode()
            error = stderr.read().decode()
            if error and "unknown command" not in error.lower():
                logging.error(f"Error executing '{command}': {error.strip()}")
                continue
            for line in output.splitlines():
                parts = line.strip().split(':', 1)
                if len(parts) == 2:
                    key, value = parts
                    key_clean = key.strip().lower().replace(' ', '_').replace('-', '_')  # Replace hyphens with underscores
                    info[key_clean] = sanitize_ros_output(value)
        except Exception as e:
            logging.error(f"Exception during executing '{command}': {e}")

    # Handle /system/routerboard print absence (for CHR)
    if 'routerboard' not in info:
        info['board_name'] = "CHR"
    else:
        # If routerboard exists, use 'board_name' from routerboard info
        info['board_name'] = sanitize_ros_output(info.get('board_name', 'Unknown'))

    # Map 'name' to 'identity' if 'name' exists; otherwise, use 'identity' from router
    info['identity'] = info.get('name', info.get('identity', 'Unknown'))

    # Log the retrieved router info for debugging
    logging.debug(f"Router Info: {info}")

    return info

def check_remote_file_exists(ssh_client: paramiko.SSHClient, file_path: str) -> bool:
    """
    Check if a file exists on the remote router.

    Returns True if the file exists, False otherwise.
    """
    # Updated command to use '/file/print' as per user's instruction
    command = f'/file/print where name="{file_path}"'
    try:
        stdin, stdout, stderr = ssh_client.exec_command(command)
        output = stdout.read().decode().strip()
        if output:
            return True
        return False
    except Exception as e:
        logging.error(f"Failed to check existence of {file_path}: {e}")
        return False

def mask_password(command: str) -> str:
    """
    Replace the password in the command with '******' for logging purposes.
    """
    return re.sub(r'password="[^"]*"', 'password="******"', command)

def perform_plaintext_backup(ssh_client: paramiko.SSHClient, plaintext_backup_path: Path) -> bool:
    """
    Perform the plaintext backup by executing the export command and capturing its output.

    Returns True if backup is successful, False otherwise.
    """
    try:
        # Execute the export command without specifying a file to capture output
        export_command = '/export show-sensitive'
        stdin, stdout, stderr = ssh_client.exec_command(export_command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        if error:
            logging.error(f"Error executing export command: {error.strip()}")
            return False

        # Write the captured output to a local plaintext backup file with .rsc extension
        with open(plaintext_backup_path, 'w') as f:
            f.write(output)
        logging.info(f"Saved plaintext backup to {plaintext_backup_path.name}")
        return True
    except Exception as e:
        logging.error(f"Plaintext backup failed: {e}")
        return False

def save_info_file(router_info: Dict, info_file_path: Path) -> bool:
    """
    Save router information to the INFO file.

    Returns True if successful, False otherwise.
    """
    try:
        with open(info_file_path, 'w') as f:
            for key, value in router_info.items():
                f.write(f"{key}: {value}\n")
        logging.info(f"Saved router info to {info_file_path.name}")
        return True
    except Exception as e:
        logging.error(f"Failed to save INFO file: {e}")
        return False

def perform_binary_backup(ssh_client: paramiko.SSHClient, router_info: Dict, backup_password: str, encrypted: bool, backup_dir: Path, timestamp: str, keep_binary_backup: bool) -> bool:
    """
    Perform the binary backup process for a single router.

    Returns True if backup is successful, False otherwise.
    """
    router_name = router_info.get('identity', 'Unknown')
    ros_version_raw = router_info.get('version', 'Unknown')
    architecture = router_info.get('architecture_name', 'Unknown')
    ip_address = router_info.get('ip_address', 'Unknown')
    board_name = router_info.get('board_name', 'Unknown')
    
    # Process ROS version to exclude " (stable)"
    ros_version = ros_version_raw.split(' ')[0]  # "7.16.2 (stable)" -> "7.16.2"
    ros_version = f"ROS{ros_version}"  # "ROS7.16.2"
    
    backup_name = f"{router_name}-{ip_address}-{ros_version}-{architecture}-{timestamp}"

    # Define backup paths
    binary_backup = f"{backup_name}{BACKUP_EXT}"
    info_file = f"{backup_name}{INFO_EXT}"

    try:
        # Create binary backup
        if encrypted:
            backup_command = f'/system backup save name="{backup_name}" password="{backup_password}"'
        else:
            backup_command = f'/system backup save name="{backup_name}" dont-encrypt=yes'
        
        ssh_client.exec_command(backup_command)
        if encrypted:
            logging.info(f"Executed binary backup command: {mask_password(backup_command)}")
        else:
            logging.info(f"Executed binary backup command: {backup_command}")

        # Wait for the backup file to be created on the router
        time.sleep(5)  # Increased from 2 to 5 seconds to ensure file creation

        # Check if the .backup file exists on the router
        if not check_remote_file_exists(ssh_client, f"{binary_backup}"):
            logging.error(f"Binary backup file {binary_backup} does not exist on the router.")
            return False
        else:
            logging.info(f"Binary backup file {binary_backup} exists on the router.")

        # SCP the .backup file
        with SCPClient(ssh_client.get_transport()) as scp:
            remote_backup_path = f"{binary_backup}"
            local_backup_path = backup_dir / binary_backup
            scp.get(remote_backup_path, str(local_backup_path))
            logging.info(f"Downloaded {binary_backup}")

        # Remove remote .backup file if not keeping it
        if not keep_binary_backup:
            ssh_client.exec_command(f'file remove "{binary_backup}"')
            logging.info(f"Removed remote {binary_backup}")
        else:
            logging.info(f"Keeping remote {binary_backup} as per configuration.")

        return True
    except Exception as e:
        logging.error(f"Binary backup failed for {router_name} ({ip_address}): {e}")
        return False

def setup_logging_custom(log_file: Path, log_level: str = "INFO", enable_file_logging: bool = True):
    """
    Set up logging to both a file and the console based on the global configuration.

    If enable_file_logging is False, only console logging is set up.
    """
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to prevent duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler
    if enable_file_logging:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file), mode='a')
        file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    colored_formatter = ColoredFormatter('%(asctime)s [%(levelname)s] %(message)s')
    console_handler.setFormatter(colored_formatter)
    logger.addHandler(console_handler)

def cleanup_old_backups(backup_dir: Path, retention_days: int):
    """
    Deletes backup directories older than the specified retention period.

    Args:
        backup_dir (Path): Path to the backup directory.
        retention_days (int): Number of days to retain backups. -1 means keep forever.
    """
    if retention_days == -1:
        logging.info(f"Backup retention is set to forever. Skipping cleanup in {backup_dir}.")
        return

    cutoff_date = datetime.now() - timedelta(days=retention_days)
    for backup_subdir in backup_dir.iterdir():
        if backup_subdir.is_dir():
            try:
                # Extract timestamp from directory name
                # Expected format: <Identity>-<IP>-ROS<Version>-<Architecture>-<Timestamp>
                parts = backup_subdir.name.split('-')
                if len(parts) < 5:
                    logging.warning(f"Unexpected backup directory format: {backup_subdir.name}. Skipping.")
                    continue
                timestamp_str = parts[-1]
                backup_time = datetime.strptime(timestamp_str, "%m%d%Y-%H%M%S")
                if backup_time < cutoff_date:
                    # Remove the backup directory
                    for file in backup_subdir.glob("*"):
                        file.unlink()
                    backup_subdir.rmdir()
                    logging.info(f"Removed old backup directory: {backup_subdir}")
            except Exception as e:
                logging.error(f"Failed to remove old backup {backup_subdir}: {e}")

def backup_router(router: Dict, global_config: Dict, backup_path_parent: Path, ssh_args: Dict, backup_password: str, notifier: Notifications):
    """
    Perform backup for a single router.
    """
    ip_address = router.get("ip_address")
    ssh_port = router.get("ssh_port", 22)
    ssh_user = router.get("ssh_user", global_config.get("ssh_user", "backup"))
    private_key_raw = router.get("private_key", "ssh-keys/private/id_rsa_rosbackup")
    encrypted = router.get("encrypted", True)  # Existing option
    router_backup_password = router.get("backup_password", backup_password)
    backup_retention_days = router.get("backup_retention_days", global_config.get("backup_retention_days", -1))  # -1 means keep forever
    keep_binary_backup = router.get("keep_binary_backup", False)  # Existing option

    # New target-specific options
    enabled = router.get("enabled", True)  # Default to True
    enable_binary_backup = router.get("enable_binary_backup", True)  # Default to True
    enable_plaintext_backup = router.get("enable_plaintext_backup", True)  # Default to True

    name = router.get("name", "Unknown")

    private_key = Path(private_key_raw).expanduser()  # Expand '~' to the home directory

    if not ip_address:
        logging.error(f"IP address missing for router '{name}' in targets.json. Skipping.")
        return

    if not private_key.exists():
        logging.error(f"Private key not found for router '{name}' at {ip_address} ({private_key})")
        return

    # Check if the target is enabled before attempting SSH connection
    if not enabled:
        logging.info(f"Backup is disabled for router '{name}' at {ip_address}. Skipping backups and retention handling.")
        return

    # Format the "Starting backup" line in bold
    bold_start = "\033[1m"
    bold_end = "\033[0m"
    starting_backup_message = f"{bold_start}Starting backup for router '{name}' at {ip_address}{bold_end}"
    logging.info(starting_backup_message)

    ssh_client = create_ssh_client(
        host=ip_address,
        port=ssh_port,
        user=ssh_user,
        key_path=private_key,
        ssh_args=ssh_args
    )

    if not ssh_client:
        logging.error(f"Skipping backup for router '{name}' at {ip_address} due to SSH connection failure.")
        notifier.notify_backup(router=name, ip=ip_address, success=False, log_entries=[])
        return

    # Retrieve router information
    router_info = get_router_info(ssh_client)
    router_info['ip_address'] = ip_address

    # Log router_info for debugging
    logging.debug(f"Router Info for {ip_address}: {router_info}")

    # Generate client-side timestamp
    timestamp = datetime.now().strftime("%m%d%Y-%H%M%S")  # MMDDYYYY-HHMMSS

    # Define backup directory using router's actual identity
    backup_dir_name = f"{router_info.get('identity', 'Unknown')}-{ip_address}-ROS{router_info.get('version', 'Unknown').split(' ')[0]}-{router_info.get('architecture_name', 'Unknown')}"
    backup_dir = backup_path_parent / backup_dir_name
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Define plaintext backup path with .rsc extension
    plaintext_backup_name = f"{backup_dir_name}-{timestamp}{PLAINTEXT_EXT}"
    plaintext_backup_path = backup_dir / plaintext_backup_name

    # Define INFO file path
    info_file_name = f"{backup_dir_name}-{timestamp}{INFO_EXT}"
    info_file_path = backup_dir / info_file_name

    # Initialize a flag to track if any backup was performed
    backups_performed = False

    # Perform Plaintext Backup if enabled
    if enable_plaintext_backup:
        plaintext_success = perform_plaintext_backup(ssh_client, plaintext_backup_path)
        if plaintext_success:
            backups_performed = True
            # Save INFO file including license information
            info_success = save_info_file(router_info, info_file_path)
            if not info_success:
                logging.error(f"Failed to save INFO file for router '{name}' at {ip_address}")
        else:
            logging.error(f"Plaintext Backup failed for router '{name}' at {ip_address}")
    else:
        logging.info(f"Plaintext backup is disabled for router '{name}' at {ip_address}.")

    # Perform Binary Backup if enabled
    if enable_binary_backup:
        binary_success = perform_binary_backup(
            ssh_client,
            router_info,
            router_backup_password,
            encrypted,
            backup_dir,
            timestamp,
            keep_binary_backup
        )
        if binary_success:
            backups_performed = True
            logging.info(f"Backup completed for router '{name}' at {ip_address}")
        else:
            logging.error(f"Backup failed for router '{name}' at {ip_address}")
    else:
        logging.info(f"Binary backup is disabled for router '{name}' at {ip_address}.")

    # Perform backup retention cleanup only if backups were performed
    if backups_performed:
        cleanup_old_backups(backup_dir, backup_retention_days)
    else:
        logging.info(f"No backups performed for router '{name}' at {ip_address}'. Skipping backup retention handling.")

    # Close SSH connection
    ssh_client.close()
    logging.info("SSH connection closed.")

    # Determine if notification should be sent
    backup_success = backups_performed
    if backup_success and global_config.get("notify_on_successful_backups", False):
        notifier.notify_backup(router=name, ip=ip_address, success=True, log_entries=[])
    elif not backup_success and global_config.get("notify_on_failed_backups", True):
        # Collect relevant log entries for this router from the log file
        # Assuming log entries are time-ordered and within a short timeframe
        # For simplicity, we'll pass an empty list. Enhancements can include parsing the log file.
        notifier.notify_backup(router=name, ip=ip_address, success=False, log_entries=[])
    else:
        # No notification needed
        pass

def main():
    """Main function to execute the backup process."""
    # Define paths
    base_dir = Path(__file__).resolve().parent
    config_dir = base_dir / "config"
    global_config_path = config_dir / "global.json"
    targets_config_path = config_dir / "targets.json"

    # Load configurations
    if not global_config_path.exists() or not targets_config_path.exists():
        print("Configuration files missing. Please check the config directory.")
        sys.exit(1)

    global_config = load_config(global_config_path)
    targets_config = load_config(targets_config_path)

    # Setup logging
    log_file_relative = global_config.get("log_file", "./rosbackup.log")
    log_file = base_dir / log_file_relative
    log_level = global_config.get("log_level", "INFO")
    enable_file_logging = global_config.get("enable_file_logging", True)  # New option
    setup_logging_custom(log_file, log_level, enable_file_logging)

    # Initialize Notifications
    notifications_enabled = global_config.get("notifications_enabled", False)
    notify_on_failed_backups = global_config.get("notify_on_failed_backups", True)
    notify_on_successful_backups = global_config.get("notify_on_successful_backups", False)

    if notify_on_successful_backups:
        notify_on_failed_backups = True  # Automatically force notifications for failed backups

    notifier = Notifications(
        enabled=notifications_enabled,
        notify_on_failed=notify_on_failed_backups,
        notify_on_success=notify_on_successful_backups,
        smtp_config=global_config.get("smtp", {})
    )

    backup_path_parent = base_dir / global_config.get("backup_path_parent", "backups")
    backup_password = global_config.get("backup_password", "")
    ssh_args = global_config.get("ssh_args", {})
    parallel_execution = global_config.get("parallel_execution", False)
    max_parallel_backups = global_config.get("max_parallel_backups", 5)

    routers: List[Dict] = targets_config.get("routers", [])
    if not routers:
        logging.error("No routers defined in targets.json")
        sys.exit(1)

    if parallel_execution:
        logging.info("Parallel execution enabled.")
        max_workers = max_parallel_backups if isinstance(max_parallel_backups, int) else 5
        logging.info(f"Max parallel backups set to: {max_workers}")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    backup_router,
                    router,
                    global_config,
                    backup_path_parent,
                    ssh_args,
                    backup_password,
                    notifier
                )
                for router in routers
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"Exception during backup: {e}")
    else:
        logging.info("Sequential execution enabled.")
        for router in routers:
            backup_router(router, global_config, backup_path_parent, ssh_args, backup_password, notifier)

    logging.info("All backups completed.")

    # Perform log retention cleanup
    log_retention_days = global_config.get("log_retention_days", 90)  # Default to 90 days
    if log_retention_days != -1:
        try:
            log_dir = log_file.parent
            cutoff_date = datetime.now() - timedelta(days=log_retention_days)
            for log_file_path in log_dir.glob("*.log"):
                file_mod_time = datetime.fromtimestamp(log_file_path.stat().st_mtime)
                if file_mod_time < cutoff_date:
                    log_file_path.unlink()
                    logging.info(f"Removed old log file: {log_file_path}")
        except Exception as e:
            logging.error(f"Failed to cleanup old log files: {e}")
    else:
        logging.info("Log retention is set to forever. Skipping log cleanup.")

if __name__ == "__main__":
    main()

