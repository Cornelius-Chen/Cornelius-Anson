from __future__ import annotations

import sys
from pathlib import Path
from collections.abc import Callable
from PySide6 import QtCore, QtGui, QtWidgets


class DugongShell:
    def __init__(
        self,
        on_mode_change: Callable[[str], None],
        on_click: Callable[[], None],
        on_manual_ping: Callable[[str], None] | None = None,
        on_sync_now: Callable[[], None] | None = None,
    ) -> None:
        self._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self._win = _DugongWindow(on_mode_change, on_click, on_manual_ping, on_sync_now)

    def schedule_every(self, seconds: int, callback: Callable[[], None]) -> None:
        timer = QtCore.QTimer(self._win)
        timer.setInterval(max(1, int(seconds * 1000)))
        timer.timeout.connect(callback)
        timer.start()
        self._win._timers.append(timer)

    def update_view(self, sprite: str, state_text: str, bubble: str | None = None) -> None:
        self._win.set_state_text(state_text)
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
    ) -> None:
        super().__init__()
        self._on_mode_change = on_mode_change
        self._on_click = on_click
        self._on_manual_ping = on_manual_ping
        self._on_sync_now = on_sync_now
        self._timers: list[QtCore.QTimer] = []

        # frameless + topmost + transparent window
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self._target_height = 260
        self._apply_screen_width()

        # drag
        self._dragging = False
        self._drag_offset = QtCore.QPoint(0, 0)

        # assets
        assets_dir = Path(__file__).resolve().parent / "assets"

        self._bg_src = QtGui.QPixmap(str(assets_dir / "bg_ocean.png"))
        if self._bg_src.isNull():
            raise RuntimeError("Failed to load bg image: bg_ocean.png")

        self._dugong_src = [
            QtGui.QPixmap(str(assets_dir / "seal_1.png")),
            QtGui.QPixmap(str(assets_dir / "seal_2.png")),
            QtGui.QPixmap(str(assets_dir / "seal_3.png")),
        ]
        if any(pm.isNull() for pm in self._dugong_src):
            raise RuntimeError("Failed to load seal_1/2/3.png")

        # animation sequence 1-2-3-2
        self._seq = [0, 1, 2, 1]
        self._seq_i = 0
        self._dugong_frame = self._dugong_src[self._seq[self._seq_i]]

        # speed controls
        self._dugong_anim_ms = 320   # dugong帧切换速度（越大越慢）
        self._bg_tick_ms = 16        # 背景刷新频率（16ms≈60fps，33ms≈30fps）
        self._bg_speed_px = 1.2      # 每次tick滚动多少像素（越大越快）
        self._bg_offset = 0.0

        # scaled caches (updated on resize)
        self._bg_scaled: QtGui.QPixmap | None = None
        self._dugong_scaled: list[QtGui.QPixmap] = []
        self._rebuild_scaled_pixmaps()

        # UI overlay: title/state/bubble + hover bar
        self._title = QtWidgets.QLabel("Dugong", self)
        self._title.setStyleSheet("color: rgba(255,255,255,210); font-size: 18px; font-weight: 700;")
        self._title.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

        self._state = QtWidgets.QLabel("state", self)
        self._state.setStyleSheet("color: rgba(255,255,255,210); font-size: 14px;")
        self._state.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

        self._bubble = QtWidgets.QLabel("", self)
        self._bubble.setWordWrap(True)
        self._bubble.setStyleSheet("""
            color: rgba(255,255,255,235);
            background: rgba(20,30,45,140);
            border-radius: 10px;
            padding: 8px 10px;
            font-size: 13px;
        """)
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
            b.setStyleSheet(f"""
                QPushButton {{
                    color: white;
                    background: {color};
                    border: none;
                    padding: 6px 12px;
                    border-radius: 10px;
                    font-weight: 700;
                }}
            """)
            b.clicked.connect(fn)
            return b

        lay.addWidget(mk_btn("study", "#1d3a57", lambda: self._emit_mode("study")))
        lay.addWidget(mk_btn("chill", "#1d3a57", lambda: self._emit_mode("chill")))
        lay.addWidget(mk_btn("rest",  "#1d3a57", lambda: self._emit_mode("rest")))
        lay.addWidget(mk_btn("ping",  "#275e44", self._emit_ping))
        lay.addWidget(mk_btn("sync",  "#6b4f1f", self._emit_sync))
        lay.addWidget(mk_btn("quit",  "#6a2c2c", self._emit_quit))
        self._bar.hide()

        self._hide_bar_timer = QtCore.QTimer(self)
        self._hide_bar_timer.setSingleShot(True)
        self._hide_bar_timer.timeout.connect(self._bar.hide)

        # timers
        self._dugong_timer = QtCore.QTimer(self)
        self._dugong_timer.setInterval(self._dugong_anim_ms)
        self._dugong_timer.timeout.connect(self._tick_dugong)
        self._dugong_timer.start()

        self._bg_timer = QtCore.QTimer(self)
        self._bg_timer.setInterval(self._bg_tick_ms)
        self._bg_timer.timeout.connect(self._tick_bg)
        self._bg_timer.start()

        self._layout_overlay()

    def _apply_screen_width(self) -> None:
        screen = QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(900, self._target_height)
            return
        geo = screen.availableGeometry()
        self.resize(max(900, geo.width()), self._target_height)

    # -------- scaling / layout ----------
    def _rebuild_scaled_pixmaps(self) -> None:
        h = self.height()
        # background: scale to window height
        self._bg_scaled = self._bg_src.scaledToHeight(
            max(1, h),
            QtCore.Qt.SmoothTransformation
        )
        # dugong: scale to ~55% of bg height (你可调)
        target_h = int(h * 0.55)
        self._dugong_scaled = [
            pm.scaledToHeight(max(1, target_h), QtCore.Qt.SmoothTransformation)
            for pm in self._dugong_src
        ]
        # refresh current frame
        self._dugong_frame = self._dugong_scaled[self._seq[self._seq_i]]

    def _layout_overlay(self) -> None:
        self._title.setGeometry(0, 8, self.width(), 26)
        self._state.setGeometry(0, self.height() - 28, self.width(), 20)

    def resizeEvent(self, _e: QtGui.QResizeEvent) -> None:
        self._rebuild_scaled_pixmaps()
        self._layout_overlay()
        if self._bar.isVisible():
            self._place_bar()
        self.update()

    def showEvent(self, e: QtGui.QShowEvent) -> None:
        self._apply_screen_width()
        super().showEvent(e)

    # -------- animation ticks ----------
    def _tick_dugong(self) -> None:
        self._seq_i = (self._seq_i + 1) % len(self._seq)
        self._dugong_frame = self._dugong_scaled[self._seq[self._seq_i]]
        self.update()

    def _tick_bg(self) -> None:
        if not self._bg_scaled:
            return
        bg_w = self._bg_scaled.width()
        if bg_w <= 0:
            return
        self._bg_offset = (self._bg_offset + self._bg_speed_px) % bg_w
        self.update()

    # -------- paint ----------
    def paintEvent(self, _e: QtGui.QPaintEvent) -> None:
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)

        # draw scrolling bg
        if self._bg_scaled:
            bg = self._bg_scaled
            bg_w = bg.width()
            off = int(self._bg_offset)
            x = -off
            while x < self.width():
                p.drawPixmap(x, 0, bg)
                x += bg_w

        # draw dugong centered
        if self._dugong_frame:
            pm = self._dugong_frame
            x = (self.width() - pm.width()) // 2
            y = (self.height() - pm.height()) // 2 + 10
            p.drawPixmap(x, y, pm)

    # -------- hover bar ----------
    def _place_bar(self) -> None:
        self._bar.adjustSize()
        w = self._bar.sizeHint().width()
        x = (self.width() - w) // 2
        y = self.height() - self._bar.height() - 8
        self._bar.setGeometry(x, y, w, self._bar.height())

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
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent) -> None:
        if self._dragging:
            self.move(e.globalPosition().toPoint() - self._drag_offset)
            e.accept()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.button() == QtCore.Qt.LeftButton:
            self._dragging = False
            try:
                self._on_click()
            except Exception:
                pass
            e.accept()

    # -------- controller hooks ----------
    def set_state_text(self, text: str) -> None:
        self._state.setText(text)

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
