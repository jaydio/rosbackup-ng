#!/usr/bin/env python3
"""
rosbackup.py - A Python3 script for backing up multiple RouterOS devices via SSH.
"""

import os
import json
import yaml
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.ssh_utils import SSHManager
from core.router_info import RouterInfoManager
from core.backup_operations import BackupManager
from core.notifications import Notifications

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

def setup_logging(log_file: str = None, log_level: str = 'INFO', use_colors: bool = True):
    """Configure logging.
    
    Args:
        log_file (str, optional): Path to log file. Defaults to None.
        log_level (str, optional): Logging level. Defaults to 'INFO'.
        use_colors (bool, optional): Whether to use colored output. Defaults to True.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

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

def load_config(config_path: Path) -> Dict:
    """Load configuration file (JSON or YAML)."""
    try:
        with open(config_path, 'r') as f:
            if config_path.suffix in ['.yaml', '.yml']:
                return yaml.safe_load(f)
            else:  # Default to JSON for backward compatibility
                return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load config file {config_path}: {str(e)}")
        raise

def backup_router(
    router: Dict,
    global_config: Dict,
    backup_path_parent: Path,
    ssh_args: Dict,
    backup_password: str,
    notifier: Notifications,
    dry_run: bool = False
) -> bool:
    """
    Perform backup for a single router.

    Args:
        router (Dict): Router configuration
        global_config (Dict): Global configuration
        backup_path_parent (Path): Parent backup directory
        ssh_args (Dict): SSH connection arguments
        backup_password (str): Password for encrypted backups
        notifier (Notifications): Notification manager
        dry_run (bool): If True, simulate operations

    Returns:
        bool: True if backup successful, False otherwise
    """
    router_name = router.get('name', 'unknown')
    if dry_run:
        logging.info(f"[DRY RUN] Would backup router: {router_name}")

    # Initialize managers
    ssh_manager = SSHManager(ssh_args)
    router_info_manager = RouterInfoManager(ssh_manager)
    backup_manager = BackupManager(ssh_manager, router_info_manager)

    # Create SSH connection
    ssh_client = ssh_manager.create_client(
        router['host'],
        router.get('ssh_port', 22),
        router['ssh_user'],
        str(Path(router['private_key']))
    )

    if not ssh_client:
        return False

    try:
        # Get router information
        router_info = router_info_manager.get_router_info(ssh_client)
        
        # Create backup directory with router info, replacing spaces with underscores
        ros_version = router_info['ros_version'].replace(' ', '')
        router_dir = f"{router_info['identity']}-{router['host']}-ROS{ros_version}-{router_info['architecture_name']}"
        timestamp = datetime.now().strftime('%d%m%Y-%H%M%S')
        backup_dir = backup_path_parent / router_dir
        if not dry_run:
            os.makedirs(backup_dir, exist_ok=True)

        success = True
        backup_files = []

        # Get router-specific settings with defaults
        encrypted = router.get('encrypted', True)
        enable_binary_backup = router.get('enable_binary_backup', True)
        enable_plaintext_backup = router.get('enable_plaintext_backup', True)
        keep_binary_backup = router.get('keep_binary_backup', False)
        keep_plaintext_backup = router.get('keep_plaintext_backup', False)
        router_backup_password = router.get('backup_password', backup_password)

        # Perform binary backup if enabled
        if enable_binary_backup:
            binary_success, binary_file = backup_manager.perform_binary_backup(
                ssh_client,
                router_info,
                router_backup_password,
                encrypted,
                backup_dir,
                timestamp,
                keep_binary_backup,
                dry_run
            )
            success &= binary_success
            if binary_file:
                backup_files.append(binary_file)

        # Perform plaintext backup if enabled
        if enable_plaintext_backup:
            plaintext_success, plaintext_file = backup_manager.perform_plaintext_backup(
                ssh_client,
                router_info,
                backup_dir,
                timestamp,
                keep_plaintext_backup,
                dry_run
            )
            success &= plaintext_success
            if plaintext_file:
                backup_files.append(plaintext_file)

        # Save router information
        info_success = backup_manager.save_info_file(
            router_info,
            backup_dir / f"{router_info['identity']}-{ros_version}-{router_info['architecture_name']}-{timestamp}.INFO.txt",
            dry_run
        )
        success &= info_success

        # Handle notifications
        if not dry_run:
            if success and notifier.notify_on_success:
                notifier.notify_backup(router_name, router['host'], True, backup_files)
            elif not success and notifier.notify_on_failed:
                notifier.notify_backup(router_name, router['host'], False, backup_files)

        return success

    finally:
        ssh_manager.close_client(ssh_client)

def main():
    """Main function to execute the backup process."""
    args = parse_arguments()
    
    # Setup logging with color option
    setup_logging(
        log_file=args.log_file,
        log_level=args.log_level,
        use_colors=not args.no_color
    )

    if args.dry_run:
        logging.info("Running in DRY RUN mode - no changes will be made")

    config_dir = Path(args.config_dir)
    # Try YAML first, fall back to JSON for backward compatibility
    try:
        global_config = load_config(config_dir / 'global.yaml')
    except:
        global_config = load_config(config_dir / 'global.json')
        logging.warning("Using legacy JSON config file. Consider migrating to YAML.")

    try:
        targets_config = load_config(config_dir / 'targets.yaml')
    except:
        targets_config = load_config(config_dir / 'targets.json')
        logging.warning("Using legacy JSON config file. Consider migrating to YAML.")

    backup_path = Path(global_config.get('backup_path', 'backups'))
    if not args.dry_run:
        os.makedirs(backup_path, exist_ok=True)

    notifier = Notifications(
        enabled=global_config.get('notifications', {}).get('enabled', False),
        notify_on_failed=global_config.get('notifications', {}).get('notify_on_failed', True),
        notify_on_success=global_config.get('notifications', {}).get('notify_on_success', False),
        smtp_config=global_config.get('notifications', {}).get('smtp', {})
    )

    ssh_args = global_config.get('ssh_args', {})
    backup_password = global_config.get('backup_password', '')

    success_count = 0
    failure_count = 0

    routers = targets_config['routers']
    # Process routers in parallel
    max_workers = min(len(routers), global_config.get('max_parallel_backups', 5))
    if max_workers > 1:
        logging.info("Parallel execution enabled.")
        logging.info(f"Max parallel backups set to: {max_workers}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_router = {
            executor.submit(
                backup_router,
                router,
                global_config,
                backup_path,
                ssh_args,
                backup_password,
                notifier,
                args.dry_run
            ): router for router in routers
        }

        for future in as_completed(future_to_router):
            router = future_to_router[future]
            try:
                if future.result():
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                logging.error(f"Router {router.get('name', 'unknown')} backup failed: {str(e)}")
                failure_count += 1

    logging.info(f"Backup completed. Success: {success_count}, Failed: {failure_count}")
    if failure_count > 0:
        sys.exit(1)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Backup RouterOS devices via SSH',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--config-dir',
        type=str,
        default='config',
        help='Directory containing configuration files'
    )
    parser.add_argument(
        '--log-file',
        type=str,
        help='Log file path (optional)'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Logging level'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate backup operations without making changes'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )
    return parser.parse_args()

if __name__ == "__main__":
    main()
