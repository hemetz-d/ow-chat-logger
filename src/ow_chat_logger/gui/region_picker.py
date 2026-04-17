"""Full-screen drag-to-select overlay for picking a capture region.

Opens a translucent, borderless `Toplevel` spanning the primary screen.
User drags a rectangle; on release the [x, y, w, h] is delivered via a
callback and the overlay closes. Escape cancels.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from ow_chat_logger.gui import theme as T


class RegionPickerOverlay(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        on_pick: Callable[[int, int, int, int], None],
    ) -> None:
        super().__init__(parent)
        self._on_pick = on_pick
        self._start: tuple[int, int] | None = None
        self._rect_id: int | None = None
        self._hint_id: int | None = None

        # Fullscreen, borderless, dim
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.35)
        except tk.TclError:
            pass
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")

        accent = T.pick(T.ACCENT)
        self._canvas = tk.Canvas(
            self,
            bg=T.pick(T.TEXT_PRIMARY),
            highlightthickness=0,
            cursor="crosshair",
        )
        self._canvas.pack(fill="both", expand=True)
        self._accent = accent

        # Crosshair hint
        self._hint_id = self._canvas.create_text(
            sw // 2,
            sh // 2,
            text="Drag to select capture region   ·   Esc to cancel",
            fill=T.pick(T.ACCENT_FG),
            font=(T.ui_family(), 18, "bold"),
        )

        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Escape>", lambda _e: self._cancel())

        self.focus_force()
        self.grab_set()

    def _on_press(self, event: tk.Event) -> None:
        self._start = (event.x_root, event.y_root)
        if self._hint_id is not None:
            self._canvas.delete(self._hint_id)
            self._hint_id = None
        if self._rect_id is None:
            self._rect_id = self._canvas.create_rectangle(
                event.x,
                event.y,
                event.x,
                event.y,
                outline=self._accent,
                width=2,
                dash=(6, 4),
            )

    def _on_drag(self, event: tk.Event) -> None:
        if self._start is None or self._rect_id is None:
            return
        x0 = self._start[0] - self.winfo_rootx()
        y0 = self._start[1] - self.winfo_rooty()
        self._canvas.coords(self._rect_id, x0, y0, event.x, event.y)

    def _on_release(self, event: tk.Event) -> None:
        if self._start is None:
            return
        x0, y0 = self._start
        x1, y1 = event.x_root, event.y_root
        x, y = min(x0, x1), min(y0, y1)
        w, h = abs(x1 - x0), abs(y1 - y0)
        # Ignore trivial drags (likely misclicks)
        if w < 20 or h < 20:
            self._cancel()
            return
        self._close()
        self._on_pick(x, y, w, h)

    def _cancel(self) -> None:
        self._close()

    def _close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
