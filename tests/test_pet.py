from __future__ import annotations

import pytest

from claude_usage_widget.models import Status
from claude_usage_widget.ui.pet import COLS, MARGIN_ROWS, ROWS, Mood, mood_for, pixels_for


@pytest.mark.parametrize(
    ("status", "peak", "busy", "expected"),
    [
        (Status.CONNECTED, 30, False, Mood.HAPPY),
        (Status.CONNECTED, 75, False, Mood.WORRIED),
        (Status.CONNECTED, 90, False, Mood.ALARMED),
        (Status.CONNECTED, None, False, Mood.HAPPY),
        (Status.STALE, 95, False, Mood.SLEEPY),
        (Status.RATE_LIMITED, 10, False, Mood.SLEEPY),
        (Status.UNAVAILABLE, None, False, Mood.SLEEPY),
        (Status.SIGN_IN_NEEDED, None, False, Mood.SLEEPY),
        (Status.CONNECTED, 95, True, Mood.BUSY),  # a refresh in progress wins over everything
    ],
)
def test_mood_follows_state(status: Status, peak: float | None, busy: bool, expected: Mood) -> None:
    assert mood_for(status, peak, warning=75, critical=90, busy=busy) is expected


@pytest.mark.parametrize("mood", list(Mood))
@pytest.mark.parametrize("tick", range(0, 60, 7))
@pytest.mark.parametrize("hop", [0, 3])
def test_every_frame_stays_inside_the_grid(mood: Mood, tick: int, hop: int) -> None:
    for row, col, role in pixels_for(mood, tick, hop):
        assert -MARGIN_ROWS <= row < ROWS
        assert 0 <= col < COLS
        assert role in {"B", "F", "A"}


def test_blink_closes_the_eyes() -> None:
    open_frame = pixels_for(Mood.HAPPY, tick=10, hop=0)
    blink_frame = pixels_for(Mood.HAPPY, tick=0, hop=0)

    # Blinking adds pixels on the eye row (row 2), so the frame has more face pixels there.
    open_row2 = [c for r, c, role in open_frame if r == 2 and role == "F"]
    blink_row2 = [c for r, c, role in blink_frame if r == 2 and role == "F"]
    assert len(blink_row2) > len(open_row2)


def test_busy_legs_alternate_between_frames() -> None:
    frame_a = sorted(pixels_for(Mood.BUSY, tick=0, hop=0))
    frame_b = sorted(pixels_for(Mood.BUSY, tick=2, hop=0))

    assert frame_a != frame_b


def test_hop_lifts_the_sprite_one_row() -> None:
    resting = {(r, c) for r, c, _ in pixels_for(Mood.HAPPY, tick=0, hop=0)}
    hopping = {(r, c) for r, c, _ in pixels_for(Mood.HAPPY, tick=0, hop=3)}

    assert hopping == {(r - 1, c) for r, c in resting}
