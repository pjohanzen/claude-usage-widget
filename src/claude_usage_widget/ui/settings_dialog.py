"""Settings dialog. Returns a normalized ``Settings``; the caller decides what to apply."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from claude_usage_widget.storage.settings import THEMES, Settings


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, autostart_available: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._original = settings

        self._refresh = QSpinBox()
        self._refresh.setRange(1, 60)
        self._refresh.setSuffix(" min")

        self._warning = QSpinBox()
        self._warning.setRange(1, 98)
        self._warning.setSuffix(" %")

        self._critical = QSpinBox()
        self._critical.setRange(2, 100)
        self._critical.setSuffix(" %")

        self._opacity = QSlider(Qt.Orientation.Horizontal)
        self._opacity.setRange(30, 100)

        self._theme = QComboBox()
        self._theme.addItems(list(THEMES))

        self._on_top = QCheckBox("Keep the widget above other windows")
        self._autostart = QCheckBox("Start when I log in")
        self._show_pet = QCheckBox("Show the pixel pet")
        self._compact = QCheckBox("Compact layout (hide reset details and status line)")
        self._autostart.setEnabled(autostart_available)

        form = QFormLayout()
        form.addRow("Refresh every", self._refresh)
        form.addRow("Warning at", self._warning)
        form.addRow("Critical at", self._critical)
        form.addRow("Opacity", self._opacity)
        form.addRow("Theme", self._theme)
        form.addRow("", self._on_top)
        form.addRow("", self._autostart)
        form.addRow("", self._show_pet)
        form.addRow("", self._compact)

        reset = QPushButton("Reset to defaults")
        reset.clicked.connect(self._load_defaults)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.addButton(reset, QDialogButtonBox.ButtonRole.ResetRole)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._warning.valueChanged.connect(lambda v: self._critical.setMinimum(v + 1))
        self._load(settings)

    def result_settings(self) -> Settings:
        return Settings(
            refresh_minutes=self._refresh.value(),
            warning_percent=self._warning.value(),
            critical_percent=self._critical.value(),
            theme=self._theme.currentText(),
            opacity=self._opacity.value() / 100,
            always_on_top=self._on_top.isChecked(),
            launch_at_login=self._autostart.isChecked(),
            show_pet=self._show_pet.isChecked(),
            compact=self._compact.isChecked(),
            window_x=self._original.window_x,
            window_y=self._original.window_y,
        ).normalized()

    def _load(self, settings: Settings) -> None:
        self._refresh.setValue(settings.refresh_minutes)
        self._warning.setValue(settings.warning_percent)
        self._critical.setValue(settings.critical_percent)
        self._opacity.setValue(round(settings.opacity * 100))
        self._theme.setCurrentText(settings.theme)
        self._on_top.setChecked(settings.always_on_top)
        self._autostart.setChecked(settings.launch_at_login)
        self._show_pet.setChecked(settings.show_pet)
        self._compact.setChecked(settings.compact)

    def _load_defaults(self) -> None:
        self._load(Settings(window_x=self._original.window_x, window_y=self._original.window_y))
