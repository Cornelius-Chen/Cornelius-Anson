from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dugong_app.core.events import DugongEvent


class EventJournal:
    def __init__(self, path: str | Path, retention_days: int = 30) -> None:
        raw_path = Path(path)
        self.retention_days = max(1, int(retention_days))

        # Backward compatible: if caller passes "event_journal.jsonl", keep loading it.
        if raw_path.suffix == ".jsonl":
            self.legacy_path = raw_path
            self.dir_path = raw_path.parent / "event_journal"
        else:
            self.legacy_path = None
            self.dir_path = raw_path

    def append(self, event: DugongEvent) -> None:
        self.dir_path.mkdir(parents=True, exist_ok=True)
        day_file = self.dir_path / f"{self._event_day(event)}.jsonl"
        line = json.dumps(event.to_dict(), ensure_ascii=True)
        with day_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        self._prune_old_files()

    def load_all(self) -> list[DugongEvent]:
        events: list[DugongEvent] = []
        if self.dir_path.exists():
            for file_path in sorted(self.dir_path.glob("*.jsonl")):
                events.extend(self._load_file(file_path))

        if self.legacy_path is not None and self.legacy_path.exists():
            events.extend(self._load_file(self.legacy_path))

        return events

    def _load_file(self, file_path: Path) -> list[DugongEvent]:
        loaded: list[DugongEvent] = []
        for line in file_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            loaded.append(
                DugongEvent(
                    event_type=payload.get("event_type", "unknown"),
                    timestamp=payload.get("timestamp", ""),
                    event_id=payload.get("event_id", ""),
                    source=payload.get("source", "dugong_app"),
                    schema_version=payload.get("schema_version", "v1"),
                    payload=payload.get("payload", {}),
                )
            )
        return loaded

    def _event_day(self, event: DugongEvent) -> str:
        try:
            return datetime.fromisoformat(event.timestamp).date().isoformat()
        except ValueError:
            return datetime.now(tz=timezone.utc).date().isoformat()

    def _prune_old_files(self) -> None:
        cutoff = datetime.now(tz=timezone.utc).date() - timedelta(days=self.retention_days - 1)
        for file_path in self.dir_path.glob("*.jsonl"):
            try:
                day = date.fromisoformat(file_path.stem)
            except ValueError:
                continue
            if day < cutoff:
                file_path.unlink(missing_ok=True)
