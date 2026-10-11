from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from claude_usage_widget.ui.formatting import (
    Level,
    format_age,
    format_percent,
    format_remaining,
    format_reset_detail,
    threshold_level,
)

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("percent", "expected"),
    [
        (0, Level.NORMAL),
        (74.9, Level.NORMAL),
        (75, Level.WARNING),
        (89.9, Level.WARNING),
        (90, Level.CRITICAL),
    ],
)
def test_threshold_levels(percent: float, expected: Level) -> None:
    assert threshold_level(percent, warning=75, critical=90) is expected


def test_percent_rounds_for_display() -> None:
    assert format_percent(42.4) == "42%"
    assert format_percent(42.6) == "43%"
    assert format_percent(61) == "61%"


def test_remaining_without_reset_time_is_explicit() -> None:
    assert format_remaining(None, NOW) == "Reset time unavailable"


def test_remaining_in_past_is_resetting_now() -> None:
    assert format_remaining(NOW - timedelta(minutes=1), NOW) == "Resetting now"


def test_remaining_formats_hours_and_minutes() -> None:
    assert format_remaining(NOW + timedelta(hours=2, minutes=14), NOW) == "Resets in 2h 14m"


def test_remaining_formats_days_and_hours() -> None:
    assert format_remaining(NOW + timedelta(days=3, hours=4), NOW) == "Resets in 3d 4h"


def test_remaining_under_a_minute_shows_one_minute() -> None:
    assert format_remaining(NOW + timedelta(seconds=40), NOW) == "Resets in 1m"


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (timedelta(seconds=30), "just now"),
        (timedelta(seconds=-30), "just now"),
        (timedelta(minutes=5), "5 min ago"),
        (timedelta(hours=3), "3 h ago"),
        (timedelta(days=3), "3 d ago"),
        (timedelta(hours=-4), "timestamp is in the future"),
    ],
)
def test_age_formatting(age: timedelta, expected: str) -> None:
    assert format_age(NOW - age, NOW) == expected


def test_reset_detail_shows_countdown_and_local_clock() -> None:
    resets_at = NOW + timedelta(hours=2, minutes=14)

    detail = format_reset_detail(resets_at, NOW)

    assert detail == f"Resets in 2h 14m · {resets_at.astimezone():%H:%M}"


def test_reset_detail_for_passed_reset_does_not_invent_a_countdown() -> None:
    assert format_reset_detail(NOW - timedelta(minutes=5), NOW) == "Reset passed · waiting for new data"


def test_reset_detail_without_timestamp_is_unavailable() -> None:
    assert format_reset_detail(None, NOW) == "Reset time unavailable"
