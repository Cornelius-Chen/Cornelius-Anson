import json
from argparse import Namespace

from dugong_app import debug
from dugong_app.persistence.runtime_health_json import RuntimeHealthStorage
from dugong_app.persistence.pomodoro_state_json import PomodoroStateStorage
from dugong_app.persistence.reward_state_json import RewardStateStorage
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


def test_debug_pomo_outputs_expected_keys(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("DUGONG_DATA_DIR", str(tmp_path))
    PomodoroStateStorage(tmp_path / "pomodoro_state.json").save(
        {
            "state": "PAUSED",
            "phase": "focus",
            "remaining_s": 321,
            "phase_duration_s": 1500,
            "session_id": "abc123",
            "ends_at_wall": 1700000000.0,
        }
    )
    RewardStateStorage(tmp_path / "reward_state.json").save(
        {
            "pearls": 42,
            "focus_streak": 2,
            "day_streak": 1,
            "cofocus_seconds_total": 600,
            "granted_sessions": ["abc123"],
            "granted_cofocus_milestones": ["cornelius:cofocus:1"],
        }
    )
    rc = debug._cmd_pomo(None)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["pomodoro"]["state"] == "PAUSED"
    assert payload["reward"]["pearls"] == 42
    assert payload["reward"]["cofocus_seconds_total"] == 600


def test_debug_pomo_watch_iterations(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("DUGONG_DATA_DIR", str(tmp_path))
    PomodoroStateStorage(tmp_path / "pomodoro_state.json").save({"state": "IDLE", "phase": "", "remaining_s": 0})
    RewardStateStorage(tmp_path / "reward_state.json").save({"pearls": 1, "granted_sessions": []})
    rc = debug._cmd_pomo(Namespace(watch=True, interval=0.001, iterations=2))
    out = capsys.readouterr().out.strip().splitlines()
    assert rc == 0
    assert len(out) == 2
    assert all("pomodoro" in json.loads(line) for line in out)
