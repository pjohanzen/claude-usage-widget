"""Usage from Claude Code's status line.

Claude Code passes ``rate_limits`` (five-hour and seven-day usage with reset times) to a
status-line command on stdin. ``claude_usage_widget.services.statusline_capture`` saves that object to a
cache file. This provider reads the file. It never touches credentials or the network.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from claude_usage_widget.models import UsageSnapshot
from claude_usage_widget.services.statusline_capture import capture_path
from claude_usage_widget.services.usage_client import (
    MalformedResponseError,
    UnavailableError,
    parse_usage_document,
)

log = logging.getLogger(__name__)

SOURCE_LABEL = "Claude Code status line"


class StatuslineUsageProvider:
    source_label = SOURCE_LABEL

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or capture_path()

    def fetch(self) -> UsageSnapshot:
        try:
            raw: object = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise UnavailableError(
                "No usage reported yet. Connect your Claude account from the widget."
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise UnavailableError("Status-line data could not be read.") from exc
        return parse_usage_document(_to_internal(raw), source_label=self.source_label)


def _to_internal(raw: object) -> dict[str, object]:
    """Convert the captured record to the widget's internal document format."""
    if not isinstance(raw, dict):
        raise MalformedResponseError("Status-line capture is not an object.")
    record = cast(dict[str, Any], raw)

    captured_at = record.get("captured_at")
    if isinstance(captured_at, bool) or not isinstance(captured_at, int | float):
        raise MalformedResponseError("Status-line capture has no captured_at.")
    limits = record.get("rate_limits")
    if not isinstance(limits, dict):
        raise MalformedResponseError("Status-line capture has no rate_limits.")

    doc: dict[str, object] = {"updated_at": _iso(captured_at)}
    for source_key, target_key in (("five_hour", "session"), ("seven_day", "weekly")):
        window = cast(dict[str, Any], limits).get(source_key)
        if not isinstance(window, dict):
            continue  # Claude Code omits windows it does not report; that is "Not provided".
        resets_at = window.get("resets_at")
        # A window whose reset has passed is kept: the UI shows "waiting for new data" for it.
        doc[target_key] = {
            "used_percent": window.get("used_percentage"),
            "resets_at": _iso(resets_at) if isinstance(resets_at, int | float) else None,
        }
    return doc


def _iso(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, UTC).isoformat()
