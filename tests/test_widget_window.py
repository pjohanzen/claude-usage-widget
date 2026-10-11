"""Window behavior of the card. Runs on the offscreen Qt platform, so no display is needed."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from claude_usage_widget.models import QuotaWindow, UsageSnapshot  # noqa: E402
from claude_usage_widget.storage.settings import Settings  # noqa: E402
from claude_usage_widget.ui.widget import UsageWidget  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])  # type: ignore[return-value]


def test_always_on_top_change_keeps_window_visible(app: QApplication) -> None:
    widget = UsageWidget()
    widget.apply_settings(Settings(always_on_top=True))
    widget.show()

    widget.apply_settings(Settings(always_on_top=False))
    assert widget.isVisible()

    widget.apply_settings(Settings(always_on_top=True))
    assert widget.isVisible()
    widget.close()


def test_opacity_is_applied_and_survives_flag_changes(app: QApplication) -> None:
    widget = UsageWidget()
    widget.apply_settings(Settings(opacity=0.6, always_on_top=True))
    widget.show()

    widget.apply_settings(Settings(opacity=0.6, always_on_top=False))

    assert widget.windowOpacity() == pytest.approx(0.6)
    widget.close()


def test_compact_hides_reset_details_and_expanded_shows_them(app: QApplication) -> None:
    widget = UsageWidget()
    widget.apply_settings(Settings(compact=True))
    widget.show()

    assert widget._session._detail.isHidden()

    widget.apply_settings(Settings(compact=False))
    assert not widget._session._detail.isHidden()
    widget.close()


def test_passed_reset_shows_waiting_state_not_old_percentage(app: QApplication) -> None:
    widget = UsageWidget()
    widget.apply_settings(Settings())
    now = datetime.now(UTC)
    widget.show_snapshot(
        UsageSnapshot("test", now, session=QuotaWindow(99, now - timedelta(minutes=1)), weekly=None)
    )

    assert widget._session._value.text() == "—"
    assert "waiting for new data" in widget._session._detail.text()
    widget.close()
