from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

from claude_usage_widget.services import statusline_capture
from claude_usage_widget.services.statusline_source import StatuslineUsageProvider
from claude_usage_widget.services.usage_client import MalformedResponseError, UnavailableError


def load_script() -> ModuleType:
    return statusline_capture


def write_capture(path: Path, record: object) -> None:
    path.write_text(json.dumps(record), encoding="utf-8")


def future(hours: float) -> float:
    return time.time() + hours * 3600


def test_maps_five_hour_and_seven_day_windows(tmp_path: Path) -> None:
    path = tmp_path / "rate_limits.json"
    captured = time.time()
    write_capture(
        path,
        {
            "captured_at": captured,
            "rate_limits": {
                "five_hour": {"used_percentage": 37.5, "resets_at": future(2)},
                "seven_day": {"used_percentage": 58, "resets_at": future(72)},
            },
        },
    )

    snap = StatuslineUsageProvider(path).fetch()

    assert snap.session is not None and snap.session.used_percent == 37.5
    assert snap.weekly is not None and snap.weekly.used_percent == 58.0
    assert snap.session.resets_at is not None
    assert abs(snap.data_as_of.timestamp() - captured) < 1


def test_missing_window_stays_none(tmp_path: Path) -> None:
    path = tmp_path / "rate_limits.json"
    write_capture(
        path,
        {
            "captured_at": time.time(),
            "rate_limits": {"five_hour": {"used_percentage": 10, "resets_at": future(1)}},
        },
    )

    snap = StatuslineUsageProvider(path).fetch()

    assert snap.session is not None
    assert snap.weekly is None


def test_already_reset_window_is_kept_with_past_reset_time(tmp_path: Path) -> None:
    path = tmp_path / "rate_limits.json"
    past = time.time() - 60
    write_capture(
        path,
        {
            "captured_at": time.time(),
            "rate_limits": {"five_hour": {"used_percentage": 99, "resets_at": past}},
        },
    )

    snap = StatuslineUsageProvider(path).fetch()

    # The UI decides how to show it; the parser must not hide the reset from the user.
    assert snap.session is not None
    assert snap.session.resets_at is not None
    assert snap.session.resets_at <= datetime.now(UTC)


def test_missing_capture_file_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(UnavailableError):
        StatuslineUsageProvider(tmp_path / "nope.json").fetch()


@pytest.mark.parametrize(
    "record",
    [
        [],
        {"rate_limits": {}},
        {"captured_at": time.time()},
        {
            "captured_at": time.time(),
            "rate_limits": {"five_hour": {"used_percentage": "lots", "resets_at": future(1)}},
        },
        {"captured_at": time.time(), "rate_limits": {"five_hour": {"used_percentage": 150}}},
    ],
)
def test_malformed_capture_is_rejected(tmp_path: Path, record: object) -> None:
    path = tmp_path / "rate_limits.json"
    write_capture(path, record)

    with pytest.raises(MalformedResponseError):
        StatuslineUsageProvider(path).fetch()


def test_capture_script_summarizes_limits() -> None:
    script = load_script()

    text = script.summarize(
        {"five_hour": {"used_percentage": 37.4}, "seven_day": {"used_percentage": 58, "resets_at": 1}}
    )

    assert text == "5h 37% · 7d 58%"
