import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.time import get_iso_utc_now, convert_to_iso_utc_z, check_timedelta_iso
from datetime import datetime, timezone, timedelta

def test_get_iso_utc_now_format():
    result = get_iso_utc_now()
    assert result.endswith('Z')
    assert 'T' in result
    assert len(result) >= 20

def test_convert_valid_iso():
    input_str = "2022-12-08T00:38:52.730Z"
    result = convert_to_iso_utc_z(input_str)
    assert result.endswith('Z')
    assert 'T' in result

def test_convert_invalid_iso():
    input_str = "not-a-date"
    result = convert_to_iso_utc_z(input_str)
    assert result is None

def test_convert_missing_timezone():
    input_str = "2022-12-08T00:38:52.730"
    result = convert_to_iso_utc_z(input_str)
    assert result.endswith('Z')

def test_check_timedelta_iso_old():
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    assert check_timedelta_iso(old_time, minutes=2) is True

def test_check_timedelta_iso_recent():
    recent_time = get_iso_utc_now()
    assert check_timedelta_iso(recent_time, minutes=2) is False

def test_check_timedelta_iso_invalid():
    assert check_timedelta_iso("invalid-date", minutes=2) is True

