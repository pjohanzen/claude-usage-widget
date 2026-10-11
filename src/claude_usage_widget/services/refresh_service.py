"""Background refresh. Fetches run on a thread pool so the UI never blocks."""

from __future__ import annotations

import logging
import time
from typing import Final

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from claude_usage_widget.services.usage_client import (
    RateLimitedError,
    UnavailableError,
    UsageError,
    UsageProvider,
)

log = logging.getLogger(__name__)

MIN_INTERVAL_MS: Final = 60_000
MAX_BACKOFF_MS: Final = 30 * 60_000
MIN_MANUAL_GAP_S: Final = 10.0


def next_interval_ms(base_ms: int, consecutive_rate_limits: int, retry_after_s: float | None) -> int:
    """Return the next timer interval.

    Each consecutive rate limit doubles the interval, up to 30 minutes. A server
    ``Retry-After`` is honored when it asks for longer. Other errors keep the base interval.
    """
    backoff = base_ms
    if consecutive_rate_limits > 0:
        backoff = min(base_ms * 2**consecutive_rate_limits, MAX_BACKOFF_MS)
    if retry_after_s is not None:
        backoff = max(backoff, min(int(retry_after_s * 1000), MAX_BACKOFF_MS))
    return max(MIN_INTERVAL_MS, backoff)


class _FetchSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object)


class _FetchTask(QRunnable):
    def __init__(self, provider: UsageProvider, signals: _FetchSignals) -> None:
        super().__init__()
        self._provider = provider
        self._signals = signals
        self.setAutoDelete(False)

    def run(self) -> None:
        try:
            snapshot = self._provider.fetch()
        except UsageError as exc:
            self._signals.failed.emit(exc)
        except Exception:  # keep the widget alive; details go to the log only
            log.exception("Unexpected error while fetching usage")
            self._signals.failed.emit(UnavailableError("Unexpected error."))
        else:
            self._signals.succeeded.emit(snapshot)


class RefreshService(QObject):
    snapshot_ready = Signal(object)  # UsageSnapshot
    fetch_failed = Signal(object)  # UsageError
    fetch_started = Signal()

    def __init__(self, provider: UsageProvider, interval_minutes: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._provider = provider
        self._base_ms = interval_minutes * 60_000
        self._rate_limits = 0
        self._in_flight = False
        self._last_started = float("-inf")
        self._task: _FetchTask | None = None
        self._signals = _FetchSignals(self)
        self._signals.succeeded.connect(self._on_succeeded)
        self._signals.failed.connect(self._on_failed)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_now)

    def start(self) -> None:
        self._timer.setInterval(self._base_ms)
        self._timer.start()
        self.refresh_now()

    def set_interval_minutes(self, minutes: int) -> None:
        self._base_ms = minutes * 60_000
        self._apply_interval()

    def refresh_now(self) -> None:
        """Start a fetch unless one is running or the last started one was too recent."""
        if self._in_flight or time.monotonic() - self._last_started < MIN_MANUAL_GAP_S:
            return
        self._in_flight = True
        self._last_started = time.monotonic()
        self.fetch_started.emit()
        self._task = _FetchTask(self._provider, self._signals)
        QThreadPool.globalInstance().start(self._task)

    def _apply_interval(self, retry_after_s: float | None = None) -> None:
        self._timer.setInterval(next_interval_ms(self._base_ms, self._rate_limits, retry_after_s))

    def _on_succeeded(self, snapshot: object) -> None:
        self._in_flight = False
        self._rate_limits = 0
        self._apply_interval()
        self.snapshot_ready.emit(snapshot)

    def _on_failed(self, error: object) -> None:
        self._in_flight = False
        if isinstance(error, RateLimitedError):
            self._rate_limits += 1
            self._apply_interval(error.retry_after_s)
        else:
            self._apply_interval()
        self.fetch_failed.emit(error)
