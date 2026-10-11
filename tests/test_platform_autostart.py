from __future__ import annotations

from pathlib import Path

from claude_usage_widget.platform.linux import LinuxAutostart, desktop_entry
from claude_usage_widget.platform.windows import SCRIPT_NAME, WindowsAutostart, cmd_script


def test_linux_autostart_enable_and_disable(tmp_path: Path) -> None:
    autostart = LinuxAutostart(config_home=tmp_path)

    assert not autostart.is_enabled()
    autostart.enable()
    assert autostart.is_enabled()
    assert (tmp_path / "autostart" / "claude-usage-widget.desktop").is_file()

    autostart.disable()
    assert not autostart.is_enabled()
    autostart.disable()  # removing twice is not an error


def test_desktop_entry_quotes_paths_with_spaces() -> None:
    entry = desktop_entry(["/home/u/claude usage widget/.venv/bin/python", "-m", "claude_usage_widget"])

    assert 'Exec="/home/u/claude usage widget/.venv/bin/python" "-m" "claude_usage_widget"' in entry
    assert "Terminal=false" in entry


def test_desktop_entry_escapes_reserved_characters() -> None:
    entry = desktop_entry(['/opt/a"b$c/run'])

    assert 'Exec="/opt/a\\\\"b\\\\$c/run"' in entry


def test_windows_autostart_writes_and_removes_startup_script(tmp_path: Path) -> None:
    autostart = WindowsAutostart(startup_dir=tmp_path)

    autostart.enable()
    assert autostart.is_enabled()
    assert (tmp_path / SCRIPT_NAME).is_file()

    autostart.disable()
    assert not autostart.is_enabled()


def test_windows_script_starts_app_without_console() -> None:
    script = cmd_script(["C:\\Apps\\Python\\python.exe", "-m", "claude_usage_widget"])

    assert script.startswith("@echo off\r\n")
    assert 'start "" "C:\\Apps\\Python\\python.exe" "-m" "claude_usage_widget"' in script
