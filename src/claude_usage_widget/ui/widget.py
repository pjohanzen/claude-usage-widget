"""Compact, frameless, draggable usage card."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Final

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QMouseEvent, QMoveEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from claude_usage_widget.models import QuotaWindow, Status, UsageSnapshot
from claude_usage_widget.storage.settings import Settings
from claude_usage_widget.ui.formatting import (
    Level,
    format_age,
    format_percent,
    format_reset_detail,
    threshold_level,
)
from claude_usage_widget.ui.pet import PetWidget, mood_for
from claude_usage_widget.ui.styles import palette_for, stylesheet

CARD_WIDTH: Final = 300
FOOTER_REFRESH_MS: Final = 30_000
ERROR_STATUSES: Final = frozenset({Status.SIGN_IN_NEEDED, Status.RATE_LIMITED, Status.UNAVAILABLE})
POSITION_SAVE_DELAY_MS: Final = 500
PET_BODY_COLOR: Final = "#d97757"
PET_ACCENT_COLOR: Final = "#5fb3ff"


def can_remember_position() -> bool:
    """Wayland hides window positions from apps, so a saved position could never be restored."""
    return QGuiApplication.platformName() != "wayland"


class QuotaRow(QWidget):
    """One quota: title, percentage, progress bar, and reset countdown."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self._value = QLabel("—")
        self._value.setObjectName("value")
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self._detail = QLabel()
        self._detail.setProperty("role", "muted")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(QLabel(title))
        header.addStretch(1)
        header.addWidget(self._value)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(header)
        layout.addWidget(self._bar)
        layout.addWidget(self._detail)

    def show_window(self, window: QuotaWindow | None, now: datetime, warning: int, critical: int) -> None:
        if window is None:
            self._apply("Not provided", "Not reported by the data source", None, None)
            return
        if window.resets_at is not None and window.resets_at <= now:
            # The old percentage belongs to a period that has ended, so it is not shown as current.
            self._apply("—", format_reset_detail(window.resets_at, now), None, None)
            return
        level = threshold_level(window.used_percent, warning, critical)
        self._apply(
            format_percent(window.used_percent),
            format_reset_detail(window.resets_at, now),
            level,
            window.used_percent,
        )

    def set_compact(self, compact: bool) -> None:
        self._detail.setVisible(not compact)

    def show_unavailable(self) -> None:
        self._apply("—", "No data", None, None)

    def _apply(self, value: str, detail: str, level: Level | None, percent: float | None) -> None:
        self._value.setText(value)
        self._detail.setText(detail)
        # Hide the bar instead of drawing a fake 0% when there is no real number.
        self._bar.setVisible(percent is not None)
        if percent is not None:
            self._bar.setValue(round(percent))
        self._bar.setProperty("level", level.value if level else "normal")
        self._bar.style().unpolish(self._bar)
        self._bar.style().polish(self._bar)


class UsageWidget(QWidget):
    refresh_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()
    position_changed = Signal(int, int)
    pin_toggled = Signal(bool)
    connection_requested = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setObjectName("card")
        self.setFixedWidth(CARD_WIDTH)

        self._settings = Settings()
        self._snapshot: UsageSnapshot | None = None
        self._status = Status.LOADING
        self._detail = ""
        self._drag_offset: QPoint | None = None
        self._busy = False

        self._pet = PetWidget()
        self._title = QLabel("Claude")
        self._title.setObjectName("title")
        # Clicking the status opens the connection screen.
        self._status_label = QToolButton()
        self._status_label.setText(Status.LOADING.value)
        self._status_label.setToolTip("Connection details")
        self._status_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._status_label.setAutoRaise(True)
        self._status_label.clicked.connect(lambda: self.connection_requested.emit())
        self._pin_btn = QToolButton()
        self._pin_btn.setText("📌")
        self._pin_btn.setToolTip("Keep on top")
        self._pin_btn.setCheckable(True)
        self._pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pin_btn.toggled.connect(self._on_pin_toggled)
        self._refresh_btn = self._tool_button("⟳", "Refresh now", self.refresh_requested.emit)
        self._settings_btn = self._tool_button("⚙", "Settings", self.settings_requested.emit)
        self._minimize_btn = self._tool_button("–", "Hide to tray", self.hide)
        self._close_btn = self._tool_button("✕", "Quit", self.quit_requested.emit)

        self._session = QuotaRow("Current session")
        self._weekly = QuotaRow("Weekly")

        # Visible whenever the Claude connection needs attention; opens the connection screen.
        self._connect_btn = QPushButton()
        self._connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._connect_btn.clicked.connect(lambda: self.connection_requested.emit())
        self._connect_btn.hide()

        self._note = QLabel()
        self._note.setWordWrap(True)
        self._note.setProperty("role", "muted")
        self._note.hide()

        self._footer = QLabel()
        self._footer.setProperty("role", "muted")

        header = QHBoxLayout()
        header.setSpacing(2)
        header.addWidget(self._pet)
        header.addWidget(self._title)
        header.addStretch(1)
        for button in (
            self._pin_btn,
            self._refresh_btn,
            self._settings_btn,
            self._minimize_btn,
            self._close_btn,
        ):
            header.addWidget(button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        layout.addLayout(header)
        layout.addWidget(self._status_label)
        layout.addWidget(self._session)
        layout.addWidget(self._weekly)
        layout.addWidget(self._connect_btn)
        layout.addWidget(self._note)
        layout.addWidget(self._footer)

        self._footer_timer = QTimer(self)
        self._footer_timer.timeout.connect(self._render)
        self._footer_timer.start(FOOTER_REFRESH_MS)

        self._save_position_timer = QTimer(self)
        self._save_position_timer.setSingleShot(True)
        self._save_position_timer.setInterval(POSITION_SAVE_DELAY_MS)
        self._save_position_timer.timeout.connect(self._emit_position)

        styles = QGuiApplication.styleHints()
        styles.colorSchemeChanged.connect(lambda _scheme: self._apply_theme())

        self._render()

    # Public API

    def apply_settings(self, settings: Settings) -> None:
        self._settings = settings
        self._pet.setVisible(settings.show_pet)
        self._pin_btn.blockSignals(True)
        self._pin_btn.setChecked(settings.always_on_top)
        self._pin_btn.blockSignals(False)
        # Set the flags first: changing window flags can recreate the native window.
        self._set_on_top(settings.always_on_top)
        self.setWindowOpacity(settings.opacity)
        self._apply_compact(settings.compact)
        self._apply_theme()
        self._render()

    def set_connection_prompt(self, text: str | None) -> None:
        """Show a call to action on the card, or hide it when text is None."""
        self._connect_btn.setVisible(text is not None)
        if text is not None:
            self._connect_btn.setText(text)

    def set_tray_available(self, available: bool) -> None:
        # Without a tray, hiding the widget would leave no way to bring it back.
        self._minimize_btn.setEnabled(available)

    def set_busy(self, busy: bool) -> None:
        """Mark a refresh in progress so the pet runs. Cleared by the next result."""
        self._busy = busy
        self._render()

    def show_snapshot(self, snapshot: UsageSnapshot) -> None:
        self._snapshot = snapshot
        self._status = Status.CONNECTED
        self._detail = ""
        self._busy = False
        self._render()

    def show_status(self, status: Status, detail: str = "") -> None:
        self._status = status
        self._detail = detail
        self._busy = False
        self._render()

    # Internals

    def _on_pin_toggled(self, checked: bool) -> None:
        self._set_on_top(checked)
        self.pin_toggled.emit(checked)

    def _tool_button(self, text: str, tooltip: str, on_click: Callable[[], object]) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda: on_click())
        return button

    def _apply_theme(self) -> None:
        dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        palette = palette_for(self._settings.theme, dark)
        self.setStyleSheet(stylesheet(palette))
        self._pet.set_colors(face=palette.text, body=PET_BODY_COLOR, accent=PET_ACCENT_COLOR)

    def _set_on_top(self, on: bool) -> None:
        if bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) == on:
            return
        was_visible = self.isVisible()  # Changing flags hides the window, so remember this first.
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on)
        self.setWindowOpacity(self._settings.opacity)  # The flag change also recreates the native window.
        if was_visible:
            self.show()

    def _apply_compact(self, compact: bool) -> None:
        # Compact keeps the bars, values, and staleness footer; it drops the status line and reset details.
        self._status_label.setVisible(not compact)
        self._session.set_compact(compact)
        self._weekly.set_compact(compact)

    def _effective_status(self, now: datetime) -> Status:
        if self._status is Status.CONNECTED and self._snapshot is not None:
            interval = timedelta(minutes=self._settings.refresh_minutes)
            if self._snapshot.is_stale(now, interval):
                return Status.STALE
        return self._status

    def _peak_percent(self) -> float | None:
        if self._snapshot is None:
            return None
        values = [w.used_percent for w in (self._snapshot.session, self._snapshot.weekly) if w is not None]
        return max(values) if values else None

    def _render(self) -> None:
        now = datetime.now(UTC)
        status = self._effective_status(now)
        self._status_label.setText(status.value)

        self._note.setText(self._detail)
        self._note.setVisible(status in ERROR_STATUSES and bool(self._detail))

        snapshot = self._snapshot
        self._pet.set_mood(
            mood_for(
                status,
                self._peak_percent(),
                self._settings.warning_percent,
                self._settings.critical_percent,
                self._busy,
            )
        )
        if snapshot is None:
            self._session.show_unavailable()
            self._weekly.show_unavailable()
            self._footer.setText("No data yet")
            return

        warning, critical = self._settings.warning_percent, self._settings.critical_percent
        self._session.show_window(snapshot.session, now, warning, critical)
        self._weekly.show_window(snapshot.weekly, now, warning, critical)
        self._footer.setText(f"Updated {format_age(snapshot.data_as_of, now)} · {snapshot.source_label}")

    # Dragging

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # On Wayland an app cannot move its own window, so ask the compositor to run the drag.
            handle = self.windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
            # X11 and other platforms: move the window ourselves.
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def moveEvent(self, event: QMoveEvent) -> None:
        # Save once the window has stopped moving, so a drag does not write settings on every pixel.
        if can_remember_position():
            self._save_position_timer.start()
        super().moveEvent(event)

    def _emit_position(self) -> None:
        self.position_changed.emit(self.x(), self.y())
