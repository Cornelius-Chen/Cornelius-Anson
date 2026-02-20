from __future__ import annotations

import json
from pathlib import Path

from .transport_base import TransportBase


class FileTransport(TransportBase):
    def __init__(self, shared_dir: str | Path, source_id: str) -> None:
        self.shared_dir = Path(shared_dir)
        self.source_id = source_id
        self.source_file = self.shared_dir / f"{self.source_id}.jsonl"
        self.presence_dir = self.shared_dir / "presence"
        self.presence_file = self.presence_dir / f"{self.source_id}.json"

    def send(self, payload: dict) -> None:
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=True)
        with self.source_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def receive(self) -> list[dict]:
        payloads, _next = self.receive_incremental({})
        return payloads

    def receive_incremental(self, cursors: dict[str, int] | None = None) -> tuple[list[dict], dict[str, int]]:
        if not self.shared_dir.exists():
            return [], {}

        current_cursors = dict(cursors or {})
        next_cursors: dict[str, int] = dict(current_cursors)
        payloads: list[dict] = []
        for file_path in sorted(self.shared_dir.glob("*.jsonl")):
            if file_path == self.source_file:
                continue
            file_key = file_path.name
            lines = file_path.read_text(encoding="utf-8").splitlines()
            offset = int(current_cursors.get(file_key, 0))
            if offset < 0 or offset > len(lines):
                offset = 0
            for line in lines[offset:]:
                if not line.strip():
                    continue
                try:
                    payloads.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            next_cursors[file_key] = len(lines)
        return payloads, next_cursors

    def update_presence(self, presence: dict) -> None:
        self.presence_dir.mkdir(parents=True, exist_ok=True)
        self.presence_file.write_text(json.dumps(presence, ensure_ascii=True), encoding="utf-8")

    def receive_presence(self) -> list[dict]:
        if not self.presence_dir.exists():
            return []
        payloads: list[dict] = []
        for file_path in sorted(self.presence_dir.glob("*.json")):
            if file_path == self.presence_file:
                continue
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                payloads.append(data)
        return payloads
