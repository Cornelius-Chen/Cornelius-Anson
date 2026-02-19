from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class RewardGrant:
    pearls: int
    streak_bonus: int
    reason: str
    session_id: str
    focus_streak: int
    day_streak: int


class RewardService:
    def __init__(self, base_pearls: int = 10, valid_ratio: float = 0.8, max_granted_sessions: int = 2000) -> None:
        self.base_pearls = max(1, int(base_pearls))
        self.valid_ratio = min(1.0, max(0.1, float(valid_ratio)))
        self.max_granted_sessions = max(100, int(max_granted_sessions))

        self.pearls = 0
        self.focus_streak = 0
        self.day_streak = 0
        self.last_focus_day = ""
        self.granted_sessions: list[str] = []
        self.granted_cofocus_milestones: list[str] = []
        self.cofocus_seconds_total = 0

    def snapshot(self) -> dict:
        return {
            "pearls": int(self.pearls),
            "focus_streak": int(self.focus_streak),
            "day_streak": int(self.day_streak),
            "last_focus_day": self.last_focus_day,
            "granted_sessions": list(self.granted_sessions),
            "granted_cofocus_milestones": list(self.granted_cofocus_milestones),
            "cofocus_seconds_total": int(self.cofocus_seconds_total),
            "base_pearls": int(self.base_pearls),
            "valid_ratio": float(self.valid_ratio),
        }

    def restore(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        self.pearls = max(0, int(payload.get("pearls", self.pearls)))
        self.focus_streak = max(0, int(payload.get("focus_streak", self.focus_streak)))
        self.day_streak = max(0, int(payload.get("day_streak", self.day_streak)))
        self.last_focus_day = str(payload.get("last_focus_day", self.last_focus_day))
        sessions = payload.get("granted_sessions", [])
        if isinstance(sessions, list):
            self.granted_sessions = [str(s) for s in sessions if str(s).strip()]
        self.granted_sessions = self.granted_sessions[-self.max_granted_sessions :]
        milestones = payload.get("granted_cofocus_milestones", [])
        if isinstance(milestones, list):
            self.granted_cofocus_milestones = [str(s) for s in milestones if str(s).strip()]
        self.granted_cofocus_milestones = self.granted_cofocus_milestones[-self.max_granted_sessions :]
        self.cofocus_seconds_total = max(0, int(payload.get("cofocus_seconds_total", self.cofocus_seconds_total)))
        self.base_pearls = max(1, int(payload.get("base_pearls", self.base_pearls)))
        self.valid_ratio = min(1.0, max(0.1, float(payload.get("valid_ratio", self.valid_ratio))))

    def _mark_day_streak(self, today: str) -> None:
        if not self.last_focus_day:
            self.day_streak = 1
            self.last_focus_day = today
            return
        if self.last_focus_day == today:
            return
        try:
            prev_day = datetime.fromisoformat(self.last_focus_day).date()
            cur_day = datetime.fromisoformat(today).date()
            if cur_day == (prev_day + timedelta(days=1)):
                self.day_streak += 1
            else:
                self.day_streak = 1
            self.last_focus_day = today
        except ValueError:
            self.day_streak = 1
            self.last_focus_day = today

    def on_skip(self, from_phase: str) -> None:
        if from_phase == "focus":
            self.focus_streak = 0

    def grant_for_completion(self, payload: dict) -> RewardGrant | None:
        phase = str(payload.get("phase", "")).lower()
        if phase != "focus":
            return None

        session_id = str(payload.get("session_id", "")).strip()
        if not session_id:
            return None
        if session_id in self.granted_sessions:
            return None

        duration_s = max(1, int(payload.get("duration_s", 0)))
        completed_s = max(0, int(payload.get("completed_s", 0)))
        if completed_s < int(duration_s * self.valid_ratio):
            self.focus_streak = 0
            return None

        self.focus_streak += 1
        streak_bonus = min(20, max(0, self.focus_streak - 1) * 2)
        pearls = self.base_pearls + streak_bonus
        self.pearls += pearls

        today = datetime.now(tz=timezone.utc).date().isoformat()
        self._mark_day_streak(today)

        self.granted_sessions.append(session_id)
        if len(self.granted_sessions) > self.max_granted_sessions:
            self.granted_sessions = self.granted_sessions[-self.max_granted_sessions :]

        return RewardGrant(
            pearls=pearls,
            streak_bonus=streak_bonus,
            reason="pomo_complete",
            session_id=session_id,
            focus_streak=self.focus_streak,
            day_streak=self.day_streak,
        )

    def grant_for_cofocus(self, milestone_id: str, pearls: int = 5) -> RewardGrant | None:
        mid = str(milestone_id).strip()
        if not mid:
            return None
        if mid in self.granted_cofocus_milestones:
            return None
        gain = max(1, int(pearls))
        self.pearls += gain
        self.granted_cofocus_milestones.append(mid)
        if len(self.granted_cofocus_milestones) > self.max_granted_sessions:
            self.granted_cofocus_milestones = self.granted_cofocus_milestones[-self.max_granted_sessions :]
        return RewardGrant(
            pearls=gain,
            streak_bonus=0,
            reason="co_focus_milestone",
            session_id=mid,
            focus_streak=self.focus_streak,
            day_streak=self.day_streak,
        )
