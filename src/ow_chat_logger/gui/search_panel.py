from __future__ import annotations

import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from ow_chat_logger.gui import theme as T
from ow_chat_logger.log_search import (
    SearchResultSet,
    history_for_player,
    search_logs,
)

_DEBOUNCE_MS = 150
_MIN_QUERY_LEN = 3

# Segmented-button labels → (match_field, channel_filter) for search_logs.
# "Player" is the default: most searches start from "show me this player's
# messages", and matching on message text too would dilute results.
_FILTER_LABELS: list[str] = ["Player", "Team", "All chat", "Hero"]
_LABEL_TO_MODE: dict[str, tuple[str, str | None]] = {
    "Player": ("player", None),
    "Team": ("text", "team"),
    "All chat": ("text", "all"),
    # "Hero" = "show this player's hero picks" — match on player in the hero log.
    "Hero": ("player", "hero"),
}


class SearchView(ctk.CTkFrame):
    """In-place search view over persisted chat + hero CSV logs.

    Lives inside the main window as a sibling of ``FeedPanel``; the active
    view is toggled by :class:`MainTabs`. Two visual modes:
      * free-text   — entry + channel filter (default).
      * player-focused — focus chip; ``×`` returns to free-text.
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        chat_log_path: Path,
        hero_log_path: Path,
    ) -> None:
        super().__init__(
            master,
            fg_color=T.BG_CARD,
            corner_radius=T.R_CARD,
            border_width=0,
        )
        self._chat_log_path = chat_log_path
        self._hero_log_path = hero_log_path
        self._focused_player: str | None = None

        self._debounce_job: str | None = None
        self._last_query: str = ""

        self._build_ui()
        self._render_empty(
            f"Type at least {_MIN_QUERY_LEN} characters to search.",
            footer="",
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def focus_player(self, player: str) -> None:
        """Switch to player-focused mode for ``player``'s history."""
        cleaned = player.strip()
        if not cleaned:
            return
        self._focused_player = cleaned
        self._rebuild_top_bar()
        self._run_player_history()

    def reset_to_free_text(self) -> None:
        self._focused_player = None
        self._last_query = ""
        self._rebuild_top_bar()
        self._render_empty(
            f"Type at least {_MIN_QUERY_LEN} characters to search.",
            footer="",
        )
        self.focus_input()

    def focus_input(self) -> None:
        """Put keyboard focus on the query entry (no-op in player mode)."""
        entry = getattr(self, "_query_entry", None)
        if entry is not None and entry.winfo_exists():
            try:
                entry.focus_set()
            except tk.TclError:
                pass

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._top_bar_container = ctk.CTkFrame(self, fg_color="transparent")
        self._top_bar_container.pack(fill="x", padx=18, pady=(14, 8))
        self._rebuild_top_bar()

        # Results: single tk.Text widget with tags — far cheaper than
        # rendering one CTk frame+labels per row for large result sets.
        results_wrap = ctk.CTkFrame(
            self,
            fg_color=T.BG_CARD,
            corner_radius=T.R_CARD,
        )
        results_wrap.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        results_wrap.grid_rowconfigure(0, weight=1)
        results_wrap.grid_columnconfigure(0, weight=1)

        bg = T.pick(T.BG_CARD)
        self._results_text = tk.Text(
            results_wrap,
            wrap="word",
            bd=0,
            relief="flat",
            highlightthickness=0,
            padx=14,
            pady=10,
            bg=bg,
            fg=T.pick(T.TEXT_PRIMARY),
            insertbackground=T.pick(T.TEXT_PRIMARY),
            selectbackground=T.pick(T.BG_SELECT),
            inactiveselectbackground=T.pick(T.BG_SELECT),
            cursor="xterm",
            state="disabled",
        )
        self._results_text.grid(row=0, column=0, sticky="nsew", padx=12, pady=10)

        scroll = ctk.CTkScrollbar(
            results_wrap,
            command=self._results_text.yview,
            button_color=T.BORDER_HOVER,
            button_hover_color=T.TEXT_MUTED,
        )
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, 6), pady=10)
        self._results_text.configure(yscrollcommand=scroll.set)

        self._configure_result_tags()

        # Footer.
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(0, 12))
        self._footer_label = ctk.CTkLabel(
            footer,
            text="",
            text_color=T.TEXT_MUTED,
            font=T.font_caption(),
        )
        self._footer_label.pack(side="left")

    def _rebuild_top_bar(self) -> None:
        for child in self._top_bar_container.winfo_children():
            child.destroy()

        if self._focused_player:
            self._build_player_chip()
        else:
            self._build_free_text_bar()

    def _build_free_text_bar(self) -> None:
        self._query_var = tk.StringVar(value="")
        entry = ctk.CTkEntry(
            self._top_bar_container,
            textvariable=self._query_var,
            placeholder_text="Search player or message…",
            height=32,
            corner_radius=T.R_INPUT,
            font=T.font_body(),
        )
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<KeyRelease>", self._on_query_keyrelease)
        entry.bind("<Return>", lambda _e: "break")
        self._query_entry = entry

        self._filter_var = tk.StringVar(value="Player")
        self._filter_buttons: dict[str, ctk.CTkButton] = {}
        chips = ctk.CTkFrame(self._top_bar_container, fg_color="transparent")
        chips.pack(side="left", padx=(10, 0))
        for i, label in enumerate(_FILTER_LABELS):
            btn = ctk.CTkButton(
                chips,
                text=label,
                height=32,
                width=72,
                corner_radius=T.R_BUTTON,
                font=T.font_small(),
                fg_color=T.BG_ELEV,
                hover_color=T.BORDER_HOVER,
                text_color=T.TEXT_SECONDARY,
                command=lambda lbl=label: self._on_filter_click(lbl),
            )
            btn.pack(side="left", padx=(0 if i == 0 else 4, 0))
            self._filter_buttons[label] = btn
        self._apply_filter_styles()

    def _build_player_chip(self) -> None:
        chip = ctk.CTkFrame(
            self._top_bar_container,
            fg_color=T.ACCENT_SUBTLE,
            corner_radius=T.R_PILL,
        )
        chip.pack(side="left")
        ctk.CTkLabel(
            chip,
            text=f"Showing history for {self._focused_player}",
            text_color=T.ACCENT,
            font=T.font_small(),
        ).pack(side="left", padx=(12, 6), pady=5)
        close_btn = ctk.CTkButton(
            chip,
            text="×",
            width=24,
            height=22,
            corner_radius=11,
            fg_color="transparent",
            hover_color=T.BG_ELEV,
            text_color=T.ACCENT,
            font=T.font_button(),
            command=self.reset_to_free_text,
        )
        close_btn.pack(side="left", padx=(0, 6), pady=3)

    # ── Free-text mode handlers ──────────────────────────────────────────────

    def _on_query_keyrelease(self, _event: tk.Event) -> None:
        self._schedule_search()

    def _on_filter_click(self, label: str) -> None:
        if self._filter_var.get() == label:
            return
        self._filter_var.set(label)
        self._apply_filter_styles()
        # Filter flips run immediately — re-use the last debounce path for
        # consistent behavior if the user is still typing.
        self._schedule_search(immediate=True)

    def _apply_filter_styles(self) -> None:
        active = self._filter_var.get()
        for label, btn in self._filter_buttons.items():
            if label == active:
                btn.configure(
                    fg_color=T.ACCENT,
                    hover_color=T.ACCENT_HOVER,
                    text_color=T.ACCENT_FG,
                )
            else:
                btn.configure(
                    fg_color=T.BG_ELEV,
                    hover_color=T.BORDER_HOVER,
                    text_color=T.TEXT_SECONDARY,
                )

    def _schedule_search(self, *, immediate: bool = False) -> None:
        if self._debounce_job is not None:
            try:
                self.after_cancel(self._debounce_job)
            except tk.TclError:
                pass
            self._debounce_job = None
        delay = 0 if immediate else _DEBOUNCE_MS
        self._debounce_job = self.after(delay, self._run_search)

    def _run_search(self) -> None:
        self._debounce_job = None
        query = self._query_var.get()
        self._last_query = query
        if len(query.strip()) < _MIN_QUERY_LEN:
            self._render_empty(
                f"Type at least {_MIN_QUERY_LEN} characters to search.",
                footer="",
            )
            return
        match_field, channel = _LABEL_TO_MODE.get(self._filter_var.get(), ("player", None))
        result_set = search_logs(
            query,
            chat_log_path=self._chat_log_path,
            hero_log_path=self._hero_log_path,
            channel_filter=channel,  # type: ignore[arg-type]
            match_field=match_field,  # type: ignore[arg-type]
        )
        self._render_results(result_set, empty_hint="No matches.")

    # ── Player-focused mode ──────────────────────────────────────────────────

    def _run_player_history(self) -> None:
        if not self._focused_player:
            return
        result_set = history_for_player(
            self._focused_player,
            chat_log_path=self._chat_log_path,
            hero_log_path=self._hero_log_path,
        )
        self._render_results(
            result_set,
            empty_hint=f"No history found for {self._focused_player}.",
        )

    # ── Result rendering ─────────────────────────────────────────────────────

    def _configure_result_tags(self) -> None:
        t = self._results_text
        body = T.font_body()
        bold = T.font_button()
        # Mono font for the timestamp guarantees pixel-identical width per
        # row, so the channel dot that follows lines up across all rows.
        # 10pt keeps the timestamp gutter compact while staying legible.
        ts_font = (T.mono_family(), 10)
        # Wrapped chat lines indent to roughly past the timestamp+dot gutter
        # so the message body stays visually attached to the player name.
        t.tag_configure("line", spacing1=3, spacing3=3, lmargin1=0, lmargin2=130)
        t.tag_configure("ts", foreground=T.pick(T.TEXT_MUTED), font=ts_font)
        t.tag_configure("dot_team", foreground=T.pick(T.CHAT_TEAM), font=ctk.CTkFont(size=10))
        t.tag_configure("dot_all", foreground=T.pick(T.CHAT_ALL), font=ctk.CTkFont(size=10))
        t.tag_configure("dot_hero", foreground=T.pick(T.CHAT_HERO), font=ctk.CTkFont(size=10))
        t.tag_configure("player", foreground=T.pick(T.TEXT_PRIMARY), font=bold)
        t.tag_configure("text", foreground=T.pick(T.TEXT_SECONDARY), font=body)
        t.tag_configure("hero_text", foreground=T.pick(T.CHAT_HERO), font=body)
        t.tag_configure("placeholder", foreground=T.pick(T.TEXT_MUTED), font=T.font_small())

    def _render_empty(self, hint: str, *, footer: str) -> None:
        t = self._results_text
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", hint, ("placeholder",))
        t.configure(state="disabled")
        self._set_footer_text(footer)

    def _render_results(self, result_set: SearchResultSet, *, empty_hint: str) -> None:
        t = self._results_text

        if not result_set.results:
            self._render_empty(empty_hint, footer="0 results")
            return

        t.configure(state="normal")
        t.delete("1.0", "end")

        # Per line, chat: "HH:MM:SS  ●  player: message"
        # Per line, hero: "HH:MM:SS  ●  player → hero"
        # No column alignment — message flows right after player name.
        for i, r in enumerate(result_set.results):
            if i > 0:
                t.insert("end", "\n", ("line",))
            t.insert("end", r.timestamp or "", ("ts", "line"))
            t.insert("end", " ", ("line",))
            t.insert("end", "●", (f"dot_{r.source}", "line"))
            t.insert("end", " ", ("line",))
            t.insert("end", r.player or "—", ("player", "line"))
            if r.source == "hero":
                t.insert("end", "  →  ", ("line",))
                t.insert("end", r.text or "", ("hero_text", "line"))
            else:
                t.insert("end", ": ", ("line",))
                t.insert("end", r.text or "", ("text", "line"))

        t.configure(state="disabled")
        t.see("1.0")

        n = len(result_set.results)
        if result_set.truncated:
            self._set_footer_text(f"{n} results (limit reached — refine query)")
        else:
            word = "result" if n == 1 else "results"
            self._set_footer_text(f"{n} {word}")

    def _set_footer_text(self, text: str) -> None:
        self._footer_label.configure(text=text)
