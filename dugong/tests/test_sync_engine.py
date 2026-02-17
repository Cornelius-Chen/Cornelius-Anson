from dugong_app.core.events import manual_ping_event
from dugong_app.interaction.transport_file import FileTransport
from dugong_app.persistence.event_journal import EventJournal
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
