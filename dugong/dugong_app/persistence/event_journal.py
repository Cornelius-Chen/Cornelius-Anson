from __future__ import annotations

import json
import logging
import os
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dugong_app.core.events import DugongEvent

LOGGER = logging.getLogger(__name__)


class EventJournal:
    def __init__(self, path: str | Path, retention_days: int = 30, fsync_writes: bool | None = None) -> None:
        raw_path = Path(path)
        self.retention_days = max(1, int(retention_days))
        self.fsync_writes = self._resolve_fsync_flag(fsync_writes)
        self._lock = threading.Lock()
        self._known_event_ids: set[str] = set()
        self._last_read_bad_lines = 0

        # Backward compatible: if caller passes "event_journal.jsonl", keep loading it.
        if raw_path.suffix == ".jsonl":
            self.legacy_path = raw_path
            self.dir_path = raw_path.parent / "event_journal"
        else:
            self.legacy_path = None
            self.dir_path = raw_path

        self._known_event_ids = self._scan_known_event_ids()

    def append(self, event: DugongEvent) -> bool:
        with self._lock:
            if event.event_id and event.event_id in self._known_event_ids:
                LOGGER.debug("journal dedupe hit event_id=%s", event.event_id)
                return False

            self.dir_path.mkdir(parents=True, exist_ok=True)
            day_file = self.dir_path / f"{self._event_day(event)}.jsonl"
            line = json.dumps(event.to_dict(), ensure_ascii=True)

            with day_file.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
                if self.fsync_writes:
                    os.fsync(handle.fileno())

            if event.event_id:
                self._known_event_ids.add(event.event_id)
            self._prune_old_files()
            return True

    def load_all(self) -> list[DugongEvent]:
        self._last_read_bad_lines = 0
        seen_ids: set[str] = set()
        events: list[DugongEvent] = []
        if self.dir_path.exists():
            for file_path in sorted(self.dir_path.glob("*.jsonl")):
                events.extend(self._load_file(file_path, seen_ids))

        if self.legacy_path is not None and self.legacy_path.exists():
            events.extend(self._load_file(self.legacy_path, seen_ids))

        with self._lock:
            self._known_event_ids = seen_ids
        return events

    def last_read_stats(self) -> dict[str, int]:
        return {"bad_lines_skipped": self._last_read_bad_lines}

    def _scan_known_event_ids(self) -> set[str]:
        seen_ids: set[str] = set()
        if self.dir_path.exists():
            for file_path in sorted(self.dir_path.glob("*.jsonl")):
                self._load_file(file_path, seen_ids, include_events=False)
        if self.legacy_path is not None and self.legacy_path.exists():
            self._load_file(self.legacy_path, seen_ids, include_events=False)
        return seen_ids

    def _load_file(self, file_path: Path, seen_ids: set[str], include_events: bool = True) -> list[DugongEvent]:
        loaded: list[DugongEvent] = []
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                for line_no, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError as exc:
                        self._last_read_bad_lines += 1
                        LOGGER.warning("journal bad line file=%s line=%s error=%s", file_path.name, line_no, exc.msg)
                        continue

                    event_id = str(payload.get("event_id", "") or "")
                    if event_id and event_id in seen_ids:
                        LOGGER.debug(
                            "journal duplicate line ignored file=%s line=%s event_id=%s",
                            file_path.name,
                            line_no,
                            event_id,
                        )
                        continue
                    if event_id:
                        seen_ids.add(event_id)
                    if not include_events:
                        continue

                    loaded.append(
                        DugongEvent(
                            event_type=payload.get("event_type", "unknown"),
                            timestamp=payload.get("timestamp", ""),
                            event_id=event_id,
                            source=payload.get("source", "dugong_app"),
                            schema_version=payload.get("schema_version", "v1"),
                            payload=payload.get("payload", {}),
                        )
                    )
        except OSError as exc:
            LOGGER.warning("journal read failed file=%s error=%s", file_path, exc)
        return loaded

    def _resolve_fsync_flag(self, explicit_value: bool | None) -> bool:
        if explicit_value is not None:
            return bool(explicit_value)
        raw = os.getenv("DUGONG_JOURNAL_FSYNC", "0").strip().lower()
        return raw in {"1", "true", "yes", "on"}

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
