from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime

from dugong_app.core.events import DugongEvent
from dugong_app.interaction.protocol import decode_event, encode_event
from dugong_app.interaction.transport_base import TransportBase
from dugong_app.persistence.event_journal import EventJournal
from dugong_app.persistence.sync_cursor_json import SyncCursorStorage


class SyncEngine:
    def __init__(
        self,
        source_id: str,
        journal: EventJournal,
        transport: TransportBase | None,
        cursor_storage: SyncCursorStorage | None = None,
        on_remote_events: Callable[[list[DugongEvent]], None] | None = None,
    ) -> None:
        self.source_id = source_id
        self.journal = journal
        self.transport = transport
        self.cursor_storage = cursor_storage
        self.on_remote_events = on_remote_events

        existing_events = self.journal.load_all()
        self._known_event_ids = {event.event_id for event in existing_events if event.event_id}
        self._published_event_ids: set[str] = set()
        self._raw_day_source_keys: set[tuple[str, str]] = set()
        for event in existing_events:
            if event.event_type != "daily_rollup":
                day = self._safe_day(event.timestamp)
                self._raw_day_source_keys.add((day, event.source))

        cursor_state = self.cursor_storage.load() if self.cursor_storage is not None else {}
        self._remote_cursors: dict[str, int] = dict(cursor_state.get("file_cursors", {}))
        self._last_seen_event_id_by_source: dict[str, str] = dict(cursor_state.get("last_seen_event_id_by_source", {}))
        self._last_seen_timestamp_by_source: dict[str, str] = dict(cursor_state.get("last_seen_timestamp_by_source", {}))

        self.last_status = "disabled" if self.transport is None else "idle"
        self._retry_count = 0
        self._next_retry_monotonic = 0.0
        self._paused = False

    def publish_local_event(self, event: DugongEvent) -> bool:
        if self.transport is None:
            return False
        if not event.event_id or event.event_id in self._published_event_ids:
            return False

        payload = encode_event(sender=self.source_id, receiver="*", event=event)
        self.transport.send(payload)
        self._published_event_ids.add(event.event_id)
        self._known_event_ids.add(event.event_id)
        self.last_status = "ok"
        self._retry_count = 0
        self._next_retry_monotonic = 0.0
        return True

    def sync_once(self, force: bool = False) -> dict:
        if self.transport is None:
            return {"status": "disabled", "imported": 0, "events": []}

        if self._paused and not force:
            self.last_status = "paused"
            return {"status": "paused", "imported": 0, "events": []}

        now = time.monotonic()
        if not force and self._next_retry_monotonic > now:
            remaining = int(max(1, round(self._next_retry_monotonic - now)))
            status = f"retrying({self._retry_count})"
            self.last_status = status
            return {"status": status, "imported": 0, "events": [], "retry_in_seconds": remaining}

        try:
            if hasattr(self.transport, "receive_incremental"):
                payloads, next_cursors = self.transport.receive_incremental(self._remote_cursors)
            else:
                payloads = self.transport.receive()
                next_cursors = dict(self._remote_cursors)

            imported: list[DugongEvent] = []
            for payload in payloads:
                event = decode_event(payload)
                if not event.event_id:
                    continue
                if event.event_id in self._known_event_ids:
                    continue
                if event.source == self.source_id:
                    self._known_event_ids.add(event.event_id)
                    continue
                if self._should_skip_rollup(event):
                    self._known_event_ids.add(event.event_id)
                    self._remember_seen(event)
                    continue

                appended = self.journal.append(event)
                self._known_event_ids.add(event.event_id)
                self._remember_seen(event)
                if appended:
                    imported.append(event)

            if imported and self.on_remote_events is not None:
                self.on_remote_events(imported)

            self._remote_cursors = next_cursors
            self._persist_cursor_state()
            self.last_status = "ok"
            self._paused = False
            self._retry_count = 0
            self._next_retry_monotonic = 0.0
            return {"status": "ok", "imported": len(imported), "events": imported}
        except Exception as exc:
            self._retry_count += 1
            self.last_status = self._classify_failure(exc)
            if self.last_status in {"auth_fail", "auth_missing"}:
                self._paused = True
                return {
                    "status": self.last_status,
                    "imported": 0,
                    "error": str(exc),
                    "events": [],
                    "paused": True,
                }

            backoff_seconds = min(60, 2 ** min(self._retry_count, 6))
            self._next_retry_monotonic = time.monotonic() + backoff_seconds
            return {
                "status": self.last_status,
                "imported": 0,
                "error": str(exc),
                "events": [],
                "retry_in_seconds": backoff_seconds,
                "retry_count": self._retry_count,
            }

    def _persist_cursor_state(self) -> None:
        if self.cursor_storage is None:
            return
        self.cursor_storage.save(
            {
                "file_cursors": self._remote_cursors,
                "last_seen_event_id_by_source": self._last_seen_event_id_by_source,
                "last_seen_timestamp_by_source": self._last_seen_timestamp_by_source,
            }
        )

    def _remember_seen(self, event: DugongEvent) -> None:
        if event.event_id:
            self._last_seen_event_id_by_source[event.source] = event.event_id
        if event.timestamp:
            self._last_seen_timestamp_by_source[event.source] = event.timestamp
        if event.event_type != "daily_rollup":
            day = self._safe_day(event.timestamp)
            self._raw_day_source_keys.add((day, event.source))

    def _should_skip_rollup(self, event: DugongEvent) -> bool:
        if event.event_type != "daily_rollup":
            return False
        payload = event.payload if isinstance(event.payload, dict) else {}
        rollup_day = str(payload.get("date", "")).strip()
        rolled_up_source = str(payload.get("rolled_up_source", "")).strip()
        if not rollup_day or not rolled_up_source:
            return False
        return (rollup_day, rolled_up_source) in self._raw_day_source_keys

    def _safe_day(self, ts: str) -> str:
        try:
            return datetime.fromisoformat(ts).date().isoformat()
        except ValueError:
            return ""

    def _classify_failure(self, exc: Exception) -> str:
        message = str(exc).lower()
        if "auth_missing" in message:
            return "auth_missing"
        if "status=401" in message or "status=403" in message or "unauthorized" in message or "forbidden" in message:
            return "auth_fail"
        if "status=429" in message or "rate limit" in message:
            return "rate_limited"
        if (
            "timed out" in message
            or "name or service not known" in message
            or "temporary failure in name resolution" in message
            or "connection refused" in message
            or "network is unreachable" in message
        ):
            return "offline"
        return f"retrying({self._retry_count})"
