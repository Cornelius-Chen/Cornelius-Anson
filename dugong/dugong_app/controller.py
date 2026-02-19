from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from datetime import datetime, timezone

from dugong_app.config import DugongConfig
from dugong_app.core.event_bus import EventBus
from dugong_app.core.events import click_event, manual_ping_event, mode_change_event, state_tick_event
from dugong_app.core.rules import apply_tick, switch_mode
from dugong_app.interaction.transport_file import FileTransport
from dugong_app.interaction.transport_github import GithubTransport
from dugong_app.persistence.event_journal import EventJournal
from dugong_app.persistence.focus_sessions_json import FocusSessionsStorage
from dugong_app.persistence.storage_json import JsonStorage
from dugong_app.persistence.summary_json import SummaryStorage
from dugong_app.persistence.sync_cursor_json import SyncCursorStorage
from dugong_app.persistence.runtime_health_json import RuntimeHealthStorage
from dugong_app.services.daily_summary import summarize_events
from dugong_app.services.focus_sessions import build_focus_sessions
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
        self._remote_presence: dict[str, dict[str, str | float]] = {}

        self.journal = EventJournal(
            config.data_dir / "event_journal.jsonl",
            retention_days=config.journal_retention_days,
            fsync_writes=config.journal_fsync,
        )
        self.summary_storage = SummaryStorage(config.data_dir / "daily_summary.json")
        self.focus_sessions_storage = FocusSessionsStorage(config.data_dir / "focus_sessions.json")
        self.sync_cursor_storage = SyncCursorStorage(config.data_dir / "sync_cursor.json")
        self.health_storage = RuntimeHealthStorage(config.data_dir / "sync_health.json")

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
                source_id=self.source_id,
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
        if event.event_type == "manual_ping":
            return f"[{event.source}] pinged you"
        if event.event_type == "mode_change":
            mode = event.payload.get("mode", "unknown")
            return f"[{event.source}] -> {mode}"
        if event.event_type == "state_tick":
            return f"[{event.source}] state updated"
        return f"[{event.source}] event: {event.event_type}"

    def _pick_representative_remote_event(self, events):
        priority = {
            "manual_ping": 4,
            "mode_change": 3,
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
        signal_types = {"manual_ping", "mode_change", "focus_session_start", "focus_session_end"}
        count = sum(1 for ev in events if ev.event_type in signal_types)
        # No strong signal: keep at least one notification so user knows remote had activity.
        return max(1 if events else 0, count)

    def _update_remote_presence(self, events) -> None:
        now = time.time()
        for ev in events:
            source = (getattr(ev, "source", "") or "").strip()
            if not source or source == self.source_id:
                continue

            entry = self._remote_presence.setdefault(
                source,
                {"source": source, "mode": "unknown", "last_seen": 0.0, "event_type": ""},
            )
            entry["last_seen"] = now
            entry["event_type"] = ev.event_type

            if ev.event_type == "mode_change":
                entry["mode"] = str(ev.payload.get("mode", entry.get("mode", "unknown")))
            elif ev.event_type == "state_tick":
                entry["mode"] = str(ev.payload.get("mode", entry.get("mode", "unknown")))

    def _shared_entities(self) -> list[dict[str, str | float]]:
        now = time.time()
        ttl_seconds = 20 * 60
        remote = [
            {
                "source": src,
                "mode": str(info.get("mode", "unknown")),
                "last_seen": float(info.get("last_seen", 0.0)),
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
        return f"E:{self.state.energy} M:{self.state.mood} F:{self.state.focus} [{self.state.mode}]"

    def refresh(self, bubble: str | None = None) -> None:
        sprite = self.renderer.sprite_for(self.state)
        try:
            self.shell.update_view(
                sprite=sprite,
                state_text=self._state_text(),
                bubble=bubble,
                entities=self._shared_entities(),
                local_source=self.source_id,
            )
        except TypeError:
            self.shell.update_view(sprite=sprite, state_text=self._state_text(), bubble=bubble)

    def _on_any_event(self, event) -> None:
        self._state_dirty = True
        self._jobs.put({"kind": "local_event", "event": event})

    def _flush_state_if_dirty(self) -> None:
        if not self._state_dirty:
            return
        self.storage.save(self.state)
        self._state_dirty = False

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
        self.refresh(bubble=f"Dugong online [{self.source_id}]")
        self.on_sync_now()
        self.shell.schedule_every(self.tick_seconds, self.on_tick)
        self.shell.schedule_every(self.sync_interval_seconds, self.on_sync_tick)
        self.shell.schedule_every(1, self._drain_worker_results)
        self.shell.schedule_every(1, self._flush_state_if_dirty)
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
