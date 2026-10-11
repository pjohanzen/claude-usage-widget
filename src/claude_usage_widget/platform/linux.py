"""Linux start-at-login via an XDG autostart ``.desktop`` entry. Never needs root or systemd."""

from __future__ import annotations

import os
import re
from pathlib import Path

from claude_usage_widget.platform import launch_argv

APP_ID = "claude-usage-widget"


class LinuxAutostart:
    def __init__(self, config_home: Path | None = None) -> None:
        base = config_home or Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        self._path = base / "autostart" / f"{APP_ID}.desktop"

    def is_enabled(self) -> bool:
        return self._path.is_file()

    def enable(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(desktop_entry(launch_argv()), encoding="utf-8")

    def disable(self) -> None:
        self._path.unlink(missing_ok=True)


def desktop_entry(argv: list[str]) -> str:
    quoted = " ".join(_quote_exec_arg(arg) for arg in argv)
    # The Exec value is a string too, so its backslashes are escaped a second time.
    exec_value = quoted.replace("\\", "\\\\")
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Claude Usage Widget\n"
        "Comment=Compact Claude usage widget\n"
        f"Exec={exec_value}\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def _quote_exec_arg(arg: str) -> str:
    """Always double-quote, escaping the reserved characters inside the quotes."""
    return '"' + re.sub(r'(["`$\\])', r"\\\1", arg) + '"'
