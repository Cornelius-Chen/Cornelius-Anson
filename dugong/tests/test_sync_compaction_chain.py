from datetime import datetime, timedelta, timezone

from dugong_app.core.events import DugongEvent, manual_ping_event
from dugong_app.interaction.transport_file import FileTransport
from dugong_app.persistence.event_journal import EventJournal
from dugong_app.persistence.sync_cursor_json import SyncCursorStorage
from dugong_app.services.daily_summary import summarize_events
from dugong_app.services.journal_compaction import compact_daily_journal
from dugong_app.services.sync_engine import SyncEngine


def test_chain_a_compaction_then_sync_with_legacy_cursor(tmp_path) -> None:
    shared = tmp_path / "shared"
    a_journal = EventJournal(tmp_path / "a" / "event_journal.jsonl")
    b_journal = EventJournal(tmp_path / "b" / "event_journal.jsonl")
    b_cursor_path = tmp_path / "b" / "sync_cursor.json"

    old_day = (datetime.now(tz=timezone.utc).date() - timedelta(days=9)).isoformat()
    a_journal.append(
        DugongEvent(
            event_type="manual_ping",
            timestamp=f"{old_day}T10:00:00+00:00",
            event_id="a_old_1",
            source="cornelius",
            payload={"message": "x"},
        )
    )
    a_journal.append(
        DugongEvent(
            event_type="mode_change",
            timestamp=f"{old_day}T10:01:00+00:00",
            event_id="a_old_2",
            source="cornelius",
            payload={"mode": "study"},
        )
    )
    compact_daily_journal(tmp_path / "a" / "event_journal", keep_days=1, dry_run=False)
    rollup = next(e for e in a_journal.load_all() if e.event_type == "daily_rollup")

    # Legacy flat cursor format.
    SyncCursorStorage(b_cursor_path).save({"file_cursors": {"cornelius.jsonl": 0}})
    b_cursor_path.write_text('{"cornelius.jsonl":0}', encoding="utf-8")

    a_engine = SyncEngine(source_id="cornelius", journal=a_journal, transport=FileTransport(shared, "cornelius"))
    b_engine = SyncEngine(
        source_id="anson",
        journal=b_journal,
        transport=FileTransport(shared, "anson"),
        cursor_storage=SyncCursorStorage(b_cursor_path),
    )

    a_engine.publish_local_event(rollup)
    first = b_engine.sync_once()
    second = b_engine.sync_once()

    assert first["imported"] == 1
    assert second["imported"] == 0

    # Restart B and continue incremental.
    b_engine2 = SyncEngine(
        source_id="anson",
        journal=b_journal,
        transport=FileTransport(shared, "anson"),
        cursor_storage=SyncCursorStorage(b_cursor_path),
    )
    a_new = manual_ping_event("new", source="cornelius")
    a_journal.append(a_new)
    a_engine.publish_local_event(a_new)
    third = b_engine2.sync_once()
    assert third["imported"] == 1


def test_chain_b_skip_rollup_when_raw_exists_summary_unchanged(tmp_path) -> None:
    shared = tmp_path / "shared"
    b_journal = EventJournal(tmp_path / "b" / "event_journal.jsonl")

    old_day = (datetime.now(tz=timezone.utc).date() - timedelta(days=8)).isoformat()
    raw1 = DugongEvent(
        event_type="manual_ping",
        timestamp=f"{old_day}T10:00:00+00:00",
        event_id="b_raw_1",
        source="cornelius",
        payload={"message": "x"},
    )
    raw2 = DugongEvent(
        event_type="mode_change",
        timestamp=f"{old_day}T10:01:00+00:00",
        event_id="b_raw_2",
        source="cornelius",
        payload={"mode": "study"},
    )
    b_journal.append(raw1)
    b_journal.append(raw2)
    before = summarize_events(b_journal.load_all())

    rollup = DugongEvent(
        event_type="daily_rollup",
        timestamp=f"{old_day}T23:59:59+00:00",
        event_id=f"rollup-{old_day}",
        source="dugong_rollup",
        schema_version="v1.2",
        payload={
            "date": old_day,
            "focus_seconds": 0,
            "ticks": 0,
            "mode_changes": 1,
            "clicks": 0,
            "manual_pings": 1,
            "rolled_up_event_count": 2,
            "rolled_up_from_dates": [old_day],
            "rolled_up_source": "cornelius",
            "rollup_version": "v1",
            "compaction_version": "v1",
        },
    )

    a_journal = EventJournal(tmp_path / "a" / "event_journal.jsonl")
    a_engine = SyncEngine(source_id="cornelius", journal=a_journal, transport=FileTransport(shared, "cornelius"))
    b_engine = SyncEngine(source_id="anson", journal=b_journal, transport=FileTransport(shared, "anson"))

    a_journal.append(rollup)
    a_engine.publish_local_event(rollup)
    result = b_engine.sync_once()
    after = summarize_events(b_journal.load_all())

    assert result["imported"] == 0
    assert before["days"] == after["days"]
