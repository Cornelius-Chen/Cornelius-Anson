from dugong_app.core.events import DugongEvent
from dugong_app.services.focus_sessions import build_focus_sessions


def test_focus_session_closed_by_mode_change() -> None:
    events = [
        DugongEvent(
            event_type="mode_change",
            event_id="evt_start",
            timestamp="2026-02-17T10:00:00+00:00",
            payload={"mode": "study"},
        ),
        DugongEvent(
            event_type="mode_change",
            event_id="evt_end",
            timestamp="2026-02-17T10:15:00+00:00",
            payload={"mode": "chill"},
        ),
    ]

    sessions = build_focus_sessions(events)
    assert len(sessions) == 1
    assert sessions[0]["duration_seconds"] == 900
    assert sessions[0]["start_event_id"] == "evt_start"
    assert sessions[0]["end_event_id"] == "evt_end"
    assert sessions[0]["ended_by"] == "mode_change"


def test_focus_session_open_if_no_exit() -> None:
    events = [
        DugongEvent(
            event_type="mode_change",
            event_id="evt_open",
            timestamp="2026-02-17T10:00:00+00:00",
            payload={"mode": "study"},
        ),
    ]

    sessions = build_focus_sessions(events)
    assert len(sessions) == 1
    assert sessions[0]["end_at"] is None
    assert sessions[0]["end_event_id"] is None
    assert sessions[0]["ended_by"] == "open"
