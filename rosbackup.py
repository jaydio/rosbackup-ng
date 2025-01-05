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
from tqdm import tqdm
from zoneinfo import ZoneInfo
from tzlocal import get_localzone

from core import (
    BackupManager,
    SSHManager,
    RouterInfoManager,
    NotificationManager,
    LogManager,
    ColoredFormatter,
    ShellPbarHandler
)
from core.backup_utils import BackupManager
from core.logging_utils import LogManager
from core.notification_utils import NotificationManager
from core.router_utils import RouterInfoManager
from core.shell_utils import ColoredFormatter, ShellPbarHandler
from core.ssh_utils import SSHManager
from core.time_utils import get_timezone, get_system_timezone, get_current_time

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Automated RouterOS backup utility")
    parser.add_argument("-c", "--config-dir", default="config",
                       help="Directory containing configuration files")
    parser.add_argument("-l", "--log-file",
                       help="Override log file path")
    parser.add_argument("-L", "--log-level",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       default="INFO", help="Logging level")
    parser.add_argument("-n", "--no-color", action="store_true",
                       help="Disable colored output")
    parser.add_argument("-d", "--dry-run", action="store_true",
                       help="Simulate operations without making changes")
    parser.add_argument("-p", "--no-parallel", action="store_true",
                       help="Disable parallel execution")
    parser.add_argument("-m", "--max-parallel", type=int,
                       help="Override maximum parallel backups")
    parser.add_argument("-t", "--target",
                       help="Run backup on specific target only")
    parser.add_argument("-b", "--progress-bar", action="store_true",
                       help="Show progress bar during parallel execution (disables scrolling output)")

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
        enabled: Whether this target is enabled
        ssh: SSH configuration dictionary containing:
            - port: SSH port number
            - user: SSH username
            - private_key: Path to SSH private key
            - args: Additional SSH arguments
        encrypted: Enable backup encryption
        enable_binary_backup: Enable binary backup creation
        enable_plaintext_backup: Enable plaintext backup creation
        keep_binary_backup: Keep binary backup on target
        keep_plaintext_backup: Keep plaintext backup on target
        backup_password: Target-specific backup password
        backup_retention_days: Target-specific retention period
    """
    name: str
    host: str
    enabled: bool
    ssh: Dict[str, Any]
    encrypted: bool
    enable_binary_backup: bool
    enable_plaintext_backup: bool
    keep_binary_backup: bool
    keep_plaintext_backup: bool
    backup_password: Optional[str]
    backup_retention_days: Optional[int]


def get_timestamp(tz: Optional[ZoneInfo] = None) -> str:
    """
    Get current timestamp in backup file format.
    
    Args:
        tz: Optional timezone for timestamp
        
    Returns:
        str: Formatted timestamp string in MMDDYYYY-HHMMSS format
    """
    logger = LogManager().system
    logger.debug(f"Getting timestamp with timezone: {tz}")
    
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
    config: Optional[GlobalConfig] = None,
    progress_callback: Optional[callable] = None
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
        progress_callback: Optional callback for progress updates

    Returns:
        bool: True if backup successful, False otherwise

    Error Handling:
        - SSH connection failures
        - Target information retrieval errors
        - Backup creation and download issues
        - File system operations
        - Notification sending failures
    """
    target_name = target.get('name', target.get('host', 'Unknown'))
    logger = LogManager().get_logger('BACKUP', target_name)

    if dry_run:
        logger.info(f"[DRY RUN] Would backup target: {target_name}")
        return True

    try:
        if progress_callback:
            progress_callback(1, f"{target_name} (Connecting)")

        # Initialize managers
        ssh = SSHManager(ssh_args, target_name)
        router_info = RouterInfoManager(ssh, target_name)
        backup_manager = BackupManager(ssh, router_info, logger)
        
        # Get private key path from target or global config
        key_path = target.get('private_key', ssh_args.get('private_key'))
        if not key_path:
            logger.error("No private key specified in target or global config")
            return False

        # Get SSH user from target or global config
        ssh_user = target.get('ssh_user', ssh_args.get('user', 'rosbackup'))

        # Create SSH client
        ssh_client = ssh.create_client(
            host=target['host'],
            port=target.get('port', 22),
            username=ssh_user,
            key_path=key_path
        )
        
        if not ssh_client:
            logger.error("Failed to establish SSH connection")
            return False

        if progress_callback:
            progress_callback(2, f"{target_name} (Getting Info)")

        # Get router information
        router_info_dict = router_info.get_router_info(ssh_client)
        if not router_info_dict:
            logger.error("Failed to retrieve router information")
            return False

        if progress_callback:
            progress_callback(3, f"{target_name} (Creating Backup)")

        # Create backup directory
        timestamp = get_timestamp(get_timezone(config.get('timezone') if config else None))
        clean_version = backup_manager._clean_version_string(router_info_dict['ros_version'])
        backup_dir = backup_path / f"{router_info_dict['identity']}_{target['host']}_ROS{clean_version}_{router_info_dict['architecture_name']}"
        os.makedirs(backup_dir, exist_ok=True)

        # Save router info file
        info_file = backup_dir / f"{router_info_dict['identity']}_{clean_version}_{router_info_dict['architecture_name']}_{timestamp}.info"
        if not backup_manager.save_info_file(router_info_dict, info_file, dry_run):
            logger.error("Failed to save router info file")
            return False

        # Perform binary backup if enabled
        binary_success = True
        if target.get('enable_binary_backup', True):
            binary_success, binary_file = backup_manager.perform_binary_backup(
                ssh_client=ssh_client,
                router_info=router_info_dict,
                backup_password=target.get('backup_password', backup_password),
                encrypted=target.get('encrypted', True),
                backup_dir=backup_dir,
                timestamp=timestamp,
                keep_binary_backup=target.get('keep_binary_backup', False),
                dry_run=dry_run
            )
            if not binary_success:
                logger.error("Binary backup failed")
                return False

        # Perform plaintext backup if enabled
        plaintext_success = True
        plaintext_file = None
        if target.get('enable_plaintext_backup', True):
            plaintext_success, plaintext_file = backup_manager.perform_plaintext_backup(
                ssh_client=ssh_client,
                router_info=router_info_dict,
                backup_dir=backup_dir,
                timestamp=timestamp,
                keep_plaintext_backup=target.get('keep_plaintext_backup', False),
                dry_run=dry_run
            )
            if not plaintext_success:
                logger.error("Plaintext backup failed")
                return False

        # Both backups succeeded
        if binary_success and plaintext_success:
            if notifier.enabled and notifier.notify_on_success:
                notifier.send_success_notification(target_name)
            return True
        else:
            logger.error("One or more backup operations failed")
            if notifier.enabled and notifier.notify_on_failed:
                notifier.send_failure_notification(target_name)
            return False

    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        if notifier.enabled and notifier.notify_on_failed:
            notifier.send_failure_notification(target_name, str(e))
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
    log_manager = LogManager()
    if args.progress_bar:
        log_manager.setup(log_level='ERROR')
    else:
        log_manager.setup(log_level=args.log_level, log_file=args.log_file)
    logger = log_manager.get_logger('SYSTEM')

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
        if not args.progress_bar:
            logger.info("Parallel execution disabled via CLI")
    if args.max_parallel is not None:
        if args.max_parallel < 1:
            logger.error("max-parallel must be at least 1")
            sys.exit(1)
        global_config['max_parallel'] = args.max_parallel
        if not args.progress_bar:
            logger.info(f"Maximum parallel backups set to {args.max_parallel} via CLI")
    
    # Handle timezone
    if 'timezone' in global_config_data:
        system_tz = get_system_timezone()
        if not args.progress_bar:
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
        'look_for_keys': ssh_config.get('args', {}).get('look_for_keys', False),
        'allow_agent': ssh_config.get('args', {}).get('allow_agent', False),
        'compress': ssh_config.get('args', {}).get('compress', True),
        'auth_timeout': ssh_config.get('args', {}).get('auth_timeout', 5),
        'channel_timeout': ssh_config.get('args', {}).get('channel_timeout', 5),
        'disabled_algorithms': ssh_config.get('args', {}).get('disabled_algorithms', {}),
        'keepalive_interval': ssh_config.get('args', {}).get('keepalive_interval', 60),
        'keepalive_countmax': ssh_config.get('args', {}).get('keepalive_countmax', 3),
        'timeout': ssh_config.get('timeout', 5),
        'known_hosts_file': ssh_config.get('known_hosts_file'),
        'add_target_host_key': ssh_config.get('add_target_host_key', True),
        'user': ssh_config.get('user', 'rosbackup'),
        'private_key': ssh_config.get('private_key')
    }

    # Load target configurations
    targets_file = Path(args.config_dir) / 'targets.yaml'
    if not targets_file.exists():
        logger.error(f"Targets configuration file not found: {targets_file}")
        sys.exit(1)

    with open(targets_file) as f:
        targets_data = yaml.safe_load(f).get('targets', [])

    if not targets_data:
        logger.error("No targets found in configuration")
        sys.exit(1)

    # Filter targets if --target is specified
    if args.target:
        targets_data = [t for t in targets_data if t.get('name') == args.target or t.get('host') == args.target]
        if not targets_data:
            logger.error(f"Target not found: {args.target}")
            sys.exit(1)
        if not args.progress_bar:
            logger.info(f"Running backup for target: {args.target}")

    # Filter enabled targets
    targets_data = [t for t in targets_data if t.get('enabled', True)]
    if not args.progress_bar:
        logger.info(f"Found {len(targets_data)} enabled target(s)")

    # Initialize progress bar if requested
    if args.progress_bar:
        pbar = ShellPbarHandler(
            total=len(targets_data),
            desc="Backup Progress",
            position=0,
            leave=True,
            ncols=80,
            bar_format='{desc:<20} {percentage:3.0f}%|{bar:40}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
        )
    else:
        pbar = None

    # Execute backups
    success_count = 0
    failure_count = 0

    if global_config['parallel_backups'] and len(targets_data) > 1:
        max_workers = min(global_config['max_parallel'], len(targets_data))
        if not args.progress_bar:
            logger.info(f"Running parallel backup with {max_workers} workers")

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for target in targets_data:
                    # Merge target-specific SSH configuration
                    target_ssh = target.get('ssh', {})
                    target_ssh_args = target_ssh.get('args', {})
                    target_ssh_args.update({
                        'port': target_ssh.get('port', 22),
                        'username': target_ssh.get('user', ssh_args.get('user', 'rosbackup')),
                        'private_key': target_ssh.get('private_key', ssh_args.get('private_key'))
                    })
                    
                    # Create a copy of global SSH args and update with target-specific args
                    target_args = ssh_args.copy()
                    target_args.update(target_ssh_args)

                    future = executor.submit(
                        backup_target,
                        target=target,
                        ssh_args=target_args,
                        backup_password=global_config['backup_password'],
                        notifier=notifier,
                        backup_path=backup_path,
                        dry_run=args.dry_run,
                        config=global_config
                    )
                    futures.append(future)

                for future in concurrent.futures.as_completed(futures):
                    try:
                        if future.result():
                            success_count += 1
                        if pbar:
                            pbar.update(1)
                    except Exception as e:
                        logger.error(f"Backup failed: {str(e)}")
                        failure_count += 1
                        if pbar:
                            pbar.update(1)
        finally:
            if pbar:
                pbar.close()
    else:
        if not args.progress_bar and len(targets_data) > 1:
            logger.info("Running sequential backup")

        try:
            for target in targets_data:
                target_name = target.get('name', target.get('host', 'Unknown'))
                try:
                    # Merge target-specific SSH configuration
                    target_ssh = target.get('ssh', {})
                    target_ssh_args = target_ssh.get('args', {})
                    target_ssh_args.update({
                        'port': target_ssh.get('port', 22),
                        'username': target_ssh.get('user', ssh_args.get('user', 'rosbackup')),
                        'private_key': target_ssh.get('private_key', ssh_args.get('private_key'))
                    })
                    
                    # Create a copy of global SSH args and update with target-specific args
                    target_args = ssh_args.copy()
                    target_args.update(target_ssh_args)

                    success = backup_target(
                        target=target,
                        ssh_args=target_args,
                        backup_password=global_config['backup_password'],
                        notifier=notifier,
                        backup_path=backup_path,
                        dry_run=args.dry_run,
                        config=global_config
                    )
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                    if pbar:
                        pbar.update(1)
                except Exception as e:
                    logger.error(f"Backup failed for {target_name}: {str(e)}")
                    failure_count += 1
                    if pbar:
                        pbar.update(1)
        finally:
            if pbar:
                pbar.close()

    # Log final status
    duration = datetime.now() - start_time
    duration_str = f"{duration.seconds//60}m {duration.seconds%60}s"
    logger.info(f"Backup completed. Success: {success_count}, Failed: {failure_count} [{duration_str}]")

    if failure_count > 0:
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
