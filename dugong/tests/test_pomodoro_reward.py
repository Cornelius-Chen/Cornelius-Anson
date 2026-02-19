from __future__ import annotations

from dugong_app.services.pomodoro_service import POMO_IDLE, POMO_PAUSED, PomodoroService
from dugong_app.services.reward_service import RewardService


class _FakeClock:
    def __init__(self) -> None:
        self.mono = 1000.0
        self.wall = 1_700_000_000.0

    def advance(self, seconds: float) -> None:
        self.mono += float(seconds)
        self.wall += float(seconds)


def test_pomodoro_focus_break_and_manual_next() -> None:
    clock = _FakeClock()
    service = PomodoroService(
        focus_minutes=1,
        break_minutes=1,
        monotonic_now=lambda: clock.mono,
        wall_now=lambda: clock.wall,
    )

    start = service.start_focus()
    assert start is not None
    assert start["phase"] == "focus"
    assert service.view().state == "FOCUS"

    clock.advance(60)
    events = service.tick()
    assert [name for name, _ in events] == ["pomo_complete", "pomo_start"]
    assert service.view().state == "BREAK"

    clock.advance(60)
    events2 = service.tick()
    assert [name for name, _ in events2] == ["pomo_complete"]
    assert service.view().state == POMO_IDLE
    assert service.start_focus() is not None


def test_pomodoro_restore_always_paused() -> None:
    clock = _FakeClock()
    service = PomodoroService(
        focus_minutes=2,
        break_minutes=1,
        monotonic_now=lambda: clock.mono,
        wall_now=lambda: clock.wall,
    )
    service.start_focus()
    clock.advance(30)
    snap = service.snapshot()

    restored = PomodoroService(
        focus_minutes=2,
        break_minutes=1,
        monotonic_now=lambda: clock.mono,
        wall_now=lambda: clock.wall,
    )
    restored.restore(snap)
    view = restored.view()
    assert view.state == POMO_PAUSED
    assert view.phase == "focus"
    assert 0 < view.remaining_s <= 120


def test_reward_grant_is_idempotent_and_ratio_guarded() -> None:
    reward = RewardService(base_pearls=10, valid_ratio=0.8)

    g1 = reward.grant_for_completion(
        {"phase": "focus", "session_id": "s1", "completed_s": 80, "duration_s": 100}
    )
    assert g1 is not None
    assert reward.pearls >= 10

    g2 = reward.grant_for_completion(
        {"phase": "focus", "session_id": "s1", "completed_s": 100, "duration_s": 100}
    )
    assert g2 is None

    # Invalid completion should not grant.
    g3 = reward.grant_for_completion(
        {"phase": "focus", "session_id": "s2", "completed_s": 10, "duration_s": 100}
    )
    assert g3 is None


def test_manual_start_only_contract() -> None:
    clock = _FakeClock()
    service = PomodoroService(
        focus_minutes=1,
        break_minutes=1,
        monotonic_now=lambda: clock.mono,
        wall_now=lambda: clock.wall,
    )
    assert service.start_focus() is not None
    # Cannot start again while already running.
    assert service.start_focus() is None
    assert service.pause() is not None
    # Cannot start directly from paused; must resume or go idle first.
    assert service.start_focus() is None


def test_sleep_like_time_jump_is_monotonic_based() -> None:
    clock = _FakeClock()
    service = PomodoroService(
        focus_minutes=1,
        break_minutes=1,
        monotonic_now=lambda: clock.mono,
        wall_now=lambda: clock.wall,
    )
    service.start_focus()
    # Simulate machine sleep / app not ticking for 65s.
    clock.advance(65)
    events = service.tick()
    # True overtime should complete exactly once and enter break.
    assert [name for name, _ in events] == ["pomo_complete", "pomo_start"]
    assert service.view().state == "BREAK"


def test_reward_threshold_boundary_exact_ratio_grants() -> None:
    reward = RewardService(base_pearls=10, valid_ratio=0.8)
    grant = reward.grant_for_completion(
        {"phase": "focus", "session_id": "boundary", "completed_s": 80, "duration_s": 100}
    )
    assert grant is not None
