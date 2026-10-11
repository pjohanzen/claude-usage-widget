"""Connection screen: sign-in guidance, connection state, and setup and disconnect actions."""

from __future__ import annotations

import logging
import webbrowser
from datetime import UTC, datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from claude_usage_widget.services.statusline_capture import capture_path
from claude_usage_widget.services.statusline_setup import (
    ConnectionState,
    SettingsFileError,
    SetupResult,
    claude_settings_path,
    clear_widget_data,
    connection_info,
    hook_command,
    install_statusline,
    remove_statusline,
)

log = logging.getLogger(__name__)

CLAUDE_URL = "https://claude.ai"
REFRESH_MS = 10_000

INTRO = (
    "Claude Code signs in to your Claude account with Google or email. This widget never asks for "
    "your Google password or your Claude login, and it does not read Claude Code's login. Once "
    "Claude Code is signed in, the widget reads the usage Claude Code reports through its status line."
)


class ConnectionDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Claude connection")
        self.setMinimumWidth(440)

        intro = QLabel(INTRO)
        intro.setWordWrap(True)
        steps = QLabel(
            "<b>Step 1: sign in.</b> In a terminal, run <code>claude</code> and choose the sign-in option, "
            "using the same Google account as claude.ai.<br><b>Step 2: connect.</b> Click "
            "<i>Set up status line</i> below, then send one message in Claude Code."
        )
        steps.setWordWrap(True)
        self._state = QLabel()
        self._detail = QLabel()
        self._detail.setWordWrap(True)
        self._last = QLabel()
        self._last.setProperty("role", "muted")

        self._sign_in = QPushButton("Open Claude sign-in page")
        self._sign_in.clicked.connect(self._open_sign_in)
        self._setup = QPushButton("Set up status line")
        self._setup.clicked.connect(self._setup_statusline)
        self._disconnect = QPushButton("Disconnect…")
        self._disconnect.clicked.connect(self._disconnect_widget)

        actions = QHBoxLayout()
        actions.addWidget(self._sign_in)
        actions.addWidget(self._setup)
        actions.addWidget(self._disconnect)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(steps)
        layout.addWidget(self._state)
        layout.addWidget(self._detail)
        layout.addWidget(self._last)
        layout.addLayout(actions)
        layout.addWidget(buttons)

        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self.refresh)
        self.refresh()

    def showEvent(self, event: object) -> None:  # noqa: N802 - Qt naming
        self.refresh()
        self._timer.start()
        super().showEvent(event)  # type: ignore[arg-type]

    def hideEvent(self, event: object) -> None:  # noqa: N802 - Qt naming
        self._timer.stop()
        super().hideEvent(event)  # type: ignore[arg-type]

    def refresh(self) -> None:
        info = connection_info(capture_path(), claude_settings_path(), datetime.now(UTC))
        self._state.setText(f"<b>Status: {info.state.value}</b>")
        self._detail.setText(info.detail)
        if info.last_update is None:
            self._last.setText("No usage reported yet.")
        else:
            self._last.setText(f"Last update: {info.last_update.astimezone():%Y-%m-%d %H:%M}")
        self._setup.setEnabled(info.state is ConnectionState.SETUP_NEEDED)
        self._disconnect.setEnabled(
            info.state is not ConnectionState.SETUP_NEEDED or info.last_update is not None
        )

    def _open_sign_in(self) -> None:
        webbrowser.open(CLAUDE_URL)

    def _setup_statusline(self) -> None:
        try:
            result = install_statusline(claude_settings_path(), hook_command())
        except SettingsFileError as exc:
            QMessageBox.warning(
                self, "Set up status line", f"Claude Code's settings could not be changed:\n{exc}"
            )
            return
        messages = {
            SetupResult.INSTALLED: (
                "The status line is set up. Send a message in Claude Code to report usage."
            ),
            SetupResult.ALREADY_CONFIGURED: "The status line was already set up.",
            SetupResult.CONFLICT: (
                "Claude Code already has a status line that this widget did not create, so it was left "
                "unchanged. Remove it in Claude Code's settings, then try again."
            ),
        }
        QMessageBox.information(self, "Set up status line", messages[result])
        self.refresh()

    def _disconnect_widget(self) -> None:
        answer = QMessageBox.question(
            self,
            "Disconnect",
            "Clear the widget's usage data and remove its status-line hook from Claude Code's settings?\n\n"
            "Claude Code's sign-in is not changed.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        clear_widget_data()
        try:
            remove_statusline(claude_settings_path())
        except SettingsFileError as exc:
            log.warning("Could not remove the status-line hook")
            QMessageBox.warning(
                self,
                "Disconnect",
                f"Widget data was cleared, but Claude Code's settings could not be changed:\n{exc}",
            )
        self.refresh()
