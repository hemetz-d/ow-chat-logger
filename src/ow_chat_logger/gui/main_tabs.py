from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable

import customtkinter as ctk

from ow_chat_logger.gui import icons as I
from ow_chat_logger.gui import theme as T
from ow_chat_logger.gui.feed_panel import FeedPanel
from ow_chat_logger.gui.search_panel import SearchView
from ow_chat_logger.gui.settings_panel import SettingsPanel

_TAB_FEED = "Live Feed"
_TAB_SEARCH = "Search"
_TAB_SETTINGS = "Settings"

_TAB_ICONS = {
    _TAB_FEED: "message_square",
    _TAB_SEARCH: "search",
    _TAB_SETTINGS: "gear",
}


class MainTabs(ctk.CTkFrame):
    """Full-width pill-tab container hosting Live Feed, Search, and Settings.

    All three child views are long-lived: switching tabs packs/unpacks them,
    so state (search query, scroll position, feed contents, in-flight
    settings edits) is preserved across tab swaps. Settings was previously
    a Toplevel modal — moving it inline collapses two parallel widget trees
    into one, which fixes the staggered accent-refresh visual.
    """

    def __init__(
        self,
        master: tk.Widget,
        *,
        chat_log_path: Path,
        hero_log_path: Path,
        on_open_in_search: Callable[[str], None] | None = None,
        on_start: Callable[[], None] | None = None,
        on_settings_saved: Callable[[], None] | None = None,
        on_accent_change: Callable[[str], None] | None = None,
        current_accent: str = "blue",
        inline_tab_bar: bool = True,
    ) -> None:
        super().__init__(master, fg_color="transparent")

        self._active: str = _TAB_FEED
        self._tab_buttons: dict[str, ctk.CTkButton] = {}
        self._tab_change_listeners: list[Callable[[str], None]] = []

        if inline_tab_bar:
            self._build_tab_bar()

        # Content container — exactly one child packed at a time.
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True)

        self.feed_panel = FeedPanel(
            self._content,
            chat_log_path=chat_log_path,
            hero_log_path=hero_log_path,
            on_open_in_search=on_open_in_search,
            on_start=on_start,
        )
        self.search_view = SearchView(
            self._content,
            chat_log_path=chat_log_path,
            hero_log_path=hero_log_path,
        )
        self.settings_panel = SettingsPanel(
            self._content,
            on_save=on_settings_saved,
            on_accent_change=on_accent_change,
            current_accent=current_accent,
        )

        self._pack_active()

    # ── Observer hook (used by toolbar segmented control to stay in sync) ────

    def add_tab_change_listener(self, fn: Callable[[str], None]) -> None:
        self._tab_change_listeners.append(fn)

    @property
    def active_tab(self) -> str:
        return self._active

    # Labels exposed as constants for callers that build external tab UI.
    TAB_FEED = _TAB_FEED
    TAB_SEARCH = _TAB_SEARCH
    TAB_SETTINGS = _TAB_SETTINGS

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build_tab_bar(self) -> None:
        # Compact segmented control — a bordered surface2 tray with tight pills.
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="x")

        tray = ctk.CTkFrame(
            wrap,
            fg_color=T.BG_ELEV,
            border_color=T.BORDER_HAIRLINE,
            border_width=1,
            corner_radius=T.R_BUTTON,
        )
        tray.pack(side="left", padx=0, pady=0)

        for col, label in enumerate((_TAB_FEED, _TAB_SEARCH, _TAB_SETTINGS)):
            btn = ctk.CTkButton(
                tray,
                text=label,
                image=I.icon(_TAB_ICONS[label], 14, color=T.TEXT_MUTED),
                compound="left",
                height=28,
                width=110,
                corner_radius=T.R_BADGE,
                font=T.font_small(),
                fg_color="transparent",
                hover_color=T.BG_CARD,
                text_color=T.TEXT_MUTED,
                anchor="center",
                command=lambda lbl=label: self._on_tab_click(lbl),
            )
            btn.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
            self._tab_buttons[label] = btn

        self._apply_tab_styles()

    def _apply_tab_styles(self) -> None:
        # Active tab = elevated card over the tray; inactive = transparent muted.
        if not self._tab_buttons:
            return
        for label, btn in self._tab_buttons.items():
            if label == self._active:
                btn.configure(
                    fg_color=T.BG_CARD,
                    hover_color=T.BG_CARD,
                    text_color=T.TEXT_PRIMARY,
                    image=I.icon(_TAB_ICONS[label], 14, color=T.pick(T.TEXT_PRIMARY)),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    hover_color=T.BG_CARD,
                    text_color=T.TEXT_MUTED,
                    image=I.icon(_TAB_ICONS[label], 14, color=T.pick(T.TEXT_MUTED)),
                )

    # ── Public API ───────────────────────────────────────────────────────────

    def show_feed(self) -> None:
        if self._active == _TAB_FEED:
            return
        self._active = _TAB_FEED
        self._apply_tab_styles()
        self._pack_active()
        self._notify_tab_change()

    def show_search(self, *, player: str | None = None) -> None:
        if player:
            self.search_view.focus_player(player)
        if self._active != _TAB_SEARCH:
            self._active = _TAB_SEARCH
            self._apply_tab_styles()
            self._pack_active()
            self._notify_tab_change()
        if not player:
            self.search_view.focus_input()

    def show_settings(self) -> None:
        if self._active == _TAB_SETTINGS:
            return
        self._active = _TAB_SETTINGS
        self._apply_tab_styles()
        self._pack_active()
        self._notify_tab_change()

    def _notify_tab_change(self) -> None:
        for fn in self._tab_change_listeners:
            try:
                fn(self._active)
            except Exception:
                pass

    # ── Internals ────────────────────────────────────────────────────────────

    def _on_tab_click(self, label: str) -> None:
        if label == self._active:
            return
        self._active = label
        self._apply_tab_styles()
        self._pack_active()
        if label == _TAB_SEARCH:
            self.search_view.focus_input()

    def _pack_active(self) -> None:
        self.feed_panel.pack_forget()
        self.search_view.pack_forget()
        self.settings_panel.pack_forget()
        if self._active == _TAB_FEED:
            target: ctk.CTkBaseClass = self.feed_panel
        elif self._active == _TAB_SEARCH:
            target = self.search_view
        else:
            target = self.settings_panel
        target.pack(fill="both", expand=True)
