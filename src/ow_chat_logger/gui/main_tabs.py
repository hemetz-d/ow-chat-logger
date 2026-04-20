from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable

import customtkinter as ctk

from ow_chat_logger.gui import icons as I
from ow_chat_logger.gui import theme as T
from ow_chat_logger.gui.feed_panel import FeedPanel
from ow_chat_logger.gui.search_panel import SearchView

_TAB_FEED = "Live Feed"
_TAB_SEARCH = "Search"

_TAB_ICONS = {
    _TAB_FEED: "message_square",
    _TAB_SEARCH: "search",
}


class MainTabs(ctk.CTkFrame):
    """Full-width pill-tab container hosting Live Feed and Search in-place.

    Both child views are long-lived: switching tabs packs/unpacks them, so
    state (search query, scroll position, feed contents) is preserved.
    """

    def __init__(
        self,
        master: tk.Widget,
        *,
        chat_log_path: Path,
        hero_log_path: Path,
        on_player_click: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")

        self._active: str = _TAB_FEED
        self._tab_buttons: dict[str, ctk.CTkButton] = {}

        self._build_tab_bar()

        # Content container — exactly one child packed at a time.
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True, pady=(10, 0))

        self.feed_panel = FeedPanel(self._content, on_player_click=on_player_click)
        self.search_view = SearchView(
            self._content,
            chat_log_path=chat_log_path,
            hero_log_path=hero_log_path,
        )

        self._pack_active()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build_tab_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x")
        bar.grid_columnconfigure(0, weight=1, uniform="tabs")
        bar.grid_columnconfigure(1, weight=1, uniform="tabs")
        bar.grid_rowconfigure(0, weight=1)

        for col, label in enumerate((_TAB_FEED, _TAB_SEARCH)):
            btn = ctk.CTkButton(
                bar,
                text=label,
                image=I.icon(_TAB_ICONS[label], 16, color=T.TEXT_SECONDARY),
                compound="left",
                height=42,
                corner_radius=T.R_BUTTON,
                font=T.font_button(),
                fg_color=T.BG_ELEV,
                hover_color=T.BORDER_HOVER,
                text_color=T.TEXT_SECONDARY,
                anchor="center",
                command=lambda lbl=label: self._on_tab_click(lbl),
            )
            btn.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 6, 0))
            self._tab_buttons[label] = btn

        self._apply_tab_styles()

    def _apply_tab_styles(self) -> None:
        for label, btn in self._tab_buttons.items():
            if label == self._active:
                btn.configure(
                    fg_color=T.ACCENT,
                    hover_color=T.ACCENT_HOVER,
                    text_color=T.ACCENT_FG,
                    image=I.icon(_TAB_ICONS[label], 16, color=T.pick(T.ACCENT_FG)),
                )
            else:
                btn.configure(
                    fg_color=T.BG_ELEV,
                    hover_color=T.BORDER_HOVER,
                    text_color=T.TEXT_SECONDARY,
                    image=I.icon(
                        _TAB_ICONS[label], 16, color=T.pick(T.TEXT_SECONDARY)
                    ),
                )

    # ── Public API ───────────────────────────────────────────────────────────

    def show_feed(self) -> None:
        if self._active == _TAB_FEED:
            return
        self._active = _TAB_FEED
        self._apply_tab_styles()
        self._pack_active()

    def show_search(self, *, player: str | None = None) -> None:
        if player:
            self.search_view.focus_player(player)
        if self._active != _TAB_SEARCH:
            self._active = _TAB_SEARCH
            self._apply_tab_styles()
            self._pack_active()
        if not player:
            self.search_view.focus_input()

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
        target = self.feed_panel if self._active == _TAB_FEED else self.search_view
        target.pack(fill="both", expand=True)
