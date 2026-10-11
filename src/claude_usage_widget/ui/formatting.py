"""Pure display helpers. No Qt imports, so they are easy to test."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from claude_usage_widget.models import CLOCK_SKEW


class Level(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


def threshold_level(percent: float, warning: int, critical: int) -> Level:
    if percent >= critical:
        return Level.CRITICAL
    if percent >= warning:
        return Level.WARNING
    return Level.NORMAL


def format_percent(percent: float) -> str:
    return f"{round(percent)}%"


def format_remaining(resets_at: datetime | None, now: datetime) -> str:
    if resets_at is None:
        return "Reset time unavailable"
    seconds = int((resets_at - now).total_seconds())
    if seconds <= 0:
        return "Resetting now"
    minutes = seconds // 60
    days, rest = divmod(minutes, 24 * 60)
    hours, mins = divmod(rest, 60)
    if days:
        return f"Resets in {days}d {hours}h"
    if hours:
        return f"Resets in {hours}h {mins}m"
    return f"Resets in {max(mins, 1)}m"


def format_reset_detail(resets_at: datetime | None, now: datetime) -> str:
    """Countdown plus the reset instant in local time, e.g. "Resets in 2h 14m · 16:30"."""
    if resets_at is None:
        return "Reset time unavailable"
    if resets_at <= now:
        return "Reset passed · waiting for new data"
    return f"{format_remaining(resets_at, now)} · {resets_at.astimezone():%H:%M}"


def format_age(data_as_of: datetime, now: datetime) -> str:
    age = now - data_as_of
    if age < -CLOCK_SKEW:
        return "timestamp is in the future"
    minutes = int(age.total_seconds()) // 60
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} h ago"
    return f"{hours // 24} d ago"
