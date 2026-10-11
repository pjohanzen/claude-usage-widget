"""A small pixel pet that reflects the usage card's state.

``mood_for`` and ``pixels_for`` are pure functions, so they can be tested without a display.
``PetWidget`` only draws the result and runs a low-frequency timer while visible.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QHideEvent, QMouseEvent, QPainter, QPaintEvent, QShowEvent
from PySide6.QtWidgets import QWidget

from claude_usage_widget.models import Status
from claude_usage_widget.ui.formatting import Level, threshold_level

PIXEL: Final = 4
COLS: Final = 10
ROWS: Final = 8
MARGIN_ROWS: Final = 1  # Space above the sprite for bobbing, hopping, and floating marks.
TICK_MS: Final = 160  # About 6 frames per second, which keeps CPU use negligible.

# Sprite parts. 'B' is body, 'F' is face, 'A' is accent. Each pixel is (row, col).
BODY_ROWS: Final = (
    "...BBBB...",
    "..BBBBBB..",
    ".BBBBBBBB.",
    ".BBBBBBBB.",
    ".BBBBBBBB.",
    "..BBBBBB..",
)
LEGS: Final = (
    ("...B..B...", "..B....B.."),  # step A
    ("...B..B...", "...B..B..."),  # step B
)
EYES_OPEN: Final = {(2, 2): "F", (2, 7): "F"}
EYES_CLOSED: Final = {(2, 2): "F", (2, 3): "F", (2, 6): "F", (2, 7): "F"}
MOUTH_SMILE: Final = {(4, 2): "F", (4, 7): "F", (5, 3): "F", (5, 4): "F", (5, 5): "F", (5, 6): "F"}
MOUTH_FROWN: Final = {(5, 2): "F", (5, 7): "F", (4, 3): "F", (4, 4): "F", (4, 5): "F", (4, 6): "F"}
MOUTH_OPEN: Final = {(4, 4): "F", (4, 5): "F", (5, 4): "F", (5, 5): "F"}
MOUTH_SMALL: Final = {(5, 4): "F", (5, 5): "F"}
SWEAT: Final = {(1, 8): "A"}
ZZZ: Final = {(0, 7): "A", (0, 8): "A", (1, 8): "A", (2, 7): "A"}


class Mood(Enum):
    HAPPY = "happy"
    WORRIED = "worried"
    ALARMED = "alarmed"
    SLEEPY = "sleepy"
    BUSY = "busy"


def mood_for(
    status: Status,
    peak_percent: float | None,
    warning: int,
    critical: int,
    busy: bool,
) -> Mood:
    """Pick the pet's mood. A refresh in progress wins; then data health; then usage level."""
    if busy:
        return Mood.BUSY
    if status in (
        Status.LOADING,
        Status.SIGN_IN_NEEDED,
        Status.RATE_LIMITED,
        Status.UNAVAILABLE,
        Status.STALE,
    ):
        return Mood.SLEEPY
    if peak_percent is None:
        return Mood.HAPPY
    level = threshold_level(peak_percent, warning, critical)
    if level is Level.CRITICAL:
        return Mood.ALARMED
    if level is Level.WARNING:
        return Mood.WORRIED
    return Mood.HAPPY


def pixels_for(mood: Mood, tick: int, hop: int) -> list[tuple[int, int, str]]:
    """Return the lit pixels for one frame as (row, col, role) tuples, already positioned.

    Rows are in grid space; row -1 is the margin above the sprite. Roles are 'B', 'F', 'A'.
    """
    offset = -1 if hop > 0 else 0
    if mood is Mood.SLEEPY:
        offset += -((tick // 10) % 2)  # slow breathing
    else:
        offset += -((tick // 3) % 2)  # gentle bob
    offset = max(-MARGIN_ROWS, offset)
    shift = 1 if mood is Mood.ALARMED and tick % 2 else 0  # nervous shake

    grid: dict[tuple[int, int], str] = {}
    for r, row in enumerate(BODY_ROWS):
        for c, ch in enumerate(row):
            if ch == "B":
                grid[(r, c)] = "B"
    fast = mood is Mood.BUSY
    legs = LEGS[((tick // 2) if fast else (tick // 6)) % 2]
    for r_offset, row in enumerate(legs):
        for c, ch in enumerate(row):
            if ch == "B":
                grid[(6 + r_offset, c)] = "B"

    eyes_closed = mood is Mood.SLEEPY or (mood is not Mood.ALARMED and tick % 28 < 2)
    grid.update(EYES_CLOSED if eyes_closed else EYES_OPEN)
    mouth = {
        Mood.HAPPY: MOUTH_SMILE,
        Mood.WORRIED: MOUTH_FROWN,
        Mood.ALARMED: MOUTH_OPEN,
        Mood.SLEEPY: MOUTH_SMALL,
        Mood.BUSY: MOUTH_SMALL,
    }[mood]
    grid.update(mouth)

    if mood in (Mood.WORRIED, Mood.ALARMED):
        grid.update(SWEAT)
    elif mood is Mood.SLEEPY:
        grid.update(ZZZ)
    elif mood is Mood.BUSY and tick % 2:
        grid[(0, 1)] = "A"

    out: list[tuple[int, int, str]] = []
    for (r, c), role in grid.items():
        pixel_row = r + offset
        pixel_col = c + shift
        if -MARGIN_ROWS <= pixel_row < ROWS and 0 <= pixel_col < COLS:
            out.append((pixel_row, pixel_col, role))
    return out


class PetWidget(QWidget):
    """Draws the pet. Animates only while visible. Clicking it makes it hop."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(COLS * PIXEL, (ROWS + MARGIN_ROWS) * PIXEL)
        self.setToolTip("Click me")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mood = Mood.HAPPY
        self._tick = 0
        self._hop = 0
        self._colors = {"B": QColor("#d97757"), "F": QColor("#1f2024"), "A": QColor("#5fb3ff")}
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._advance)

    def set_mood(self, mood: Mood) -> None:
        if mood is not self._mood:
            self._mood = mood
            self.update()

    def set_colors(self, face: str, body: str, accent: str) -> None:
        self._colors = {"B": QColor(body), "F": QColor(face), "A": QColor(accent)}
        self.update()

    def hop(self) -> None:
        self._hop = 3

    def showEvent(self, event: QShowEvent) -> None:
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.hop()
        event.accept()  # Do not let the card start dragging from the pet.

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        for row, col, role in pixels_for(self._mood, self._tick, self._hop):
            painter.setBrush(self._colors[role])
            painter.drawRect(col * PIXEL, (row + MARGIN_ROWS) * PIXEL, PIXEL, PIXEL)
        painter.end()

    def _advance(self) -> None:
        self._tick += 1
        if self._hop:
            self._hop -= 1
        self.update()
