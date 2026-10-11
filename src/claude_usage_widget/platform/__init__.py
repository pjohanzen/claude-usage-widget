"""Per-OS adapters. Only the start-at-login mechanism differs between platforms."""

from __future__ import annotations

import os
import sys
from typing import Protocol


class Autostart(Protocol):
    def is_enabled(self) -> bool: ...

    def enable(self) -> None: ...

    def disable(self) -> None: ...


def launch_argv() -> list[str]:
    """Command that starts this app. Uses the AppImage path when packaged as one."""
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return [appimage]
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "claude_usage_widget"]


def get_autostart() -> Autostart | None:
    """Return the start-at-login adapter for this OS, or ``None`` if unsupported."""
    if sys.platform == "win32":
        from claude_usage_widget.platform.windows import WindowsAutostart

        return WindowsAutostart()
    if sys.platform.startswith("linux"):
        from claude_usage_widget.platform.linux import LinuxAutostart

        return LinuxAutostart()
    return None
