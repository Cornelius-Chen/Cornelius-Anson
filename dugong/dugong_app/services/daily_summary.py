from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from dugong_app.core.events import DugongEvent


def _safe_date(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).date().isoformat()
    except ValueError:
        return datetime.now(tz=timezone.utc).date().isoformat()


def _current_streak(active_days: set[str]) -> int:
    if not active_days:
        return 0
    day = max(date.fromisoformat(d) for d in active_days)
    streak = 0
    while day.isoformat() in active_days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def summarize_events(events: list[DugongEvent]) -> dict:
    by_day: dict[str, dict] = defaultdict(
        lambda: {
            "focus_seconds": 0,
            "ticks": 0,
            "mode_changes": 0,
            "clicks": 0,
            "manual_pings": 0,
        }
    )

    for event in events:
        day = _safe_date(event.timestamp)
        bucket = by_day[day]

        if event.event_type == "state_tick":
            bucket["ticks"] += 1
            mode = event.payload.get("mode")
            tick_seconds = int(event.payload.get("tick_seconds", 60))
            if mode == "study":
                bucket["focus_seconds"] += max(0, tick_seconds)
        elif event.event_type == "mode_change":
            bucket["mode_changes"] += 1
        elif event.event_type == "click":
            bucket["clicks"] += 1
        elif event.event_type == "manual_ping":
            bucket["manual_pings"] += 1

    days: list[dict] = []
    for day_key in sorted(by_day.keys()):
        payload = by_day[day_key]
        days.append(
            {
                "date": day_key,
                "focus_seconds": payload["focus_seconds"],
                "ticks": payload["ticks"],
                "mode_changes": payload["mode_changes"],
                "clicks": payload["clicks"],
                "manual_pings": payload["manual_pings"],
            }
        )

    active_days = {item["date"] for item in days if item["focus_seconds"] > 0}
    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "days": days,
        "current_streak_days": _current_streak(active_days),
    }
