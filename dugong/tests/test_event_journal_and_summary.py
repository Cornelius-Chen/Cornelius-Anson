from datetime import datetime, timedelta, timezone

from dugong_app.core.events import DugongEvent
from dugong_app.persistence.event_journal import EventJournal
from dugong_app.services.daily_summary import summarize_events


def test_event_journal_append_and_load(tmp_path) -> None:
    path = tmp_path / "event_journal.jsonl"
    journal = EventJournal(path)

    event = DugongEvent(
        event_type="mode_change",
        timestamp="2026-02-17T10:00:00+00:00",
        event_id="evt_mode_1",
        payload={"mode": "study"},
    )
    journal.append(event)

    loaded = journal.load_all()
    assert len(loaded) == 1
    assert loaded[0].event_type == "mode_change"
    assert loaded[0].payload["mode"] == "study"


def test_event_journal_retention_prunes_old_days(tmp_path) -> None:
    path = tmp_path / "event_journal.jsonl"
    journal = EventJournal(path, retention_days=2)

    today = datetime.now(tz=timezone.utc).date()
    d1 = (today - timedelta(days=2)).isoformat()
    d2 = (today - timedelta(days=1)).isoformat()
    d3 = today.isoformat()

    journal.append(DugongEvent(event_type="click", timestamp=f"{d1}T10:00:00+00:00", payload={}))
    journal.append(DugongEvent(event_type="click", timestamp=f"{d2}T10:00:00+00:00", payload={}))
    journal.append(DugongEvent(event_type="click", timestamp=f"{d3}T10:00:00+00:00", payload={}))

    files = sorted((tmp_path / "event_journal").glob("*.jsonl"))
    names = [f.name for f in files]
    assert names == [f"{d2}.jsonl", f"{d3}.jsonl"]


def test_daily_summary_focus_and_streak() -> None:
    events = [
        DugongEvent(
            event_type="state_tick",
            timestamp="2026-02-16T10:00:00+00:00",
            payload={"mode": "study", "tick_seconds": 60},
        ),
        DugongEvent(
            event_type="state_tick",
            timestamp="2026-02-17T10:00:00+00:00",
            payload={"mode": "study", "tick_seconds": 120},
        ),
        DugongEvent(
            event_type="manual_ping",
            timestamp="2026-02-17T10:01:00+00:00",
            payload={"message": "checkin"},
        ),
    ]

    summary = summarize_events(events)

    assert summary["current_streak_days"] == 2
    assert len(summary["days"]) == 2
    latest = summary["days"][-1]
    assert latest["focus_seconds"] == 120
    assert latest["manual_pings"] == 1
