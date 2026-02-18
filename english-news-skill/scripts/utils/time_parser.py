#!/usr/bin/env python3
"""
Centralized ISO 8601 timestamp handling for English News Skill.

All timestamps are normalized to UTC with timezone info.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional


def relative_to_absolute(relative_str: str) -> Optional[datetime]:
    """
    Convert relative time string to absolute UTC datetime.

    Handles formats like:
    - "2 hours ago"
    - "5 minutes ago"
    - "1 day ago"
    - "3 weeks ago"
    - "Today"
    - "Yesterday"

    Returns UTC-aware datetime or None if unparseable.
    """
    if not relative_str:
        return None

    time_lower = relative_str.lower().strip()
    now = datetime.now(timezone.utc)

    # Handle "Today" / "Yesterday"
    if time_lower == 'today':
        return now.replace(hour=12, minute=0, second=0, microsecond=0)
    elif time_lower == 'yesterday':
        return (now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)

    # Handle relative times like "2 hours ago"
    match = re.search(r'(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago', time_lower)
    if match:
        value = int(match.group(1))
        unit = match.group(2)

        if unit == 'second':
            return now - timedelta(seconds=value)
        elif unit == 'minute':
            return now - timedelta(minutes=value)
        elif unit == 'hour':
            return now - timedelta(hours=value)
        elif unit == 'day':
            return now - timedelta(days=value)
        elif unit == 'week':
            return now - timedelta(weeks=value)
        elif unit == 'month':
            return now - timedelta(days=value * 30)
        elif unit == 'year':
            return now - timedelta(days=value * 365)

    return None


def parse_time(time_str: str) -> Optional[datetime]:
    """
    Parse various time string formats to UTC-aware datetime.

    Supports:
    - ISO 8601: "2026-01-25T10:30:00Z", "2026-01-25T10:30:00+00:00"
    - RFC 2822: "Sat, 25 Jan 2026 10:30:00 GMT"
    - Simple datetime: "2026-01-25 10:30"
    - Relative: "2 hours ago", "Today"
    - Unix timestamp (epoch): 1737800000

    Returns UTC-aware datetime or None if unparseable.
    """
    if not time_str:
        return None

    # Handle numeric timestamp (epoch)
    if isinstance(time_str, (int, float)):
        try:
            return datetime.fromtimestamp(time_str, tz=timezone.utc)
        except (ValueError, OSError):
            return None

    time_str = str(time_str).strip()

    # Try relative time first
    relative_result = relative_to_absolute(time_str)
    if relative_result:
        return relative_result

    # Try ISO format (handles Z and +00:00)
    try:
        # Replace Z with +00:00 for fromisoformat
        iso_str = time_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(iso_str)
        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        pass

    # Try common formats
    formats = [
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%a, %d %b %Y %H:%M:%S %z',      # RFC 2822 with tz
        '%a, %d %b %Y %H:%M:%S GMT',     # RFC 2822 GMT
        '%a, %d %b %Y %H:%M:%S %Z',      # RFC 2822 with tz name
        '%d %b %Y %H:%M:%S',
        '%b %d, %Y',                      # "Jan 25, 2026"
        '%B %d, %Y',                      # "January 25, 2026"
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    return None


def parse_to_iso8601(time_str: str, source_hint: str = "") -> Optional[str]:
    """
    Convert any time format to ISO 8601 string with timezone.

    Args:
        time_str: Input time string in any supported format
        source_hint: Optional hint about the source (e.g., "hackernews", "reddit")
                    to help with source-specific parsing

    Returns:
        ISO 8601 string like "2026-01-25T10:30:00+00:00" or None if unparseable
    """
    dt = parse_time(time_str)
    if dt is None:
        return None

    # Ensure UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt.isoformat()


def format_human_readable(iso_str: str) -> str:
    """
    Format ISO 8601 string for human display.

    Returns format like: "Jan 25, 2026 10:30 AM UTC"
    """
    if not iso_str:
        return ""

    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime('%b %d, %Y %I:%M %p UTC')
    except (ValueError, AttributeError):
        return iso_str


def calculate_hours_ago(time_str: str) -> Optional[float]:
    """
    Calculate how many hours ago a timestamp was.

    Returns hours as float, or None if unparseable.
    """
    dt = parse_time(time_str)
    if dt is None:
        return None

    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = now - dt
    return delta.total_seconds() / 3600


def recency_bonus(time_str: str) -> int:
    """
    Calculate recency bonus for ranking.

    Returns:
        +20 if < 2 hours ago
        +10 if < 6 hours ago
        0 otherwise
    """
    hours = calculate_hours_ago(time_str)
    if hours is None:
        return 0

    if hours < 2:
        return 20
    elif hours < 6:
        return 10
    else:
        return 0


# CLI for testing
if __name__ == '__main__':
    import sys

    test_cases = [
        "2 hours ago",
        "5 minutes ago",
        "1 day ago",
        "Today",
        "Yesterday",
        "2026-01-25T10:30:00Z",
        "2026-01-25T10:30:00+00:00",
        "2026-01-25 10:30",
        "Sat, 25 Jan 2026 10:30:00 GMT",
        "Jan 25, 2026",
        "Recent",  # Should fail gracefully
    ]

    print("Time Parser Test Results:")
    print("=" * 60)

    for tc in test_cases:
        iso = parse_to_iso8601(tc)
        human = format_human_readable(iso) if iso else "FAILED"
        hours = calculate_hours_ago(tc)
        bonus = recency_bonus(tc)

        print(f"Input:  {tc}")
        print(f"  ISO:    {iso}")
        print(f"  Human:  {human}")
        print(f"  Hours:  {hours:.1f if hours else 'N/A'}")
        print(f"  Bonus:  {bonus}")
        print()
