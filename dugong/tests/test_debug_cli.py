import json

from dugong_app import debug
from dugong_app.persistence.runtime_health_json import RuntimeHealthStorage
from dugong_app.persistence.sync_cursor_json import SyncCursorStorage


def test_debug_config_masks_token(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("DUGONG_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DUGONG_GITHUB_TOKEN", "secret-token")
    rc = debug._cmd_config(None)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["github_token"] == "***"


def test_debug_health_outputs_expected_keys(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("DUGONG_DATA_DIR", str(tmp_path))
    RuntimeHealthStorage(tmp_path / "sync_health.json").save({"sync_state": "ok", "unread_remote_count": 2})
    SyncCursorStorage(tmp_path / "sync_cursor.json").save(
        {
            "file_cursors": {"anson.jsonl": 5},
            "last_seen_event_id_by_source": {"anson": "evt1"},
            "last_seen_timestamp_by_source": {"anson": "2026-02-18T00:00:00+00:00"},
        }
    )
    rc = debug._cmd_health(None)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["sync_state"] == "ok"
    assert "cursor_last_seen_event_id_by_source" in payload
