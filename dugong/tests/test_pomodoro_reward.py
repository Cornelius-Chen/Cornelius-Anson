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
    assert reward.exp >= 20

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


def test_reward_cofocus_milestone_is_idempotent() -> None:
    reward = RewardService(base_pearls=10, valid_ratio=0.8)
    reward.cofocus_seconds_total = 600
    g1 = reward.grant_for_cofocus("cornelius:cofocus:1", pearls=5)
    assert g1 is not None
    assert reward.pearls == 5
    g2 = reward.grant_for_cofocus("cornelius:cofocus:1", pearls=5)
    assert g2 is None
    assert reward.pearls == 5


def test_reward_snapshot_restore_carries_cofocus_fields() -> None:
    reward = RewardService(base_pearls=10, valid_ratio=0.8)
    reward.cofocus_seconds_total = 123
    reward.grant_for_cofocus("a:cofocus:1", pearls=3)
    snap = reward.snapshot()

    restored = RewardService(base_pearls=10, valid_ratio=0.8)
    restored.restore(snap)
    assert restored.cofocus_seconds_total == 123
    assert "a:cofocus:1" in restored.granted_cofocus_milestones
    assert restored.exp == reward.exp
    assert restored.level == reward.level


def test_reward_exp_levels_up_and_tracks_progress() -> None:
    reward = RewardService(base_pearls=10, valid_ratio=0.8)
    assert reward.level == 1
    assert reward.exp == 0
    assert reward.exp_in_level == 0
    # 3 valid focus completions should pass level 1 threshold (50 exp).
    for idx in range(3):
        grant = reward.grant_for_completion(
            {"phase": "focus", "session_id": f"lvl{idx}", "completed_s": 100, "duration_s": 100}
        )
        assert grant is not None
        assert grant.exp > 0
    assert reward.exp >= 60
    assert reward.level >= 2
    assert reward.exp_in_level < reward.exp_to_next_level()


def test_focus_progress_exp_starts_after_one_minute_and_increments_slowly() -> None:
    reward = RewardService(base_pearls=10, valid_ratio=0.8)
    session_id = "focus-progress-1"
    # First minute: no progress EXP.
    g0, l0 = reward.grant_focus_progress(session_id=session_id, completed_s=60)
    assert g0 == 0 and l0 == 0
    # At 120s completed: 1 EXP (one step after threshold).
    g1, _ = reward.grant_focus_progress(session_id=session_id, completed_s=120)
    assert g1 == 1
    # Re-check same time should be idempotent.
    g2, _ = reward.grant_focus_progress(session_id=session_id, completed_s=120)
    assert g2 == 0
    # Next minute step gives one more.
    g3, _ = reward.grant_focus_progress(session_id=session_id, completed_s=180)
    assert g3 == 1


def test_focus_progress_state_clears_on_completion_or_skip() -> None:
    reward = RewardService(base_pearls=10, valid_ratio=0.8)
    sid = "focus-progress-clear"
    reward.grant_focus_progress(session_id=sid, completed_s=240)
    assert sid in reward.focus_progress_awarded_steps
    reward.grant_for_completion({"phase": "focus", "session_id": sid, "completed_s": 100, "duration_s": 100})
    assert sid not in reward.focus_progress_awarded_steps

    sid2 = "focus-progress-skip"
    reward.grant_focus_progress(session_id=sid2, completed_s=240)
    assert sid2 in reward.focus_progress_awarded_steps
    reward.on_skip("focus", session_id=sid2)
    assert sid2 not in reward.focus_progress_awarded_steps


def test_reward_tiered_bonus_increases_after_streak_thresholds() -> None:
    reward = RewardService(base_pearls=10, valid_ratio=0.8)
    for idx in range(1, 8):
        g = reward.grant_for_completion(
            {"phase": "focus", "session_id": f"s{idx}", "completed_s": 100, "duration_s": 100}
        )
        assert g is not None
        if idx <= 3:
            assert g.pearls == 10
        elif idx <= 6:
            assert g.pearls == 15
        else:
            assert g.pearls == 20
    assert reward.lifetime_pearls >= reward.pearls
    assert reward.today_pearls >= reward.pearls


def test_shop_purchase_and_equip_flow() -> None:
    reward = RewardService(base_pearls=10, valid_ratio=0.8)
    reward.pearls = 200
    reward.lifetime_pearls = 200
    reward.today_pearls = 200

    ok, reason = reward.buy_shop_item("title", "explorer", 60)
    assert ok and reason == "purchased"
    assert reward.equipped_title_id == "explorer"
    assert reward.pearls == 140

    # Re-buy should become free equip path.
    ok2, reason2 = reward.buy_shop_item("title", "explorer", 60)
    assert ok2 and reason2 == "equipped"
    assert reward.pearls == 140
