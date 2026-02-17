from __future__ import annotations

from collections.abc import Callable

from dugong_app.core.events import DugongEvent
from dugong_app.interaction.protocol import decode_event, encode_event
from dugong_app.interaction.transport_base import TransportBase
from dugong_app.persistence.event_journal import EventJournal


class SyncEngine:
    def __init__(
        self,
        source_id: str,
        journal: EventJournal,
        transport: TransportBase | None,
        on_remote_events: Callable[[list[DugongEvent]], None] | None = None,
    ) -> None:
        self.source_id = source_id
        self.journal = journal
        self.transport = transport
        self.on_remote_events = on_remote_events

        self._known_event_ids = {event.event_id for event in self.journal.load_all() if event.event_id}
        self._published_event_ids: set[str] = set()
        self.last_status = "disabled" if self.transport is None else "idle"

    def publish_local_event(self, event: DugongEvent) -> None:
        if self.transport is None:
            return
        if not event.event_id or event.event_id in self._published_event_ids:
            return

        payload = encode_event(sender=self.source_id, receiver="*", event=event)
        self.transport.send(payload)
        self._published_event_ids.add(event.event_id)
        self._known_event_ids.add(event.event_id)
        self.last_status = "ok"

    def sync_once(self) -> dict:
        if self.transport is None:
            return {"status": "disabled", "imported": 0}

        try:
            payloads = self.transport.receive()
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

                self.journal.append(event)
                self._known_event_ids.add(event.event_id)
                imported.append(event)

            if imported and self.on_remote_events is not None:
                self.on_remote_events(imported)

            self.last_status = "ok"
            return {"status": "ok", "imported": len(imported)}
        except Exception as exc:
            self.last_status = "fail"
            return {"status": "fail", "imported": 0, "error": str(exc)}
