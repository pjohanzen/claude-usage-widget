"""Wiring: connects the UI, refresh service, settings, tray, and platform adapters."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QMessageBox,
    QStyle,
    QSystemTrayIcon,
)

from claude_usage_widget.models import Status, UsageSnapshot
from claude_usage_widget.platform import Autostart, get_autostart
from claude_usage_widget.services.refresh_service import RefreshService
from claude_usage_widget.services.statusline_capture import capture_path
from claude_usage_widget.services.statusline_setup import (
    ConnectionState,
    claude_settings_path,
    connection_info,
)
from claude_usage_widget.services.usage_client import UsageError, UsageProvider
from claude_usage_widget.storage.settings import Settings, save_settings
from claude_usage_widget.ui.connection_dialog import ConnectionDialog
from claude_usage_widget.ui.settings_dialog import SettingsDialog
from claude_usage_widget.ui.widget import UsageWidget, can_remember_position

log = logging.getLogger(__name__)


class WidgetController(QObject):
    def __init__(
        self,
        qapp: QApplication,
        provider: UsageProvider,
        settings: Settings,
        settings_path: Path,
    ) -> None:
        super().__init__()
        self._qapp = qapp
        self._settings = settings
        self._settings_path = settings_path
        self._last_snapshot: UsageSnapshot | None = None
        self._autostart: Autostart | None = get_autostart()

        self._widget = UsageWidget()
        self._icon = QIcon.fromTheme(
            "utilities-system-monitor",
            qapp.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon),
        )
        self._widget.setWindowIcon(self._icon)

        self._refresh = RefreshService(provider, settings.refresh_minutes, self)
        self._tray_menu = QMenu()
        self._tray = self._build_tray()
        self._widget.set_tray_available(self._tray is not None)

        self._widget.refresh_requested.connect(self._refresh.refresh_now)
        self._widget.settings_requested.connect(self.open_settings)
        self._widget.quit_requested.connect(qapp.quit)
        self._widget.position_changed.connect(self._on_position_changed)
        self._widget.pin_toggled.connect(self._on_pin_toggled)
        self._widget.connection_requested.connect(self.open_connection)
        self._connection_dialog: ConnectionDialog | None = None
        self._refresh.fetch_started.connect(self._on_fetch_started)
        self._refresh.snapshot_ready.connect(self._on_snapshot)
        self._refresh.fetch_failed.connect(self._on_failed)

        self._widget.apply_settings(settings)

    def open_connection(self) -> None:
        if self._connection_dialog is None:
            self._connection_dialog = ConnectionDialog(parent=self._widget)
            self._connection_dialog.finished.connect(lambda _code: self._update_connection_prompt())
        self._connection_dialog.show()
        self._connection_dialog.raise_()
        self._connection_dialog.activateWindow()

    def _update_connection_prompt(self) -> None:
        info = connection_info(capture_path(), claude_settings_path(), datetime.now(UTC))
        prompts = {
            ConnectionState.SETUP_NEEDED: "Set up Claude connection…",
            ConnectionState.WAITING: "Finish connecting Claude…",
            ConnectionState.STALE: "Reconnect Claude…",
        }
        self._widget.set_connection_prompt(prompts.get(info.state))

    def _show_connection_on_first_run(self) -> None:
        info = connection_info(capture_path(), claude_settings_path(), datetime.now(UTC))
        if info.state is ConnectionState.SETUP_NEEDED:
            log.info("Status line not set up; opening the connection screen")
            self.open_connection()

    def start(self) -> None:
        self._reconcile_autostart()
        self._restore_position()
        self._widget.show()
        self._update_connection_prompt()
        self._refresh.start()
        QTimer.singleShot(0, self._show_connection_on_first_run)

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            self._settings,
            autostart_available=self._autostart is not None,
            parent=self._widget,
        )
        if dialog.exec():
            self._apply_new_settings(dialog.result_settings())

    # Settings

    def _apply_new_settings(self, new: Settings) -> None:
        old = self._settings
        self._settings = new
        if not self._persist():
            QMessageBox.warning(
                self._widget,
                "Settings",
                "Settings were applied but could not be saved. They will be lost when the widget closes.",
            )
        self._widget.apply_settings(new)
        if new.refresh_minutes != old.refresh_minutes:
            self._refresh.set_interval_minutes(new.refresh_minutes)
        if new.launch_at_login != old.launch_at_login:
            self._set_autostart(new.launch_at_login)

    def _set_autostart(self, enabled: bool) -> None:
        if self._autostart is None:
            return
        try:
            if enabled:
                self._autostart.enable()
            else:
                self._autostart.disable()
        except OSError as exc:
            log.warning("Could not change start-at-login entry")
            QMessageBox.warning(self._widget, "Start at login", f"Could not change the login setting:\n{exc}")
        # Keep the saved preference in line with what actually happened on disk.
        self._settings = replace(self._settings, launch_at_login=self._autostart.is_enabled())
        self._persist()

    def _reconcile_autostart(self) -> None:
        """The OS entry is the truth for start-at-login. Also rewrite it so it points at the running build."""
        if self._autostart is None:
            return
        try:
            if self._settings.launch_at_login:
                self._autostart.enable()  # Idempotent; refreshes the path after an AppImage moves.
            actual = self._autostart.is_enabled()
        except OSError:
            log.warning("Could not update the start-at-login entry")
            actual = self._autostart.is_enabled()
        if actual != self._settings.launch_at_login:
            self._settings = replace(self._settings, launch_at_login=actual)
            self._persist()

    def _persist(self) -> bool:
        try:
            save_settings(self._settings, self._settings_path)
        except OSError:
            log.warning("Could not save settings to %s", self._settings_path)
            return False
        return True

    def _on_pin_toggled(self, pinned: bool) -> None:
        self._settings = replace(self._settings, always_on_top=pinned)
        self._persist()

    def _on_position_changed(self, x: int, y: int) -> None:
        self._settings = replace(self._settings, window_x=x, window_y=y)
        self._persist()

    def _restore_position(self) -> None:
        s = self._settings
        if s.window_x < 0 or s.window_y < 0 or not can_remember_position():
            return
        point = QPoint(s.window_x, s.window_y)
        # Only restore onto a screen that still exists, e.g. after a monitor was unplugged.
        if QGuiApplication.screenAt(point) is not None:
            self._widget.move(point)

    # Refresh results

    def _on_fetch_started(self) -> None:
        self._widget.set_busy(True)
        if self._last_snapshot is None:
            self._widget.show_status(Status.LOADING)

    def _on_snapshot(self, snapshot: object) -> None:
        if not isinstance(snapshot, UsageSnapshot):
            return
        self._last_snapshot = snapshot
        self._widget.show_snapshot(snapshot)
        self._update_connection_prompt()
        log.debug("Usage refreshed")

    def _on_failed(self, error: object) -> None:
        if isinstance(error, UsageError):
            # The widget keeps the last good snapshot and marks it stale or failed.
            self._widget.show_status(error.status, str(error))
        self._update_connection_prompt()

    # Tray

    def _build_tray(self) -> QSystemTrayIcon | None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.info("No system tray available; the widget stays on screen")
            return None
        tray = QSystemTrayIcon(self._icon, self)
        tray.setToolTip("Claude Usage Widget")
        self._tray_menu.addAction("Show / hide", self._toggle_widget)
        self._tray_menu.addAction("Refresh now", self._refresh.refresh_now)
        self._tray_menu.addAction("Claude connection…", self.open_connection)
        self._tray_menu.addAction("Settings…", self.open_settings)
        self._tray_menu.addSeparator()
        self._tray_menu.addAction("Quit", self._qapp.quit)
        tray.setContextMenu(self._tray_menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        return tray

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_widget()

    def _toggle_widget(self) -> None:
        if self._widget.isVisible():
            self._widget.hide()
        else:
            self._widget.show()
            self._widget.raise_()
            self._widget.activateWindow()


def run_app(provider: UsageProvider, settings: Settings, settings_path: Path) -> int:
    qapp = QApplication.instance() or QApplication([])
    if not isinstance(qapp, QApplication):
        raise RuntimeError("A QApplication is required")
    qapp.setApplicationName("Claude Usage Widget")
    qapp.setOrganizationName("claude-usage-widget")
    qapp.setQuitOnLastWindowClosed(False)
    controller = WidgetController(qapp, provider, settings, settings_path)
    controller.start()
    return qapp.exec()
