from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from claude_usage_widget.services.usage_client import (
    FixtureUsageProvider,
    MalformedResponseError,
    RateLimitedError,
    SignInNeededError,
    UnavailableError,
    parse_usage_document,
)

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
LABEL = "test"


def load(name: str) -> dict[str, object]:
    doc: dict[str, object] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return doc


def doc_with(**windows: object) -> dict[str, object]:
    return {"updated_at": "2026-10-11T12:00:00Z", **windows}


def test_valid_document_parses_both_windows() -> None:
    snap = parse_usage_document(load("valid.json"), source_label=LABEL)

    assert snap.session is not None
    assert snap.session.used_percent == 42.5
    assert snap.session.resets_at == datetime(2026, 10, 11, 14, 30, tzinfo=UTC)
    assert snap.weekly is not None
    assert snap.weekly.used_percent == 61.0
    assert snap.data_as_of == NOW


def test_missing_window_is_none_not_zero() -> None:
    snap = parse_usage_document(load("partial.json"), source_label=LABEL)

    assert snap.session is not None
    assert snap.weekly is None


def test_missing_reset_time_is_none() -> None:
    snap = parse_usage_document(doc_with(session={"used_percent": 10}), source_label=LABEL)

    assert snap.session is not None
    assert snap.session.resets_at is None


def test_naive_timestamp_is_treated_as_utc() -> None:
    doc = {
        "updated_at": "2026-10-11T12:00:00",
        "session": {"used_percent": 1, "resets_at": "2026-10-11T13:00:00"},
    }
    snap = parse_usage_document(doc, source_label=LABEL)

    assert snap.data_as_of == NOW
    assert snap.session is not None
    assert snap.session.resets_at == datetime(2026, 10, 11, 13, tzinfo=UTC)


@pytest.mark.parametrize(
    "doc",
    [
        [],
        "not an object",
        {"session": {"used_percent": 5}},
        {"updated_at": 12345, "session": {"used_percent": 5}},
        {"updated_at": "yesterday-ish"},
        doc_with(session="42%"),
        doc_with(session={"used_percent": "lots"}),
        doc_with(session={"used_percent": True}),
        doc_with(session={"used_percent": -1}),
        doc_with(session={"used_percent": 101}),
        doc_with(session={"used_percent": float("nan")}),
        doc_with(session={"used_percent": 5, "resets_at": 1234}),
        doc_with(session={"used_percent": 5, "resets_at": "tomorrow"}),
    ],
)
def test_malformed_documents_are_rejected(doc: object) -> None:
    with pytest.raises(MalformedResponseError):
        parse_usage_document(doc, source_label=LABEL)


def test_snapshot_is_stale_after_two_refresh_cycles() -> None:
    snap = parse_usage_document(load("valid.json"), source_label=LABEL)

    assert not snap.is_stale(NOW + timedelta(minutes=5), timedelta(minutes=5))
    assert snap.is_stale(NOW + timedelta(minutes=30), timedelta(minutes=5))


def test_old_fixture_is_stale() -> None:
    snap = parse_usage_document(load("stale.json"), source_label=LABEL)

    assert snap.is_stale(NOW, timedelta(minutes=5))


def test_future_timestamp_is_stale_not_fresh() -> None:
    snap = parse_usage_document(load("valid.json"), source_label=LABEL)

    assert snap.is_stale(NOW - timedelta(hours=4), timedelta(minutes=5))


def test_small_clock_skew_is_not_stale() -> None:
    snap = parse_usage_document(load("valid.json"), source_label=LABEL)

    assert not snap.is_stale(NOW - timedelta(minutes=2), timedelta(minutes=5))


def test_fixture_provider_returns_valid_snapshot() -> None:
    snap = FixtureUsageProvider(FIXTURES / "valid.json").fetch()

    assert snap.session is not None
    assert snap.source_label == "Fixture: valid.json"


def test_fixture_provider_reports_malformed_file() -> None:
    with pytest.raises(MalformedResponseError):
        FixtureUsageProvider(FIXTURES / "malformed.json").fetch()


def test_fixture_provider_reports_missing_file() -> None:
    with pytest.raises(UnavailableError):
        FixtureUsageProvider(FIXTURES / "does_not_exist.json").fetch()


def test_fixture_provider_simulates_rate_limit_with_retry_after() -> None:
    with pytest.raises(RateLimitedError) as info:
        FixtureUsageProvider(FIXTURES / "rate_limited.json").fetch()

    assert info.value.retry_after_s == 120.0


def test_fixture_provider_simulates_sign_in_needed() -> None:
    with pytest.raises(SignInNeededError):
        FixtureUsageProvider(FIXTURES / "sign_in_needed.json").fetch()
