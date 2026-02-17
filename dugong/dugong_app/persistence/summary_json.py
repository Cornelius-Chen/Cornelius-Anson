from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile


class SummaryStorage:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, summary: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(summary, ensure_ascii=True, indent=2)
        with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(self.path.parent)) as handle:
            handle.write(payload)
            tmp_path = Path(handle.name)
        tmp_path.replace(self.path)
