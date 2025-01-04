"""
Logging utilities for RouterOS backup operations.

This module provides centralized logging configuration and management,
ensuring consistent log formatting and handling across all components.
"""

import logging
import sys
from typing import Optional, Dict
from pathlib import Path
from .shell_utils import ColoredFormatter, BaseFormatter
from .time_utils import get_current_time, get_timezone, get_system_timezone
from zoneinfo import ZoneInfo


class ColoredTZFormatter(ColoredFormatter):
    """Formatter that combines color output with timezone support."""

    def __init__(self, fmt: str = None, datefmt: str = None, tz: Optional[ZoneInfo] = None,
                 target_name: str = 'SYSTEM', use_colors: bool = True):
        """Initialize the formatter."""
        super().__init__(fmt=fmt, datefmt=datefmt, target_name=target_name, use_colors=use_colors)
        self.tz = tz if tz is not None else get_system_timezone()

    def formatTime(self, record, datefmt=None):
        """Format the time with the configured timezone."""
        current_time = get_current_time()
        current_time = current_time.astimezone(self.tz)
        if datefmt is None:
            datefmt = '%m-%d-%Y %H:%M:%S'
        return current_time.strftime(datefmt) if datefmt else current_time.isoformat()


class LogManager:
    """
    Central logging manager to handle all logging configuration and filtering.

    This class implements the singleton pattern to ensure consistent logging
    configuration across all components of the application.
    """
    _instance: Optional['LogManager'] = None
    _loggers: Dict[str, logging.LoggerAdapter] = {}
    _log_level: int = logging.INFO
    _use_colors: bool = True
    _file_handler: Optional[logging.FileHandler] = None
    _tz: Optional[ZoneInfo] = None
    _system_logger: Optional[logging.Logger] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LogManager, cls).__new__(cls)
        return cls._instance

    def setup(self, log_level: str = 'INFO', log_file: Optional[str] = None, use_colors: bool = True):
        """Set up logging configuration."""
        self._use_colors = use_colors
        self._log_level = getattr(logging, log_level.upper())
        self._tz = get_system_timezone()

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self._log_level)

        # Clear any existing handlers
        root_logger.handlers.clear()

        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self._log_level)

        # Use ColoredTZFormatter for console output
        console_formatter = ColoredTZFormatter(
            tz=self._tz,
            use_colors=self._use_colors
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # Add file handler if specified
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(self._log_level)
            file_handler.setFormatter(ColoredTZFormatter(
                tz=self._tz,
                use_colors=False  # Never use colors in file output
            ))
            root_logger.addHandler(file_handler)
            self._file_handler = file_handler

        # Initialize system logger
        self._system_logger = self.get_logger('SYSTEM')

    def configure(self, log_level: int = logging.INFO, use_colors: bool = True, log_file: Optional[str] = None) -> None:
        """
        Configure logging settings.

        Args:
            log_level: Logging level for all loggers
            use_colors: Whether to use colored output
            log_file: Optional log file path
        """
        self._log_level = log_level
        self._use_colors = use_colors

        # Remove existing file handler if any
        if self._file_handler:
            for logger in [logging.getLogger()] + list(self._loggers.values()):
                logger.removeHandler(self._file_handler)
            self._file_handler = None

        # Add new file handler if specified
        if log_file:
            self._file_handler = logging.FileHandler(log_file)
            self._file_handler.setFormatter(ColoredTZFormatter(
                tz=self._tz,
                use_colors=False  # Never use colors in file output
            ))  # No colors in file
            logging.getLogger().addHandler(self._file_handler)
            for logger in self._loggers.values():
                logger.logger.addHandler(self._file_handler)

        # Update existing loggers
        for logger in self._loggers.values():
            logger.logger.setLevel(log_level)
            for handler in logger.logger.handlers:
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    handler.setFormatter(ColoredTZFormatter(
                        tz=self._tz,
                        use_colors=self._use_colors
                    ))

    def get_logger(self, name: str, target_name: str = 'SYSTEM') -> logging.LoggerAdapter:
        """Get or create a logger with the specified name and target name."""
        logger_key = f"{name}:{target_name}"
        if logger_key not in self._loggers:
            logger = logging.getLogger(logger_key)
            logger.propagate = False
            logger.setLevel(self._log_level)
            
            # Clear any existing handlers
            logger.handlers = []
            
            # Add console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(self._log_level)
            
            # Use ColoredTZFormatter
            formatter = ColoredTZFormatter(
                tz=self._tz,
                target_name=target_name,
                use_colors=self._use_colors
            )
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            # Add file handler if configured
            if self._file_handler:
                logger.addHandler(self._file_handler)
            
            # Create adapter
            adapter = logging.LoggerAdapter(logger, {'target_name': target_name})
            self._loggers[logger_key] = adapter

        return self._loggers[logger_key]

    def set_log_level(self, level: int) -> None:
        """
        Set log level for all loggers.

        Args:
            level: Logging level (e.g., logging.DEBUG, logging.INFO)
        """
        self._log_level = level
        logging.getLogger().setLevel(level)
        for logger in self._loggers.values():
            logger.setLevel(level)
        
        # Update console handler level
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                handler.setLevel(level)

    def set_timezone(self, tz: Optional[ZoneInfo] = None):
        """Set timezone for log timestamps."""
        self._tz = tz
        # Update existing handlers
        for logger in [logging.getLogger()] + list(self._loggers.values()):
            if isinstance(logger, logging.LoggerAdapter):
                logger = logger.logger
            for handler in logger.handlers:
                if isinstance(handler.formatter, ColoredTZFormatter):
                    handler.formatter.tz = tz

    @property
    def system(self) -> logging.LoggerAdapter:
        """Get the system logger."""
        # Create adapter if it doesn't exist
        system_key = 'SYSTEM:SYSTEM'
        if system_key not in self._loggers:
            # Add console handler if none exists
            if not self._system_logger.handlers:
                handler = logging.StreamHandler()
                formatter = ColoredTZFormatter(
                    tz=self._tz,
                    use_colors=self._use_colors
                )
                handler.setFormatter(formatter)
                self._system_logger.addHandler(handler)
            
            # Create adapter
            adapter = logging.LoggerAdapter(self._system_logger, {'target_name': 'SYSTEM'})
            self._loggers[system_key] = adapter
        
        return self._loggers[system_key]

class BaseFormatter(logging.Formatter):
    """Base formatter for all log messages."""

    def __init__(self, target_name: str = 'SYSTEM'):
        """Initialize the formatter."""
        fmt = '%(asctime)s [%(levelname)s] [%(target_name)s] %(message)s'
        datefmt = '%Y-%m-%d %H:%M:%S'
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.target_name = target_name

    def format(self, record):
        """Format the log record."""
        if not hasattr(record, 'target_name'):
            record.target_name = self.target_name
        # Don't repeat target_name in message
        if record.target_name == 'SYSTEM' and '[SYSTEM]' in record.msg:
            record.msg = record.msg.replace('[SYSTEM]', '').strip()
        return super().format(record)


class ColoredFormatter(BaseFormatter):
    """Colored formatter for console output."""
