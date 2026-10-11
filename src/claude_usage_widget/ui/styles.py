"""Theme tokens and the application stylesheet."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    background: str
    border: str
    text: str
    muted: str
    track: str
    normal: str
    warning: str
    critical: str


DARK = Palette(
    background="#1c1d21",
    border="#2f3138",
    text="#eceef2",
    muted="#9a9fab",
    track="#2e3038",
    normal="#4fb286",
    warning="#e0a33a",
    critical="#e5534b",
)

LIGHT = Palette(
    background="#fbfbfa",
    border="#dcdcd8",
    text="#1f2024",
    muted="#6b6f78",
    track="#e4e4e0",
    normal="#2f8f63",
    warning="#b87a12",
    critical="#c83a32",
)


def palette_for(theme: str, system_is_dark: bool) -> Palette:
    if theme == "dark":
        return DARK
    if theme == "light":
        return LIGHT
    return DARK if system_is_dark else LIGHT


def stylesheet(p: Palette) -> str:
    return f"""
    QWidget#card {{
        background: {p.background};
        border: 1px solid {p.border};
        border-radius: 12px;
    }}
    QLabel {{ color: {p.text}; background: transparent; }}
    QLabel#title {{ font-weight: 600; font-size: 13px; }}
    QLabel#value {{ font-weight: 600; }}
    QLabel[role="muted"] {{ color: {p.muted}; font-size: 11px; }}
    QToolButton {{ color: {p.muted}; border: none; padding: 2px 5px; }}
    QToolButton:hover {{ color: {p.text}; }}
    QToolButton:disabled {{ color: {p.track}; }}
    QProgressBar {{ background: {p.track}; border: none; border-radius: 4px; }}
    QProgressBar[level="normal"]::chunk {{ background: {p.normal}; border-radius: 4px; }}
    QProgressBar[level="warning"]::chunk {{ background: {p.warning}; border-radius: 4px; }}
    QProgressBar[level="critical"]::chunk {{ background: {p.critical}; border-radius: 4px; }}
    """
