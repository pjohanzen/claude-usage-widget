"""Connection setup: the Claude Code status-line hook and the widget's connection state.

This module edits only the ``statusLine`` entry in Claude Code's ``settings.json``, and only with
the user's explicit action. It never reads or writes Claude Code's login files, and it never
overwrites a status line that the widget did not create.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from claude_usage_widget.platform import launch_argv
from claude_usage_widget.services.statusline_capture import capture_path

STATUS_KEY = "statusLine"
HOOK_FLAG = "--capture-statusline"
STALE_AFTER = timedelta(minutes=30)


class SettingsFileError(Exception):
    """Claude Code's settings.json exists but cannot be read as a JSON object."""


class SetupResult(Enum):
    INSTALLED = "installed"
    ALREADY_CONFIGURED = "already configured"
    CONFLICT = "another status line is already set"


class ConnectionState(Enum):
    SETUP_NEEDED = "Setup needed"
    WAITING = "Waiting for Claude Code"
    CONNECTED = "Connected"
    STALE = "Stale"


@dataclass(frozen=True, slots=True)
class ConnectionInfo:
    state: ConnectionState
    detail: str
    last_update: datetime | None


def claude_settings_path() -> Path:
    """Claude Code's user settings file. Honors CLAUDE_CONFIG_DIR like Claude Code does."""
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(base) if base else Path.home() / ".claude") / "settings.json"


def hook_command() -> str:
    """Command Claude Code will run for the status line. Quoted for the current platform."""
    return _quote([*launch_argv(), HOOK_FLAG])


def read_settings(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SettingsFileError(f"{path} is not readable JSON") from exc
    if not isinstance(data, dict):
        raise SettingsFileError(f"{path} does not contain a JSON object")
    return data


def is_widget_entry(entry: object) -> bool:
    """True for a status-line entry this widget created (the current hook or the older script)."""
    if not isinstance(entry, dict):
        return False
    command = str(entry.get("command", ""))
    return HOOK_FLAG in command or "statusline_capture" in command


def install_statusline(path: Path, command: str) -> SetupResult:
    data = read_settings(path)
    current = data.get(STATUS_KEY)
    if isinstance(current, dict) and current.get("command") == command:
        return SetupResult.ALREADY_CONFIGURED
    if current is not None and not is_widget_entry(current):
        return SetupResult.CONFLICT
    data[STATUS_KEY] = {"type": "command", "command": command}
    _write(path, data)
    return SetupResult.INSTALLED


def remove_statusline(path: Path) -> bool:
    """Remove only a status line this widget created. Returns True if something was removed."""
    data = read_settings(path)
    if not is_widget_entry(data.get(STATUS_KEY)):
        return False
    del data[STATUS_KEY]
    _write(path, data)
    return True


def is_configured(path: Path) -> bool:
    try:
        return is_widget_entry(read_settings(path).get(STATUS_KEY))
    except SettingsFileError:
        return False


def clear_widget_data() -> None:
    """Delete the widget's own cache file. Nothing else is touched."""
    capture_path().unlink(missing_ok=True)


def connection_info(
    capture_file: Path,
    settings_file: Path,
    now: datetime,
) -> ConnectionInfo:
    """Work out the connection state from the two files. Pure apart from reading them."""
    last_update = _last_capture(capture_file)
    if not is_configured(settings_file):
        return ConnectionInfo(
            ConnectionState.SETUP_NEEDED,
            "Set up the status line so Claude Code can report your usage to the widget.",
            last_update,
        )
    if last_update is None:
        return ConnectionInfo(
            ConnectionState.WAITING,
            "Sign in to Claude Code, then send one message. Usage appears after Claude Code's next response.",
            None,
        )
    if now - last_update > STALE_AFTER:
        return ConnectionInfo(
            ConnectionState.STALE,
            "Claude Code has not reported usage recently. Open Claude Code to refresh, or sign in again "
            "if it asks.",
            last_update,
        )
    return ConnectionInfo(ConnectionState.CONNECTED, "Usage is reported by Claude Code.", last_update)


def _last_capture(path: Path) -> datetime | None:
    try:
        record: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict):
        return None
    captured = record.get("captured_at")
    if isinstance(captured, bool) or not isinstance(captured, int | float):
        return None
    return datetime.fromtimestamp(captured, UTC)


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))  # Keep the previous version.
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _quote(argv: list[str]) -> str:
    if sys.platform == "win32":
        return " ".join('"' + part.replace('"', '\\"') + '"' for part in argv)
    return " ".join(shlex.quote(part) for part in argv)
