#!/usr/bin/env python3
"""
RouterOS Backup Script.

This script performs automated backups of RouterOS devices, supporting both
binary and plaintext backups with encryption and parallel execution.
"""

import argparse
import concurrent.futures
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, TypedDict, Any

import yaml
from zoneinfo import ZoneInfo
from tzlocal import get_localzone

from core.backup_utils import BackupManager
from core.logging_utils import LogManager
from core.notification_utils import NotificationManager
from core.router_utils import RouterInfoManager
from core.shell_utils import ColoredFormatter
from core.ssh_utils import SSHManager
from core.time_utils import get_timezone, get_system_timezone, get_current_time

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
    parser.add_argument('--no-parallel', action='store_true',
                       help='Disable parallel execution')
    parser.add_argument('--max-parallel', type=int,
                       help='Override maximum parallel backups')
    parser.add_argument('--target', type=str,
                       help='Run backup on specific target only')

    return parser.parse_args()


class GlobalConfig(TypedDict, total=False):
    """
    Type definition for global configuration.

    Attributes:
        backup_path: Path to store backups
        backup_password: Global backup password
        parallel_backups: Enable parallel backups
        max_parallel: Maximum parallel backups
        notifications: Notification configuration
        ssh: SSH configuration
        timezone: Optional timezone for timestamps (e.g. Europe/Berlin)
    """
    backup_path: str
    backup_password: str
    parallel_backups: bool
    max_parallel: int
    notifications: Dict[str, Any]
    ssh: Dict[str, Any]
    timezone: str


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


def get_timestamp(config: Optional[GlobalConfig] = None) -> str:
    """
    Get current timestamp in backup file format.
    
    Args:
        config: Optional global config containing timezone setting
        
    Returns:
        str: Formatted timestamp string in MMDDYYYY-HHMMSS format
    """
    logger = LogManager().system
    logger.debug(f"Getting timestamp with config: {config}")
    
    # Get timezone from config if available
    tz = get_timezone(config['timezone'] if config and 'timezone' in config else None)
    logger.debug(f"Using timezone: {tz}")
    
    # Generate timestamp in specified timezone
    current_time = get_current_time()
    if tz:
        current_time = current_time.astimezone(tz)
    
    # Format timestamp
    return current_time.strftime("%m%d%Y-%H%M%S")


def backup_target(
    target: Dict[str, Any],
    ssh_args: Dict[str, Any],
    backup_password: str,
    notifier: NotificationManager,
    backup_path: Path,
    dry_run: bool = False,
    config: Optional[GlobalConfig] = None
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
        config: Optional global configuration

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
            target.get('ssh_user', config['ssh'].get('user', 'rosbackup')),
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
        timestamp = get_timestamp(config)
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

    # Load global configuration first to get timezone
    global_config_file = Path(args.config_dir) / 'global.yaml'
    if not global_config_file.exists():
        print(f"Global configuration file not found: {global_config_file}")
        sys.exit(1)

    with open(global_config_file) as f:
        global_config_data = yaml.safe_load(f)
        
    # Configure timezone before setting up logging
    if 'timezone' in global_config_data:
        os.environ['TZ'] = global_config_data['timezone']

    # Set up logging with correct timezone
    setup_logging(
        log_file=args.log_file,
        log_level=args.log_level,
        use_colors=not args.no_color
    )
    logger = LogManager().system
        
    # Convert to GlobalConfig TypedDict
    global_config: GlobalConfig = {
        'backup_path': global_config_data.get('backup_path_parent', 'backups'),
        'backup_password': global_config_data.get('backup_password', ''),
        'parallel_backups': global_config_data.get('parallel_execution', False),
        'max_parallel': global_config_data.get('max_parallel_backups', 4),
        'notifications': global_config_data.get('notifications', {}),
        'ssh': global_config_data.get('ssh', {}),
    }

    # Apply CLI overrides for parallel execution settings
    if args.no_parallel:
        global_config['parallel_backups'] = False
        logger.info("Parallel execution disabled via CLI")
    if args.max_parallel is not None:
        if args.max_parallel < 1:
            logger.error("max-parallel must be at least 1")
            sys.exit(1)
        global_config['max_parallel'] = args.max_parallel
        logger.info(f"Maximum parallel backups set to {args.max_parallel} via CLI")
    
    # Handle timezone
    if 'timezone' in global_config_data:
        system_tz = get_system_timezone()
        logger.info(f"Using timezone: {global_config_data['timezone']}")
        global_config['timezone'] = global_config_data['timezone']
        # Set timezone for logging
        LogManager().set_timezone(get_timezone(global_config['timezone']))

    logger.debug(f"Loaded global config: {global_config_data}")
        
    # Set up backup directory
    backup_path = Path(global_config['backup_path'])
    os.makedirs(backup_path, exist_ok=True)

    # Initialize notification system
    notifier = NotificationManager(
        enabled=global_config['notifications'].get('enabled', False),
        notify_on_failed=global_config['notifications'].get('notify_on_failed_backups', True),
        notify_on_success=global_config['notifications'].get('notify_on_successful_backups', False),
        smtp_config={
            'enabled': global_config['notifications'].get('smtp', {}).get('enabled', False),
            'host': global_config['notifications'].get('smtp', {}).get('host', 'localhost'),
            'port': global_config['notifications'].get('smtp', {}).get('port', 25),
            'username': global_config['notifications'].get('smtp', {}).get('username'),
            'password': global_config['notifications'].get('smtp', {}).get('password'),
            'from_email': global_config['notifications'].get('smtp', {}).get('from_email'),
            'to_emails': global_config['notifications'].get('smtp', {}).get('to_emails', []),
            'use_ssl': global_config['notifications'].get('smtp', {}).get('use_ssl', False),
            'use_tls': global_config['notifications'].get('smtp', {}).get('use_tls', True)
        }
    )

    # Load SSH configuration
    ssh_config = global_config['ssh']
    ssh_args = {
        'timeout': ssh_config.get('timeout', 30),
        'auth_timeout': ssh_config.get('auth_timeout', 30),
        'banner_timeout': ssh_config.get('banner_timeout', 60),
        'transport_factory': ssh_config.get('transport_factory', None)
    }

    # Load target configurations
    targets_file = Path(args.config_dir) / 'targets.yaml'
    if not targets_file.exists():
        logger.error(f"Target configuration file not found: {targets_file}")
        sys.exit(1)

    with open(targets_file) as f:
        targets_data = yaml.safe_load(f)

    if not targets_data or 'targets' not in targets_data:
        logger.error("No targets found in configuration")
        sys.exit(1)

    # Filter targets if --target is specified
    if args.target:
        targets = [t for t in targets_data['targets'] if t.get('name') == args.target]
        if not targets:
            logger.error(f"Target '{args.target}' not found in configuration")
            sys.exit(1)
        logger.info(f"Running backup for target '{args.target}' only")
    else:
        targets = targets_data['targets']

    # Filter enabled targets
    targets = [t for t in targets if t.get('enabled', True)]

    # Get global backup password
    backup_password = global_config.get('backup_password', '')

    # Execute backups
    parallel_backups = global_config.get('parallel_backups', False)
    max_parallel = global_config.get('max_parallel', 4)

    if args.dry_run:
        logger.info("Running in dry-run mode - no changes will be made")

    if parallel_backups:
        logger.info(f"Parallel execution enabled.")
        logger.info(f"Max parallel backups set to: {max_parallel}")

    successful_backups = 0
    failed_backups = 0

    if parallel_backups:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = [
                executor.submit(backup_target, target, ssh_args, backup_password, notifier, backup_path, args.dry_run, global_config)
                for target in targets
            ]
            for future in concurrent.futures.as_completed(futures):
                if future.result():
                    successful_backups += 1
                else:
                    failed_backups += 1
    else:
        for target in targets:
            if backup_target(target, ssh_args, backup_password, notifier, backup_path, args.dry_run, global_config):
                successful_backups += 1
            else:
                failed_backups += 1

    elapsed_time = datetime.now() - start_time
    minutes, seconds = divmod(elapsed_time.seconds, 60)

    # Log completion
    if failed_backups == 0:
        logger.info(f"Backup completed. Success: {successful_backups}, Failed: {failed_backups} [{minutes}m {seconds}s]")
        sys.exit(0)
    else:
        logger.error(f"Backup completed. Success: {successful_backups}, Failed: {failed_backups} [{minutes}m {seconds}s]")
        sys.exit(1)

def setup_logging(log_file: Optional[str], log_level: str = 'INFO', use_colors: bool = True):
    """
    Set up logging configuration.

    Args:
        log_file: Optional log file path
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        use_colors: Whether to use colors in console output
    """
    # Set color environment variables before any color-related imports
    if not use_colors:
        os.environ['NO_COLOR'] = '1'
        if 'FORCE_COLOR' in os.environ:
            del os.environ['FORCE_COLOR']
    else:
        os.environ['FORCE_COLOR'] = '1'
        if 'NO_COLOR' in os.environ:
            del os.environ['NO_COLOR']

    # Initialize log manager
    log_manager = LogManager()
    log_manager.setup(
        log_level=log_level,
        log_file=log_file,
        use_colors=use_colors
    )

if __name__ == '__main__':
    main()
