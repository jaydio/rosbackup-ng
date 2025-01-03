#!/usr/bin/env python3
"""
RouterOS Backup Script.

This script performs automated backups of RouterOS devices, supporting both
binary and plaintext backups with encryption and parallel execution.
"""

# Initialize colorama before any imports that might use colors
import os
os.environ['FORCE_COLOR'] = '1'
os.environ['CLICOLOR_FORCE'] = '1'
import colorama
colorama.init(autoreset=False, strip=False, convert=True, wrap=True)

import sys
import yaml
import argparse
import concurrent.futures
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, TypedDict
import logging

from core.ssh_utils import SSHManager
from core.router_utils import RouterInfoManager
from core.backup_utils import BackupManager
from core.notification_utils import NotificationManager
from core.logging_utils import LogManager
from core.shell_utils import ColoredFormatter


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Automated RouterOS backup utility",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('-c', '--config-dir', default='./config',
                       help='Directory containing configuration files')
    parser.add_argument('-l', '--log-file',
                       help='Override log file path')
    parser.add_argument('-L', '--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Logging level')
    parser.add_argument('-n', '--no-color', action='store_true',
                       help='Disable colored output')
    parser.add_argument('-d', '--dry-run', action='store_true',
                       help='Simulate operations without making changes')

    return parser.parse_args()


class GlobalConfig(TypedDict):
    """
    Type definition for global configuration.

    Attributes:
        backup_path: Path to store backups
        backup_password: Global backup password
        parallel_backups: Enable parallel backups
        max_parallel: Maximum parallel backups
        notifications: Notification configuration
        ssh: SSH configuration
    """
    backup_path: str
    backup_password: str
    parallel_backups: bool
    max_parallel: int
    notifications: Dict[str, Any]
    ssh: Dict[str, Any]


class TargetConfig(TypedDict):
    """
    Type definition for target configuration.

    Attributes:
        name: Target name
        host: Hostname or IP address
        port: SSH port
        ssh_user: SSH username
        private_key: Path to SSH private key
        encrypted: Enable backup encryption
        keep_binary_backup: Keep binary backup on target
        keep_plaintext_backup: Keep plaintext backup on target
        backup_password: Target-specific backup password
    """
    name: str
    host: str
    port: int
    ssh_user: str
    private_key: str
    encrypted: bool
    keep_binary_backup: bool
    keep_plaintext_backup: bool
    backup_password: Optional[str]


def get_timestamp() -> str:
    """Get current timestamp in backup file format."""
    return datetime.now().strftime("%d%m%Y-%H%M%S")


def backup_target(
    target: Dict[str, Any],
    ssh_args: Dict[str, Any],
    backup_password: str,
    notifier: NotificationManager,
    backup_path: Path,
    dry_run: bool = False
) -> bool:
    """
    Backup a single target's configuration.

    Args:
        target: Target configuration dictionary
        ssh_args: SSH connection arguments
        backup_password: Password for encrypted backups
        notifier: Notification manager
        backup_path: Path to store backups
        dry_run: If True, simulate operations

    Returns:
        bool: True if backup successful, False otherwise

    Error Handling:
        - SSH connection failures
        - Target information retrieval errors
        - Backup creation and download issues
        - File system operations
        - Notification sending failures
    """
    # Get target-specific logger
    logger = LogManager().get_logger('BACKUP', target.get('name', 'UNKNOWN'))

    if dry_run:
        logger.info(f"[DRY RUN] Would backup target: {target.get('name', 'UNKNOWN')}")
        return True

    # Initialize managers
    ssh_manager = SSHManager(ssh_args, target.get('name', 'UNKNOWN'))
    target_info_manager = RouterInfoManager(ssh_manager, target.get('name', 'UNKNOWN'))
    backup_manager = BackupManager(ssh_manager, target_info_manager, logger)

    try:
        # Create SSH connection
        ssh_client = ssh_manager.create_client(
            target['host'],
            target.get('port', 22),
            target['ssh_user'],
            str(Path(target['private_key']))
        )

        if not ssh_client:
            logger.error(f"Failed to establish SSH connection to {target['host']}")
            return False

        # Get target information
        target_info = target_info_manager.get_router_info(ssh_client)
        if not target_info:
            logger.error("Failed to retrieve target information")
            return False

        # Prepare backup directory
        timestamp = get_timestamp()
        clean_version = backup_manager._clean_version_string(target_info['ros_version'])
        backup_dir = backup_path / f"{target_info['identity']}_{target['host']}_ROS{clean_version}_{target_info['architecture_name']}"
        os.makedirs(backup_dir, exist_ok=True)

        success = True
        backup_files = []

        # Perform binary backup
        keep_binary_backup = target.get('keep_binary_backup', True)
        enable_binary_backup = target.get('enable_binary_backup', True)
        if enable_binary_backup:
            binary_success, binary_file = backup_manager.perform_binary_backup(
                ssh_client,
                target_info,
                backup_password,
                target.get('encrypted', False),
                backup_dir,
                timestamp,
                keep_binary_backup,
                dry_run
            )
            success &= binary_success
            if binary_file:
                backup_files.append(binary_file)

        # Perform plaintext backup
        keep_plaintext_backup = target.get('keep_plaintext_backup', True)
        enable_plaintext_backup = target.get('enable_plaintext_backup', True)
        if enable_plaintext_backup:
            plaintext_success, plaintext_file = backup_manager.perform_plaintext_backup(
                ssh_client,
                target_info,
                backup_dir,
                timestamp,
                keep_plaintext_backup,
                dry_run
            )
            success &= plaintext_success
            if plaintext_file:
                backup_files.append(plaintext_file)

        # Save target information
        clean_version = backup_manager._clean_version_string(target_info['ros_version'])
        info_file = backup_dir / f"{target_info['identity']}_{clean_version}_{target_info['architecture_name']}_{timestamp}.INFO.txt"
        info_success = backup_manager.save_info_file(target_info, info_file, dry_run)
        success &= info_success

        # Close SSH connection
        ssh_client.close()
        logger.debug("SSH connection closed")

        # Send notification
        if success:
            notifier.notify_backup(target.get('name', 'UNKNOWN'), target['host'], True, [])
        else:
            notifier.notify_backup(target.get('name', 'UNKNOWN'), target['host'], False, ["Backup operation failed"])

        return success

    except Exception as e:
        logger.error(f"Target {target.get('name', 'UNKNOWN')} backup failed: {str(e)}")
        try:
            notifier.notify_backup(target.get('name', 'UNKNOWN'), target['host'], False, [str(e)])
        except Exception as notify_error:
            logger.warning(f"Failed to send notification: {str(notify_error)}")
        return False


def main() -> None:
    """
    Main function to execute the backup process.

    This function:
    1. Parses command line arguments
    2. Loads configuration files
    3. Sets up logging and notifications
    4. Executes backups (parallel or sequential)
    5. Reports final status

    Error Handling:
        - Configuration file loading errors
        - Invalid configuration values
        - Parallel execution failures
        - Individual target backup failures
    """
    start_time = datetime.now()
    args = parse_arguments()

    # Set up logging first
    setup_logging(args.log_file, not args.no_color)
    logger = LogManager().system

    try:
        # Load global configuration
        global_config_file = Path(args.config_dir) / 'global.yaml'
        if not global_config_file.exists():
            logger.error(f"Global configuration file not found: {global_config_file}")
            sys.exit(1)

        with open(global_config_file) as f:
            global_config = yaml.safe_load(f)

        # Set up backup directory
        backup_path = Path(global_config.get('backup_path_parent', 'backups'))
        os.makedirs(backup_path, exist_ok=True)

        # Initialize notification system
        notifier = NotificationManager(
            enabled=global_config.get('notifications_enabled', False),
            notify_on_failed=global_config.get('notify_on_failed_backups', True),
            notify_on_success=global_config.get('notify_on_successful_backups', False),
            smtp_config={
                'enabled': global_config.get('smtp', {}).get('enabled', False),
                'host': global_config.get('smtp', {}).get('host', 'localhost'),
                'port': global_config.get('smtp', {}).get('port', 25),
                'username': global_config.get('smtp', {}).get('username'),
                'password': global_config.get('smtp', {}).get('password'),
                'from_email': global_config.get('smtp', {}).get('from_email'),
                'to_emails': global_config.get('smtp', {}).get('to_emails', []),
                'use_ssl': global_config.get('smtp', {}).get('use_ssl', False),
                'use_tls': global_config.get('smtp', {}).get('use_tls', True)
            }
        )

        # Load SSH configuration
        ssh_config = global_config.get('ssh', {})
        ssh_args = {
            'timeout': ssh_config.get('timeout', 30),
            'auth_timeout': ssh_config.get('auth_timeout', 30),
            'known_hosts_file': ssh_config.get('known_hosts_file'),
            'add_target_host_key': ssh_config.get('add_target_host_key', True),
            'look_for_keys': ssh_config.get('args', {}).get('look_for_keys', False),
            'allow_agent': ssh_config.get('args', {}).get('allow_agent', False)
        }

        # Load target configurations
        targets_file = Path(args.config_dir) / 'targets.yaml'
        if not targets_file.exists():
            logger.error(f"Targets configuration file not found: {targets_file}")
            sys.exit(1)

        with open(targets_file) as f:
            targets_config = yaml.safe_load(f)

        targets = targets_config.get('targets', [])
        if not targets:
            logger.error("No targets found in targets file")
            sys.exit(1)

        # Get global backup password
        backup_password = global_config.get('backup_password', '')

        # Execute backups
        parallel_backups = global_config.get('parallel_execution', False)
        max_parallel = global_config.get('max_parallel_backups', 4)

        if args.dry_run:
            logger.info("Running in dry-run mode - no changes will be made")

        if parallel_backups:
            logger.info(f"[SYSTEM] Parallel execution enabled.")
            logger.info(f"[SYSTEM] Max parallel backups set to: {max_parallel}")

        successful_backups = 0
        failed_backups = 0

        if parallel_backups:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
                futures = [
                    executor.submit(backup_target, target, ssh_args, backup_password, notifier, backup_path, args.dry_run)
                    for target in targets
                ]
                for future in concurrent.futures.as_completed(futures):
                    if future.result():
                        successful_backups += 1
                    else:
                        failed_backups += 1
        else:
            for target in targets:
                if backup_target(target, ssh_args, backup_password, notifier, backup_path, args.dry_run):
                    successful_backups += 1
                else:
                    failed_backups += 1

        elapsed_time = datetime.now() - start_time
        minutes, seconds = divmod(elapsed_time.seconds, 60)
        
        if failed_backups == 0:
            logger.info(f"[SYSTEM] Backup completed. Success: {successful_backups}, Failed: {failed_backups} [{minutes}m {seconds}s]")
            sys.exit(0)
        else:
            logger.error(f"[SYSTEM] Backup completed. Success: {successful_backups}, Failed: {failed_backups} [{minutes}m {seconds}s]")
            sys.exit(1)

    except Exception as e:
        elapsed_time = datetime.now() - start_time
        minutes, seconds = divmod(elapsed_time.seconds, 60)
        logger.error(f"[SYSTEM] Backup process failed: {str(e)} [{minutes}m {seconds}s]")
        sys.exit(1)


def setup_logging(log_file: Optional[str], use_colors: bool = True) -> None:
    """
    Set up logging configuration.

    Args:
        log_file: Optional log file path
        use_colors: Whether to use colors in console output
    """
    LogManager().configure(
        log_level=logging.INFO,
        use_colors=use_colors,
        log_file=log_file
    )


if __name__ == '__main__':
    main()
