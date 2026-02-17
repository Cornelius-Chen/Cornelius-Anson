from __future__ import annotations

import tkinter as tk
from collections.abc import Callable


class DugongShell:
    def __init__(
        self,
        on_mode_change: Callable[[str], None],
        on_click: Callable[[], None],
    ) -> None:
        self._on_mode_change = on_mode_change
        self._on_click = on_click

        self.root = tk.Tk()
        self.root.title("Dugong V1")
        self.root.geometry("260x220+120+120")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self._drag_origin_x = 0
        self._drag_origin_y = 0
        self._dragging = False
        self._hide_job: str | None = None

        self.frame = tk.Frame(self.root, bd=1, relief=tk.SOLID, bg="#eaf4ff")
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Title
        self.title_label = tk.Label(
            self.frame, text="Dugong", bg="#eaf4ff", font=("TkDefaultFont", 12, "bold")
        )
        self.title_label.pack(pady=(10, 2))

        # BIG PET EMOJI (NEW)
        self.pet_label = tk.Label(
            self.frame, text="🦭", bg="#eaf4ff", font=("TkDefaultFont", 48)
        )
        self.pet_label.pack(pady=(2, 2))

        # State line
        self.state_label = tk.Label(
            self.frame, text="state", bg="#eaf4ff", font=("TkFixedFont", 10)
        )
        self.state_label.pack(pady=2)

        # Bubble
        self.bubble_label = tk.Label(
            self.frame,
            text="",
            bg="#eaf4ff",
            fg="#174a7a",
            wraplength=240,
            justify="center",
        )
        self.bubble_label.pack(pady=(6, 8))

        # ---- Hover Action Bar (study/chill/rest) ----
        self.option_bar = tk.Frame(self.frame, bg="#0f2033")
        self.option_bar.place_forget()

        self._mk_option_btn("study").pack(side=tk.LEFT, padx=6, pady=6)
        self._mk_option_btn("chill").pack(side=tk.LEFT, padx=6, pady=6)
        self._mk_option_btn("rest").pack(side=tk.LEFT, padx=6, pady=6)

        # Bind drag + click on all main widgets
        for w in (self.frame, self.title_label, self.pet_label, self.state_label, self.bubble_label):
            self._bind_drag(w)
            w.bind("<Button-1>", self._handle_click)

        # Hover show/hide (debounced)
        for w in (self.root, self.frame, self.title_label, self.pet_label, self.state_label, self.bubble_label, self.option_bar):
            w.bind("<Enter>", lambda _e: self._show_option_bar())
            w.bind("<Leave>", lambda _e: self._schedule_hide())

        # Backup context menu (optional)
        self._menu = tk.Menu(self.root, tearoff=0)
        self._menu.add_command(label="study", command=lambda: self._emit_mode("study"))
        self._menu.add_command(label="chill", command=lambda: self._emit_mode("chill"))
        self._menu.add_command(label="rest", command=lambda: self._emit_mode("rest"))
        self._menu.add_separator()
        self._menu.add_command(label="quit", command=self.root.destroy)
        self._bind_context_menu(self.frame)

        self.root.bind("<Configure>", lambda _e: self._reposition_option_bar())

    # ---------- Action Bar ----------
    def _mk_option_btn(self, mode: str) -> tk.Button:
        return tk.Button(
            self.option_bar,
            text=mode,
            command=lambda m=mode: self._emit_mode(m),
            bd=0,
            fg="white",
            bg="#1d3a57",
            activebackground="#2a577f",
            activeforeground="white",
            padx=10,
            pady=4,
            cursor="hand2",
        )

    def _place_option_bar(self) -> None:
        self.option_bar.update_idletasks()
        w = self.option_bar.winfo_reqwidth()
        h = self.option_bar.winfo_reqheight()
        fw = self.frame.winfo_width()
        fh = self.frame.winfo_height()
        x = max(0, (fw - w) // 2)
        y = max(0, fh - h - 8)
        self.option_bar.place(x=x, y=y)

    def _show_option_bar(self) -> None:
        if self._dragging:
            return
        self._cancel_hide_job()
        self._place_option_bar()
        self.option_bar.lift()

    def _schedule_hide(self, delay_ms: int = 180) -> None:
        self._cancel_hide_job()
        self._hide_job = self.root.after(delay_ms, self._hide_if_pointer_outside)

    def _cancel_hide_job(self) -> None:
        if self._hide_job is not None:
            try:
                self.root.after_cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None

    def _hide_if_pointer_outside(self) -> None:
        try:
            px = self.root.winfo_pointerx()
            py = self.root.winfo_pointery()
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
            inside = (rx <= px <= rx + rw) and (ry <= py <= ry + rh)
        except Exception:
            inside = False
        if not inside:
            self.option_bar.place_forget()

    def _reposition_option_bar(self) -> None:
        # keep it bottom-centered if visible
        try:
            if self.option_bar.winfo_ismapped():
                self._place_option_bar()
        except Exception:
            pass

    # ---------- Drag / Menu / Click ----------
    def _bind_drag(self, widget: tk.Widget) -> None:
        widget.bind("<ButtonPress-1>", self._drag_start)
        widget.bind("<B1-Motion>", self._drag_move)
        widget.bind("<ButtonRelease-1>", self._drag_end)

    def _drag_start(self, event: tk.Event) -> None:
        self._dragging = True
        self.option_bar.place_forget()
        self._drag_origin_x = event.x
        self._drag_origin_y = event.y

    def _drag_move(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + event.x - self._drag_origin_x
        y = self.root.winfo_y() + event.y - self._drag_origin_y
        self.root.geometry(f"+{x}+{y}")

    def _drag_end(self, _event: tk.Event) -> None:
        self._dragging = False
        self._show_option_bar()

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

    # ---------- Controller contract ----------
    def schedule_every(self, seconds: int, callback: Callable[[], None]) -> None:
        def loop() -> None:
            callback()
            self.root.after(seconds * 1000, loop)
        self.root.after(seconds * 1000, loop)

    def update_view(self, sprite: str, state_text: str, bubble: str | None = None) -> None:
        # sprite is now emoji (e.g. "🦭", "💤🦭")
        self.pet_label.configure(text=sprite)
        self.state_label.configure(text=state_text)

        if bubble is not None:
            self.bubble_label.configure(text=bubble)
            self.root.after(2500, lambda: self.bubble_label.configure(text=""))

    def run(self) -> None:
        self.root.mainloop()

