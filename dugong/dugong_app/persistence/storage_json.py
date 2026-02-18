from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from dugong_app.core.state import DugongState


class JsonStorage:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> DugongState:
        if not self.path.exists():
            return DugongState()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return DugongState()
        return DugongState.from_dict(data)

    def save(self, state: DugongState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state.to_dict(), ensure_ascii=True, indent=2)
        with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(self.path.parent)) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_path = Path(handle.name)
        os.replace(tmp_path, self.path)
