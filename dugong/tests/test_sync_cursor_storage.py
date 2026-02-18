import json

from dugong_app.persistence.sync_cursor_json import SyncCursorStorage


def test_sync_cursor_storage_loads_legacy_flat_dict(tmp_path) -> None:
    path = tmp_path / "sync_cursor.json"
    path.write_text(json.dumps({"anson.jsonl": 12}), encoding="utf-8")
    storage = SyncCursorStorage(path)
    state = storage.load()
    assert state["file_cursors"]["anson.jsonl"] == 12
    assert state["last_seen_event_id_by_source"] == {}
    assert state["last_seen_timestamp_by_source"] == {}
