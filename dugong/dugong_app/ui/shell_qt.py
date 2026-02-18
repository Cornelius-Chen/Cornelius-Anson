from __future__ import annotations

import math
import sys
import tkinter as tk
from collections.abc import Callable
from pathlib import Path


def apply_transparency(root: tk.Tk, transparent_key_color: str) -> dict:
    """Cross-platform transparency setup with mac-safe fallback."""
    info = {"mode": "fallback", "bg": transparent_key_color}

    try:
        if sys.platform == "darwin":
            # macOS fallback: keep opaque background for stable PNG rendering.
            root.wm_attributes("-alpha", 1.0)
            root.configure(bg=transparent_key_color)
            return {"mode": "mac_fallback_opaque", "bg": transparent_key_color}

        if sys.platform.startswith("win"):
            root.attributes("-transparentcolor", transparent_key_color)
            root.configure(bg=transparent_key_color)
            return {"mode": "win", "bg": transparent_key_color}
    except Exception:
        pass

    try:
        root.attributes("-alpha", 0.98)
    except Exception:
        pass

    return info


class DugongShell:
    """
    UI contract (kept stable):
      - update_view(sprite, state_text, bubble)
      - schedule_every(seconds, callback)
      - run()
    """

    def __init__(
        self,
        on_mode_change: Callable[[str], None],
        on_click: Callable[[], None],
        on_manual_ping: Callable[[str], None] | None = None,
        on_sync_now: Callable[[], None] | None = None,
    ) -> None:
        self._on_mode_change = on_mode_change
        self._on_click = on_click
        self._on_manual_ping = on_manual_ping
        self._on_sync_now = on_sync_now

        self._pet_frames: list[tk.PhotoImage] = []
        self._pet_frame_idx = 0
        self._pet_anim_job: str | None = None
        self._pet_anim_ms = 140
        self._pet_max_width = 150
        self._pet_max_height = 105

        self.root = tk.Tk()
        self.root.title("Dugong V1")
        self.root.geometry("400x250+120+120")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        transparent_key = "#eaf4ff"
        t = apply_transparency(self.root, transparent_key)
        self.BG = t["bg"]
        print("[UI] platform:", sys.platform, "transparency:", t)

        self._drag_origin_x = 0
        self._drag_origin_y = 0

        # Root stage
        self.stage = tk.Frame(self.root, bd=0, relief=tk.FLAT, bg=self.BG)
        self.stage.pack(fill=tk.BOTH, expand=True)

        # Layer 1: pet layer
        self.pet_layer = tk.Frame(self.stage, bg=self.BG, width=220, height=120)
        self.pet_layer.pack(pady=(8, 0))
        self.pet_layer.pack_propagate(False)

        self.pet_label = tk.Label(self.pet_layer, text="", bg=self.BG, font=("TkDefaultFont", 48))
        self.pet_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        self._load_pet_frames()
        if not self._pet_frames:
            self.pet_label.configure(text="🦭")
        self._start_pet_animation()

        # Layer 2: text/info layer
        self.text_layer = tk.Frame(self.stage, bg=self.BG)
        self.text_layer.pack(fill=tk.X)

        self.title_label = tk.Label(self.text_layer, text="Dugong", bg=self.BG, font=("TkDefaultFont", 12, "bold"))
        self.title_label.pack(pady=(0, 2))

        self.state_label = tk.Label(self.text_layer, text="state", bg=self.BG, font=("TkFixedFont", 10))
        self.state_label.pack(pady=1)

        self.bubble_label = tk.Label(
            self.text_layer,
            text="",
            bg=self.BG,
            fg="#174a7a",
            wraplength=320,
            justify="center",
        )
        self.bubble_label.pack(pady=(3, 6))

        # Layer 3: controls layer
        control_bg = self.BG if sys.platform == "darwin" else "#0f2033"
        self.control_layer = tk.Frame(self.stage, bg=control_bg)
        self.control_layer.pack(side=tk.BOTTOM, pady=8)

        self._mk_option_btn("study").pack(side=tk.LEFT, padx=6, pady=6)
        self._mk_option_btn("chill").pack(side=tk.LEFT, padx=6, pady=6)
        self._mk_option_btn("rest").pack(side=tk.LEFT, padx=6, pady=6)
        self._mk_ping_btn().pack(side=tk.LEFT, padx=6, pady=6)
        self._mk_sync_btn().pack(side=tk.LEFT, padx=6, pady=6)

        # Context menu
        self._menu = tk.Menu(self.root, tearoff=0)
        self._menu.add_command(label="study", command=lambda: self._emit_mode("study"))
        self._menu.add_command(label="chill", command=lambda: self._emit_mode("chill"))
        self._menu.add_command(label="rest", command=lambda: self._emit_mode("rest"))
        self._menu.add_command(label="manual ping", command=self._emit_ping)
        self._menu.add_command(label="sync now", command=self._emit_sync_now)
        self._menu.add_separator()
        self._menu.add_command(label="quit", command=self.root.destroy)

        # Bind drag + click
        widgets = [self.stage, self.pet_layer, self.pet_label, self.text_layer, self.title_label, self.state_label, self.bubble_label, self.control_layer]
        for w in widgets:
            self._bind_drag(w)
            w.bind("<Button-1>", self._handle_click)
            self._bind_context_menu(w)

    def _mk_option_btn(self, mode: str) -> tk.Button:
        return tk.Button(
            self.control_layer,
            text=mode,
            command=lambda m=mode: self._emit_mode(m),
            bd=0,
            fg="white",
            bg="#1d3a57",
            activebackground="#2a577f",
            activeforeground="white",
            padx=6,
            pady=4,
            cursor="hand2",
        )

    def _mk_ping_btn(self) -> tk.Button:
        return tk.Button(
            self.control_layer,
            text="ping",
            command=self._emit_ping,
            bd=0,
            fg="white",
            bg="#275e44",
            activebackground="#2f7f5d",
            activeforeground="white",
            padx=6,
            pady=4,
            cursor="hand2",
        )

    def _mk_sync_btn(self) -> tk.Button:
        return tk.Button(
            self.control_layer,
            text="sync",
            command=self._emit_sync_now,
            bd=0,
            fg="white",
            bg="#6b4f1f",
            activebackground="#8a672a",
            activeforeground="white",
            padx=6,
            pady=4,
            cursor="hand2",
        )

    def _load_pet_frames(self) -> None:
        assets_dir = Path(__file__).resolve().parent / "assets"
        frame_names = ["seal_1.png", "seal_2.png", "seal_3.png"]

        frames: list[tk.PhotoImage] = []
        for name in frame_names:
            frame_path = assets_dir / name
            if not frame_path.exists():
                continue
            try:
                raw = tk.PhotoImage(file=str(frame_path))
                frames.append(self._fit_frame(raw, self._pet_max_width, self._pet_max_height))
            except tk.TclError:
                continue

        self._pet_frames = frames
        if self._pet_frames:
            self.pet_label.configure(image=self._pet_frames[0], text="")
            self.pet_label.image = self._pet_frames[0]

    def _fit_frame(self, frame: tk.PhotoImage, max_w: int, max_h: int) -> tk.PhotoImage:
        w = max(1, frame.width())
        h = max(1, frame.height())
        scale = max(w / max_w, h / max_h, 1.0)
        if scale <= 1.0:
            return frame
        factor = int(math.ceil(scale))
        return frame.subsample(factor, factor)

    def _start_pet_animation(self) -> None:
        if len(self._pet_frames) < 2:
            return

        def loop() -> None:
            self._pet_frame_idx = (self._pet_frame_idx + 1) % len(self._pet_frames)
            frame = self._pet_frames[self._pet_frame_idx]
            self.pet_label.configure(image=frame, text="")
            self.pet_label.image = frame
            self._pet_anim_job = self.root.after(self._pet_anim_ms, loop)

        self._pet_anim_job = self.root.after(self._pet_anim_ms, loop)

    def _bind_drag(self, widget: tk.Widget) -> None:
        widget.bind("<ButtonPress-1>", self._drag_start)
        widget.bind("<B1-Motion>", self._drag_move)

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_origin_x = event.x
        self._drag_origin_y = event.y

    def _drag_move(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + event.x - self._drag_origin_x
        y = self.root.winfo_y() + event.y - self._drag_origin_y
        self.root.geometry(f"+{x}+{y}")

    def _bind_context_menu(self, widget: tk.Widget) -> None:
        widget.bind("<Button-2>", self._open_menu)
        widget.bind("<Button-3>", self._open_menu)
        widget.bind("<Control-Button-1>", self._open_menu)

    def _open_menu(self, event: tk.Event) -> None:
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def _handle_click(self, _event: tk.Event) -> None:
        self._on_click()

    def _emit_mode(self, mode: str) -> None:
        self._on_mode_change(mode)

    def _emit_ping(self) -> None:
        if self._on_manual_ping is not None:
            self._on_manual_ping("checkin")

    def _emit_sync_now(self) -> None:
        if self._on_sync_now is not None:
            self._on_sync_now()

    def schedule_every(self, seconds: int, callback: Callable[[], None]) -> None:
        def loop() -> None:
            callback()
            self.root.after(seconds * 1000, loop)

        self.root.after(seconds * 1000, loop)

    def update_view(self, sprite: str, state_text: str, bubble: str | None = None) -> None:
        if not self._pet_frames:
            self.pet_label.configure(text=sprite)
        self.state_label.configure(text=state_text)

        if bubble is not None:
            self.bubble_label.configure(text=bubble)
            self.root.after(2500, lambda: self.bubble_label.configure(text=""))

    def run(self) -> None:
        self.root.mainloop()
