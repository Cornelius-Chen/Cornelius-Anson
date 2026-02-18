from dugong_app.core.events import manual_ping_event
from dugong_app.interaction.transport_file import FileTransport
from dugong_app.persistence.event_journal import EventJournal
from dugong_app.persistence.sync_cursor_json import SyncCursorStorage
from dugong_app.services.sync_engine import SyncEngine


def test_file_transport_and_sync_engine_deduplicate(tmp_path) -> None:
    shared_dir = tmp_path / "shared"
    a_journal = EventJournal(tmp_path / "a" / "event_journal.jsonl")
    b_journal = EventJournal(tmp_path / "b" / "event_journal.jsonl")

    a_transport = FileTransport(shared_dir=shared_dir, source_id="cornelius")
    b_transport = FileTransport(shared_dir=shared_dir, source_id="anson")

    a_engine = SyncEngine(source_id="cornelius", journal=a_journal, transport=a_transport)
    b_engine = SyncEngine(source_id="anson", journal=b_journal, transport=b_transport)

    event = manual_ping_event("hello", source="cornelius")
    a_journal.append(event)
    a_engine.publish_local_event(event)

    first = b_engine.sync_once()
    second = b_engine.sync_once()

    assert first["status"] == "ok"
    assert first["imported"] == 1
    assert second["status"] == "ok"
    assert second["imported"] == 0

    loaded = b_journal.load_all()
    assert len([e for e in loaded if e.event_type == "manual_ping"]) == 1


def test_sync_engine_backoff_and_force(tmp_path) -> None:
    class FailingTransport:
        def __init__(self) -> None:
            self.receive_calls = 0

        def send(self, _payload: dict) -> None:
            return None

        def receive(self) -> list[dict]:
            self.receive_calls += 1
            raise RuntimeError("status=500")

    journal = EventJournal(tmp_path / "event_journal.jsonl")
    transport = FailingTransport()
    engine = SyncEngine(source_id="cornelius", journal=journal, transport=transport)

    first = engine.sync_once()
    second = engine.sync_once()
    forced = engine.sync_once(force=True)

    assert first["status"].startswith("retrying(")
    assert "retry_in_seconds" in first
    assert second["status"].startswith("retrying(")
    assert transport.receive_calls == 2
    assert forced["status"].startswith("retrying(")


def test_sync_engine_failure_status_classification(tmp_path) -> None:
    class AuthFailTransport:
        def send(self, _payload: dict) -> None:
            return None

        def receive(self) -> list[dict]:
            raise RuntimeError("github read failed: status=401")

    engine = SyncEngine(
        source_id="cornelius",
        journal=EventJournal(tmp_path / "event_journal.jsonl"),
        transport=AuthFailTransport(),
    )
    result = engine.sync_once()
    assert result["status"] == "auth_fail"
    paused = engine.sync_once()
    assert paused["status"] == "paused"


def test_sync_engine_cursor_persistence_across_restart(tmp_path) -> None:
    shared_dir = tmp_path / "shared"
    a_journal = EventJournal(tmp_path / "a" / "event_journal.jsonl")
    b_journal = EventJournal(tmp_path / "b" / "event_journal.jsonl")
    cursor_path = tmp_path / "b" / "sync_cursor.json"

    a_transport = FileTransport(shared_dir=shared_dir, source_id="cornelius")
    b_transport = FileTransport(shared_dir=shared_dir, source_id="anson")

    a_engine = SyncEngine(source_id="cornelius", journal=a_journal, transport=a_transport)
    b_engine = SyncEngine(
        source_id="anson",
        journal=b_journal,
        transport=b_transport,
        cursor_storage=SyncCursorStorage(cursor_path),
    )

    event1 = manual_ping_event("e1", source="cornelius")
    a_journal.append(event1)
    a_engine.publish_local_event(event1)
    r1 = b_engine.sync_once()
    assert r1["imported"] == 1

    # Recreate engine (simulates restart) and ensure old event is not re-imported.
    b_engine2 = SyncEngine(
        source_id="anson",
        journal=b_journal,
        transport=b_transport,
        cursor_storage=SyncCursorStorage(cursor_path),
    )
    r2 = b_engine2.sync_once()
    assert r2["imported"] == 0

    event2 = manual_ping_event("e2", source="cornelius")
    a_journal.append(event2)
    a_engine.publish_local_event(event2)
    r3 = b_engine2.sync_once()
    assert r3["imported"] == 1
