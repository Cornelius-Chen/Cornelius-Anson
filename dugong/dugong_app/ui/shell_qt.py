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
        self.root.geometry("240x150+120+120")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self._drag_origin_x = 0
        self._drag_origin_y = 0

        self.frame = tk.Frame(self.root, bd=1, relief=tk.SOLID, bg="#eaf4ff")
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.title_label = tk.Label(self.frame, text="Dugong", bg="#eaf4ff", font=("Segoe UI", 11, "bold"))
        self.title_label.pack(pady=(8, 2))

        self.state_label = tk.Label(self.frame, text="state", bg="#eaf4ff", font=("Consolas", 9))
        self.state_label.pack(pady=2)

        self.bubble_label = tk.Label(self.frame, text="", bg="#eaf4ff", fg="#174a7a", wraplength=220)
        self.bubble_label.pack(pady=(6, 8))

        self._bind_drag(self.frame)
        self._bind_drag(self.title_label)
        self._bind_drag(self.state_label)
        self._bind_drag(self.bubble_label)

        self.frame.bind("<Button-1>", self._handle_click)
        self.title_label.bind("<Button-1>", self._handle_click)
        self.state_label.bind("<Button-1>", self._handle_click)
        self.bubble_label.bind("<Button-1>", self._handle_click)

        self._menu = tk.Menu(self.root, tearoff=0)
        self._menu.add_command(label="study", command=lambda: self._on_mode_change("study"))
        self._menu.add_command(label="chill", command=lambda: self._on_mode_change("chill"))
        self._menu.add_command(label="rest", command=lambda: self._on_mode_change("rest"))
        self._menu.add_separator()
        self._menu.add_command(label="quit", command=self.root.destroy)

    def _bind_drag(self, widget: tk.Widget) -> None:
        widget.bind("<ButtonPress-1>", self._drag_start)
        widget.bind("<B1-Motion>", self._drag_move)
        self._bind_context_menu(widget)

    def _bind_context_menu(self, widget: tk.Widget) -> None:
        # Cross-platform context menu bindings:
        # - Windows/Linux: Button-3
        # - macOS Tk variants: Button-2 or Control-Button-1
        widget.bind("<Button-2>", self._open_menu)
        widget.bind("<Button-3>", self._open_menu)
        widget.bind("<Control-Button-1>", self._open_menu)

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_origin_x = event.x
        self._drag_origin_y = event.y

    def _drag_move(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + event.x - self._drag_origin_x
        y = self.root.winfo_y() + event.y - self._drag_origin_y
        self.root.geometry(f"+{x}+{y}")

    def _open_menu(self, event: tk.Event) -> None:
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def _handle_click(self, _event: tk.Event) -> None:
        self._on_click()

    def schedule_every(self, seconds: int, callback: Callable[[], None]) -> None:
        def loop() -> None:
            callback()
            self.root.after(seconds * 1000, loop)

        self.root.after(seconds * 1000, loop)

    def update_view(self, sprite: str, state_text: str, bubble: str | None = None) -> None:
        self.title_label.configure(text=f"Dugong [{sprite}]")
        self.state_label.configure(text=state_text)
        if bubble is not None:
            self.bubble_label.configure(text=bubble)
            self.root.after(2500, lambda: self.bubble_label.configure(text=""))

    def run(self) -> None:
        self.root.mainloop()
