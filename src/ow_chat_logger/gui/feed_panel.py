from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from ow_chat_logger.gui.backend_bridge import FeedEntry

_COLOR_BG = "#0d0d1a"
_COLOR_TEAM = "#5BC8F5"
_COLOR_ALL = "#FFAA00"
_COLOR_HERO = "#5FAF5F"
_COLOR_TS = "#666666"
_COLOR_FG = "#cccccc"

_MAX_LINES = 2000


class FeedPanel(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent, fg_color=_COLOR_BG, corner_radius=6)
        self._count = 0
        self._auto_scroll = tk.BooleanVar(value=True)
        self._build()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="#0f3460", corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(
            header,
            text="LIVE FEED",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_COLOR_TEAM,
        ).pack(side="left", padx=10, pady=5)
        self._count_label = ctk.CTkLabel(
            header, text="0 messages", text_color="#888888", font=ctk.CTkFont(size=10)
        )
        self._count_label.pack(side="right", padx=10)

        text_frame = tk.Frame(self, bg=_COLOR_BG)
        text_frame.pack(fill="both", expand=True, padx=2, pady=(2, 0))

        scrollbar = tk.Scrollbar(text_frame, bg="#1a1a2e", troughcolor="#0d0d1a", width=12)
        scrollbar.pack(side="right", fill="y")

        self._text = tk.Text(
            text_frame,
            yscrollcommand=scrollbar.set,
            bg=_COLOR_BG,
            fg=_COLOR_FG,
            font=("Consolas", 10),
            wrap="word",
            state="disabled",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            selectbackground="#1a4a8a",
            insertbackground=_COLOR_FG,
            padx=6,
            pady=4,
        )
        self._text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._text.yview)

        self._text.tag_config("team", foreground=_COLOR_TEAM)
        self._text.tag_config("all", foreground=_COLOR_ALL)
        self._text.tag_config("hero", foreground=_COLOR_HERO)
        self._text.tag_config("ts", foreground=_COLOR_TS)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=8, pady=(4, 6))
        ctk.CTkCheckBox(
            footer,
            text="Auto-scroll",
            variable=self._auto_scroll,
            checkbox_width=16,
            checkbox_height=16,
            font=ctk.CTkFont(size=11),
        ).pack(side="left")

    def append_message(self, entry: FeedEntry) -> None:
        self._count += 1
        self._count_label.configure(
            text=f"{self._count} message{'s' if self._count != 1 else ''}"
        )

        ts = entry.timestamp.split(" ")[-1]  # keep only HH:MM:SS

        if entry.category == "hero":
            tag = "hero"
            ts_prefix = f"{ts} | "
            body = f"{'HERO':<4} | {entry.player} / {entry.text}\n"
        else:
            ct = entry.chat_type.lower()
            tag = ct if ct in ("team", "all") else "all"
            ts_prefix = f"{ts} | "
            body = f"{entry.chat_type.upper():<4} | {entry.player}: {entry.text}\n"

        self._text.configure(state="normal")
        self._text.insert("end", ts_prefix, "ts")
        self._text.insert("end", body, tag)

        # Trim oldest lines if over cap
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
