from __future__ import annotations

import math
import random
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets


class DugongShell:
    def __init__(
        self,
        on_mode_change: Callable[[str], None],
        on_click: Callable[[], None],
        on_manual_ping: Callable[[str], None] | None = None,
        on_sync_now: Callable[[], None] | None = None,
        source_id: str = "local",
    ) -> None:
        self._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self._win = _DugongWindow(on_mode_change, on_click, on_manual_ping, on_sync_now, source_id=source_id)

    def schedule_every(self, seconds: int, callback: Callable[[], None]) -> None:
        timer = QtCore.QTimer(self._win)
        timer.setInterval(max(1, int(seconds * 1000)))
        timer.timeout.connect(callback)
        timer.start()
        self._win._timers.append(timer)

    def update_view(
        self,
        sprite: str,
        state_text: str,
        bubble: str | None = None,
        entities: list[dict[str, str | float]] | None = None,
        local_source: str | None = None,
    ) -> None:
        self._win.set_state_text(state_text)
        self._win.apply_sprite_hint(sprite)
        if entities is not None:
            self._win.set_shared_entities(entities, local_source=local_source)
        if bubble is not None:
            self._win.show_bubble(bubble)

    def run(self) -> None:
        self._win.show()
        self._win.raise_()
        self._win.activateWindow()
        self._app.exec()


class _DugongWindow(QtWidgets.QWidget):
    def __init__(
        self,
        on_mode_change: Callable[[str], None],
        on_click: Callable[[], None],
        on_manual_ping: Callable[[str], None] | None,
        on_sync_now: Callable[[], None] | None,
        source_id: str = "local",
    ) -> None:
        super().__init__()
        self._on_mode_change = on_mode_change
        self._on_click = on_click
        self._on_manual_ping = on_manual_ping
        self._on_sync_now = on_sync_now
        self._timers: list[QtCore.QTimer] = []
        self._local_source = source_id or "local"
        self._peer_entities: dict[str, dict[str, float | str]] = {}
        self._peer_anim_index: dict[str, int] = {}
        self._peer_current_frame: dict[str, QtGui.QPixmap] = {}

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self._target_height = 260
        self._apply_screen_width()

        self._dragging = False
        self._drag_moved = False
        self._press_global = QtCore.QPoint(0, 0)
        self._drag_offset = QtCore.QPoint(0, 0)

        assets_dir = Path(__file__).resolve().parent / "assets"
        self._bg_src = self._load_background(assets_dir)
        self._frames_raw, self._react_raw = self._load_character_assets(assets_dir)

        self._anim_mode = "swim"  # swim | idle | turn | react
        self._react_kind = "happy"  # happy | chill | dumb | shock
        self._react_until = 0.0
        self._anim_direction = "right"
        self._anim_index: dict[str, int] = {}

        self._last_mode = ""

        self._dugong_frame = QtGui.QPixmap()
        self._x = 0.0
        self._y = 0.0
        self._target_x = 0.0
        self._target_y = 0.0
        self._vx = 1.7
        self._vy = 0.0
        self._swim_speed = 2.0
        self._float_phase = 0.0
        self._idle_ticks_left = 0
        self._turn_ticks_left = 0

        self._dugong_anim_ms = 130
        self._world_tick_ms = 28
        self._bg_tick_ms = 30
        self._bg_speed_px = 0.7
        self._bg_offset = 0.0

        self._bg_scaled: QtGui.QPixmap | None = None
        self._frames_scaled: dict[str, dict[str, list[QtGui.QPixmap]]] = {"right": {}, "left": {}}
        self._react_scaled: dict[str, dict[str, list[QtGui.QPixmap]]] = {"right": {}, "left": {}}
        self._rebuild_scaled_pixmaps()

        self._title = QtWidgets.QLabel("Dugong", self)
        self._title.setStyleSheet("color: rgba(255,255,255,210); font-size: 18px; font-weight: 700;")
        self._title.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

        self._state = QtWidgets.QLabel("state", self)
        self._state.setStyleSheet("color: rgba(255,255,255,210); font-size: 14px;")
        self._state.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

        self._bubble = QtWidgets.QLabel("", self)
        self._bubble.setWordWrap(True)
        self._bubble.setStyleSheet(
            """
            color: rgba(255,255,255,235);
            background: rgba(20,30,45,140);
            border-radius: 10px;
            padding: 8px 10px;
            font-size: 13px;
        """
        )
        self._bubble.hide()
        self._bubble_timer = QtCore.QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self._bubble.hide)

        self._bar = QtWidgets.QFrame(self)
        self._bar.setStyleSheet("background: rgba(10,18,28,210); border-radius: 12px;")
        self._bar.setFixedHeight(44)
        lay = QtWidgets.QHBoxLayout(self._bar)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(10)

        def mk_btn(text: str, color: str, fn: Callable[[], None]) -> QtWidgets.QPushButton:
            b = QtWidgets.QPushButton(text)
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            b.setStyleSheet(
                f"""
                QPushButton {{
                    color: white;
                    background: {color};
                    border: none;
                    padding: 6px 12px;
                    border-radius: 10px;
                    font-weight: 700;
                }}
            """
            )
            b.clicked.connect(fn)
            return b

        lay.addWidget(mk_btn("study", "#1d3a57", lambda: self._emit_mode("study")))
        lay.addWidget(mk_btn("chill", "#1d3a57", lambda: self._emit_mode("chill")))
        lay.addWidget(mk_btn("rest", "#1d3a57", lambda: self._emit_mode("rest")))
        lay.addWidget(mk_btn("ping", "#275e44", self._emit_ping))
        lay.addWidget(mk_btn("sync", "#6b4f1f", self._emit_sync))
        lay.addWidget(mk_btn("quit", "#6a2c2c", self._emit_quit))
        self._bar.hide()

        self._hide_bar_timer = QtCore.QTimer(self)
        self._hide_bar_timer.setSingleShot(True)
        self._hide_bar_timer.timeout.connect(self._bar.hide)

        self._dugong_timer = QtCore.QTimer(self)
        self._dugong_timer.setInterval(self._dugong_anim_ms)
        self._dugong_timer.timeout.connect(self._tick_dugong)
        self._dugong_timer.start()

        self._world_timer = QtCore.QTimer(self)
        self._world_timer.setInterval(self._world_tick_ms)
        self._world_timer.timeout.connect(self._tick_world)
        self._world_timer.start()

        self._bg_timer = QtCore.QTimer(self)
        self._bg_timer.setInterval(self._bg_tick_ms)
        self._bg_timer.timeout.connect(self._tick_bg)
        self._bg_timer.start()

        self._layout_overlay()
        self._reset_dugong_position()
        self._update_frame(force=True)

    # -------- assets ----------
    def _load_background(self, assets_dir: Path) -> QtGui.QPixmap:
        bg = QtGui.QPixmap(str(assets_dir / "bg_ocean.png"))
        if not bg.isNull():
            return bg

        fallback = QtGui.QPixmap(1920, self._target_height)
        fallback.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(fallback)
        grad = QtGui.QLinearGradient(0, 0, 0, self._target_height)
        grad.setColorAt(0.0, QtGui.QColor(24, 72, 120, 220))
        grad.setColorAt(1.0, QtGui.QColor(6, 22, 44, 220))
        painter.fillRect(fallback.rect(), grad)
        painter.end()
        return fallback

    def _list_pngs(self, assets_dir: Path) -> list[Path]:
        return [
            path
            for path in assets_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".png"
        ]

    def _sort_with_trailing_number(self, paths: list[Path]) -> list[Path]:
        def key_fn(path: Path):
            stem = path.stem.lower()
            m = re.search(r"(\d+)$", stem)
            if m:
                return (0, int(m.group(1)), stem)
            return (1, 9999, stem)

        return sorted(paths, key=key_fn)

    def _load_pixmaps(self, paths: list[Path]) -> list[QtGui.QPixmap]:
        pixmaps: list[QtGui.QPixmap] = []
        for path in paths:
            pm = QtGui.QPixmap(str(path))
            if not pm.isNull():
                pixmaps.append(pm)
        return pixmaps

    def _load_by_prefix(self, assets_dir: Path, prefix: str) -> list[QtGui.QPixmap]:
        prefix_l = prefix.lower()
        files = [p for p in self._list_pngs(assets_dir) if p.stem.lower().startswith(prefix_l)]
        return self._load_pixmaps(self._sort_with_trailing_number(files))

    def _load_character_assets(
        self, assets_dir: Path
    ) -> tuple[dict[str, list[QtGui.QPixmap]], dict[str, list[QtGui.QPixmap]]]:
        swim = self._load_by_prefix(assets_dir, "Swim_loop")
        idle = self._load_by_prefix(assets_dir, "Idle_loop")
        turn = self._load_by_prefix(assets_dir, "Turn")

        if not swim:
            swim = self._load_by_prefix(assets_dir, "seal_")

        if not idle:
            idle = list(swim)
        if not turn:
            turn = list(swim)

        if not swim:
            raise RuntimeError("No character frames found in ui/assets (Swim_loop* or seal_*).")

        react_happy = self._load_by_prefix(assets_dir, "React_happy")
        react_chill = self._load_by_prefix(assets_dir, "React_chill")
        react_dumb = self._load_by_prefix(assets_dir, "React_dumb")
        react_shock = self._load_by_prefix(assets_dir, "React_shock")

        default_react = [idle[0] if idle else swim[0]]
        react = {
            "happy": react_happy or default_react,
            "chill": react_chill or default_react,
            "dumb": react_dumb or default_react,
            "shock": react_shock or react_dumb or default_react,
        }

        frames = {
            "swim": swim,
            "idle": idle,
            "turn": turn,
        }
        return frames, react

    # -------- geometry / layout ----------
    def _apply_screen_width(self) -> None:
        screen = QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(900, self._target_height)
            return
        geo = screen.availableGeometry()
        self.resize(max(900, geo.width()), self._target_height)

    def _scale_and_pad(self, frames: list[QtGui.QPixmap], target_h: int) -> list[QtGui.QPixmap]:
        scaled = [
            pm.scaledToHeight(max(1, target_h), QtCore.Qt.SmoothTransformation)
            for pm in frames
            if not pm.isNull()
        ]
        if not scaled:
            return []

        max_w = max(pm.width() for pm in scaled)
        max_h = max(pm.height() for pm in scaled)
        normalized: list[QtGui.QPixmap] = []

        for pm in scaled:
            canvas = QtGui.QPixmap(max_w, max_h)
            canvas.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(canvas)
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
            x = (max_w - pm.width()) // 2
            y = (max_h - pm.height()) // 2
            painter.drawPixmap(x, y, pm)
            painter.end()
            normalized.append(canvas)

        return normalized

    def _mirror_frames(self, frames: list[QtGui.QPixmap]) -> list[QtGui.QPixmap]:
        transform = QtGui.QTransform().scale(-1.0, 1.0)
        return [pm.transformed(transform) for pm in frames]

    def _rebuild_scaled_pixmaps(self) -> None:
        h = self.height()

        self._bg_scaled = self._bg_src.scaledToHeight(max(1, h), QtCore.Qt.SmoothTransformation)

        target_h = int(h * 0.36)

        right_frames = {
            key: self._scale_and_pad(frames, target_h)
            for key, frames in self._frames_raw.items()
        }
        right_reacts = {
            key: self._scale_and_pad(frames, target_h)
            for key, frames in self._react_raw.items()
        }

        self._frames_scaled["right"] = right_frames
        self._react_scaled["right"] = right_reacts

        self._frames_scaled["left"] = {
            key: self._mirror_frames(frames)
            for key, frames in right_frames.items()
        }
        self._react_scaled["left"] = {
            key: self._mirror_frames(frames)
            for key, frames in right_reacts.items()
        }

    def _layout_overlay(self) -> None:
        self._title.setGeometry(0, 8, self.width(), 26)
        self._state.setGeometry(0, self.height() - 28, self.width(), 20)

    def _place_bar(self) -> None:
        self._bar.adjustSize()
        w = self._bar.sizeHint().width()
        x = (self.width() - w) // 2
        y = self.height() - self._bar.height() - 8
        self._bar.setGeometry(x, y, w, self._bar.height())

    def _motion_bounds(self, frame: QtGui.QPixmap) -> tuple[float, float, float, float]:
        margin = 6.0
        min_x = margin
        max_x = float(max(min_x, self.width() - frame.width() - margin))
        min_y = 34.0
        max_y = float(max(min_y, self.height() - frame.height() - 52))
        return min_x, max_x, min_y, max_y

    def _pick_new_target(self, frame: QtGui.QPixmap) -> None:
        min_x, max_x, min_y, max_y = self._motion_bounds(frame)
        for _ in range(8):
            tx = random.uniform(min_x, max_x)
            ty = random.uniform(min_y, max_y)
            if math.hypot(tx - self._x, ty - self._y) > 40:
                self._target_x = tx
                self._target_y = ty
                return
        self._target_x = random.uniform(min_x, max_x)
        self._target_y = random.uniform(min_y, max_y)

    def _new_peer(self, source: str, frame: QtGui.QPixmap) -> dict[str, float | str]:
        min_x, max_x, min_y, max_y = self._motion_bounds(frame)
        x = random.uniform(min_x, max_x)
        y = random.uniform(min_y, max_y)
        target_x = random.uniform(min_x, max_x)
        target_y = random.uniform(min_y, max_y)
        vx = random.choice([-1.0, 1.0]) * random.uniform(1.1, 1.8)
        return {
            "source": source,
            "x": x,
            "y": y,
            "target_x": target_x,
            "target_y": target_y,
            "vx": vx,
            "vy": 0.0,
            "speed": random.uniform(1.0, 1.9),
            "mode": "unknown",
            "last_seen": time.time(),
            "float_phase": random.uniform(0.0, 6.28),
        }

    def set_shared_entities(
        self, entities: list[dict[str, str | float]], local_source: str | None = None
    ) -> None:
        if local_source:
            self._local_source = local_source

        current_sources: set[str] = set()
        frame = self._dugong_frame if not self._dugong_frame.isNull() else self._next_frame("swim", "right")
        if frame.isNull():
            return

        for entity in entities:
            source = str(entity.get("source", "")).strip()
            if not source or source == self._local_source:
                continue
            current_sources.add(source)

            peer = self._peer_entities.get(source)
            if peer is None:
                peer = self._new_peer(source, frame)
                self._peer_entities[source] = peer

            peer["mode"] = str(entity.get("mode", peer.get("mode", "unknown")))
            peer["last_seen"] = float(entity.get("last_seen", time.time()))

        stale = [src for src in self._peer_entities if src not in current_sources]
        for src in stale:
            self._peer_entities.pop(src, None)
            self._peer_anim_index.pop(src, None)
            self._peer_current_frame.pop(src, None)

    def _reset_dugong_position(self) -> None:
        frame = self._dugong_frame
        if frame.isNull():
            frame = self._next_frame("swim", "right")
        if frame.isNull():
            return

        min_x, max_x, min_y, max_y = self._motion_bounds(frame)
        if self._x <= 0.0 and self._y <= 0.0:
            self._x = random.uniform(min_x, max_x)
            self._y = random.uniform(min_y, max_y)
        else:
            self._x = max(min_x, min(self._x, max_x))
            self._y = max(min_y, min(self._y, max_y))
        self._pick_new_target(frame)

    def resizeEvent(self, _e: QtGui.QResizeEvent) -> None:
        self._rebuild_scaled_pixmaps()
        self._layout_overlay()
        self._reset_dugong_position()
        if self._bar.isVisible():
            self._place_bar()
        self._update_frame(force=True)
        self.update()

    def showEvent(self, e: QtGui.QShowEvent) -> None:
        self._apply_screen_width()
        super().showEvent(e)

    # -------- animation state ----------
    def _frame_list(self, anim: str, direction: str) -> list[QtGui.QPixmap]:
        if anim == "react":
            return self._react_scaled.get(direction, {}).get(self._react_kind, [])
        return self._frames_scaled.get(direction, {}).get(anim, [])

    def _safe_anim(self, anim: str, direction: str) -> str:
        if self._frame_list(anim, direction):
            return anim
        if self._frame_list("swim", direction):
            return "swim"
        if self._frame_list("idle", direction):
            return "idle"
        return "turn"

    def _next_frame(self, anim: str, direction: str) -> QtGui.QPixmap:
        safe_anim = self._safe_anim(anim, direction)
        key = f"{direction}:{safe_anim}:{self._react_kind if safe_anim == 'react' else '-'}"
        frames = self._frame_list(safe_anim, direction)
        if not frames:
            return QtGui.QPixmap()
        idx = self._anim_index.get(key, 0)
        frame = frames[idx % len(frames)]
        self._anim_index[key] = (idx + 1) % len(frames)
        return frame

    def _update_frame(self, force: bool = False) -> None:
        if self._vx > 0.35:
            direction = "right"
        elif self._vx < -0.35:
            direction = "left"
        else:
            direction = self._anim_direction
        self._anim_direction = direction

        if self._anim_mode == "react" and time.monotonic() >= self._react_until:
            self._anim_mode = "swim"

        frame = self._next_frame(self._anim_mode, direction)
        if not frame.isNull() or force:
            self._dugong_frame = frame

    def _trigger_react(self, kind: str, ms: int = 1400) -> None:
        if kind not in {"happy", "chill", "dumb", "shock"}:
            return
        direction = "right" if self._vx >= 0 else "left"
        if not self._react_scaled.get(direction, {}).get(kind):
            return
        self._react_kind = kind
        self._anim_mode = "react"
        self._react_until = time.monotonic() + max(0.3, ms / 1000.0)

    def _start_turn(self) -> None:
        self._anim_mode = "turn"
        self._turn_ticks_left = max(4, len(self._frame_list("turn", self._anim_direction)))

    def _maybe_enter_idle(self) -> None:
        if self._anim_mode != "swim":
            return
        if random.random() < 0.009:
            self._anim_mode = "idle"
            self._idle_ticks_left = random.randint(12, 30)
            self._vx = 0.0
            self._vy = 0.0

    def _step_towards_target(self, frame: QtGui.QPixmap) -> None:
        min_x, max_x, min_y, max_y = self._motion_bounds(frame)
        if not (min_x <= self._target_x <= max_x and min_y <= self._target_y <= max_y):
            self._pick_new_target(frame)

        dx = self._target_x - self._x
        dy = self._target_y - self._y
        dist = math.hypot(dx, dy)
        if dist < 10:
            self._pick_new_target(frame)
            if self._anim_mode == "swim" and random.random() < 0.28:
                self._anim_mode = "idle"
                self._idle_ticks_left = random.randint(10, 24)
                self._vx = 0.0
                self._vy = 0.0
            return

        old_sign = 1 if self._vx >= 0 else -1
        speed = self._swim_speed * (0.75 if self._anim_mode == "turn" else 1.0)
        self._vx = (dx / dist) * speed
        self._vy = (dy / dist) * speed

        if abs(self._vx) < 0.06:
            self._vx = 0.06 if dx >= 0 else -0.06

        new_sign = 1 if self._vx >= 0 else -1
        if (
            new_sign != old_sign
            and self._anim_mode == "swim"
            and abs(self._vx) > 0.35
        ):
            self._start_turn()

        self._x += self._vx
        self._y += self._vy

        clamped = False
        if self._x < min_x:
            self._x = min_x
            clamped = True
        elif self._x > max_x:
            self._x = max_x
            clamped = True

        if self._y < min_y:
            self._y = min_y
            clamped = True
        elif self._y > max_y:
            self._y = max_y
            clamped = True

        if clamped:
            self._pick_new_target(frame)

        self._float_phase += 0.20
        self._y += math.sin(self._float_phase) * 0.25

    def _step_peer_towards_target(self, frame: QtGui.QPixmap, peer: dict[str, float | str]) -> None:
        min_x, max_x, min_y, max_y = self._motion_bounds(frame)
        x = float(peer.get("x", min_x))
        y = float(peer.get("y", min_y))
        target_x = float(peer.get("target_x", x))
        target_y = float(peer.get("target_y", y))
        vx = float(peer.get("vx", 1.0))
        old_sign = 1 if vx >= 0 else -1

        if not (min_x <= target_x <= max_x and min_y <= target_y <= max_y):
            target_x = random.uniform(min_x, max_x)
            target_y = random.uniform(min_y, max_y)

        dx = target_x - x
        dy = target_y - y
        dist = math.hypot(dx, dy)
        if dist < 14:
            target_x = random.uniform(min_x, max_x)
            target_y = random.uniform(min_y, max_y)
            dx = target_x - x
            dy = target_y - y
            dist = max(0.1, math.hypot(dx, dy))

        speed = float(peer.get("speed", 1.4))
        vx = (dx / dist) * speed
        vy = (dy / dist) * speed
        if abs(vx) < 0.05:
            vx = 0.05 if dx >= 0 else -0.05

        x += vx
        y += vy

        if x < min_x:
            x = min_x
            target_x = random.uniform(min_x, max_x)
            target_y = random.uniform(min_y, max_y)
        elif x > max_x:
            x = max_x
            target_x = random.uniform(min_x, max_x)
            target_y = random.uniform(min_y, max_y)

        if y < min_y:
            y = min_y
            target_x = random.uniform(min_x, max_x)
            target_y = random.uniform(min_y, max_y)
        elif y > max_y:
            y = max_y
            target_x = random.uniform(min_x, max_x)
            target_y = random.uniform(min_y, max_y)

        phase = float(peer.get("float_phase", 0.0)) + 0.12
        y += math.sin(phase) * 0.2

        peer["x"] = x
        peer["y"] = y
        peer["target_x"] = target_x
        peer["target_y"] = target_y
        peer["vx"] = vx
        peer["vy"] = vy
        peer["float_phase"] = phase
        old_facing = str(peer.get("facing", "right"))
        if vx > 0.28:
            facing = "right"
        elif vx < -0.28:
            facing = "left"
        else:
            facing = old_facing
        peer["facing"] = facing
        peer["turning"] = 1.0 if (1 if vx >= 0 else -1) != old_sign else 0.0

    def _next_peer_frame(self, source: str, direction: str) -> QtGui.QPixmap:
        frames = self._frame_list("swim", direction)
        if not frames:
            frames = self._frame_list("idle", direction)
        if not frames:
            return QtGui.QPixmap()
        idx = self._peer_anim_index.get(source, 0)
        frame = frames[idx % len(frames)]
        self._peer_anim_index[source] = (idx + 1) % len(frames)
        return frame

    def _tick_dugong(self) -> None:
        self._update_frame()
        for source, peer in self._peer_entities.items():
            direction = str(peer.get("facing", "right"))
            if direction not in {"left", "right"}:
                direction = "right"
            pm = self._next_peer_frame(source, direction)
            if not pm.isNull():
                self._peer_current_frame[source] = pm
        self.update()

    def _tick_world(self) -> None:
        current = self._dugong_frame
        if current.isNull():
            return

        if self._anim_mode == "react":
            if time.monotonic() >= self._react_until:
                self._anim_mode = "swim"
        elif self._anim_mode == "turn":
            self._turn_ticks_left -= 1
            if self._turn_ticks_left <= 0:
                self._anim_mode = "swim"
        elif self._anim_mode == "idle":
            self._idle_ticks_left -= 1
            if self._idle_ticks_left <= 0:
                self._anim_mode = "swim"
                self._pick_new_target(current)
        else:
            self._maybe_enter_idle()

        if self._anim_mode in {"swim", "turn"}:
            self._step_towards_target(current)

        for peer in self._peer_entities.values():
            self._step_peer_towards_target(current, peer)

        self.update()

    def _tick_bg(self) -> None:
        if not self._bg_scaled:
            return
        bg_w = self._bg_scaled.width()
        if bg_w <= 0:
            return
        self._bg_offset = (self._bg_offset + self._bg_speed_px) % bg_w
        self.update()

    def _draw_name_tag(
        self,
        painter: QtGui.QPainter,
        x: int,
        y: int,
        source: str,
        *,
        is_local: bool,
        anchor_w: int,
        anchor_h: int,
    ) -> None:
        raw = (source or "").strip()
        if not raw:
            return
        text = raw if len(raw) <= 14 else f"{raw[:13]}…"

        font = QtGui.QFont("Segoe UI", 8 if not is_local else 9, QtGui.QFont.DemiBold)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        pad_x = 8
        pad_y = 3
        text_w = metrics.horizontalAdvance(text)
        text_h = metrics.height()
        w = text_w + (pad_x * 2)
        h = text_h + (pad_y * 2)
        rx = x + max(0, (anchor_w - w) // 2)
        # PNG has transparent top padding; anchor label closer to visible head area.
        head_anchor_y = y + int(anchor_h * 0.10)
        ry = head_anchor_y - h - 1

        bg = QtGui.QColor(21, 42, 66, 190) if is_local else QtGui.QColor(26, 58, 92, 168)
        border = QtGui.QColor(169, 225, 255, 180) if is_local else QtGui.QColor(150, 200, 235, 140)
        fg = QtGui.QColor(245, 251, 255, 240)

        painter.setPen(QtGui.QPen(border, 1))
        painter.setBrush(QtGui.QBrush(bg))
        painter.drawRoundedRect(rx, ry, w, h, 8, 8)
        painter.setPen(QtGui.QPen(fg))
        painter.drawText(rx + pad_x, ry + pad_y + metrics.ascent(), text)

    # -------- paint ----------
    def paintEvent(self, _e: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)

        if self._bg_scaled:
            bg = self._bg_scaled
            bg_w = bg.width()
            off = int(self._bg_offset)
            x = -off
            while x < self.width():
                painter.drawPixmap(x, 0, bg)
                x += bg_w

        if not self._dugong_frame.isNull():
            painter.drawPixmap(int(self._x), int(self._y), self._dugong_frame)
            self._draw_name_tag(
                painter,
                int(self._x),
                int(self._y),
                self._local_source,
                is_local=True,
                anchor_w=self._dugong_frame.width(),
                anchor_h=self._dugong_frame.height(),
            )

        for source, peer in sorted(self._peer_entities.items(), key=lambda x: x[0]):
            pm = self._peer_current_frame.get(source)
            if pm is None or pm.isNull():
                direction = str(peer.get("facing", "right"))
                if direction not in {"left", "right"}:
                    direction = "right"
                pm = self._next_peer_frame(source, direction)
                if not pm.isNull():
                    self._peer_current_frame[source] = pm
            if pm.isNull():
                continue
            x = int(float(peer.get("x", 0.0)))
            y = int(float(peer.get("y", 0.0)))
            painter.drawPixmap(x, y, pm)
            self._draw_name_tag(
                painter,
                x,
                y,
                source,
                is_local=False,
                anchor_w=pm.width(),
                anchor_h=pm.height(),
            )

    # -------- hover bar ----------
    def enterEvent(self, _e: QtCore.QEvent) -> None:
        self._hide_bar_timer.stop()
        self._place_bar()
        self._bar.show()
        self._bar.raise_()

    def leaveEvent(self, _e: QtCore.QEvent) -> None:
        self._hide_bar_timer.start(180)

    # -------- drag + click ----------
    def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.button() == QtCore.Qt.LeftButton:
            self._dragging = True
            self._drag_moved = False
            self._press_global = e.globalPosition().toPoint()
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent) -> None:
        if self._dragging:
            if (e.globalPosition().toPoint() - self._press_global).manhattanLength() > 4:
                self._drag_moved = True
            self.move(e.globalPosition().toPoint() - self._drag_offset)
            e.accept()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.button() == QtCore.Qt.LeftButton:
            self._dragging = False
            if not self._drag_moved:
                try:
                    self._on_click()
                except Exception:
                    pass
            e.accept()

    # -------- controller hooks ----------
    def set_state_text(self, text: str) -> None:
        self._state.setText(text)

        m = re.search(r"\[([^\]]+)\]", text)
        if not m:
            return

        mode = m.group(1).strip().lower()
        if mode == self._last_mode:
            return
        self._last_mode = mode

        if mode == "rest":
            self._anim_mode = "idle"
            self._idle_ticks_left = max(self._idle_ticks_left, 30)

    def apply_sprite_hint(self, sprite: str) -> None:
        _ = sprite

    def show_bubble(self, text: str, ms: int = 2500) -> None:
        self._bubble.setText(text)
        self._bubble.adjustSize()
        bw = min(self.width() - 40, max(220, self._bubble.width()))
        self._bubble.setFixedWidth(bw)
        self._bubble.adjustSize()
        self._bubble.move((self.width() - self._bubble.width()) // 2, int(self.height() * 0.60))
        self._bubble.show()
        self._bubble.raise_()
        self._bubble_timer.start(ms)

    def _emit_mode(self, mode: str) -> None:
        self._on_mode_change(mode)

    def _emit_ping(self) -> None:
        if self._on_manual_ping is not None:
            self._on_manual_ping("checkin")

    def _emit_sync(self) -> None:
        if self._on_sync_now is not None:
            self._on_sync_now()

    def _emit_quit(self) -> None:
        self.close()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()

    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:
        if e.key() == QtCore.Qt.Key_Escape:
            self._emit_quit()
            e.accept()
            return
        super().keyPressEvent(e)
