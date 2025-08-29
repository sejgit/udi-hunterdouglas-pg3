# utils/time.py
from datetime import datetime, timezone, timedelta

def get_iso_utc_now():
    """Returns current UTC time in ISO 8601 format with 'Z' suffix and millisecond precision."""
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def convert_to_iso_utc_z(iso_string):
    """
    Converts an ISO 8601 string to UTC format with 'Z' suffix and millisecond precision.
    Returns None if input is invalid.
    """
    try:
        # Attempt to parse the input string
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        # Convert to UTC if not already
        dt_utc = dt.astimezone(timezone.utc)
        # Format with milliseconds and 'Z'
        return dt_utc.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    except (ValueError, TypeError):
        return None


def check_timedelta_iso(iso_string, minutes = 0):
    """
    Checks if the given ISO 8601 string is older than the specified number of minutes.
    Returns True if it is, or bad, or None, False otherwise. Returns False if input is invalid.
    """
    converted = convert_to_iso_utc_z(iso_string)
    if not converted:
        return True

    try:
        dt = datetime.fromisoformat(converted.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        return dt < now - timedelta(minutes=minutes)
    except (ValueError, TypeError):
        return False


