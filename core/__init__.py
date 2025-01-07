"""
Core utilities for RouterOS backup operations.
"""

__version__ = '0.1.0'

from .backup_utils import (
    BackupManager,
    RouterInfoManager,
    TargetConfig,
    BackupConfig,
    SMTPConfig,
    NotificationConfig
)
from .logging_utils import LogManager
from .shell_utils import (
    ColoredFormatter,
    ShellPbarHandler,
    ComposeStyleHandler,
    BackupProgressHandler
)
from .notification_utils import NotificationManager
from .ssh_utils import SSHManager

__all__ = [
    'BackupManager',
    'RouterInfoManager',
    'LogManager',
    'NotificationManager',
    'SSHManager',
    'ColoredFormatter',
    'ShellPbarHandler',
    'ComposeStyleHandler',
    'BackupProgressHandler',
    'TargetConfig',
    'BackupConfig',
    'SMTPConfig',
    'NotificationConfig'
]
