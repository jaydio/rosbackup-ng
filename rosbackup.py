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
    logger = LogManager().get_logger(target_name)

    try:
        if progress_callback:
            progress_callback(1, f"{target_name} (Connecting)")

        # Initialize SSH manager
        ssh = SSHManager(ssh_args, target_name)
        
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
            username=ssh_user,  # Use target-specific or global SSH user
            key_path=key_path
        )
        
        if not ssh_client:
            logger.error("Failed to establish SSH connection")
            return False

        if progress_callback:
            progress_callback(2, f"{target_name} (Getting Info)")

        # Get router information
        router_info = RouterInfoManager(ssh, target_name)
        router_info_dict = router_info.get_router_info(ssh_client)

        if progress_callback:
            progress_callback(3, f"{target_name} (Creating Backup)")

        # Initialize backup manager
        backup_mgr = BackupManager(
            ssh_manager=ssh,
            router_info_manager=router_info,
            logger=logger
        )

        # Get timestamp for backup files
        tz = get_timezone(config.get('timezone')) if config else None
        timestamp = get_timestamp(tz)

        # Create backup directory
        clean_version = backup_mgr._clean_version_string(router_info_dict['ros_version'])
        backup_dir = backup_path / f"{router_info_dict['identity']}_{target['host']}_ROS{clean_version}_{router_info_dict['architecture_name']}"
        os.makedirs(backup_dir, exist_ok=True)

        # Perform binary backup
        binary_success = False
        if target.get('enable_binary_backup', True):
            binary_success, binary_file = backup_mgr.perform_binary_backup(
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
                logger.error("Failed to create binary backup")
                return False

        # Perform plaintext backup
        plaintext_success = False
        if target.get('enable_plaintext_backup', True):
            plaintext_success, plaintext_file = backup_mgr.perform_plaintext_backup(
                ssh_client=ssh_client,
                router_info=router_info_dict,
                backup_dir=backup_dir,
                timestamp=timestamp,
                keep_plaintext_backup=target.get('keep_plaintext_backup', False),
                dry_run=dry_run
            )
            if not plaintext_success:
                logger.error("Failed to create plaintext backup")
                return False

        # Save router information
        info_file = backup_dir / f"{router_info_dict['identity']}_{clean_version}_{router_info_dict['architecture_name']}_{timestamp}.INFO.txt"
        info_success = backup_mgr.save_info_file(router_info_dict, info_file, dry_run)
        if not info_success:
            logger.error("Failed to save router information")
            return False

        if progress_callback:
            progress_callback(4, f"{target_name} (Success)")

        logger.info("Backup completed successfully")
        return True

    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
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
    log_manager.setup(
        log_level=args.log_level,
        log_file=args.log_file,
        use_colors=not args.no_color
    )
    logger = log_manager.system
        
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
        'transport_factory': ssh_config.get('transport_factory', None),
        'user': ssh_config.get('user', 'rosbackup'),  # Add global SSH user to ssh_args
        'private_key': ssh_config.get('private_key')  # Add global private key path
    }

    # Load target configurations
    targets_file = Path(args.config_dir) / 'targets.yaml'
    if not targets_file.exists():
        logger.error(f"Target configuration file not found: {targets_file}")
        sys.exit(1)

    with open(targets_file) as f:
        targets_data = yaml.safe_load(f)

    if not targets_data or 'targets' not in targets_data:
        logger.error("No targets defined in configuration")
        sys.exit(1)

    targets_data = targets_data['targets']

    # Filter targets if specified
    if args.target:
        targets_data = [t for t in targets_data if t.get('name') == args.target]
        if not targets_data:
            logger.error(f"Target '{args.target}' not found in configuration")
            sys.exit(1)

    # Filter disabled targets
    targets_data = [t for t in targets_data if t.get('enabled', True)]
    if not targets_data:
        logger.error("No enabled targets found")
        sys.exit(1)

    # Log target count only if not using progress bar
    if not (global_config['parallel_backups'] and not args.no_parallel and args.progress_bar):
        logger.info(f"Found {len(targets_data)} enabled target(s)")

    # Execute backups
    parallel_backups = global_config.get('parallel_backups', False)
    max_parallel = global_config.get('max_parallel', 4)

    # Determine execution mode
    use_parallel = global_config['parallel_backups'] and not args.no_parallel
    max_workers = min(global_config['max_parallel'], len(targets_data)) if use_parallel else 1

    pbar_handler = None
    if use_parallel and args.progress_bar:
        # Suppress all output below WARNING when using progress bar
        log_manager.set_log_level(logging.WARNING)
        log_manager.disable_console()
        
        # Only show initial dry-run warning if needed
        if args.dry_run:
            logger.warning("Running in dry-run mode - no changes will be made")
            
        # Create progress bar with total number of targets
        pbar_handler = ShellPbarHandler(
            total=len(targets_data),
            desc="Overall Progress",
            bar_format='{desc:<20} {percentage:3.0f}%|{bar:20}| {n_fmt}/{total_fmt} routers [{elapsed}<{remaining}]'
        )

    successful_backups = 0
    failed_backups = 0

    try:
        # Perform backups
        if use_parallel:
            success_count = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for target in targets_data:
                    future = executor.submit(
                        backup_target,
                        target=target,
                        ssh_args=ssh_args,
                        backup_password=global_config['backup_password'],
                        notifier=notifier,
                        backup_path=backup_path,
                        dry_run=args.dry_run,
                        config=global_config,
                        progress_callback=None  # Remove per-router progress callback
                    )
                    futures.append((target['name'], future))

                # Track progress
                for target_name, future in futures:
                    try:
                        success = future.result()
                        if success:
                            success_count += 1
                            if pbar_handler:
                                pbar_handler.update(1, desc=f"Success: {success_count}/{len(targets_data)}")
                        else:
                            failed_backups += 1
                            if pbar_handler:
                                pbar_handler.update(1, desc=f"Success: {success_count}/{len(targets_data)}")
                    except Exception as e:
                        logger.error(f"Failed to backup {target_name}: {str(e)}")
                        failed_backups += 1
                        if pbar_handler:
                            pbar_handler.update(1, desc=f"Success: {success_count}/{len(targets_data)}")
        else:
            # Sequential execution
            for target in targets_data:
                try:
                    if backup_target(
                        target=target,
                        ssh_args=ssh_args,
                        backup_password=global_config['backup_password'],
                        notifier=notifier,
                        backup_path=backup_path,
                        dry_run=args.dry_run,
                        config=global_config
                    ):
                        successful_backups += 1
                    else:
                        failed_backups += 1
                except Exception as e:
                    logger.error(f"Failed to backup {target['name']}: {str(e)}")
                    failed_backups += 1

        # Re-enable console logging and restore log level
        if pbar_handler:
            pbar_handler.set_complete()
            pbar_handler.close()
            log_manager.enable_console()
            log_manager.set_log_level(logging.INFO)

        # Print summary
        failed_count = len(targets_data) - successful_backups
        duration = datetime.now() - start_time
        minutes = int(duration.seconds // 60)
        seconds = int(duration.seconds % 60)
        if not (use_parallel and args.progress_bar):
            logger.info(f"Backup completed. Success: {successful_backups}, Failed: {failed_count} [{minutes}m {seconds}s]")

        return 0 if failed_count == 0 else 1

    except KeyboardInterrupt:
        logger.error("Backup interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        return 1

    finally:
        # Always re-enable console logging and restore log level
        if pbar_handler:
            pbar_handler.set_complete()
            pbar_handler.close()
            log_manager.enable_console()
            log_manager.set_log_level(logging.INFO)

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
