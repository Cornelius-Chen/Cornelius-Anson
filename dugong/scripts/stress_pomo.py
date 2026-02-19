from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dugong_app.core.events import (
    DugongEvent,
    pomo_complete_event,
    pomo_pause_event,
    pomo_resume_event,
    pomo_skip_event,
    pomo_start_event,
    reward_grant_event,
)
from dugong_app.persistence.event_journal import EventJournal
from dugong_app.persistence.pomodoro_state_json import PomodoroStateStorage
from dugong_app.persistence.reward_state_json import RewardStateStorage
from dugong_app.services.pomodoro_service import POMO_BREAK, POMO_FOCUS, POMO_IDLE, POMO_PAUSED, PomodoroService
from dugong_app.services.reward_service import RewardGrant, RewardService


class SimClock:
    def __init__(self, mono_start: float = 1000.0, wall_start: float = 1_700_000_000.0) -> None:
        self.mono = mono_start
        self.wall = wall_start

    def monotonic(self) -> float:
        return self.mono

    def wall_time(self) -> float:
        return self.wall

    def advance(self, seconds: float) -> None:
        self.mono += float(seconds)
        self.wall += float(seconds)


@dataclass
class Metrics:
    pomo_started_total: int = 0
    pomo_completed_total: int = 0
    pomo_effective_completed: int = 0
    pomo_skipped_total: int = 0
    pause_total: int = 0
    resume_total: int = 0
    action_start_attempts: int = 0
    action_skip_attempts: int = 0
    action_pause_resume_attempts: int = 0
    reward_dedupe_hits: int = 0
    reward_duplicate_grant_violations: int = 0
    journal_dedupe_hits: int = 0
    state_machine_invariant_violations: int = 0
    auto_start_violations: int = 0
    recovery_attempted: int = 0
    recovery_passed: int = 0
    recovery_failed: int = 0
    pearls_delta_expected: int = 0
    pearls_delta_actual: int = 0
    illegal_transition_samples: list[str] = field(default_factory=list)


@dataclass
class ExpectedRewardModel:
    base_pearls: int
    valid_ratio: float
    seen_sessions: set[str] = field(default_factory=set)
    focus_streak: int = 0
    pearls: int = 0
    dedupe_hits: int = 0

    def on_focus_complete(self, payload: dict) -> tuple[bool, int]:
        session_id = str(payload.get("session_id", "")).strip()
        duration_s = max(1, int(payload.get("duration_s", 0)))
        completed_s = max(0, int(payload.get("completed_s", 0)))
        effective = completed_s >= int(duration_s * self.valid_ratio)

        if not session_id:
            return False, 0
        if session_id in self.seen_sessions:
            self.dedupe_hits += 1
            return effective, 0

        if not effective:
            self.focus_streak = 0
            return False, 0

        self.seen_sessions.add(session_id)
        self.focus_streak += 1
        streak_bonus = min(20, max(0, self.focus_streak - 1) * 2)
        pearls = self.base_pearls + streak_bonus
        self.pearls += pearls
        return True, pearls

    def on_focus_skip(self) -> None:
        self.focus_streak = 0


def _progress_line(step: int, total_steps: int, metrics: Metrics, state: str) -> str:
    width = 30
    ratio = 0.0 if total_steps <= 0 else min(1.0, step / total_steps)
    fill = int(width * ratio)
    bar = "#" * fill + "-" * (width - fill)
    return (
        f"\r[{bar}] {ratio*100:6.2f}% step={step:5d}/{total_steps:<5d} "
        f"state={state:<6s} comp={metrics.pomo_completed_total:<4d} "
        f"dedupe={metrics.reward_dedupe_hits + metrics.journal_dedupe_hits:<4d}"
    )


def _safe_append(journal: EventJournal, event: DugongEvent, metrics: Metrics) -> None:
    appended = journal.append(event)
    if not appended:
        metrics.journal_dedupe_hits += 1


def _make_event(name: str, payload: dict, source: str) -> DugongEvent:
    if name == "pomo_start":
        return pomo_start_event(
            phase=str(payload.get("phase", "")),
            duration_s=int(payload.get("duration_s", 0)),
            session_id=str(payload.get("session_id", "")),
            source=source,
        )
    if name == "pomo_pause":
        return pomo_pause_event(
            phase=str(payload.get("phase", "")),
            session_id=str(payload.get("session_id", "")),
            remaining_s=int(payload.get("remaining_s", 0)),
            source=source,
        )
    if name == "pomo_resume":
        return pomo_resume_event(
            phase=str(payload.get("phase", "")),
            session_id=str(payload.get("session_id", "")),
            remaining_s=int(payload.get("remaining_s", 0)),
            source=source,
        )
    if name == "pomo_skip":
        return pomo_skip_event(
            from_phase=str(payload.get("from_phase", "")),
            session_id=str(payload.get("session_id", "")),
            completed_s=int(payload.get("completed_s", 0)),
            duration_s=int(payload.get("duration_s", 0)),
            source=source,
        )
    if name == "pomo_complete":
        return pomo_complete_event(
            phase=str(payload.get("phase", "")),
            session_id=str(payload.get("session_id", "")),
            completed_s=int(payload.get("completed_s", 0)),
            duration_s=int(payload.get("duration_s", 0)),
            source=source,
        )
    raise ValueError(f"unsupported event name: {name}")


def run_stress_pomo(args: argparse.Namespace) -> int:
    random.seed(args.seed)

    workdir = Path(args.workdir).resolve()
    if args.clean and workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "logs").mkdir(parents=True, exist_ok=True)

    if args.mode == "fast":
        focus_s = int(args.focus_seconds or 18)
        break_s = int(args.break_seconds or 6)
        runtime_s = int((args.minutes or 3.0) * 60)
    else:
        focus_s = int(args.focus_seconds or 25 * 60)
        break_s = int(args.break_seconds or 5 * 60)
        runtime_s = int((args.hours or 1.0) * 3600)
    step_s = max(1, int(args.step_seconds))
    total_steps = max(1, runtime_s // step_s)

    clock = SimClock()
    pomodoro = PomodoroService(
        focus_minutes=max(1, focus_s // 60),
        break_minutes=max(1, break_s // 60),
        monotonic_now=clock.monotonic,
        wall_now=clock.wall_time,
    )
    # override with precise seconds for stress testing
    pomodoro.focus_minutes = max(1, focus_s // 60)
    pomodoro.break_minutes = max(1, break_s // 60)

    reward = RewardService(base_pearls=int(args.base_pearls), valid_ratio=float(args.valid_ratio))
    expected = ExpectedRewardModel(base_pearls=int(args.base_pearls), valid_ratio=float(args.valid_ratio))
    metrics = Metrics()

    pomodoro_storage = PomodoroStateStorage(workdir / "pomodoro_state.json")
    reward_storage = RewardStateStorage(workdir / "reward_state.json")
    journal = EventJournal(workdir / "event_journal.jsonl", retention_days=30, fsync_writes=False)

    # Custom per-phase seconds while keeping existing service contract.
    def start_focus_seconds() -> dict | None:
        payload = pomodoro.start_focus()
        if payload:
            pomodoro.phase_duration_s = focus_s
            pomodoro._ends_at_mono = clock.monotonic() + focus_s  # noqa: SLF001
            pomodoro._ends_at_wall = clock.wall_time() + focus_s  # noqa: SLF001
            payload["duration_s"] = focus_s
        return payload

    def start_break_seconds() -> None:
        pomodoro.phase_duration_s = break_s
        pomodoro._ends_at_mono = clock.monotonic() + break_s  # noqa: SLF001
        pomodoro._ends_at_wall = clock.wall_time() + break_s  # noqa: SLF001

    last_state = pomodoro.view().state
    source = "stress_pomo"
    t0 = time.monotonic()

    for step in range(1, total_steps + 1):
        action_cause = ""

        # Random action driver
        view = pomodoro.view()
        if view.state == POMO_IDLE:
            metrics.action_start_attempts += 1
            if random.random() < 0.45:
                payload = start_focus_seconds()
                if payload is not None:
                    action_cause = "manual_start_focus"
                    metrics.pomo_started_total += 1
                    ev = _make_event("pomo_start", payload, source=source)
                    _safe_append(journal, ev, metrics)
        elif view.state in {POMO_FOCUS, POMO_BREAK}:
            r = random.random()
            if r < args.pause_rate:
                metrics.action_pause_resume_attempts += 1
                payload = pomodoro.pause()
                if payload is not None:
                    action_cause = "manual_pause"
                    metrics.pause_total += 1
                    ev = _make_event("pomo_pause", payload, source=source)
                    _safe_append(journal, ev, metrics)
            elif r < (args.pause_rate + args.skip_rate):
                metrics.action_skip_attempts += 1
                events = pomodoro.skip()
                if events:
                    action_cause = "manual_skip"
                    for name, payload in events:
                        ev = _make_event(name, payload, source=source)
                        _safe_append(journal, ev, metrics)
                        if name == "pomo_skip":
                            metrics.pomo_skipped_total += 1
                            if str(payload.get("from_phase", "")) == "focus":
                                expected.on_focus_skip()
                                reward.on_skip("focus")
                        if name == "pomo_start" and str(payload.get("phase", "")) == "break":
                            start_break_seconds()
            else:
                # Sleep/clock jump fault injection.
                if random.random() < args.time_jump_rate:
                    clock.advance(float(args.time_jump_seconds))

        elif view.state == POMO_PAUSED:
            metrics.action_pause_resume_attempts += 1
            if random.random() < args.resume_rate:
                payload = pomodoro.resume()
                if payload is not None:
                    action_cause = "manual_resume"
                    metrics.resume_total += 1
                    ev = _make_event("pomo_resume", payload, source=source)
                    _safe_append(journal, ev, metrics)

        # Tick-driven transitions.
        tick_events = pomodoro.tick()
        for name, payload in tick_events:
            if name == "pomo_start" and str(payload.get("phase", "")) == "break":
                start_break_seconds()
                payload["duration_s"] = break_s
            ev = _make_event(name, payload, source=source)
            _safe_append(journal, ev, metrics)

            if name == "pomo_complete":
                metrics.pomo_completed_total += 1
                phase = str(payload.get("phase", ""))
                if phase == "focus":
                    effective, _ = expected.on_focus_complete(payload)
                    if effective:
                        metrics.pomo_effective_completed += 1
                    grant = reward.grant_for_completion(payload)
                    if grant is not None:
                        grant_event = reward_grant_event(
                            pearls=grant.pearls,
                            streak_bonus=grant.streak_bonus,
                            reason=grant.reason,
                            session_id=grant.session_id,
                            focus_streak=grant.focus_streak,
                            day_streak=grant.day_streak,
                            source=source,
                        )
                        _safe_append(journal, grant_event, metrics)

                    # Replay duplicates (sync jitter / re-delivery)
                    if random.random() < args.net_jitter:
                        replay_times = random.randint(1, 3)
                        for _ in range(replay_times):
                            replay_grant = reward.grant_for_completion(payload)
                            if replay_grant is None:
                                metrics.reward_dedupe_hits += 1
                            else:
                                metrics.reward_duplicate_grant_violations += 1
                            _safe_append(journal, ev, metrics)

        # Restart simulation: persist -> recreate -> restore.
        if random.random() < args.restart_rate:
            metrics.recovery_attempted += 1
            pomodoro_storage.save(pomodoro.snapshot())
            reward_storage.save(reward.snapshot())

            restored_pomo = PomodoroService(
                focus_minutes=max(1, focus_s // 60),
                break_minutes=max(1, break_s // 60),
                monotonic_now=clock.monotonic,
                wall_now=clock.wall_time,
            )
            restored_pomo.restore(pomodoro_storage.load())
            restored_reward = RewardService(base_pearls=int(args.base_pearls), valid_ratio=float(args.valid_ratio))
            restored_reward.restore(reward_storage.load())

            rv = restored_pomo.view()
            if rv.state not in {POMO_PAUSED, POMO_IDLE}:
                metrics.recovery_failed += 1
                metrics.state_machine_invariant_violations += 1
                metrics.illegal_transition_samples.append(f"restore_state={rv.state}")
            else:
                metrics.recovery_passed += 1

            before = restored_pomo.view().state
            restored_pomo.tick()
            after = restored_pomo.view().state
            if before == POMO_IDLE and after == POMO_FOCUS:
                metrics.auto_start_violations += 1
                metrics.state_machine_invariant_violations += 1
                metrics.illegal_transition_samples.append("auto_start_after_restart")

            pomodoro = restored_pomo
            reward = restored_reward

        # Invariant checks.
        now_state = pomodoro.view().state
        if now_state == POMO_FOCUS and action_cause not in {"manual_start_focus", "manual_resume"}:
            if last_state in {POMO_IDLE, POMO_BREAK}:
                metrics.auto_start_violations += 1
                metrics.state_machine_invariant_violations += 1
                metrics.illegal_transition_samples.append(f"{last_state}->FOCUS without manual action")
        if last_state == POMO_BREAK and now_state == POMO_FOCUS:
            metrics.state_machine_invariant_violations += 1
            metrics.illegal_transition_samples.append("BREAK->FOCUS illegal auto transition")
        last_state = now_state

        clock.advance(step_s)
        if args.sleep_per_step > 0:
            print(_progress_line(step, total_steps, metrics, now_state), end="", flush=True)
            time.sleep(args.sleep_per_step)

    if args.sleep_per_step > 0:
        print()

    # Persist final snapshots for debug inspect.
    pomodoro_storage.save(pomodoro.snapshot())
    reward_storage.save(reward.snapshot())

    metrics.pearls_delta_expected = expected.pearls
    metrics.pearls_delta_actual = reward.pearls

    effective_rate = (
        0.0
        if metrics.pomo_completed_total <= 0
        else (metrics.pomo_effective_completed / max(1, metrics.pomo_completed_total))
    )
    skip_rate = (
        0.0
        if metrics.pomo_started_total <= 0
        else (metrics.pomo_skipped_total / max(1, metrics.pomo_started_total))
    )

    fail_reasons: list[str] = []
    warn_reasons: list[str] = []

    if metrics.pearls_delta_expected != metrics.pearls_delta_actual:
        fail_reasons.append(
            f"pearls mismatch expected={metrics.pearls_delta_expected} actual={metrics.pearls_delta_actual}"
        )
    if metrics.reward_duplicate_grant_violations > 0:
        fail_reasons.append("duplicate reward grant detected for same session_id")
    if metrics.auto_start_violations > 0:
        fail_reasons.append("auto start violation detected")
    if metrics.state_machine_invariant_violations > 0:
        fail_reasons.append("state machine invariant violation detected")

    if effective_rate < args.warn_effective_rate:
        warn_reasons.append(f"effective_rate low ({effective_rate:.2%})")
    if skip_rate > args.warn_skip_rate:
        warn_reasons.append(f"skip_rate high ({skip_rate:.2%})")

    status = "PASS" if not fail_reasons else "FAIL"
    summary = {
        "status": status,
        "mode": args.mode,
        "seed": args.seed,
        "runtime_simulated_seconds": runtime_s,
        "runtime_wall_seconds": round(time.monotonic() - t0, 3),
        "config": {
            "focus_seconds": focus_s,
            "break_seconds": break_s,
            "step_seconds": step_s,
            "restart_rate": args.restart_rate,
            "net_jitter": args.net_jitter,
            "valid_ratio": args.valid_ratio,
        },
        "metrics": {
            "pomo_completed_total": metrics.pomo_completed_total,
            "pomo_effective_rate": round(effective_rate, 4),
            "pearls_delta_expected": metrics.pearls_delta_expected,
            "pearls_delta_actual": metrics.pearls_delta_actual,
            "dedupe_hits": {
                "reward": metrics.reward_dedupe_hits + expected.dedupe_hits,
                "journal": metrics.journal_dedupe_hits,
            },
            "state_machine_invariant_violations": metrics.state_machine_invariant_violations,
            "recovery_checks": {
                "attempted": metrics.recovery_attempted,
                "passed": metrics.recovery_passed,
                "failed": metrics.recovery_failed,
                "auto_start_violations": metrics.auto_start_violations,
            },
            "skip_rate": round(skip_rate, 4),
        },
        "warnings": warn_reasons,
        "fail_reasons": fail_reasons,
        "samples": metrics.illegal_transition_samples[:8],
        "workdir": str(workdir),
    }

    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = workdir / "logs" / f"stress_pomo_{stamp}.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"log_saved={out_path}")
    return 0 if status == "PASS" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dugong Pomodoro black-box stress harness")
    parser.add_argument("--mode", choices=["fast", "soak"], default="fast")
    parser.add_argument("--minutes", type=float, default=3.0, help="fast mode simulated minutes")
    parser.add_argument("--hours", type=float, default=1.0, help="soak mode simulated hours")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workdir", default=".stress_pomo")
    parser.add_argument("--clean", action="store_true")

    parser.add_argument("--focus-seconds", type=int, default=0)
    parser.add_argument("--break-seconds", type=int, default=0)
    parser.add_argument("--step-seconds", type=int, default=1)
    parser.add_argument("--sleep-per-step", type=float, default=0.0)

    parser.add_argument("--pause-rate", type=float, default=0.03)
    parser.add_argument("--resume-rate", type=float, default=0.25)
    parser.add_argument("--skip-rate", type=float, default=0.02)
    parser.add_argument("--restart-rate", type=float, default=0.02)
    parser.add_argument("--net-jitter", type=float, default=0.1)
    parser.add_argument("--time-jump-rate", type=float, default=0.02)
    parser.add_argument("--time-jump-seconds", type=int, default=90)

    parser.add_argument("--base-pearls", type=int, default=10)
    parser.add_argument("--valid-ratio", type=float, default=0.8)
    parser.add_argument("--warn-effective-rate", type=float, default=0.55)
    parser.add_argument("--warn-skip-rate", type=float, default=0.45)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_stress_pomo(parse_args()))
