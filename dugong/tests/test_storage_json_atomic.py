import json

from dugong_app.core.state import DugongState
from dugong_app.persistence.storage_json import JsonStorage


def test_storage_save_uses_atomic_replace_and_preserves_old_on_failure(tmp_path, monkeypatch) -> None:
    path = tmp_path / "dugong_state.json"
    path.write_text(json.dumps({"energy": 1, "mood": 2, "focus": 3, "mode": "chill", "tick_count": 0}), encoding="utf-8")
    storage = JsonStorage(path)

    def _boom(_src, _dst):
        raise OSError("replace failed")

    monkeypatch.setattr("dugong_app.persistence.storage_json.os.replace", _boom)

    try:
        storage.save(DugongState(energy=88, mood=77, focus=66, mode="study", tick_count=9))
    except OSError:
        pass

    restored = json.loads(path.read_text(encoding="utf-8"))
    assert restored["energy"] == 1
    assert restored["mood"] == 2
