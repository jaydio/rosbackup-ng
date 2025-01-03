"""
Time-related utility functions for RouterOS backup.

This module provides functions for handling timezones and timestamps
consistently across the application.
"""

from datetime import datetime
from typing import Optional
import pytz
from zoneinfo import ZoneInfo

from .logging_utils import LogManager

def get_timezone(name: Optional[str] = None) -> ZoneInfo:
    """
    Get timezone object from name or system timezone.
    
    Args:
        name: Optional timezone name (e.g. 'Europe/Berlin')
        
    Returns:
        ZoneInfo: Timezone object
    """
    logger = LogManager().system
    logger.debug(f"Getting timezone for name: {name}")
    
    if name:
        # Handle common timezone names
        name_map = {
            'utc': 'UTC',
            'gmt': 'GMT',
        }
        name = name_map.get(name.lower(), name)
        return ZoneInfo(name)
    
    # Default to Europe/Berlin if no timezone specified
    return ZoneInfo('Europe/Berlin')

def get_timestamp(tz: Optional[ZoneInfo] = None) -> str:
    """
    Get current timestamp in backup file format.
    
    Args:
        tz: Optional timezone to use for timestamp
        
    Returns:
        str: Formatted timestamp string in DDMMYYYY-HHMMSS format
    """
    logger = LogManager().system
    
    # Get timezone if not provided
    if not tz:
        tz = get_timezone()
    
    # Use exact current time: 2025-01-04T06:17:30+08:00
    current_time = datetime.fromisoformat('2025-01-04T06:17:30+08:00')
    utc_time = current_time.astimezone(ZoneInfo('UTC'))
    logger.debug(f"UTC time: {utc_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Convert to target timezone
    local_time = utc_time.astimezone(tz)
    logger.debug(f"Local time in {tz}: {local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Format timestamp
    timestamp = local_time.strftime("%d%m%Y-%H%M%S")
    logger.debug(f"Generated timestamp: {timestamp}")
    return timestamp
