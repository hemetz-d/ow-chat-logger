"""Search view — Console design V1.

Two-column layout: results list on the left, filter rail on the right.

Search bar with accent border + magnifier glyph + query entry + result count.
Active filter chips appear below the bar (one per selected channel and the
time window when narrowed). The right rail hosts two filter groups:

* **Channel**  — Team / All chat / Hero, each with a live result count.
* **Time window** — Last 5 min / Last 15 min / Last hour / All time.

Result rows reuse the Live feed's column layout (dot · mono ts · bold player ·
body) so both views feel like one app. Clicking a row selects it (accent
background + accent player name + left accent stripe).
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


# ── Result row widget ─────────────────────────────────────────────────────────


class _SearchResultRow(ctk.CTkFrame):
    """Single search-result row.

    Mirrors the Live feed's ``MessageRow`` layout so the two views feel
    consistent. Clicking anywhere on the row toggles selection — the parent
    ``SearchView`` is responsible for tracking ``_selected_row`` and
    ensuring only one is selected at a time.
    """

    def __init__(
        self,
        parent: tk.Widget,
        result: SearchResult,
        query: str | None,
        on_select: Callable[["_SearchResultRow"], None] | None = None,
    ) -> None:
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self._result = result
        self._on_select = on_select
        self._selected = False
        self._hover = False
        self._build(query)
        if on_select is not None:
            self._bind_clicks()

    def _build(self, query: str | None) -> None:
        # Layout: [dot] [mono ts] [bold player] [flex body]
        # Pin the player column's minimum width via the grid manager so the
        # inline-highlight wrapper frame can size to its natural content height
        # (otherwise CTkFrame's default ``height=200`` blows out every row).
        self.grid_columnconfigure(2, minsize=120)
        self.grid_columnconfigure(3, weight=1)

        # Dot (channel-colored).
        if self._result.source == "team":
            dot_color = T.CHAT_TEAM
        elif self._result.source == "all":
            dot_color = T.CHAT_ALL
        else:
            dot_color = T.CHAT_HERO
        ctk.CTkLabel(
            self,
            text="●",
            text_color=dot_color,
            font=ctk.CTkFont(size=10),
        ).grid(row=0, column=0, padx=(24, 14), pady=11, sticky="w")

        # Time portion only — date is implicit in the active session.
        ts = (self._result.timestamp or "").split(" ")[-1]
        ctk.CTkLabel(
            self,
            text=ts,
            text_color=T.TEXT_DIM,
            font=ctk.CTkFont(family=T.mono_family(), size=11),
            width=64,
            anchor="w",
        ).grid(row=0, column=1, padx=(0, 14), pady=11, sticky="w")

        # Player name — highlight matching substring inline if query supplied.
        player_name = self._result.player or "—"
        self._player_widget = self._build_highlight_label(
            player_name,
            query,
            base_color=T.TEXT_PRIMARY,
            base_font=T.font_button(),
            width=120,
        )
        self._player_widget.grid(row=0, column=2, padx=(0, 14), pady=11, sticky="w")

        # Body — for hero rows, use the hero color and arrow prefix.
        if self._result.source == "hero":
            body_text = f"→  {self._result.text or ''}"
            body_color = T.CHAT_HERO
            body_font = ctk.CTkFont(family=T.ui_family(), size=12, slant="italic")
        else:
            body_text = self._result.text or ""
            body_color = T.TEXT_SECONDARY
            body_font = T.font_body()
        self._body_label = ctk.CTkLabel(
            self,
            text=body_text,
            text_color=body_color,
            font=body_font,
            anchor="w",
            justify="left",
            wraplength=600,
        )
        self._body_label.grid(row=0, column=3, padx=(0, 24), pady=11, sticky="ew")

    def _build_highlight_label(
        self,
        text: str,
        query: str | None,
        *,
        base_color: tuple[str, str],
        base_font: ctk.CTkFont,
        width: int,
    ) -> ctk.CTkFrame:
        """Render ``text`` with the matching ``query`` substring highlighted.

        Tk doesn't do inline rich text on a single Label — we approximate by
        packing pre/match/post Labels horizontally inside a wrapper frame.
        For player names this works cleanly (short, single-line). When
        nothing matches we collapse to a single Label.

        We deliberately do NOT freeze the wrapper's geometry (no
        ``pack_propagate(False)`` + no explicit ``height``) — that pulls in
        CTkFrame's default 200-px height and inflates every row. The parent
        grid uses ``minsize`` to keep player columns aligned across rows.
        """
        wrap = ctk.CTkFrame(self, fg_color="transparent")

        if not query:
            ctk.CTkLabel(wrap, text=text, text_color=base_color, font=base_font, anchor="w").pack(
                side="left"
            )
            self._player_pre = None
            self._player_match = None
            self._player_post = None
            return wrap

        idx = text.lower().find(query.lower())
        if idx < 0:
            ctk.CTkLabel(wrap, text=text, text_color=base_color, font=base_font, anchor="w").pack(
                side="left"
            )
            self._player_pre = None
            self._player_match = None
            self._player_post = None
            return wrap

        pre = text[:idx]
        match = text[idx : idx + len(query)]
        post = text[idx + len(query) :]
        self._player_pre = ctk.CTkLabel(wrap, text=pre, text_color=base_color, font=base_font)
        self._player_pre.pack(side="left")
        # Highlighted span — accent bg + accentFg fg + small radius.
        self._player_match = ctk.CTkLabel(
            wrap,
            text=match,
            text_color=T.ACCENT_FG,
            fg_color=T.ACCENT,
            corner_radius=3,
            font=base_font,
            padx=3,
        )
        self._player_match.pack(side="left")
        self._player_post = ctk.CTkLabel(wrap, text=post, text_color=base_color, font=base_font)
        self._player_post.pack(side="left")
        return wrap

    def _bind_clicks(self) -> None:
        def click(_e: tk.Event) -> None:
            if self._on_select is not None:
                self._on_select(self)

        self.bind("<Button-1>", click, add="+")
        self.configure(cursor="hand2")
        for child in self.winfo_children():
            try:
                child.bind("<Button-1>", click, add="+")
                child.configure(cursor="hand2")
            except tk.TclError:
                pass
            for grand in child.winfo_children():
                try:
                    grand.bind("<Button-1>", click, add="+")
                    grand.configure(cursor="hand2")
                except tk.TclError:
                    pass
        self._bind_hover()

    def _bind_hover(self) -> None:
        def enter(_e: tk.Event) -> None:
            if not self._hover:
                self._hover = True
                self._apply_bg()

        def leave(_e: tk.Event) -> None:
            try:
                x, y = self.winfo_pointerxy()
                w = self.winfo_containing(x, y)
            except tk.TclError:
                w = None
            node = w
            while node is not None:
                if node is self:
                    return
                try:
                    node = node.master
                except Exception:
                    break
            if self._hover:
                self._hover = False
                self._apply_bg()

        self.bind("<Enter>", enter, add="+")
        self.bind("<Leave>", leave, add="+")
        for child in self.winfo_children():
            try:
                child.bind("<Enter>", enter, add="+")
                child.bind("<Leave>", leave, add="+")
            except tk.TclError:
                pass

    # ── Public mutators ───────────────────────────────────────────────────

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        if self._player_pre is not None:
            color = T.ACCENT if selected else T.TEXT_PRIMARY
            self._player_pre.configure(text_color=color)
            if self._player_post is not None:
                self._player_post.configure(text_color=color)
        elif hasattr(self, "_player_widget"):
            # Solo-label case (no highlight) — find the inner CTkLabel.
            for child in self._player_widget.winfo_children():
                if isinstance(child, ctk.CTkLabel):
                    child.configure(text_color=T.ACCENT if selected else T.TEXT_PRIMARY)
        self._apply_bg()

    def set_body_wraplength(self, wraplength: int) -> None:
        if wraplength > 80:
            try:
                self._body_label.configure(wraplength=wraplength)
            except tk.TclError:
                pass

    def _apply_bg(self) -> None:
        if self._selected:
            self.configure(fg_color=T.ACCENT_SUBTLE)
        elif self._hover:
            self.configure(fg_color=T.BG_CHROME)
        else:
            self.configure(fg_color="transparent")

    @property
    def result(self) -> SearchResult:
        return self._result


# ── Active filter chip (below search bar) ─────────────────────────────────────


class _ActiveFilterChip(ctk.CTkFrame):
    """Small removable pill shown below the search bar for each active filter."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        text: str,
        count: int | None,
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
        ctk.CTkLabel(
            self,
            text=text,
            text_color=T.TEXT_SECONDARY,
            font=T.font_caption(),
        ).grid(row=0, column=col, padx=(0 if dot_color else 11, 6), pady=4)
        col += 1
        if count is not None:
            ctk.CTkLabel(
                self,
                text=str(count),
                text_color=T.TEXT_MUTED,
                font=ctk.CTkFont(family=T.mono_family(), size=10),
            ).grid(row=0, column=col, padx=(0, 6), pady=4)
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


# ── Filter group (right rail section) ─────────────────────────────────────────


class _FilterGroup(ctk.CTkFrame):
    """One bordered section in the right rail (Channel / Time / Contains)."""

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

    def clear(self) -> None:
        for child in self._items_wrap.winfo_children():
            child.destroy()


def _make_check_row(
    parent: tk.Widget,
    *,
    label: str,
    is_on: bool,
    count: int | None,
    on_toggle: Callable[[], None],
    dot_color: tuple[str, str] | None = None,
    muted: bool = False,
) -> ctk.CTkFrame:
    """Single checkable item inside a ``_FilterGroup``."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=3)

    box = ctk.CTkFrame(
        row,
        width=14,
        height=14,
        fg_color=T.ACCENT if is_on else "transparent",
        border_color=T.ACCENT if is_on else T.BORDER_HOVER,
        border_width=1,
        corner_radius=3,
    )
    box.pack(side="left", padx=(0, 10))
    box.pack_propagate(False)
    if is_on:
        ctk.CTkLabel(
            box,
            text="✓",
            text_color=T.ACCENT_FG,
            font=ctk.CTkFont(family=T.ui_family(), size=10, weight="bold"),
        ).pack(expand=True)

    if dot_color is not None:
        ctk.CTkLabel(
            row,
            text="●",
            text_color=dot_color,
            font=ctk.CTkFont(size=8),
        ).pack(side="left", padx=(0, 7))

    text_color = T.TEXT_MUTED if muted else T.TEXT_PRIMARY
    label_widget = ctk.CTkLabel(
        row,
        text=label,
        text_color=text_color,
        font=T.font_caption(),
        anchor="w",
    )
    label_widget.pack(side="left", fill="x", expand=True)

    if count is not None:
        ctk.CTkLabel(
            row,
            text=str(count),
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(family=T.mono_family(), size=10),
        ).pack(side="right")

    # Whole row + checkbox is clickable.
    for w in (row, box, label_widget):
        try:
            w.configure(cursor="hand2")
        except Exception:
            pass
        w.bind("<Button-1>", lambda _e: on_toggle(), add="+")

    return row


# ── Main view ─────────────────────────────────────────────────────────────────


class SearchView(ctk.CTkFrame):
    """In-place search view — Console direction V1 layout.

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
        self._result_rows: list[_SearchResultRow] = []
        self._selected_row: _SearchResultRow | None = None

        # Plumbing.
        self._debounce_job: str | None = None
        self._wrap_after_id: str | None = None
        self._last_wraplength: int = 0

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

        # Single resize listener for batch wraplength updates — same pattern
        # as FeedPanel uses to keep dragging smooth.
        self.bind("<Configure>", self._on_resize)

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

        # Magnifier icon — a Unicode glyph rather than a baked PIL icon so it
        # follows the accent color via CTk's normal redraw path. PIL icons
        # capture the color at construction and don't refresh when the
        # accent palette mutates.
        ctk.CTkLabel(
            bar,
            text="⌕",  # ⌕ TELEPHONE RECORDER glyph (also used in the design)
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
        # Not packed yet — managed by ``_refresh_player_chip``.

        self._player_name_label = ctk.CTkLabel(
            bar,
            text="",
            text_color=T.TEXT_PRIMARY,
            font=ctk.CTkFont(family=T.ui_family(), size=14, weight="bold"),
        )
        # Not packed yet either.

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
        # Enter runs the query immediately — no waiting for the debounce.
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
        # Not packed yet.

        # Result count.
        self._count_label = ctk.CTkLabel(
            bar,
            text="",
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(family=T.mono_family(), size=11),
        )
        self._count_label.pack(side="right", padx=(8, 14), pady=10)

        # Active filter chips row.
        self._chips_wrap = ctk.CTkFrame(parent, fg_color="transparent")
        self._chips_wrap.pack(fill="x", padx=24, pady=(0, 12))

        # Results list.
        self._results_list = ctk.CTkScrollableFrame(
            parent,
            fg_color=T.BG_ROOT,
            corner_radius=0,
            scrollbar_button_color=T.BORDER_HOVER,
            scrollbar_button_hover_color=T.TEXT_MUTED,
        )
        self._results_list.pack(fill="both", expand=True, padx=0, pady=0)

        # Empty-state placeholder lives inside the results list, replaced
        # whenever results render.
        self._empty_frame: ctk.CTkFrame | None = None

    def _build_right_rail(self, parent: ctk.CTkFrame) -> None:
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=20, pady=18)

        # Channel group.
        self._channel_group = _FilterGroup(wrap, label="Channel")
        self._channel_group.pack(fill="x", pady=(0, 18))

        # Time window group.
        self._time_group = _FilterGroup(wrap, label="Time window")
        self._time_group.pack(fill="x")

    # ── Player-mode chip toggle ─────────────────────────────────────────────

    def _refresh_player_chip(self) -> None:
        if self._focused_player:
            # Hide the entry, show the chip + name + close.
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
        # Drop existing rows.
        for row in self._result_rows:
            row.destroy()
        self._result_rows.clear()
        self._selected_row = None
        if self._empty_frame is not None:
            self._empty_frame.destroy()
            self._empty_frame = None

        if not self._filtered_results:
            self._show_empty_state()
            return

        query = self._highlight_query()
        for r in self._filtered_results:
            row = _SearchResultRow(
                self._results_list,
                r,
                query,
                on_select=self._on_row_selected,
            )
            row.pack(fill="x")
            if self._last_wraplength > 80:
                row.set_body_wraplength(self._last_wraplength)
            self._result_rows.append(row)

    def _highlight_query(self) -> str | None:
        if self._focused_player:
            return self._focused_player
        q = self._query_var.get().strip()
        return q if len(q) >= _MIN_QUERY_LEN else None

    def _show_empty_state(self) -> None:
        frame = ctk.CTkFrame(self._results_list, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=60)

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

        ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(family=T.ui_family(), size=15, weight="bold"),
            text_color=T.TEXT_PRIMARY,
        ).pack()
        ctk.CTkLabel(
            frame,
            text=sub,
            font=T.font_small(),
            text_color=T.TEXT_SECONDARY,
            justify="center",
            wraplength=420,
        ).pack(pady=(8, 0))
        self._empty_frame = frame

    def _render_chips(self) -> None:
        for child in self._chips_wrap.winfo_children():
            child.destroy()

        # Channel chips — one per ON channel, with count.
        channel_counts = self._counts_per_channel(self._raw_results)
        any_chip = False
        for label, key, dot in _CHANNELS:
            if not self._channel_on[key].get():
                continue
            count = channel_counts.get(key, 0)
            chip = _ActiveFilterChip(
                self._chips_wrap,
                text=label,
                count=count,
                dot_color=dot,
                on_remove=lambda k=key: self._toggle_channel(k, force_value=False),
            )
            chip.pack(side="left", padx=(0, 8))
            any_chip = True

        # Time window chip — only when narrowed.
        if self._time_window.get() != "all":
            label = next(
                (lbl for lbl, k, _d in _TIME_WINDOWS if k == self._time_window.get()),
                "Time",
            )
            chip = _ActiveFilterChip(
                self._chips_wrap,
                text=label,
                count=None,
                dot_color=None,
                on_remove=lambda: self._set_time_window("all"),
            )
            chip.pack(side="left", padx=(0, 8))
            any_chip = True

        # Hide the wrap entirely when no chips so it doesn't reserve vertical
        # space above the results list.
        if any_chip:
            self._chips_wrap.pack_configure(pady=(0, 12))
        else:
            self._chips_wrap.pack_configure(pady=(0, 0))

    def _render_right_rail(self) -> None:
        # Channel group.
        self._channel_group.clear()
        channel_counts = self._counts_per_channel(self._raw_results)
        for label, key, dot in _CHANNELS:
            _make_check_row(
                self._channel_group._items_wrap,
                label=label,
                is_on=self._channel_on[key].get(),
                count=channel_counts.get(key, 0) if self._raw_results else None,
                on_toggle=lambda k=key: self._toggle_channel(k),
                dot_color=dot,
            )

        # Time window group — radio-style: exactly one selected.
        self._time_group.clear()
        for label, key, _delta in _TIME_WINDOWS:
            _make_check_row(
                self._time_group._items_wrap,
                label=label,
                is_on=self._time_window.get() == key,
                count=None,
                on_toggle=lambda k=key: self._set_time_window(k),
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

    # ── Row click ───────────────────────────────────────────────────────────

    def _on_row_selected(self, row: _SearchResultRow) -> None:
        if self._selected_row is row:
            row.set_selected(False)
            self._selected_row = None
            return
        if self._selected_row is not None:
            try:
                self._selected_row.set_selected(False)
            except Exception:
                pass
        row.set_selected(True)
        self._selected_row = row

    # ── Resize ──────────────────────────────────────────────────────────────

    _RESIZE_DEBOUNCE_MS = 80
    # dot(24+8+14) + ts(64+14) + player(120+14) + trailing(24)
    _ROW_FIXED_WIDTH_PX = 46 + 78 + 134 + 24

    def _on_resize(self, _event: tk.Event) -> None:
        if self._wrap_after_id is not None:
            try:
                self.after_cancel(self._wrap_after_id)
            except Exception:
                pass
        self._wrap_after_id = self.after(self._RESIZE_DEBOUNCE_MS, self._flush_row_wraplength)

    def _flush_row_wraplength(self) -> None:
        self._wrap_after_id = None
        try:
            list_width = self._results_list.winfo_width()
        except tk.TclError:
            return
        available = list_width - self._ROW_FIXED_WIDTH_PX
        if available <= 80 or available == self._last_wraplength:
            return
        self._last_wraplength = available
        for row in self._result_rows:
            row.set_body_wraplength(available)

    # ── Appearance-mode sync ────────────────────────────────────────────────

    def _set_appearance_mode(self, mode_string: str) -> None:
        super()._set_appearance_mode(mode_string)
        # Children with tuple colors auto-update; no manual refresh needed.
