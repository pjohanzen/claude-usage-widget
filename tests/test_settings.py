from __future__ import annotations

import json
from pathlib import Path

from claude_usage_widget.storage.settings import Settings, load_settings, save_settings


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    assert load_settings(tmp_path / "nope.json") == Settings()


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    original = Settings(refresh_minutes=10, theme="dark", opacity=0.7, window_x=40, window_y=90)

    save_settings(original, path)

    assert load_settings(path) == original


def test_corrupt_json_gives_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")

    assert load_settings(path) == Settings()


def test_wrong_types_fall_back_per_field(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"refresh_minutes": "5", "opacity": 0.5, "theme": "neon", "always_on_top": 1}),
        encoding="utf-8",
    )

    settings = load_settings(path)

    assert settings.refresh_minutes == 5  # string rejected
    assert settings.opacity == 0.5  # valid float kept
    assert settings.theme == "system"  # unknown theme replaced
    assert settings.always_on_top is True  # int is not a bool


def test_out_of_range_values_are_clamped(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"refresh_minutes": 0, "warning_percent": 150, "critical_percent": 3, "opacity": 0.01}),
        encoding="utf-8",
    )

    settings = load_settings(path)

    assert settings.refresh_minutes == 1
    assert settings.warning_percent == 98
    assert settings.critical_percent == 99  # always above warning
    assert settings.opacity == 0.3


def test_unknown_keys_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"api_token": "secret-should-not-load", "theme": "light"}), encoding="utf-8")

    settings = load_settings(path)

    assert settings.theme == "light"
    assert not hasattr(settings, "api_token")


def test_compact_and_pet_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_settings(Settings(compact=True, show_pet=False), path)

    loaded = load_settings(path)

    assert loaded.compact is True
    assert loaded.show_pet is False


def test_defaults_are_documented_values() -> None:
    defaults = Settings()

    assert (defaults.refresh_minutes, defaults.warning_percent, defaults.critical_percent) == (5, 75, 90)
    assert (defaults.theme, defaults.opacity, defaults.always_on_top) == ("system", 0.95, True)
    assert (defaults.launch_at_login, defaults.compact, defaults.show_pet) == (False, False, True)
