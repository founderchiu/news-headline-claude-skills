"""Tests for time parsing and ISO 8601 conversion."""

import pytest
from datetime import datetime, timezone, timedelta
from utils.time_parser import (
    parse_time,
    parse_to_iso8601,
    relative_to_absolute,
    format_human_readable,
    calculate_hours_ago,
    recency_bonus,
)


class TestRelativeTimeConversion:
    """Tests for relative time string conversion."""

    def test_hours_ago(self):
        """'X hours ago' should convert to correct datetime."""
        result = relative_to_absolute("2 hours ago")
        assert result is not None
        now = datetime.now(timezone.utc)
        delta = now - result
        # Should be approximately 2 hours (within a few seconds)
        assert 7100 <= delta.total_seconds() <= 7300

    def test_minutes_ago(self):
        """'X minutes ago' should convert to correct datetime."""
        result = relative_to_absolute("30 minutes ago")
        assert result is not None
        now = datetime.now(timezone.utc)
        delta = now - result
        assert 1750 <= delta.total_seconds() <= 1850

    def test_days_ago(self):
        """'X days ago' should convert to correct datetime."""
        result = relative_to_absolute("1 day ago")
        assert result is not None
        now = datetime.now(timezone.utc)
        delta = now - result
        # Should be approximately 24 hours
        assert 86000 <= delta.total_seconds() <= 86800

    def test_weeks_ago(self):
        """'X weeks ago' should convert to correct datetime."""
        result = relative_to_absolute("2 weeks ago")
        assert result is not None
        now = datetime.now(timezone.utc)
        delta = now - result
        # Should be approximately 14 days
        assert 13.5 <= delta.days <= 14.5

    def test_today(self):
        """'Today' should convert to today's date."""
        result = relative_to_absolute("Today")
        assert result is not None
        assert result.date() == datetime.now(timezone.utc).date()

    def test_yesterday(self):
        """'Yesterday' should convert to yesterday's date."""
        result = relative_to_absolute("Yesterday")
        assert result is not None
        expected_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        assert result.date() == expected_date

    def test_case_insensitive(self):
        """Relative time parsing should be case insensitive."""
        assert relative_to_absolute("2 HOURS AGO") is not None
        assert relative_to_absolute("today") is not None
        assert relative_to_absolute("YESTERDAY") is not None

    def test_invalid_returns_none(self):
        """Invalid relative times should return None."""
        assert relative_to_absolute("not a time") is None
        assert relative_to_absolute("Recent") is None
        assert relative_to_absolute("") is None


class TestParseTime:
    """Tests for the main parse_time function."""

    def test_iso_8601_with_z(self):
        """ISO 8601 with Z suffix should parse correctly."""
        result = parse_time("2026-01-25T10:30:00Z")
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 25
        assert result.hour == 10
        assert result.minute == 30
        assert result.tzinfo is not None

    def test_iso_8601_with_offset(self):
        """ISO 8601 with timezone offset should parse correctly."""
        result = parse_time("2026-01-25T10:30:00+00:00")
        assert result is not None
        assert result.tzinfo is not None

    def test_rfc_2822_format(self):
        """RFC 2822 date format should parse correctly."""
        result = parse_time("Sat, 25 Jan 2026 10:30:00 GMT")
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 25

    def test_simple_datetime(self):
        """Simple datetime format should parse correctly."""
        result = parse_time("2026-01-25 10:30")
        assert result is not None
        assert result.year == 2026
        assert result.hour == 10

    def test_relative_time(self):
        """Relative time strings should parse correctly."""
        result = parse_time("2 hours ago")
        assert result is not None
        assert result.tzinfo is not None

    def test_returns_utc_aware(self):
        """All parsed times should be UTC-aware."""
        times = [
            "2026-01-25T10:30:00Z",
            "2 hours ago",
            "2026-01-25 10:30",
            "Sat, 25 Jan 2026 10:30:00 GMT",
        ]
        for time_str in times:
            result = parse_time(time_str)
            if result is not None:
                assert result.tzinfo is not None, f"'{time_str}' should be timezone-aware"

    def test_invalid_returns_none(self):
        """Invalid time strings should return None."""
        assert parse_time("not a time") is None
        assert parse_time("") is None
        assert parse_time(None) is None


class TestParseToISO8601:
    """Tests for ISO 8601 output conversion."""

    def test_converts_to_iso8601(self):
        """Output should be valid ISO 8601 format."""
        result = parse_to_iso8601("2026-01-25 10:30")
        assert result is not None
        # Should be parseable as ISO 8601
        parsed = datetime.fromisoformat(result)
        assert parsed.year == 2026

    def test_output_has_timezone(self):
        """ISO 8601 output should include timezone."""
        result = parse_to_iso8601("2 hours ago")
        assert result is not None
        assert "+" in result or "Z" in result.upper()

    def test_relative_time_converts(self):
        """Relative times should convert to absolute ISO 8601."""
        result = parse_to_iso8601("2 hours ago")
        assert result is not None
        # Should be approximately now minus 2 hours
        parsed = datetime.fromisoformat(result)
        now = datetime.now(timezone.utc)
        delta = now - parsed
        assert 7100 <= delta.total_seconds() <= 7300

    def test_invalid_returns_none(self):
        """Invalid inputs should return None."""
        assert parse_to_iso8601("not a time") is None
        assert parse_to_iso8601("") is None


class TestFormatHumanReadable:
    """Tests for human-readable formatting."""

    def test_formats_correctly(self):
        """Should produce human-readable format."""
        iso = "2026-01-25T10:30:00+00:00"
        result = format_human_readable(iso)
        assert "Jan" in result
        assert "2026" in result
        assert "UTC" in result

    def test_handles_empty(self):
        """Empty input should return empty string."""
        assert format_human_readable("") == ""
        assert format_human_readable(None) == ""


class TestRecencyBonus:
    """Tests for recency bonus calculation."""

    def test_very_recent_gets_20(self):
        """Items < 2 hours old should get 20 points."""
        recent_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert recency_bonus(recent_time) == 20

    def test_recent_gets_10(self):
        """Items 2-6 hours old should get 10 points."""
        recent_time = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
        assert recency_bonus(recent_time) == 10

    def test_old_gets_0(self):
        """Items > 6 hours old should get 0 points."""
        old_time = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
        assert recency_bonus(old_time) == 0

    def test_relative_time_works(self):
        """Relative time strings should work for recency bonus."""
        assert recency_bonus("1 hour ago") == 20
        assert recency_bonus("5 hours ago") == 10
        assert recency_bonus("2 days ago") == 0

    def test_invalid_returns_0(self):
        """Invalid times should return 0 bonus."""
        assert recency_bonus("not a time") == 0
        assert recency_bonus("") == 0
