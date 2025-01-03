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


class LogManager:
    """
    Central logging manager to handle all logging configuration and filtering.

    This class implements the singleton pattern to ensure consistent logging
    configuration across all components of the application.

    Attributes:
        _instance (Optional[LogManager]): Singleton instance
        _loggers (Dict[str, logging.LoggerAdapter]): Dictionary of configured loggers
        _log_level (int): Current log level for all loggers
        _use_colors (bool): Whether to use colored output
        _file_handler (Optional[logging.FileHandler]): File handler for logging to file
    """
    _instance: Optional['LogManager'] = None
    _loggers: Dict[str, logging.LoggerAdapter] = {}
    _log_level: int = logging.INFO
    _use_colors: bool = True
    _file_handler: Optional[logging.FileHandler] = None

    def __new__(cls) -> 'LogManager':
        """
        Create or return the singleton instance of LogManager.

        Returns:
            LogManager instance
        """
        if cls._instance is None:
            cls._instance = super(LogManager, cls).__new__(cls)
            cls._instance._setup_root_logger()
        return cls._instance

    def _setup_root_logger(self) -> None:
        """
        Set up the root logger with default configuration.

        Configures the root logger with a standard format that includes
        timestamp, log level, logger name, and message.
        """
        root_logger = logging.getLogger()
        root_logger.setLevel(self._log_level)

        # Remove any existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Add console handler with colored output by default
        console_handler = logging.StreamHandler(sys.stderr)
        formatter = ColoredFormatter() if self._use_colors else BaseFormatter()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

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
            self._file_handler.setFormatter(BaseFormatter())  # No colors in file
            logging.getLogger().addHandler(self._file_handler)
            for logger in self._loggers.values():
                logger.logger.addHandler(self._file_handler)

        # Update existing loggers
        for logger in self._loggers.values():
            logger.logger.setLevel(log_level)
            for handler in logger.logger.handlers:
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    handler.setFormatter(ColoredFormatter() if use_colors else BaseFormatter())

        # Update root logger
        self._setup_root_logger()

    def get_logger(self, name: str, target_name: str = 'SYSTEM') -> logging.LoggerAdapter:
        """
        Get or create a logger with the specified name and target name.

        Args:
            name: Logger name (e.g., 'SSH', 'BACKUP')
            target_name: Name of the target system (e.g., router name)

        Returns:
            Configured logger instance with appropriate name and formatting
        """
        logger_key = f"{name}:{target_name}"
        if logger_key not in self._loggers:
            # Create a new logger with the full name
            logger = logging.getLogger(logger_key)
            logger.propagate = False  # Don't propagate to root logger
            logger.setLevel(self._log_level)
            
            # Clear any existing handlers
            logger.handlers = []
            
            # Add console handler with colored output by default
            console_handler = logging.StreamHandler(sys.stderr)
            formatter = ColoredFormatter(target_name) if self._use_colors else BaseFormatter(target_name)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            # Add file handler if configured
            if self._file_handler:
                logger.addHandler(self._file_handler)
            
            # Create an adapter that adds target name to all messages
            extra = {'target_name': target_name}
            adapter = logging.LoggerAdapter(logger, extra)
            
            self._loggers[logger_key] = adapter

        return self._loggers[logger_key]

    def set_log_level(self, level: int) -> None:
        """
        Set log level for all loggers.

        Args:
            level: Logging level (e.g., logging.DEBUG, logging.INFO)
        """
        # Set level for root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Set level for all managed loggers
        for logger in self._loggers.values():
            logger.logger.setLevel(level)

    @property
    def system(self) -> logging.LoggerAdapter:
        """
        Get the system logger.

        Returns:
            System logger instance
        """
        return self.get_logger('SYSTEM')  # Use default target_name


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
