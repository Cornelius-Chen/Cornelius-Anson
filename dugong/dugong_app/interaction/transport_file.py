from __future__ import annotations

import json
from pathlib import Path

from .transport_base import TransportBase


class FileTransport(TransportBase):
    def __init__(self, shared_dir: str | Path, source_id: str) -> None:
        self.shared_dir = Path(shared_dir)
        self.source_id = source_id
        self.source_file = self.shared_dir / f"{self.source_id}.jsonl"

    def send(self, payload: dict) -> None:
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=True)
        with self.source_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def receive(self) -> list[dict]:
        if not self.shared_dir.exists():
            return []

        payloads: list[dict] = []
        for file_path in sorted(self.shared_dir.glob("*.jsonl")):
            if file_path == self.source_file:
                continue
            for line in file_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    payloads.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return payloads
