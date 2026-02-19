from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4


POMO_IDLE = "IDLE"
POMO_FOCUS = "FOCUS"
POMO_BREAK = "BREAK"
POMO_PAUSED = "PAUSED"


@dataclass
class PomodoroView:
    state: str
    phase: str
    remaining_s: int
    session_id: str
    focus_minutes: int
    break_minutes: int


class PomodoroService:
    def __init__(
        self,
        focus_minutes: int = 25,
        break_minutes: int = 5,
        monotonic_now: Callable[[], float] | None = None,
        wall_now: Callable[[], float] | None = None,
    ) -> None:
        self.focus_minutes = max(1, int(focus_minutes))
        self.break_minutes = max(1, int(break_minutes))
        self._mono_now = monotonic_now or time.monotonic
        self._wall_now = wall_now or time.time

        self.state = POMO_IDLE
        self.phase = ""
        self.session_id = ""
        self.phase_duration_s = 0
        self._ends_at_mono = 0.0
        self._ends_at_wall = 0.0
        self._paused_remaining_s = 0

    def _new_session_id(self) -> str:
        return uuid4().hex

    def _remaining(self) -> int:
        if self.state in {POMO_FOCUS, POMO_BREAK}:
            return max(0, int(round(self._ends_at_mono - self._mono_now())))
        if self.state == POMO_PAUSED:
            return max(0, int(self._paused_remaining_s))
        return 0

    def view(self) -> PomodoroView:
        return PomodoroView(
            state=self.state,
            phase=self.phase,
            remaining_s=self._remaining(),
            session_id=self.session_id,
            focus_minutes=self.focus_minutes,
            break_minutes=self.break_minutes,
        )

    def snapshot(self) -> dict:
        return {
            "state": self.state,
            "phase": self.phase,
            "session_id": self.session_id,
            "phase_duration_s": int(self.phase_duration_s),
            "remaining_s": int(self._remaining()),
            "ends_at_wall": float(self._ends_at_wall),
            "focus_minutes": int(self.focus_minutes),
            "break_minutes": int(self.break_minutes),
        }

    def restore(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        self.focus_minutes = max(1, int(payload.get("focus_minutes", self.focus_minutes)))
        self.break_minutes = max(1, int(payload.get("break_minutes", self.break_minutes)))

        loaded_state = str(payload.get("state", POMO_IDLE)).upper()
        loaded_phase = str(payload.get("phase", "")).lower()
        if loaded_phase not in {"focus", "break"}:
            loaded_phase = ""

        if loaded_state in {POMO_FOCUS, POMO_BREAK, POMO_PAUSED} and loaded_phase:
            remaining = int(payload.get("remaining_s", 0))
            if remaining <= 0:
                ends_at_wall = float(payload.get("ends_at_wall", 0.0))
                if ends_at_wall > 0:
                    remaining = max(0, int(round(ends_at_wall - self._wall_now())))
            self.state = POMO_PAUSED
            self.phase = loaded_phase
            self.session_id = str(payload.get("session_id", "")).strip() or self._new_session_id()
            self.phase_duration_s = max(1, int(payload.get("phase_duration_s", remaining or 1)))
            self._paused_remaining_s = max(0, int(remaining))
            self._ends_at_mono = 0.0
            self._ends_at_wall = 0.0
            return

        self.state = POMO_IDLE
        self.phase = ""
        self.session_id = ""
        self.phase_duration_s = 0
        self._paused_remaining_s = 0
        self._ends_at_mono = 0.0
        self._ends_at_wall = 0.0

    def _start_phase(self, phase: str, duration_s: int) -> dict:
        now_mono = self._mono_now()
        now_wall = self._wall_now()
        self.phase = phase
        self.state = POMO_FOCUS if phase == "focus" else POMO_BREAK
        self.session_id = self._new_session_id()
        self.phase_duration_s = max(1, int(duration_s))
        self._paused_remaining_s = 0
        self._ends_at_mono = now_mono + self.phase_duration_s
        self._ends_at_wall = now_wall + self.phase_duration_s
        return {
            "phase": self.phase,
            "duration_s": self.phase_duration_s,
            "session_id": self.session_id,
        }

    def start_focus(self) -> dict | None:
        # Manual start only.
        if self.state != POMO_IDLE:
            return None
        return self._start_phase("focus", self.focus_minutes * 60)

    def pause(self) -> dict | None:
        if self.state not in {POMO_FOCUS, POMO_BREAK}:
            return None
        self._paused_remaining_s = self._remaining()
        self._ends_at_mono = 0.0
        self._ends_at_wall = 0.0
        self.state = POMO_PAUSED
        return {
            "phase": self.phase,
            "session_id": self.session_id,
            "remaining_s": int(self._paused_remaining_s),
        }

    def resume(self) -> dict | None:
        if self.state != POMO_PAUSED or self.phase not in {"focus", "break"}:
            return None
        remaining = max(1, int(self._paused_remaining_s))
        now_mono = self._mono_now()
        now_wall = self._wall_now()
        self.state = POMO_FOCUS if self.phase == "focus" else POMO_BREAK
        self._ends_at_mono = now_mono + remaining
        self._ends_at_wall = now_wall + remaining
        self._paused_remaining_s = 0
        return {
            "phase": self.phase,
            "session_id": self.session_id,
            "remaining_s": remaining,
        }

    def _phase_complete_payload(self, completed_s: int) -> dict:
        return {
            "phase": self.phase,
            "session_id": self.session_id,
            "completed_s": int(max(0, completed_s)),
            "duration_s": int(max(1, self.phase_duration_s)),
        }

    def tick(self) -> list[tuple[str, dict]]:
        events: list[tuple[str, dict]] = []
        if self.state not in {POMO_FOCUS, POMO_BREAK}:
            return events
        remaining = self._remaining()
        if remaining > 0:
            return events

        completed = self._phase_complete_payload(completed_s=self.phase_duration_s)
        events.append(("pomo_complete", completed))

        if self.phase == "focus":
            start_break = self._start_phase("break", self.break_minutes * 60)
            events.append(("pomo_start", start_break))
            return events

        # Break end: require manual start for the next focus.
        self.state = POMO_IDLE
        self.phase = ""
        self.session_id = ""
        self.phase_duration_s = 0
        self._paused_remaining_s = 0
        self._ends_at_mono = 0.0
        self._ends_at_wall = 0.0
        return events

    def skip(self) -> list[tuple[str, dict]]:
        events: list[tuple[str, dict]] = []
        if self.state not in {POMO_FOCUS, POMO_BREAK, POMO_PAUSED}:
            return events

        from_phase = self.phase
        if from_phase not in {"focus", "break"}:
            return events

        remaining = self._remaining()
        completed_s = max(0, self.phase_duration_s - remaining)
        events.append(
            (
                "pomo_skip",
                {
                    "from_phase": from_phase,
                    "session_id": self.session_id,
                    "completed_s": int(completed_s),
                    "duration_s": int(max(1, self.phase_duration_s)),
                },
            )
        )

        if from_phase == "focus":
            start_break = self._start_phase("break", self.break_minutes * 60)
            events.append(("pomo_start", start_break))
            return events

        self.state = POMO_IDLE
        self.phase = ""
        self.session_id = ""
        self.phase_duration_s = 0
        self._paused_remaining_s = 0
        self._ends_at_mono = 0.0
        self._ends_at_wall = 0.0
        return events
