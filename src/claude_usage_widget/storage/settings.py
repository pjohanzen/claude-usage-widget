"""User preferences only. Credentials and usage data are never stored here."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

import platformdirs

APP_NAME = "claude-usage-widget"
THEMES: tuple[str, ...] = ("system", "dark", "light")

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Settings:
    refresh_minutes: int = 5
    warning_percent: int = 75
    critical_percent: int = 90
    theme: str = "system"
    opacity: float = 0.95
    always_on_top: bool = True
    launch_at_login: bool = False
    show_pet: bool = True
    compact: bool = False
    window_x: int = -1  # -1 means "not placed yet"
    window_y: int = -1

    def normalized(self) -> Settings:
        """Clamp every value into its valid range."""
        warning = _clamp_int(self.warning_percent, 1, 98)
        return replace(
            self,
            refresh_minutes=_clamp_int(self.refresh_minutes, 1, 60),
            warning_percent=warning,
            critical_percent=_clamp_int(self.critical_percent, warning + 1, 100),
            theme=self.theme if self.theme in THEMES else "system",
            opacity=min(1.0, max(0.3, float(self.opacity))),
        )


def default_settings_path() -> Path:
    """Windows: %APPDATA%\\claude-usage-widget. Linux: $XDG_CONFIG_HOME/claude-usage-widget."""
    return Path(platformdirs.user_config_dir(APP_NAME, appauthor=False, roaming=True)) / "settings.json"


def load_settings(path: Path | None = None) -> Settings:
    target = path or default_settings_path()
    try:
        raw: object = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Settings()
    except (OSError, json.JSONDecodeError):
        log.warning("Ignoring unreadable settings file %s", target)
        return Settings()
    if not isinstance(raw, dict):
        log.warning("Ignoring settings file with unexpected shape: %s", target)
        return Settings()

    defaults = Settings()
    values: dict[str, Any] = {}
    for field in fields(Settings):
        default = getattr(defaults, field.name)
        values[field.name] = _coerce(raw.get(field.name, default), default)
    return Settings(**values).normalized()


def save_settings(settings: Settings, path: Path | None = None) -> None:
    target = path or default_settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)


def _coerce(value: object, default: object) -> Any:
    """Accept the value only if its type matches the default's type."""
    if isinstance(default, bool):
        return value if isinstance(value, bool) else default
    if isinstance(default, int):
        return value if isinstance(value, int) and not isinstance(value, bool) else default
    if isinstance(default, float):
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
        return default
    return value if isinstance(value, str) else default


def _clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))
