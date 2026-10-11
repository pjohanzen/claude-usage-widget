"""Domain models shared by services and UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

# Allowed clock disagreement between this machine and the data source.
CLOCK_SKEW = timedelta(minutes=5)


class Status(Enum):
    LOADING = "Loading"
    CONNECTED = "Connected"
    STALE = "Stale"
    SIGN_IN_NEEDED = "Sign-in needed"
    RATE_LIMITED = "Rate limited"
    UNAVAILABLE = "Unavailable"


@dataclass(frozen=True, slots=True)
class QuotaWindow:
    """One quota bucket. ``used_percent`` is 0-100 and was supplied by the data source."""

    used_percent: float
    resets_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    """A validated usage reading. Every value here came from the data source."""

    source_label: str
    data_as_of: datetime
    session: QuotaWindow | None = None
    weekly: QuotaWindow | None = None

    def is_stale(self, now: datetime, refresh_interval: timedelta) -> bool:
        """Stale when older than two refresh cycles (never under ten minutes).

        A timestamp well in the future cannot be trusted either, so it counts as stale.
        """
        age = now - self.data_as_of
        if age < -CLOCK_SKEW:
            return True
        allowed = max(2 * refresh_interval, timedelta(minutes=10))
        return age > allowed
