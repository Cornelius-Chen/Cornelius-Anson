from __future__ import annotations

import json

import math
import random
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
try:
    from PySide6 import QtMultimedia
except Exception:
    QtMultimedia = None


class DugongShell:
    def __init__(
        self,
        on_mode_change: Callable[[str], None],
        on_click: Callable[[], None],
        on_manual_ping: Callable[[str], None] | None = None,
        on_sync_now: Callable[[], None] | None = None,
        on_pomo_start: Callable[[], None] | None = None,
        on_pomo_pause_resume: Callable[[], None] | None = None,
        on_pomo_skip: Callable[[], None] | None = None,
        on_shop_action: Callable[[str, str, int], None] | None = None,
        on_quit: Callable[[], None] | None = None,
        source_id: str = "local",
        skin_id: str = "default",
    ) -> None:
        self._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self._win = _DugongWindow(
            on_mode_change,
            on_click,
            on_manual_ping,
            on_sync_now,
            on_pomo_start,
            on_pomo_pause_resume,
            on_pomo_skip,
            on_shop_action,
            on_quit,
            source_id=source_id,
            skin_id=skin_id,
        )

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
        pomo_text: str | None = None,
        pomo_state: str | None = None,
        reward_stats: dict[str, int | str] | None = None,
        local_profile: dict[str, str | int] | None = None,
        bubble: str | None = None,
        entities: list[dict[str, str | float]] | None = None,
        local_source: str | None = None,
    ) -> None:
        self._win.set_state_text(state_text)
        if pomo_text is not None:
            self._win.set_pomo_text(pomo_text)
        if pomo_state is not None:
            self._win.set_pomo_state(pomo_state)
        if reward_stats is not None:
            self._win.set_reward_stats(reward_stats)
        if local_profile is not None:
            self._win.set_local_profile(local_profile)
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
        on_pomo_start: Callable[[], None] | None,
        on_pomo_pause_resume: Callable[[], None] | None,
        on_pomo_skip: Callable[[], None] | None,
        on_shop_action: Callable[[str, str, int], None] | None,
        on_quit: Callable[[], None] | None,
        source_id: str = "local",
        skin_id: str = "default",
    ) -> None:
        super().__init__()
        self._on_mode_change = on_mode_change
        self._on_click = on_click
        self._on_manual_ping = on_manual_ping
        self._on_sync_now = on_sync_now
        self._on_pomo_start = on_pomo_start
        self._on_pomo_pause_resume = on_pomo_pause_resume
        self._on_pomo_skip = on_pomo_skip
        self._on_shop_action = on_shop_action
        self._on_quit = on_quit
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
        self._compact_mode = False
        self._compact_width = 420
        self._apply_screen_width()

        self._dragging = False
        self._drag_moved = False
        self._press_global = QtCore.QPoint(0, 0)
        self._drag_offset = QtCore.QPoint(0, 0)

        self._assets_root = Path(__file__).resolve().parent / "assets"
        self._skin_root = self._assets_root / "dugong_skin"
        self._is_muted = False
        self._mode_sound_players: dict[str, object] = {}
        self._mode_audio_outputs: dict[str, object] = {}
        self._mode_sound_files: dict[str, Path] = {}
        self._mode_sound_play_paths: dict[str, Path] = {}
        self._init_mode_sounds()
        self._skin_id = self._resolve_skin_id(self._local_source, skin_id)
        self._local_skin_assets_dir = self._resolve_skin_assets_dir(self._skin_root, self._skin_id)
        self._peer_skin_assets_dir = self._resolve_skin_assets_dir(self._skin_root, "default")
        self._bg_src = self._load_background(self._local_skin_assets_dir)
        self._local_frames_raw, self._local_react_raw = self._load_character_assets(self._local_skin_assets_dir)
        self._peer_frames_raw, self._peer_react_raw = self._load_character_assets(self._peer_skin_assets_dir)

        self._anim_mode = "swim"  # swim | idle | turn | react
        self._react_kind = "chill"  # study | chill | rest (with legacy aliases)
        self._react_until = 0.0
        self._anim_direction = "right"
        self._anim_index: dict[str, int] = {}

        self._last_mode = ""
        self._pomo_state = "IDLE"
        self._last_pomo_state = "IDLE"
        self._state_text_raw = ""
        self._local_profile: dict[str, str | int] = {}
        self._hover_pos = QtCore.QPoint(-1, -1)
        self._pearls_total = 0
        self._lifetime_pearls = 0
        self._today_pearls = 0
        self._focus_streak = 0
        self._day_streak = 0
        self._equipped_title_id = "drifter"
        self._equipped_bubble_style = "default"
        self._equipped_skin_id = self._skin_id
        self._owned_skins: set[str] = {"default"}
        self._owned_bubbles: set[str] = {"default"}
        self._owned_titles: set[str] = {"drifter"}
        self._floating_rewards: list[dict[str, float | str]] = []
        self._shop_dialog: QtWidgets.QDialog | None = None
        self._shop_hint_label: QtWidgets.QLabel | None = None
        self._shop_scale = 0.5
        self._shop_manual_pos: QtCore.QPoint | None = None
        self._shop_edge_hold_ms = 220
        self._shop_edge_pressing = False
        self._shop_edge_drag_ready = False
        self._shop_edge_dragging = False
        self._shop_drag_offset = QtCore.QPoint(0, 0)
        self._shop_drag_dlg: QtWidgets.QDialog | None = None
        self._shop_edge_hold_timer = QtCore.QTimer(self)
        self._shop_edge_hold_timer.setSingleShot(True)
        self._shop_edge_hold_timer.timeout.connect(self._enable_shop_edge_drag)
        self._did_initial_center = False

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
        self._turn_target_direction = ""
        self._turn_cooldown_until = 0.0

        self._dugong_anim_ms = 130
        self._world_tick_ms = 28
        self._bg_tick_ms = 30
        self._bg_speed_px = 0.7
        self._bg_offset = 0.0

        self._bg_scaled: QtGui.QPixmap | None = None
        self._local_frames_scaled: dict[str, dict[str, list[QtGui.QPixmap]]] = {"right": {}, "left": {}}
        self._local_react_scaled: dict[str, dict[str, list[QtGui.QPixmap]]] = {"right": {}, "left": {}}
        self._rebuild_scaled_pixmaps()

        self._title = QtWidgets.QLabel("Dugong", self)
        self._title.setStyleSheet("color: rgba(255,255,255,210); font-size: 18px; font-weight: 700;")
        self._title.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

        self._pearl = QtWidgets.QLabel("Pearls 0 (+0 today)", self)
        self._pearl.setAlignment(QtCore.Qt.AlignCenter)
        self._pearl.setFixedHeight(22)
        self._pearl.setMinimumWidth(170)
        self._pearl.setStyleSheet(
            """
            QLabel {
                color: rgba(242,252,255,245);
                background: rgba(23,58,88,205);
                border: 1px solid rgba(150,210,240,180);
                border-radius: 11px;
                font-size: 12px;
                font-weight: 700;
                padding: 0 10px;
            }
            """
        )

        self._state = QtWidgets.QLabel("state", self)
        self._state.setStyleSheet("color: rgba(255,255,255,210); font-size: 14px;")
        self._state.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
        self._state.hide()

        self._pomo = QtWidgets.QLabel("POMO IDLE", self)
        self._pomo.setAlignment(QtCore.Qt.AlignCenter)
        self._pomo.setFixedHeight(22)
        self._pomo.setMinimumWidth(170)
        self._apply_pomo_chip_style("IDLE")

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
        self._bubble_tail = QtWidgets.QLabel(self)
        self._bubble_tail.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self._bubble_tail.hide()
        self._bubble_timer = QtCore.QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self._hide_bubble_widgets)

        self._focus_strip = QtWidgets.QFrame(self)
        self._focus_strip.setStyleSheet(
            "background: rgba(10,18,28,195); border: 1px solid rgba(130,190,230,120); border-radius: 9px;"
        )
        self._focus_strip.setFixedHeight(38)
        flay = QtWidgets.QHBoxLayout(self._focus_strip)
        # Keep vertical padding symmetric and avoid clipping inside framed content rect.
        flay.setContentsMargins(8, 4, 8, 4)
        flay.setSpacing(6)
        flay.setAlignment(QtCore.Qt.AlignCenter)

        self._drawer = QtWidgets.QFrame(self)
        self._drawer.setStyleSheet("background: rgba(9,18,28,220); border-radius: 12px;")
        self._drawer.setFixedWidth(210)
        self._drawer_open = False
        self._drawer_anim = QtCore.QPropertyAnimation(self._drawer, b"geometry", self)
        self._drawer_anim.setDuration(180)
        self._drawer_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._drawer_anim.finished.connect(self._on_drawer_anim_finished)
        self._drawer.hide()

        self._drawer_toggle = QtWidgets.QPushButton("menu", self)
        self._drawer_toggle.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._drawer_toggle.setStyleSheet(
            """
            QPushButton {
                color: rgba(235,245,255,240);
                background: rgba(14,36,58,210);
                border: 1px solid rgba(130,190,230,150);
                border-radius: 9px;
                font-size: 12px;
                font-weight: 700;
                padding: 4px 10px;
            }
            """
        )
        self._drawer_toggle.clicked.connect(self._toggle_drawer)

        self._quit_top = QtWidgets.QPushButton("", self)
        self._quit_top.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._quit_top.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogCloseButton))
        self._quit_top.setIconSize(QtCore.QSize(14, 14))
        self._quit_top.setFixedSize(24, 24)
        self._quit_top.setStyleSheet(
            """
            QPushButton {
                color: rgba(245,250,255,240);
                background: rgba(32,52,74,215);
                border: 1px solid rgba(150,190,230,140);
                border-radius: 8px;
            }
            """
        )
        self._quit_top.clicked.connect(self._emit_quit)

        self._size_mode_top = QtWidgets.QPushButton("小", self)
        self._size_mode_top.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._size_mode_top.setFixedSize(24, 24)
        self._size_mode_top.setStyleSheet(
            """
            QPushButton {
                color: rgba(245,250,255,240);
                background: rgba(32,52,74,215);
                border: 1px solid rgba(150,190,230,140);
                border-radius: 8px;
                font-size: 11px;
                font-weight: 700;
            }
            """
        )
        self._size_mode_top.clicked.connect(self._toggle_size_mode)

        def mk_btn(
            text: str,
            color: str,
            fn: Callable[[], None],
            icon: QtWidgets.QStyle.StandardPixmap | None = None,
        ) -> QtWidgets.QPushButton:
            b = QtWidgets.QPushButton(text)
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            b.setStyleSheet(
                f"""
                QPushButton {{
                    color: white;
                    background: {color};
                    border: none;
                    padding: 2px 8px;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 12px;
                }}
            """
            )
            if icon is not None:
                b.setIcon(self.style().standardIcon(icon))
                b.setIconSize(QtCore.QSize(14, 14))
            b.setMinimumWidth(56)
            b.setFixedHeight(28)
            b.clicked.connect(fn)
            return b

        self._pomo_toggle = mk_btn("start", "#7b3f00", self._emit_pomo_toggle)
        self._pomo_toggle.setMinimumWidth(96)
        flay.addWidget(self._pomo_toggle)
        self._pomo_skip_btn = mk_btn("skip", "#874321", self._emit_pomo_skip)
        self._pomo_skip_btn.setMinimumWidth(80)
        flay.addWidget(self._pomo_skip_btn)

        dlay = QtWidgets.QVBoxLayout(self._drawer)
        dlay.setContentsMargins(8, 8, 8, 8)
        dlay.setSpacing(6)

        self._drawer_tabs = QtWidgets.QTabWidget(self._drawer)
        self._drawer_tabs.setDocumentMode(True)
        self._drawer_tabs.setElideMode(QtCore.Qt.ElideRight)
        self._drawer_tabs.setStyleSheet(
            """
            QTabWidget::pane {
                border: 1px solid rgba(100,150,190,90);
                border-radius: 8px;
                background: rgba(7,16,26,145);
            }
            QTabBar::tab {
                color: rgba(220,238,252,230);
                background: rgba(17,39,62,175);
                border: 1px solid rgba(100,150,190,80);
                border-bottom: none;
                min-width: 42px;
                padding: 3px 6px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 11px;
                font-weight: 700;
            }
            QTabBar::tab:selected {
                background: rgba(34,74,108,215);
            }
            """
        )

        def mk_page(buttons: list[QtWidgets.QPushButton]) -> QtWidgets.QWidget:
            page = QtWidgets.QWidget(self._drawer_tabs)
            lay = QtWidgets.QVBoxLayout(page)
            lay.setContentsMargins(8, 8, 8, 8)
            lay.setSpacing(6)
            for b in buttons:
                lay.addWidget(b)
            lay.addStretch(1)
            return page

        modes_page = mk_page(
            [
                mk_btn("专注", "#1d3a57", lambda: self._emit_mode("study")),
                mk_btn("放松", "#1d3a57", lambda: self._emit_mode("chill")),
                mk_btn("休息", "#1d3a57", lambda: self._emit_mode("rest")),
            ]
        )
        economy_page = mk_page(
            [
                mk_btn("shop", "#36577a", self._emit_shop),
                mk_btn("wardrobe", "#3f5d7b", self._emit_wardrobe),
            ]
        )
        network_page = mk_page(
            [
                mk_btn("ping", "#275e44", self._emit_ping),
                mk_btn("sync", "#6b4f1f", self._emit_sync),
            ]
        )
        self._mute_btn = mk_btn("mute: off", "#4f4f4f", self._toggle_mute)
        system_page = mk_page([self._mute_btn, mk_btn("quit", "#6a2c2c", self._emit_quit)])

        self._drawer_tabs.addTab(modes_page, "M")
        self._drawer_tabs.addTab(economy_page, "E")
        self._drawer_tabs.addTab(network_page, "N")
        self._drawer_tabs.addTab(system_page, "S")
        dlay.addWidget(self._drawer_tabs, 1)
        self._update_pomo_toggle_label(self._pomo_state)

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
    def _init_mode_sounds(self) -> None:
        sound_dir = self._assets_root / "sound"
        mode_to_file = {
            "study": "skeleton.mp3",
            "chill": "pvz.mp3",
            "rest": "mc.mp3",
        }
        for mode, filename in mode_to_file.items():
            path = sound_dir / filename
            if not path.exists():
                continue
            self._mode_sound_files[mode] = path
            if QtMultimedia is None:
                continue
            try:
                audio = QtMultimedia.QAudioOutput(self)
                audio.setVolume(0.85)
                audio.setMuted(self._is_muted)
                player = QtMultimedia.QMediaPlayer(self)
                player.setAudioOutput(audio)
                player.setSource(QtCore.QUrl.fromLocalFile(str(path)))
                self._mode_audio_outputs[mode] = audio
                self._mode_sound_players[mode] = player
            except Exception:
                continue

    def _play_mode_sound(self, mode: str) -> None:
        if self._is_muted:
            return
        player = self._mode_sound_players.get(mode)
        if player is not None:
            try:
                player.setPosition(0)
                player.play()
                return
            except Exception:
                pass
        sound_path = self._mode_sound_files.get(mode)
        if sound_path is not None:
            self._play_mode_sound_fallback(sound_path)

    def _play_mode_sound_fallback(self, sound_path: Path) -> None:
        if not sound_path.exists():
            return
        try:
            if sys.platform == "darwin":
                play_path = self._mac_playable_path(sound_path)
                subprocess.Popen(["afplay", str(play_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            if sys.platform.startswith("win"):
                escaped = str(sound_path).replace("\\", "\\\\").replace("'", "''")
                ps = (
                    "Add-Type -AssemblyName presentationCore; "
                    "$p = New-Object System.Windows.Media.MediaPlayer; "
                    f"$p.Open([Uri]'{escaped}'); "
                    "$p.Volume = 1.0; "
                    "$p.Play(); "
                    "Start-Sleep -Milliseconds 3000; "
                    "$p.Close();"
                )
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command", ps],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
        except Exception:
            pass

    def _mac_playable_path(self, sound_path: Path) -> Path:
        key = str(sound_path.resolve())
        cached = self._mode_sound_play_paths.get(key)
        if cached is not None and cached.exists():
            return cached
        if sound_path.suffix.lower() != ".mp3":
            self._mode_sound_play_paths[key] = sound_path
            return sound_path
        try:
            tmp_dir = Path(tempfile.gettempdir()) / "dugong_sound_cache"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            play_path = tmp_dir / f"{sound_path.stem}.m4a"
            play_path.write_bytes(sound_path.read_bytes())
            self._mode_sound_play_paths[key] = play_path
            return play_path
        except Exception:
            self._mode_sound_play_paths[key] = sound_path
            return sound_path

    def _toggle_mute(self) -> None:
        self._is_muted = not self._is_muted
        for audio in self._mode_audio_outputs.values():
            try:
                audio.setMuted(self._is_muted)
            except Exception:
                continue
        label = "mute: on" if self._is_muted else "mute: off"
        color = "#6a2c2c" if self._is_muted else "#4f4f4f"
        self._mute_btn.setText(label)
        self._mute_btn.setStyleSheet(
            f"""
            QPushButton {{
                color: white;
                background: {color};
                border: none;
                padding: 2px 8px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
            }}
            """
        )

    def _resolve_skin_id(self, source_id: str, requested_skin_id: str) -> str:
        requested = (requested_skin_id or "").strip()
        if requested and requested.lower() != "auto":
            return requested

        mapping_file = self._skin_root / "skin_map.json"
        default_skin = "default"
        try:
            if mapping_file.exists():
                # Use utf-8-sig to tolerate BOM produced by some editors/PowerShell.
                data = json.loads(mapping_file.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    default_skin = str(data.get("default_skin", default_skin)).strip() or default_skin
                    source_to_skin = data.get("source_to_skin", {})
                    if isinstance(source_to_skin, dict):
                        sid = (source_id or "").strip().lower()
                        for raw_key, raw_skin in source_to_skin.items():
                            if str(raw_key).strip().lower() == sid:
                                mapped = str(raw_skin).strip()
                                if mapped:
                                    return mapped
        except Exception:
            # Keep startup resilient even if mapping file is malformed.
            pass
        return default_skin

    def _resolve_skin_assets_dir(self, skin_root: Path, skin_id: str) -> Path:
        # Priority:
        # 1) assets/dugong_skin/<skin_id>/
        # 2) assets/dugong_skin/default/
        # 3) assets/default/ (legacy)
        # 4) assets/ (legacy flat layout)
        candidate = skin_root / skin_id
        if candidate.exists() and candidate.is_dir():
            return candidate
        fallback_default = skin_root / "default"
        if fallback_default.exists() and fallback_default.is_dir():
            return fallback_default
        legacy_default = self._assets_root / "default"
        if legacy_default.exists() and legacy_default.is_dir():
            return legacy_default
        return self._assets_root

    def _load_background(self, assets_dir: Path) -> QtGui.QPixmap:
        bg = QtGui.QPixmap(str(assets_dir / "bg_ocean.png"))
        if bg.isNull() and assets_dir != self._assets_root:
            bg = QtGui.QPixmap(str(self._assets_root / "bg_ocean.png"))
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
        if not assets_dir.exists():
            return []
        files = [
            path
            for path in assets_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".png"
        ]
        if files:
            return files
        if assets_dir != self._assets_root and self._assets_root.exists():
            return [
                path
                for path in self._assets_root.iterdir()
                if path.is_file() and path.suffix.lower() == ".png"
            ]
        return files

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

        react_study = self._load_by_prefix(assets_dir, "React_study")
        react_chill = self._load_by_prefix(assets_dir, "React_chill")
        react_rest = self._load_by_prefix(assets_dir, "React_rest")

        # Legacy aliases (older naming)
        react_happy = self._load_by_prefix(assets_dir, "React_happy")
        react_dumb = self._load_by_prefix(assets_dir, "React_dumb")
        react_shock = self._load_by_prefix(assets_dir, "React_shock")

        default_react = [idle[0] if idle else swim[0]]
        react = {
            # Current mode-based keys
            "study": react_study or react_shock or react_dumb or default_react,
            "chill": react_chill or default_react,
            "rest": react_rest or react_happy or default_react,
            # Legacy keys kept for compatibility
            "happy": react_happy or react_rest or default_react,
            "dumb": react_dumb or react_study or default_react,
            "shock": react_shock or react_study or react_dumb or default_react,
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
        if self._compact_mode:
            # Small-window mode: keep it close to character-card size, not full-width strip.
            width = max(340, min(self._compact_width, int(geo.width() * 0.72)))
        else:
            width = max(900, geo.width())
        self.resize(width, self._target_height)
        if self.x() < geo.left():
            self.move(geo.left(), self.y())
        if self.x() + self.width() > geo.right():
            self.move(max(geo.left(), geo.right() - self.width()), self.y())

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

    def _build_scaled_bundle(
        self,
        frames_raw: dict[str, list[QtGui.QPixmap]],
        react_raw: dict[str, list[QtGui.QPixmap]],
        target_h: int,
    ) -> tuple[dict[str, dict[str, list[QtGui.QPixmap]]], dict[str, dict[str, list[QtGui.QPixmap]]]]:
        right_frames = {
            key: self._scale_and_pad(frames, target_h)
            for key, frames in frames_raw.items()
        }
        right_reacts = {
            key: self._scale_and_pad(frames, target_h)
            for key, frames in react_raw.items()
        }
        frames_scaled = {
            "right": right_frames,
            "left": {key: self._mirror_frames(frames) for key, frames in right_frames.items()},
        }
        reacts_scaled = {
            "right": right_reacts,
            "left": {key: self._mirror_frames(frames) for key, frames in right_reacts.items()},
        }
        return frames_scaled, reacts_scaled

    def _peer_set_skin(self, peer: dict[str, float | str], skin_id: str, target_h: int) -> None:
        skin_assets_dir = self._resolve_skin_assets_dir(self._skin_root, skin_id)
        peer_frames_raw, peer_react_raw = self._load_character_assets(skin_assets_dir)
        frames_scaled, reacts_scaled = self._build_scaled_bundle(peer_frames_raw, peer_react_raw, target_h)
        peer["skin_id"] = skin_id
        peer["frames_scaled"] = frames_scaled
        peer["react_scaled"] = reacts_scaled
        if not str(peer.get("react_kind", "")).strip():
            peer["react_kind"] = "chill"
        if "react_until" not in peer:
            peer["react_until"] = 0.0

    def _rebuild_scaled_pixmaps(self) -> None:
        h = self.height()

        self._bg_scaled = self._bg_src.scaledToHeight(max(1, h), QtCore.Qt.SmoothTransformation)

        target_h = int(h * 0.36)

        self._local_frames_scaled, self._local_react_scaled = self._build_scaled_bundle(
            self._local_frames_raw,
            self._local_react_raw,
            target_h,
        )
        for peer in self._peer_entities.values():
            skin_id = str(peer.get("skin_id", "default")) or "default"
            self._peer_set_skin(peer, skin_id, target_h)

    def _layout_overlay(self) -> None:
        self._quit_top.move(8, 8)
        self._quit_top.raise_()
        self._size_mode_top.move(36, 8)
        self._size_mode_top.raise_()

        if self._compact_mode:
            self._title.hide()
            chip_w = max(138, min(190, self._pomo.sizeHint().width() + 10))
            self._pomo.setGeometry(self.width() - chip_w - 8, 8, chip_w, 22)

            self._focus_strip.adjustSize()
            focus_w = self._focus_strip.sizeHint().width() + 2
            focus_h = self._focus_strip.height()
            focus_x = self.width() - focus_w - 8
            focus_y = self._pomo.y() + self._pomo.height() + 4
            self._focus_strip.setGeometry(focus_x, focus_y, focus_w, focus_h)

            pearl_w = max(170, min(self.width() - 16, self._pearl.sizeHint().width() + 12))
            self._pearl.setGeometry(8, self.height() - 30, pearl_w, 22)
            self._drawer_toggle.setFixedSize(56, 24)
        else:
            self._title.show()
            self._title.setGeometry(0, 8, self.width(), 26)
            pearl_w = max(170, min(320, self._pearl.sizeHint().width() + 16))
            self._pearl.setGeometry(66, 10, pearl_w, 22)
            chip_w = max(170, min(280, self._pomo.sizeHint().width() + 16))
            x = self.width() - chip_w - 14
            self._pomo.setGeometry(x, 10, chip_w, 22)
            self._focus_strip.adjustSize()
            focus_w = self._focus_strip.sizeHint().width() + 2
            focus_h = self._focus_strip.height()
            focus_x = max(14, x - focus_w - 8)
            focus_y = max(6, self._pomo.y() - 4)
            self._focus_strip.setGeometry(focus_x, focus_y, focus_w, focus_h)
            self._drawer_toggle.setFixedSize(62, 28)

        self._place_drawer(animated=False)

    def _toggle_size_mode(self) -> None:
        self._compact_mode = not self._compact_mode
        self._size_mode_top.setText("大" if self._compact_mode else "小")
        screen = QtGui.QGuiApplication.primaryScreen()
        old_geo = self.geometry()
        self._apply_screen_width()
        if screen is not None:
            sg = screen.availableGeometry()
            if self._compact_mode:
                self.move(
                    max(sg.left(), sg.left() + 10),
                    max(sg.top(), sg.top() + 10),
                )
            else:
                cx = old_geo.x() + (old_geo.width() // 2)
                nx = cx - (self.width() // 2)
                nx = max(sg.left(), min(sg.right() - self.width(), nx))
                ny = max(sg.top(), min(sg.bottom() - self.height(), self.y()))
                self.move(nx, ny)
        self._rebuild_scaled_pixmaps()
        self._update_pearl_text()
        self._layout_overlay()
        self._reset_dugong_position()
        self._update_frame(force=True)
        self.update()

    def _update_pearl_text(self) -> None:
        if self._compact_mode:
            self._pearl.setText(
                f"P {self._pearls_total}  +{self._today_pearls}  L {self._lifetime_pearls}  S{self._focus_streak} D{self._day_streak}"
            )
        else:
            self._pearl.setText(
                f"Pearls {self._pearls_total} (+{self._today_pearls} today) | Life {self._lifetime_pearls} | S{self._focus_streak} D{self._day_streak}"
            )

    def _drawer_closed_rect(self) -> QtCore.QRect:
        margin = 10
        toggle = self._drawer_toggle.geometry()
        h = min(self.height() - 48, 248)
        w = self._drawer.width()
        top = max(34, self.height() - h - (toggle.height() + 12))
        left = self.width() - margin
        return QtCore.QRect(left, top, w, h)

    def _drawer_open_rect(self) -> QtCore.QRect:
        closed = self._drawer_closed_rect()
        margin = 10
        return QtCore.QRect(self.width() - closed.width() - margin, closed.y(), closed.width(), closed.height())

    def _place_drawer(self, animated: bool) -> None:
        if self._drawer_anim.state() == QtCore.QAbstractAnimation.Running:
            self._drawer_anim.stop()
        target = self._drawer_open_rect() if self._drawer_open else self._drawer_closed_rect()
        tw = self._drawer_toggle.width()
        th = self._drawer_toggle.height()
        if self._drawer_open:
            toggle_x = max(10, target.x() - tw - 8)
            toggle_y = target.y()
        else:
            toggle_x = self.width() - tw - 10
            toggle_y = self.height() - th - 10
        self._drawer_toggle.setGeometry(toggle_x, toggle_y, tw, th)

        if self._drawer_open:
            if self._drawer.isHidden():
                self._drawer.setGeometry(self._drawer_closed_rect())
            self._drawer.show()
        self._drawer.raise_()
        self._drawer_toggle.raise_()
        if animated:
            self._drawer_anim.setStartValue(self._drawer.geometry())
            self._drawer_anim.setEndValue(target)
            self._drawer_anim.start()
        else:
            self._drawer.setGeometry(target)
            if not self._drawer_open:
                self._drawer.hide()

    def _on_drawer_anim_finished(self) -> None:
        if not self._drawer_open:
            self._drawer.hide()

    def _toggle_drawer(self) -> None:
        self._drawer_open = not self._drawer_open
        self._drawer_toggle.setText("close" if self._drawer_open else "menu")
        self._place_drawer(animated=True)

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

    def _maybe_turn_towards_target(self) -> bool:
        if self._anim_mode != "swim":
            return False
        dx = self._target_x - self._x
        if abs(dx) < 12.0:
            return False
        desired_direction = "right" if dx >= 0 else "left"
        if desired_direction != self._anim_direction:
            self._start_turn_to(desired_direction)
            return True
        return False

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
            "react_kind": "chill",
            "react_until": 0.0,
            "skin_id": "default",
            "last_event_id": "",
            "last_event_type": "",
            "pomo_phase": "",
            "pearls": 0,
            "today_pearls": 0,
            "lifetime_pearls": 0,
            "focus_streak": 0,
            "day_streak": 0,
            "title_id": "drifter",
            "bubble_style": "default",
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
                peer_skin_id = self._resolve_skin_id(source, "auto")
                self._peer_set_skin(peer, peer_skin_id, target_h=int(self.height() * 0.36))
            else:
                peer_skin_id = self._resolve_skin_id(source, "auto")
                if str(peer.get("skin_id", "default")) != peer_skin_id:
                    self._peer_set_skin(peer, peer_skin_id, target_h=int(self.height() * 0.36))

            prev_mode = str(peer.get("mode", "unknown"))
            prev_event_id = str(peer.get("last_event_id", ""))
            peer["mode"] = str(entity.get("mode", peer.get("mode", "unknown")))
            peer["pomo_phase"] = str(entity.get("pomo_phase", peer.get("pomo_phase", "")))
            peer["last_seen"] = float(entity.get("last_seen", time.time()))
            peer["last_event_type"] = str(entity.get("last_event_type", peer.get("last_event_type", "")))
            peer["last_event_id"] = str(entity.get("last_event_id", peer.get("last_event_id", "")))
            peer["pearls"] = int(entity.get("pearls", peer.get("pearls", 0)))
            peer["today_pearls"] = int(entity.get("today_pearls", peer.get("today_pearls", 0)))
            peer["lifetime_pearls"] = int(entity.get("lifetime_pearls", peer.get("lifetime_pearls", 0)))
            peer["focus_streak"] = int(entity.get("focus_streak", peer.get("focus_streak", 0)))
            peer["day_streak"] = int(entity.get("day_streak", peer.get("day_streak", 0)))
            peer["title_id"] = str(entity.get("title_id", peer.get("title_id", "drifter")))
            peer["bubble_style"] = str(entity.get("bubble_style", peer.get("bubble_style", "default")))
            peer["online"] = float(entity.get("online", peer.get("online", 1.0)))

            # Trigger remote reaction on every new remote event id (not only mode changes).
            if peer["last_event_id"] and peer["last_event_id"] != prev_event_id:
                evt_type = str(peer.get("last_event_type", ""))
                if evt_type == "mode_change":
                    mode = str(peer.get("mode", "chill"))
                    if mode not in {"study", "chill", "rest"}:
                        mode = "chill"
                    peer["react_kind"] = mode
                    peer["react_until"] = time.monotonic() + 2.0
                elif evt_type == "manual_ping":
                    peer["react_kind"] = "chill"
                    peer["react_until"] = time.monotonic() + 1.2
            elif peer["mode"] != prev_mode and peer["mode"] in {"study", "chill", "rest"}:
                # Fallback for compatibility if event id is unavailable.
                peer["react_kind"] = str(peer["mode"])
                peer["react_until"] = time.monotonic() + 2.0

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
        self._position_bubble_near_mouth()
        self._position_shop_dialog()
        self._update_frame(force=True)
        self.update()

    def moveEvent(self, e: QtGui.QMoveEvent) -> None:
        super().moveEvent(e)
        self._position_shop_dialog()

    def showEvent(self, e: QtGui.QShowEvent) -> None:
        self._apply_screen_width()
        if not self._did_initial_center:
            screen = QtGui.QGuiApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                self.move(
                    geo.left() + (geo.width() - self.width()) // 2,
                    geo.top() + (geo.height() - self.height()) // 2,
                )
            self._did_initial_center = True
        super().showEvent(e)
        self._position_shop_dialog()

    # -------- animation state ----------
    def _frame_list(
        self,
        anim: str,
        direction: str,
        role: str = "local",
        react_kind: str | None = None,
        peer: dict[str, float | str] | None = None,
    ) -> list[QtGui.QPixmap]:
        if role == "local":
            frames_scaled = self._local_frames_scaled
            react_scaled = self._local_react_scaled
            rk = react_kind or self._react_kind
        else:
            if peer is None:
                return []
            frames_scaled = peer.get("frames_scaled", {})
            react_scaled = peer.get("react_scaled", {})
            if not isinstance(frames_scaled, dict) or not isinstance(react_scaled, dict):
                return []
            rk = react_kind or str(peer.get("react_kind", "chill"))

        if anim == "react":
            by_dir = react_scaled.get(direction, {})
            if isinstance(by_dir, dict):
                return by_dir.get(rk, [])
            return []
        by_dir = frames_scaled.get(direction, {})
        if isinstance(by_dir, dict):
            return by_dir.get(anim, [])
        return []

    def _safe_anim(
        self,
        anim: str,
        direction: str,
        role: str = "local",
        react_kind: str | None = None,
        peer: dict[str, float | str] | None = None,
    ) -> str:
        if self._frame_list(anim, direction, role=role, react_kind=react_kind, peer=peer):
            return anim
        if self._frame_list("swim", direction, role=role, react_kind=react_kind, peer=peer):
            return "swim"
        if self._frame_list("idle", direction, role=role, react_kind=react_kind, peer=peer):
            return "idle"
        return "turn"

    def _next_frame(self, anim: str, direction: str) -> QtGui.QPixmap:
        safe_anim = self._safe_anim(anim, direction, role="local", react_kind=self._react_kind)
        key = f"{direction}:{safe_anim}:{self._react_kind if safe_anim == 'react' else '-'}"
        frames = self._frame_list(safe_anim, direction, role="local", react_kind=self._react_kind)
        if not frames:
            return QtGui.QPixmap()
        idx = self._anim_index.get(key, 0)
        frame = frames[idx % len(frames)]
        self._anim_index[key] = (idx + 1) % len(frames)
        return frame

    def _update_frame(self, force: bool = False) -> None:
        if self._anim_mode == "react" and time.monotonic() >= self._react_until:
            self._anim_mode = "swim"

        frame = self._next_frame(self._anim_mode, self._anim_direction)
        if not frame.isNull() or force:
            self._dugong_frame = frame

    def _trigger_react(self, kind: str, ms: int = 1400) -> None:
        direction = "right" if self._vx >= 0 else "left"
        if not self._local_react_scaled.get(direction, {}).get(kind):
            # Graceful fallback if requested react key does not exist.
            kind = "chill" if self._local_react_scaled.get(direction, {}).get("chill") else ""
        if not kind:
            return
        self._react_kind = kind
        self._anim_mode = "react"
        self._react_until = time.monotonic() + max(0.3, ms / 1000.0)

    def _start_turn(self) -> None:
        self._start_turn_to("left" if self._anim_direction == "right" else "right")

    def _start_turn_to(self, target_direction: str) -> None:
        if target_direction not in {"left", "right"}:
            return
        if target_direction == self._anim_direction:
            return
        self._anim_mode = "turn"
        self._turn_target_direction = target_direction
        self._turn_ticks_left = max(3, len(self._frame_list("turn", self._anim_direction)))
        self._vx = 0.0
        self._vy = 0.0
        self._turn_cooldown_until = time.monotonic() + 0.25

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
            if self._maybe_turn_towards_target():
                return
            if self._anim_mode == "swim" and random.random() < 0.28:
                self._anim_mode = "idle"
                self._idle_ticks_left = random.randint(10, 24)
                self._vx = 0.0
                self._vy = 0.0
            return

        speed = self._swim_speed * (0.75 if self._anim_mode == "turn" else 1.0)
        next_vx = (dx / dist) * speed
        next_vy = (dy / dist) * speed

        if abs(next_vx) < 0.06:
            next_vx = 0.06 if dx >= 0 else -0.06

        desired_direction = "right" if dx >= 0 else "left"
        if self._anim_mode == "swim" and desired_direction != self._anim_direction:
            self._start_turn_to(desired_direction)
            return

        self._vx = next_vx
        self._vy = next_vy

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

    def _next_peer_frame(self, source: str, direction: str, peer: dict[str, float | str]) -> QtGui.QPixmap:
        now = time.monotonic()
        react_until = float(peer.get("react_until", 0.0))
        react_kind = str(peer.get("react_kind", "chill"))
        if react_until > now:
            anim = "react"
        else:
            anim = "swim"

        safe_anim = self._safe_anim(anim, direction, role="peer", react_kind=react_kind, peer=peer)
        frames = self._frame_list(safe_anim, direction, role="peer", react_kind=react_kind, peer=peer)
        if not frames:
            frames = self._frame_list("idle", direction, role="peer", react_kind=react_kind, peer=peer)
        if not frames:
            return QtGui.QPixmap()
        idx_key = f"{source}:{safe_anim}:{react_kind if safe_anim == 'react' else '-'}:{direction}"
        idx = self._peer_anim_index.get(idx_key, 0)
        frame = frames[idx % len(frames)]
        self._peer_anim_index[idx_key] = (idx + 1) % len(frames)
        return frame

    def _tick_dugong(self) -> None:
        self._update_frame()
        for source, peer in self._peer_entities.items():
            direction = str(peer.get("facing", "right"))
            if direction not in {"left", "right"}:
                direction = "right"
            pm = self._next_peer_frame(source, direction, peer)
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
                if self._turn_target_direction in {"left", "right"}:
                    self._anim_direction = self._turn_target_direction
                    if self._anim_direction == "right" and self._vx < 0:
                        self._vx = abs(self._vx)
                    elif self._anim_direction == "left" and self._vx > 0:
                        self._vx = -abs(self._vx)
                self._turn_target_direction = ""
                self._anim_mode = "swim"
        elif self._anim_mode == "idle":
            self._idle_ticks_left -= 1
            if self._idle_ticks_left <= 0:
                self._anim_mode = "swim"
                self._pick_new_target(current)
        else:
            self._maybe_enter_idle()

        if self._anim_mode == "swim":
            self._step_towards_target(current)

        now = time.monotonic()
        for peer in self._peer_entities.values():
            # Keep peer stationary while its react clip is playing.
            if float(peer.get("react_until", 0.0)) > now:
                continue
            self._step_peer_towards_target(current, peer)

        self._tick_floating_rewards()
        self._position_bubble_near_mouth()
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
        title_text: str | None = None,
    ) -> None:
        name = (source or "").strip()
        if not name:
            return
        name_text = name if len(name) <= 14 else f"{name[:13]}…"
        title = (title_text or "").strip()
        if not title and is_local:
            title = self._title_label(self._equipped_title_id)
        title = title if len(title) <= 16 else f"{title[:15]}…"

        font = QtGui.QFont()
        font.setPointSize(8 if not is_local else 9)
        font.setWeight(QtGui.QFont.DemiBold)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        pad_x = 8
        pad_y = 3
        text_w = metrics.horizontalAdvance(name_text)
        text_h = metrics.height()
        name_w = text_w + (pad_x * 2)
        name_h = text_h + (pad_y * 2)
        title_w = 0
        title_h = 0
        if title:
            tfont = QtGui.QFont()
            tfont.setPointSize(7)
            tfont.setWeight(QtGui.QFont.DemiBold)
            tmetrics = QtGui.QFontMetrics(tfont)
            title_w = tmetrics.horizontalAdvance(title) + 12
            title_h = tmetrics.height() + 4
        total_w = max(name_w, title_w) if title else name_w
        center_x = x + (anchor_w // 2)
        # PNG has transparent top padding; anchor label closer to visible head area.
        head_anchor_y = y + int(anchor_h * 0.10)
        total_h = name_h + (title_h + 3 if title else 0)
        ry = head_anchor_y - total_h - 1

        bg = QtGui.QColor(21, 42, 66, 190) if is_local else QtGui.QColor(26, 58, 92, 168)
        border = QtGui.QColor(169, 225, 255, 180) if is_local else QtGui.QColor(150, 200, 235, 140)
        fg = QtGui.QColor(245, 251, 255, 240)
        title_bg = QtGui.QColor(22, 74, 108, 205) if is_local else QtGui.QColor(19, 63, 94, 186)
        title_border = QtGui.QColor(130, 213, 246, 180) if is_local else QtGui.QColor(125, 193, 232, 145)

        name_y = ry
        name_x = center_x - (name_w // 2)
        if title:
            tx = center_x - (title_w // 2)
            painter.setPen(QtGui.QPen(title_border, 1))
            painter.setBrush(QtGui.QBrush(title_bg))
            painter.drawRoundedRect(tx, ry, title_w, title_h, 7, 7)
            tfont = QtGui.QFont()
            tfont.setPointSize(7)
            tfont.setWeight(QtGui.QFont.DemiBold)
            tmetrics = QtGui.QFontMetrics(tfont)
            painter.setFont(tfont)
            painter.setPen(QtGui.QPen(fg))
            painter.drawText(tx + 6, ry + 2 + tmetrics.ascent(), title)
            painter.setFont(font)
            name_y = ry + title_h + 3

        painter.setPen(QtGui.QPen(border, 1))
        painter.setBrush(QtGui.QBrush(bg))
        painter.drawRoundedRect(name_x, name_y, name_w, name_h, 8, 8)
        painter.setPen(QtGui.QPen(fg))
        painter.drawText(name_x + pad_x, name_y + pad_y + metrics.ascent(), name_text)

    def _stage_from_pearls(self, pearls: int) -> tuple[str, str]:
        if pearls >= 1000:
            return "S", "Deepsea Sovereign"
        if pearls >= 600:
            return "A", "Abyss Sentinel"
        if pearls >= 320:
            return "B", "Focus Navigator"
        if pearls >= 160:
            return "C", "Pearl Hunter"
        if pearls >= 60:
            return "D", "Reef Explorer"
        return "E", "Tiny Drifter"

    def _local_stats_from_text(self) -> tuple[int, int, int, str]:
        energy = int(self._local_profile.get("energy", 0))
        mood = int(self._local_profile.get("mood", 0))
        focus = int(self._local_profile.get("focus", 0))
        mode = str(self._local_profile.get("mode", "unknown"))
        return energy, mood, focus, mode

    def _title_label(self, title_id: str) -> str:
        mapping = {
            "drifter": "Wanderer",
            "explorer": "Explorer",
        }
        return mapping.get(title_id, title_id.title())

    def _bubble_palette(self) -> tuple[str, str]:
        if self._equipped_bubble_style == "ocean":
            return (
                "background: rgba(16,49,75,170); border: 1px solid rgba(120,198,240,170);",
                "color: rgba(232,248,255,240);",
            )
        return ("background: rgba(20,30,45,140); border: 1px solid rgba(120,170,210,110);", "color: rgba(255,255,255,235);")

    def _bubble_colors(self) -> tuple[QtGui.QColor, QtGui.QColor, QtGui.QColor]:
        if self._equipped_bubble_style == "ocean":
            return (
                QtGui.QColor(16, 49, 75, 170),
                QtGui.QColor(120, 198, 240, 170),
                QtGui.QColor(232, 248, 255, 240),
            )
        return (
            QtGui.QColor(20, 30, 45, 140),
            QtGui.QColor(120, 170, 210, 110),
            QtGui.QColor(255, 255, 255, 235),
        )

    def _bubble_tail_pixmap(
        self, width: int, height: int, *, downward: bool, fill: QtGui.QColor, border: QtGui.QColor
    ) -> QtGui.QPixmap:
        pm = QtGui.QPixmap(width, height)
        pm.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pm)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        poly = QtGui.QPolygonF()
        if downward:
            poly.append(QtCore.QPointF(1.0, 1.0))
            poly.append(QtCore.QPointF(width - 2.0, 1.0))
            poly.append(QtCore.QPointF(width * 0.5, height - 1.0))
        else:
            poly.append(QtCore.QPointF(width * 0.5, 1.0))
            poly.append(QtCore.QPointF(width - 2.0, height - 2.0))
            poly.append(QtCore.QPointF(1.0, height - 2.0))
        painter.setPen(QtGui.QPen(border, 1))
        painter.setBrush(QtGui.QBrush(fill))
        painter.drawPolygon(poly)
        painter.end()
        return pm

    def _hide_bubble_widgets(self) -> None:
        self._bubble.hide()
        self._bubble_tail.hide()

    def _position_bubble_near_mouth(self) -> None:
        if self._bubble.text() == "" or not self._bubble.isVisible():
            self._bubble_tail.hide()
            return
        facing = self._anim_direction if self._anim_direction in {"left", "right"} else ("right" if self._vx >= 0 else "left")
        if not self._dugong_frame.isNull():
            mouth_ratio_x = 0.30 if facing == "left" else 0.70
            mouth_x = int(self._x + (self._dugong_frame.width() * mouth_ratio_x))
            mouth_y = int(self._y + (self._dugong_frame.height() * 0.43))
        else:
            mouth_x = self.width() // 2
            mouth_y = int(self.height() * 0.56)

        bubble_w = self._bubble.width()
        bubble_h = self._bubble.height()
        # Keep bubble in front of the mouth and higher to avoid name tag overlap.
        if facing == "left":
            bubble_x = mouth_x - bubble_w - 34
        else:
            bubble_x = mouth_x + 24
        bubble_y = mouth_y - int(bubble_h * 0.98) - 12
        if bubble_x < 10:
            bubble_x = 10
        if bubble_x + bubble_w > self.width() - 10:
            bubble_x = self.width() - bubble_w - 10

        # Pure relative placement: keep bubble above mouth, do not auto-flip below.
        below = False
        if bubble_y < 0:
            bubble_y = 0
        if bubble_y + bubble_h > self.height() - 14:
            bubble_y = self.height() - bubble_h - 14

        self._bubble.move(bubble_x, bubble_y)
        self._bubble.raise_()

        fill, border, _fg = self._bubble_colors()
        tail_w = 14
        tail_h = 10
        downward = not below
        tail_pm = self._bubble_tail_pixmap(tail_w, tail_h, downward=downward, fill=fill, border=border)
        self._bubble_tail.setPixmap(tail_pm)
        anchor_x = max(bubble_x + 10, min(bubble_x + bubble_w - 10, mouth_x))
        tail_x = anchor_x - (tail_w // 2)
        if downward:
            tail_y = bubble_y + bubble_h - 1
        else:
            tail_y = bubble_y - tail_h + 1
        self._bubble_tail.setGeometry(tail_x, tail_y, tail_w, tail_h)
        self._bubble_tail.show()
        self._bubble_tail.raise_()

    def _hover_target(self) -> tuple[str, str, QtCore.QRect] | None:
        if self._hover_pos.x() < 0 or self._hover_pos.y() < 0:
            return None

        # Prioritize peer entities so overlapping local sprite does not block.
        for source, peer in reversed(sorted(self._peer_entities.items(), key=lambda x: x[0])):
            pm = self._peer_current_frame.get(source)
            if pm is None or pm.isNull():
                continue
            rect = QtCore.QRect(
                int(float(peer.get("x", 0.0))),
                int(float(peer.get("y", 0.0))),
                pm.width(),
                pm.height(),
            )
            if rect.contains(self._hover_pos):
                return ("peer", source, rect)

        if not self._dugong_frame.isNull():
            local_rect = QtCore.QRect(int(self._x), int(self._y), self._dugong_frame.width(), self._dugong_frame.height())
            if local_rect.contains(self._hover_pos):
                return ("local", self._local_source, local_rect)
        return None

    def _draw_hover_card(self, painter: QtGui.QPainter) -> None:
        target = self._hover_target()
        if target is None:
            return
        kind, source, rect = target

        lines: list[str] = []
        if kind == "local":
            energy, mood, focus, mode = self._local_stats_from_text()
            rank, title = self._stage_from_pearls(self._pearls_total)
            lines = [
                f"[{rank}] {title}",
                f"Name: {source}",
                f"Title: {self._title_label(self._equipped_title_id)}",
                f"Mode: {mode}  Pomo: {str(self._local_profile.get('pomo_state', self._pomo_state.lower()))}",
                f"Mood: {mood}  Energy: {energy}  Focus: {focus}",
                f"Pearls: {self._pearls_total}  Today: +{self._today_pearls}  Lifetime: {self._lifetime_pearls}",
                f"Streak: {self._focus_streak}  Day: {self._day_streak}",
            ]
        else:
            peer = self._peer_entities.get(source, {})
            mode = str(peer.get("mode", "unknown"))
            phase = str(peer.get("pomo_phase", "")).lower() or "idle"
            last_seen = float(peer.get("last_seen", time.time()))
            age = max(0, int(time.time() - last_seen))
            online = float(peer.get("online", 1.0)) > 0.0
            title = self._title_label(str(peer.get("title_id", "drifter")))
            status_line = "Status: online" if online else f"Last seen: {age}s ago"
            lines = [
                "[ALLY] Co-focus Partner",
                f"Name: {source}",
                f"Title: {title}",
                f"Mode: {mode}  Pomo: {phase}",
                status_line,
                f"Pearls: {int(peer.get('pearls', 0))} (+{int(peer.get('today_pearls', 0))} today)",
                f"Streak: {int(peer.get('focus_streak', 0))}  Day: {int(peer.get('day_streak', 0))}",
            ]

        font = QtGui.QFont()
        font.setPointSize(9)
        font.setWeight(QtGui.QFont.DemiBold)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        pad_x = 10
        pad_y = 8
        line_h = metrics.height() + 2
        width = max(metrics.horizontalAdvance(line) for line in lines) + (pad_x * 2)
        height = (line_h * len(lines)) + (pad_y * 2)

        x = rect.x() + (rect.width() // 2) - (width // 2)
        y = rect.y() - height - 10
        if x < 8:
            x = 8
        if x + width > self.width() - 8:
            x = self.width() - width - 8
        if y < 36:
            y = rect.bottom() + 10
        if y + height > self.height() - 8:
            y = self.height() - height - 8

        bg = QtGui.QColor(14, 30, 48, 228)
        border = QtGui.QColor(135, 214, 255, 190)
        title_color = QtGui.QColor(164, 244, 224, 240)
        text_color = QtGui.QColor(242, 248, 255, 238)

        painter.setPen(QtGui.QPen(border, 1))
        painter.setBrush(QtGui.QBrush(bg))
        painter.drawRoundedRect(x, y, width, height, 10, 10)

        for idx, line in enumerate(lines):
            ly = y + pad_y + ((idx + 1) * line_h) - 4
            painter.setPen(title_color if idx == 0 else text_color)
            painter.drawText(x + pad_x, ly, line)

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
                title_text=self._title_label(self._equipped_title_id),
            )

        if self._floating_rewards:
            font = QtGui.QFont()
            font.setPointSize(10)
            font.setWeight(QtGui.QFont.DemiBold)
            painter.setFont(font)
            for item in self._floating_rewards:
                life = max(0.0, min(1.0, float(item.get("life", 0.0)) / 1.4))
                alpha = int(255 * life)
                text = str(item.get("text", ""))
                x = int(float(item.get("x", 0.0)))
                y = int(float(item.get("y", 0.0)))
                shadow = QtGui.QColor(12, 26, 38, alpha)
                fg = QtGui.QColor(170, 255, 225, alpha)
                painter.setPen(shadow)
                painter.drawText(x + 1, y + 1, text)
                painter.setPen(fg)
                painter.drawText(x, y, text)

        for source, peer in sorted(self._peer_entities.items(), key=lambda x: x[0]):
            pm = self._peer_current_frame.get(source)
            if pm is None or pm.isNull():
                direction = str(peer.get("facing", "right"))
                if direction not in {"left", "right"}:
                    direction = "right"
                pm = self._next_peer_frame(source, direction, peer)
                if not pm.isNull():
                    self._peer_current_frame[source] = pm
            if pm.isNull():
                continue
            x = int(float(peer.get("x", 0.0)))
            y = int(float(peer.get("y", 0.0)))
            painter.drawPixmap(x, y, pm)
            peer_title = self._title_label(str(peer.get("title_id", "drifter")))
            self._draw_name_tag(
                painter,
                x,
                y,
                source,
                is_local=False,
                anchor_w=pm.width(),
                anchor_h=pm.height(),
                title_text=peer_title,
            )

        self._draw_hover_card(painter)

    # -------- hover ----------
    def enterEvent(self, _e: QtCore.QEvent) -> None:
        self.update()

    def leaveEvent(self, _e: QtCore.QEvent) -> None:
        self._hover_pos = QtCore.QPoint(-1, -1)
        self.update()

    # -------- drag + click ----------
    def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.button() == QtCore.Qt.LeftButton:
            pos = e.position().toPoint()
            if self._drawer_open:
                in_drawer = self._drawer.geometry().contains(pos)
                in_toggle = self._drawer_toggle.geometry().contains(pos)
                if not in_drawer and not in_toggle:
                    self._drawer_open = False
                    self._drawer_toggle.setText("menu")
                    self._place_drawer(animated=True)
                    e.accept()
                    return
            self._dragging = True
            self._drag_moved = False
            self._press_global = e.globalPosition().toPoint()
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent) -> None:
        self._hover_pos = e.position().toPoint()
        if self._dragging:
            if (e.globalPosition().toPoint() - self._press_global).manhattanLength() > 4:
                self._drag_moved = True
            self.move(e.globalPosition().toPoint() - self._drag_offset)
            e.accept()
            return
        self.update()

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
        self._state_text_raw = text
        self._state.setText("")

        mode = ""
        m = re.search(r"\[([^\]]+)\]", text)
        if m:
            mode = m.group(1).strip().lower()
        else:
            m2 = re.search(r"mode:([a-zA-Z_]+)", text)
            if m2:
                mode = m2.group(1).strip().lower()
        if not mode:
            return
        if mode == self._last_mode:
            return
        self._last_mode = mode

        if mode == "rest" and self._anim_mode not in {"react", "turn"}:
            self._anim_mode = "idle"
            self._idle_ticks_left = max(self._idle_ticks_left, 30)

    def set_pomo_text(self, text: str) -> None:
        if self._compact_mode:
            upper = (text or "").upper()
            mmss = ""
            m = re.search(r"(\d{2}:\d{2})", upper)
            if m:
                mmss = m.group(1)
            if "PAUSED" in upper or "PAUSE" in upper:
                compact = f"PAUSE {mmss}".strip()
            elif "FOCUS" in upper:
                compact = f"FOCUS {mmss}".strip()
            elif "BREAK" in upper:
                compact = f"BREAK {mmss}".strip()
            else:
                compact = "POMO IDLE"
            self._pomo.setText(compact)
        else:
            self._pomo.setText(text)
        self._layout_overlay()

    def set_pomo_state(self, state: str) -> None:
        s = (state or "").upper()
        self._pomo_state = s
        self._update_pomo_toggle_label(s)
        if s == self._last_pomo_state:
            return
        self._last_pomo_state = s
        self._apply_pomo_chip_style(s)
        if s == "FOCUS":
            if self._anim_mode not in {"react", "turn"}:
                self._anim_mode = "swim"
        elif s == "BREAK":
            if self._anim_mode not in {"react", "turn"}:
                self._trigger_react("chill", ms=1200)
        elif s == "PAUSED":
            if self._anim_mode not in {"react", "turn"}:
                self._anim_mode = "idle"
                self._idle_ticks_left = max(self._idle_ticks_left, 16)

    def set_reward_stats(self, stats: dict[str, int | str]) -> None:
        pearls = int(stats.get("pearls", self._pearls_total))
        lifetime = int(stats.get("lifetime_pearls", self._lifetime_pearls))
        today = int(stats.get("today_pearls", self._today_pearls))
        focus_streak = int(stats.get("focus_streak", self._focus_streak))
        day_streak = int(stats.get("day_streak", self._day_streak))
        equipped_skin_id = str(stats.get("equipped_skin_id", self._equipped_skin_id))
        equipped_bubble_style = str(stats.get("equipped_bubble_style", self._equipped_bubble_style))
        equipped_title_id = str(stats.get("equipped_title_id", self._equipped_title_id))
        owned_skins = stats.get("shop_owned_skins", [])
        owned_bubbles = stats.get("shop_owned_bubbles", [])
        owned_titles = stats.get("shop_owned_titles", [])

        delta = pearls - self._pearls_total
        if delta > 0:
            self._spawn_reward_float(delta)

        self._pearls_total = pearls
        self._lifetime_pearls = lifetime
        self._today_pearls = today
        self._focus_streak = focus_streak
        self._day_streak = day_streak
        self._equipped_bubble_style = equipped_bubble_style
        self._equipped_title_id = equipped_title_id
        if isinstance(owned_skins, list):
            self._owned_skins = {str(x).strip().lower() for x in owned_skins if str(x).strip()}
            self._owned_skins.add("default")
        if isinstance(owned_bubbles, list):
            self._owned_bubbles = {str(x).strip().lower() for x in owned_bubbles if str(x).strip()}
            self._owned_bubbles.add("default")
        if isinstance(owned_titles, list):
            self._owned_titles = {str(x).strip().lower() for x in owned_titles if str(x).strip()}
            self._owned_titles.add("drifter")
        if equipped_skin_id and equipped_skin_id != self._equipped_skin_id:
            self._apply_local_skin(equipped_skin_id)
        self._update_pearl_text()
        self._layout_overlay()

    def _spawn_reward_float(self, gain: int) -> None:
        if self._dugong_frame.isNull():
            return
        base_x = self._x + (self._dugong_frame.width() * 0.52)
        base_y = self._y + (self._dugong_frame.height() * 0.18)
        self._floating_rewards.append(
            {
                "x": float(base_x),
                "y": float(base_y),
                "vy": -0.75,
                "life": 1.4,
                "text": f"+{int(gain)} pearls",
            }
        )
        if len(self._floating_rewards) > 8:
            self._floating_rewards = self._floating_rewards[-8:]

    def _tick_floating_rewards(self) -> None:
        if not self._floating_rewards:
            return
        dt = max(0.01, self._world_tick_ms / 1000.0)
        alive: list[dict[str, float | str]] = []
        for item in self._floating_rewards:
            life = float(item.get("life", 0.0)) - dt
            if life <= 0:
                continue
            item["life"] = life
            item["y"] = float(item.get("y", 0.0)) + float(item.get("vy", -0.75))
            alive.append(item)
        self._floating_rewards = alive

    def _apply_local_skin(self, skin_id: str) -> None:
        sid = (skin_id or "").strip()
        if not sid:
            return
        assets_dir = self._resolve_skin_assets_dir(self._skin_root, sid)
        try:
            frames_raw, react_raw = self._load_character_assets(assets_dir)
        except Exception:
            return
        self._skin_id = sid
        self._equipped_skin_id = sid
        self._local_skin_assets_dir = assets_dir
        self._local_frames_raw = frames_raw
        self._local_react_raw = react_raw
        self._rebuild_scaled_pixmaps()
        self._update_frame(force=True)
        self.update()

    def set_local_profile(self, profile: dict[str, str | int]) -> None:
        self._local_profile = dict(profile)

    def apply_sprite_hint(self, sprite: str) -> None:
        _ = sprite

    def show_bubble(self, text: str, ms: int = 2500) -> None:
        bubble_bg, bubble_fg = self._bubble_palette()
        self._bubble.setStyleSheet(
            f"""
            {bubble_fg}
            {bubble_bg}
            border-radius: 10px;
            padding: 8px 10px;
            font-size: 13px;
            """
        )
        self._bubble.setText(text)
        metrics = QtGui.QFontMetrics(self._bubble.font())
        content = (text or "").strip() or "..."
        max_w = min(max(180, int(self.width() * 0.45)), 420)
        min_w = 96
        natural_w = metrics.horizontalAdvance(content) + 24
        bw = max(min_w, min(max_w, natural_w))
        self._bubble.setFixedWidth(bw)
        self._bubble.adjustSize()
        self._bubble.show()
        self._position_bubble_near_mouth()
        self._bubble.raise_()
        life = ms
        lowered = text.lower()
        if "complete" in lowered or "pearls" in lowered or "milestone" in lowered:
            life = max(ms, 2600)
            if self._anim_mode not in {"turn"}:
                self._trigger_react("chill", ms=1800)
        self._bubble_timer.start(life)

    def _apply_pomo_chip_style(self, state: str) -> None:
        s = (state or "").upper()
        bg = "rgba(30,52,75,205)"
        border = "rgba(130,170,210,180)"
        fg = "rgba(240,248,255,245)"
        if s == "FOCUS":
            bg = "rgba(20,74,44,210)"
            border = "rgba(120,220,165,190)"
        elif s == "BREAK":
            bg = "rgba(78,58,22,210)"
            border = "rgba(240,205,120,190)"
        elif s == "PAUSED":
            bg = "rgba(63,47,96,210)"
            border = "rgba(186,160,246,185)"
        self._pomo.setStyleSheet(
            f"""
            QLabel {{
                color: {fg};
                background: {bg};
                border: 1px solid {border};
                border-radius: 11px;
                font-size: 12px;
                font-weight: 700;
                padding: 0 10px;
            }}
            """
        )

    def _update_pomo_toggle_label(self, state: str) -> None:
        s = (state or "").upper()
        if s in {"FOCUS", "BREAK"}:
            text = "pause"
            color = "#4d3d73"
        elif s == "PAUSED":
            text = "resume"
            color = "#2b5d58"
        else:
            text = "start"
            color = "#7b3f00"
        self._pomo_toggle.setText(text)
        self._pomo_toggle.setStyleSheet(
            f"""
            QPushButton {{
                color: white;
                background: {color};
                border: none;
                padding: 2px 8px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
            }}
            """
        )

    def _emit_mode(self, mode: str) -> None:
        # Keep a short deterministic action clip when user clicks mode buttons.
        self._play_mode_sound(mode)
        if mode == "study":
            self._trigger_react("study", ms=2000)
        elif mode == "chill":
            self._trigger_react("chill", ms=2000)
        elif mode == "rest":
            self._trigger_react("rest", ms=2000)
        self._on_mode_change(mode)

    def _emit_ping(self) -> None:
        if self._on_manual_ping is not None:
            self._on_manual_ping("checkin")

    def _emit_pomo_start(self) -> None:
        if self._on_pomo_start is not None:
            self._on_pomo_start()

    def _emit_pomo_pause_resume(self) -> None:
        if self._on_pomo_pause_resume is not None:
            self._on_pomo_pause_resume()

    def _emit_pomo_toggle(self) -> None:
        s = self._pomo_state.upper()
        if s in {"FOCUS", "BREAK", "PAUSED"}:
            self._emit_pomo_pause_resume()
            return
        self._emit_pomo_start()

    def _emit_pomo_skip(self) -> None:
        if self._on_pomo_skip is not None:
            self._on_pomo_skip()

    def _emit_shop(self) -> None:
        self._open_shop_dialog()

    def _shop_skin_preview(self, skin_id: str, size: QtCore.QSize) -> QtGui.QPixmap:
        assets_dir = self._resolve_skin_assets_dir(self._skin_root, skin_id)
        for prefix in ("Idle_loop", "Swim_loop", "React_chill"):
            frames = self._load_by_prefix(assets_dir, prefix)
            if frames:
                return frames[0].scaled(size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        return QtGui.QPixmap()

    def _shop_badge_preview(self, title_id: str, size: QtCore.QSize) -> QtGui.QPixmap:
        badge_dir = self._assets_root / "badge"
        title_l = (title_id or "").strip().lower()
        alias = {"drifter": "wanderer"}.get(title_l, title_l)
        candidates = [
            badge_dir / f"{title_id}.png",
            badge_dir / f"{title_id}.PNG",
            badge_dir / f"{title_l}.png",
            badge_dir / f"{title_l}.PNG",
            badge_dir / f"{title_l.capitalize()}.png",
            badge_dir / f"{title_l.capitalize()}.PNG",
            badge_dir / f"{alias}.png",
            badge_dir / f"{alias}.PNG",
            badge_dir / f"{alias.capitalize()}.png",
            badge_dir / f"{alias.capitalize()}.PNG",
        ]
        for path in candidates:
            if path.exists() and path.is_file():
                pm = QtGui.QPixmap(str(path))
                if not pm.isNull():
                    return pm.scaled(size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

        pm = QtGui.QPixmap(size)
        pm.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pm)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        bg = QtGui.QColor(30, 72, 110, 220)
        border = QtGui.QColor(150, 220, 245, 210)
        fg = QtGui.QColor(245, 252, 255, 245)
        painter.setPen(QtGui.QPen(border, 2))
        painter.setBrush(QtGui.QBrush(bg))
        painter.drawEllipse(2, 2, size.width() - 4, size.height() - 4)
        label = self._title_label(title_id)
        letter = (label[:1] or "?").upper()
        font = QtGui.QFont()
        font.setPointSize(max(9, int(size.height() * 0.38)))
        font.setWeight(QtGui.QFont.Bold)
        painter.setFont(font)
        painter.setPen(fg)
        painter.drawText(pm.rect(), QtCore.Qt.AlignCenter, letter)
        painter.end()
        return pm

    def _item_state_suffix(self, kind: str, item_id: str, price: int) -> str:
        item_l = item_id.lower()
        if kind == "skin":
            owned = item_l in self._owned_skins
            equipped = item_id == self._equipped_skin_id
        elif kind == "bubble":
            owned = item_l in self._owned_bubbles
            equipped = item_id == self._equipped_bubble_style
        else:
            owned = item_l in self._owned_titles
            equipped = item_id == self._equipped_title_id
        if equipped:
            return "已装备"
        if owned:
            return "已拥有"
        return f"{int(price)} 珍珠"

    def _position_shop_dialog(self) -> None:
        dlg = self._shop_dialog
        if dlg is None or not dlg.isVisible():
            return

        if self._shop_manual_pos is not None:
            x = int(self._shop_manual_pos.x())
            y = int(self._shop_manual_pos.y())
        else:
            fg = self.frameGeometry()
            x = fg.left() + (fg.width() - dlg.width()) // 2
            # Lift shop upward relative to the app center.
            y = fg.top() + (fg.height() - dlg.height()) // 2 - max(20, int(self.height() * 0.09))

        screen = self.screen() or QtGui.QGuiApplication.primaryScreen()
        if screen is not None:
            sg = screen.availableGeometry()
            x = max(sg.left(), min(x, sg.right() - dlg.width() + 1))
            y = max(sg.top(), min(y, sg.bottom() - dlg.height() + 1))
        dlg.move(x, y)
        if self._shop_manual_pos is not None:
            self._shop_manual_pos = QtCore.QPoint(x, y)
        dlg.raise_()

    def _open_shop_dialog(self) -> None:
        if self._shop_dialog is not None and self._shop_dialog.isVisible():
            self._position_shop_dialog()
            self._shop_dialog.raise_()
            self._shop_dialog.activateWindow()
            return

        # Magnetic shop window: follows the main Dugong bar position.
        dlg = QtWidgets.QDialog(None)
        dlg.setWindowTitle("Dugong Shop")
        dlg.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        dlg.setModal(False)
        dlg.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        bg_src = QtGui.QPixmap(str(self._assets_root / "dugong_shop.png"))
        if bg_src.isNull():
            # fallback to old menu if asset is missing
            menu = QtWidgets.QMenu(self)
            menu.addAction("shop asset missing")
            menu.exec(QtGui.QCursor.pos())
            return

        # Use different sizing rules for compact/full modes.
        if self._compact_mode:
            target_h = min(430, max(290, int(self.height() * 1.22)))
            max_w = max(430, int(self.width() * 1.08))
        else:
            target_h = min(520, max(320, int(self.height() * 1.45)))
            max_w = max(640, int(self.width() * 0.72))
        shop_scale = self._shop_scale
        target_h = max(180, int(target_h * shop_scale))
        max_w = max(260, int(max_w * shop_scale))
        bg = bg_src.scaledToHeight(target_h, QtCore.Qt.SmoothTransformation)
        if bg.width() > max_w:
            bg = bg.scaledToWidth(max_w, QtCore.Qt.SmoothTransformation)
        dlg.setFixedSize(bg.width(), bg.height())

        root = QtWidgets.QFrame(dlg)
        root.setGeometry(0, 0, dlg.width(), dlg.height())
        root.setStyleSheet("background: transparent;")

        bg_label = QtWidgets.QLabel(root)
        bg_label.setGeometry(0, 0, dlg.width(), dlg.height())
        bg_label.setPixmap(bg)
        bg_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        dlg.setProperty("shop_drag_surface", True)
        root.setProperty("shop_drag_surface", True)
        dlg.installEventFilter(self)
        root.installEventFilter(self)

        hint = QtWidgets.QLabel("", root)
        hint.setGeometry(int(dlg.width() * 0.24), int(dlg.height() * 0.84), int(dlg.width() * 0.52), 30)
        hint.setAlignment(QtCore.Qt.AlignCenter)
        hint.setStyleSheet(
            """
            QLabel {
                color: rgba(236,247,255,245);
                background: rgba(18,48,74,210);
                border: 1px solid rgba(128,198,234,175);
                border-radius: 9px;
                font-size: 12px;
                font-weight: 700;
                padding: 2px 8px;
            }
            """
        )
        hint.hide()
        self._shop_hint_label = hint

        def mk_item_btn(
            icon: QtGui.QPixmap,
            rect: QtCore.QRect,
            hover_text: str,
            on_click: Callable[[], None],
            *,
            hit_expand_w: int = 0,
            hit_expand_h: int = 0,
        ) -> QtWidgets.QPushButton:
            hit_rect = QtCore.QRect(
                rect.x() - (hit_expand_w // 2),
                rect.y() - (hit_expand_h // 2),
                rect.width() + hit_expand_w,
                rect.height() + hit_expand_h,
            )
            b = QtWidgets.QPushButton("", root)
            b.setGeometry(hit_rect)
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            b.setFlat(True)
            b.setStyleSheet(
                """
                QPushButton {
                    color: rgba(245,252,255,240);
                    background: transparent;
                    border: none;
                    border-radius: 0px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background: transparent;
                    border: none;
                }
                """
            )
            if not icon.isNull():
                b.setIcon(QtGui.QIcon(icon))
                b.setIconSize(QtCore.QSize(rect.width(), rect.height()))
            b.setProperty("shop_info", hover_text)
            b.installEventFilter(self)
            b.clicked.connect(lambda _checked=False, fn=on_click: fn())
            return b

        # close button
        close_btn = QtWidgets.QPushButton("X", root)
        close_btn.setGeometry(dlg.width() - 46, 12, 34, 34)
        close_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        close_btn.setStyleSheet(
            """
            QPushButton {
                color: rgba(248,253,255,248);
                background: rgba(10,34,58,235);
                border: 1px solid rgba(150,210,240,205);
                border-radius: 10px;
                font-size: 15px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: rgba(22,52,82,240);
            }
            """
        )
        close_btn.raise_()
        close_btn.clicked.connect(dlg.close)

        def adjust_shop_scale(delta: float) -> None:
            new_scale = max(0.35, min(1.20, round(self._shop_scale + delta, 2)))
            if abs(new_scale - self._shop_scale) < 0.001:
                return
            self._shop_scale = new_scale
            dlg.close()
            QtCore.QTimer.singleShot(0, self._open_shop_dialog)

        zoom_out_btn = QtWidgets.QPushButton("-", root)
        zoom_out_btn.setGeometry(12, 12, 30, 30)
        zoom_out_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        zoom_out_btn.setStyleSheet(
            """
            QPushButton {
                color: rgba(248,253,255,248);
                background: rgba(10,34,58,235);
                border: 1px solid rgba(150,210,240,205);
                border-radius: 9px;
                font-size: 16px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: rgba(22,52,82,240);
            }
            """
        )
        zoom_out_btn.clicked.connect(lambda _checked=False: adjust_shop_scale(-0.1))
        zoom_out_btn.raise_()

        zoom_in_btn = QtWidgets.QPushButton("+", root)
        zoom_in_btn.setGeometry(46, 12, 30, 30)
        zoom_in_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        zoom_in_btn.setStyleSheet(
            """
            QPushButton {
                color: rgba(248,253,255,248);
                background: rgba(10,34,58,235);
                border: 1px solid rgba(150,210,240,205);
                border-radius: 9px;
                font-size: 16px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: rgba(22,52,82,240);
            }
            """
        )
        zoom_in_btn.clicked.connect(lambda _checked=False: adjust_shop_scale(0.1))
        zoom_in_btn.raise_()

        # Main target: left wooden shelf for skins (image cards)
        skin_items = [
            ("king", 160, "King"),
            ("horse", 120, "Horse"),
        ]
        # King on the left, horse on the right, and both enlarged x2.
        skin_rects = [
            QtCore.QRect(int(dlg.width() * 0.148), int(dlg.height() * 0.618), int(dlg.width() * 0.416), int(dlg.height() * 0.192)),  # king
            QtCore.QRect(int(dlg.width() * 0.148), int(dlg.height() * 0.322), int(dlg.width() * 0.416), int(dlg.height() * 0.192)),  # horse (raised one body higher)
        ]
        for idx, (sid, price, label) in enumerate(skin_items):
            suffix = self._item_state_suffix("skin", sid, price)
            hover_text = f"皮肤 {label} | {suffix}"
            rect = skin_rects[idx]
            icon = self._shop_skin_preview(sid, QtCore.QSize(rect.width() - 4, rect.height() - 2))

            def on_skin_click(_checked: bool = False, item_id: str = sid, p: int = price) -> None:
                if self._on_shop_action:
                    self._on_shop_action("skin", item_id, p)
                dlg.close()

            mk_item_btn(icon, rect, hover_text, on_skin_click, hit_expand_w=14, hit_expand_h=8)

        # Right pearl seats reserved for title/badge icons.
        badge_items = [
            ("drifter", 0, "Wanderer"),
            ("explorer", 60, "Explorer"),
        ]
        badge_x = [int(dlg.width() * 0.68), int(dlg.width() * 0.77)]
        for idx, (tid, price, label) in enumerate(badge_items):
            suffix = self._item_state_suffix("title", tid, price)
            hover_text = f"徽章 {label} | {suffix}"
            rect = QtCore.QRect(badge_x[idx], int(dlg.height() * 0.54), int(dlg.width() * 0.108), int(dlg.height() * 0.162))
            icon = self._shop_badge_preview(tid, QtCore.QSize(rect.width() - 8, rect.height() - 8))

            def on_title_click(_checked: bool = False, item_id: str = tid, p: int = price) -> None:
                if self._on_shop_action:
                    self._on_shop_action("title", item_id, p)
                dlg.close()

            mk_item_btn(icon, rect, hover_text, on_title_click, hit_expand_w=14, hit_expand_h=10)

        dlg.destroyed.connect(lambda _obj=None: setattr(self, "_shop_dialog", None))
        dlg.show()
        self._position_shop_dialog()
        dlg.raise_()
        dlg.activateWindow()
        self._shop_dialog = dlg

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if watched.property("shop_drag_surface"):
            dlg = watched if isinstance(watched, QtWidgets.QDialog) else self._shop_dialog
            if isinstance(dlg, QtWidgets.QDialog):
                if event.type() == QtCore.QEvent.MouseButtonPress and isinstance(event, QtGui.QMouseEvent):
                    if event.button() == QtCore.Qt.LeftButton and self._is_shop_edge_press(dlg, event.position().toPoint()):
                        self._shop_edge_pressing = True
                        self._shop_edge_drag_ready = False
                        self._shop_edge_dragging = False
                        self._shop_drag_dlg = dlg
                        self._shop_drag_offset = event.globalPosition().toPoint() - dlg.frameGeometry().topLeft()
                        self._shop_edge_hold_timer.start(self._shop_edge_hold_ms)
                        return True
                elif event.type() == QtCore.QEvent.MouseMove and isinstance(event, QtGui.QMouseEvent):
                    if self._shop_edge_pressing and self._shop_edge_drag_ready and (event.buttons() & QtCore.Qt.LeftButton):
                        self._shop_edge_dragging = True
                        self._move_shop_dialog_to(event.globalPosition().toPoint())
                        return True
                    if self._shop_edge_pressing and not self._shop_edge_drag_ready:
                        if (event.globalPosition().toPoint() - (dlg.frameGeometry().topLeft() + self._shop_drag_offset)).manhattanLength() > 8:
                            self._shop_edge_hold_timer.stop()
                            self._shop_edge_pressing = False
                elif event.type() == QtCore.QEvent.MouseButtonRelease and isinstance(event, QtGui.QMouseEvent):
                    if event.button() == QtCore.Qt.LeftButton and self._shop_edge_pressing:
                        self._shop_edge_hold_timer.stop()
                        handled = self._shop_edge_dragging
                        self._shop_edge_pressing = False
                        self._shop_edge_drag_ready = False
                        self._shop_edge_dragging = False
                        self._shop_drag_dlg = None
                        if handled:
                            return True

        if self._shop_hint_label is not None:
            info = watched.property("shop_info") if watched is not None else None
            if isinstance(info, str) and info:
                if event.type() == QtCore.QEvent.Enter:
                    self._shop_hint_label.setText(info)
                    self._shop_hint_label.show()
                elif event.type() == QtCore.QEvent.Leave:
                    self._shop_hint_label.hide()
        return super().eventFilter(watched, event)

    def _is_shop_edge_press(self, dlg: QtWidgets.QDialog, pos: QtCore.QPoint) -> bool:
        margin = max(12, min(28, int(min(dlg.width(), dlg.height()) * 0.08)))
        return (
            pos.x() <= margin
            or pos.x() >= dlg.width() - margin
            or pos.y() <= margin
            or pos.y() >= dlg.height() - margin
        )

    def _enable_shop_edge_drag(self) -> None:
        if self._shop_edge_pressing:
            self._shop_edge_drag_ready = True

    def _move_shop_dialog_to(self, global_pos: QtCore.QPoint) -> None:
        dlg = self._shop_drag_dlg or self._shop_dialog
        if dlg is None:
            return
        pos = global_pos - self._shop_drag_offset
        screen = self.screen() or QtGui.QGuiApplication.primaryScreen()
        if screen is not None:
            sg = screen.availableGeometry()
            x = max(sg.left(), min(pos.x(), sg.right() - dlg.width() + 1))
            y = max(sg.top(), min(pos.y(), sg.bottom() - dlg.height() + 1))
            pos = QtCore.QPoint(x, y)
        dlg.move(pos)
        self._shop_manual_pos = QtCore.QPoint(pos)

    def _emit_wardrobe(self) -> None:
        menu = QtWidgets.QMenu(self)
        skin_root = self._skin_root
        candidates: list[str] = []
        if skin_root.exists():
            for p in skin_root.iterdir():
                if p.is_dir():
                    sid = p.name.strip()
                    if sid:
                        candidates.append(sid)
        candidates = sorted(set(candidates))
        if not candidates:
            action = menu.addAction("No skins found")
            action.setEnabled(False)
            menu.exec(QtGui.QCursor.pos())
            return

        for sid in candidates:
            pretty = sid.replace("_", " ").title()
            if sid == "default":
                price = 0
            elif sid == "horse":
                price = 120
            elif sid == "king":
                price = 160
            else:
                price = 100
            sid_l = sid.lower()
            equipped = sid == self._equipped_skin_id
            owned = sid_l in self._owned_skins
            if equipped:
                suffix = "(equipped)"
            elif owned:
                suffix = "(owned)"
            else:
                suffix = f"({price} pearls)" if price > 0 else "(free)"
            action = menu.addAction(f"{pretty} {suffix}")
            action.triggered.connect(
                lambda _checked=False, item_id=sid, p=price: self._on_shop_action and self._on_shop_action("skin", item_id, p)
            )
        menu.exec(QtGui.QCursor.pos())

    def _emit_sync(self) -> None:
        if self._on_sync_now is not None:
            self._on_sync_now()

    def _emit_quit(self) -> None:
        if self._on_quit is not None:
            try:
                self._on_quit()
            except Exception:
                pass
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
