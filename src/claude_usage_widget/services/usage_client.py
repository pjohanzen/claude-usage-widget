"""Usage providers. The UI depends only on the ``UsageProvider`` protocol.

No live account endpoint is wired up. Its response format has not been verified,
so this module does not guess at one. The only format parsed here is the app's own
internal JSON document (see README, "Usage document format").
"""

from __future__ import annotations

import json
import logging
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar, Protocol, cast

from claude_usage_widget.models import QuotaWindow, Status, UsageSnapshot

log = logging.getLogger(__name__)

MAX_DOCUMENT_BYTES = 64 * 1024
DEMO_SOURCE_LABEL = "Demo data"


class UsageError(Exception):
    """Base class for fetch failures. ``status`` tells the UI how to present them."""

    status: ClassVar[Status] = Status.UNAVAILABLE


class SignInNeededError(UsageError):
    status = Status.SIGN_IN_NEEDED


class RateLimitedError(UsageError):
    status = Status.RATE_LIMITED

    def __init__(self, message: str = "Rate limited.", retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class UnavailableError(UsageError):
    """The source could not be reached or read."""


class MalformedResponseError(UsageError):
    """The document arrived but failed validation."""


class UsageProvider(Protocol):
    source_label: str

    def fetch(self) -> UsageSnapshot:
        """Blocking call. Runs on a worker thread, never on the GUI thread."""
        ...


def parse_usage_document(doc: object, *, source_label: str) -> UsageSnapshot:
    """Validate the internal usage document. Missing windows become ``None``, never 0%."""
    if not isinstance(doc, dict):
        raise MalformedResponseError("Unexpected data format.")
    data = cast(dict[str, object], doc)

    updated_at = data.get("updated_at")
    if not isinstance(updated_at, str):
        raise MalformedResponseError("Missing updated_at.")

    return UsageSnapshot(
        source_label=source_label,
        data_as_of=_parse_timestamp(updated_at),
        session=_parse_window(data.get("session"), "session"),
        weekly=_parse_window(data.get("weekly"), "weekly"),
    )


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise MalformedResponseError("Invalid timestamp.") from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _parse_window(raw: object, name: str) -> QuotaWindow | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise MalformedResponseError(f"{name}: expected an object.")
    window = cast(dict[str, object], raw)

    used = window.get("used_percent")
    if (
        isinstance(used, bool)
        or not isinstance(used, int | float)
        or not math.isfinite(used)
        or not 0 <= used <= 100
    ):
        raise MalformedResponseError(f"{name}: used_percent must be a number from 0 to 100.")

    resets_raw = window.get("resets_at")
    resets_at: datetime | None = None
    if resets_raw is not None:
        if not isinstance(resets_raw, str):
            raise MalformedResponseError(f"{name}: resets_at must be a string.")
        resets_at = _parse_timestamp(resets_raw)

    return QuotaWindow(used_percent=float(used), resets_at=resets_at)


class FixtureUsageProvider:
    """Reads the internal document from a local JSON file. For development and tests."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self.source_label = f"Fixture: {path.name}"

    def fetch(self) -> UsageSnapshot:
        try:
            if self._path.stat().st_size > MAX_DOCUMENT_BYTES:
                raise MalformedResponseError("Fixture file is too large.")
            doc: object = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Could not read fixture %s", self._path.name)
            raise UnavailableError("Fixture file could not be read.") from exc

        _raise_simulated(doc)
        return parse_usage_document(doc, source_label=self.source_label)


def _raise_simulated(doc: object) -> None:
    """Fixture-only hook: a fixture can name a failure to simulate."""
    if not isinstance(doc, dict):
        return
    kind = doc.get("simulate")
    if kind == "rate_limited":
        retry = doc.get("retry_after_s")
        retry_s = float(retry) if isinstance(retry, int | float) and not isinstance(retry, bool) else None
        raise RateLimitedError("Rate limited (simulated).", retry_s)
    if kind == "sign_in_needed":
        raise SignInNeededError("Sign-in needed (simulated).")
    if kind == "unavailable":
        raise UnavailableError("Unavailable (simulated).")


class DemoUsageProvider:
    """Fixed sample numbers, labeled as demo data. Not related to any account."""

    source_label = DEMO_SOURCE_LABEL

    def fetch(self) -> UsageSnapshot:
        now = datetime.now(UTC)
        doc: dict[str, object] = {
            "updated_at": now.isoformat(),
            "session": {
                "used_percent": 37,
                "resets_at": (now + timedelta(hours=2, minutes=14)).isoformat(),
            },
            "weekly": {
                "used_percent": 82,
                "resets_at": (now + timedelta(days=3, hours=4)).isoformat(),
            },
        }
        return parse_usage_document(doc, source_label=self.source_label)
