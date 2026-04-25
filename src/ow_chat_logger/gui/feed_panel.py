from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable

import customtkinter as ctk

from ow_chat_logger.gui import icons as I
from ow_chat_logger.gui import theme as T
from ow_chat_logger.gui.backend_bridge import FeedEntry
from ow_chat_logger.gui.color_utils import hsv_bounds_to_hex
from ow_chat_logger.gui.config_io import load_ui_config
from ow_chat_logger.log_search import history_for_player

_MAX_ROWS = 500
_NEW_BADGE_MS = 2500  # how long the "NEW" badge stays visible
_MAX_RECENT_MESSAGES = 10  # shown inside the PlayerSidePanel


def _is_clickable_player(name: str) -> bool:
    cleaned = (name or "").strip()
    return bool(cleaned) and cleaned != "—"


def _bind_player_click(
    label: ctk.CTkLabel,
    player: str,
    on_click: Callable[[str], None] | None,
) -> None:
    """Give a player label hover underline + click-to-history behavior.

    No-op when ``on_click`` is not wired or the player is a placeholder.
    """
    if on_click is None or not _is_clickable_player(player):
        return

    base_font = label.cget("font")
    # CTkFont is the expected type here; fall back gracefully on mismatch.
    try:
        hover_font = ctk.CTkFont(
            family=base_font.cget("family"),
            size=base_font.cget("size"),
            weight=base_font.cget("weight"),
            underline=True,
        )
    except Exception:
        hover_font = base_font

    def _enter(_e: tk.Event) -> None:
        label.configure(cursor="hand2", font=hover_font)

    def _leave(_e: tk.Event) -> None:
        label.configure(cursor="", font=base_font)

    def _click(_e: tk.Event) -> None:
        on_click(player.strip())

    label.bind("<Enter>", _enter, add="+")
    label.bind("<Leave>", _leave, add="+")
    label.bind("<Button-1>", _click, add="+")


# ── Message row widget ────────────────────────────────────────────────────────


class MessageRow(ctk.CTkFrame):
    """Compact chat row: channel dot, player, message (wraps), timestamp.

    Supports a ``selected`` visual state (accent bg + left accent border +
    accent-tinted player name) and a short-lived "NEW" badge on newly
    appended rows. Both are driven by ``FeedPanel``.
    """

    def __init__(
        self,
        parent: tk.Widget,
        entry: FeedEntry,
        dot_color: str | None,
        on_select: Callable[["MessageRow"], None] | None = None,
    ) -> None:
        super().__init__(
            parent,
            fg_color="transparent",
            corner_radius=0,
        )
        self._entry = entry
        self._on_select = on_select
        self._selected = False
        self._new_badge_label: ctk.CTkLabel | None = None
        self._new_badge_after_id: str | None = None
        self._hover = False
        self._build(dot_color)
        # No per-row <Configure> binding here — the parent FeedPanel listens
        # for resizes once, debounces, and batches wraplength updates across
        # every row. Per-row bindings are O(visible-rows × resize-events) and
        # made dragging the window visibly laggy.
        if self._on_select is not None and _is_clickable_player(entry.player):
            self._bind_hover()
            self._bind_clicks(self._handle_click)

    def _build(self, dot_color: str | None) -> None:
        # Layout: [dot] [mono ts] [bold player] [flexible body] [badge]
        # Columns are 0..4 — no separate stripe column. Selection is indicated
        # by the row background tint + accent-tinted player name.
        self.grid_columnconfigure(3, weight=1)

        # Leading channel dot — tracks the user's chosen team/all chat color.
        self._dot = ctk.CTkLabel(
            self,
            text="●",
            text_color=dot_color if dot_color else T.pick(T.TEXT_DIM),
            font=ctk.CTkFont(size=10),
        )
        self._dot.grid(row=0, column=0, padx=(24, 14), pady=9, sticky="w")

        ts = self._entry.timestamp.split(" ")[-1] if self._entry.timestamp else ""
        ctk.CTkLabel(
            self,
            text=ts,
            text_color=T.TEXT_DIM,
            font=ctk.CTkFont(family=T.mono_family(), size=11),
            width=64,
            anchor="w",
        ).grid(row=0, column=1, padx=(0, 14), pady=9, sticky="w")

        player_name = self._entry.player or "—"
        self._player_label = ctk.CTkLabel(
            self,
            text=player_name,
            text_color=T.TEXT_PRIMARY,
            font=T.font_button(),
            width=140,
            anchor="w",
        )
        self._player_label.grid(row=0, column=2, padx=(0, 14), pady=9, sticky="w")

        body = ctk.CTkLabel(
            self,
            text=self._entry.text,
            text_color=T.TEXT_SECONDARY,
            font=T.font_body(),
            anchor="w",
            justify="left",
            wraplength=600,
        )
        body.grid(row=0, column=3, padx=(0, 24), pady=9, sticky="ew")
        self._body = body

    def _bind_clicks(self, handler: Callable[[tk.Event], None]) -> None:
        """Bind ``handler`` to every visible child — the whole row is clickable."""
        self.bind("<Button-1>", handler, add="+")
        for child in self.winfo_children():
            try:
                child.bind("<Button-1>", handler, add="+")
            except tk.TclError:
                pass
        # Hand-cursor on the interactive row surface.
        self.configure(cursor="hand2")
        for child in self.winfo_children():
            try:
                child.configure(cursor="hand2")
            except Exception:
                pass

    def _bind_hover(self) -> None:
        """Robust row hover that survives <Enter>/<Leave> flips on children.

        Tk fires a <Leave> on the parent whenever the pointer crosses into a
        child widget — if we only listen on ``self``, hover flickers off the
        moment the cursor enters any label inside the row. Fix: bind on every
        child too, and in the <Leave> handler check if the pointer is still
        physically inside this row's bounding box before turning hover off.
        """

        def _enter(_e: tk.Event) -> None:
            if not self._hover:
                self._hover = True
                self._apply_bg()

        def _leave(_e: tk.Event) -> None:
            # Re-check: the pointer may still be over a descendant.
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

        self.bind("<Enter>", _enter, add="+")
        self.bind("<Leave>", _leave, add="+")
        for child in self.winfo_children():
            try:
                child.bind("<Enter>", _enter, add="+")
                child.bind("<Leave>", _leave, add="+")
            except tk.TclError:
                pass

    def _handle_click(self, _e: tk.Event) -> None:
        if self._on_select is not None:
            self._on_select(self)

    # ── Public mutators ───────────────────────────────────────────────────

    def set_dot_color(self, color: str | None) -> None:
        self._dot.configure(text_color=color if color else T.pick(T.TEXT_DIM))

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self._player_label.configure(text_color=T.ACCENT if selected else T.TEXT_PRIMARY)
        self._apply_bg()

    def flash_new_badge(self) -> None:
        """Show an accent 'NEW' badge on this row that fades after ~2.5s."""
        self._cancel_new_badge()
        badge = ctk.CTkLabel(
            self,
            text="NEW",
            text_color=T.ACCENT,
            fg_color=T.ACCENT_SUBTLE,
            font=ctk.CTkFont(family=T.ui_family(), size=9, weight="bold"),
            corner_radius=4,
            padx=7,
            pady=1,
        )
        badge.grid(row=0, column=4, padx=(0, 16), pady=9, sticky="e")
        self._new_badge_label = badge
        self._new_badge_after_id = self.after(_NEW_BADGE_MS, self._cancel_new_badge)

    def _cancel_new_badge(self) -> None:
        if self._new_badge_after_id is not None:
            try:
                self.after_cancel(self._new_badge_after_id)
            except Exception:
                pass
            self._new_badge_after_id = None
        if self._new_badge_label is not None:
            try:
                self._new_badge_label.destroy()
            except Exception:
                pass
            self._new_badge_label = None

    def destroy(self) -> None:  # type: ignore[override]
        self._cancel_new_badge()
        super().destroy()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def chat_type(self) -> str:
        return (self._entry.chat_type or "").lower()

    @property
    def player(self) -> str:
        return (self._entry.player or "").strip()

    @property
    def entry(self) -> FeedEntry:
        return self._entry

    # ── Layout / visual helpers ───────────────────────────────────────────

    def set_body_wraplength(self, wraplength: int) -> None:
        """Push a wraplength value into this row's body label.

        Called in batch by ``FeedPanel`` after a debounced resize, instead of
        each row listening to its own ``<Configure>`` event.
        """
        if wraplength > 80:
            try:
                self._body.configure(wraplength=wraplength)
            except tk.TclError:
                pass

    def _apply_bg(self) -> None:
        if self._selected:
            self.configure(fg_color=T.ACCENT_SUBTLE)
        elif self._hover:
            # Subtle hover — matches the Console design's 2.5%-alpha feel on
            # both light and dark surfaces. BG_CHROME sits one tick above
            # BG_ROOT without competing with the selection accent.
            self.configure(fg_color=T.BG_CHROME)
        else:
            self.configure(fg_color="transparent")


# ── Hero event row — stands out from real chat ────────────────────────────────


class HeroRow(ctk.CTkFrame):
    """Hero-pick log event — deliberately not styled like chat.

    Hero rows are not selectable (per design they're tracking markers, not
    chat lines). The player name is still a clickable affordance that routes
    to the same ``on_player_click`` handler the FeedPanel provides.
    """

    def __init__(
        self,
        parent: tk.Widget,
        entry: FeedEntry,
        on_player_click: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self._on_player_click = on_player_click
        self._entry = entry
        self._build(entry)

    def _build(self, entry: FeedEntry) -> None:
        # Same five-column layout as MessageRow so dot/ts/player line up.
        self.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            self,
            text="●",
            text_color=T.CHAT_HERO,
            font=ctk.CTkFont(size=10),
        ).grid(row=0, column=0, padx=(24, 14), pady=9, sticky="w")

        ts = entry.timestamp.split(" ")[-1] if entry.timestamp else ""
        ctk.CTkLabel(
            self,
            text=ts,
            text_color=T.TEXT_DIM,
            font=ctk.CTkFont(family=T.mono_family(), size=11),
            width=64,
            anchor="w",
        ).grid(row=0, column=1, padx=(0, 14), pady=9, sticky="w")

        player = entry.player or "—"
        hero = entry.text or "—"
        italic = ctk.CTkFont(family=T.ui_family(), size=12, slant="italic")

        player_label = ctk.CTkLabel(
            self,
            text=player,
            text_color=T.TEXT_MUTED,
            font=italic,
            width=140,
            anchor="w",
        )
        player_label.grid(row=0, column=2, padx=(0, 14), pady=9, sticky="w")
        _bind_player_click(player_label, player, self._on_player_click)

        ctk.CTkLabel(
            self,
            text=f"→  {hero}",
            text_color=T.CHAT_HERO,
            font=italic,
            anchor="w",
        ).grid(row=0, column=3, padx=(0, 24), pady=9, sticky="ew")

    @property
    def chat_type(self) -> str:
        return "hero"

    @property
    def entry(self) -> FeedEntry:
        return self._entry


# ── Filter-pill widget for the feed header ────────────────────────────────────


class _FilterPill(ctk.CTkFrame):
    """One of the All / Team / All chat pills in the feed header."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        label: str,
        key: str,  # "all" (meta) | "team" | "all_chat"
        dot_color: tuple[str, str] | None,
        on_click: Callable[[str], None],
    ) -> None:
        super().__init__(
            parent,
            fg_color="transparent",
            corner_radius=7,
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
        )
        self._key = key
        self._label = label
        self._active = False
        self._on_click = on_click

        # Dot (optional) + label + count
        col = 0
        if dot_color is not None:
            self._dot = ctk.CTkLabel(
                self,
                text="●",
                text_color=dot_color,
                font=ctk.CTkFont(size=9),
            )
            self._dot.grid(row=0, column=col, padx=(10, 6), pady=4, sticky="w")
            col += 1
        self._label_widget = ctk.CTkLabel(
            self,
            text=label,
            text_color=T.TEXT_SECONDARY,
            font=T.font_caption(),
        )
        self._label_widget.grid(
            row=0, column=col, padx=(0 if dot_color is not None else 11, 6), pady=4, sticky="w"
        )
        col += 1
        self._count_widget = ctk.CTkLabel(
            self,
            text="",
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(family=T.mono_family(), size=10),
        )
        self._count_widget.grid(row=0, column=col, padx=(0, 11), pady=4, sticky="w")

        for w in (self, self._label_widget, self._count_widget):
            w.configure(cursor="hand2")
            w.bind("<Button-1>", self._handle_click, add="+")
        if dot_color is not None:
            self._dot.configure(cursor="hand2")
            self._dot.bind("<Button-1>", self._handle_click, add="+")

    def _handle_click(self, _e: tk.Event) -> None:
        self._on_click(self._key)

    def set_count(self, n: int | None) -> None:
        self._count_widget.configure(text="" if n is None else str(n))

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = active
        if active:
            self.configure(fg_color=T.ACCENT_SUBTLE, border_color=T.ACCENT)
            self._label_widget.configure(text_color=T.ACCENT)
            self._count_widget.configure(text_color=T.ACCENT)
        else:
            self.configure(fg_color="transparent", border_color=T.BORDER_HAIRLINE)
            self._label_widget.configure(text_color=T.TEXT_SECONDARY)
            self._count_widget.configure(text_color=T.TEXT_MUTED)


# ── Mini-stat block (used inside the PlayerSidePanel) ─────────────────────────


class _MiniStat(ctk.CTkFrame):
    """Small bordered stat cell — label on top, value below."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        label: str,
        value: str = "—",
        mono: bool = False,
        accent: bool = False,
        value_size: int = 13,
        dot_color: tuple[str, str] | str | None = None,
    ) -> None:
        super().__init__(
            parent,
            fg_color=T.BG_ELEV,
            border_color=T.BORDER_HAIRLINE,
            border_width=1,
            corner_radius=7,
            height=58,
        )
        self._mono = mono
        self._accent = accent
        # Lock the cell to its declared height so the 3-row grid below can
        # actually center the content vertically. Without this, propagation
        # shrinks the frame to its content's natural size and there's no
        # slack for the spacer rows to absorb.
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)  # top spacer
        self.grid_rowconfigure(2, weight=1)  # bottom spacer
        self.grid_columnconfigure(0, weight=1)

        # Centered content stack — label / value / sub-value packed top-down
        # inside an inner frame that sits in the middle row of the parent grid.
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="ew", padx=9)

        ctk.CTkLabel(
            content,
            text=label.upper(),
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(family=T.ui_family(), size=8, weight="bold"),
            anchor="w",
            height=12,
        ).pack(fill="x", anchor="w")

        # Main value row (with optional leading dot).
        row = ctk.CTkFrame(content, fg_color="transparent", height=18)
        row.pack(fill="x", anchor="w", pady=(2, 0))
        if dot_color is not None:
            ctk.CTkLabel(
                row,
                text="●",
                text_color=dot_color,
                font=ctk.CTkFont(size=8),
            ).pack(side="left", padx=(0, 5))

        self._value_label = ctk.CTkLabel(
            row,
            text=value,
            text_color=T.ACCENT if accent else T.TEXT_PRIMARY,
            font=ctk.CTkFont(
                family=T.mono_family() if mono else T.ui_family(),
                size=value_size,
                weight="bold",
            ),
            anchor="w",
            height=18,
        )
        self._value_label.pack(side="left")

        # Sub-value line (e.g. seconds-precision time under a date). Always
        # packed — even when empty — so every cell reserves the same height
        # and the 2×2 grid stays visually aligned. ``set_subvalue`` only
        # changes the text.
        self._subvalue_label = ctk.CTkLabel(
            content,
            text=" ",  # non-empty so the label keeps its line height
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(family=T.mono_family(), size=9),
            anchor="w",
            height=12,
        )
        self._subvalue_label.pack(fill="x", anchor="w")

    def set_value(self, value: str) -> None:
        self._value_label.configure(text=value)

    def set_subvalue(self, text: str) -> None:
        # Empty falls back to a single space so the line keeps its height.
        self._subvalue_label.configure(text=text or " ")


# ── Player side panel ─────────────────────────────────────────────────────────


class PlayerSidePanel(ctk.CTkFrame):
    """300px right-side panel with the selected player's stats and history.

    Hidden by default — FeedPanel calls :meth:`show_player` when a row is
    selected and :meth:`hide` when it's deselected.
    """

    WIDTH = 300

    def __init__(
        self,
        parent: tk.Widget,
        *,
        chat_log_path: Path,
        hero_log_path: Path,
        on_close: Callable[[], None],
        on_open_in_search: Callable[[str], None],
    ) -> None:
        super().__init__(
            parent,
            fg_color=T.BG_CHROME,
            width=self.WIDTH,
            corner_radius=0,
        )
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._chat_log_path = chat_log_path
        self._hero_log_path = hero_log_path
        self._on_close = on_close
        self._on_open_in_search = on_open_in_search
        self._current_player: str = ""
        self._recent_rows: list[ctk.CTkFrame] = []
        self._build()

    def _build(self) -> None:
        # Header: "Player" label + name pill + ↗ search + × close
        header = ctk.CTkFrame(self, fg_color="transparent", height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Player",
            text_color=T.TEXT_PRIMARY,
            font=ctk.CTkFont(family=T.ui_family(), size=13, weight="bold"),
        ).pack(side="left", padx=(20, 10), pady=14)

        self._name_pill = ctk.CTkLabel(
            header,
            text="—",
            text_color=T.ACCENT,
            fg_color=T.ACCENT_SUBTLE,
            font=ctk.CTkFont(family=T.ui_family(), size=12, weight="bold"),
            corner_radius=5,
            padx=10,
            pady=3,
        )
        self._name_pill.pack(side="left", pady=14)

        close_btn = ctk.CTkButton(
            header,
            text="×",
            width=22,
            height=22,
            corner_radius=4,
            fg_color="transparent",
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_DIM,
            font=ctk.CTkFont(family=T.ui_family(), size=16),
            command=self._handle_close,
        )
        close_btn.pack(side="right", padx=(0, 16), pady=14)

        open_btn = ctk.CTkButton(
            header,
            text="Search",
            image=I.icon("search", 12, color=T.TEXT_SECONDARY),
            compound="left",
            width=0,
            height=22,
            corner_radius=6,
            fg_color="transparent",
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_SECONDARY,
            font=T.font_caption(),
            command=self._handle_open_in_search,
        )
        open_btn.pack(side="right", padx=(0, 6), pady=14)

        # Hairline under the header
        ctk.CTkFrame(self, height=1, fg_color=T.BORDER_HAIRLINE, corner_radius=0).pack(fill="x")

        # Body — stats grid + recent messages
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(16, 16))

        # 2×2 stats grid
        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1, uniform="stat")
        grid.grid_columnconfigure(1, weight=1, uniform="stat")

        self._stat_messages = _MiniStat(grid, label="Messages", value="0")
        self._stat_messages.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=(0, 10))

        # Two-line value — date on top (main), time underneath (sub) — so the
        # full datetime fits inside the half-width cell without truncation.
        self._stat_first_seen = _MiniStat(
            grid, label="First seen", value="—", mono=True, value_size=11
        )
        self._stat_first_seen.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=(0, 10))

        self._stat_channel = _MiniStat(grid, label="Channel", value="—")
        self._stat_channel.grid(row=1, column=0, sticky="ew", padx=(0, 5))

        self._stat_current = _MiniStat(grid, label="Current", value="—", accent=True)
        self._stat_current.grid(row=1, column=1, sticky="ew", padx=(5, 0))

        # Recent messages section
        ctk.CTkLabel(
            body,
            text="RECENT MESSAGES",
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(family=T.ui_family(), size=9, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(20, 10))

        self._recent_list = ctk.CTkScrollableFrame(
            body,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=T.BORDER_HOVER,
            scrollbar_button_hover_color=T.TEXT_MUTED,
        )
        self._recent_list.pack(fill="both", expand=True)

        self._recent_empty = ctk.CTkLabel(
            self._recent_list,
            text="No messages yet this session.",
            text_color=T.TEXT_MUTED,
            font=T.font_caption(),
            anchor="w",
        )
        self._recent_empty.pack(fill="x", pady=4)

    # ── Public API ───────────────────────────────────────────────────────

    def show_player(self, player: str) -> None:
        """Populate every surface for ``player`` from the full on-disk history.

        Reads ``chat_log.csv`` + ``hero_log.csv`` once (via the existing
        :func:`history_for_player`) and derives Messages / First seen /
        Channel / Current hero plus the recent-messages list from the
        returned :class:`SearchResultSet`. Covers the player's full history
        across sessions, not just messages observed since the GUI started.
        """
        self._current_player = player
        self._name_pill.configure(text=player or "—")

        chat_results, hero_results = self._load_history(player)

        # Messages — total count across history.
        self._stat_messages.set_value(str(len(chat_results)))

        # First seen — oldest timestamp in chat history (results are
        # newest-first; the last element is the earliest). Date and time
        # split across two lines so the full datetime fits the half-width
        # cell without truncating.
        if chat_results:
            raw = chat_results[-1].timestamp or ""
            date_part, _, time_part = raw.partition(" ")
            self._stat_first_seen.set_value(date_part or raw or "—")
            self._stat_first_seen.set_subvalue(time_part)
        else:
            self._stat_first_seen.set_value("—")
            self._stat_first_seen.set_subvalue("")

        # Channel — most-used over history (source is "team" or "all" for
        # chat rows). Tie-breaks toward team, the more common default.
        team_n = sum(1 for r in chat_results if r.source == "team")
        all_n = sum(1 for r in chat_results if r.source == "all")
        if team_n == 0 and all_n == 0:
            channel_label = "—"
        elif team_n >= all_n:
            channel_label = "Team"
        else:
            channel_label = "All chat"
        self._stat_channel.set_value(channel_label)

        # Current hero — newest hero entry (results are newest-first).
        current_hero = next(
            (r.text.strip() for r in hero_results if r.text and r.text.strip()),
            None,
        )
        self._stat_current.set_value(current_hero or "—")

        # Recent chat messages — newest 5.
        recent = [
            {
                "timestamp": (r.timestamp or "").split(" ")[-1],
                "channel": r.source,
                "text": r.text or "",
            }
            for r in chat_results[:_MAX_RECENT_MESSAGES]
        ]
        self._render_recent(recent)

    def hide(self) -> None:
        self._current_player = ""

    # ── Internals ────────────────────────────────────────────────────────

    def _handle_close(self) -> None:
        self._on_close()

    def _handle_open_in_search(self) -> None:
        if self._current_player:
            self._on_open_in_search(self._current_player)

    def _load_history(self, player: str):
        """Read full on-disk history for ``player`` and split by source.

        Returns ``(chat_results, hero_results)`` — both newest-first. On any
        I/O error returns empty lists so the panel still renders gracefully.
        """
        try:
            rs = history_for_player(
                player,
                chat_log_path=self._chat_log_path,
                hero_log_path=self._hero_log_path,
            )
        except Exception:
            return [], []
        chat_results = [r for r in rs.results if r.source in ("team", "all")]
        hero_results = [r for r in rs.results if r.source == "hero"]
        return chat_results, hero_results

    def _render_recent(self, messages: list[dict]) -> None:
        for w in self._recent_rows:
            w.destroy()
        self._recent_rows.clear()
        if self._recent_empty.winfo_ismapped():
            self._recent_empty.pack_forget()
        if not messages:
            self._recent_empty.pack(fill="x", pady=4)
            return

        for i, m in enumerate(messages[:_MAX_RECENT_MESSAGES]):
            # Compact two-line message: meta row (dot + ts + CHANNEL) on top,
            # body underneath. Tight padding, hairline divider between entries.
            row = ctk.CTkFrame(self._recent_list, fg_color="transparent")
            row.pack(fill="x", pady=(0, 0))

            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", pady=(6, 1))
            channel = (m.get("channel") or "").lower()
            dot_color = (
                T.CHAT_TEAM if channel == "team" else T.CHAT_ALL if channel == "all" else T.TEXT_DIM
            )
            ctk.CTkLabel(
                top,
                text="●",
                text_color=dot_color,
                font=ctk.CTkFont(size=8),
            ).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(
                top,
                text=m.get("timestamp") or "",
                text_color=T.TEXT_DIM,
                font=ctk.CTkFont(family=T.mono_family(), size=10),
            ).pack(side="left", padx=(0, 8))
            if channel:
                ctk.CTkLabel(
                    top,
                    text=channel.upper(),
                    text_color=T.TEXT_MUTED,
                    font=ctk.CTkFont(family=T.ui_family(), size=9, weight="bold"),
                ).pack(side="left")
            ctk.CTkLabel(
                row,
                text=m.get("text") or "",
                text_color=T.TEXT_SECONDARY,
                font=ctk.CTkFont(family=T.ui_family(), size=12),
                anchor="w",
                justify="left",
                wraplength=self.WIDTH - 56,
            ).pack(fill="x", padx=(14, 0), pady=(0, 7))
            self._recent_rows.append(row)

            if i < len(messages) - 1:
                div = ctk.CTkFrame(
                    self._recent_list, height=1, fg_color=T.BORDER_FAINT, corner_radius=0
                )
                div.pack(fill="x")
                self._recent_rows.append(div)


def _load_chat_colors() -> dict[str, str]:
    """Resolve the user's picked team/all colors (hex) from saved config."""
    cfg = load_ui_config()
    out: dict[str, str] = {}
    for key in ("team", "all"):
        try:
            out[key] = hsv_bounds_to_hex(cfg[f"{key}_hsv_lower"], cfg[f"{key}_hsv_upper"])
        except Exception:
            out[key] = T.pick(T.CHAT_TEAM if key == "team" else T.CHAT_ALL)
    return out


# ── Onboarding side panel (shown alongside the empty state) ──────────────────


class OnboardingSidePanel(ctk.CTkFrame):
    """Right column shown before recording starts (Empty V3 design).

    Mirrors PlayerSidePanel's surface but renders the user's current capture
    config — Region / Interval / Team color / All chat color — plus an
    accent-tinted Tip card. Mutually exclusive with the player side panel:
    onboarding shows when the feed is empty, player shows when a row is
    selected.

    Narrower than ``PlayerSidePanel`` (which needs room for a stats grid +
    recent messages list) so the empty live feed reads as the primary focus
    on first launch.
    """

    WIDTH = 285

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(
            parent,
            fg_color=T.BG_CHROME,
            width=self.WIDTH,
            corner_radius=0,
        )
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._build()
        self.refresh()

    def _build(self) -> None:
        # Header: section title
        header = ctk.CTkFrame(self, fg_color="transparent", height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header,
            text="Configuration",
            text_color=T.TEXT_PRIMARY,
            font=ctk.CTkFont(family=T.ui_family(), size=13, weight="bold"),
        ).pack(side="left", padx=20, pady=14)

        ctk.CTkFrame(self, height=1, fg_color=T.BORDER_HAIRLINE, corner_radius=0).pack(fill="x")

        # Body — config rows + accent-tinted tip card
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(14, 14))

        self._rows_wrap = ctk.CTkFrame(body, fg_color="transparent")
        self._rows_wrap.pack(fill="x")

        # Tip card — accent-tinted background, accent-colored heading.
        tip = ctk.CTkFrame(
            body,
            fg_color=T.ACCENT_SUBTLE,
            border_color=T.ACCENT_SUBTLE,
            border_width=1,
            corner_radius=8,
        )
        tip.pack(fill="x", pady=(16, 0))

        ctk.CTkLabel(
            tip,
            text="TIP",
            text_color=T.ACCENT,
            font=ctk.CTkFont(family=T.ui_family(), size=9, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 0))
        ctk.CTkLabel(
            tip,
            text=(
                "If messages aren't being detected reliably, tweak the "
                "capture interval and the chat color detection thresholds "
                "in Settings."
            ),
            text_color=T.TEXT_SECONDARY,
            font=ctk.CTkFont(family=T.ui_family(), size=11),
            anchor="w",
            justify="left",
            wraplength=self.WIDTH - 64,
        ).pack(fill="x", padx=12, pady=(2, 10))

    def refresh(self) -> None:
        """Re-read the current config and rebuild the rows.

        Called on first show and whenever the user saves Settings, so the
        onboarding panel always reflects the values that will actually be
        used when Start is pressed.

        Region is intentionally omitted — it's a fixed-by-the-game value the
        user shouldn't have to think about and lives in the Advanced section
        of Settings as read-only.
        """
        for child in self._rows_wrap.winfo_children():
            child.destroy()

        cfg = load_ui_config()
        chat_colors = _load_chat_colors()

        interval = cfg.get("capture_interval")
        if isinstance(interval, (int, float)):
            interval_text = f"{float(interval):.1f}s"
        else:
            interval_text = "—"
        self._row_value(self._rows_wrap, "Interval", interval_text, mono=True)

        self._row_chip(self._rows_wrap, "Team color", chat_colors.get("team", T.pick(T.CHAT_TEAM)))
        self._row_chip(
            self._rows_wrap, "All chat color", chat_colors.get("all", T.pick(T.CHAT_ALL))
        )

    # ── Row primitives ───────────────────────────────────────────────────

    def _row_shell(self, parent: tk.Widget) -> ctk.CTkFrame:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=4)
        return row

    def _row_value(self, parent: tk.Widget, label: str, value: str, *, mono: bool = False) -> None:
        row = self._row_shell(parent)
        ctk.CTkLabel(
            row,
            text=label,
            text_color=T.TEXT_SECONDARY,
            font=ctk.CTkFont(family=T.ui_family(), size=12),
            anchor="w",
        ).pack(side="left")
        ctk.CTkLabel(
            row,
            text=value,
            text_color=T.TEXT_PRIMARY,
            font=ctk.CTkFont(
                family=T.mono_family() if mono else T.ui_family(),
                size=12,
                weight="bold",
            ),
            anchor="e",
        ).pack(side="right")

    def _row_chip(self, parent: tk.Widget, label: str, hex_color: str) -> None:
        row = self._row_shell(parent)
        ctk.CTkLabel(
            row,
            text=label,
            text_color=T.TEXT_SECONDARY,
            font=ctk.CTkFont(family=T.ui_family(), size=12),
            anchor="w",
        ).pack(side="left")
        ctk.CTkFrame(
            row,
            width=18,
            height=14,
            fg_color=hex_color,
            border_color=T.BORDER_HAIRLINE,
            border_width=1,
            corner_radius=4,
        ).pack(side="right", pady=2)


# ── Feed panel ────────────────────────────────────────────────────────────────


class FeedPanel(ctk.CTkFrame):
    def __init__(
        self,
        parent: tk.Widget,
        *,
        chat_log_path: Path,
        hero_log_path: Path,
        on_open_in_search: Callable[[str], None] | None = None,
        on_start: Callable[[], None] | None = None,
    ) -> None:
        # Edge-to-edge treatment per the Console design — the feed fills the
        # main area flush with the window, with hairline borders instead of a
        # rounded card.
        super().__init__(
            parent,
            fg_color=T.BG_ROOT,
            corner_radius=0,
            border_width=0,
        )
        self._chat_log_path = chat_log_path
        self._hero_log_path = hero_log_path
        self._on_open_in_search = on_open_in_search
        self._on_start = on_start

        self._count = 0
        self._counts: dict[str, int] = {"team": 0, "all": 0}
        self._rows: list[tk.Widget] = []
        self._players_seen: set[str] = set()
        self._filter: str = "all"  # "all" | "team" | "all_chat"
        self._selected_row: MessageRow | None = None
        self._auto_scroll = tk.BooleanVar(value=True)
        self._empty_frame: ctk.CTkFrame | None = None
        self._empty_start_btn: ctk.CTkButton | None = None
        self._jump_pill: ctk.CTkButton | None = None
        self._chat_colors: dict[str, str] = _load_chat_colors()
        self._status_kind: str = "idle"
        self._wrap_after_id: str | None = None
        self._last_wraplength: int = 0
        self._build()
        self._show_empty_state()
        # Single resize listener — debounces and batches per-row wraplength
        # updates across all currently-mounted MessageRows.
        self.bind("<Configure>", self._on_panel_resize)

    def refresh_chat_colors(self) -> None:
        """Re-read the user's team/all colors and update existing dots."""
        self._chat_colors = _load_chat_colors()
        for row in self._rows:
            if isinstance(row, MessageRow):
                row.set_dot_color(self._chat_colors.get(row.chat_type))
        # Filter pill dots also follow the configured channel colors.
        self._refresh_filter_dots()
        # Onboarding panel mirrors Region/Interval/colors — refresh too.
        if hasattr(self, "_onboarding_panel"):
            self._onboarding_panel.refresh()

    def _dot_color_for(self, entry: FeedEntry) -> str | None:
        ct = (entry.chat_type or "").lower()
        return self._chat_colors.get(ct)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Root is a 3-column grid: feed-column | hairline divider | side panel.
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # Feed column hosts the existing header/hairline/body/footer stack.
        self._feed_column = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._feed_column.grid(row=0, column=0, sticky="nsew")

        self._side_divider = ctk.CTkFrame(
            self, width=1, fg_color=T.BORDER_HAIRLINE, corner_radius=0
        )
        # Placed/removed alongside the side panel.

        self._side_panel = PlayerSidePanel(
            self,
            chat_log_path=self._chat_log_path,
            hero_log_path=self._hero_log_path,
            on_close=self._deselect_and_hide_panel,
            on_open_in_search=self._handle_open_in_search,
        )
        # Hidden until a row is selected.

        # Onboarding panel — same column 2 slot, but shown when the feed is
        # empty (Empty V3 design). Mutually exclusive with the player panel.
        self._onboarding_panel = OnboardingSidePanel(self)

        self._build_feed_column(self._feed_column)

    def _build_feed_column(self, parent: ctk.CTkFrame) -> None:
        # Header — 14×24 padding to match the design spec exactly.
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=14)

        ctk.CTkLabel(
            header,
            text="Live feed",
            text_color=T.TEXT_PRIMARY,
            font=ctk.CTkFont(family=T.ui_family(), size=13, weight="bold"),
        ).pack(side="left", padx=(0, 12))

        self._header_count = ctk.CTkLabel(
            header,
            text="waiting for first message",
            text_color=T.TEXT_MUTED,
            font=T.font_small(),
        )
        self._header_count.pack(side="left")

        # Filter pills — anchored to the right of the header.
        pills_wrap = ctk.CTkFrame(header, fg_color="transparent")
        pills_wrap.pack(side="right")

        self._filter_pills: dict[str, _FilterPill] = {}
        for key, label, dot in (
            ("all", "All", None),
            ("team", "Team", T.CHAT_TEAM),
            ("all_chat", "All chat", T.CHAT_ALL),
        ):
            pill = _FilterPill(
                pills_wrap,
                label=label,
                key=key,
                dot_color=dot,
                on_click=self._set_filter,
            )
            pill.pack(side="left", padx=(0, 6))
            self._filter_pills[key] = pill

        self._filter_pills["all"].set_active(True)

        # Hairline divider under header
        ctk.CTkFrame(parent, height=1, fg_color=T.BORDER_HAIRLINE, corner_radius=0).pack(
            fill="x", padx=0
        )

        # Body container holds scrollable list + overlays (empty state, pill)
        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=0, pady=(0, 0))
        self._body = body

        self._list = ctk.CTkScrollableFrame(
            body,
            fg_color=T.BG_ROOT,
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
        footer = ctk.CTkFrame(parent, fg_color="transparent")
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

        # Three accent dots with fading opacity — matches the Console direction.
        dots = ctk.CTkFrame(frame, fg_color="transparent")
        dots.pack(pady=(20, 18))
        for _ in range(3):
            ctk.CTkLabel(
                dots,
                text="●",
                text_color=T.ACCENT,
                font=ctk.CTkFont(size=11),
            ).pack(side="left", padx=3)

        ctk.CTkLabel(
            frame,
            text="Nothing captured yet",
            font=ctk.CTkFont(family=T.ui_family(), size=17, weight="bold"),
            text_color=T.TEXT_PRIMARY,
        ).pack()
        ctk.CTkLabel(
            frame,
            text="Your capture region is set. Press Start or jump into a match —\nmessages will stream in here.",
            font=T.font_small(),
            text_color=T.TEXT_SECONDARY,
            justify="center",
        ).pack(pady=(8, 0))

        # Inline Start button (Empty V3 design). Only visible while idle —
        # status changes hide it via ``set_status``.
        self._empty_start_btn = ctk.CTkButton(
            frame,
            text="Start recording",
            image=I.icon("play", 10, color=T.ACCENT_FG),
            compound="left",
            width=144,
            height=32,
            corner_radius=7,
            font=ctk.CTkFont(family=T.ui_family(), size=12, weight="bold"),
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            text_color=T.ACCENT_FG,
            command=self._handle_empty_start,
        )
        self._empty_start_btn.pack(pady=(20, 0))
        if self._status_kind != "idle" or self._on_start is None:
            self._empty_start_btn.pack_forget()

        self._empty_frame = frame

        # Show the onboarding side panel alongside the empty state, unless a
        # player is currently selected (player panel takes priority).
        if self._selected_row is None:
            self._show_onboarding_panel()

    def _hide_empty_state(self) -> None:
        if self._empty_frame is not None:
            self._empty_frame.destroy()
            self._empty_frame = None
        self._empty_start_btn = None
        # Onboarding panel only makes sense alongside the empty state.
        self._hide_onboarding_panel()

    def _handle_empty_start(self) -> None:
        if self._on_start is not None:
            self._on_start()

    # ── Appearance-mode sync ──────────────────────────────────────────────────

    def _set_appearance_mode(self, mode_string: str) -> None:
        super()._set_appearance_mode(mode_string)
        # Children with tuple colors auto-update; nothing else to do here.

    # ── Filter pills ──────────────────────────────────────────────────────────

    def _set_filter(self, key: str) -> None:
        if self._filter == key:
            return
        self._filter = key
        for k, pill in self._filter_pills.items():
            pill.set_active(k == key)
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Show/hide rows based on the current filter. Preserves feed order."""
        for row in self._rows:
            if self._row_matches_filter(row):
                if not row.winfo_ismapped():
                    row.pack(fill="x")
            else:
                row.pack_forget()

    def _row_matches_filter(self, row: tk.Widget) -> bool:
        if self._filter == "all":
            return True
        ct = getattr(row, "chat_type", "")
        if self._filter == "team":
            return ct == "team"
        if self._filter == "all_chat":
            return ct == "all"
        return True

    def _refresh_filter_dots(self) -> None:
        # No-op right now: pill dots use the design's CHAT_TEAM/CHAT_ALL tuple.
        # If we ever drive the dot from the user-picked HSV colors this is
        # where we'd push the update.
        pass

    def _update_pill_counts(self) -> None:
        self._filter_pills["all"].set_count(self._count if self._count > 0 else None)
        self._filter_pills["team"].set_count(
            self._counts["team"] if self._counts["team"] > 0 else None
        )
        self._filter_pills["all_chat"].set_count(
            self._counts["all"] if self._counts["all"] > 0 else None
        )

    # ── Message append / clear ────────────────────────────────────────────────

    def append_message(self, entry: FeedEntry) -> None:
        self._hide_empty_state()

        self._count += 1
        ct = (entry.chat_type or "").lower()
        if ct in self._counts:
            self._counts[ct] += 1
        if entry.player and entry.player.strip() and entry.player.strip() != "—":
            self._players_seen.add(entry.player.strip())

        self._refresh_header_count()
        self._update_pill_counts()

        # No hairline between rows — design uses row padding for separation.
        row: tk.Widget
        if entry.category == "hero":
            # Hero rows are read-only tracking markers — no hover, no click,
            # no side-panel open. Passing no handler skips both the player
            # label hover-underline and the row click binding.
            row = HeroRow(self._list, entry, on_player_click=None)
        else:
            row = MessageRow(
                self._list,
                entry,
                self._dot_color_for(entry),
                on_select=self._handle_row_selected,
            )

        if self._row_matches_filter(row):
            row.pack(fill="x")
        self._rows.append(row)

        # New rows must inherit the current wraplength so they render at the
        # right width on first paint (rather than the MessageRow constructor
        # default that's then overwritten by the next resize).
        if isinstance(row, MessageRow) and self._last_wraplength > 80:
            row.set_body_wraplength(self._last_wraplength)

        # Flash the NEW badge on every newly-arrived chat row independently —
        # each row owns its own 2.5s timer, so a quick burst of messages all
        # show NEW until each fades on its own schedule.
        if isinstance(row, MessageRow):
            row.flash_new_badge()

        # Trim oldest widgets if we exceed the cap
        while len(self._rows) > _MAX_ROWS * 2:
            old = self._rows.pop(0)
            if old is self._selected_row:
                self._selected_row = None
                self._hide_side_panel()
            old.destroy()

        # If the side panel is open for this player, refresh its stats.
        # The panel reads from disk; live messages have already been written
        # to chat_log.csv by the backend logger before the GUI sees them.
        side_player = self._side_panel_player()
        if side_player and entry.player.strip().lower() == side_player.lower():
            self._refresh_side_panel(side_player)

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
        self._counts = {"team": 0, "all": 0}
        self._players_seen.clear()
        self._selected_row = None
        self._refresh_header_count()
        self._update_pill_counts()
        self._hide_side_panel()
        self._show_empty_state()
        self._hide_jump_pill()

    def _refresh_header_count(self) -> None:
        if self._count == 0:
            self._header_count.configure(text="waiting for first message")
            return
        msg_word = "message" if self._count == 1 else "messages"
        player_count = len(self._players_seen)
        if player_count == 0:
            self._header_count.configure(text=f"{self._count} {msg_word}")
        else:
            plr_word = "player" if player_count == 1 else "players"
            self._header_count.configure(
                text=f"{self._count} {msg_word} · {player_count} {plr_word}"
            )

    # ── Row selection / side panel ───────────────────────────────────────────

    def _handle_row_selected(self, row: MessageRow) -> None:
        # Toggle off if the same row is clicked again.
        if self._selected_row is row:
            row.set_selected(False)
            self._selected_row = None
            self._hide_side_panel()
            return
        if self._selected_row is not None:
            try:
                self._selected_row.set_selected(False)
            except Exception:
                pass
        row.set_selected(True)
        self._selected_row = row
        self._show_side_panel_for(row.player)

    def _show_side_panel_for(self, player: str) -> None:
        # Player panel takes priority over onboarding when both want col 2.
        self._hide_onboarding_panel()
        self._side_divider.grid(row=0, column=1, sticky="ns")
        self._side_panel.grid(row=0, column=2, sticky="ns")
        self._side_panel.show_player(player)

    def _refresh_side_panel(self, player: str) -> None:
        """Re-render the side panel after new rows arrive for this player."""
        if not player:
            return
        self._side_panel.show_player(player)

    def _side_panel_player(self) -> str:
        """Player currently shown in the side panel ('' if hidden).

        The selection can come from a clicked MessageRow OR a HeroRow player
        link, so we read it from the panel itself rather than the row state.
        """
        return getattr(self._side_panel, "_current_player", "") or ""

    def _hide_side_panel(self) -> None:
        self._side_panel.hide()
        self._side_panel.grid_remove()
        self._side_divider.grid_remove()
        # If the feed is currently empty, the onboarding panel should
        # reappear in the slot the player panel just vacated.
        if self._empty_frame is not None:
            self._show_onboarding_panel()

    def _deselect_and_hide_panel(self) -> None:
        if self._selected_row is not None:
            try:
                self._selected_row.set_selected(False)
            except Exception:
                pass
            self._selected_row = None
        self._hide_side_panel()

    # ── Onboarding panel ─────────────────────────────────────────────────────

    def _show_onboarding_panel(self) -> None:
        # Mutually exclusive with the player side panel — never grid both.
        if self._side_panel.winfo_ismapped():
            return
        self._onboarding_panel.refresh()
        self._side_divider.grid(row=0, column=1, sticky="ns")
        self._onboarding_panel.grid(row=0, column=2, sticky="ns")

    def _hide_onboarding_panel(self) -> None:
        if self._onboarding_panel.winfo_ismapped():
            self._onboarding_panel.grid_remove()
        # Keep the divider only if the player panel is showing.
        if not self._side_panel.winfo_ismapped():
            self._side_divider.grid_remove()

    # ── Resize handling ──────────────────────────────────────────────────────

    _RESIZE_DEBOUNCE_MS = 80  # quiet period after the last Configure event
    # Fixed column reservation: dot(24+8+14) + ts(64+14) + player(140+14) +
    # trailing(24) + NEW-badge headroom(44) — see MessageRow._build for the
    # canonical column layout this mirrors.
    _ROW_FIXED_WIDTH_PX = 46 + 78 + 154 + 24 + 44

    def _on_panel_resize(self, _event: tk.Event) -> None:
        """Debounce window resize: only flush wraplength after drag settles.

        During an active drag Tk fires Configure events at ~30 Hz. If every
        row reconfigured its body wraplength on each tick, that's hundreds
        of CTk redraws per second per visible row — a major source of
        resize lag. We schedule a single batch update once the user stops
        dragging (default 80 ms quiet period).
        """
        if self._wrap_after_id is not None:
            try:
                self.after_cancel(self._wrap_after_id)
            except Exception:
                pass
        self._wrap_after_id = self.after(self._RESIZE_DEBOUNCE_MS, self._flush_row_wraplength)

    def _flush_row_wraplength(self) -> None:
        self._wrap_after_id = None
        try:
            list_width = self._list.winfo_width()
        except tk.TclError:
            return
        available = list_width - self._ROW_FIXED_WIDTH_PX
        if available <= 80 or available == self._last_wraplength:
            return
        self._last_wraplength = available
        for row in self._rows:
            if isinstance(row, MessageRow):
                row.set_body_wraplength(available)

    # ── Status hook ──────────────────────────────────────────────────────────

    def set_status(self, kind: str) -> None:
        """Tell the panel what the recording status is.

        Used to gate the empty-state Start button so it only appears while
        idle. The app calls this from its own status dispatcher.
        """
        self._status_kind = kind
        if self._empty_start_btn is None:
            return
        if kind == "idle" and self._on_start is not None:
            if not self._empty_start_btn.winfo_ismapped():
                self._empty_start_btn.pack(pady=(20, 0))
        else:
            self._empty_start_btn.pack_forget()

    def _handle_open_in_search(self, player: str) -> None:
        if self._on_open_in_search is not None and player:
            self._on_open_in_search(player)

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
