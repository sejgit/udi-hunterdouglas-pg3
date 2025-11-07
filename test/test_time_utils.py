"""Tests for the time utility module.

(C) 2025 Stephen Jenkins
"""

import pytest
from datetime import datetime, timezone, timedelta

from utils.time import get_iso_utc_now, convert_to_iso_utc_z, check_timedelta_iso


class TestGetIsoUtcNow:
    """Tests for get_iso_utc_now function."""

    def test_returns_string(self):
        """Test that function returns a string."""
        result = get_iso_utc_now()
        assert isinstance(result, str)

    def test_ends_with_z(self):
        """Test that result ends with 'Z' suffix."""
        result = get_iso_utc_now()
        assert result.endswith("Z")

    def test_contains_milliseconds(self):
        """Test that result includes milliseconds (has a dot before Z)."""
        result = get_iso_utc_now()
        # Format should be like: 2025-11-07T19:55:10.531Z
        assert "." in result
        # Should have 3 digits for milliseconds
        ms_part = result.split(".")[-1].rstrip("Z")
        assert len(ms_part) == 3

    def test_is_valid_iso_format(self):
        """Test that result is valid ISO 8601 format."""
        result = get_iso_utc_now()
        # Should be parseable
        dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert isinstance(dt, datetime)

    def test_result_is_utc(self):
        """Test that result represents UTC time."""
        result = get_iso_utc_now()
        dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert dt.tzinfo == timezone.utc


class TestConvertToIsoUtcZ:
    """Tests for convert_to_iso_utc_z function."""

    def test_converts_valid_iso_string(self):
        """Test conversion of valid ISO string."""
        input_str = "2025-11-07T19:55:10.531Z"
        result = convert_to_iso_utc_z(input_str)

        assert result == "2025-11-07T19:55:10.531Z"

    def test_converts_iso_without_z(self):
        """Test conversion of ISO string without Z suffix."""
        input_str = "2025-11-07T19:55:10.531+00:00"
        result = convert_to_iso_utc_z(input_str)

        assert result.endswith("Z")
        assert "2025-11-07T19:55:10.531Z" == result

    def test_converts_different_timezone(self):
        """Test conversion from different timezone to UTC."""
        # EST is UTC-5
        input_str = "2025-11-07T14:55:10.531-05:00"
        result = convert_to_iso_utc_z(input_str)

        assert result == "2025-11-07T19:55:10.531Z"

    def test_handles_no_milliseconds(self):
        """Test conversion of ISO string without milliseconds."""
        input_str = "2025-11-07T19:55:10Z"
        result = convert_to_iso_utc_z(input_str)

        # Should add milliseconds (.000)
        assert result.endswith("Z")
        assert "." in result

    def test_returns_none_for_invalid_string(self):
        """Test that invalid ISO string returns None."""
        invalid_inputs = [
            "not-a-date",
            "2025-13-01T00:00:00Z",  # Invalid month
            "2025-11-32T00:00:00Z",  # Invalid day
            "",
            "just text",
        ]

        for invalid in invalid_inputs:
            result = convert_to_iso_utc_z(invalid)
            assert result is None, f"Expected None for input: {invalid}"

    def test_crashes_on_none_input(self):
        """Test that None input causes AttributeError (current behavior)."""
        with pytest.raises(AttributeError):
            convert_to_iso_utc_z(None)

    def test_crashes_on_non_string(self):
        """Test that non-string input causes AttributeError (current behavior)."""
        with pytest.raises(AttributeError):
            convert_to_iso_utc_z(12345)

    def test_preserves_utc_timezone(self):
        """Test that UTC timezone is preserved."""
        input_str = "2025-11-07T19:55:10.531Z"
        result = convert_to_iso_utc_z(input_str)

        # Parse and verify it's UTC
        dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert dt.tzinfo == timezone.utc


class TestCheckTimedeltaIso:
    """Tests for check_timedelta_iso function."""

    def test_returns_false_for_recent_time(self):
        """Test that recent time (within threshold) returns False."""
        # Create a time 2 minutes ago
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=2)
        recent_iso = recent_time.isoformat().replace("+00:00", "Z")

        result = check_timedelta_iso(recent_iso, minutes=5)

        assert result is False

    def test_returns_true_for_old_time(self):
        """Test that old time (beyond threshold) returns True."""
        # Create a time 10 minutes ago
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        old_iso = old_time.isoformat().replace("+00:00", "Z")

        result = check_timedelta_iso(old_iso, minutes=5)

        assert result is True

    def test_zero_minutes_threshold(self):
        """Test with zero minutes threshold."""
        # Any past time should return True
        past_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        past_iso = past_time.isoformat().replace("+00:00", "Z")

        result = check_timedelta_iso(past_iso, minutes=0)

        assert result is True

    def test_returns_true_for_invalid_iso_string(self):
        """Test that invalid ISO string returns True."""
        result = check_timedelta_iso("not-a-valid-date", minutes=5)
        assert result is True

    def test_crashes_on_none_input(self):
        """Test that None input causes error in convert then True return."""
        # Since convert crashes on None, check_timedelta will catch it and return True
        # Actually it doesn't catch it, so this will raise
        with pytest.raises(AttributeError):
            check_timedelta_iso(None, minutes=5)

    def test_returns_true_for_empty_string(self):
        """Test that empty string returns True."""
        result = check_timedelta_iso("", minutes=5)
        assert result is True

    def test_future_time_returns_false(self):
        """Test that future time returns False."""
        # Time in the future
        future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        future_iso = future_time.isoformat().replace("+00:00", "Z")

        result = check_timedelta_iso(future_iso, minutes=5)

        # Future time is not older than now minus minutes
        assert result is False

    def test_different_timezones(self):
        """Test with different timezone formats."""
        # Create a time 15 minutes ago in EST format
        utc_time = datetime.now(timezone.utc) - timedelta(minutes=15)
        # Convert to EST representation (UTC-5)
        est_time = utc_time.astimezone(timezone(timedelta(hours=-5)))
        est_iso = est_time.isoformat()

        result = check_timedelta_iso(est_iso, minutes=10)

        # Should be True (15 minutes is older than 10)
        assert result is True

    def test_with_milliseconds(self):
        """Test with millisecond precision."""
        # Create time with milliseconds
        old_time = datetime.now(timezone.utc) - timedelta(minutes=6)
        time_with_ms = old_time.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )

        result = check_timedelta_iso(time_with_ms, minutes=5)

        # 6 minutes ago should be True with 5 minute threshold
        assert result is True


class TestTimeUtilsIntegration:
    """Integration tests for time utility functions."""

    def test_get_and_convert_roundtrip(self):
        """Test that get_iso_utc_now output can be converted."""
        now_iso = get_iso_utc_now()
        converted = convert_to_iso_utc_z(now_iso)

        assert converted == now_iso

    def test_check_current_time_is_not_old(self):
        """Test that current time is not considered old."""
        current_iso = get_iso_utc_now()
        result = check_timedelta_iso(current_iso, minutes=1)

        assert result is False

    def test_full_workflow(self):
        """Test full workflow of time utilities."""
        # Get current time
        now = get_iso_utc_now()

        # Convert it (should be unchanged)
        converted = convert_to_iso_utc_z(now)
        assert converted == now

        # Check if it's old (should not be)
        is_old = check_timedelta_iso(now, minutes=5)
        assert is_old is False

        # Create and check a past time
        past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        past_iso = past_time.isoformat().replace("+00:00", "Z")
        is_past_old = check_timedelta_iso(past_iso, minutes=5)
        assert is_past_old is True

    def test_convert_then_check_old_time(self):
        """Test converting and then checking if time is old."""
        # Create a time 20 minutes ago with different format
        old_time = datetime.now(timezone.utc) - timedelta(minutes=20)
        old_iso = old_time.isoformat()  # Without Z

        # Convert to standard format
        converted = convert_to_iso_utc_z(old_iso)
        assert converted is not None

        # Check if it's old
        is_old = check_timedelta_iso(converted, minutes=10)
        assert is_old is True
