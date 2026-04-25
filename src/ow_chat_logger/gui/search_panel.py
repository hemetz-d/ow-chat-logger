"""Search view — Console design V1, virtualized via ``tk.Text``.

Two-column layout: results on the left, filter rail on the right.

Search bar with accent border + magnifier glyph + query entry + result count.
Active filter chips appear below the bar (one per selected channel and the
time window when narrowed). The right rail hosts two filter groups:

* **Channel** — Team / All chat / Hero, each with a live result count.
* **Time window** — Last 5 min / Last 15 min / Last hour / All time.

Result rows are rendered into a single ``tk.Text`` widget with per-row tags
(``row_<i>``) plus content tags (``ts``, ``dot_<source>``, ``player``,
``body``, ``hero_body``, ``match``). Tk's text widget paints only glyphs
in the visible viewport, so this scales to thousands of results without
the per-row CTk widget construction cost the previous design paid. The
results panel is read-only: clicks and hover are intentionally inert.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import customtkinter as ctk

from ow_chat_logger.gui import theme as T
from ow_chat_logger.log_search import (
    SearchResult,
    history_for_player,
    search_logs,
)

_DEBOUNCE_MS = 250  # quiet period after the last keystroke
_MIN_QUERY_LEN = 3
_RIGHT_RAIL_WIDTH = 260

# Indent for wrapped continuation lines. Roughly the pixel width of
# "YYYY-MM-DD HH:MM  ●  player_name:  " — keeps wrapped body text aligned
# past the timestamp / dot / player gutter so the message column stays
# readable.
_WRAP_INDENT_PX = 190

# Channel display: (label, key, dot color).
_CHANNELS: list[tuple[str, str, tuple[str, str]]] = [
    ("Team", "team", T.CHAT_TEAM),
    ("All chat", "all", T.CHAT_ALL),
    ("Hero", "hero", T.CHAT_HERO),
]

# Time window options: (label, key, timedelta | None for "all time").
_TIME_WINDOWS: list[tuple[str, str, "timedelta | None"]] = [
    ("Last 5 min", "5m", timedelta(minutes=5)),
    ("Last 15 min", "15m", timedelta(minutes=15)),
    ("Last hour", "1h", timedelta(hours=1)),
    ("All time", "all", None),
]


def _format_result_timestamp(raw: str | None) -> str:
    """Format a stored ``YYYY-MM-DD HH:MM:SS`` timestamp as
    ``YYYY-MM-DD HH:MM`` for the result row gutter. Falls back to the raw
    string padded to the expected width if parsing fails."""
    s = (raw or "").strip()
    if len(s) >= 16 and s[4] == "-" and s[7] == "-" and s[10] == " " and s[13] == ":":
        return s[:16]
    return s.ljust(16)


# ── Active filter chip (below search bar) ─────────────────────────────────────


class _ActiveFilterChip(ctk.CTkFrame):
    """Small removable pill shown below the search bar for each active filter.

    Built once per slot (Team / All / Hero / Time) and shown / hidden / count-
    updated in place via :meth:`set_state`. The previous design destroyed and
    recreated chips on every query keystroke, which caused the whole HUD to
    flicker.
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        text: str,
        dot_color: tuple[str, str] | None,
        on_remove: Callable[[], None],
    ) -> None:
        super().__init__(
            parent,
            fg_color=T.BG_ELEV,
            border_color=T.BORDER_HAIRLINE,
            border_width=1,
            corner_radius=6,
        )
        col = 0
        if dot_color is not None:
            ctk.CTkLabel(
                self,
                text="●",
                text_color=dot_color,
                font=ctk.CTkFont(size=8),
            ).grid(row=0, column=col, padx=(10, 5), pady=4)
            col += 1
        self._text_label = ctk.CTkLabel(
            self,
            text=text,
            text_color=T.TEXT_SECONDARY,
            font=T.font_caption(),
        )
        self._text_label.grid(row=0, column=col, padx=(0 if dot_color else 11, 6), pady=4)
        col += 1
        self._count_label = ctk.CTkLabel(
            self,
            text="",
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(family=T.mono_family(), size=10),
        )
        # Always grid the count label; an empty text just reserves no glyph
        # space. Keeps the chip's grid stable across count changes.
        self._count_label.grid(row=0, column=col, padx=(0, 6), pady=4)
        col += 1
        x = ctk.CTkLabel(
            self,
            text="×",
            text_color=T.TEXT_DIM,
            font=ctk.CTkFont(family=T.ui_family(), size=12),
            cursor="hand2",
        )
        x.grid(row=0, column=col, padx=(0, 10), pady=4)
        x.bind("<Button-1>", lambda _e: on_remove())

    def set_text(self, text: str) -> None:
        self._text_label.configure(text=text)

    def set_count(self, count: int | None) -> None:
        self._count_label.configure(text="" if count is None else str(count))


# ── Filter group (right rail section) ─────────────────────────────────────────


class _FilterGroup(ctk.CTkFrame):
    """One bordered section in the right rail (Channel / Time)."""

    def __init__(self, parent: tk.Widget, label: str) -> None:
        super().__init__(parent, fg_color="transparent")
        ctk.CTkLabel(
            self,
            text=label.upper(),
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(family=T.ui_family(), size=10, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 10))
        self._items_wrap = ctk.CTkFrame(self, fg_color="transparent")
        self._items_wrap.pack(fill="x")


class _CheckRow(ctk.CTkFrame):
    """Single checkable item inside a ``_FilterGroup``.

    Built once and updated in place via :meth:`set_state` — destroying and
    re-creating these on every keystroke caused visible flicker across the
    whole HUD.
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        label: str,
        on_toggle: Callable[[], None],
        dot_color: tuple[str, str] | None = None,
    ) -> None:
        super().__init__(parent, fg_color="transparent")

        self._box = ctk.CTkFrame(
            self,
            width=14,
            height=14,
            fg_color="transparent",
            border_color=T.BORDER_HOVER,
            border_width=1,
            corner_radius=3,
        )
        self._box.pack(side="left", padx=(0, 10))
        self._box.pack_propagate(False)
        # Always pack the check glyph; toggle text "" / "✓" via configure so
        # we don't churn the widget tree on every state flip.
        self._check_glyph = ctk.CTkLabel(
            self._box,
            text="",
            text_color=T.ACCENT_FG,
            font=ctk.CTkFont(family=T.ui_family(), size=10, weight="bold"),
        )
        self._check_glyph.pack(expand=True)

        if dot_color is not None:
            ctk.CTkLabel(
                self,
                text="●",
                text_color=dot_color,
                font=ctk.CTkFont(size=8),
            ).pack(side="left", padx=(0, 7))

        self._label = ctk.CTkLabel(
            self,
            text=label,
            text_color=T.TEXT_PRIMARY,
            font=T.font_caption(),
            anchor="w",
        )
        self._label.pack(side="left", fill="x", expand=True)

        self._count_label = ctk.CTkLabel(
            self,
            text="",
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(family=T.mono_family(), size=10),
        )
        self._count_label.pack(side="right")

        for w in (self, self._box, self._label, self._count_label):
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass
            w.bind("<Button-1>", lambda _e: on_toggle(), add="+")

    def set_state(self, *, is_on: bool, count: int | None) -> None:
        self._box.configure(
            fg_color=T.ACCENT if is_on else "transparent",
            border_color=T.ACCENT if is_on else T.BORDER_HOVER,
        )
        self._check_glyph.configure(text="✓" if is_on else "")
        self._count_label.configure(text="" if count is None else str(count))


# ── Main view ─────────────────────────────────────────────────────────────────


class SearchView(ctk.CTkFrame):
    """In-place search view — Console direction V1 layout, virtualized.

    Two-column grid: results list on the left, filter rail on the right.
    Public API kept stable for callers (FeedPanel / app):

      * ``focus_player(player)`` — switch to a player-history view.
      * ``reset_to_free_text()`` — return to query mode.
      * ``focus_input()`` — keyboard focus on the query entry.
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
            fg_color=T.BG_ROOT,
            corner_radius=0,
            border_width=0,
        )
        self._chat_log_path = chat_log_path
        self._hero_log_path = hero_log_path

        # Mode state.
        self._focused_player: str | None = None
        self._query_var = tk.StringVar(value="")

        # Filter state. Defaults: chat channels on (team + all), hero off,
        # all-time.
        self._channel_on: dict[str, tk.BooleanVar] = {
            "team": tk.BooleanVar(value=True),
            "all": tk.BooleanVar(value=True),
            "hero": tk.BooleanVar(value=False),
        }
        self._time_window: tk.StringVar = tk.StringVar(value="all")

        # Results state.
        self._raw_results: list[SearchResult] = []
        self._filtered_results: list[SearchResult] = []
        self._showing_placeholder: bool = True

        # Plumbing.
        self._debounce_job: str | None = None

        self._build()
        self._update_view()

    # ── Public API ───────────────────────────────────────────────────────────

    def focus_player(self, player: str) -> None:
        """Switch to player-focused mode for ``player``'s history."""
        cleaned = player.strip()
        if not cleaned:
            return
        self._focused_player = cleaned
        self._query_var.set("")
        self._refresh_player_chip()
        self._run_query()

    def reset_to_free_text(self) -> None:
        self._focused_player = None
        self._query_var.set("")
        self._refresh_player_chip()
        self._raw_results = []
        self._update_view()
        self.focus_input()

    def focus_input(self) -> None:
        entry = getattr(self, "_query_entry", None)
        if entry is not None and entry.winfo_exists():
            try:
                entry.focus_set()
            except tk.TclError:
                pass

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # 3-column grid: results column | divider | right rail.
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(0, weight=1)

        results_col = ctk.CTkFrame(self, fg_color="transparent")
        results_col.grid(row=0, column=0, sticky="nsew")
        self._build_results_column(results_col)

        ctk.CTkFrame(self, width=1, fg_color=T.BORDER_HAIRLINE, corner_radius=0).grid(
            row=0, column=1, sticky="ns"
        )

        rail = ctk.CTkFrame(
            self,
            fg_color=T.BG_CHROME,
            width=_RIGHT_RAIL_WIDTH,
            corner_radius=0,
        )
        rail.grid(row=0, column=2, sticky="ns")
        rail.grid_propagate(False)
        rail.pack_propagate(False)
        self._build_right_rail(rail)

    def _build_results_column(self, parent: ctk.CTkFrame) -> None:
        # Search bar (top section).
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=18)

        # Bar — accent-bordered rounded container.
        bar = ctk.CTkFrame(
            top,
            fg_color=T.BG_CARD,
            border_color=T.ACCENT,
            border_width=1,
            corner_radius=9,
            height=42,
        )
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Magnifier glyph (CTkLabel, follows accent via the redraw path).
        ctk.CTkLabel(
            bar,
            text="⌕",
            text_color=T.ACCENT,
            font=ctk.CTkFont(family=T.ui_family(), size=16),
        ).pack(side="left", padx=(14, 10), pady=10)

        # `player:` chip — only visible in player-focused mode.
        self._player_chip = ctk.CTkLabel(
            bar,
            text="player:",
            text_color=T.ACCENT,
            fg_color=T.ACCENT_SUBTLE,
            font=ctk.CTkFont(family=T.mono_family(), size=11),
            corner_radius=4,
            padx=7,
            pady=2,
        )
        self._player_name_label = ctk.CTkLabel(
            bar,
            text="",
            text_color=T.TEXT_PRIMARY,
            font=ctk.CTkFont(family=T.ui_family(), size=14, weight="bold"),
        )

        # Free-text entry.
        self._query_entry = ctk.CTkEntry(
            bar,
            textvariable=self._query_var,
            placeholder_text="Search player or message…",
            fg_color="transparent",
            border_width=0,
            height=22,
            font=ctk.CTkFont(family=T.ui_family(), size=14),
        )
        self._query_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._query_entry.bind("<KeyRelease>", lambda _e: self._schedule_query())
        # Enter runs the query immediately — no debounce wait.
        self._query_entry.bind(
            "<Return>",
            lambda _e: (self._schedule_query(immediate=True), "break")[1],
        )

        # Player-mode close button (×) — clears focused-player.
        self._player_close_btn = ctk.CTkButton(
            bar,
            text="×",
            width=22,
            height=22,
            corner_radius=4,
            fg_color="transparent",
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_DIM,
            font=ctk.CTkFont(family=T.ui_family(), size=14),
            command=self.reset_to_free_text,
        )

        # Result count.
        self._count_label = ctk.CTkLabel(
            bar,
            text="",
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(family=T.mono_family(), size=11),
        )
        self._count_label.pack(side="right", padx=(8, 14), pady=10)

        # Active filter chips row — chips are built once per slot (Team /
        # All / Hero / Time) and shown / hidden / count-updated in place.
        self._chips_wrap = ctk.CTkFrame(parent, fg_color="transparent")
        self._chips_wrap.pack(fill="x", padx=24, pady=(0, 0))
        self._channel_chips: dict[str, _ActiveFilterChip] = {}
        for label, key, dot in _CHANNELS:
            chip = _ActiveFilterChip(
                self._chips_wrap,
                text=label,
                dot_color=dot,
                on_remove=lambda k=key: self._toggle_channel(k, force_value=False),
            )
            self._channel_chips[key] = chip
        self._time_chip = _ActiveFilterChip(
            self._chips_wrap,
            text="",
            dot_color=None,
            on_remove=lambda: self._set_time_window("all"),
        )

        # Results: a single tk.Text widget (virtualized) + scrollbar.
        results_wrap = ctk.CTkFrame(parent, fg_color=T.BG_ROOT, corner_radius=0)
        results_wrap.pack(fill="both", expand=True)
        results_wrap.grid_rowconfigure(0, weight=1)
        results_wrap.grid_columnconfigure(0, weight=1)

        self._results_text = tk.Text(
            results_wrap,
            wrap="word",
            bd=0,
            relief="flat",
            highlightthickness=0,
            padx=24,
            pady=11,
            spacing1=5,  # extra space above each logical line
            spacing3=5,  # extra space below each logical line
            cursor="arrow",
            state="disabled",
            takefocus=0,
        )
        self._results_text.grid(row=0, column=0, sticky="nsew")

        # The results widget is purely a read-only display — kill every Tk
        # default that would place an insertion cursor or start a text
        # selection. Returning "break" stops the class-level handler from
        # running after ours.
        for seq in (
            "<Button-1>",
            "<B1-Motion>",
            "<Double-Button-1>",
            "<Triple-Button-1>",
            "<Shift-Button-1>",
        ):
            self._results_text.bind(seq, lambda _e: "break")

        self._results_scroll = ctk.CTkScrollbar(
            results_wrap,
            command=self._results_text.yview,
            button_color=T.BORDER_HOVER,
            button_hover_color=T.TEXT_MUTED,
        )
        self._results_scroll.grid(row=0, column=1, sticky="ns")
        self._results_text.configure(yscrollcommand=self._results_scroll.set)

        self._configure_result_tags()

    def _build_right_rail(self, parent: ctk.CTkFrame) -> None:
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=20, pady=18)

        # Channel group — built once, updated in place.
        self._channel_group = _FilterGroup(wrap, label="Channel")
        self._channel_group.pack(fill="x", pady=(0, 18))
        self._channel_rows: dict[str, _CheckRow] = {}
        for label, key, dot in _CHANNELS:
            row = _CheckRow(
                self._channel_group._items_wrap,
                label=label,
                on_toggle=lambda k=key: self._toggle_channel(k),
                dot_color=dot,
            )
            row.pack(fill="x", pady=3)
            self._channel_rows[key] = row

        # Time window group — built once, updated in place.
        self._time_group = _FilterGroup(wrap, label="Time window")
        self._time_group.pack(fill="x")
        self._time_rows: dict[str, _CheckRow] = {}
        for label, key, _delta in _TIME_WINDOWS:
            row = _CheckRow(
                self._time_group._items_wrap,
                label=label,
                on_toggle=lambda k=key: self._set_time_window(k),
            )
            row.pack(fill="x", pady=3)
            self._time_rows[key] = row

    # ── tk.Text tag system ──────────────────────────────────────────────────

    def _configure_result_tags(self) -> None:
        """Configure all tags used by the result text widget.

        Tag priority is creation order — tags configured LATER win on
        conflict. Background/foreground tags (``hover``, ``selected``,
        ``match``) are configured last so they override per-cell color tags
        when applied to the same characters.
        """
        t = self._results_text
        body_font = T.font_body()
        bold_font = T.font_button()
        ts_font = ctk.CTkFont(family=T.mono_family(), size=11)
        hero_font = ctk.CTkFont(family=T.ui_family(), size=12, slant="italic")
        placeholder_font = ctk.CTkFont(family=T.ui_family(), size=15, weight="bold")
        placeholder_sub_font = T.font_small()

        # Layout / spacing — wrapped lines indent past the gutter so the
        # message column stays vertically aligned across rows.
        t.tag_configure("line", lmargin1=0, lmargin2=_WRAP_INDENT_PX)
        # Per-source dot tags — color set in ``_apply_mode_colors``.
        t.tag_configure("dot_team", font=ctk.CTkFont(size=10))
        t.tag_configure("dot_all", font=ctk.CTkFont(size=10))
        t.tag_configure("dot_hero", font=ctk.CTkFont(size=10))
        # Content tags — fonts here, colors below.
        t.tag_configure("ts", font=ts_font)
        t.tag_configure("player", font=bold_font)
        t.tag_configure("body", font=body_font)
        t.tag_configure("hero_body", font=hero_font)
        t.tag_configure("placeholder_title", font=placeholder_font, justify="center")
        t.tag_configure("placeholder_sub", font=placeholder_sub_font, justify="center")

        # ``match`` overlay — accent-tinted highlighted substring inside text.
        t.tag_configure("match")

        self._apply_mode_colors()

    def _apply_mode_colors(self) -> None:
        """Re-resolve every mode-/accent-dependent color on the text widget.

        Called on initial setup, on appearance-mode change, and whenever the
        accent palette mutates so that the in-place SQLite tag colors track
        the rest of the app.
        """
        t = self._results_text
        if not t.winfo_exists():
            return
        t.configure(
            bg=T.pick(T.BG_ROOT),
            fg=T.pick(T.TEXT_PRIMARY),
            insertbackground=T.pick(T.TEXT_PRIMARY),
            selectbackground=T.pick(T.BG_SELECT),
            inactiveselectbackground=T.pick(T.BG_SELECT),
        )
        t.tag_configure("ts", foreground=T.pick(T.TEXT_DIM))
        t.tag_configure("dot_team", foreground=T.pick(T.CHAT_TEAM))
        t.tag_configure("dot_all", foreground=T.pick(T.CHAT_ALL))
        t.tag_configure("dot_hero", foreground=T.pick(T.CHAT_HERO))
        t.tag_configure("player", foreground=T.pick(T.TEXT_PRIMARY))
        t.tag_configure("body", foreground=T.pick(T.TEXT_SECONDARY))
        t.tag_configure("hero_body", foreground=T.pick(T.CHAT_HERO))
        t.tag_configure("placeholder_title", foreground=T.pick(T.TEXT_PRIMARY))
        t.tag_configure("placeholder_sub", foreground=T.pick(T.TEXT_SECONDARY))
        t.tag_configure(
            "match",
            background=T.pick(T.ACCENT),
            foreground=T.pick(T.ACCENT_FG),
        )

    # ── Player-mode chip toggle ─────────────────────────────────────────────

    def _refresh_player_chip(self) -> None:
        if self._focused_player:
            self._query_entry.pack_forget()
            self._player_chip.pack(side="left", padx=(0, 8), pady=10)
            self._player_name_label.configure(text=self._focused_player)
            self._player_name_label.pack(side="left", fill="x", expand=True, pady=10)
            self._player_close_btn.pack(side="right", padx=(0, 6), pady=10)
        else:
            self._player_chip.pack_forget()
            self._player_name_label.pack_forget()
            self._player_close_btn.pack_forget()
            self._query_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

    # ── Query plumbing ──────────────────────────────────────────────────────

    def _schedule_query(self, *, immediate: bool = False) -> None:
        if self._debounce_job is not None:
            try:
                self.after_cancel(self._debounce_job)
            except tk.TclError:
                pass
            self._debounce_job = None
        delay = 0 if immediate else _DEBOUNCE_MS
        self._debounce_job = self.after(delay, self._run_query)

    def _run_query(self) -> None:
        self._debounce_job = None
        if self._focused_player:
            self._raw_results = list(
                history_for_player(
                    self._focused_player,
                    chat_log_path=self._chat_log_path,
                    hero_log_path=self._hero_log_path,
                ).results
            )
        else:
            query = self._query_var.get().strip()
            if len(query) < _MIN_QUERY_LEN:
                self._raw_results = []
            else:
                self._raw_results = list(
                    search_logs(
                        query,
                        chat_log_path=self._chat_log_path,
                        hero_log_path=self._hero_log_path,
                        match_field="both",
                    ).results
                )
        self._update_view()

    # ── Filtering ───────────────────────────────────────────────────────────

    def _apply_filters(self, results: list[SearchResult]) -> list[SearchResult]:
        active_channels = {k for k, v in self._channel_on.items() if v.get()}
        time_cutoff = self._time_cutoff()

        out: list[SearchResult] = []
        for r in results:
            if r.source not in active_channels:
                continue
            if time_cutoff is not None and not self._within_cutoff(r.timestamp, time_cutoff):
                continue
            out.append(r)
        return out

    def _time_cutoff(self) -> datetime | None:
        key = self._time_window.get()
        for _label, k, delta in _TIME_WINDOWS:
            if k == key and delta is not None:
                return datetime.now() - delta
        return None

    @staticmethod
    def _within_cutoff(ts_str: str, cutoff: datetime) -> bool:
        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            return True  # unparseable → include rather than silently drop
        return ts >= cutoff

    # ── Render ──────────────────────────────────────────────────────────────

    def _update_view(self) -> None:
        """Re-render results, chips, and right-rail counts from current state."""
        self._filtered_results = self._apply_filters(self._raw_results)
        self._render_rows()
        self._render_chips()
        self._render_right_rail()
        self._update_count_label()

    def _render_rows(self) -> None:
        """Bulk-insert all filtered results into the text widget.

        Synchronous on purpose — Tk's text widget only paints glyphs in the
        visible viewport, so even a 10k-result render is dominated by string
        manipulation, not widget construction. No chunking needed.
        """
        t = self._results_text
        t.configure(state="normal")
        t.delete("1.0", "end")

        if not self._filtered_results:
            self._show_empty_state_inline()
            t.configure(state="disabled")
            return

        self._showing_placeholder = False
        query = self._highlight_query()
        for i, r in enumerate(self._filtered_results):
            self._insert_row(i, r, query)

        t.configure(state="disabled")
        # Scroll to the top so users see the newest matches first.
        t.yview_moveto(0)

    def _insert_row(self, row_id: int, r: SearchResult, query: str | None) -> None:
        """Append one row's content to the text widget with all its tags.

        The ``row_<id>`` tag is kept (cheap, and useful for debugging /
        future selective re-coloring); per-cell tags layer color and font
        on top, and ``match`` overlays the highlighted substring.
        """
        t = self._results_text
        row_tag = f"row_{row_id}"
        base_tags: tuple[str, ...] = ("line", row_tag)

        if row_id > 0:
            t.insert("end", "\n", base_tags)

        # Timestamp — full date + HH:MM. Logs span many days; without the
        # date a search across history is unreadable. Seconds are dropped
        # to claw back some horizontal space.
        ts = _format_result_timestamp(r.timestamp)
        t.insert("end", ts + "  ", base_tags + ("ts",))

        # Channel-colored dot.
        t.insert("end", "●  ", base_tags + (f"dot_{r.source}",))

        # Player name with optional inline highlight.
        self._insert_with_highlight(r.player or "—", query, base_tags + ("player",))

        # Separator + body.
        if r.source == "hero":
            t.insert("end", "  →  ", base_tags)
            self._insert_with_highlight(r.text or "", query, base_tags + ("hero_body",))
        else:
            t.insert("end", ":  ", base_tags)
            self._insert_with_highlight(r.text or "", query, base_tags + ("body",))

    def _insert_with_highlight(
        self,
        text: str,
        query: str | None,
        base_tags: tuple[str, ...],
    ) -> None:
        """Insert ``text`` overlaying ``match`` where the case-insensitive
        ``query`` substring appears."""
        t = self._results_text
        if not text:
            return
        if not query:
            t.insert("end", text, base_tags)
            return
        idx = text.lower().find(query.lower())
        if idx < 0:
            t.insert("end", text, base_tags)
            return
        if idx > 0:
            t.insert("end", text[:idx], base_tags)
        t.insert("end", text[idx : idx + len(query)], base_tags + ("match",))
        rest = text[idx + len(query) :]
        if rest:
            t.insert("end", rest, base_tags)

    def _highlight_query(self) -> str | None:
        if self._focused_player:
            return self._focused_player
        q = self._query_var.get().strip()
        return q if len(q) >= _MIN_QUERY_LEN else None

    def _show_empty_state_inline(self) -> None:
        """Render the empty-state copy directly into the text widget."""
        t = self._results_text
        if self._raw_results and not self._filtered_results:
            title = "No matches with current filters"
            sub = "Try widening the time window or removing word filters."
        elif self._focused_player:
            title = f"No history for {self._focused_player}"
            sub = "Once messages from this player are logged they'll show up here."
        elif len(self._query_var.get().strip()) >= _MIN_QUERY_LEN:
            title = "No matches"
            sub = "Try a different query."
        else:
            title = "Search your chat log"
            sub = f"Type at least {_MIN_QUERY_LEN} characters to search by player or message text."
        # Push the placeholder a few lines down so it lands roughly centered
        # within the typical viewport.
        t.insert("end", "\n\n\n")
        t.insert("end", title + "\n", ("placeholder_title",))
        t.insert("end", sub, ("placeholder_sub",))
        self._showing_placeholder = True

    # ── Filter chips + right rail ───────────────────────────────────────────

    def _render_chips(self) -> None:
        """Show / hide pre-built chips and refresh their count labels.

        Done in place to avoid the destroy + rebuild flicker the previous
        implementation caused on every keystroke.
        """
        channel_counts = self._counts_per_channel(self._raw_results)
        any_chip = False
        # Re-pack from scratch so newly-shown chips slot back into their
        # canonical left-to-right position. ``pack_forget`` then ``pack``
        # is cheap (no widget construction).
        for _label, key, _dot in _CHANNELS:
            self._channel_chips[key].pack_forget()
        self._time_chip.pack_forget()

        for _label, key, _dot in _CHANNELS:
            if not self._channel_on[key].get():
                continue
            chip = self._channel_chips[key]
            chip.set_count(channel_counts.get(key, 0))
            chip.pack(side="left", padx=(0, 8))
            any_chip = True

        if self._time_window.get() != "all":
            label = next(
                (lbl for lbl, k, _d in _TIME_WINDOWS if k == self._time_window.get()),
                "Time",
            )
            self._time_chip.set_text(label)
            self._time_chip.set_count(None)
            self._time_chip.pack(side="left", padx=(0, 8))
            any_chip = True

        # Adjust outer spacing so the chips row collapses cleanly when empty.
        self._chips_wrap.pack_configure(pady=(0, 12) if any_chip else (0, 0))

    def _render_right_rail(self) -> None:
        """Update the pre-built check rows in place.

        Counts and check-state are pushed via ``_CheckRow.set_state`` so
        the widget tree never gets torn down — keystroke updates no longer
        flicker the sidebar.
        """
        channel_counts = self._counts_per_channel(self._raw_results)
        for _label, key, _dot in _CHANNELS:
            self._channel_rows[key].set_state(
                is_on=self._channel_on[key].get(),
                count=channel_counts.get(key, 0) if self._raw_results else None,
            )
        for _label, key, _delta in _TIME_WINDOWS:
            self._time_rows[key].set_state(
                is_on=self._time_window.get() == key,
                count=None,
            )

    def _update_count_label(self) -> None:
        n = len(self._filtered_results)
        if n == 0 and not self._raw_results:
            text = ""
        else:
            text = f"{n} result" + ("" if n == 1 else "s")
        self._count_label.configure(text=text)

    @staticmethod
    def _counts_per_channel(results: list[SearchResult]) -> dict[str, int]:
        counts: dict[str, int] = {"team": 0, "all": 0, "hero": 0}
        for r in results:
            if r.source in counts:
                counts[r.source] += 1
        return counts

    # ── Filter mutators ─────────────────────────────────────────────────────

    def _toggle_channel(self, key: str, *, force_value: bool | None = None) -> None:
        var = self._channel_on.get(key)
        if var is None:
            return
        if force_value is not None:
            var.set(force_value)
        else:
            var.set(not var.get())
        self._update_view()

    def _set_time_window(self, key: str) -> None:
        if self._time_window.get() == key:
            return
        self._time_window.set(key)
        self._update_view()

    # ── Appearance-mode sync ────────────────────────────────────────────────

    def _set_appearance_mode(self, mode_string: str) -> None:
        super()._set_appearance_mode(mode_string)
        # tk.Text and its tags don't participate in CTk's (light, dark)
        # tuple plumbing, so we re-pick hexes whenever the mode flips.
        # Guarded because ctk may call this during super().__init__, before
        # ``_results_text`` exists.
        t = getattr(self, "_results_text", None)
        if t is not None and t.winfo_exists():
            self._apply_mode_colors()
