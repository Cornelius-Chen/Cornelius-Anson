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


def pomo_start_event(
    phase: str,
    duration_s: int,
    session_id: str,
    source: str = "dugong_app",
) -> DugongEvent:
    return DugongEvent(
        event_type="pomo_start",
        payload={"phase": phase, "duration_s": int(duration_s), "session_id": session_id},
        source=source,
    )


def pomo_pause_event(phase: str, session_id: str, remaining_s: int, source: str = "dugong_app") -> DugongEvent:
    return DugongEvent(
        event_type="pomo_pause",
        payload={"phase": phase, "session_id": session_id, "remaining_s": int(remaining_s)},
        source=source,
    )


def pomo_resume_event(phase: str, session_id: str, remaining_s: int, source: str = "dugong_app") -> DugongEvent:
    return DugongEvent(
        event_type="pomo_resume",
        payload={"phase": phase, "session_id": session_id, "remaining_s": int(remaining_s)},
        source=source,
    )


def pomo_skip_event(
    from_phase: str,
    session_id: str,
    completed_s: int,
    duration_s: int,
    source: str = "dugong_app",
) -> DugongEvent:
    return DugongEvent(
        event_type="pomo_skip",
        payload={
            "from_phase": from_phase,
            "session_id": session_id,
            "completed_s": int(completed_s),
            "duration_s": int(duration_s),
        },
        source=source,
    )


def pomo_complete_event(
    phase: str,
    session_id: str,
    completed_s: int,
    duration_s: int,
    source: str = "dugong_app",
) -> DugongEvent:
    return DugongEvent(
        event_type="pomo_complete",
        payload={
            "phase": phase,
            "session_id": session_id,
            "completed_s": int(completed_s),
            "duration_s": int(duration_s),
        },
        source=source,
    )


def reward_grant_event(
    pearls: int,
    streak_bonus: int,
    reason: str,
    session_id: str,
    focus_streak: int,
    day_streak: int,
    source: str = "dugong_app",
) -> DugongEvent:
    return DugongEvent(
        event_type="reward_grant",
        payload={
            "pearls": int(pearls),
            "streak_bonus": int(streak_bonus),
            "reason": reason,
            "session_id": session_id,
            "focus_streak": int(focus_streak),
            "day_streak": int(day_streak),
        },
        source=source,
    )


def co_focus_milestone_event(
    milestone_id: str,
    milestone_index: int,
    milestone_seconds: int,
    total_cofocus_seconds: int,
    source: str = "dugong_app",
) -> DugongEvent:
    return DugongEvent(
        event_type="co_focus_milestone",
        payload={
            "milestone_id": milestone_id,
            "milestone_index": int(milestone_index),
            "milestone_seconds": int(milestone_seconds),
            "total_cofocus_seconds": int(total_cofocus_seconds),
        },
        source=source,
    )


def profile_update_event(
    pearls: int,
    today_pearls: int,
    lifetime_pearls: int,
    focus_streak: int,
    day_streak: int,
    title_id: str,
    skin_id: str,
    bubble_style: str,
    source: str = "dugong_app",
) -> DugongEvent:
    return DugongEvent(
        event_type="profile_update",
        payload={
            "pearls": int(pearls),
            "today_pearls": int(today_pearls),
            "lifetime_pearls": int(lifetime_pearls),
            "focus_streak": int(focus_streak),
            "day_streak": int(day_streak),
            "title_id": str(title_id),
            "skin_id": str(skin_id),
            "bubble_style": str(bubble_style),
        },
        source=source,
    )
