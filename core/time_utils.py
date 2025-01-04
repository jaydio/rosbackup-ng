"""
Time-related utility functions for RouterOS backup.

This module provides functions for handling timezones and timestamps
consistently across the application.
"""

from datetime import datetime
from typing import Optional
import pytz
from tzlocal import get_localzone
from zoneinfo import ZoneInfo

def get_current_time() -> datetime:
    """
    Get current time from the source of truth.
    
    Returns:
        datetime: Current time with timezone info
    """
    return datetime.now(tz=get_localzone())

def get_timezone(name: Optional[str] = None) -> Optional[ZoneInfo]:
    """
    Get timezone object from name.
    
    Args:
        name: Optional timezone name (e.g. 'Europe/Berlin')
        
    Returns:
        Optional[ZoneInfo]: Timezone object if name provided, None otherwise
    """
    if not name:
        return get_system_timezone()
        
    # Handle common timezone names
    name_map = {
        'utc': 'UTC',
        'gmt': 'GMT',
    }
    name = name_map.get(name.lower(), name)
    return ZoneInfo(name)

def get_system_timezone() -> ZoneInfo:
    """
    Get system timezone.
    
    Returns:
        ZoneInfo: System timezone
    """
    return ZoneInfo(str(get_localzone()))

def get_timestamp(tz: Optional[ZoneInfo] = None) -> str:
    """
    Get current timestamp in backup file format.
    
    Args:
        tz: Optional timezone to use for timestamp, defaults to system timezone
        
    Returns:
        str: Formatted timestamp string in MMDDYYYY-HHMMSS format
    """
    current_time = get_current_time()
    
    # Use system timezone if none specified
    if tz is None:
        tz = get_system_timezone()
    
    # Convert to target timezone
    current_time = current_time.astimezone(tz)
    
    # Format timestamp
    return current_time.strftime("%m%d%Y-%H%M%S")
