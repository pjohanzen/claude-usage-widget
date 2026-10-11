from __future__ import annotations

import io
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from claude_usage_widget.services import statusline_capture
from claude_usage_widget.services.statusline_setup import (
    ConnectionState,
    SettingsFileError,
    SetupResult,
    connection_info,
    hook_command,
    install_statusline,
    is_configured,
    remove_statusline,
)

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


def read(path: Path) -> dict[str, object]:
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data


def test_install_creates_settings_file_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"

    assert install_statusline(path, "widget --capture-statusline") is SetupResult.INSTALLED

    assert read(path)["statusLine"] == {"type": "command", "command": "widget --capture-statusline"}
    assert not path.with_name("settings.json.bak").exists()


def test_install_keeps_other_settings_and_backs_up(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}}), encoding="utf-8")

    install_statusline(path, "widget --capture-statusline")

    data = read(path)
    assert data["permissions"] == {"allow": ["Bash(ls)"]}
    assert path.with_name("settings.json.bak").exists()


def test_install_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    install_statusline(path, "widget --capture-statusline")

    assert install_statusline(path, "widget --capture-statusline") is SetupResult.ALREADY_CONFIGURED


def test_install_never_overwrites_a_foreign_status_line(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    original = {"statusLine": {"type": "command", "command": "my-own-bar.sh"}}
    path.write_text(json.dumps(original), encoding="utf-8")

    assert install_statusline(path, "widget --capture-statusline") is SetupResult.CONFLICT
    assert read(path) == original


def test_install_replaces_an_older_widget_entry(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"statusLine": {"type": "command", "command": "python3 /old/statusline_capture.py"}}),
        encoding="utf-8",
    )

    assert install_statusline(path, "widget --capture-statusline") is SetupResult.INSTALLED
    assert read(path)["statusLine"] == {"type": "command", "command": "widget --capture-statusline"}


def test_remove_only_touches_widget_entries(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    install_statusline(path, "widget --capture-statusline")
    assert remove_statusline(path) is True
    assert "statusLine" not in read(path)

    foreign = {"statusLine": {"type": "command", "command": "my-own-bar.sh"}}
    path.write_text(json.dumps(foreign), encoding="utf-8")
    assert remove_statusline(path) is False
    assert read(path) == foreign


def test_unreadable_settings_raise_and_are_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(SettingsFileError):
        install_statusline(path, "widget --capture-statusline")
    assert path.read_text(encoding="utf-8") == "{not json"
    assert is_configured(path) is False


def test_hook_command_uses_the_capture_flag_and_quotes_paths() -> None:
    command = hook_command()

    assert "--capture-statusline" in command


def test_state_setup_needed_without_hook(tmp_path: Path) -> None:
    info = connection_info(tmp_path / "rate_limits.json", tmp_path / "settings.json", NOW)

    assert info.state is ConnectionState.SETUP_NEEDED


def test_state_waiting_when_hook_set_but_no_capture(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    install_statusline(settings, "widget --capture-statusline")

    info = connection_info(tmp_path / "rate_limits.json", settings, NOW)

    assert info.state is ConnectionState.WAITING
    assert info.last_update is None


def test_state_connected_with_recent_capture(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    capture = tmp_path / "rate_limits.json"
    install_statusline(settings, "widget --capture-statusline")
    capture.write_text(json.dumps({"captured_at": NOW.timestamp() - 60, "rate_limits": {}}), encoding="utf-8")

    info = connection_info(capture, settings, NOW)

    assert info.state is ConnectionState.CONNECTED
    assert info.last_update == NOW - timedelta(minutes=1)


def test_state_stale_with_old_capture(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    capture = tmp_path / "rate_limits.json"
    install_statusline(settings, "widget --capture-statusline")
    capture.write_text(json.dumps({"captured_at": NOW.timestamp() - 7200}), encoding="utf-8")

    assert connection_info(capture, settings, NOW).state is ConnectionState.STALE


def test_corrupt_capture_counts_as_no_capture(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    capture = tmp_path / "rate_limits.json"
    install_statusline(settings, "widget --capture-statusline")
    capture.write_text("garbage", encoding="utf-8")

    assert connection_info(capture, settings, NOW).state is ConnectionState.WAITING


def test_capture_hook_saves_limits_from_stdin(tmp_path: Path) -> None:
    target = tmp_path / "rate_limits.json"
    payload = {"rate_limits": {"five_hour": {"used_percentage": 41.2, "resets_at": time.time() + 3600}}}
    out = io.StringIO()

    assert statusline_capture.run(io.StringIO(json.dumps(payload)), out, target) == 0

    assert (
        json.loads(target.read_text(encoding="utf-8"))["rate_limits"]["five_hour"]["used_percentage"] == 41.2
    )
    assert out.getvalue().strip() == "5h 41%"


@pytest.mark.parametrize("stdin_text", ['{"model": {}}', "not json", "[]"])
def test_capture_hook_ignores_input_without_limits(tmp_path: Path, stdin_text: str) -> None:
    target = tmp_path / "rate_limits.json"

    assert statusline_capture.run(io.StringIO(stdin_text), io.StringIO(), target) == 0
    assert not target.exists()
