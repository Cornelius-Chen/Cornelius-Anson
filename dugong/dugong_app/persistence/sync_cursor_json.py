from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


class SyncCursorStorage:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return {
                "file_cursors": {},
                "last_seen_event_id_by_source": {},
                "last_seen_timestamp_by_source": {},
            }
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "file_cursors": {},
                "last_seen_event_id_by_source": {},
                "last_seen_timestamp_by_source": {},
            }

        # Backward compatibility with old flat dict format: {"file.jsonl": 12, ...}
        if isinstance(payload, dict) and "file_cursors" not in payload and "last_seen_event_id_by_source" not in payload:
            return {
                "file_cursors": self._coerce_int_map(payload),
                "last_seen_event_id_by_source": {},
                "last_seen_timestamp_by_source": {},
            }
        if not isinstance(payload, dict):
            return {
                "file_cursors": {},
                "last_seen_event_id_by_source": {},
                "last_seen_timestamp_by_source": {},
            }

        return {
            "file_cursors": self._coerce_int_map(payload.get("file_cursors", {})),
            "last_seen_event_id_by_source": self._coerce_str_map(payload.get("last_seen_event_id_by_source", {})),
            "last_seen_timestamp_by_source": self._coerce_str_map(payload.get("last_seen_timestamp_by_source", {})),
        }

    def save(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "v2",
            "file_cursors": self._coerce_int_map(state.get("file_cursors", {})),
            "last_seen_event_id_by_source": self._coerce_str_map(state.get("last_seen_event_id_by_source", {})),
            "last_seen_timestamp_by_source": self._coerce_str_map(state.get("last_seen_timestamp_by_source", {})),
        }
        data = json.dumps(payload, ensure_ascii=True, indent=2)
        with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(self.path.parent)) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_path = Path(handle.name)
        os.replace(tmp_path, self.path)

    def _coerce_int_map(self, payload: dict) -> dict[str, int]:
        if not isinstance(payload, dict):
            return {}
        out: dict[str, int] = {}
        for key, value in payload.items():
            try:
                out[str(key)] = max(0, int(value))
            except (TypeError, ValueError):
                continue
        return out

    def _coerce_str_map(self, payload: dict) -> dict[str, str]:
        if not isinstance(payload, dict):
            return {}
        out: dict[str, str] = {}
        for key, value in payload.items():
            text = str(value or "").strip()
            if not text:
                continue
            out[str(key)] = text
        return out
