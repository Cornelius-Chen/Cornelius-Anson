from __future__ import annotations

from datetime import datetime, timezone

from dugong_app.core.events import DugongEvent


def _safe_dt(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.now(tz=timezone.utc)


def build_focus_sessions(events: list[DugongEvent]) -> list[dict]:
    sorted_events = sorted(events, key=lambda e: _safe_dt(e.timestamp))
    sessions: list[dict] = []

    active_start: datetime | None = None
    active_start_id: str | None = None

    for event in sorted_events:
        if event.event_type == "mode_change":
            mode = event.payload.get("mode")
            ts = _safe_dt(event.timestamp)
            if mode == "study" and active_start is None:
                active_start = ts
                active_start_id = event.event_id
            elif mode != "study" and active_start is not None:
                duration = int(max(0.0, (ts - active_start).total_seconds()))
                sessions.append(
                    {
                        "start_at": active_start.isoformat(),
                        "end_at": ts.isoformat(),
                        "duration_seconds": duration,
                        "start_event_id": active_start_id,
                        "end_event_id": event.event_id,
                        "ended_by": "mode_change",
                    }
                )
                active_start = None
                active_start_id = None

    if active_start is not None:
        now = datetime.now(tz=timezone.utc)
        duration = int(max(0.0, (now - active_start).total_seconds()))
        sessions.append(
            {
                "start_at": active_start.isoformat(),
                "end_at": None,
                "duration_seconds": duration,
                "start_event_id": active_start_id,
                "end_event_id": None,
                "ended_by": "open",
            }
        )

    return sessions
