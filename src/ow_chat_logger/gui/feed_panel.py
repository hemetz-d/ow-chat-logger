from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from ow_chat_logger.gui import icons as I
from ow_chat_logger.gui import theme as T
from ow_chat_logger.gui.backend_bridge import FeedEntry
from ow_chat_logger.gui.color_utils import hsv_bounds_to_hex
from ow_chat_logger.gui.config_io import load_ui_config

_MAX_ROWS = 500


# ── Message row widget ────────────────────────────────────────────────────────

class MessageRow(ctk.CTkFrame):
    """Compact chat row: channel dot, player, message (wraps), timestamp."""

    def __init__(
        self,
        parent: tk.Widget,
        entry: FeedEntry,
        dot_color: str | None,
    ) -> None:
        super().__init__(
            parent,
            fg_color="transparent",
            corner_radius=0,
        )
        self._entry = entry
        self._build(dot_color)
        self.bind("<Configure>", self._on_row_configure)
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))

    def _build(self, dot_color: str | None) -> None:
        self.grid_columnconfigure(1, weight=1)

        # Leading channel dot — tracks the user's chosen team/all chat color.
        self._dot = ctk.CTkLabel(
            self,
            text="●",
            text_color=dot_color if dot_color else T.pick(T.TEXT_DIM),
            font=ctk.CTkFont(size=10),
        )
        self._dot.grid(row=0, column=0, padx=(20, 8), pady=1, sticky="w")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=0, column=1, sticky="ew", pady=1)

        ctk.CTkLabel(
            content,
            text=self._entry.player or "—",
            text_color=T.TEXT_PRIMARY,
            font=T.font_button(),
            anchor="w",
        ).pack(side="left")

        body = ctk.CTkLabel(
            content,
            text=self._entry.text,
            text_color=T.TEXT_SECONDARY,
            font=T.font_body(),
            anchor="w",
            justify="left",
            wraplength=600,
        )
        body.pack(side="left", padx=(10, 0), fill="x", expand=True)
        self._body = body

        ts = self._entry.timestamp.split(" ")[-1] if self._entry.timestamp else ""
        ctk.CTkLabel(
            self,
            text=ts,
            text_color=T.TEXT_MUTED,
            font=T.font_caption(),
            anchor="e",
        ).grid(row=0, column=2, sticky="ne", padx=(10, 14), pady=3)

    def set_dot_color(self, color: str | None) -> None:
        self._dot.configure(
            text_color=color if color else T.pick(T.TEXT_DIM)
        )

    @property
    def chat_type(self) -> str:
        return (self._entry.chat_type or "").lower()

    def _on_row_configure(self, event: tk.Event) -> None:
        # Row width − dot column (~36) − player estimate (~120) − ts (~70)
        available = event.width - 36 - 120 - 70
        if available > 80:
            self._body.configure(wraplength=available)

    def _set_hover(self, on: bool) -> None:
        self.configure(fg_color=T.ACCENT_SUBTLE if on else "transparent")


# ── Hero event row — stands out from real chat ────────────────────────────────

class HeroRow(ctk.CTkFrame):
    """Hero-pick log event — deliberately not styled like chat."""

    def __init__(self, parent: tk.Widget, entry: FeedEntry) -> None:
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self._build(entry)

    def _build(self, entry: FeedEntry) -> None:
        self.grid_columnconfigure(1, weight=1)

        # Small leading marker so it reads as a log line, not a chat message
        ctk.CTkLabel(
            self,
            text="•",
            text_color=T.CHAT_HERO,
            font=T.font_body(),
        ).grid(row=0, column=0, padx=(28, 0), pady=3, sticky="w")

        player = entry.player or "—"
        hero = entry.text or "—"
        text = f"{player}  →  {hero}"
        ctk.CTkLabel(
            self,
            text=text,
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(family=T.ui_family(), size=12, slant="italic"),
            anchor="w",
        ).grid(row=0, column=1, padx=(8, 0), pady=3, sticky="w")

        ts = entry.timestamp.split(" ")[-1] if entry.timestamp else ""
        ctk.CTkLabel(
            self,
            text=ts,
            text_color=T.TEXT_DIM,
            font=T.font_caption(),
            anchor="e",
        ).grid(row=0, column=2, padx=(10, 14), pady=3, sticky="e")


def _load_chat_colors() -> dict[str, str]:
    """Resolve the user's picked team/all colors (hex) from saved config."""
    cfg = load_ui_config()
    out: dict[str, str] = {}
    for key in ("team", "all"):
        try:
            out[key] = hsv_bounds_to_hex(
                cfg[f"{key}_hsv_lower"], cfg[f"{key}_hsv_upper"]
            )
        except Exception:
            out[key] = T.pick(T.CHAT_TEAM if key == "team" else T.CHAT_ALL)
    return out


# ── Feed panel ────────────────────────────────────────────────────────────────

class FeedPanel(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(
            parent,
            fg_color=T.BG_CARD,
            corner_radius=T.R_CARD,
            border_width=0,
        )
        self._count = 0
        self._rows: list[tk.Widget] = []
        self._auto_scroll = tk.BooleanVar(value=True)
        self._empty_frame: ctk.CTkFrame | None = None
        self._jump_pill: ctk.CTkButton | None = None
        self._chat_colors: dict[str, str] = _load_chat_colors()
        self._build()
        self._show_empty_state()

    def refresh_chat_colors(self) -> None:
        """Re-read the user's team/all colors and update existing dots."""
        self._chat_colors = _load_chat_colors()
        for row in self._rows:
            if isinstance(row, MessageRow):
                row.set_dot_color(self._chat_colors.get(row.chat_type))

    def _dot_color_for(self, entry: FeedEntry) -> str | None:
        ct = (entry.chat_type or "").lower()
        return self._chat_colors.get(ct)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(14, 8))
        ctk.CTkLabel(
            header,
            text="Live Feed",
            font=T.font_title(),
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left")

        self._count_pill = ctk.CTkLabel(
            header,
            text="0",
            text_color=T.ACCENT,
            fg_color=T.ACCENT_SUBTLE,
            font=T.font_badge(),
            corner_radius=T.R_BADGE,
            padx=8,
            pady=2,
        )
        self._count_pill.pack(side="right")

        # Hairline divider under header
        ctk.CTkFrame(self, height=1, fg_color=T.BORDER_FAINT, corner_radius=0).pack(
            fill="x", padx=0
        )

        # Body container holds scrollable list + overlays (empty state, pill)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=0, pady=(0, 0))
        self._body = body

        self._list = ctk.CTkScrollableFrame(
            body,
            fg_color=T.BG_CARD,
            corner_radius=0,
            scrollbar_button_color=T.BORDER_HOVER,
            scrollbar_button_hover_color=T.TEXT_MUTED,
        )
        self._list.pack(fill="both", expand=True, padx=0, pady=0)

        # Jump-to-latest floating pill (hidden initially)
        self._jump_pill = ctk.CTkButton(
            body,
            text="New messages",
            image=I.icon("jump_down", 14, color=T.ACCENT_FG),
            compound="left",
            width=130,
            height=28,
            corner_radius=14,
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            text_color=T.ACCENT_FG,
            font=T.font_small(),
            command=self._on_jump_click,
        )
        # Not placed yet — _maybe_show_jump_pill handles visibility

        # Footer: auto-scroll checkbox
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(6, 12))
        ctk.CTkCheckBox(
            footer,
            text="Auto-scroll",
            variable=self._auto_scroll,
            checkbox_width=16,
            checkbox_height=16,
            corner_radius=4,
            font=T.font_small(),
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            border_color=T.BORDER_HOVER,
            border_width=1,
            text_color=T.TEXT_SECONDARY,
        ).pack(side="left")

        # Periodically poll scroll position for jump-pill visibility
        self.after(400, self._poll_scroll)

    # ── Empty state ───────────────────────────────────────────────────────────

    def _show_empty_state(self) -> None:
        if self._empty_frame is not None:
            return
        frame = ctk.CTkFrame(self._list, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=60)

        bubble = ctk.CTkLabel(
            frame,
            text="",
            image=I.icon("message_square", 48, color=T.TEXT_DIM),
        )
        bubble.pack(pady=(20, 12))
        ctk.CTkLabel(
            frame,
            text="Waiting for chat…",
            font=T.font_button(),
            text_color=T.TEXT_SECONDARY,
        ).pack()
        ctk.CTkLabel(
            frame,
            text="Press Start to begin capturing.",
            font=T.font_small(),
            text_color=T.TEXT_MUTED,
        ).pack(pady=(4, 0))
        self._empty_frame = frame

    def _hide_empty_state(self) -> None:
        if self._empty_frame is not None:
            self._empty_frame.destroy()
            self._empty_frame = None

    # ── Appearance-mode sync ──────────────────────────────────────────────────

    def _set_appearance_mode(self, mode_string: str) -> None:
        super()._set_appearance_mode(mode_string)
        # Children with tuple colors auto-update; nothing else to do here.

    # ── Message append / clear ────────────────────────────────────────────────

    def append_message(self, entry: FeedEntry) -> None:
        self._hide_empty_state()

        self._count += 1
        self._count_pill.configure(text=str(self._count))

        # Hairline divider above this row (except for the first row)
        if self._rows:
            divider = ctk.CTkFrame(
                self._list, height=1, fg_color=T.BORDER_FAINT, corner_radius=0
            )
            divider.pack(fill="x", padx=16)
            self._rows.append(divider)

        row: tk.Widget = (
            HeroRow(self._list, entry)
            if entry.category == "hero"
            else MessageRow(self._list, entry, self._dot_color_for(entry))
        )
        row.pack(fill="x")
        self._rows.append(row)

        # Trim oldest widgets if we exceed the cap
        while len(self._rows) > _MAX_ROWS * 2:
            old = self._rows.pop(0)
            old.destroy()

        # Auto-scroll
        if self._auto_scroll.get():
            self.after_idle(self._scroll_to_bottom)
        else:
            self._maybe_show_jump_pill()

    def clear(self) -> None:
        for w in self._rows:
            w.destroy()
        self._rows.clear()
        self._count = 0
        self._count_pill.configure(text="0")
        self._show_empty_state()
        self._hide_jump_pill()

    # ── Scroll / jump-to-latest ───────────────────────────────────────────────

    def _scroll_to_bottom(self) -> None:
        # Force pending geometry to settle so yview_moveto lands on the real
        # scrollregion, not a stale one from before the row was packed.
        try:
            self._list.update_idletasks()
        except tk.TclError:
            return
        canvas = getattr(self._list, "_parent_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(1.0)
        self._hide_jump_pill()

    def _at_bottom(self) -> bool:
        canvas = getattr(self._list, "_parent_canvas", None)
        if canvas is None:
            return True
        top, bottom = canvas.yview()
        return bottom >= 0.995 or top == 0.0 and bottom == 1.0

    def _maybe_show_jump_pill(self) -> None:
        if self._at_bottom():
            self._hide_jump_pill()
        else:
            self._show_jump_pill()

    def _show_jump_pill(self) -> None:
        if self._jump_pill is None:
            return
        self._jump_pill.place(relx=1.0, rely=1.0, x=-18, y=-14, anchor="se")

    def _hide_jump_pill(self) -> None:
        if self._jump_pill is None:
            return
        self._jump_pill.place_forget()

    def _on_jump_click(self) -> None:
        self._auto_scroll.set(True)
        self._scroll_to_bottom()

    def _poll_scroll(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self._maybe_show_jump_pill()
        self.after(400, self._poll_scroll)


