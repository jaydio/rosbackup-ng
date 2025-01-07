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
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, TypedDict, Any

import yaml
from tqdm import tqdm
from zoneinfo import ZoneInfo
from tzlocal import get_localzone

from core import (
    NotificationManager,
    LogManager,
    ColoredFormatter,
    ShellPbarHandler,
    ComposeStyleHandler
)
from core.backup_utils import BackupManager
from core.logging_utils import LogManager
from core.router_utils import RouterInfoManager
from core.shell_utils import ColoredFormatter, ShellPbarHandler
from core.ssh_utils import SSHManager
from core.time_utils import get_timezone, get_system_timezone, get_current_time

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Automated RouterOS backup utility")
    parser.add_argument("-c", "--config-dir", default="config",
                       help="Directory containing configuration files")
    
    # Create a group for mutually exclusive logging and output style options
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("-l", "--log-file",
                            help="Override log file path")
    output_group.add_argument("-L", "--log-level",
                            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                            default="INFO", help="Logging level")
    output_group.add_argument("-b", "--progress-bar", action="store_true",
                            help="Show progress bar during parallel execution (disables scrolling output)")
    output_group.add_argument("-x", "--compose-style", action="store_true",
                            help="Show Docker Compose style output instead of log messages")
    
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
    config_dir: str,
    dry_run: bool = False,
    config: Optional[GlobalConfig] = None,
    suppress_logs: bool = False,
    compose_handler: Optional[ComposeStyleHandler] = None,
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
        config_dir: Directory containing configuration files
        dry_run: If True, simulate operations
        config: Optional global configuration
        suppress_logs: If True, suppress log messages (used with progress bar)
        compose_handler: Optional ComposeStyleHandler for Docker Compose style output
        progress_callback: Optional callback function for progress updates

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

    try:
        if compose_handler:
            compose_handler.update(target_name, "Starting")
            
        # Initialize managers
        ssh = SSHManager(ssh_args, target_name)
        router_info = RouterInfoManager(ssh, target_name)
        backup_manager = BackupManager(ssh, router_info, logger)
        
        # Get SSH configuration from target and global settings
        target_ssh = target.get('ssh', {})
        
        # Get private key path from target or global config
        key_path = target_ssh.get('private_key', ssh_args.get('private_key'))
        if not key_path:
            if not suppress_logs:
                logger.error("No SSH private key specified in target or global config")
                logger.error("Please set 'private_key' in either target SSH config or global SSH config")
            return False

        # Resolve relative key path if needed
        if not os.path.isabs(key_path):
            project_root = str(Path(config_dir).parent.resolve())
            key_path = os.path.normpath(os.path.join(project_root, key_path))
            
        # Verify key file exists
        if not os.path.isfile(key_path):
            if not suppress_logs:
                logger.error(f"SSH private key not found: {key_path}")
                logger.error("Please check that the key file exists and the path is correct")
            return False

        # Get SSH user from target or global config
        ssh_user = target_ssh.get('user', ssh_args.get('user', 'rosbackup'))
        ssh_port = target_ssh.get('port', 22)

        if dry_run:
            if not suppress_logs:
                logger.info(f"[DRY RUN] Testing SSH authentication for target: {target_name}")
                logger.info(f"[DRY RUN] Using SSH configuration:")
                logger.info(f"[DRY RUN]   - Host: {target['host']}")
                logger.info(f"[DRY RUN]   - Port: {ssh_port}")
                logger.info(f"[DRY RUN]   - User: {ssh_user}")
                logger.info(f"[DRY RUN]   - Key:  {key_path}")
            
            # Test SSH connection
            ssh_client = ssh.create_client(
                host=target['host'],
                port=ssh_port,
                username=ssh_user,
                key_path=key_path,
                suppress_logs=suppress_logs
            )
            
            if not ssh_client:
                if not suppress_logs:
                    logger.error("[DRY RUN] SSH authentication test failed")
                    logger.error("[DRY RUN] Please check:")
                    logger.error("[DRY RUN]   - SSH key exists and has correct permissions")
                    logger.error("[DRY RUN]   - Target host is reachable")
                    logger.error("[DRY RUN]   - SSH credentials are correct")
                if compose_handler:
                    compose_handler.update(target_name, "Failed")
                return False
                
            # Test router access permissions
            if not router_info.validate_router_access(ssh_client):
                if not suppress_logs:
                    logger.error("[DRY RUN] Router access validation failed")
                    logger.error("[DRY RUN] Please check that the SSH user has required permissions:")
                    logger.error("[DRY RUN]   - Read access to system resources")
                    logger.error("[DRY RUN]   - Access to file system")
                    logger.error("[DRY RUN]   - Permission to create backups")
                ssh_client.close()
                if compose_handler:
                    compose_handler.update(target_name, "Failed")
                return False
                
            if not suppress_logs:
                logger.info("[DRY RUN] SSH authentication test successful")
                logger.info("[DRY RUN] Router access validation successful")
                logger.info(f"[DRY RUN] Would backup target: {target_name}")
            ssh_client.close()
            return True

        # Create SSH client for actual backup
        ssh_client = ssh.create_client(
            host=target['host'],
            port=ssh_port,
            username=ssh_user,
            key_path=key_path,
            suppress_logs=suppress_logs
        )
        
        if not ssh_client:
            if not suppress_logs:
                logger.error("Failed to establish SSH connection")
            if compose_handler:
                compose_handler.update(target_name, "Failed")
            return False

        if compose_handler:
            compose_handler.update(target_name, "Connecting")
            
        # Get router information
        if compose_handler:
            compose_handler.update(target_name, "Getting Info")
        router_info_dict = router_info.get_router_info(ssh_client)
        if not router_info_dict:
            if not suppress_logs:
                logger.error("Failed to retrieve router information")
            return False

        # Create backup directory
        timestamp = get_timestamp(get_timezone(config.get('timezone') if config else None))
        clean_version = backup_manager._clean_version_string(router_info_dict['ros_version'])
        backup_dir = backup_path / f"{router_info_dict['identity']}_{target['host']}_ROS{clean_version}_{router_info_dict['architecture_name']}"
        os.makedirs(backup_dir, exist_ok=True)

        # Save router info file
        info_file = backup_dir / f"{router_info_dict['identity']}_{clean_version}_{router_info_dict['architecture_name']}_{timestamp}.info"
        if not backup_manager.save_info_file(router_info_dict, info_file, dry_run):
            if not suppress_logs:
                logger.error("Failed to save router info file")
            return False

        if compose_handler:
            compose_handler.update(target_name, "Creating Backup")
            
        # Perform binary backup if enabled (default: True)
        binary_success = True
        if target.get('enable_binary_backup', True):
            binary_success, binary_file = backup_manager.perform_binary_backup(
                ssh_client=ssh_client,
                router_info=router_info_dict,
                backup_password=target.get('backup_password', backup_password),
                encrypted=target.get('encrypted', False),
                backup_dir=backup_dir,
                timestamp=timestamp,
                keep_binary_backup=target.get('keep_binary_backup', False),
                dry_run=dry_run
            )
            if not binary_success:
                if not suppress_logs:
                    logger.error("Binary backup failed")
                return False

        # Perform plaintext backup if enabled (default: True)
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
                if not suppress_logs:
                    logger.error("Plaintext backup failed")
                return False

        if compose_handler:
            compose_handler.update(target_name, "Downloading")
            
        # Both backups succeeded
        if binary_success and plaintext_success:
            if compose_handler:
                compose_handler.update(target_name, "Downloading")
            if not suppress_logs:
                logger.info("Backup completed successfully")
            if notifier.enabled and notifier.notify_on_success:
                notifier.send_success_notification(target_name)
            if compose_handler:
                compose_handler.update(target_name, "Finished")
            return True
        else:
            if not suppress_logs:
                logger.error("One or more backup operations failed")
            if notifier.enabled and notifier.notify_on_failed:
                notifier.send_failure_notification(target_name)
            if compose_handler:
                compose_handler.update(target_name, "Failed")
            return False

    except Exception as e:
        if compose_handler:
            compose_handler.update(target_name, "Failed")
        if not suppress_logs:
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
    if args.progress_bar or args.compose_style:
        log_manager.setup(log_level='ERROR')
    else:
        log_manager.setup(log_level=args.log_level, log_file=args.log_file, use_colors=not args.no_color)
    logger = log_manager.get_logger('SYSTEM')

    # Convert to GlobalConfig TypedDict
    global_config: GlobalConfig = {
        'backup_path': global_config_data.get('backup_path_parent', 'backups'),
        'backup_password': global_config_data.get('backup_password', ''),
        'parallel_backups': global_config_data.get('parallel_execution', True),
        'max_parallel': global_config_data.get('max_parallel_backups', 5),
        'notifications': global_config_data.get('notifications', {}),
        'ssh': global_config_data.get('ssh', {}),
    }

    # Apply CLI overrides for parallel execution settings
    if args.no_parallel:
        global_config['parallel_backups'] = False
        if not args.progress_bar and not args.compose_style:
            logger.info("Parallel execution disabled via CLI")
    if args.max_parallel is not None:
        if args.max_parallel < 1:
            logger.error("max-parallel must be at least 1")
            sys.exit(1)
        global_config['max_parallel'] = args.max_parallel
        if not args.progress_bar and not args.compose_style:
            logger.info(f"Maximum parallel backups set to {args.max_parallel} via CLI")
    
    # Handle timezone
    if 'timezone' in global_config_data:
        system_tz = get_system_timezone()
        if not args.progress_bar and not args.compose_style:
            logger.info(f"Using timezone: {global_config_data['timezone']}")
        global_config['timezone'] = global_config_data['timezone']
        # Set timezone for logging
        LogManager().set_timezone(get_timezone(global_config['timezone']))

    logger.debug(f"Loaded global config: {global_config_data}")
        
    # Set up backup directory
    backup_path = Path(global_config['backup_path'])
    os.makedirs(backup_path, exist_ok=True)

    # Initialize notification system with defaults
    notifier = NotificationManager(
        enabled=global_config['notifications'].get('enabled', False),
        notify_on_failed=global_config['notifications'].get('notify_on_failed_backups', True),
        notify_on_success=global_config['notifications'].get('notify_on_successful_backups', False),
        smtp_config={
            'enabled': global_config['notifications'].get('smtp', {}).get('enabled', False),
            'host': global_config['notifications'].get('smtp', {}).get('host', 'localhost'),
            'port': global_config['notifications'].get('smtp', {}).get('port', 25),
            'username': global_config['notifications'].get('smtp', {}).get('username', ''),
            'password': global_config['notifications'].get('smtp', {}).get('password', ''),
            'from_email': global_config['notifications'].get('smtp', {}).get('from_email', ''),
            'to_emails': global_config['notifications'].get('smtp', {}).get('to_emails', []),
            'use_ssl': global_config['notifications'].get('smtp', {}).get('use_ssl', False),
            'use_tls': global_config['notifications'].get('smtp', {}).get('use_tls', True)
        }
    )

    # Load SSH configuration with defaults
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
        if not args.progress_bar and not args.compose_style:
            logger.info(f"Running backup for target: {args.target}")

    # Filter enabled targets
    targets_data = [t for t in targets_data if t.get('enabled', True)]
    if not args.progress_bar and not args.compose_style:
        logger.info(f"Found {len(targets_data)} enabled target(s)")

    # Create progress bar or compose style handler if enabled
    if args.compose_style:
        progress_handler = ComposeStyleHandler([t['name'] for t in targets_data])
        def progress_callback(target: str, status: str, file_size: Optional[int] = None):
            progress_handler.update(target, status, file_size)
    elif args.progress_bar:
        progress_handler = ShellPbarHandler(
            total=len(targets_data),
            desc="Backup Progress",
            position=0,
            leave=True,
            ncols=100,
            bar_format='{desc:<20} {percentage:3.0f}%|{bar:40}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
        )
        def progress_callback(target: str, status: str, file_size: Optional[int] = None):
            if status == "Failed":
                progress_handler.error()
            elif status == "Finished":
                progress_handler.advance()
    else:
        progress_handler = None
        progress_callback = None

    # Execute backups
    success_count = 0
    failure_count = 0
    failed_targets = []

    if global_config['parallel_backups'] and len(targets_data) > 1:
        max_workers = min(global_config['max_parallel'], len(targets_data))
        if not args.progress_bar and not args.compose_style:
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
                        config_dir=args.config_dir,
                        dry_run=args.dry_run,
                        config=global_config,
                        suppress_logs=args.progress_bar or args.compose_style,
                        compose_handler=progress_handler if args.compose_style else None,
                        progress_callback=progress_callback
                    )
                    futures.append((target, future))

                for target, future in [(t, f) for t, f in futures]:
                    try:
                        if future.result():
                            success_count += 1
                        else:
                            failure_count += 1
                            target_name = target.get('name', target.get('host', 'Unknown'))
                            failed_targets.append(target_name)
                            if not args.progress_bar and not args.compose_style:
                                logger.error(f"Backup failed for target: {target_name}")
                        if progress_handler:
                            if args.compose_style:
                                progress_handler.update(target['name'], "Finished" if success_count > 0 else "Failed")
                    except Exception as e:
                        failure_count += 1
                        target_name = target.get('name', target.get('host', 'Unknown'))
                        failed_targets.append(target_name)
                        if progress_handler:
                            if args.compose_style:
                                progress_handler.update(target['name'], "Failed")
                        if not args.progress_bar and not args.compose_style:
                            logger.error(f"Backup failed for target {target_name}: {str(e)}")
        except KeyboardInterrupt:
            logger.error("Backup operation interrupted by user")
            sys.exit(1)
    else:
        # Sequential backup
        if not args.progress_bar and not args.compose_style:
            logger.info("Running sequential backup")
        
        for target in targets_data:
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

                if backup_target(
                    target=target,
                    ssh_args=target_args,
                    backup_password=global_config['backup_password'],
                    notifier=notifier,
                    backup_path=backup_path,
                    config_dir=args.config_dir,
                    dry_run=args.dry_run,
                    config=global_config,
                    suppress_logs=args.progress_bar or args.compose_style,
                    compose_handler=progress_handler if args.compose_style else None,
                    progress_callback=progress_callback
                ):
                    success_count += 1
                else:
                    failure_count += 1
                    failed_targets.append(target.get('name', target.get('host', 'Unknown')))
                if progress_handler:
                    if args.compose_style:
                        progress_handler.update(target['name'], "Finished" if success_count > 0 else "Failed")
            except Exception as e:
                failure_count += 1
                failed_targets.append(target.get('name', target.get('host', 'Unknown')))
                if progress_handler:
                    if args.compose_style:
                        progress_handler.update(target['name'], "Failed")
                if not args.progress_bar and not args.compose_style:
                    logger.error(f"Backup failed: {str(e)}")

    if progress_handler:
        progress_handler.close()
        # Only add newline for progress bar mode
        if args.progress_bar:
            print()  # Add newline after progress bar
            if failed_targets:
                print("Failed backups:")
                for target in failed_targets:
                    print(f"  - {target}")
    else:
        pass

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
