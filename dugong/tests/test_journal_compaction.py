import json
from datetime import datetime, timedelta, timezone

from dugong_app.core.events import DugongEvent
from dugong_app.persistence.event_journal import EventJournal
from dugong_app.services.daily_summary import summarize_events
from dugong_app.services.journal_compaction import compact_daily_journal


def test_compact_daily_journal_preserves_summary_and_shrinks_old_day(tmp_path) -> None:
    journal = EventJournal(tmp_path / "event_journal.jsonl")
    today = datetime.now(tz=timezone.utc).date()
    old_day = (today - timedelta(days=3)).isoformat()
    recent_day = today.isoformat()

    journal.append(
        DugongEvent(
            event_type="mode_change",
            timestamp=f"{old_day}T10:00:00+00:00",
            event_id="old_mode",
            payload={"mode": "study"},
        )
    )
    journal.append(
        DugongEvent(
            event_type="state_tick",
            timestamp=f"{old_day}T10:01:00+00:00",
            event_id="old_tick",
            payload={"mode": "study", "tick_seconds": 120},
        )
    )
    journal.append(
        DugongEvent(
            event_type="manual_ping",
            timestamp=f"{old_day}T10:02:00+00:00",
            event_id="old_ping",
            payload={"message": "x"},
        )
    )
    journal.append(
        DugongEvent(
            event_type="manual_ping",
            timestamp=f"{recent_day}T12:00:00+00:00",
            event_id="recent_ping",
            payload={"message": "y"},
        )
    )

    before = summarize_events(journal.load_all())
    result = compact_daily_journal(tmp_path / "event_journal", keep_days=1, dry_run=False)
    after = summarize_events(journal.load_all())

    assert result["compacted_days"] >= 1
    assert before["days"] == after["days"]

    old_file = tmp_path / "event_journal" / f"{old_day}.jsonl"
    lines = old_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event_type"] == "daily_rollup"
    assert payload["payload"]["rolled_up_event_count"] == 3
    assert payload["payload"]["compaction_version"] == "v1"
    assert payload["payload"]["rolled_up_from_dates"] == [old_day]


def test_compact_daily_journal_is_idempotent(tmp_path) -> None:
    journal = EventJournal(tmp_path / "event_journal.jsonl")
    old_day = (datetime.now(tz=timezone.utc).date() - timedelta(days=10)).isoformat()
    journal.append(
        DugongEvent(
            event_type="manual_ping",
            timestamp=f"{old_day}T10:00:00+00:00",
            event_id="old_1",
            payload={"message": "a"},
        )
    )
    journal.append(
        DugongEvent(
            event_type="manual_ping",
            timestamp=f"{old_day}T10:01:00+00:00",
            event_id="old_2",
            payload={"message": "b"},
        )
    )

    first = compact_daily_journal(tmp_path / "event_journal", keep_days=1, dry_run=False)
    second = compact_daily_journal(tmp_path / "event_journal", keep_days=1, dry_run=False)

    assert first["compacted_days"] == 1
    assert second["compacted_days"] == 0
