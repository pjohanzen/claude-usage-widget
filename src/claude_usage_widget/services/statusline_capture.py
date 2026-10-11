"""Claude Code status-line hook. Saves ``rate_limits`` for the widget and prints a short status.

Claude Code runs the status-line command with session JSON on stdin. This hook reads only the
``rate_limits`` field and writes it, with a timestamp, to the widget's cache file. It makes no
network requests, reads no credentials, and never writes anything else.

It is started as ``claude-usage-widget --capture-statusline``, so it must not import Qt.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, TextIO

import platformdirs

APP_NAME = "claude-usage-widget"
CAPTURE_FILENAME = "rate_limits.json"


def capture_path() -> Path:
    """Cache file shared by the hook and the widget."""
    return Path(platformdirs.user_cache_dir(APP_NAME, appauthor=False)) / CAPTURE_FILENAME


def save(limits: dict[str, Any], path: Path | None = None) -> None:
    target = path or capture_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps({"captured_at": time.time(), "rate_limits": limits}), encoding="utf-8")
    os.replace(tmp, target)


def summarize(limits: dict[str, Any]) -> str:
    parts = []
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        window = limits.get(key)
        if isinstance(window, dict) and isinstance(window.get("used_percentage"), int | float):
            parts.append(f"{label} {window['used_percentage']:.0f}%")
    return " · ".join(parts)


def run(stdin: TextIO, stdout: TextIO, path: Path | None = None) -> int:
    """Read one status-line payload. Bad or empty input never breaks Claude Code's status line."""
    try:
        payload = json.load(stdin)
    except json.JSONDecodeError:
        return 0
    limits = payload.get("rate_limits") if isinstance(payload, dict) else None
    if not isinstance(limits, dict):
        return 0  # Not a subscriber, or no API response yet. The last capture is kept.
    try:
        save(limits, path)
    except OSError:
        return 0
    print(summarize(limits), file=stdout)
    return 0


def statusline_main() -> int:
    import sys

    # A windowed Windows build may have no stdin or stdout. Nothing can be read then, so do nothing.
    if sys.stdin is None or sys.stdout is None:
        return 0
    return run(sys.stdin, sys.stdout)
