from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from datetime import datetime, timezone

from dugong_app.config import DugongConfig
from dugong_app.core.event_bus import EventBus
from dugong_app.core.events import DugongEvent
from dugong_app.core.events import (
    co_focus_milestone_event,
    click_event,
    manual_ping_event,
    mode_change_event,
    pomo_complete_event,
    pomo_pause_event,
    pomo_resume_event,
    pomo_skip_event,
    pomo_start_event,
    reward_grant_event,
    state_tick_event,
)
from dugong_app.core.rules import apply_tick, switch_mode
from dugong_app.interaction.transport_file import FileTransport
from dugong_app.interaction.transport_github import GithubTransport
from dugong_app.persistence.event_journal import EventJournal
from dugong_app.persistence.focus_sessions_json import FocusSessionsStorage
from dugong_app.persistence.storage_json import JsonStorage
from dugong_app.persistence.summary_json import SummaryStorage
from dugong_app.persistence.sync_cursor_json import SyncCursorStorage
from dugong_app.persistence.runtime_health_json import RuntimeHealthStorage
from dugong_app.persistence.pomodoro_state_json import PomodoroStateStorage
from dugong_app.persistence.reward_state_json import RewardStateStorage
from dugong_app.services.daily_summary import summarize_events
from dugong_app.services.focus_sessions import build_focus_sessions
from dugong_app.services.pomodoro_service import POMO_BREAK, POMO_FOCUS, POMO_PAUSED, PomodoroService
from dugong_app.services.reward_service import RewardService
from dugong_app.services.sync_engine import SyncEngine
from dugong_app.services.data_migration import migrate_legacy_repo_data
from dugong_app.ui.renderer import Renderer
from dugong_app.ui.shell_qt import DugongShell


class DugongController:
    def __init__(self, config: DugongConfig) -> None:
        self.config = config
        self.tick_seconds = config.tick_seconds
        self.source_id = config.source_id
        self.sync_interval_seconds = config.sync_interval_seconds

        self.bus = EventBus()
        self.storage = JsonStorage(config.data_dir / "dugong_state.json")
        self.renderer = Renderer()
        self.state = self.storage.load()

        self.unread_remote_count = 0
        self.sync_status = "idle"
        self._state_dirty = False
        self._pomo_dirty = False
        self._reward_dirty = False
        self._remote_presence: dict[str, dict[str, str | float]] = {}
        self._last_pomo_render_key: tuple[str, str, int] | None = None
        self._cofocus_last_monotonic = time.monotonic()
        self._cofocus_seconds = 0.0

        self.journal = EventJournal(
            config.data_dir / "event_journal.jsonl",
            retention_days=config.journal_retention_days,
            fsync_writes=config.journal_fsync,
        )
        self.summary_storage = SummaryStorage(config.data_dir / "daily_summary.json")
        self.focus_sessions_storage = FocusSessionsStorage(config.data_dir / "focus_sessions.json")
        self.sync_cursor_storage = SyncCursorStorage(config.data_dir / "sync_cursor.json")
        self.health_storage = RuntimeHealthStorage(config.data_dir / "sync_health.json")
        self.pomodoro_storage = PomodoroStateStorage(config.data_dir / "pomodoro_state.json")
        self.reward_storage = RewardStateStorage(config.data_dir / "reward_state.json")

        self.pomodoro = PomodoroService(
            focus_minutes=config.pomo_focus_minutes,
            break_minutes=config.pomo_break_minutes,
        )
        self.pomodoro.restore(self.pomodoro_storage.load())

        self.reward = RewardService(
            base_pearls=config.reward_base_pearls,
            valid_ratio=(config.reward_valid_ratio_percent / 100.0),
        )
        self.reward.restore(self.reward_storage.load())
        self._cofocus_seconds = float(self.reward.cofocus_seconds_total)

        transport, init_sync_status = self._create_transport()
        self.sync_status = init_sync_status
        self.sync_engine = SyncEngine(
            source_id=self.source_id,
            journal=self.journal,
            transport=transport,
            cursor_storage=self.sync_cursor_storage,
            on_remote_events=None,
        )
        if self.sync_status == "auth_missing":
            self.sync_engine.last_status = "auth_missing"

        self._jobs: queue.Queue[dict] = queue.Queue()
        self._results: queue.Queue[dict] = queue.Queue()
        self._sync_lock = threading.Lock()
        self._sync_pending = False
        self._sync_idle_multiplier = 1
        self._sync_idle_max_multiplier = max(1, config.sync_idle_max_multiplier)
        self._next_auto_sync_monotonic = 0.0
        self._last_fast_sync_monotonic = 0.0
        self._fast_sync_cooldown_seconds = 1.2
        self._derived_dirty = False
        self._derived_rebuild_interval_seconds = config.derived_rebuild_seconds
        self._derived_last_rebuild_monotonic = 0.0
        self._health_dirty = False
        self._health = {
            "sync_state": self.sync_status,
            "paused_reason": "",
            "unread_remote_count": 0,
            "bad_lines_skipped": 0,
            "last_push_at": "",
            "last_push_count": 0,
            "last_pull_at": "",
            "last_pull_imported": 0,
            "last_pull_received": 0,
            "cursor_last_seen_event_id_by_source": {},
            "cursor_last_seen_timestamp_by_source": {},
        }

        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

        self.shell = self._create_shell()
        self.bus.subscribe("*", self._on_any_event)

    def _create_transport(self):
        if self.config.transport == "file":
            return FileTransport(shared_dir=self.config.file_transport_dir, source_id=self.source_id), "idle"
        if self.config.transport == "github":
            if not self.config.github_repo or not self.config.github_token:
                return None, "auth_missing"
            return (
                GithubTransport(
                    repo=self.config.github_repo,
                    token=self.config.github_token,
                    source_id=self.source_id,
                    branch=self.config.github_branch,
                    folder=self.config.github_folder,
                ),
                "idle",
            )
        return None, "disabled"

    def _create_shell(self) -> DugongShell:
        try:
            return DugongShell(
                on_mode_change=self.on_mode_change,
                on_click=self.on_click,
                on_manual_ping=self.on_manual_ping,
                on_sync_now=self.on_sync_now,
                on_pomo_start=self.on_pomo_start,
                on_pomo_pause_resume=self.on_pomo_pause_resume,
                on_pomo_skip=self.on_pomo_skip,
                source_id=self.source_id,
                skin_id=self.config.skin_id,
            )
        except TypeError:
            return DugongShell(
                on_mode_change=self.on_mode_change,
                on_click=self.on_click,
            )

    def _rebuild_derived(self) -> None:
        all_events = self.journal.load_all()
        self.summary_storage.save(summarize_events(all_events))
        self.focus_sessions_storage.save(build_focus_sessions(all_events))

    def _worker_loop(self) -> None:
        while True:
            try:
                job = self._jobs.get(timeout=1)
            except queue.Empty:
                self._maybe_rebuild_derived(force=False)
                continue

            try:
                kind = job.get("kind")
                if kind == "local_event":
                    self._handle_local_event(job["event"])
                elif kind == "sync":
                    self._handle_sync_job(manual=bool(job.get("manual", False)))
            except Exception as exc:
                self._results.put({"kind": "worker_error", "error": str(exc)})

    def _handle_local_event(self, event) -> None:
        self.journal.append(event)
        self._derived_dirty = True

        status = "ok"
        pushed_count = 0
        try:
            published = self.sync_engine.publish_local_event(event)
            pushed_count = 1 if published else 0
            status = self.sync_engine.last_status
        except Exception:
            status = "fail"
        if self.sync_status == "auth_missing" and status == "disabled":
            status = "auth_missing"

        self._results.put({"kind": "local_done", "status": status, "pushed_count": pushed_count})
        self._maybe_rebuild_derived(force=False)

    def _handle_sync_job(self, manual: bool) -> None:
        result = self.sync_engine.sync_once(force=manual)
        imported = int(result.get("imported", 0))
        received = len(result.get("events", [])) if isinstance(result.get("events", []), list) else 0
        if imported > 0:
            self._derived_dirty = True
            self._maybe_rebuild_derived(force=True)
        self._results.put(
            {
                "kind": "sync_done",
                "status": result.get("status", "fail"),
                "imported": imported,
                "events": result.get("events", []),
                "received": received,
                "manual": manual,
            }
        )

    def _mark_health_dirty(self) -> None:
        self._health["sync_state"] = self.sync_status
        self._health["unread_remote_count"] = int(self.unread_remote_count)
        self._health["bad_lines_skipped"] = int(self.journal.last_read_stats().get("bad_lines_skipped", 0))
        cursor_state = self.sync_cursor_storage.load()
        self._health["cursor_last_seen_event_id_by_source"] = dict(
            cursor_state.get("last_seen_event_id_by_source", {})
        )
        self._health["cursor_last_seen_timestamp_by_source"] = dict(
            cursor_state.get("last_seen_timestamp_by_source", {})
        )
        self._health_dirty = True

    def _flush_health_if_dirty(self) -> None:
        if not self._health_dirty:
            return
        self.health_storage.save(self._health)
        self._health_dirty = False

    def _maybe_rebuild_derived(self, force: bool) -> None:
        if not self._derived_dirty:
            return
        now = time.monotonic()
        if not force and (now - self._derived_last_rebuild_monotonic) < self._derived_rebuild_interval_seconds:
            return
        self._rebuild_derived()
        self._derived_dirty = False
        self._derived_last_rebuild_monotonic = now

    def _remote_bubble(self, event) -> str:
        if event.event_type == "presence_hello":
            return f"[{event.source}] joined aquarium"
        if event.event_type == "manual_ping":
            return f"[{event.source}] pinged you"
        if event.event_type == "pomo_start":
            phase = str(event.payload.get("phase", "focus"))
            return f"[{event.source}] started {phase}"
        if event.event_type == "pomo_complete":
            phase = str(event.payload.get("phase", "focus"))
            return f"[{event.source}] completed {phase}"
        if event.event_type == "co_focus_milestone":
            mins = int(event.payload.get("milestone_seconds", 0)) // 60
            return f"[{event.source}] co-focus milestone {mins}m"
        if event.event_type == "reward_grant":
            pearls = int(event.payload.get("pearls", 0))
            return f"[{event.source}] +{pearls} pearls"
        if event.event_type == "mode_change":
            mode = event.payload.get("mode", "unknown")
            return f"[{event.source}] -> {mode}"
        if event.event_type == "state_tick":
            return f"[{event.source}] state updated"
        return f"[{event.source}] event: {event.event_type}"

    def _pick_representative_remote_event(self, events):
        priority = {
            "reward_grant": 5,
            "pomo_complete": 5,
            "co_focus_milestone": 5,
            "manual_ping": 4,
            "pomo_start": 4,
            "mode_change": 3,
            "presence_hello": 3,
            "focus_session_end": 2,
            "focus_session_start": 2,
            "state_tick": 1,
        }
        best = None
        best_rank = -1
        for ev in events:
            rank = priority.get(ev.event_type, 0)
            if rank >= best_rank:
                best = ev
                best_rank = rank
        return best

    def _signal_event_count(self, events) -> int:
        signal_types = {
            "manual_ping",
            "mode_change",
            "focus_session_start",
            "focus_session_end",
            "pomo_start",
            "pomo_complete",
            "co_focus_milestone",
            "reward_grant",
        }
        count = sum(1 for ev in events if ev.event_type in signal_types)
        if count > 0:
            return count
        # Presence/tick are background activity: no unread badge noise.
        if events and any(ev.event_type not in {"presence_hello", "state_tick"} for ev in events):
            return 1
        return 0

    def _update_remote_presence(self, events) -> None:
        now = time.time()
        for ev in events:
            source = (getattr(ev, "source", "") or "").strip()
            if not source or source == self.source_id:
                continue

            entry = self._remote_presence.setdefault(
                source,
                {
                    "source": source,
                    "mode": "unknown",
                    "last_seen": 0.0,
                    "event_type": "",
                    "event_id": "",
                    "pomo_phase": "",
                    "pomo_session_id": "",
                },
            )
            entry["last_seen"] = now
            entry["event_type"] = ev.event_type
            entry["event_id"] = str(getattr(ev, "event_id", "") or "")

            if ev.event_type == "mode_change":
                entry["mode"] = str(ev.payload.get("mode", entry.get("mode", "unknown")))
            elif ev.event_type == "state_tick":
                entry["mode"] = str(ev.payload.get("mode", entry.get("mode", "unknown")))
            elif ev.event_type == "presence_hello":
                entry["mode"] = str(ev.payload.get("mode", entry.get("mode", "unknown")))
            elif ev.event_type in {"pomo_start", "pomo_resume"}:
                phase = str(ev.payload.get("phase", "")).lower()
                entry["pomo_phase"] = phase
                entry["pomo_session_id"] = str(ev.payload.get("session_id", ""))
                if phase == "focus":
                    entry["mode"] = "study"
                elif phase == "break":
                    entry["mode"] = "chill"
            elif ev.event_type in {"pomo_pause", "pomo_complete", "pomo_skip"}:
                phase = str(ev.payload.get("phase", ev.payload.get("from_phase", ""))).lower()
                if phase == "focus":
                    entry["pomo_phase"] = ""

    def _shared_entities(self) -> list[dict[str, str | float]]:
        now = time.time()
        ttl_seconds = 20 * 60
        remote = [
            {
                "source": src,
                "mode": str(info.get("mode", "unknown")),
                "last_seen": float(info.get("last_seen", 0.0)),
                "last_event_type": str(info.get("event_type", "")),
                "last_event_id": str(info.get("event_id", "")),
                "is_local": 0.0,
            }
            for src, info in self._remote_presence.items()
            if (now - float(info.get("last_seen", 0.0))) <= ttl_seconds
        ]
        remote.sort(key=lambda x: str(x["source"]))
        local = {
            "source": self.source_id,
            "mode": self.state.mode,
            "last_seen": now,
            "is_local": 1.0,
        }
        return [local, *remote]

    def _update_auto_sync_policy(self, status: str, imported: int, manual: bool) -> None:
        if manual:
            self._sync_idle_multiplier = 1
            return
        if status == "ok":
            if imported > 0:
                self._sync_idle_multiplier = 1
            else:
                self._sync_idle_multiplier = min(self._sync_idle_max_multiplier, self._sync_idle_multiplier * 2)
            return
        if status in {"auth_fail", "auth_missing"}:
            self._sync_idle_multiplier = self._sync_idle_max_multiplier
            return
        if status == "paused":
            self._sync_idle_multiplier = self._sync_idle_max_multiplier
            return
        self._sync_idle_multiplier = min(self._sync_idle_max_multiplier, self._sync_idle_multiplier * 2)

    def _drain_worker_results(self) -> None:
        changed = False
        bubble: str | None = None

        while True:
            try:
                result = self._results.get_nowait()
            except queue.Empty:
                break

            kind = result.get("kind")
            if kind == "local_done":
                self.sync_status = result.get("status", "fail")
                pushed_count = int(result.get("pushed_count", 0))
                if pushed_count > 0:
                    self._health["last_push_at"] = datetime.now(tz=timezone.utc).isoformat()
                    self._health["last_push_count"] = pushed_count
                changed = True
            elif kind == "sync_done":
                self.sync_status = result.get("status", "fail")
                imported = int(result.get("imported", 0))
                events = result.get("events", [])
                received = int(result.get("received", 0))
                manual = bool(result.get("manual", False))
                self._update_auto_sync_policy(status=self.sync_status, imported=imported, manual=manual)
                self._health["last_pull_at"] = datetime.now(tz=timezone.utc).isoformat()
                self._health["last_pull_imported"] = imported
                self._health["last_pull_received"] = received
                if self.sync_status == "paused":
                    self._health["paused_reason"] = "auth_fail_or_missing"
                elif self.sync_status in {"auth_fail", "auth_missing"}:
                    self._health["paused_reason"] = self.sync_status
                else:
                    self._health["paused_reason"] = ""
                changed = True

                with self._sync_lock:
                    self._sync_pending = False

                if self.sync_status in {"auth_fail", "auth_missing"}:
                    bubble = "Sync auth missing/invalid"
                elif self.sync_status == "paused":
                    bubble = "Sync paused (auth)"
                elif self.sync_status == "rate_limited":
                    bubble = "Sync rate limited"
                elif self.sync_status == "offline":
                    bubble = "Sync offline"
                elif self.sync_status.startswith("retrying("):
                    bubble = self.sync_status
                elif self.sync_status == "fail":
                    bubble = "Sync failed"
                elif imported > 0:
                    self._update_remote_presence(events)
                    self.unread_remote_count += self._signal_event_count(events)
                    representative = self._pick_representative_remote_event(events)
                    if representative is not None:
                        bubble = self._remote_bubble(representative)
                elif manual:
                    bubble = "Sync now: +0"
            elif kind == "worker_error":
                self.sync_status = "fail"
                bubble = f"Worker error: {result.get('error', 'unknown')}"
                changed = True

        if changed:
            self._mark_health_dirty()
        if changed or bubble is not None:
            self.refresh(bubble=bubble)

    def _state_text(self) -> str:
        cofocus_min = int(self.reward.cofocus_seconds_total) // 60
        return (
            f"E:{self.state.energy} M:{self.state.mood} F:{self.state.focus} "
            f"[{self.state.mode}] P:{self.reward.pearls} C:{cofocus_min}m"
        )

    def _pomo_text(self) -> str:
        view = self.pomodoro.view()
        mm = view.remaining_s // 60
        ss = view.remaining_s % 60
        if view.state == "IDLE":
            return f"POMO IDLE  ({view.focus_minutes}m/{view.break_minutes}m)"
        if view.state == "PAUSED":
            phase = view.phase.upper() if view.phase else "READY"
            return f"POMO {phase} PAUSED  {mm:02d}:{ss:02d}"
        phase = view.phase.upper() if view.phase else view.state
        return f"POMO {phase}  {mm:02d}:{ss:02d}"

    def _active_remote_focus_peers(self) -> int:
        now = time.time()
        ttl = max(20.0, float(self.sync_interval_seconds * 3))
        count = 0
        for info in self._remote_presence.values():
            if (now - float(info.get("last_seen", 0.0))) > ttl:
                continue
            if str(info.get("pomo_phase", "")).lower() == "focus":
                count += 1
        return count

    def _update_cofocus_progress(self) -> None:
        now_mono = time.monotonic()
        delta = max(0.0, now_mono - self._cofocus_last_monotonic)
        self._cofocus_last_monotonic = now_mono
        if delta <= 0.0:
            return
        if self.pomodoro.view().state != POMO_FOCUS:
            return
        peers = self._active_remote_focus_peers()
        if peers <= 0:
            return

        prev = self._cofocus_seconds
        self._cofocus_seconds += delta
        self.reward.cofocus_seconds_total = int(self._cofocus_seconds)
        self._reward_dirty = True

        milestone_seconds = max(60, int(self.config.cofocus_milestone_seconds))
        prev_idx = int(prev // milestone_seconds)
        cur_idx = int(self._cofocus_seconds // milestone_seconds)
        if cur_idx <= prev_idx:
            return
        for idx in range(prev_idx + 1, cur_idx + 1):
            milestone_id = f"{self.source_id}:cofocus:{idx}"
            self.bus.emit(
                co_focus_milestone_event(
                    milestone_id=milestone_id,
                    milestone_index=idx,
                    milestone_seconds=(idx * milestone_seconds),
                    total_cofocus_seconds=int(self._cofocus_seconds),
                    source=self.source_id,
                )
            )

    def refresh(self, bubble: str | None = None) -> None:
        sprite = self.renderer.sprite_for(self.state)
        try:
            self.shell.update_view(
                sprite=sprite,
                state_text=self._state_text(),
                pomo_text=self._pomo_text(),
                pomo_state=self.pomodoro.view().state,
                reward_stats={
                    "pearls": int(self.reward.pearls),
                    "focus_streak": int(self.reward.focus_streak),
                    "day_streak": int(self.reward.day_streak),
                },
                bubble=bubble,
                entities=self._shared_entities(),
                local_source=self.source_id,
            )
        except TypeError:
            self.shell.update_view(sprite=sprite, state_text=self._state_text(), bubble=bubble)

    def _on_any_event(self, event) -> None:
        self._state_dirty = True
        if event.event_type.startswith("pomo_"):
            self._pomo_dirty = True
        if event.event_type == "pomo_complete" and str(event.source) == self.source_id:
            grant = self.reward.grant_for_completion(event.payload)
            if grant is not None:
                self._reward_dirty = True
                self.bus.emit(
                    reward_grant_event(
                        pearls=grant.pearls,
                        streak_bonus=grant.streak_bonus,
                        reason=grant.reason,
                        session_id=grant.session_id,
                        focus_streak=grant.focus_streak,
                        day_streak=grant.day_streak,
                        source=self.source_id,
                    )
                )
        elif event.event_type == "pomo_skip" and str(event.source) == self.source_id:
            self.reward.on_skip(str(event.payload.get("from_phase", "")))
            self._reward_dirty = True
        elif event.event_type == "co_focus_milestone" and str(event.source) == self.source_id:
            grant = self.reward.grant_for_cofocus(
                milestone_id=str(event.payload.get("milestone_id", "")),
                pearls=int(self.config.cofocus_bonus_pearls),
            )
            if grant is not None:
                self._reward_dirty = True
                self.bus.emit(
                    reward_grant_event(
                        pearls=grant.pearls,
                        streak_bonus=grant.streak_bonus,
                        reason=grant.reason,
                        session_id=grant.session_id,
                        focus_streak=grant.focus_streak,
                        day_streak=grant.day_streak,
                        source=self.source_id,
                    )
                )
        elif event.event_type == "reward_grant":
            self._reward_dirty = True
        self._jobs.put({"kind": "local_event", "event": event})

    def _flush_state_if_dirty(self) -> None:
        if not self._state_dirty:
            return
        self.storage.save(self.state)
        self._state_dirty = False

    def _flush_pomodoro_if_dirty(self) -> None:
        if not self._pomo_dirty:
            return
        self.pomodoro_storage.save(self.pomodoro.snapshot())
        self._pomo_dirty = False

    def _flush_reward_if_dirty(self) -> None:
        if not self._reward_dirty:
            return
        self.reward_storage.save(self.reward.snapshot())
        self._reward_dirty = False

    def on_mode_change(self, mode: str) -> None:
        self.state = switch_mode(self.state, mode)
        self.bus.emit(mode_change_event(mode, source=self.source_id))
        self._request_fast_sync()
        self.refresh(bubble=f"Mode -> {mode}")

    def on_click(self) -> None:
        if self.unread_remote_count > 0:
            self.unread_remote_count = 0
        self.bus.emit(click_event(source=self.source_id))
        self.refresh(bubble=self.renderer.bubble_for_click(self.state))

    def on_manual_ping(self, message: str = "manual_ping") -> None:
        self.bus.emit(manual_ping_event(message, source=self.source_id))
        self._request_fast_sync()
        self.refresh(bubble="Signal sent")

    def _emit_pomo_event(self, event_type: str, payload: dict) -> None:
        if event_type == "pomo_start":
            self.bus.emit(
                pomo_start_event(
                    phase=str(payload.get("phase", "")),
                    duration_s=int(payload.get("duration_s", 0)),
                    session_id=str(payload.get("session_id", "")),
                    source=self.source_id,
                )
            )
            return
        if event_type == "pomo_pause":
            self.bus.emit(
                pomo_pause_event(
                    phase=str(payload.get("phase", "")),
                    session_id=str(payload.get("session_id", "")),
                    remaining_s=int(payload.get("remaining_s", 0)),
                    source=self.source_id,
                )
            )
            return
        if event_type == "pomo_resume":
            self.bus.emit(
                pomo_resume_event(
                    phase=str(payload.get("phase", "")),
                    session_id=str(payload.get("session_id", "")),
                    remaining_s=int(payload.get("remaining_s", 0)),
                    source=self.source_id,
                )
            )
            return
        if event_type == "pomo_skip":
            self.bus.emit(
                pomo_skip_event(
                    from_phase=str(payload.get("from_phase", "")),
                    session_id=str(payload.get("session_id", "")),
                    completed_s=int(payload.get("completed_s", 0)),
                    duration_s=int(payload.get("duration_s", 0)),
                    source=self.source_id,
                )
            )
            return
        if event_type == "pomo_complete":
            self.bus.emit(
                pomo_complete_event(
                    phase=str(payload.get("phase", "")),
                    session_id=str(payload.get("session_id", "")),
                    completed_s=int(payload.get("completed_s", 0)),
                    duration_s=int(payload.get("duration_s", 0)),
                    source=self.source_id,
                )
            )
            return

    def on_pomo_start(self) -> None:
        payload = self.pomodoro.start_focus()
        if not payload:
            self.refresh(bubble="Pomodoro: start unavailable")
            return
        self._pomo_dirty = True
        self._emit_pomo_event("pomo_start", payload)
        self._request_fast_sync()
        self.refresh(bubble="Focus started")

    def on_pomo_pause_resume(self) -> None:
        view = self.pomodoro.view()
        if view.state in {POMO_FOCUS, POMO_BREAK}:
            payload = self.pomodoro.pause()
            if payload:
                self._pomo_dirty = True
                self._emit_pomo_event("pomo_pause", payload)
                self.refresh(bubble="Pomodoro paused")
            return
        if view.state == POMO_PAUSED:
            payload = self.pomodoro.resume()
            if payload:
                self._pomo_dirty = True
                self._emit_pomo_event("pomo_resume", payload)
                self.refresh(bubble="Pomodoro resumed")
            return
        self.refresh(bubble="Pomodoro is idle")

    def on_pomo_skip(self) -> None:
        events = self.pomodoro.skip()
        if not events:
            self.refresh(bubble="Pomodoro skip unavailable")
            return
        self._pomo_dirty = True
        for event_type, payload in events:
            self._emit_pomo_event(event_type, payload)
        self._request_fast_sync()
        self.refresh(bubble="Pomodoro skipped")

    def on_pomo_tick(self) -> None:
        self._update_cofocus_progress()
        events = self.pomodoro.tick()
        if events:
            self._pomo_dirty = True
            for event_type, payload in events:
                self._emit_pomo_event(event_type, payload)
            self._request_fast_sync()
            phase = str(events[0][1].get("phase", ""))
            if phase == "focus":
                self.refresh(bubble="Focus complete. Break started.")
            elif phase == "break":
                self.refresh(bubble="Break complete. Start next focus manually.")
            else:
                self.refresh()
            return
        view = self.pomodoro.view()
        key = (view.state, view.phase, view.remaining_s)
        if key == self._last_pomo_render_key:
            return
        self._last_pomo_render_key = key
        self.refresh()

    def on_tick(self) -> None:
        self.state = apply_tick(self.state, tick_seconds=self.tick_seconds)
        self.bus.emit(state_tick_event(self.state.to_dict(), tick_seconds=self.tick_seconds, source=self.source_id))
        self.refresh()

    def _enqueue_sync(self, manual: bool) -> None:
        with self._sync_lock:
            if self._sync_pending:
                return
            self._sync_pending = True
        self._jobs.put({"kind": "sync", "manual": manual})

    def _request_fast_sync(self) -> None:
        now = time.monotonic()
        if (now - self._last_fast_sync_monotonic) < self._fast_sync_cooldown_seconds:
            return
        self._last_fast_sync_monotonic = now
        self._enqueue_sync(manual=False)

    def on_sync_tick(self) -> None:
        now = time.monotonic()
        if now < self._next_auto_sync_monotonic:
            return
        self._enqueue_sync(manual=False)
        self._next_auto_sync_monotonic = now + (self.sync_interval_seconds * self._sync_idle_multiplier)

    def on_sync_now(self) -> None:
        self._sync_idle_multiplier = 1
        self._next_auto_sync_monotonic = 0.0
        self._enqueue_sync(manual=True)
        self.refresh(bubble="Syncing...")

    def run(self) -> None:
        self.bus.emit(
            DugongEvent(
                event_type="presence_hello",
                source=self.source_id,
                payload={"mode": self.state.mode},
            )
        )
        self._request_fast_sync()
        self.refresh(bubble=f"Dugong online [{self.source_id}]")
        self.on_sync_now()
        self.shell.schedule_every(self.tick_seconds, self.on_tick)
        self.shell.schedule_every(1, self.on_pomo_tick)
        self.shell.schedule_every(self.sync_interval_seconds, self.on_sync_tick)
        self.shell.schedule_every(1, self._drain_worker_results)
        self.shell.schedule_every(1, self._flush_state_if_dirty)
        self.shell.schedule_every(1, self._flush_pomodoro_if_dirty)
        self.shell.schedule_every(1, self._flush_reward_if_dirty)
        self.shell.schedule_every(1, self._flush_health_if_dirty)
        self.shell.run()


def create_default_controller() -> DugongController:
    repo_root = Path(__file__).resolve().parent.parent
    config = DugongConfig.from_env(repo_root)
    migration = migrate_legacy_repo_data(repo_root=repo_root, data_dir=config.data_dir)
    if migration.get("migrated_files", 0) or migration.get("migrated_dirs", 0):
        print(
            f"[dugong] migrated legacy data -> {config.data_dir} "
            f"(files={migration.get('migrated_files', 0)}, dirs={migration.get('migrated_dirs', 0)})"
        )
    return DugongController(config=config)
