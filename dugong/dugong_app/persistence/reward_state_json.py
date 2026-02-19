from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


class RewardStateStorage:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def save(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, ensure_ascii=True, indent=2)
        with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(self.path.parent)) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_path = Path(handle.name)
        os.replace(tmp_path, self.path)
