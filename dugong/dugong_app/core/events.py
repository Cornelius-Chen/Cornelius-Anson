from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass(frozen=True)
class DugongEvent:
    event_type: str
    timestamp: str = field(default_factory=utc_now_iso)
    event_id: str = field(default_factory=lambda: uuid4().hex)
    source: str = "dugong_app"
    schema_version: str = "v1.1"
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def state_tick_event(state_dict: dict[str, Any], tick_seconds: int = 60, source: str = "dugong_app") -> DugongEvent:
    payload = dict(state_dict)
    payload["tick_seconds"] = int(tick_seconds)
    return DugongEvent(event_type="state_tick", payload=payload, source=source)


def mode_change_event(mode: str, source: str = "dugong_app") -> DugongEvent:
    return DugongEvent(event_type="mode_change", payload={"mode": mode}, source=source)


def click_event(source: str = "dugong_app") -> DugongEvent:
    return DugongEvent(event_type="click", payload={}, source=source)


def manual_ping_event(message: str = "manual_ping", source: str = "dugong_app") -> DugongEvent:
    return DugongEvent(event_type="manual_ping", payload={"message": message}, source=source)
