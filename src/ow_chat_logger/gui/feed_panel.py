from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from ow_chat_logger.gui import theme as T
from ow_chat_logger.gui.backend_bridge import FeedEntry

_MAX_LINES = 2000


class FeedPanel(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(
            parent,
            fg_color=T.BG_CARD,
            corner_radius=T.R_CARD,
            border_width=0,
        )
        self._count = 0
        self._auto_scroll = tk.BooleanVar(value=True)
        self._build()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(14, 8))
        ctk.CTkLabel(
            header,
            text="Live Feed",
            font=T.font_title(),
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left")
        self._count_label = ctk.CTkLabel(
            header,
            text="0 messages",
            text_color=T.TEXT_MUTED,
            font=T.font_caption(),
        )
        self._count_label.pack(side="right")

        # Hairline divider under header
        ctk.CTkFrame(self, height=1, fg_color=T.BORDER_FAINT, corner_radius=0).pack(
            fill="x", padx=0
        )

        text_frame = tk.Frame(self, bg=T.pick(T.BG_CARD), highlightthickness=0, bd=0)
        text_frame.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        self._text_frame = text_frame

        scrollbar = ctk.CTkScrollbar(
            text_frame,
            button_color=T.BORDER_HOVER,
            button_hover_color=T.TEXT_MUTED,
            fg_color="transparent",
            width=10,
            corner_radius=5,
        )
        scrollbar.pack(side="right", fill="y", padx=(0, 2))

        self._text = tk.Text(
            text_frame,
            yscrollcommand=scrollbar.set,
            bg=T.pick(T.BG_CARD),
            fg=T.pick(T.TEXT_PRIMARY),
            font=T.font_mono(),
            wrap="word",
            state="disabled",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            selectbackground=T.pick(T.BG_SELECT),
            selectforeground=T.pick(T.TEXT_PRIMARY),
            insertbackground=T.pick(T.TEXT_PRIMARY),
            padx=12,
            pady=6,
            spacing1=1,
            spacing3=1,
        )
        self._text.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self._text.yview)

        self._refresh_text_tags()

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

    # ── Appearance-mode sync for tk.Text (not CTk-native) ─────────────────────

    def _set_appearance_mode(self, mode_string: str) -> None:
        super()._set_appearance_mode(mode_string)
        self._sync_native_colors()

    def _sync_native_colors(self) -> None:
        if not hasattr(self, "_text"):
            return
        card_bg = T.pick(T.BG_CARD)
        try:
            self._text_frame.configure(bg=card_bg)
        except Exception:
            pass
        self._text.configure(
            bg=card_bg,
            fg=T.pick(T.TEXT_PRIMARY),
            selectbackground=T.pick(T.BG_SELECT),
            selectforeground=T.pick(T.TEXT_PRIMARY),
            insertbackground=T.pick(T.TEXT_PRIMARY),
        )
        self._refresh_text_tags()

    def _refresh_text_tags(self) -> None:
        self._text.tag_config("team", foreground=T.pick(T.CHAT_TEAM))
        self._text.tag_config("all", foreground=T.pick(T.CHAT_ALL))
        self._text.tag_config("hero", foreground=T.pick(T.CHAT_HERO))
        self._text.tag_config("ts", foreground=T.pick(T.CHAT_TS))

    # ── Message append / clear ────────────────────────────────────────────────

    def append_message(self, entry: FeedEntry) -> None:
        self._count += 1
        self._count_label.configure(
            text=f"{self._count} message{'s' if self._count != 1 else ''}"
        )

        ts = entry.timestamp.split(" ")[-1]  # keep only HH:MM:SS

        if entry.category == "hero":
            tag = "hero"
            ts_prefix = f"{ts} "
            body = f"{'HERO':>4} {entry.player} / {entry.text}\n"
        else:
            ct = entry.chat_type.lower()
            tag = ct if ct in ("team", "all") else "all"
            ts_prefix = f"{ts} "
            body = f"{entry.chat_type.upper():>4} {entry.player}: {entry.text}\n"

        self._text.configure(state="normal")
        self._text.insert("end", ts_prefix, "ts")
        self._text.insert("end", body, tag)

        lines = int(self._text.index("end-1c").split(".")[0])
        if lines > _MAX_LINES:
            self._text.delete("1.0", f"{lines - _MAX_LINES}.0")

        self._text.configure(state="disabled")

        if self._auto_scroll.get():
            self._text.see("end")

    def clear(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")
        self._count = 0
        self._count_label.configure(text="0 messages")
