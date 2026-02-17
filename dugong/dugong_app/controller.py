from __future__ import annotations

import os
from pathlib import Path

from dugong_app.core.event_bus import EventBus
from dugong_app.core.events import click_event, manual_ping_event, mode_change_event, state_tick_event
from dugong_app.interaction.transport_github import GithubTransport
from dugong_app.core.rules import apply_tick, switch_mode
from dugong_app.interaction.transport_file import FileTransport
from dugong_app.persistence.event_journal import EventJournal
from dugong_app.persistence.focus_sessions_json import FocusSessionsStorage
from dugong_app.persistence.storage_json import JsonStorage
from dugong_app.persistence.summary_json import SummaryStorage
from dugong_app.services.daily_summary import summarize_events
from dugong_app.services.focus_sessions import build_focus_sessions
from dugong_app.services.sync_engine import SyncEngine
from dugong_app.ui.renderer import Renderer
from dugong_app.ui.shell_qt import DugongShell


class DugongController:
    def __init__(self, storage_path: str | Path, tick_seconds: int = 60) -> None:
        self.tick_seconds = tick_seconds
        self.source_id = os.getenv("DUGONG_SOURCE_ID", "unknown")
        self.sync_interval_seconds = int(os.getenv("DUGONG_SYNC_INTERVAL_SECONDS", "10"))

        self.bus = EventBus()
        self.storage = JsonStorage(storage_path)
        self.renderer = Renderer()
        self.state = self.storage.load()

        self.unread_remote_count = 0
        self.sync_status = "idle"

        root_dir = Path(storage_path).resolve().parent
        retention_days = int(os.getenv("DUGONG_JOURNAL_RETENTION_DAYS", "30"))
        self.journal = EventJournal(root_dir / "event_journal.jsonl", retention_days=retention_days)
        self.summary_storage = SummaryStorage(root_dir / "daily_summary.json")
        self.focus_sessions_storage = FocusSessionsStorage(root_dir / "focus_sessions.json")

        transport = self._create_transport(root_dir)
        self.sync_engine = SyncEngine(
            source_id=self.source_id,
            journal=self.journal,
            transport=transport,
            on_remote_events=self._on_remote_events,
        )

        self.shell = self._create_shell()
        self.bus.subscribe("*", self._on_any_event)

    def _create_transport(self, root_dir: Path):
        transport_name = os.getenv("DUGONG_TRANSPORT", "file").lower()
        if transport_name == "file":
            shared_dir = Path(os.getenv("DUGONG_FILE_TRANSPORT_DIR", str(root_dir / "transport_shared")))
            return FileTransport(shared_dir=shared_dir, source_id=self.source_id)
        if transport_name == "github":
            repo = os.getenv("DUGONG_GITHUB_REPO", "").strip()
            token = os.getenv("DUGONG_GITHUB_TOKEN", "").strip()
            if not repo or not token:
                return None
            branch = os.getenv("DUGONG_GITHUB_BRANCH", "main").strip() or "main"
            folder = os.getenv("DUGONG_GITHUB_FOLDER", "dugong_sync").strip() or "dugong_sync"
            return GithubTransport(
                repo=repo,
                token=token,
                source_id=self.source_id,
                branch=branch,
                folder=folder,
            )
        return None

    def _create_shell(self) -> DugongShell:
        try:
            return DugongShell(
                on_mode_change=self.on_mode_change,
                on_click=self.on_click,
                on_manual_ping=self.on_manual_ping,
                on_sync_now=self.on_sync_now,
            )
        except TypeError:
            return DugongShell(
                on_mode_change=self.on_mode_change,
                on_click=self.on_click,
            )

    def _rebuild_derived(self) -> None:
        all_events = self.journal.load_all()
        summary = summarize_events(all_events)
        focus_sessions = build_focus_sessions(all_events)
        self.summary_storage.save(summary)
        self.focus_sessions_storage.save(focus_sessions)

    def _remote_bubble(self, event) -> str:
        if event.event_type == "manual_ping":
            return f"[{event.source}] pinged you"
        if event.event_type == "mode_change":
            mode = event.payload.get("mode", "unknown")
            return f"[{event.source}] -> {mode}"
        if event.event_type == "state_tick":
            return f"[{event.source}] state updated"
        return f"[{event.source}] event: {event.event_type}"

    def _on_remote_events(self, events) -> None:
        self.unread_remote_count += len(events)
        self._rebuild_derived()
        if events:
            self.refresh(bubble=self._remote_bubble(events[-1]))

    def _on_any_event(self, event) -> None:
        self.storage.save(self.state)
        self.journal.append(event)
        self._rebuild_derived()

        try:
            self.sync_engine.publish_local_event(event)
            self.sync_status = self.sync_engine.last_status
        except Exception:
            self.sync_status = "fail"

    def _state_text(self) -> str:
        return (
            f"E:{self.state.energy} M:{self.state.mood} F:{self.state.focus} "
            f"[{self.state.mode}] R:{self.unread_remote_count} S:{self.sync_status}"
        )

    def refresh(self, bubble: str | None = None) -> None:
        sprite = self.renderer.sprite_for(self.state)
        self.shell.update_view(sprite=sprite, state_text=self._state_text(), bubble=bubble)

    def on_mode_change(self, mode: str) -> None:
        self.state = switch_mode(self.state, mode)
        self.bus.emit(mode_change_event(mode, source=self.source_id))
        self.refresh(bubble=f"Mode -> {mode}")

    def on_click(self) -> None:
        if self.unread_remote_count > 0:
            self.unread_remote_count = 0
        self.bus.emit(click_event(source=self.source_id))
        bubble = self.renderer.bubble_for_click(self.state)
        self.refresh(bubble=bubble)

    def on_manual_ping(self, message: str = "manual_ping") -> None:
        self.bus.emit(manual_ping_event(message, source=self.source_id))
        self.refresh(bubble="Signal sent")

    def on_tick(self) -> None:
        self.state = apply_tick(self.state, tick_seconds=self.tick_seconds)
        self.bus.emit(state_tick_event(self.state.to_dict(), tick_seconds=self.tick_seconds, source=self.source_id))
        self.refresh()

    def on_sync_tick(self) -> None:
        result = self.sync_engine.sync_once()
        self.sync_status = result.get("status", "fail")
        if result.get("status") == "fail":
            self.refresh(bubble="Sync failed")
        else:
            self.refresh()

    def on_sync_now(self) -> None:
        result = self.sync_engine.sync_once()
        self.sync_status = result.get("status", "fail")
        if result.get("status") == "fail":
            self.refresh(bubble="Sync failed")
            return
        imported = int(result.get("imported", 0))
        self.refresh(bubble=f"Sync now: +{imported}")

    def run(self) -> None:
        self.refresh(bubble=f"Dugong online [{self.source_id}]")
        self.on_sync_now()
        self.shell.schedule_every(self.tick_seconds, self.on_tick)
        self.shell.schedule_every(self.sync_interval_seconds, self.on_sync_tick)
        self.shell.run()


def create_default_controller() -> DugongController:
    repo_root = Path(__file__).resolve().parent.parent
    storage_path = repo_root / "dugong_state.json"
    tick_seconds = int(os.getenv("DUGONG_TICK_SECONDS", "60"))
    return DugongController(storage_path=storage_path, tick_seconds=tick_seconds)
