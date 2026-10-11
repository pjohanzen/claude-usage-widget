from __future__ import annotations

from claude_usage_widget.services.refresh_service import MAX_BACKOFF_MS, MIN_INTERVAL_MS, next_interval_ms

BASE = 5 * 60_000


def test_no_failures_uses_base_interval() -> None:
    assert next_interval_ms(BASE, 0, None) == BASE


def test_each_rate_limit_doubles_the_interval() -> None:
    assert next_interval_ms(BASE, 1, None) == 2 * BASE
    assert next_interval_ms(BASE, 2, None) == 4 * BASE


def test_backoff_is_capped() -> None:
    assert next_interval_ms(BASE, 20, None) == MAX_BACKOFF_MS


def test_retry_after_is_honored_when_longer() -> None:
    assert next_interval_ms(BASE, 1, 600.0) == 600_000


def test_retry_after_is_capped() -> None:
    assert next_interval_ms(BASE, 1, 10_000.0) == MAX_BACKOFF_MS


def test_retry_after_shorter_than_base_keeps_base() -> None:
    assert next_interval_ms(BASE, 0, 30.0) == BASE


def test_interval_never_drops_below_minimum() -> None:
    assert next_interval_ms(10_000, 0, None) == MIN_INTERVAL_MS
