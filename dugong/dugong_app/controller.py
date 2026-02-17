from __future__ import annotations

import os
from pathlib import Path

from dugong_app.core.event_bus import EventBus
from dugong_app.core.events import click_event, mode_change_event, state_tick_event
from dugong_app.core.rules import apply_tick, switch_mode
from dugong_app.persistence.storage_json import JsonStorage
from dugong_app.ui.renderer import Renderer
from dugong_app.ui.shell_qt import DugongShell


class DugongController:
    def __init__(self, storage_path: str | Path, tick_seconds: int = 60) -> None:
        self.tick_seconds = tick_seconds
        self.bus = EventBus()
        self.storage = JsonStorage(storage_path)
        self.renderer = Renderer()
        self.state = self.storage.load()

        self.shell = DugongShell(
            on_mode_change=self.on_mode_change,
            on_click=self.on_click,
        )
        self.bus.subscribe("*", self._on_any_event)

    def _on_any_event(self, _event) -> None:
        self.storage.save(self.state)

    def _state_text(self) -> str:
        return f"E:{self.state.energy} M:{self.state.mood} F:{self.state.focus} [{self.state.mode}]"

    def refresh(self, bubble: str | None = None) -> None:
        sprite = self.renderer.sprite_for(self.state)
        self.shell.update_view(sprite=sprite, state_text=self._state_text(), bubble=bubble)

    def on_mode_change(self, mode: str) -> None:
        self.state = switch_mode(self.state, mode)
        self.bus.emit(mode_change_event(mode))
        self.refresh(bubble=f"Mode -> {mode}")

    def on_click(self) -> None:
        self.bus.emit(click_event())
        bubble = self.renderer.bubble_for_click(self.state)
        self.refresh(bubble=bubble)

    def on_tick(self) -> None:
        self.state = apply_tick(self.state, tick_seconds=self.tick_seconds)
        self.bus.emit(state_tick_event(self.state.to_dict()))
        self.refresh()

    def run(self) -> None:
        self.refresh(bubble="Dugong online")
        self.shell.schedule_every(self.tick_seconds, self.on_tick)
        self.shell.run()


def create_default_controller() -> DugongController:
    repo_root = Path(__file__).resolve().parent.parent
    storage_path = repo_root / "dugong_state.json"
    tick_seconds = int(os.getenv("DUGONG_TICK_SECONDS", "60"))
    return DugongController(storage_path=storage_path, tick_seconds=tick_seconds)
