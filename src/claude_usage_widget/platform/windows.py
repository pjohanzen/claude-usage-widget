"""Windows start-at-login via a per-user Startup folder entry.

The entry is a small ``.cmd`` script. No registry edits and no administrator rights are
needed, and disabling the option deletes the file.
"""

from __future__ import annotations

import os
from pathlib import Path

from claude_usage_widget.platform import launch_argv

SCRIPT_NAME = "Claude Usage Widget.cmd"


class WindowsAutostart:
    def __init__(self, startup_dir: Path | None = None) -> None:
        self._dir = startup_dir or _default_startup_dir()
        self._path = self._dir / SCRIPT_NAME

    def is_enabled(self) -> bool:
        return self._path.is_file()

    def enable(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path.write_text(cmd_script(launch_argv()), encoding="utf-8")

    def disable(self) -> None:
        self._path.unlink(missing_ok=True)


def cmd_script(argv: list[str]) -> str:
    """Build a script that starts the app without leaving a console window open."""
    exe, *rest = argv
    if exe.lower().endswith("python.exe") and Path(exe).with_name("pythonw.exe").exists():
        exe = str(Path(exe).with_name("pythonw.exe"))
    command = " ".join(f'"{part}"' for part in [exe, *rest])
    return f'@echo off\r\nstart "" {command}\r\n'


def _default_startup_dir() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
